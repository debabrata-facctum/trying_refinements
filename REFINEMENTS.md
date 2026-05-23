# Refinements — Cross-Platform, Performance & Stability

A running list of issues and planned updates to make this project work reliably on any OS, adapt to the user's hardware, and avoid subtle bugs in long sessions.

Items are grouped by priority. Each item has a status tracker:
- 🔴 Not started
- 🟡 Partially addressed
- 🟢 Done

---

## Priority: HIGH

These should be tackled first. They affect whether the app runs at all on a new machine, or introduce security/stability risks.

---

### 1. Config File — Remove All Hardcoded Values �

**Covers:** Model path, threads, GPU layers, context size, host, port.

**What was done:** The server no longer hardcodes a model path. Users pick any `.gguf` file through the built-in file browser UI and configure `n_ctx`, `n_threads`, and `n_gpu_layers` from the Settings panel. Model loading happens on-demand via the `/api/load-model` endpoint — no source code editing required.

---

### 2. Static File Serving Security (Path Traversal) 🟡

**Problem:** The catch-all route `/{file_path:path}` in `server.py` serves any file relative to the working directory. No path sanitization. If someone runs the server from their home directory, a crafted request like `GET /../../.ssh/id_rsa` could leak sensitive files.

**Target fix:**

```python
from pathlib import Path

STATIC_DIR = Path(__file__).parent.resolve()

@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    resolved = (STATIC_DIR / file_path).resolve()
    if not str(resolved).startswith(str(STATIC_DIR)):
        raise HTTPException(status_code=403, detail="Access denied")
    if resolved.is_file():
        return FileResponse(resolved)
    raise HTTPException(status_code=404, detail="File not found")
```

---

### 3. Bundle CDN Dependencies for Offline Use 🔴

**Problem:** `index.html` loads `marked.js` and `highlight.js` from CDNs. The whole point of this project is running locally/offline. If the network is down, markdown rendering silently fails — AI responses show up as raw text with `**bold**` markers visible.

**Fix:**
1. Download `marked.min.js` and `highlight.min.js` + the `github-dark.min.css` theme.
2. Put them in a `vendor/` folder.
3. Update `index.html` to load from `vendor/` first, with CDN as fallback.

```html
<!-- Local first, CDN fallback -->
<script src="vendor/marked.min.js"></script>
<script>
  if (typeof marked === 'undefined') {
    document.write('<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"><\/script>');
  }
</script>
```

---

### 4. Conversation History & Persistence with SQLite 🔴

**Problem:** `state.history` in `script.js` grows without limit. Every message ever sent gets included in the next API call. Once the total tokens exceed `n_ctx`, the model returns an empty response (no output at all — confirmed on this setup with 2048 context). No error, no warning — just silence.

**Solution:** Save all conversations to a local SQLite database, support multiple conversations with a sidebar ("New Chat"), and implement server-side history trimming so the model always has room to respond.

**Why SQLite over localStorage:**
- Unlimited storage (localStorage caps at ~5-10MB)
- Supports full-text search across all past conversations
- Proper relational structure (conversations → messages)
- Easy to export/backup (single `.db` file)
- Python's `sqlite3` is in the stdlib — no extra install needed

---

#### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│  FRONTEND (Browser)                                                     │
│                                                                         │
│  ┌──────────────┐    ┌──────────────────────────────────────────────┐   │
│  │   Sidebar    │    │              Main Chat Area                  │   │
│  │              │    │                                              │   │
│  │ • New Chat   │    │  ┌─────────────────────────────────────────┐ │   │
│  │ • Chat 1     │◄──►│  │  Messages (loaded from DB via API)      │ │   │
│  │ • Chat 2     │    │  │  - User: "What is Python?"              │ │   │
│  │ • Chat 3     │    │  │  - AI: "Python is a programming..."     │ │   │
│  │              │    │  │  - User: "How do I install it?"         │ │   │
│  │              │    │  │  - AI: "You can download..."            │ │   │
│  └──────────────┘    │  └─────────────────────────────────────────┘ │   │
│                      │                                              │   │
│                      │  ┌─────────────────────────────────────────┐ │   │
│                      │  │  Input: [Type a message...] [Send]      │ │   │
│                      │  └─────────────────────────────────────────┘ │   │
│                      └──────────────────────────────────────────────┘   │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │ HTTP (fetch)
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI + Python)                                             │
│                                                                         │
│  ┌─────────────────────┐    ┌────────────────────────────────────────┐  │
│  │      db.py           │    │         Model (llama-cpp-python)       │  │
│  │                      │    │                                        │  │
│  │  • init_db()         │    │  • Loaded on demand via UI             │  │
│  │  • create_convo()    │    │  • Receives trimmed messages           │  │
│  │  • save_message()    │    │  • Generates response (stream/batch)   │  │
│  │  • list_convos()     │    │  • n_ctx configurable from Settings    │  │
│  │  • get_messages()    │    │  • max_tokens reserved for response    │  │
│  │  • delete_convo()    │    │                                        │  │
│  └──────────┬───────────┘    └────────────────────────────────────────┘  │
│             │                                                            │
│             ▼                                                            │
│  ┌──────────────────────┐                                                │
│  │   SQLite (chats.db)  │                                                │
│  │                      │                                                │
│  │  conversations table │  ◄── id, title, created_at, updated_at         │
│  │  messages table      │  ◄── id, conversation_id, role, content, ts    │
│  └──────────────────────┘                                                │
└──────────────────────────────────────────────────────────────────────────┘
```

---

#### Database Schema

```sql
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation 
ON messages(conversation_id, timestamp);
```

---

#### Server-Side History Trimming

Before sending messages to the model, trim to fit the context window:

```python
MAX_RESPONSE_TOKENS = 1024
MAX_PROMPT_TOKENS = n_ctx - MAX_RESPONSE_TOKENS

