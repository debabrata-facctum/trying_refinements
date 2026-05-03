"""
Model Config Builder

Reads hw_config.json (produced by hw_detect.py) and translates
hardware capabilities into llama-cpp-python parameters:
  - n_ctx        (context window size)
  - n_threads    (CPU threads for inference)
  - n_gpu_layers (layers offloaded to GPU)

The logic is intentionally conservative — it picks values that
will run reliably on the detected hardware rather than pushing
limits and risking OOM kills or swap thrashing.
"""

import json
import os


# ---------------------------------------------------------------------------
# Context window sizing
# ---------------------------------------------------------------------------
#
# Context window directly impacts RAM usage. Rough rule of thumb for
# quantized models (Q4_K_M):
#   ~1 MB per 512 tokens of context
#   so 2048 ctx ≈ 4 MB, 4096 ctx ≈ 8 MB, 8192 ctx ≈ 16 MB
#
# The model weights themselves are the big cost (e.g. 7B Q4 ≈ 4 GB).
# Context is small relative to weights, but on low-RAM machines every
# bit counts.
#
# We size context based on recommended_memory_gb (the safe limit that
# accounts for what's actually free right now).

_CTX_TIERS = [
    # (min_recommended_gb, context_size)
    (6.0,  8192),   # plenty of headroom
    (4.0,  4096),   # comfortable
    (2.0,  2048),   # tight but workable
    (0.0,   512),   # survival mode
]


def _pick_context_size(recommended_gb):
    """Pick context window size based on available memory budget."""
    for min_gb, ctx in _CTX_TIERS:
        if recommended_gb >= min_gb:
            return ctx
    return 512


# ---------------------------------------------------------------------------
# Thread count
# ---------------------------------------------------------------------------
#
# llama-cpp uses n_threads for the compute-heavy matrix multiplications.
# Best practice:
#   - Use physical cores (not logical/hyperthreaded) for compute
#   - Leave 1 core free for the OS + main thread
#   - On Apple Silicon all cores are physical, so logical == physical
#
# The hw_config profile already calculates compute_threads this way,
# so we just use it directly.


# ---------------------------------------------------------------------------
# GPU layer offloading
# ---------------------------------------------------------------------------
#
# n_gpu_layers controls how many transformer layers run on GPU vs CPU.
# More layers on GPU = faster, but uses more VRAM (or unified memory).
#
# For Apple Silicon (unified memory):
#   The GPU and CPU share the same RAM pool, so offloading layers to
#   GPU doesn't cost "extra" memory — it just changes which processor
#   does the work. We can be more aggressive here.
#
# For discrete GPUs (NVIDIA):
#   VRAM is separate and limited. Need to be careful not to exceed it.
#
# For CPU-only:
#   n_gpu_layers = 0
#
# Typical 7B model has ~32 transformer layers.
# Setting n_gpu_layers = -1 means "offload everything" in llama-cpp.

_GPU_LAYER_TIERS_UNIFIED = [
    # (min_recommended_gb, n_gpu_layers)
    # Unified memory (Apple Silicon) — can be aggressive
    (6.0,  -1),    # offload all layers
    (4.0,   24),   # most layers
    (2.0,   12),   # partial offload
    (0.0,    0),   # too tight, CPU only
]

_GPU_LAYER_TIERS_DISCRETE = [
    # (min_vram_gb, n_gpu_layers)
    # Discrete GPU (NVIDIA) — based on VRAM
    (8.0,  -1),    # offload all
    (6.0,   28),
    (4.0,   20),
    (2.0,   10),
    (0.0,    0),
]


def _pick_gpu_layers(profile):
    """Pick n_gpu_layers based on GPU type and available memory."""
    if not profile.get("use_gpu"):
        return 0

    accel = profile.get("acceleration_mode", "CPU_ONLY")

    if accel == "METAL_ACCELERATED":
        # Unified memory — use recommended_memory_gb as the budget
        budget = profile.get("recommended_memory_gb", 0)
        for min_gb, layers in _GPU_LAYER_TIERS_UNIFIED:
            if budget >= min_gb:
                return layers

    elif accel == "CUDA_ACCELERATED":
        # Discrete VRAM — use gpu_memory_gb
        vram = profile.get("gpu_memory_gb", 0)
        for min_gb, layers in _GPU_LAYER_TIERS_DISCRETE:
            if vram >= min_gb:
                return layers

    return 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_model_config(hw_config):
    """
    Given a hw_config dict (from hw_detect.run_detection or hw_config.json),
    return the llama-cpp-python parameters the server should use.

    Returns dict with:
      - n_ctx:        int   (context window tokens)
      - n_threads:    int   (CPU threads for inference)
      - n_gpu_layers: int   (layers offloaded to GPU, -1 = all)
      - reasoning:    dict  (explains why each value was chosen)
    """
    profile = hw_config.get("profile", {})
    cpu = hw_config.get("cpu", {})
    ram = hw_config.get("ram", {})

    recommended_gb = profile.get("recommended_memory_gb",
                                 profile.get("memory_limit_gb", 4.0))

    n_ctx = _pick_context_size(recommended_gb)
    n_threads = profile.get("compute_threads", max(1, (cpu.get("physical_cores") or 2) - 1))
    n_gpu_layers = _pick_gpu_layers(profile)

    return {
        "n_ctx": n_ctx,
        "n_threads": n_threads,
        "n_gpu_layers": n_gpu_layers,
        "reasoning": {
            "n_ctx": (
                f"recommended_memory={recommended_gb} GB -> "
                f"context window={n_ctx} tokens"
            ),
            "n_threads": (
                f"physical_cores={cpu.get('physical_cores', '?')}, "
                f"using {n_threads} for inference "
                f"(leaving 1 for OS/main thread)"
            ),
            "n_gpu_layers": (
                f"acceleration={profile.get('acceleration_mode', 'CPU_ONLY')}, "
                f"gpu_memory={profile.get('gpu_memory_gb', 0)} GB -> "
                f"{n_gpu_layers} layers offloaded"
                + (" (all)" if n_gpu_layers == -1 else "")
            ),
        },
    }


def load_hw_config(config_path=None):
    """Load hw_config.json from disk. Returns dict or None."""
    if config_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "hw_config.json")

    if not os.path.exists(config_path):
        return None

    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_model_config(model_config, output_path=None):
    """Write model config to model_config.json alongside this script."""
    if output_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, "model_config.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(model_config, f, indent=2, ensure_ascii=False)

    return output_path


if __name__ == "__main__":
    hw = load_hw_config()
    if hw is None:
        print("No hw_config.json found. Run hw_detect.py first.")
        raise SystemExit(1)

    mc = build_model_config(hw)
    path = write_model_config(mc)
    print(f"Model config written to: {path}")
    print(json.dumps(mc, indent=2))
