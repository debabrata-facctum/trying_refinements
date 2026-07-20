# LocalMind — Development Logic (v2)

Design decisions and implementation notes for the v2. The engine-level logic
(context management, response-length hint) is carried over from v1 unchanged and
documented here for completeness. The v2-specific sections cover the UI rebuild
and the backend additions that feed it.

---

## v2 Overview

v2 is a front-end rebuild of LocalMind onto a llama.cpp-style shell (sidebar +
topbar + floating composer + overlays), plus small backend additions to power
new live-feedback features. No v1 capability was removed.

> **Design lineage:** the v2 look is heavily inspired by the web UI bundled with
> llama.cpp's `llama-server`. It's an independent reimplementation (our own
> HTML/CSS/JS), not a copy of their code — see the Acknowledgments in the README.

| Area | v1 | v2 |
|------|----|----|
| Page model | `index.html` + `script.js` + `style.css` | Single page: `index.html` + `app.js` + `styles.css` |
| Layout | Header + centered chat + input bar | Sidebar (collapsible rail) + topbar + floating composer |
| Settings | One large modal | In-app overlay with **General** + **Sampling** + **Export** tabs |
| Connection | Binary dot (reachable or not) | **Three-state** dot (loaded / no-model / disconnected) |
| Per-turn info | None | **Token stats** per message (user + assistant) |
| Context display | None | **Real-token usage ring** + popover |
| Model details | None | **Model Info card** with GGUF specs + runtime config |
| Copy / edit | None | Copy toast; edit-and-resend on user messages |
| Chat stream | `{done:true}` | `{done:true, stats:{...}}` |
| model-status | runtime config only | + GGUF specs (`training_ctx`, `n_params`, ...) |

---

## Front-end architecture (v2)

### Single page, class-driven state

The whole UI lives in one `index.html`. State is expressed through classes on the
root `#app`:

- `.collapsed` — sidebar shrinks to the icon rail (toggled from the topbar).
- `.generating` — send button becomes a stop control and the "Generating…" dots show.

Overlays (`#settingsOverlay`, `#modelOverlay`, `#file-browser-modal`) use a shared
`.overlay` + `.open` pattern. `app.js` toggles `.open`; CSS handles display.

### Collapsible sidebar → icon rail

**Decision:** collapse to a 56px rail instead of hiding the sidebar entirely.

**Reasoning:** fully hiding removes navigation and branding; a rail keeps New chat /
Settings reachable and keeps the brand present. When collapsed:
- `.brand-word` (LocalMind) is hidden, `.brand-mark` ("LM" monogram) is shown.
- `.nav-label` spans hide, leaving centered icons; `title` attributes provide tooltips.

A CSS specificity note: `.field > label { display:block }` was overriding
`.toggle-label { display:flex }`, collapsing toggle pills. Fixed by raising the
toggle selector to `.field > label.toggle-label`.

### Settings as an overlay with tabs

**Decision:** in-app overlay (not a separate page/route), with **General**,
**Sampling**, and **Export** tabs.

**Reasoning:** the server serves a single `index.html`; an overlay keeps everything
client-side with no reload. The "+" tools menu from the reference mock was dropped
(no backend for it). Every v1 setting is folded into the General/Sampling tabs so
nothing is lost. **Export** was added later as a third tab — it needs no backend
(the download is built entirely in the browser, see *Chat export* below), so it fits
the client-side overlay model cleanly.

