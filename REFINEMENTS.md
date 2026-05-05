# Refinements — Cross-Platform, Performance & Stability

A running list of issues and planned updates to make this project work reliably on any OS, adapt to the user's hardware, and avoid subtle bugs in long sessions.

Items are grouped by priority. Each item has a status tracker:
- 🔴 Not started
- 🟡 Partially addressed (e.g., fixed in `server_simple.py` but not in `server.py`)
- 🟢 Done

---

## Priority: HIGH

These should be tackled first. They affect whether the app runs at all on a new machine, or introduce security/stability risks.

---

### 1. Config File — Remove All Hardcoded Values 🟡

**Covers:** Model path, threads, GPU layers, context size, host, port.

**Problem:** `server.py` has a hardcoded Windows model path (`r"C:\llama\models\..."`), hardcoded `n_threads=10`, `n_gpu_layers=20`, and `host="0.0.0.0"`. Every new user must edit source code to get it running, and the defaults can crash weaker machines or trigger firewall prompts.

**Current state:** `server_simple.py` moves these to top-level variables with sensible defaults (auto threads, 0 GPU layers, `127.0.0.1`). But they're still in the Python file, not externalized.

**Target fix:** A single `config.json` that the server reads at startup. Users edit JSON, not code.

```json
{
    "model_path": "./models/default.gguf",
    "n_threads": "auto",
    "n_gpu_layers": 0,
    "n_ctx": 2048,
    "host": "127.0.0.1",
    "port": 8080
}
```

```python
import json, os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {
    "model_path": "./models/default.gguf",
    "n_threads": "auto",
    "n_gpu_layers": 0,
    "n_ctx": 2048,
    "host": "127.0.0.1",
    "port": 8080,
}

def load_config():
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            user_config = json.load(f)
        config = {**DEFAULT_CONFIG, **user_config}
    else:
        config = DEFAULT_CONFIG.copy()

    if config["n_threads"] == "auto":
        config["n_threads"] = os.cpu_count() or 4

    config["model_path"] = str(Path(config["model_path"]).resolve())
    return config
```

**Why it matters long-term:** If you ever distribute this to non-developers (e.g., compliance team members at Facctum), they need a zero-code setup experience. A config file is the first step toward that.

---

### 2. Static File Serving Security (Path Traversal) 🟡

**Problem:** The catch-all route `/{file_path:path}` in `server.py` serves any file relative to the working directory. No path sanitization. If someone runs the server from their home directory, a crafted request like `GET /../../.ssh/id_rsa` could leak sensitive files.

**Current state:** Fixed in `server_simple.py` with `Path.resolve()` + prefix check.

**Target fix (apply to `server.py` too):**

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

```
Web_llm/
├── vendor/
│   ├── marked.min.js
│   ├── highlight.min.js
│   └── github-dark.min.css
```

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
- Good learning exercise for real-world patterns

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
                                     │
         ┌───────────────────────────┼───────────────────────────┐
         │                           │                           │
         ▼                           ▼                           ▼
┌─────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│ GET/POST/DELETE  │    │   POST /api/chat     │    │   GET /api/tags      │
│ /api/convers...  │    │                      │    │   (health check)     │
│                  │    │  1. Receive messages  │    └──────────────────────┘
│ CRUD operations  │    │  2. Trim to fit ctx  │
│ on conversations │    │  3. Run inference    │
└────────┬─────────┘    │  4. Save to DB       │
         │              │  5. Stream response   │
         │              └──────────┬───────────┘
         │                         │
         ▼                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  BACKEND (FastAPI + Python)                                             │
