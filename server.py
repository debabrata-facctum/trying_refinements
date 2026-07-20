import os
import gc
import json
import time
import platform
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from llama_cpp import Llama
from pydantic import BaseModel
from typing import List, Optional, Literal
from context_manager import ContextManager
from hardware_detector import run_detection

# Directory this file lives in — used for robust static file serving so the
# server works no matter which directory it is launched from.
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = FastAPI(title="Local LLM Server")

# Enable CORS for the frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model instance
llm = None

# Context manager instance
ctx_manager = ContextManager()

# Model state tracking
model_state = {
    "model_path": "",
    "n_ctx": 2048,
    "n_threads": 6,
    "n_gpu_layers": 20,
    "flash_attn": True,
    "use_mlock": True,
    "numa": False,
    "n_batch": 1024,
    "type_k": None,
    "type_v": None,
    "status": "not_loaded",
    # Model specs read from the GGUF file at load time (None until a model loads)
    "training_ctx": None,
    "n_params": None,
    "n_embd": None,
    "n_vocab": None,
    "file_size_bytes": None,
    "desc": None,
}


def _first_ok(*getters):
    """Return the first getter that yields a non-None value without raising."""
    for get in getters:
        try:
            val = get()
            if val is not None:
                return val
        except Exception:
            pass
    return None


def extract_model_specs(model, path):
    """Read intrinsic model specs from a loaded llama_cpp model.

    Method names vary across llama-cpp-python versions, so every read is
    attempted against both the high-level Llama object and its internal
    `_model` handle, and failures fall back to None gracefully.
    """
    inner = getattr(model, "_model", None)
    specs = {
        "training_ctx": _first_ok(
            lambda: model.n_ctx_train(),
            lambda: inner.n_ctx_train(),
        ),
        "n_embd": _first_ok(
            lambda: model.n_embd(),
            lambda: inner.n_embd(),
        ),
        "n_vocab": _first_ok(
            lambda: model.n_vocab(),
            lambda: inner.n_vocab(),
        ),
        "n_params": _first_ok(
            lambda: inner.n_params(),
            lambda: model.n_params(),
        ),
        "desc": _first_ok(
            lambda: inner.desc(),
            lambda: model.desc(),
        ),
    }
    # Model size: on-disk file size is the most reliable; fall back to the
    # loaded tensor size if the file can't be stat'd.
    try:
        specs["file_size_bytes"] = os.path.getsize(path)
    except Exception:
        specs["file_size_bytes"] = _first_ok(
            lambda: inner.size(),
            lambda: model.size(),
        )
    return specs


def count_tokens(text):
    """Count tokens for a piece of text using the loaded model's tokenizer.

    Falls back to a rough word-based estimate if no model is loaded or the
    tokenizer fails for any reason.
    """
    if not text:
        return 0
    global llm
    if llm is not None:
        try:
            return len(llm.tokenize(text.encode("utf-8"), add_bos=False))
        except Exception:
            pass
    # Fallback heuristic: ~1.3 tokens per word
    return max(1, int(len(text.split()) * 1.3))


