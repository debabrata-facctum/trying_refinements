"""
Hardware Detector for LocalMind.

Cross-platform auto-detection of CPU, RAM, GPU capabilities.
Produces llama-cpp-python-specific recommended parameters.

Detection approach:
  CPU / RAM: psutil + py-cpuinfo (pinned dependencies), stdlib safety net.
  GPU:       OS-native probes (nvidia-smi, system_profiler) — no Python lib covers this.

Supported platforms: Windows, Linux, macOS (Intel + Apple Silicon)
"""

import os
import platform
import subprocess
import multiprocessing
from typing import Optional, Dict, Any


# ---------------------------------------------------------------------------
# Static Profiles — llama-cpp-python optimized configurations
# ---------------------------------------------------------------------------

PROFILES = {
    "windows_cpu": {
        "label": "\U0001fa9f Windows (CPU)",
        "n_gpu_layers": 0,
        "flash_attn": True,
        "use_mlock": True,
        "numa": True,
        "n_batch": 1024,
        "type_k": None,
        "type_v": None,
    },
    "windows_nvidia": {
        "label": "\U0001fa9f Windows (NVIDIA GPU)",
        "n_gpu_layers": -1,
        "flash_attn": True,
        "use_mlock": True,
        "numa": True,
        "n_batch": 1024,
        "type_k": None,
        "type_v": None,
    },
    "linux_cpu": {
        "label": "\U0001f427 Linux (CPU)",
        "n_gpu_layers": 0,
        "flash_attn": True,
        "use_mlock": True,
        "numa": True,
        "n_batch": 1024,
        "type_k": None,
        "type_v": None,
    },
    "linux_nvidia": {
        "label": "\U0001f427 Linux (NVIDIA GPU)",
        "n_gpu_layers": -1,
        "flash_attn": True,
        "use_mlock": True,
        "numa": True,
        "n_batch": 1024,
        "type_k": None,
        "type_v": None,
    },
    "macos_apple_silicon": {
        "label": "\U0001f34f macOS (Apple Silicon)",
        "n_gpu_layers": 99,
        "flash_attn": True,
        "use_mlock": True,
        "numa": False,
        "n_batch": 512,
        "type_k": None,
        "type_v": None,
    },
    "macos_intel": {
        "label": "\U0001f34f macOS (Intel)",
        "n_gpu_layers": 0,
        "flash_attn": True,
        "use_mlock": True,
        "numa": False,
        "n_batch": 512,
        "type_k": None,
        "type_v": None,
    },
}


# ---------------------------------------------------------------------------
# CPU Detection (psutil + py-cpuinfo, stdlib fallback)
# ---------------------------------------------------------------------------

def detect_cpu() -> Dict[str, Any]:
    """
    Detect CPU core counts, brand and instruction flags.

    psutil and py-cpuinfo are pinned dependencies; if either is somehow
    unavailable we fall back to the stdlib (logical cores only).
    """
    system = platform.system()

    # Core counts via psutil, stdlib as the safety net.
    logical = physical = None
    try:
        import psutil
        logical = psutil.cpu_count(logical=True)
        physical = psutil.cpu_count(logical=False)
    except ImportError:
        pass

    info: Dict[str, Any] = {
        "logical_cores": logical or os.cpu_count() or multiprocessing.cpu_count() or 4,
        "physical_cores": physical or logical,
    }

    # Brand + instruction flags via py-cpuinfo, platform.processor() as fallback.
    try:
        import cpuinfo
        cpu = cpuinfo.get_cpu_info()
        flags = cpu.get("flags", [])
        info["brand"] = cpu.get("brand_raw", "unknown")
        info["has_avx"] = "avx" in flags
        info["has_avx2"] = "avx2" in flags
        info["has_avx512"] = any("avx512" in f for f in flags)
        info["has_fma"] = "fma" in flags
        info["has_f16c"] = "f16c" in flags
    except Exception:
        info["brand"] = platform.processor() or "unknown"
        info["has_avx"] = None
        info["has_avx2"] = None
        info["has_avx512"] = None
        info["has_fma"] = None
        info["has_f16c"] = None

    info["architecture"] = platform.machine() or "unknown"
    info["is_apple_silicon"] = (
        system == "Darwin" and info["architecture"] == "arm64"
    )

    return info


# ---------------------------------------------------------------------------
# RAM Detection (psutil, safe default fallback)
# ---------------------------------------------------------------------------

def detect_ram() -> Dict[str, Any]:
    """Detect total/available RAM via psutil, with an 8 GB safe default."""
    try:
        import psutil
        mem = psutil.virtual_memory()
        return {
            "total_bytes": mem.total,
            "total_gb": round(mem.total / (1024 ** 3), 2),
            "available_bytes": mem.available,
            "available_gb": round(mem.available / (1024 ** 3), 2),
            "percent_used": mem.percent,
            "source": "psutil",
        }
    except ImportError:
        return {
            "total_bytes": 8 * (1024 ** 3),
            "total_gb": 8.0,
            "available_bytes": None,
            "available_gb": None,
            "percent_used": None,
            "source": "safe_default",
        }


