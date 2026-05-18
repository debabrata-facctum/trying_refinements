# LocalMind

A private, local chat interface for running GGUF language models on your own machine. No cloud, no API keys, no data leaving your computer.

Built with **FastAPI** + **llama-cpp-python** on the backend and a clean dark-themed frontend.

![UI Preview](https://img.shields.io/badge/status-active-brightgreen) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-GPLv3-blue)

---

## Why This Exists

Most local LLM tools (Ollama, text-generation-webui, LM Studio) hide the model configuration behind abstractions. You get a chat box, but no direct control over how the model actually runs on your hardware. LocalMind gives you that control.

**The core idea:** a lightweight chat UI where you explicitly configure the inference parameters — context length, CPU thread allocation, GPU layer offloading — and see the effect immediately. No guessing, no hidden defaults, no restarting.

### What makes this different

| Feature | Ollama / LM Studio | LocalMind |
|---------|--------------------:|----------:|
| Context window control | Hidden or limited | You set `n_ctx` directly (128 → 8192+) |
| Thread allocation | Automatic (opaque) | You choose exactly how many CPU threads to dedicate |
| GPU layer offloading | All-or-nothing | Fine-grained: 0 (CPU only), partial, or -1 (offload all) |
| Model loading | Restart required | Hot-swap from the UI, no server restart |
| Configuration | Config files / CLI flags | Visual settings panel with immediate feedback |

**Quick primer on these parameters:**

- **Context window (`n_ctx`)** — how many tokens the model can hold in memory at once. Your messages, the conversation history, and the model's response all share this space. Bigger = longer conversations, but uses more RAM.
- **Threads (`n_threads`)** — how many CPU cores to throw at inference. More threads = faster responses, but only up to your physical core count. Going higher actually hurts performance.
- **GPU layers (`n_gpu_layers`)** — a model is a stack of transformer layers. This controls how many run on GPU vs CPU. Set to `0` for CPU-only, set to `-1` to offload everything to GPU, or pick a number in between based on how much VRAM you have.

The point: you see exactly what's happening and can tune it for your specific machine — whether that's a MacBook Air with 8 GB or a desktop with a 12 GB GPU.

This matters if you're:
- Running on constrained hardware and need to tune for your specific machine
- Learning how LLM inference parameters affect speed and quality
- Want a minimal, transparent setup with no magic

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

All configurable from the Settings modal in the UI. Settings persist in `localStorage` — they survive page refreshes.

| Parameter | Default | Range |
|-----------|---------|-------|
| **Model Path** | — | Any `.gguf` file on your system |
| **n_ctx** | 2048 | 128 – 8192+ |
| **n_threads** | 6 | 1 – your core count |
| **n_gpu_layers** | 20 | 0, 1–99, or -1 |
| **System Prompt** | "You are a helpful AI assistant." | Any text |

### Understanding the parameters

**`n_ctx` — Context Window**

This is how many tokens (roughly words) the model can "see" at once — your message, the conversation history, and its own response all share this budget. A 7B model with `n_ctx=2048` uses about 4 MB of extra RAM for context; bumping to 8192 costs ~16 MB more. The real cost is the model weights (~4 GB for a Q4 7B model), so context size is cheap to increase if you have the RAM.

- `2048` — good default, handles ~3-4 back-and-forth exchanges
- `4096` — comfortable for longer conversations
- `8192` — full context, useful for document analysis or long chats
- Below `1024` — the model loses track of the conversation very quickly

**`n_threads` — CPU Thread Allocation**

How many CPU threads `llama-cpp-python` uses for the heavy matrix math during inference. More threads = faster token generation, but only up to your physical core count. Going beyond that causes thread contention and actually slows things down.

Rule of thumb: **physical cores minus 1** (leave one for the OS and the server itself).

- 4-core machine → set to 3
- 6-core machine → set to 5
- 8-core machine → set to 6–7

> Note: use *physical* cores, not logical (hyperthreaded) cores. Hyperthreads don't help much for this workload.

**`n_gpu_layers` — GPU Offloading**

A transformer model is made of stacked layers (a 7B model typically has 32). This parameter controls how many of those layers run on your GPU instead of CPU. More layers on GPU = dramatically faster inference.

| Value | Meaning |
|-------|---------|
| `0` | CPU only — works everywhere, slowest |
| `10–20` | Partial offload — good if your GPU has limited VRAM |
| `32+` | Full offload for that model size |
| **`-1`** | **Offload ALL layers to GPU** — fastest, requires enough VRAM |

Guidelines:
- **No GPU or unsure?** → set to `0`
- **NVIDIA with 4 GB VRAM** → try `20` for a 7B Q4 model
- **NVIDIA with 8+ GB VRAM** → set to `-1` (offload everything)
- **Apple Silicon (M1/M2/M3)** → set to `-1` (unified memory, GPU offload is always a win)

If you set it too high for your VRAM, the server will crash on model load. Just lower the value and try again.

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

- Conversation persistence with SQLite (multi-chat sidebar, "New Chat" button)
- Server-side history trimming — automatically drop old messages so the model never hits a silent context overflow
- Bundle JS dependencies locally for true offline use (no CDN needed)
- Hardware auto-detection — suggest optimal `n_threads` and `n_gpu_layers` on startup
- `max_tokens` control — let users cap response length from the UI
- Proper structured logging (replace debug prints with Python `logging`)
- Path traversal protection on static file serving
- Pin dependency versions for reproducible installs

---

## Contributing

1. Fork the repo
2. Create a feature branch (`git checkout -b feature/your-idea`)
3. Commit your changes
4. Push and open a Pull Request

---

## License

This project is licensed under the [GNU General Public License v3.0](./LICENSE).

You're free to use, modify, and distribute this software — but any derivative work must also be open-sourced under the same license.