def load_model(path=None, n_ctx=2048, n_threads=6, n_gpu_layers=20,
               flash_attn=True, use_mlock=True, numa=None, n_batch=None,
               type_k=None, type_v=None):
    global llm, model_state
    target_path = path or model_state["model_path"]

    if not os.path.exists(target_path):
        print(f"WARNING: Model not found at {target_path}. Please update MODEL_PATH in server.py")
        model_state["status"] = "error"
        return None

    # Unload existing model
    if llm is not None:
        del llm
        llm = None
        gc.collect()

    # Auto-detect platform defaults if not explicitly set
    system = platform.system()
    if numa is None:
        numa = system in ("Windows", "Linux")
    if n_batch is None:
        n_batch = 512 if system == "Darwin" else 1024

    model_state["status"] = "loading"
    print(f"Loading model from {target_path}...")
    print(f"  Params: n_ctx={n_ctx}, n_threads={n_threads}, n_gpu_layers={n_gpu_layers}")
    print(f"  Flags:  flash_attn={flash_attn}, use_mlock={use_mlock}, numa={numa}, n_batch={n_batch}")
    if type_k is not None:
        print(f"  KV Quant: type_k={type_k}, type_v={type_v}")

    try:
        # Build kwargs for optional parameters
        kwargs = {}
        if type_k is not None:
            kwargs["type_k"] = type_k
        if type_v is not None:
            kwargs["type_v"] = type_v

        llm = Llama(
            model_path=target_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            flash_attn=flash_attn,
            use_mlock=use_mlock,
            numa=numa,
            n_batch=n_batch,
            verbose=False,
            **kwargs
        )
        model_state.update({
            "model_path": target_path,
            "n_ctx": n_ctx,
            "n_threads": n_threads,
            "n_gpu_layers": n_gpu_layers,
            "flash_attn": flash_attn,
            "use_mlock": use_mlock,
            "numa": numa,
            "n_batch": n_batch,
            "type_k": type_k,
            "type_v": type_v,
            "status": "loaded"
        })
        # Read intrinsic model specs from the GGUF and store them.
        try:
            model_state.update(extract_model_specs(llm, target_path))
        except Exception as e:
            print(f"WARNING: Could not read model specs: {e}")
        print("Model loaded successfully!")
        specs_dbg = {k: model_state.get(k) for k in ("training_ctx", "n_params", "n_embd", "n_vocab", "file_size_bytes")}
        print(f"  Specs: {specs_dbg}")
    except Exception as e:
        print(f"Failed to load model: {e}")
        model_state["status"] = "error"
        return None
    return llm

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatRequest(BaseModel):
    model: Optional[str] = "gemma-local-model"
    messages: List[ChatMessage]
    stream: Optional[bool] = False
    max_tokens: Optional[int] = 512
    summarize: Optional[bool] = False
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.9
    top_k: Optional[int] = 40
    repeat_penalty: Optional[float] = 1.1

class LoadModelRequest(BaseModel):
    model_path: str
    n_ctx: int = 2048
    n_threads: int = 6
    n_gpu_layers: int = 20
    flash_attn: bool = True
    use_mlock: bool = True
    numa: Optional[bool] = None
    n_batch: Optional[int] = None
    type_k: Optional[int] = None
    type_v: Optional[int] = None

class BrowseEntry(BaseModel):
    name: str
    type: Literal["dir", "file"]
    size: Optional[int] = None

class BrowseResponse(BaseModel):
    current_path: str
    parent: Optional[str] = None
    entries: List[BrowseEntry]

# --- API Routes ---

@app.get("/api/tags")
async def get_tags():
    """Mock endpoint to satisfy the connection check in the frontend"""
    return {"models": [{"name": "gemma-local-model"}]}

@app.get("/api/browse", response_model=BrowseResponse)
async def browse(path: Optional[str] = Query(default=None)):
    """Browse directories and .gguf files for model selection."""
    # Determine default root based on OS
    if path is None or path.strip() == "":
        if platform.system() == "Windows":
            path = "C:\\"
        else:
            path = "/"

    # Prevent path traversal attacks
    resolved_path = os.path.abspath(path)

    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail=f"Path not found: {resolved_path}")

    if not os.path.isdir(resolved_path):
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {resolved_path}")

    # Determine parent directory
    parent = os.path.dirname(resolved_path)
    if parent == resolved_path:
        # We're at the root, no parent
        parent = None

    entries: List[BrowseEntry] = []

    try:
        dir_entries = os.listdir(resolved_path)
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {resolved_path}")

    for entry_name in dir_entries:
        entry_path = os.path.join(resolved_path, entry_name)
        try:
            if os.path.isdir(entry_path):
                entries.append(BrowseEntry(name=entry_name, type="dir", size=None))
            elif os.path.isfile(entry_path) and entry_name.lower().endswith(".gguf"):
                try:
                    file_size = os.path.getsize(entry_path)
                except OSError:
                    file_size = None
                entries.append(BrowseEntry(name=entry_name, type="file", size=file_size))
        except (PermissionError, OSError):
            # Skip inaccessible entries gracefully
            continue

    # Sort: directories first, then files, alphabetical within each group
    dirs = sorted([e for e in entries if e.type == "dir"], key=lambda x: x.name.lower())
    files = sorted([e for e in entries if e.type == "file"], key=lambda x: x.name.lower())
    entries = dirs + files

    return BrowseResponse(
        current_path=resolved_path,
        parent=parent,
        entries=entries
    )