# ---------------------------------------------------------------------------
# GPU Detection (OS-native probes — no Python lib covers this)
# ---------------------------------------------------------------------------

def _gpu_nvidia_detect() -> Optional[Dict[str, Any]]:
    """Check for NVIDIA GPU via nvidia-smi."""
    try:
        result = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            timeout=10, stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="ignore").strip()

        if not result:
            return None

        # Can have multiple GPUs, take the first line
        first_gpu = result.split("\n")[0]
        parts = first_gpu.split(",")
        if len(parts) >= 2:
            name = parts[0].strip()
            vram_mb = int(parts[1].strip())
            return {
                "type": "nvidia",
                "name": name,
                "vram_mb": vram_mb,
                "vram_gb": round(vram_mb / 1024, 1),
                "source": "nvidia-smi",
            }
        return None
    except (subprocess.SubprocessError, FileNotFoundError, ValueError):
        return None


def _gpu_apple_detect() -> Optional[Dict[str, Any]]:
    """Detect Apple Silicon GPU via system_profiler (macOS arm64 only)."""
    if platform.system() != "Darwin":
        return None
    if platform.machine() != "arm64":
        return None

    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            timeout=10, stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="ignore")

        # Look for chipset model and core count
        chipset = None
        cores = None
        for line in raw.split("\n"):
            stripped = line.strip()
            if "Chipset Model:" in stripped:
                chipset = stripped.split(":", 1)[1].strip()
            elif "Total Number of Cores:" in stripped:
                cores = stripped.split(":", 1)[1].strip()

        if chipset:
            return {
                "type": "apple_metal",
                "name": chipset,
                "gpu_cores": cores,
                "vram_mb": None,  # Unified memory — shared with system RAM
                "vram_gb": None,
                "source": "system_profiler",
            }
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def detect_gpu() -> Optional[Dict[str, Any]]:
    """
    Full GPU detection waterfall.
    Returns None if no usable GPU found.
    """
    # Try NVIDIA first (cross-platform)
    nvidia = _gpu_nvidia_detect()
    if nvidia:
        return nvidia

    # Try Apple Silicon Metal
    apple = _gpu_apple_detect()
    if apple:
        return apple

    return None


# ---------------------------------------------------------------------------
# OS Info
# ---------------------------------------------------------------------------

def detect_os() -> Dict[str, Any]:
    """Gather OS info."""
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
    }

    # macOS version
    if platform.system() == "Darwin":
        try:
            mac_ver = platform.mac_ver()
            if mac_ver[0]:
                info["macos_version"] = mac_ver[0]
        except Exception:
            pass

    return info


# ---------------------------------------------------------------------------
# Recommendation Engine
# ---------------------------------------------------------------------------

def _determine_profile_key(cpu: Dict, gpu: Optional[Dict]) -> str:
    """Pick the best matching profile based on detected hardware."""
    system = platform.system()

    if system == "Darwin":
        if cpu.get("is_apple_silicon"):
            return "macos_apple_silicon"
        else:
            return "macos_intel"
    elif system == "Linux":
        if gpu and gpu.get("type") == "nvidia":
            return "linux_nvidia"
        else:
            return "linux_cpu"
    elif system == "Windows":
        if gpu and gpu.get("type") == "nvidia":
            return "windows_nvidia"
        else:
            return "windows_cpu"
    else:
        return "linux_cpu"  # fallback


