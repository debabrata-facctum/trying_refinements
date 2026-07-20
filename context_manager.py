"""
Context Manager for LocalMind.

Handles conversation trimming and optional summarization to keep
messages within the model's context window budget.
"""


class ContextManager:
    def __init__(self):
        self.summary_cache = ""  # rolling summary text
        self.summarized_count = 0  # how many messages have been summarized so far

    def trim_messages(self, messages, n_ctx, max_tokens, summarize_enabled, llm):
        """
        Main entry point. Returns a trimmed message list that fits within budget.

        Args:
            messages: list of {"role": str, "content": str} (already processed,
                      system prompt merged into first user message)
            n_ctx: context window size
            max_tokens: response token cap
            summarize_enabled: bool from frontend toggle
            llm: Llama instance (needed for tokenize + summarization)

        Returns:
            list of messages that fit within budget
        """
        budget = n_ctx - max_tokens
        threshold = int(budget * 0.75)

        # Tokenize all messages and get total
        message_tokens = []
        total_tokens = 0
        for msg in messages:
            tokens = self._count_tokens(msg["content"], llm)
            message_tokens.append(tokens)
            total_tokens += tokens

        # Fast path: everything fits
        if total_tokens <= threshold:
            return messages

        # Determine mode
        if n_ctx < 3000 or not summarize_enabled:
            result = self._sliding_window(messages, message_tokens, budget)
        else:
            result = self._summarize_and_protect(messages, message_tokens, budget, n_ctx, llm)

        # Guarantee strictly alternating roles before handing off to the model.
        return self._enforce_alternation(result)

    def _count_tokens(self, text, llm):
        """Count tokens for a string using the model's tokenizer."""
        if not text:
            return 0
        return len(llm.tokenize(text.encode("utf-8")))

    def will_summarize(self, messages, n_ctx, max_tokens, summarize_enabled, llm):
        """Predict whether trim_messages() will run a summarization pass.

        Lets the server notify the client that a (slow) summary is starting,
        before the blocking work happens. Mirrors the decision logic in
        trim_messages() without doing any summarization itself.
        """
        if not summarize_enabled or n_ctx < 3000 or len(messages) <= 2:
            return False
        budget = n_ctx - max_tokens
        threshold = int(budget * 0.75)
        total = 0
        for msg in messages:
            total += self._count_tokens(msg["content"], llm)
        return total > threshold

    def _sliding_window(self, messages, message_tokens, budget):
        """
        Keep newest messages that fit within budget.
        Always keeps the first message (contains system prompt merged in).
        """
        if not messages:
            return messages

        # Always keep the first message (system prompt merged into first user msg)
        first_msg_tokens = message_tokens[0]
        remaining_budget = budget - first_msg_tokens

        # Fill from newest to oldest (skip first message)
        kept_indices = []
        for i in range(len(messages) - 1, 0, -1):
            if message_tokens[i] <= remaining_budget:
                kept_indices.insert(0, i)
                remaining_budget -= message_tokens[i]
            else:
                break  # Stop at first message that doesn't fit

        # Assemble: first message + kept messages
        result = [messages[0]]
        for i in kept_indices:
            result.append(messages[i])

        return result

    def _summarize_and_protect(self, messages, message_tokens, budget, n_ctx, llm):
        """
        Summarize old messages, keep recent ones verbatim within protected budget.
        """
        if len(messages) <= 2:
            return messages

        # Budget allocations
        protected_budget = int(budget * 0.30)
        summary_cap = self._get_summary_cap(budget, n_ctx)

        # First message is always kept (has system prompt merged in)
        first_msg_tokens = message_tokens[0]

        # Build protected zone from newest messages (excluding first)
        # Work backwards from the end
        protected_indices = []
        protected_tokens_used = 0

        for i in range(len(messages) - 1, 0, -1):
            msg_tokens = message_tokens[i]
            if protected_tokens_used + msg_tokens <= protected_budget:
                protected_indices.insert(0, i)
                protected_tokens_used += msg_tokens
            else:
                # If we haven't protected anything yet, force-include the last message
                if not protected_indices:
                    protected_indices.append(i)
                    protected_tokens_used += msg_tokens
                break

        # Guarantee at least the very last message is protected
        if not protected_indices:
            protected_indices = [len(messages) - 1]
            protected_tokens_used = message_tokens[-1]

        # Everything between first message and protected zone = to_summarize
        protected_start = protected_indices[0]
        to_summarize_messages = messages[1:protected_start]

        # If nothing to summarize, just return what fits
        if not to_summarize_messages:
            return self._sliding_window(messages, message_tokens, budget)

        # Generate or update the rolling summary
        summary_text = self._generate_summary(
            self.summary_cache,
            to_summarize_messages,
            summary_cap,
            llm
        )

        # Cache the summary
        self.summary_cache = summary_text
        self.summarized_count = protected_start - 1  # messages summarized so far

        # Assemble final messages:
        # [first message (with system prompt)] + [summary as context] + [protected messages]
        result = [messages[0]]

        # Insert summary as a user message providing context
        if summary_text.strip():
            summary_msg = {
                "role": "user",
                "content": f"[Earlier conversation summary: {summary_text}]"
            }
            result.append(summary_msg)
            # Add a brief assistant acknowledgment so the conversation flow is valid
            result.append({
                "role": "assistant",
                "content": "Understood, I have the context from our earlier conversation."
            })

        # Add protected messages
        for i in protected_indices:
            result.append(messages[i])

        return result

    def _generate_summary(self, old_summary, new_messages, summary_cap, llm):
        """
        Run inference to produce/update the rolling summary.

        Args:
            old_summary: previous summary text (empty string if first time)
            new_messages: list of message dicts to summarize
            summary_cap: max tokens for the summary output
            llm: Llama instance

        Returns:
            summary text string
        """
        # Build the content to summarize
        conversation_text = ""
        for msg in new_messages:
            role = msg["role"].capitalize()
            conversation_text += f"{role}: {msg['content']}\n\n"

        # Build the summarization prompt
        if old_summary:
            prompt = (
                f"Previous conversation summary:\n{old_summary}\n\n"
                f"New messages to incorporate:\n{conversation_text}\n"
                f"Write an updated summary in 2-4 sentences. "
                f"Preserve key facts, decisions, and context needed to continue the conversation."
            )
        else:
            prompt = (
                f"Conversation to summarize:\n{conversation_text}\n"
                f"Write a summary in 2-4 sentences. "
                f"Preserve key facts, decisions, and context needed to continue the conversation."
            )

        # Run inference for summarization
        try:
            response = llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=summary_cap,
                stream=False
            )
            summary = response["choices"][0]["message"]["content"].strip()
            print(f"DEBUG: Generated summary ({len(summary)} chars, ~{self._count_tokens(summary, llm)} tokens)")
            return summary
        except Exception as e:
            print(f"ERROR: Summarization failed: {e}")
            # Fallback: return old summary if summarization fails
            return old_summary or ""

    def _get_summary_cap(self, budget, n_ctx):
        """Calculate the maximum tokens allowed for the summary."""
        if n_ctx < 4096:
            return min(300, budget // 10)
        else:
            return budget // 10

    def _enforce_alternation(self, messages):
        """Merge consecutive same-role messages so roles strictly alternate.

        llama.cpp chat templates (Llama, Mistral, Gemma, etc.) require the
        conversation to alternate user/assistant/user/... Trimming and summary
        injection can leave two messages with the same role in a row (e.g. the
        first user message followed by the summary user message). This collapses
        any such runs by concatenating their content, producing a valid
        alternating sequence that still begins with 'user'.
        """
        if not messages:
            return messages
        merged = [dict(messages[0])]
        for msg in messages[1:]:
            if msg["role"] == merged[-1]["role"]:
                merged[-1]["content"] = f"{merged[-1]['content']}\n\n{msg['content']}"
            else:
                merged.append(dict(msg))
        return merged

    def reset(self):
        """Clear summary cache (called when user starts new chat)."""
        self.summary_cache = ""
        self.summarized_count = 0