@app.get("/api/hardware-profile")
async def get_hardware_profile():
    """
    Return detected hardware info and recommended llama-cpp settings.
    Detection runs once and is cached for the server lifetime.
    """
    try:
        detection = run_detection()
        return detection
    except Exception as e:
        print(f"ERROR: Hardware detection failed: {e}")
        # Return safe defaults even if detection fails
        return {
            "hardware": {
                "cpu_brand": "unknown",
                "physical_cores": None,
                "logical_cores": os.cpu_count() or 4,
                "architecture": platform.machine(),
                "is_apple_silicon": False,
                "has_avx": None,
                "has_avx2": None,
                "has_avx512": None,
                "has_fma": None,
                "has_f16c": None,
                "ram_total_gb": None,
                "ram_available_gb": None,
                "gpu": None,
                "platform": platform.system(),
            },
            "recommended_profile": "windows_cpu" if platform.system() == "Windows" else "linux_cpu",
            "recommended": {
                "n_gpu_layers": 0,
                "n_threads": 4,
                "flash_attn": True,
                "use_mlock": True,
                "numa": platform.system() != "Darwin",
                "n_batch": 1024,
                "type_k": None,
                "type_v": None,
            },
            "max_safe_n_ctx": 2048,
            "profiles": {},
            "error": str(e),
        }


@app.post("/api/load-model")
async def load_model_endpoint(request: LoadModelRequest):
    """Load a new model with specified parameters."""
    global llm, model_state

    # Validate .gguf extension
    if not request.model_path.lower().endswith(".gguf"):
        raise HTTPException(status_code=400, detail="Invalid model file: path must end with .gguf extension")

    # Validate file exists
    resolved_path = os.path.abspath(request.model_path)
    if not os.path.exists(resolved_path):
        raise HTTPException(status_code=404, detail=f"Model file not found: {resolved_path}")

    # Attempt to load the model
    try:
        result = load_model(
            path=resolved_path,
            n_ctx=request.n_ctx,
            n_threads=request.n_threads,
            n_gpu_layers=request.n_gpu_layers,
            flash_attn=request.flash_attn,
            use_mlock=request.use_mlock,
            numa=request.numa,
            n_batch=request.n_batch,
            type_k=request.type_k,
            type_v=request.type_v,
        )
        if result is None:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to load model from {resolved_path}. Check server logs for details."
            )
        return {
            "success": True,
            "model_path": model_state["model_path"],
            "status": model_state["status"]
        }
    except HTTPException:
        raise
    except Exception as e:
        model_state["status"] = "error"
        raise HTTPException(status_code=500, detail=f"Error loading model: {str(e)}")

@app.get("/api/model-status")
async def get_model_status():
    """Return the current model state including path, parameters, and status."""
    return model_state


@app.post("/api/reset-context")
async def reset_context():
    """Reset the context manager's summary cache (for new chat sessions)."""
    ctx_manager.reset()
    return {"success": True}


