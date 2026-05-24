# LocalMind — Development Logic

This file documents the design decisions, logic, and implementation plans for features in development.

---

## Context Manager

### Problem

Every chat request sends the entire conversation history to the model. With unlimited response length and no trimming, an 8k context window fills up in ~8-10 exchanges. The model then silently truncates or produces garbage output.

### Solution

A two-layer context management system:
1. **Sliding window** (always active) — drops oldest messages when budget is exceeded
2. **Summarization** (opt-in toggle) — compresses dropped messages into a rolling summary before discarding them

### Design Decisions

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Where to trim | Server-side | Has access to `llm.tokenize()` for exact token counts |
| `max_tokens` required | Yes (default 512) | Without it, budget can't be calculated deterministically |
| Summary toggle | Opt-in (OFF by default) | Summarization adds latency; not everyone wants it |
| n_ctx < 3000 | Sliding window only, toggle ignored | Too little room for summary to be useful |
| n_ctx ≥ 3000 | Full logic (sliding window + optional summary) | Enough headroom for summary to add value |
| Drop granularity | Complete message pairs (user + assistant) | Never split a message mid-content |
| Summary style | Rolling (old_summary + newly_dropped → updated_summary) | Avoids re-summarizing entire history each time |

### Budget Allocation (after trim)

```
Total budget = n_ctx - max_tokens (100%)

After a trim event, the budget is split:
  System prompt:    ~1%  (fixed, small)
  Summary:          10%  (rolling compressed context)
  Protected zone:   30%  (recent exchanges, verbatim)
  Headroom:         ~59% (free space for new messages)
```

This guarantees ~60% headroom after every trim, regardless of context window size.

### Summary Token Cap

```python
if n_ctx < 4096:
    summary_cap = min(300, budget // 10)
else:
    summary_cap = budget // 10   # no upper cap, scales freely
```

| n_ctx | budget | summary cap |
|-------|--------|-------------|
| 3072  | 2560   | 256         |
| 3584  | 3072   | 300         |
| 4096  | 3584   | 358         |
| 8192  | 7680   | 768         |
| 16384 | 15360  | 1536        |

### Protected Zone (Token-Budgeted)

The protected zone is NOT a fixed number of messages. It's a **token budget** — 30% of the total input budget.

```python
protected_budget = budget * 0.30

# Fill from newest to oldest, stop when budget is full
protected = []
tokens_used = 0
for pair in reversed(message_pairs):
    pair_tokens = tokenize(pair)
    if tokens_used + pair_tokens > protected_budget:
        break
    protected.insert(0, pair)
    tokens_used += pair_tokens
```

**Why token-budgeted instead of fixed count:**

A fixed "last 3 pairs" could consume anywhere from 500 to 3072 tokens depending on message length. On a 4k context window, 3 maxed-out responses would eat 86% of the budget — leaving almost no headroom after a trim.

With 30% budget allocation, the protected zone adapts:
- Short exchanges → more pairs fit (5-7 exchanges protected)
- Long exchanges → fewer pairs fit (1-2 exchanges protected)
- Always leaves exactly 60% headroom after trim (100% - 30% protected - 10% summary)

**Guaranteed minimum:** at least 1 pair (the most recent exchange) is always protected, even if it alone exceeds 30%. This ensures the model always sees the last user message + response.

| n_ctx | budget | protected budget (30%) | typical pairs protected |
|-------|--------|----------------------|------------------------|
| 3072  | 2560   | 768                  | 2-3 exchanges          |
| 4096  | 3584   | 1075                 | 3-4 exchanges          |
| 8192  | 7680   | 2304                 | 5-7 exchanges          |
| 16384 | 15360  | 4608                 | 10-15 exchanges        |

### Logic Flow

```
1. Request arrives with messages + summarize flag + max_tokens

2. Calculate budget:
   budget = n_ctx - max_tokens
   threshold = budget * 0.75

3. Tokenize all messages, get total

4. If total ≤ threshold → send as-is (fast path, most common)

5. If total > threshold → determine mode:
   a. n_ctx < 3000 OR toggle OFF → SLIDING WINDOW
      - Keep system prompt
      - Fill from newest to oldest until budget full
      - Drop the rest
      - Final: [system] + [newest messages that fit]

   b. n_ctx ≥ 3000 AND toggle ON → SUMMARIZE + PROTECT
      - Calculate protected_budget = budget * 0.30
      - Fill protected zone from newest pairs until protected_budget full
        (always include at least 1 pair minimum)
      - Everything else = to_summarize
      - Calculate summary_cap:
        if n_ctx < 4096: min(300, budget // 10)
        else: budget // 10
      - Generate summary:
        input = old_summary (if exists) + to_summarize messages
        prompt = "Summarize preserving key facts and decisions"
        output capped at summary_cap tokens
      - Cache the summary
      - Final: [system] + [summary as system msg] + [protected pairs]

6. Pass final messages to llm.create_chat_completion(max_tokens=max_tokens, stream=True)
```