│                                                                         │
│  ┌─────────────────────┐    ┌────────────────────────────────────────┐  │
│  │      db.py           │    │         Model (llama-cpp-python)       │ │
│  │                      │    │                                        │ │
│  │  • init_db()         │    │  • Loaded once at startup              │ │
│  │  • create_convo()    │    │  • Receives trimmed messages           │ │
│  │  • save_message()    │    │  • Generates response (stream/batch)   │ │
│  │  • list_convos()     │    │  • n_ctx = 16384 (configurable)        │ │
│  │  • get_messages()    │    │  • max_tokens = 1024 (reserved)        │ │
│  │  • delete_convo()    │    │                                        │ │
│  └──────────┬───────────┘    └────────────────────────────────────────┘ │
│             │                                                           │
│             ▼                                                           │
│  ┌──────────────────────┐                                               │
│  │   SQLite (chats.db)  │                                               │
│  │                      │                                               │
│  │  conversations table │  ◄── id, title, created_at, updated_at        │
│  │  messages table      │  ◄── id, conversation_id, role, content, ts   │
│  └──────────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

**Data flow for a single message:**

```
1. User types message, clicks Send
2. Frontend sends POST /api/chat with:
   - conversation_id (which chat this belongs to)
   - messages (system + recent history + new message)
   - stream: true
3. Server receives request:
   a. Merges system prompt into first user message
   b. Trims messages to fit within (n_ctx - max_tokens)
   c. Sends trimmed messages to llama-cpp-python
   d. Streams response chunks back to frontend
   e. After completion: saves user message + AI response to SQLite
4. Frontend:
   a. Displays streamed response in real-time
   b. Adds messages to local state.history
   c. Refreshes sidebar (updated_at changes)
```

---

#### Database Schema

```sql
-- File: chats.db (auto-created on first run)

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,                    -- UUID or timestamp-based ID
    title TEXT NOT NULL DEFAULT 'New Chat', -- Auto-generated from first user message
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

-- Index for fast message lookups by conversation
CREATE INDEX IF NOT EXISTS idx_messages_conversation 
ON messages(conversation_id, timestamp);
```

---

#### New API Endpoints

| Method | Endpoint | Purpose | Returns |
|--------|----------|---------|---------|
| GET | `/api/conversations` | List all chats for sidebar | `[{id, title, created_at, updated_at}]` |
| POST | `/api/conversations` | Create a new empty chat | `{id, title, created_at}` |
| GET | `/api/conversations/{id}` | Get a chat's messages | `{id, title, messages: [...]}` |
| DELETE | `/api/conversations/{id}` | Delete a chat and its messages | `{success: true}` |
| PATCH | `/api/conversations/{id}` | Rename a chat | `{id, title}` |

Messages are saved automatically during the existing `/api/chat` flow — no separate message endpoint needed.

---

#### Backend Implementation (Python)

```python
import sqlite3
import uuid
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).parent / "chats.db"

def init_db():
    """Create tables if they don't exist. Called once at startup."""
    with get_db() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conversation 
            ON messages(conversation_id, timestamp);
        """)

@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return dicts instead of tuples
    conn.execute("PRAGMA foreign_keys = ON")  # Enable cascade deletes
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def create_conversation():
    """Create a new conversation, return its ID."""
    conv_id = str(uuid.uuid4())
    with get_db() as db:
        db.execute(
            "INSERT INTO conversations (id) VALUES (?)", (conv_id,)
        )
    return conv_id

def save_message(conversation_id: str, role: str, content: str):
    """Save a single message to a conversation."""
    with get_db() as db:
        db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content)
        )
        # Auto-title: use first user message as the conversation title
        if role == "user":
            existing = db.execute(
                "SELECT title FROM conversations WHERE id = ?", (conversation_id,)
            ).fetchone()
            if existing and existing["title"] == "New Chat":
                title = content[:50] + ("..." if len(content) > 50 else "")
                db.execute(
                    "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (title, conversation_id)
                )
        # Always update the timestamp
        db.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,)
        )

def get_conversation_messages(conversation_id: str):
    """Get all messages for a conversation, ordered by time."""
    with get_db() as db:
        rows = db.execute(
            "SELECT role, content, timestamp FROM messages WHERE conversation_id = ? ORDER BY timestamp",
            (conversation_id,)
        ).fetchall()
    return [dict(row) for row in rows]

def list_conversations():
    """List all conversations, newest first."""
    with get_db() as db:
        rows = db.execute(
            "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]

def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages (cascade)."""
    with get_db() as db:
        db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
```

