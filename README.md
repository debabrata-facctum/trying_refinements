# LocalMind

A private, local chat interface for running GGUF language models on your own machine. No cloud, no API keys, no data leaving your computer.

Built with **FastAPI** + **llama-cpp-python** on the backend and a clean dark-themed frontend.

![UI Preview](https://img.shields.io/badge/status-active-brightgreen) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

---

## Why This Exists

Most local LLM tools either require complex setup (Ollama, text-generation-webui) or force you to use a terminal. LocalMind is a single `python server.py` that gives you a ChatGPT-style UI talking to a model running on your hardware.

Key design choices:
- **No hardcoded model path** — pick any `.gguf` file through a built-in file browser in the UI
- **Hot-swappable models** — load a different model without restarting the server
- **Streaming responses** — tokens appear as they're generated, not after a 30-second wait
- **Zero external accounts** — everything runs on `localhost`

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

<details>
<summary><strong>Platform-specific notes for llama-cpp-python</strong></summary>

`llama-cpp-python` compiles C++ code during install. If you hit build errors:

```bash
# Pre-built wheels (no compiler needed)
pip install llama-cpp-python --prefer-binary

# Windows — requires Visual Studio Build Tools
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

# macOS with Apple Silicon GPU (Metal acceleration)
CMAKE_ARGS="-DGGML_METAL=on" pip install llama-cpp-python

# Linux/Windows with NVIDIA GPU (CUDA 12.4)
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124
```

</details>

### 2. Get a model

Download any GGUF-format model. Good starting points:

| Model | Size | RAM needed | Link |
|-------|------|-----------|------|
| **Gemma 3 4B IT Q4_K_M** | ~2.9 GB | 6 GB | [bartowski/gemma-3-4b-it-GGUF](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF) |
| Mistral 7B Instruct Q4_K_M | ~4.4 GB | 8 GB | [unsloth/Mistral-7B-Instruct-v0.2-GGUF](https://huggingface.co/unsloth/mistral-7b-instruct-v0.3) |
| Llama 3 8B Instruct Q4 | ~4.7 GB | 8 GB | [QuantFactory/Meta-Llama-3-8B-Instruct-GGUF](https://huggingface.co/unsloth/Llama-3.1-8B-Instruct-GGUF) |

> **Recommended:** Gemma 3 4B IT Q4_K_M — small enough to run comfortably on most machines, good instruction-following quality for its size.

Place the `.gguf` file anywhere on your machine — you'll point to it from the UI.

### 3. Run

```bash
python server.py
```

Open [http://localhost:8080](http://localhost:8080)

### 4. Load a model

1. Click the ⚙️ gear icon (top-right)
2. Click **Pick Model** → browse to your `.gguf` file
3. Adjust parameters if needed (context window, threads, GPU layers)
4. Click **Load Model**
5. Start chatting

---

## How It Works

```
Browser (localhost:8080)          FastAPI Server (server.py)
┌─────────────────────┐          ┌──────────────────────────┐
│  Chat UI            │  fetch   │  /api/chat               │
│  • Send messages    │ ──────►  │  • Merge system prompt   │
│  • Stream responses │ ◄──────  │  • Run inference         │
│  • Render markdown  │  NDJSON  │  • Stream tokens back    │
│                     │          │                          │
│  Settings Modal     │          │  /api/browse             │
│  • Pick model file  │ ──────►  │  • List dirs + .gguf     │
│  • Set parameters   │          │                          │
│  • Load/swap model  │ ──────►  │  /api/load-model         │
└─────────────────────┘          │  • Hot-swap model        │
                                 └──────────┬───────────────┘
                                            │
                                            ▼
                                 ┌──────────────────────────┐
                                 │  llama-cpp-python         │
                                 │  • GGUF model in memory   │
                                 │  • CPU or GPU inference   │
                                 └──────────────────────────┘
```

### System prompt handling

Many GGUF models are picky about the `system` role in chat messages. The server automatically merges system prompts into the first user message for maximum compatibility across model families (Llama, Mistral, Gemma, etc.).

### Streaming

Responses stream as newline-delimited JSON (`application/x-ndjson`). Each chunk:
```json
{"message": {"content": "partial token"}, "done": false}
```

Final signal:
```json
{"done": true}
```

The frontend renders markdown in real-time using `marked.js` and syntax-highlights code blocks with `highlight.js`.

---

## Settings & Parameters

All configurable from the Settings modal in the UI:

| Parameter | What it does | Default | Guidance |
|-----------|-------------|---------|----------|
| **Model Path** | Path to your `.gguf` file | — | Use the file browser |
| **n_ctx** | Context window (tokens) | 2048 | Higher = more conversation memory, more RAM |
| **n_threads** | CPU threads for inference | 10 | Set to your physical core count minus 1 |
| **n_gpu_layers** | Layers offloaded to GPU | 20 | Set to 0 if no GPU; -1 to offload everything |
| **System Prompt** | Instructions for the model | "You are a helpful AI assistant." | Customize personality/behavior |

Settings persist in `localStorage` — they survive page refreshes.

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/tags` | Connection health check |
| `GET` | `/api/browse?path=` | Browse filesystem for `.gguf` files |
| `POST` | `/api/load-model` | Load a model with given parameters |
| `GET` | `/api/model-status` | Current model state (loaded/error/not_loaded) |
| `POST` | `/api/chat` | Send messages, receive inference response |

<details>
<summary><strong>Example: POST /api/chat</strong></summary>

```json
{
  "model": "local-model",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain recursion in one sentence."}
  ],
  "stream": true
}
```

</details>

<details>
<summary><strong>Example: POST /api/load-model</strong></summary>

```json
{
  "model_path": "/path/to/mistral-7b-q4.gguf",
  "n_ctx": 4096,
  "n_threads": 7,
  "n_gpu_layers": 0
}
```

</details>

---

## Project Structure

```
web_refinements/
├── server.py           # FastAPI backend — model loading, chat, file browser
├── index.html          # Chat UI with settings modal and file browser
├── script.js           # Frontend logic — streaming, model management
├── style.css           # Dark theme (GitHub-dark inspired)
├── requirements.txt    # Python dependencies
└── REFINEMENTS.md      # Roadmap of planned improvements
```

---

## Troubleshooting

### "No model loaded" when I try to chat
The server starts without a model. Open Settings → Pick Model → select a `.gguf` file → Load Model.

### Responses are empty or cut off
The conversation history may exceed the context window. Refresh the page to clear history, or increase `n_ctx` in Settings (costs more RAM).

### Server crashes with GPU-related errors
Set **GPU Layers** to `0` in Settings. This forces CPU-only inference — slower but universally compatible.

### "Failed to fetch" in the browser
- Confirm the server is running (`python server.py`)
- If using Brave or a strict ad-blocker, disable shields for `localhost`
- Check that the API URL in Settings is `http://localhost:8080/api/chat`

### Slow responses
- Reduce `n_ctx` (smaller context = faster)
- Use a smaller quantized model (Q4 instead of Q8)
- Increase `n_threads` to match your CPU core count
- If you have a GPU, set `n_gpu_layers` to `-1` to offload everything

---

## Roadmap

See [REFINEMENTS.md](./REFINEMENTS.md) for the full list. Highlights:

- [ ] Conversation persistence with SQLite (multi-chat sidebar)
- [ ] Server-side history trimming (prevent silent context overflow)
- [ ] Bundle JS dependencies for true offline use
- [ ] Hardware auto-detection for optimal default parameters
- [ ] `max_tokens` control for response length
- [ ] Proper logging (replace debug prints)

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-idea`)
3. Commit your changes
4. Push and open a Pull Request

Anything marked 🔴 in [REFINEMENTS.md](./REFINEMENTS.md) is fair game.

---

## License

MIT
