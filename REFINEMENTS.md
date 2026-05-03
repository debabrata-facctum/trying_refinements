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

### 4. Conversation History Limit (Context Window Overflow) 🔴

**Problem:** `state.history` in `script.js` grows without limit. Every message ever sent gets included in the next API call. With `n_ctx=2048`, the model silently truncates or errors out after ~15-20 exchanges. The user sees degraded responses with no explanation.

**Why this is high priority:** It's invisible to the user. The model just starts giving worse answers and they don't know why.

**Fix options (pick one):**

**Option A — Client-side cap (simplest):**
Keep only the last N message pairs in history. Simple and predictable.

```javascript
const MAX_HISTORY = 20; // 10 exchanges (user + assistant each)

// After pushing new messages to history:
if (state.history.length > MAX_HISTORY) {
    state.history = state.history.slice(-MAX_HISTORY);
}
```

**Option B — Server-side token counting (more accurate):**
Before sending to the model, count tokens and trim oldest messages to fit within `n_ctx`. This is more complex but respects the actual context window.

```python
# Pseudocode — llama-cpp-python has a tokenize() method
max_prompt_tokens = config["n_ctx"] - 512  # Reserve 512 for the response

while count_tokens(messages) > max_prompt_tokens:
    messages.pop(1)  # Remove oldest non-system message
```

**Recommendation:** Start with Option A. It's 3 lines of code and solves 90% of the problem. Add Option B later if you need precision.

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

### Conversation Persistence
Save chat history to `localStorage` or a local JSON file so conversations survive page refreshes. Would pair well with the history limit (item 4) — persist the full history to disk but only send the last N messages to the model.

### Multiple Model Support
Allow users to configure multiple models in `config.json` and switch between them in the UI. Would require a model selector dropdown and lazy-loading models on demand (since each model uses significant RAM).

---

## Implementation Order

| Phase | Items | Effort | Impact |
|-------|-------|--------|--------|
| **Phase 1** | Config file (1), Path traversal fix (2), History limit (4), max_tokens (5) | 1-2 hours | App works safely on any machine |
| **Phase 2** | Bundle vendor JS (3), Pin versions (7), Install guide (6) | 1-2 hours | Works offline, reproducible installs |
| **Phase 3** | GPU auto-detect (8), Model name cleanup (9), Remove Ollama check (10), Logging (11) | 1 hour | Polish and cleanup |
| **Phase 4** | Future ideas as needed | Varies | Extended functionality |

**Note:** Items 1, 2, and 5 are already addressed in `server_simple.py`. Phase 1 work is about backporting those fixes to `server.py` and adding the config file + history limit + max_tokens.