---

#### Modified Chat Flow

The existing `/api/chat` endpoint changes slightly to accept a `conversation_id`:

```python
class ChatRequest(BaseModel):
    messages: List[Message]
    conversation_id: Optional[str] = None  # NEW: link to a saved conversation
    stream: Optional[bool] = False

@app.post("/api/chat")
async def chat(request: ChatRequest):
    # ... existing inference logic ...

    # After generating the response, save both messages to DB
    if request.conversation_id:
        # Save the user's message
        user_msg = request.messages[-1].content
        save_message(request.conversation_id, "user", user_msg)
        # Save the assistant's response
        save_message(request.conversation_id, "assistant", ai_response_content)

    return {"message": {"content": ai_response_content}, "done": True}
```

---

#### Server-Side History Trimming

This is what prevents the "empty response" problem. Before sending messages to the model, trim to fit:

```python
MAX_RESPONSE_TOKENS = 1024
MAX_PROMPT_TOKENS = CONTEXT_SIZE - MAX_RESPONSE_TOKENS  # e.g., 16384 - 1024 = 15360

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

---

#### How History Trimming Works With Persistence

The key insight — **saved history and model context are separate:**

```
┌─────────────────────────────────────────────────────────────┐
│  SQLite DB: ALL messages (100+ exchanges, full history)     │
│  → Used for: displaying in UI, scrolling back, search       │
└──────────────────────────────┬──────────────────────────────┘
                               │
              On each API call, trim to fit context window
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│  What the model receives: last N messages that fit in 16K   │
│  [system prompt] + [recent messages] + [new user message]   │
│  → Used for: generating the next response                   │
└─────────────────────────────────────────────────────────────┘
```

The user sees the full conversation (loaded from DB). The model only gets what fits. Both are correct.

---

#### Frontend Changes

**New UI elements:**
- A collapsible sidebar listing past conversations (title + date)
- A "New Chat" button at the top of the sidebar
- Click a conversation to load its messages
- A delete button (trash icon) on each conversation

**State management in script.js:**

```javascript
let state = {
    currentConversationId: null,  // Active chat ID
    history: [],                   // Messages sent to model (trimmed)
    apiUrl: '...',
    // ...
};

// On page load: fetch conversation list for sidebar
async function loadSidebar() {
    const res = await fetch('/api/conversations');
    const conversations = await res.json();
    renderSidebar(conversations);
}

// "New Chat" button
async function newChat() {
    const res = await fetch('/api/conversations', { method: 'POST' });
    const { id } = await res.json();
    state.currentConversationId = id;
    state.history = [];
    clearChatArea();
    loadSidebar();  // Refresh sidebar
}

// Click on a past conversation
async function loadConversation(id) {
    const res = await fetch(`/api/conversations/${id}`);
    const data = await res.json();
    state.currentConversationId = id;
    state.history = data.messages;  // Full history for display
    renderAllMessages(data.messages);
}

