# LocalMind

A private, local chat interface for running GGUF language models on your own machine. No cloud, no API keys, no data leaving your computer.

Built with **FastAPI** + **llama-cpp-python** on the backend and a clean dark-themed frontend.

![Status](https://img.shields.io/badge/status-active-brightgreen) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-GPLv3-blue)

---

## Why This Exists

Most local LLM tools (Ollama, text-generation-webui, LM Studio) hide the model configuration behind abstractions. You get a chat box, but no direct control over how the model actually runs on your hardware. Worse — they use generic default settings that leave performance on the table. Your CPU's instruction sets, your RAM capacity, your GPU's VRAM — none of it is leveraged unless you dig through CLI flags or config files.

LocalMind gives you that control, without requiring you to be an expert.

**The core idea:** a lightweight chat UI that **auto-detects your hardware** and applies platform-optimized inference settings out of the box — then lets you fine-tune every parameter visually if you want to. Flash attention, memory locking, NUMA-aware scheduling, KV-cache quantization, batch sizing — all exposed and tunable from a single settings panel.

The result: you get the maximum performance your specific machine can deliver, whether that's a 13th Gen Intel laptop with no GPU, a Linux workstation with an RTX 4090, or a MacBook Pro with Apple Silicon.

### What makes this different

| Feature | Ollama / LM Studio | LocalMind |
|---------|--------------------:|----------:|
| Hardware detection | None — one-size-fits-all defaults | Auto-detects CPU, RAM, GPU, instruction sets on startup |
| Optimization profiles | Not available | Platform-specific profiles (Win/Linux/macOS) with one-click apply |
| Context window control | Hidden or limited | You set `n_ctx` directly (128 → 32768) |
| Thread allocation | Automatic (opaque) | Auto-detected physical cores, fully overridable |
| GPU layer offloading | All-or-nothing | Fine-grained: 0 (CPU only), partial, or -1 (offload all) |
| Flash attention | Hidden or unavailable | Toggle on/off from the UI |
| Memory locking | Not configurable | Toggle on/off — eliminates page-fault stutter |
| NUMA awareness | Not exposed | Auto-enabled on Intel hybrid-core / multi-socket systems |
| KV-cache quantization | Not available | q8_0 for large contexts — saves ~40% memory |
| Batch size control | Hidden | Configurable per-platform (1024 Win/Linux, 512 Mac) |
| Model loading | Restart required | Hot-swap from the UI, no server restart |
| Context management | Silent truncation | Smart trimming with optional rolling summarization |
| Configuration | Config files / CLI flags | Visual settings panel with immediate feedback |

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

<details>
<summary><strong>Platform-specific notes for llama-cpp-python</strong></summary>

`llama-cpp-python` compiles C++ code during install and can be tricky to set up depending on your OS and hardware (CPU vs GPU).

See **[INSTALL_LLAMA_CPP.md](./INSTALL_LLAMA_CPP.md)** for the full installation guide covering Windows, Linux, and macOS with both CPU and GPU builds.

</details>

### 2. Get a model

Download any GGUF-format model. Good starting points:

| Model | Size | RAM needed | Link |
|-------|------|-----------|------|
| **Gemma 3 4B IT Q4_K_M** | ~2.9 GB | 6 GB | [bartowski/gemma-3-4b-it-GGUF](https://huggingface.co/bartowski/google_gemma-3-4b-it-GGUF) |
| Mistral 7B Instruct Q4_K_M | ~4.4 GB | 8 GB | [TheBloke/Mistral-7B-Instruct-v0.2-GGUF](https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.2-GGUF) |
| Llama 3.1 8B Instruct Q4 | ~4.7 GB | 8 GB | [bartowski/Meta-Llama-3.1-8B-Instruct-GGUF](https://huggingface.co/bartowski/Meta-Llama-3.1-8B-Instruct-GGUF) |

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
│  • Send messages    │ ──────►  │  • Context management    │
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

### Hardware auto-detection

On startup, the server probes your system using a layered detection approach:

```
Layer A: psutil + py-cpuinfo (fast, detailed)
Layer B: OS native commands (wmic, /proc, sysctl, nvidia-smi)
Layer C: Safe defaults (if everything else fails)
```

Detection covers:
- CPU: physical/logical core count, brand, instruction flags (AVX2, AVX-512, FMA, F16C)
- RAM: total and available memory
- GPU: NVIDIA (via nvidia-smi) or Apple Metal (via system_profiler)
- OS: platform, architecture

Results are cached in memory (runs once per server lifetime) and served via `/api/hardware-profile`. The frontend uses this to auto-select the best optimization profile and pre-fill all hardware settings.

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

## Context Management

Local models have limited context windows. Without management, long conversations silently overflow — the model loses track of earlier messages or produces broken output. LocalMind handles this automatically.

### How it works

Every chat request goes through the context manager before reaching the model:

```
Messages arrive → Check token budget → Trim if needed → Send to model
```

The system operates in two modes based on a toggle in Settings:

**Sliding Window (default)** — oldest messages are dropped when the conversation exceeds 75% of the available token budget. Simple, fast, zero overhead.

**Summarize + Protect (opt-in)** — instead of dropping old messages entirely, the server compresses them into a rolling summary using the model itself. Recent messages stay verbatim so the model can reference exact wording.

### Budget allocation

```
Total context window (n_ctx)
├── Response reserve (max_tokens)     → space for the model's answer
└── Input budget (the rest)
    ├── System prompt                 → ~1%
    ├── Summary (when enabled)        → 10% of input budget
    ├── Protected zone                → 30% of input budget (recent messages, verbatim)
    └── Headroom                      → ~59% (free space for new messages)
```

After every trim, ~60% of the input budget is free — giving you several more exchanges before the next trim triggers.

### Adaptive behavior

The context manager adapts to the configured context window:

| n_ctx | Behavior |
|-------|----------|
| < 3000 | Sliding window only (summary toggle ignored — not enough room for it to help) |
| ≥ 3000 | Full logic: sliding window when toggle OFF, summarize + protect when toggle ON |

The summary size also scales:
- Under 4k context: capped at 300 tokens
- 4k and above: 10% of input budget (no cap — larger windows get richer summaries)

### Protected zone

Recent messages are never summarized. The protected zone uses a **token budget** (30% of input budget), not a fixed message count. This means:
- Short exchanges → more pairs protected (5–7 recent exchanges)
- Long exchanges → fewer pairs protected (1–2 recent exchanges)
- Always at least 1 exchange protected (the most recent one)

### Rolling summary

When summarization is enabled, dropped messages are compressed into a rolling summary:

1. First overflow: messages 1–5 get summarized → "Summary v1"
2. Next overflow: old summary + messages 6–8 → "Summary v2" (updated, not re-summarized from scratch)
3. Repeats as conversation grows

The summary call is fast (~2–5 seconds) because it only processes the old summary + newly dropped messages, not the entire history.

### Settings

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| **Max Response Tokens** | 512 | 64 – 4096 | Caps how long the model's response can be |
| **Summarize old context** | OFF | ON/OFF | Enable rolling summarization of dropped messages |

> **Tip:** If you notice the model "forgetting" things from earlier in the conversation, enable summarization. It adds a few seconds of latency at trim points but preserves awareness of earlier topics.

---

## Settings & Parameters

All configurable from the Settings modal in the UI. Settings persist in `localStorage` — they survive page refreshes.

### Hardware Profile (Auto-Detected)

On first load, the server probes your hardware (CPU, RAM, GPU, instruction sets) and recommends optimal settings. You can accept the recommendation, pick a different profile, or go fully custom.

| Profile | Description |
|---------|-------------|
| 🪟 Windows (CPU) | ngl=0, threads=P-cores-1, flash=on, mlock=on, numa=on, batch=1024 |
| 🪟 Windows (NVIDIA GPU) | ngl=-1, same as above |
| 🐧 Linux (CPU) | Same as Windows CPU |
| 🐧 Linux (NVIDIA GPU) | ngl=-1, same as above |
| 🍏 macOS (Apple Silicon) | ngl=99, batch=512, mlock=on, no numa |
| 🍏 macOS (Intel) | ngl=0, batch=512, mlock=on, no numa |
| ⚙️ Custom | All fields editable — auto-selected when you change any individual field |

### Model Parameters

| Parameter | Default | Range |
|-----------|---------|-------|
| **Model Path** | — | Any `.gguf` file on your system |
| **n_ctx** | 2048 | 128 – 32768 |

### Hardware Optimization Flags

| Parameter | Default | Range | Purpose |
|-----------|---------|-------|---------|
| **n_gpu_layers** | 0 (auto) | -1 – 999 | GPU layer offloading |
| **n_threads** | auto-detected | 1 – 64 | CPU threads for inference |
| **n_batch** | 1024 (512 on Mac) | 32 – 4096 | Tokens per forward pass during prompt eval |
| **Flash Attention** | ON | ON/OFF | Fused attention kernel — faster, less memory |
| **Memory Lock** | ON | ON/OFF | Lock model in RAM — no page-fault stutter |
| **NUMA** | ON (Win/Linux) | ON/OFF | NUMA-aware scheduling for hybrid-core CPUs |
| **KV Quantization** | Off | Off / q8_0 | Quantize KV-cache — saves ~40% memory at >8k context |

### Inference Parameters

| Parameter | Default | Range |
|-----------|---------|-------|
| **Max Response Tokens** | 512 | 64 – 4096 |
| **Temperature** | 0.7 | 0.0 – 2.0 |
| **Top P** | 0.9 | 0.05 – 1.0 |
| **Top K** | 40 | 1 – 100 |
| **Repeat Penalty** | 1.1 | 1.0 – 2.0 |
| **Summarize old context** | OFF | ON/OFF |
| **System Prompt** | "You are a helpful AI assistant." | Any text |

### Understanding the parameters

**`n_ctx` — Context Window**

How many tokens (roughly words) the model can "see" at once — your message, the conversation history, and its own response all share this budget.

The maximum context window you can set depends on two things:

1. **The model's trained limit** — each model has a maximum context length it was trained on. Setting `n_ctx` beyond this won't help and may produce garbage output. Check the model card on HuggingFace for this value.
2. **Your available RAM/VRAM** — larger context windows consume more memory. Roughly, doubling `n_ctx` adds ~0.5–1 GB of RAM usage depending on the model size.

| Model example | Trained max context | Recommended n_ctx |
|---------------|:-------------------:|:-----------------:|
| Gemma 3 4B | 128000 | 2048–8192 (RAM limited) |
| Mistral 7B v0.2 | 32000 | 2048–8192 (RAM limited) |
| Llama 3.1 8B | 128000 | 2048–8192 (RAM limited) |
| Phi-3 Mini (4K variant) | 4096 | 2048–4096 |
| Phi-3 Mini (128K variant) | 128000 | 2048–8192 (RAM limited) |

**Practical guidelines:**

- `2048` — safe default, works on any machine with 8 GB RAM. Handles ~3–4 back-and-forth exchanges.
- `4096` — comfortable for longer conversations. Needs ~1–2 GB extra RAM over the base model.
- `8192` — good for document analysis or extended chats. Needs ~2–4 GB extra RAM.
- `16384+` — only if your model supports it AND you have 16+ GB RAM to spare. Diminishing returns for casual chat.
- Below `1024` — the model loses track of the conversation very quickly. Not recommended.

> **How to decide:** Start with `2048`. If the model forgets things too quickly, bump to `4096`. Only go higher if you have the RAM and the model was trained for it. If the server crashes or slows to a crawl after loading, your `n_ctx` is too high for your hardware — lower it.

**`n_threads` — CPU Thread Allocation**

How many CPU threads to use for inference. More threads = faster token generation, but only up to your physical core count. Going beyond that causes thread contention and slows things down.

Rule of thumb: **physical cores minus 1** (leave one for the OS and the server itself).

- 4-core machine → set to 3
- 6-core machine → set to 5
- 8-core machine → set to 6–7

> Note: use *physical* cores, not logical (hyperthreaded) cores. Hyperthreads don't help much for this workload.

**`n_gpu_layers` — GPU Offloading**

A transformer model is made of stacked layers (a 7B model typically has 32). This parameter controls how many of those layers run on your GPU instead of CPU.

| Value | Meaning |
|-------|---------|
| `0` | CPU only — works everywhere, slowest |
| `10–20` | Partial offload — good if your GPU has limited VRAM |
| `32+` | Full offload for that model size |
| `-1` | Offload ALL layers to GPU — fastest, requires enough VRAM |

Guidelines:
- **No GPU or unsure?** → set to `0`
- **NVIDIA with 4 GB VRAM** → try `20` for a 7B Q4 model
- **NVIDIA with 8+ GB VRAM** → set to `-1` (offload everything)
- **Apple Silicon (M1/M2/M3)** → set to `-1` (unified memory, GPU offload is always a win)

If you set it too high for your VRAM, the server will crash on model load. Lower the value and try again.

**`max_tokens` — Response Length Cap**

Maximum number of tokens the model can generate per response. Without this, the model decides when to stop — which could be 50 tokens or 2000.

- `256` — short, concise answers
- `512` — good default for most conversations
- `1024` — detailed explanations, code generation
- `2048+` — long-form content (essays, full implementations)

This also determines how much of the context window is reserved for the response vs. conversation history.

---

## Inference Sampling Parameters

These parameters control **how the model picks the next token** during generation. They directly affect the creativity, coherence, and repetitiveness of the output.

### How LLM token sampling works

At each step, the model produces a probability distribution over its entire vocabulary (~32,000+ tokens). Sampling parameters filter and reshape this distribution before a token is picked:

```
Model outputs probabilities for all tokens
    │
    ▼
[Top K filter] → Keep only the K most probable tokens, discard the rest
    │
    ▼
[Top P filter] → From those K tokens, keep only enough to cover P cumulative probability
    │
    ▼
[Temperature] → Flatten or sharpen the remaining distribution
    │
    ▼
[Sample] → Pick one token randomly from the adjusted distribution
    │
    ▼
[Repeat Penalty] → If the picked token appeared recently, penalize it (reduce its chance next time)
```

### Parameter details

**`temperature` — Randomness Control**

Reshapes the probability distribution before sampling.

| Value | Effect |
|-------|--------|
| 0.0–0.2 | Nearly deterministic — always picks the most likely token. Same input → same output. |
| 0.5–0.8 | Balanced — some variety while staying coherent. Good for general use. |
| 1.0 | Raw probabilities — no modification. |
| 1.2–2.0 | High randomness — flattens the distribution so unlikely tokens get picked more often. Creative but can become incoherent. |

**When to adjust:** Lower it for factual Q&A, code generation, or when you want consistent answers. Raise it for creative writing, brainstorming, or when responses feel too robotic.

---

**`top_p` — Nucleus Sampling**

After Top K filtering, Top P further narrows the candidates. It keeps the smallest set of tokens whose cumulative probability adds up to P.

| Value | Effect |
|-------|--------|
| 0.1–0.3 | Very narrow — only the top 1–3 tokens are considered. Extremely focused. |
| 0.5–0.7 | Moderate — a handful of strong candidates. |
| 0.9 | Default — covers most of the probability mass, allows some variety. |
| 1.0 | No filtering — all tokens that survived Top K are eligible. |

**Example:** If the model thinks the next token is 60% "rain", 25% "water", 10% "drops", 5% "storm" — with Top P = 0.85, only "rain" and "water" are kept (60% + 25% = 85%).

---

**`top_k` — Hard Candidate Limit**

The simplest filter: keep only the K most probable tokens, throw away everything else.

| Value | Effect |
|-------|--------|
| 1 | Greedy decoding — always picks the single most likely token. Fully deterministic. |
| 10–20 | Very focused — limited vocabulary at each step. |
| 40 | Default — good balance of variety and coherence. |
| 80–100 | Wide open — many candidates, more surprising word choices. |

**When to adjust:** Lower it when the model is being too random or off-topic. Raise it when responses feel repetitive or predictable.

---

**`repeat_penalty` — Repetition Control**

Penalizes tokens that have already appeared in the generated text. The penalty multiplies against the token's probability, making it less likely to be picked again.

| Value | Effect |
|-------|--------|
| 1.0 | No penalty — the model can repeat freely. May loop on phrases. |
| 1.1 | Light penalty (default) — discourages exact repetition without being aggressive. |
| 1.3–1.5 | Strong penalty — actively avoids repeating words/phrases. Can make output more verbose as the model searches for synonyms. |
| 1.8–2.0 | Very aggressive — forces extreme variety. Can produce unnatural phrasing. |

**When to adjust:** If the model keeps repeating the same phrase in a loop, bump this to 1.3+. If responses feel unnaturally wordy or use strange synonyms, lower it back toward 1.1.

---

### Recommended presets

| Use Case | Temperature | Top P | Top K | Repeat Penalty |
|----------|:-----------:|:-----:|:-----:|:--------------:|
| **Factual Q&A / Code** | 0.1–0.3 | 0.5 | 10–20 | 1.0–1.1 |
| **General chat** | 0.7 | 0.9 | 40 | 1.1 |
| **Creative writing** | 0.9–1.1 | 0.95 | 60–80 | 1.2–1.3 |
| **Brainstorming** | 1.2+ | 0.95 | 80–100 | 1.3 |

> **Tip:** Temperature is the most impactful parameter. Start by adjusting only temperature, then fine-tune with Top P and Top K if needed. Repeat Penalty is mostly useful when you notice looping behavior.

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/api/tags` | Connection health check |
| `GET` | `/api/browse?path=` | Browse filesystem for `.gguf` files |
| `GET` | `/api/hardware-profile` | Auto-detected hardware info + recommended settings |
| `POST` | `/api/load-model` | Load a model with given parameters |
| `GET` | `/api/model-status` | Current model state (loaded/error/not_loaded) |
| `POST` | `/api/chat` | Send messages, receive inference response |
| `POST` | `/api/reset-context` | Clear the summary cache (new chat session) |

<details>
<summary><strong>Example: POST /api/chat</strong></summary>

```json
{
  "model": "local-model",
  "messages": [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Explain recursion in one sentence."}
  ],
  "stream": true,
  "max_tokens": 512,
  "summarize": false
}
```

</details>

<details>
<summary><strong>Example: POST /api/load-model</strong></summary>

```json
{
  "model_path": "C:/models/gemma-3-4b-it-Q4_K_M.gguf",
  "n_ctx": 4096,
  "n_threads": 5,
  "n_gpu_layers": 0,
  "flash_attn": true,
  "use_mlock": true,
  "numa": true,
  "n_batch": 1024,
  "type_k": null,
  "type_v": null
}
```

</details>

---

## Project Structure

```
Web_local_llm/
├── server.py             # FastAPI backend — routing, model loading, chat
├── context_manager.py    # Context trimming + optional summarization logic
├── hardware_detector.py  # Cross-platform hardware detection + profile engine
├── index.html            # Chat UI with settings modal and file browser
├── script.js             # Frontend logic — streaming, model management, profiles
├── style.css             # Dark theme (GitHub-dark inspired)
├── requirements.txt      # Python dependencies (pinned versions)
├── INSTALL_LLAMA_CPP.md  # Platform-specific llama-cpp-python installation guide
├── logic.md              # Internal design docs for development reference
└── README.md             # This file
```

---

## Troubleshooting

### "No model loaded" when I try to chat
The server starts without a model. Open Settings → Pick Model → select a `.gguf` file → Load Model.

### Responses are empty or cut off
- The `max_tokens` setting may be too low — increase it in Settings.
- If responses cut off mid-sentence at the same length every time, that's the `max_tokens` cap. Raise it.

### Model seems to forget earlier conversation
- This is normal — the context manager drops old messages to stay within budget.
- Enable **Summarize old context** in Settings to preserve awareness of earlier topics.
- Increase `n_ctx` for a larger conversation window (costs more RAM).

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
- If summarization is ON, it adds a few seconds at trim points — this is expected

---

## Roadmap

- Conversation persistence with SQLite (multi-chat sidebar, "New Chat" button)
- Bundle JS dependencies locally for true offline use (no CDN needed)
- ~~Hardware auto-detection — suggest optimal `n_threads` and `n_gpu_layers` on startup~~ ✅ Done
- Structured logging with Python `logging` module

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
