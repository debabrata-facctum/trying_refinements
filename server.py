import os
import gc
import json
import platform
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from llama_cpp import Llama
from pydantic import BaseModel
from typing import List, Optional, Literal

app = FastAPI(title="Local LLM Server")

# Enable CORS for the frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    print(f"DEBUG: Incoming {request.method} request to {request.url.path}")
    response = await call_next(request)
    print(f"DEBUG: Response status: {response.status_code}")
    return response

# Configuration
# IMPORTANT: Update this path to your local .gguf model file
MODEL_PATH = r"C:\llama\models\mistral-7b-instruct-v0.2.Q4_K_M.gguf"

# Global model instance
llm = None

# Model state tracking
model_state = {
    "model_path": MODEL_PATH,
    "n_ctx": 2048,
    "n_threads": 10,
    "n_gpu_layers": 20,
    "status": "not_loaded"
}


def load_model(path=None, n_ctx=2048, n_threads=10, n_gpu_layers=20):
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

    model_state["status"] = "loading"
    print(f"Loading model from {target_path}...")
    try:
        llm = Llama(
            model_path=target_path,
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            verbose=False
        )
        model_state.update({
            "model_path": target_path,
            "n_ctx": n_ctx,
            "n_threads": n_threads,
            "n_gpu_layers": n_gpu_layers,
            "status": "loaded"
        })
        print("Model loaded successfully!")
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

class LoadModelRequest(BaseModel):
    model_path: str
    n_ctx: int = 2048
    n_threads: int = 10
    n_gpu_layers: int = 20

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
    """Mock endpoint to satisfy the connection check in script.js"""
    print("DEBUG: Received request for /api/tags")
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
            n_gpu_layers=request.n_gpu_layers
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


@app.post("/api/chat")
async def chat(chat_request: ChatRequest):
    print(f"DEBUG: Received chat request: {chat_request}")
    global llm
    if llm is None:
        load_model()
        if llm is None:
            print("ERROR: Model failed to load")
            raise HTTPException(status_code=500, detail="Model not configured or not found. Check server.py")

    # Process messages to handle system prompts and ensure validity
    raw_messages = [m.model_dump() for m in chat_request.messages]
    processed_messages = []
    
    system_instruction = None
    
    for msg in raw_messages:
        if msg['role'] == 'system':
            if system_instruction is None:
                system_instruction = msg['content']
            else:
                system_instruction += "\n\n" + msg['content']
        else:
            processed_messages.append(msg)
            
    # If we have a system prompt, prepend it to the first user message or handle it
    # Llama-cpp-python can be finicky with explicit 'system' roles depending on the model,
    # so merging into the first user message is a safe compatibility strategy.
    if system_instruction:
        if processed_messages and processed_messages[0]['role'] == 'user':
            processed_messages[0]['content'] = f"{system_instruction}\n\n{processed_messages[0]['content']}"
        else:
            # If no user message starts, insert one (edge case)
            processed_messages.insert(0, {"role": "user", "content": system_instruction})
            
    print(f"DEBUG: Processed {len(raw_messages)} raw messages into {len(processed_messages)} messages for inference.")
    stream = chat_request.stream
    
    try:
        if stream:
            def generate():
                print("DEBUG: Starting stream generation...")
                try:
                    response = llm.create_chat_completion(
                        messages=processed_messages,
                        stream=True
                    )
                    for chunk in response:
                        delta = chunk['choices'][0]['delta']
                        content = delta.get('content', '')
                        
                        yield json.dumps({
                            "message": {
                                "content": content
                            },
                            "done": False
                        }) + "\n"
                except Exception as e:
                    print(f"ERROR: Stream generation error: {e}")
                    yield json.dumps({"error": str(e), "done": True}) + "\n"
                
                yield json.dumps({"done": True}) + "\n"
                print("DEBUG: Stream generation complete.")

            return StreamingResponse(generate(), media_type="application/x-ndjson")
        else:
            print("DEBUG: Starting non-stream generation...")
            response = llm.create_chat_completion(
                messages=processed_messages,
                stream=False
            )
            content = response['choices'][0]['message']['content']
            print("DEBUG: Generation complete.")
            return {
                "message": {
                    "content": content
                },
                "done": True
            }

    except Exception as e:
        print(f"ERROR: General generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Static File Serving ---

@app.get("/")
async def serve_index():
    print("DEBUG: Serving index.html")
    return FileResponse("index.html")

@app.get("/{file_path:path}")
async def serve_static(file_path: str):
    # This serves script.js, style.css, etc.
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)
    print(f"DEBUG: File not found: {file_path}")
    raise HTTPException(status_code=404)

if __name__ == "__main__":
    print(f"Starting server on http://localhost:8080")
    print(f"Please ensure your model file exists at: {MODEL_PATH}")
    uvicorn.run(app, host="0.0.0.0", port=8080)