### Summarization Frequency

NOT time-based or every-K-messages. Event-driven:
- Triggers only when messages are about to be dropped
- Batched: when threshold hit, drop enough to get back under budget (not just 1 message)
- Cached: same summary reused until new messages get dropped
- Rolling: when new messages drop, feed old_summary + new_drops → updated_summary

### Summarization Prompt

```
"Here is the previous conversation summary: {old_summary}

Here are additional messages to incorporate:
{newly_dropped_messages}

Write an updated summary in 2-3 sentences. Preserve key facts, decisions, and context that would help continue the conversation."
```

Summary call parameters:
- max_tokens = summary_cap
- stream = False (we need the full result before proceeding)

### Edge Cases

| Case | Handling |
|------|----------|
| Single message exceeds entire budget | Can't happen if max_tokens is set (response capped) |
| Threshold falls mid-message | Drop in complete pairs, never split |
| n_ctx < 3000 with toggle ON | Ignore toggle, use sliding window |
| Summary cache stale | Invalidated when new messages get dropped |
| First request (no history) | Fits in budget, no trimming |
| User clears chat | Reset summary cache |
| Last pair alone exceeds 30% budget | Always protect at least 1 pair (override budget) |
| Protected zone has 0 pairs (impossible) | Guaranteed minimum of 1 pair |

### Implementation Plan

**File: `context_manager.py`**

```python
class ContextManager:
    def __init__(self):
        self.summary_cache = ""  # rolling summary text
        self.summarized_count = 0  # how many messages have been summarized

    def trim_messages(self, messages, n_ctx, max_tokens, summarize_enable
        """
        Main entry point. Returns trimmed message list ready for inference.
        
        Args:
            messages: list of {"role": str, "content": str}
            n_ctx: context window size
            max_tokens: response token cap
            summarize_enabled: bool from frontend toggle
            llm: Llama instance (needed for tokenize + summarization)
        
        Returns:
            list of messages that fit within budget
        """
        pass

    def _tokenize_count(self, text, llm):
        """Count tokens for a string using the model's tokenizer."""
        pass

    def _sliding_window(self, messages, budget, llm):
        """Keep newest messages that fit within budget."""
        pass

    def _summarize_and_protect(self, messages, budget, summary_cap, llm):
        """Summarize old messages, keep recent ones verbatim."""
        pass

    def _generate_summary(self, old_summary, new_messages, summary_cap, llm):
        """Run inference to produce/update the rolling summary."""
        pass

    def reset(self):
        """Clear summary cache (called when user starts new chat)."""
        self.summary_cache = ""
        self.summarized_count = 0
```

**Changes to `server.py`:**
- Import `ContextManager`
- Instantiate globally: `ctx_manager = ContextManager()`
- In `/api/chat`: call `ctx_manager.trim_messages()` before `create_chat_completion()`
- Add `max_tokens` and `summarize` fields to `ChatRequest` model

**Changes to `script.js`:**
- Send `max_tokens` and `summarize` in the request body
- Read from localStorage (persisted settings)

**Changes to `index.html`:**
- Add `max_tokens` slider in settings (range: 128–2048, default 512)
- Add "Summarize old context" toggle switch

**Changes to `style.css`:**
- Toggle switch styles

### Frontend Settings Addition

```
| Parameter | Default | Range |
|-----------|---------|-------|
| max_tokens | 512 | 128 – 2048 |
| Summarize old context | OFF | ON/OFF toggle |
```

---

## Response Length Hint

### Problem

When `max_tokens` is set, the model has no awareness of the limit. It generates freely until the hard cap cuts it off mid-sentence, resulting in abrupt incomplete answers.

### Solution

Inject a dynamic length instruction into the system prompt on every request. The model is told (in words) how long its response should be, so it attempts to wrap up naturally within the budget.

### Implementation

In `server.py`, after collecting the system prompt from the request:

```python
word_limit = int(max_tokens * 0.75)  # tokens → approximate words
length_hint = f"\nKeep your response concise and complete within approximately {word_limit} words."
system_instruction += length_hint
```

### Token-to-Word Conversion

Uses the standard English approximation: **1 token ≈ 0.75 words**.

| max_tokens | word_limit in prompt |
|-----------|---------------------|
| 256       | ~192 words          |
| 512       | ~384 words          |
| 1024      | ~768 words          |
| 2048      | ~1536 words         |

### Behavior

- The hint is appended server-side — the user doesn't see it in their system prompt field
- It's dynamic: changes immediately when the user updates `max_tokens` in settings
- It's a best-effort instruction — small models (4B) may still overshoot
- The hard `max_tokens` cap remains as a safety net for when the model ignores the hint
- Combined effect: fewer abrupt cutoffs because the model *tries* to finish within budget

### Limitations

- Small models (4B) are unreliable at following length constraints
- The model may produce shorter answers than necessary (over-constraining)
- Code-heavy responses are harder to fit in word limits (code is dense)

---
d, llm):