// Modified handleSendMessage — include conversation_id in request
body: JSON.stringify({
    messages: messages,
    conversation_id: state.currentConversationId,
    stream: true
})
```

---

#### File Structure After Implementation

```
Web_llm/
├── server.py           (updated with DB endpoints)
├── db.py               (database helper functions — extracted for clarity)
├── chats.db            (auto-created, gitignored)
├── index.html          (updated with sidebar)
├── script.js           (updated with conversation management)
├── style.css           (updated with sidebar styles)
├── config.json
├── requirements.txt
└── vendor/
```

Add to `.gitignore`:
```
chats.db
```

---

#### Effort Estimate

| Component | Work | Time |
|-----------|------|------|
| `db.py` — schema + helper functions | Write the module above | ~45 min |
| New API endpoints in `server.py` | 5 routes + wire up DB | ~45 min |
| Frontend sidebar HTML/CSS | Collapsible panel, conversation list | ~1 hour |
| Frontend JS — conversation switching | Load/save/new/delete logic | ~1.5 hours |
| Integration + testing | Wire everything, test edge cases | ~1 hour |
| **Total** | | **~5 hours** |

---

#### Edge Cases to Handle

1. **First message in a new chat** — auto-create conversation if `conversation_id` is null
2. **Empty conversations** — if user clicks "New Chat" but never sends a message, clean up on next "New Chat"
3. **Very long titles** — truncate first user message to 50 chars for the sidebar title
4. **Deleted conversation while active** — reset to a new chat state
5. **DB file permissions** — handle the case where `chats.db` can't be created (read-only filesystem)

---

#### Quick Temporary Fix (before building the full feature)

If you want a stopgap before implementing all of the above, add this to `script.js`:

```javascript
const MAX_HISTORY = 40;
if (state.history.length > MAX_HISTORY) {
    state.history = state.history.slice(-MAX_HISTORY);
}
```

---

### 5. Add `max_tokens` to Generation Calls 🔴

**Problem:** Neither `server.py` nor `server_simple.py` sets `max_tokens` on `create_chat_completion()`. Without it, the model generates until it hits the context limit or produces an end token. On some prompts this means very long generation times (30+ seconds) with no way to control output length.

**Fix:** Add a sensible default and make it configurable.

```python
# In config
"max_tokens": 512

# In the chat endpoint
result = llm.create_chat_completion(
    messages=conversation,
    max_tokens=config.get("max_tokens", 512),
)
```

Also expose this in the frontend settings modal so users can adjust it per-session.

---

## Priority: MEDIUM

Important for polish and broader compatibility, but the app works without these.

---

### 6. `llama-cpp-python` Installation Guide 🔴

**Problem:** `pip install llama-cpp-python` requires a C++ compiler. On Windows this means Visual Studio Build Tools (~6GB install). GPU support needs CUDA toolkit + a special pip index URL. Most beginners hit a wall here.

**Fix:** Create a `SETUP.md` with platform-specific instructions:

```bash
# CPU only — any OS (requires C++ compiler)
pip install llama-cpp-python

# CPU only — pre-built wheels (no compiler needed)
pip install llama-cpp-python --prefer-binary

# GPU — Windows/Linux with CUDA 12.4
pip install llama-cpp-python \
  --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

# macOS with Metal (Apple Silicon GPU)
CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python
```

Also consider adding a `setup.py` or `Makefile` that detects the OS and runs the right command.

---

### 7. Pin Dependency Versions 🔴

**Problem:** `requirements.txt` has no version pins:
```
fastapi
uvicorn
llama-cpp-python
```

A future `pip install` could pull a breaking change in any of these. `llama-cpp-python` in particular has frequent breaking changes between versions.

**Fix:**
```
fastapi>=0.115.0,<1.0.0
uvicorn>=0.34.0,<1.0.0
llama-cpp-python>=0.3.0,<1.0.0
```

Run `pip freeze` on a working setup and pin to those versions for reproducibility.

---

### 8. Hardware Auto-Detection (GPU Availability) 🔴

**Problem:** Setting `n_gpu_layers` to a non-zero value on a machine without a GPU (or without CUDA) causes a crash or silent fallback to CPU. Users don't know what value to use.

**Fix:** Add a startup probe that checks GPU availability and suggests a value.

```python
def detect_gpu():
    """Check if GPU offloading is likely available."""
    try:
        # llama-cpp-python with CUDA will have this
        import llama_cpp
        # Try loading with 1 GPU layer as a test
        # If it fails, fall back to 0
        return True
    except Exception:
        return False

# In config loading:
if config["n_gpu_layers"] == "auto":
    config["n_gpu_layers"] = 35 if detect_gpu() else 0