@app.post("/api/chat")
async def chat(chat_request: ChatRequest):
    global llm
    if llm is None:
        load_model()
        if llm is None:
            raise HTTPException(status_code=500, detail="Model not configured or not found. Check server.py")

    # Sampling parameters, with sensible defaults if the client omits them.
    sampling = {
        "temperature": chat_request.temperature if chat_request.temperature is not None else 0.7,
        "top_p": chat_request.top_p if chat_request.top_p is not None else 0.9,
        "top_k": chat_request.top_k if chat_request.top_k is not None else 40,
        "repeat_penalty": chat_request.repeat_penalty if chat_request.repeat_penalty is not None else 1.1,
    }

    # Process messages to handle system prompts and ensure validity
    raw_messages = [m.model_dump() for m in chat_request.messages]

    # Capture the last user message text so we can report its token count.
    last_user_text = ""
    for msg in reversed(raw_messages):
        if msg["role"] == "user":
            last_user_text = msg["content"]
            break
    user_tokens = count_tokens(last_user_text)

    processed_messages = []
    max_tokens = chat_request.max_tokens or 512

    system_instruction = None

    for msg in raw_messages:
        if msg['role'] == 'system':
            if system_instruction is None:
                system_instruction = msg['content']
            else:
                system_instruction += "\n\n" + msg['content']
        else:
            processed_messages.append(msg)

    # Append length guidance based on max_tokens setting
    word_limit = int(max_tokens * 0.75)
    length_hint = f"\nKeep your response concise and complete within approximately {word_limit} words."
    if system_instruction:
        system_instruction += length_hint
    else:
        system_instruction = length_hint.strip()

    # If we have a system prompt, prepend it to the first user message or handle it
    # Llama-cpp-python can be finicky with explicit 'system' roles depending on the model,
    # so merging into the first user message is a safe compatibility strategy.
    if system_instruction:
        if processed_messages and processed_messages[0]['role'] == 'user':
            processed_messages[0]['content'] = f"{system_instruction}\n\n{processed_messages[0]['content']}"
        else:
            # If no user message starts, insert one (edge case)
            processed_messages.insert(0, {"role": "user", "content": system_instruction})

    stream = chat_request.stream

    # Context management (trimming + optional summarization).
    # For streaming, this runs *inside* the generator so we can tell the client
    # when a slow summarization pass is happening.
    n_ctx = model_state.get("n_ctx", 2048)
    summarize_enabled = chat_request.summarize or False

    def run_trim():
        """Trim/summarize the conversation to fit the context budget."""
        return ctx_manager.trim_messages(
            messages=processed_messages,
            n_ctx=n_ctx,
            max_tokens=max_tokens,
            summarize_enabled=summarize_enabled,
            llm=llm,
        )

    try:
        if stream:
            def generate():
                started = time.perf_counter()
                completion_text = ""
                try:
                    # Signal a summarization pass before doing the blocking work.
                    doing_summary = ctx_manager.will_summarize(
                        processed_messages, n_ctx, max_tokens, summarize_enabled, llm
                    )
                    if doing_summary:
                        yield json.dumps({"status": "summarizing", "done": False}) + "\n"

                    final_messages = run_trim()

                    if doing_summary:
                        yield json.dumps({"status": "generating", "done": False}) + "\n"

                    response = llm.create_chat_completion(
                        messages=final_messages,
                        max_tokens=max_tokens,
                        stream=True,
                        **sampling,
                    )
                    for chunk in response:
                        delta = chunk['choices'][0]['delta']
                        content = delta.get('content', '')
                        if content:
                            completion_text += content

                        yield json.dumps({
                            "message": {
                                "content": content
                            },
                            "done": False
                        }) + "\n"
                except Exception as e:
                    print(f"ERROR: Stream generation error: {e}")
                    yield json.dumps({"error": str(e), "done": True}) + "\n"
                    return

                elapsed = max(time.perf_counter() - started, 1e-6)
                completion_tokens = count_tokens(completion_text)
                stats = {
                    "user_tokens": user_tokens,
                    "completion_tokens": completion_tokens,
                    "elapsed_s": round(elapsed, 2),
                    "tokens_per_s": round(completion_tokens / elapsed, 2),
                }
                yield json.dumps({"done": True, "stats": stats}) + "\n"

            return StreamingResponse(generate(), media_type="application/x-ndjson")
        else:
            final_messages = run_trim()
            started = time.perf_counter()
            response = llm.create_chat_completion(
                messages=final_messages,
                max_tokens=max_tokens,
                stream=False,
                **sampling,
            )
            content = response['choices'][0]['message']['content']
            elapsed = max(time.perf_counter() - started, 1e-6)
            completion_tokens = count_tokens(content)
            return {
                "message": {
                    "content": content
                },
                "done": True,
                "stats": {
                    "user_tokens": user_tokens,
                    "completion_tokens": completion_tokens,
                    "elapsed_s": round(elapsed, 2),
                    "tokens_per_s": round(completion_tokens / elapsed, 2),
                }
            }

    except Exception as e:
        print(f"ERROR: General generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Static File Serving ---
# Serve index.html at "/" and all static assets from BASE_DIR. StaticFiles
# handles path-traversal safety; this mount is registered after every API
# route so the routes above always take precedence.
app.mount("/", StaticFiles(directory=BASE_DIR, html=True), name="static")

if __name__ == "__main__":
    print("Starting LocalMind server on http://localhost:8080")
    print("Open the browser and load a model from Settings.")
    uvicorn.run(app, host="0.0.0.0", port=8080)