Tab switching is generic: the nav buttons carry `data-page` and each panel a matching
`data-content`; clicking a tab shows the panel whose `data-content` matches. The shared
Reset/Save footer applies only to General/Sampling, so it's hidden when the Export tab
is active (there's nothing to save there).

### Message rendering

`addMessage(text, sender)` builds either a `.msg.user` (bubble + copy/edit actions)
or a `.msg.assistant` (`.md-body` markdown + copy action). Markdown is rendered with
`marked` and highlighted with `highlight.js`. Assistant "regenerate" was removed as
not relevant to the current flow.

**Edit-and-resend:** editing a user message removes that message and everything after
it (DOM + `state.history`), recomputes the running token total from the remaining
messages' `data-tokens`, and drops the text back into the composer.

### Cache-busting

`app.js` and `styles.css` are referenced with `?v=N`. Bump `N` on change so browsers
reload. `index.html` is unversioned — a one-time hard reload is expected after HTML
edits.

---

## End-of-answer stats

### Server

In `/api/chat`, the server:
1. Captures the last user message and counts its tokens with `count_tokens()`
   (`llm.tokenize(...)`, with a word-based fallback if no model/tokenizer).
2. Times generation with `time.perf_counter()` and accumulates the streamed text.
3. Counts completion tokens from the accumulated text.
4. Emits a final chunk: `{"done": true, "stats": {user_tokens, completion_tokens, elapsed_s, tokens_per_s}}`.

The non-streaming path returns the same `stats` object in its JSON body.

### Client

`handleSendMessage()` keeps references to the current user + assistant message
elements. On the final chunk it calls `renderStats()`:
- user message → a `.meta-row` with the token count, and `data-tokens` for later recompute.
- assistant message → a `.answer-footer` with a model pill and `tokens / elapsed_s / tokens_per_s`.

**Why re-tokenize the completion instead of counting stream deltas:** stream deltas
don't map 1:1 to tokens; tokenizing the final text gives an accurate count.

**Caveat:** `user_tokens` is the last user message alone, not the full prompt
(system + history) sent to the model. It intentionally mirrors the per-message
display in the reference UI.

---

## Context-usage meter (v2)

### Decision: real tokenizer counts, no estimation

v1 had no meter. An early v2 draft used a `words × 1.3` client estimate — inaccurate.
Replaced with real counts: the client accumulates `stats.user_tokens +
stats.completion_tokens` per turn into `contextTokens`, and displays
`contextTokens / n_ctx`.

- Reset to 0 on **New chat** (also calls `/api/reset-context`).
- Gated on `modelLoaded`: shows **`0 / 0`** and an empty ring when no model is loaded,
  so a default `n_ctx` never appears as if a model were configured.
- The ring is an SVG progress circle driven by `stroke-dashoffset`; amber ≥ 75%, red ≥ 90%.

**Caveat:** this sums the exchanged message tokens (the conversation size from the
tokenizer). It does not add system-prompt tokens or llama.cpp's internal prompt
formatting overhead, so it can read slightly lower than the engine's exact KV fill.
It's tokenizer-accurate for conversation content and library-free.

---

## Connection status (three-state)

`/api/tags` only reports reachability, so v1's dot was effectively always "on".
v2 combines reachability with model state:

```
fetch /api/tags:
  not ok            → red    "Disconnected"
  ok → fetch /api/model-status:
       status==loaded → green "Model loaded"
       else           → amber "No model loaded"
```

Refreshed on startup, after saving settings, and immediately after a successful load.

---

## Model spec introspection (v2)

### Decision: read from the loaded model, expose via model-status

We only show the info card after a model loads, so the loaded `Llama` object is the
simplest source (vs. parsing GGUF headers without loading — a possible future
enhancement for previewing unloaded files).

### Implementation

`extract_model_specs(model, path)` reads:
- `training_ctx` ← `n_ctx_train()`
- `n_embd`, `n_vocab` ← model introspection
- `n_params` ← parameter count
- `file_size_bytes` ← `os.path.getsize(path)` (reliable), tensor `size()` as fallback
- `desc` ← model description string

Every read is attempted against both the high-level `Llama` object and its internal
`_model` handle via a `_first_ok(*getters)` helper, because method names vary across
`llama-cpp-python` versions. Anything unavailable degrades to `None` → "—" in the UI.

Specs are stored in `model_state` at load time and returned by `/api/model-status`.
The card separates **model specs** (from the GGUF) from **runtime config** (what it
was loaded with), and shows "—" for all of them until `status == "loaded"`.

---

## Static file serving (v2)

`server.py` computes `BASE_DIR = os.path.abspath(os.path.dirname(__file__))` and mounts
FastAPI's `StaticFiles(directory=BASE_DIR, html=True)` at `/` to serve `index.html` and
all static assets (v1 used a CWD-relative `FileResponse("index.html")`). This lets the
server run correctly regardless of the directory it's launched from.

**Why `StaticFiles` instead of hand-rolled routes:** an earlier v2 draft used a custom
`/{file_path:path}` catch-all with manual path-traversal checks and an allowed-extension
whitelist. `StaticFiles` already handles traversal safety, so the custom route was
replaced with the one-line mount — less code, and a standard component readers can trust
at a glance. The mount is registered **after** all `/api/*` routes, so those take
precedence and only unmatched paths fall through to static serving.

---

## Chat export (v2)

### Decision: client-side JSON, no backend

The current conversation can be downloaded as a JSON file from the **Export** settings
tab. There is deliberately **no server endpoint** for this — the conversation already
lives in the browser (`state.history`), so export is built there with a `Blob` and a
temporary `<a download>` click. No new route, no new dependency.

This intentionally does *not* implement the full ConversationStore / ZIP-of-JSONL design
in `docs/WEBUI_LOGIC.md` — that's a larger multi-conversation persistence feature. Export
here is scoped to "save the conversation I'm looking at."

### Data shape

```json
{
  "app": "LocalMind",
  "exported_at": "<ISO-8601>",
  "model": "<model name or null>",
  "system_prompt": "<text>",
  "messages": [
    { "role": "user",      "content": "…", "stats": { "tokens": 18 } },
    { "role": "assistant", "content": "…", "stats": { "tokens": 42, "elapsed_s": 6.2, "tokens_per_s": 6.82 } }
  ]
}
```

### Implementation notes

- **`buildExportObject()`** assembles the object above from `state.history` + session
  state; **`exportChat()`** serializes it and triggers the download. They're split so the
  data shape is easy to inspect/verify independently of the DOM/download.
- **Stats capture:** each turn's stats are stored on the pushed `state.history` items
  (`user` → `{tokens}`, `assistant` → `{tokens, elapsed_s, tokens_per_s}`) at the moment
  they're rendered. The extra `stats` key is harmless to `/api/chat` — the server's
  `ChatMessage` model ignores unknown fields.
- **Empty guard:** exporting with no messages is a no-op that shows a "Nothing to export"
  toast rather than downloading an empty file.
- **Filename:** `localmind-chat-<timestamp>.json`.

---

## Context Manager (carried over from v1)

### Problem

Every chat request sends the entire conversation history to the model. Without
trimming, an 8k context window fills up in ~8–10 exchanges and the model silently
truncates or produces garbage.

### Solution

Two layers:
1. **Sliding window** (always active) — drop oldest messages when budget is exceeded.
2. **Summarization** (opt-in) — compress dropped messages into a rolling summary first.

### Design decisions

| Decision | Choice | Reasoning |
|----------|--------|-----------|
| Where to trim | Server-side | Has `llm.tokenize()` for exact counts |
| `max_tokens` required | Yes (default 512) | Budget can't be computed without it |
| Summary toggle | Opt-in (OFF) | Summarization adds latency |
| n_ctx < 3000 | Sliding window only | Too little room for summary to help |
| n_ctx ≥ 3000 | Full logic | Enough headroom for summary value |
| Drop granularity | Complete pairs | Never split a message |
| Summary style | Rolling | Avoids re-summarizing whole history |

### Budget allocation (after trim)

```
Total budget = n_ctx - max_tokens (100%)
  System prompt:  ~1%
  Summary:        10%  (when enabled)
  Protected zone: 30%  (recent pairs, verbatim)
  Headroom:       ~59% (free for new messages)
```

### Summary token cap

```python
if n_ctx < 4096:
    summary_cap = min(300, budget // 10)
else:
    summary_cap = budget // 10   # scales freely
```

### Protected zone (token-budgeted)

30% of the input budget, filled newest→oldest until full; always at least one pair.
Short exchanges protect more pairs, long exchanges fewer — always leaving ~60%
headroom after a trim.

### Logic flow

```
1. Request arrives (messages + summarize flag + max_tokens)
2. budget = n_ctx - max_tokens; threshold = budget * 0.75
3. Tokenize all messages
4. total ≤ threshold → send as-is (fast path)
5. total > threshold:
   a. n_ctx < 3000 OR toggle OFF → sliding window
   b. n_ctx ≥ 3000 AND toggle ON → summarize + protect
6. Pass final messages to create_chat_completion(...)
```

### Summarization

Event-driven (only when messages are about to drop), batched, cached, and rolling
(`old_summary + newly_dropped → updated_summary`). The summary call uses
`stream=False` and `max_tokens = summary_cap`.

Prompt:

```
Here is the previous conversation summary: {old_summary}
Here are additional messages to incorporate: {newly_dropped_messages}
Write an updated summary in 2-3 sentences. Preserve key facts, decisions, and
context that would help continue the conversation.
```

### Edge cases

| Case | Handling |
|------|----------|
| Single message exceeds budget | Can't happen if max_tokens is set |
| Threshold mid-message | Drop complete pairs only |
| n_ctx < 3000 with toggle ON | Ignore toggle → sliding window |
| Summary cache stale | Invalidated when new messages drop |
| First request | Fits, no trimming |
| New chat | Reset summary cache (`/api/reset-context`) |
| Last pair > 30% | Always protect ≥ 1 pair |

---

## Response Length Hint (carried over from v1)

### Problem

With a hard `max_tokens` cap, the model has no awareness of the limit and gets cut
off mid-sentence.

### Solution

Inject a dynamic length instruction into the system prompt each request:

```python
word_limit = int(max_tokens * 0.75)   # 1 token ≈ 0.75 words
length_hint = f"\nKeep your response concise and complete within approximately {word_limit} words."
system_instruction += length_hint
```

Appended server-side (invisible to the user), dynamic with `max_tokens`, best-effort
(small models may overshoot), with the hard cap as the safety net.

| max_tokens | word_limit |
|-----------|-----------|
| 256 | ~192 |
| 512 | ~384 |
| 1024 | ~768 |
| 2048 | ~1536 |

### Limitations

- Small models (4B) are unreliable at following length constraints.
- May over-constrain (shorter than needed).
- Code-heavy responses are dense and harder to fit in a word budget.