def trim_to_fit(messages, max_tokens, llm):
    """Remove oldest messages (keeping system) until prompt fits."""
    while len(messages) > 2:
        prompt_text = "\n".join(m["content"] for m in messages)
        token_count = len(llm.tokenize(prompt_text.encode()))
        if token_count <= max_tokens:
            break
        messages.pop(1)  # Remove oldest non-system message
    return messages
```

The user sees the full conversation (loaded from DB). The model only gets what fits. Both are correct.

---

### 5. Add `max_tokens` to Generation Calls 🔴

**Problem:** The server doesn't set `max_tokens` on `create_chat_completion()`. Without it, the model generates until it hits the context limit or produces an end token. On some prompts this means very long generation times (30+ seconds) with no way to control output length.

**Fix:** Add a sensible default and expose it in the Settings UI.

```python
result = llm.create_chat_completion(
    messages=conversation,
    max_tokens=config.get("max_tokens", 512),
)
```

---

## Priority: MEDIUM

Important for polish and broader compatibility, but the app works without these.

---

### 6. `llama-cpp-python` Installation Guide 🔴

**Problem:** `pip install llama-cpp-python` requires a C++ compiler. On Windows this means Visual Studio Build Tools (~6 GB install). GPU support needs CUDA toolkit + a special pip index URL. Most beginners hit a wall here.

**Fix:** The README now includes platform-specific install commands. Consider adding a `Makefile` or `setup.sh` that auto-detects the OS and runs the right command.

---

### 7. Pin Dependency Versions 🔴

**Problem:** `requirements.txt` has no version pins:
```
fastapi
uvicorn
llama-cpp-python
```

A future `pip install` could pull a breaking change. `llama-cpp-python` in particular has frequent breaking changes between versions.

**Fix:**
```
fastapi>=0.115.0,<1.0.0
uvicorn>=0.34.0,<1.0.0
llama-cpp-python>=0.3.0,<1.0.0
```

---

### 8. Hardware Auto-Detection (GPU Availability) 🔴

**Problem:** Setting `n_gpu_layers` to a non-zero value on a machine without a GPU (or without CUDA) causes a crash or silent fallback to CPU. Users don't know what value to use.

**Fix:** Add a startup probe that checks GPU availability and suggests a value. Or: try the configured value and catch the error gracefully, falling back to CPU-only with a warning message in the UI.

---

### 9. Debug Logging Cleanup 🔴

**Problem:** `server.py` has `print(f"DEBUG: ...")` statements on every request, including the full request body. This clutters the terminal and could log sensitive content from conversations.

**Fix:**
- Remove the HTTP logging middleware.
- Replace scattered `print()` calls with Python's `logging` module at appropriate levels.
- Default log level to `INFO` (startup messages only). Let users set `DEBUG` via config if they need verbose output.

```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("localmind")
```

---

## Future Ideas (Not Prioritized Yet)

These are longer-term possibilities that would change the project's scope.

### GitHub Pages Deployment (Frontend Only)
Deploy the frontend (HTML/CSS/JS) to GitHub Pages as a hosted UI. Users still run the Python server locally. The frontend's settings modal already supports changing the API URL, so this mostly works today.

### WebLLM / In-Browser Inference
Replace the Python backend entirely with [WebLLM](https://github.com/mlc-ai/web-llm), which runs models in the browser via WebGPU. True zero-install experience, but requires a WebGPU-capable browser and a decent GPU. Different model format (not GGUF). Essentially a different project.

### Multiple Model Support
Allow users to switch between multiple loaded models from the UI. Would require a model selector dropdown and lazy-loading models on demand (since each model uses significant RAM).

### Response Length Control in UI
Add a slider or input in the Settings modal for `max_tokens` so users can control how long responses are without touching config files.

---

## Implementation Order

| Phase | Items | Effort | Impact |
|-------|-------|--------|--------|
| **Phase 1** | ~~Config file (1)~~, Path traversal fix (2), max_tokens (5) | 1-2 hours | App works safely on any machine |
| **Phase 2** | Bundle vendor JS (3), Pin versions (7), Install guide (6) | 1-2 hours | Works offline, reproducible installs |
| **Phase 3** | GPU auto-detect (8), Logging cleanup (9) | 1 hour | Polish and cleanup |
| **Phase 4** | Conversation History & SQLite Persistence (4) | ~5 hours | Real-world chat UX |
| **Phase 5** | GitHub Pages deployment, Multiple model support, WebLLM | Varies | Extended functionality |

**Phase 4 dependency:** The SQLite feature (item 4) depends on item 5 (`max_tokens`) being done first. The `max_tokens` setting reserves space for the model's response, which the trimming logic relies on to calculate how much history fits.