def _calculate_threads(cpu: Dict) -> int:
    """
    Calculate recommended thread count.
    Rule: physical cores - 1 (leave one for OS + server).
    Minimum: 2, Maximum: 8 (diminishing returns beyond this for most models).
    """
    physical = cpu.get("physical_cores")
    logical = cpu.get("logical_cores", 4)

    if physical and physical > 0:
        # Use physical cores (P-cores on hybrid architectures)
        recommended = max(2, physical - 1)
    else:
        # Fallback: logical / 2 - 1 (rough physical core estimate)
        estimated_physical = max(2, logical // 2)
        recommended = max(2, estimated_physical - 1)

    # Cap at 8 — beyond this, thread contention often hurts more than helps
    return min(recommended, 8)


def _should_enable_kv_quant(n_ctx: int, system: str) -> bool:
    """Determine if KV-cache quantization should be recommended."""
    # On macOS Apple Silicon, unified memory handles it — no quant needed
    if system == "Darwin" and platform.machine() == "arm64":
        return False
    # Only recommend for large contexts
    return n_ctx > 8192


def build_recommendation(
    cpu: Dict,
    ram: Dict,
    gpu: Optional[Dict],
    n_ctx: int = 2048,
) -> Dict[str, Any]:
    """
    Build a complete recommendation config from detected hardware.

    Args:
        cpu: detect_cpu() result
        ram: detect_ram() result
        gpu: detect_gpu() result (or None)
        n_ctx: context window size (affects KV quant recommendation)

    Returns:
        Dict with profile_key, recommended params, and all profiles.
    """
    system = platform.system()
    profile_key = _determine_profile_key(cpu, gpu)
    profile = PROFILES[profile_key].copy()

    # Override thread count with detected value
    profile["n_threads"] = _calculate_threads(cpu)

    # KV quantization recommendation based on context size
    if _should_enable_kv_quant(n_ctx, system):
        profile["type_k"] = 8  # GGML_TYPE_Q8_0
        profile["type_v"] = 8

    # For partial GPU offload, estimate layers based on VRAM
    if gpu and gpu.get("type") == "nvidia" and gpu.get("vram_gb"):
        vram = gpu["vram_gb"]
        # Rough heuristic: ~0.5GB per layer for 7B Q4 models
        # -1 means offload all, but if VRAM is limited suggest partial
        if vram < 4:
            profile["n_gpu_layers"] = 15
        elif vram < 6:
            profile["n_gpu_layers"] = 25
        elif vram < 8:
            profile["n_gpu_layers"] = 33
        else:
            profile["n_gpu_layers"] = -1  # offload everything

    # Max safe context window recommendation based on available RAM
    total_ram_gb = ram.get("total_gb", 8.0)
    if total_ram_gb >= 32:
        max_safe_ctx = 16384
    elif total_ram_gb >= 16:
        max_safe_ctx = 8192
    elif total_ram_gb >= 8:
        max_safe_ctx = 4096
    else:
        max_safe_ctx = 2048

    return {
        "profile_key": profile_key,
        "recommended": profile,
        "max_safe_n_ctx": max_safe_ctx,
    }


# ---------------------------------------------------------------------------
# Public API — main entry point
# ---------------------------------------------------------------------------

# Cache the detection result so it only runs once per server lifetime
_cached_detection: Optional[Dict[str, Any]] = None


def run_detection() -> Dict[str, Any]:
    """
    Run full hardware detection and return structured result.
    Cached after first call — hardware doesn't change at runtime.
    """
    global _cached_detection
    if _cached_detection is not None:
        return _cached_detection

    cpu = detect_cpu()
    ram = detect_ram()
    gpu = detect_gpu()
    os_info = detect_os()
    recommendation = build_recommendation(cpu, ram, gpu)

    _cached_detection = {
        "hardware": {
            "cpu_brand": cpu.get("brand", "unknown"),
            "physical_cores": cpu.get("physical_cores"),
            "logical_cores": cpu.get("logical_cores"),
            "architecture": cpu.get("architecture", "unknown"),
            "is_apple_silicon": cpu.get("is_apple_silicon", False),
            "has_avx": cpu.get("has_avx"),
            "has_avx2": cpu.get("has_avx2"),
            "has_avx512": cpu.get("has_avx512"),
            "has_fma": cpu.get("has_fma"),
            "has_f16c": cpu.get("has_f16c"),
            "ram_total_gb": ram.get("total_gb"),
            "ram_available_gb": ram.get("available_gb"),
            "gpu": gpu,
            "platform": os_info.get("system"),
        },
        "recommended_profile": recommendation["profile_key"],
        "recommended": recommendation["recommended"],
        "max_safe_n_ctx": recommendation["max_safe_n_ctx"],
        "profiles": PROFILES,
    }

    return _cached_detection


# ---------------------------------------------------------------------------
# CLI — run standalone for testing
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    print("Running hardware detection...")
    result = run_detection()
    print(json.dumps(result, indent=2, default=str))

    hw = result["hardware"]
    rec = result["recommended"]

    print("\n--- Hardware Summary ---")
    print(f"  Platform:  {hw['platform']}")
    print(f"  CPU:       {hw['cpu_brand']}")
    print(f"  Cores:     {hw['logical_cores']} logical / {hw['physical_cores']} physical")
    print(f"  Arch:      {hw['architecture']}")
    print(f"  RAM:       {hw['ram_total_gb']} GB total, {hw['ram_available_gb']} GB available")
    if hw["gpu"]:
        print(f"  GPU:       {hw['gpu']['name']} ({hw['gpu'].get('vram_gb', 'unified')} GB)")
    else:
        print(f"  GPU:       None detected")

    # CPU flags
    flags = []
    if hw.get("has_avx2"):
        flags.append("AVX2")
    if hw.get("has_avx512"):
        flags.append("AVX-512")
    if hw.get("has_fma"):
        flags.append("FMA")
    if hw.get("has_f16c"):
        flags.append("F16C")
    if flags:
        print(f"  CPU Flags: {', '.join(flags)}")

    print(f"\n--- Recommended Profile: {result['recommended_profile']} ---")
    print(f"  GPU Layers:      {rec['n_gpu_layers']}")
    print(f"  Threads:         {rec['n_threads']}")
    print(f"  Flash Attention: {rec['flash_attn']}")
    print(f"  Memory Lock:     {rec['use_mlock']}")
    print(f"  NUMA:            {rec['numa']}")
    print(f"  Batch Size:      {rec['n_batch']}")
    print(f"  KV Quant (k):    {rec['type_k']}")
    print(f"  KV Quant (v):    {rec['type_v']}")
    print(f"  Max safe n_ctx:  {result['max_safe_n_ctx']}")