```

A simpler approach: just try the configured value and catch the error gracefully, falling back to CPU-only with a warning message.

---

## Priority: LOW

Nice-to-have cleanups. Won't affect functionality.

---

### 9. Clean Up Model Name Mismatch 🔴

**Problem:** The code defaults to `"gemma-local-model"` in both `server.py` and `script.js`, but the actual model loaded is Mistral 7B. The README references Gemma. The model name field in the API isn't used for anything — it's passed through but ignored by `llama-cpp-python`.

**Fix:**
- Change the default model name to something generic like `"local-model"` (done in `server_simple.py`).
- Update README to not reference a specific model family.
- Consider removing the model name field entirely since it serves no purpose with a single-model setup.

---

### 10. Remove Ollama Port Check 🔴

**Problem:** `script.js` has a hardcoded check for port `11434`:
```javascript
if (state.apiUrl.includes('11434')) {
    alert('Wait! Your settings are still pointing to port 11434 (Ollama)...');
```

This is a leftover from migrating away from Ollama. It's confusing for anyone who doesn't know that history, and `alert()` is a jarring UX.

**Fix:** Remove the check entirely. If the user has the wrong URL, the connection check (status indicator) already shows a red dot. That's sufficient feedback.

---

### 11. Debug Logging Cleanup 🔴

**Problem:** `server.py` has `print(f"DEBUG: ...")` statements on every request, including the full request body. This clutters the terminal and could log sensitive content from conversations.

**Fix:**
- Remove the HTTP logging middleware.
- Replace scattered `print()` calls with Python's `logging` module at appropriate levels.
- Default log level to `INFO` (startup messages only). Let users set `DEBUG` via config if they need verbose output.

```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("localmind")

# Instead of: print(f"DEBUG: Received chat request: {chat_request}")
# Use:        logger.debug("Chat request received with %d messages", len(request.messages))
```

---

## Future Ideas (Not Prioritized Yet)

These are longer-term possibilities that would change the project's scope.

### GitHub Pages Deployment (Frontend Only)
Deploy the frontend (HTML/CSS/JS) to GitHub Pages as a hosted UI. Users still run the Python server locally. The frontend's settings modal already supports changing the API URL, so this mostly works today. Would need:
- Bundled vendor JS (item 3 above)
- A first-run setup wizard guiding users to start the local server
- Clear documentation on the split architecture

### WebLLM / In-Browser Inference
Replace the Python backend entirely with [WebLLM](https://github.com/mlc-ai/web-llm), which runs models in the browser via WebGPU. True zero-install experience, but requires a WebGPU-capable browser and a decent GPU. Different model format (not GGUF). Essentially a different project.

### Multiple Model Support
Allow users to configure multiple models in `config.json` and switch between them in the UI. Would require a model selector dropdown and lazy-loading models on demand (since each model uses significant RAM).

---

## Implementation Order

| Phase | Items | Effort | Impact |
|-------|-------|--------|--------|
| **Phase 1** | Config file (1), Path traversal fix (2), max_tokens (5) | 1-2 hours | App works safely on any machine |
| **Phase 2** | Bundle vendor JS (3), Pin versions (7), Install guide (6) | 1-2 hours | Works offline, reproducible installs |
| **Phase 3** | GPU auto-detect (8), Model name cleanup (9), Remove Ollama check (10), Logging (11) | 1 hour | Polish and cleanup |
| **Phase 4** | Conversation History & SQLite Persistence (4) — includes history trimming, New Chat, sidebar | ~5 hours | Real-world chat UX, learning exercise |
| **Phase 5** | GitHub Pages deployment, Multiple model support, WebLLM | Varies | Extended functionality |

**Note:** Items 1, 2, and 5 are already addressed in `server_simple.py`. Phase 1 work is about backporting those fixes to `server.py` and adding the config file + max_tokens.

**Phase 4 dependency:** The SQLite feature (item 4) depends on Phase 1 being done first (specifically item 5 — max_tokens). The `max_tokens` setting is what reserves space for the model's response, which the trimming logic relies on to calculate how much history fits.
