"""
Hardware-Aware Auto-Detection Script (macOS-first)

Detects CPU, GPU, RAM, and OS info on macOS and writes
the results to a JSON config file (hw_config.json).

Layered fallback approach:
  Layer A: Python libs (psutil)
  Layer B: Framework check (PyTorch MPS)
  Layer C: OS native commands (system_profiler, sysctl)
  Layer D: Safe defaults
"""

import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# CPU Detection
# ---------------------------------------------------------------------------

def _cpu_via_psutil():
    """Layer A: psutil for detailed CPU info."""
    try:
        import psutil
        logical = psutil.cpu_count(logical=True)
        physical = psutil.cpu_count(logical=False)
        if logical is None and physical is None:
            return None
        return {
            "logical_cores": logical or physical,
            "physical_cores": physical or logical,
            "source": "psutil",
        }
    except ImportError:
        return None


def _cpu_via_stdlib():
    """Layer C (stdlib): os.cpu_count / multiprocessing as fallback."""
    count = os.cpu_count()
    if count is not None:
        return {
            "logical_cores": count,
            "physical_cores": None,  # stdlib can't distinguish
            "source": "os.cpu_count",
        }

    try:
        import multiprocessing
        count = multiprocessing.cpu_count()
        return {
            "logical_cores": count,
            "physical_cores": None,
            "source": "multiprocessing.cpu_count",
        }
    except (ImportError, NotImplementedError):
        return None


def _cpu_via_sysctl():
    """Layer C (macOS): sysctl for core counts."""
    try:
        logical = subprocess.check_output(
            ["sysctl", "-n", "hw.logicalcpu"],
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()

        physical = subprocess.check_output(
            ["sysctl", "-n", "hw.physicalcpu"],
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()

        return {
            "logical_cores": int(logical),
            "physical_cores": int(physical),
            "source": "sysctl",
        }
    except (subprocess.SubprocessError, FileNotFoundError, ValueError):
        return None


def _cpu_brand_mac():
    """Get CPU brand string on macOS via sysctl."""
    try:
        brand = subprocess.check_output(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        return brand
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _cpu_arch():
    """Get CPU architecture (arm64 for Apple Silicon, x86_64 for Intel)."""
    machine = platform.machine()
    return machine if machine else "unknown"


def detect_cpu():
    """Waterfall: psutil -> stdlib -> sysctl -> safe default."""
    info = _cpu_via_psutil() or _cpu_via_stdlib() or _cpu_via_sysctl()

    if info is None:
        info = {
            "logical_cores": 2,
            "physical_cores": 2,
            "source": "safe_default",
        }

    # Enrich with brand and architecture
    info["brand"] = _cpu_brand_mac() or platform.processor() or "unknown"
    info["architecture"] = _cpu_arch()
    info["is_apple_silicon"] = info["architecture"] == "arm64"

    return info


# ---------------------------------------------------------------------------
# RAM Detection
# ---------------------------------------------------------------------------

def _ram_via_psutil():
    """Layer A: psutil for RAM."""
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
        return None


def _ram_via_sysctl():
    """Layer C (macOS): sysctl for total RAM."""
    try:
        raw = subprocess.check_output(
            ["sysctl", "-n", "hw.memsize"],
            timeout=5,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8").strip()
        total = int(raw)
        return {
            "total_bytes": total,
            "total_gb": round(total / (1024 ** 3), 2),
            "available_bytes": None,
            "available_gb": None,
            "percent_used": None,
            "source": "sysctl",
        }
    except (subprocess.SubprocessError, FileNotFoundError, ValueError):
        return None


def detect_ram():
    """Waterfall: psutil -> sysctl -> safe default."""
    info = _ram_via_psutil() or _ram_via_sysctl()

    if info is None:
        info = {
            "total_bytes": 4 * (1024 ** 3),
            "total_gb": 4.0,
            "available_bytes": None,
            "available_gb": None,
            "percent_used": None,
            "source": "safe_default",
        }

    return info


# ---------------------------------------------------------------------------
# GPU Detection (macOS)
# ---------------------------------------------------------------------------

def _gpu_via_pytorch_mps():
    """Layer B: Check PyTorch MPS backend for Apple Silicon GPU."""
    try:
        import torch
        mps_available = torch.backends.mps.is_available()
        mps_built = torch.backends.mps.is_built()
        return {
            "mps_available": mps_available,
            "mps_built": mps_built,
            "pytorch_version": torch.__version__,
            "source": "pytorch_mps",
        }
    except (ImportError, AttributeError):
        return None


def _gpu_via_system_profiler():
    """Layer C (macOS): system_profiler for GPU hardware info."""
    try:
        raw = subprocess.check_output(
            ["system_profiler", "SPDisplaysDataType"],
            timeout=10,
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="ignore")

        gpu_info = _parse_system_profiler_gpu(raw)
        return gpu_info
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _parse_system_profiler_gpu(raw_output):
    """Parse system_profiler SPDisplaysDataType output into structured data."""
    gpus = []
    current_gpu = {}
    lines = raw_output.strip().split("\n")

    for line in lines:
        stripped = line.strip()

        # New GPU block — lines that aren't key:value and aren't the header
        if stripped and ":" not in stripped and stripped != "Graphics/Displays:":
            if current_gpu:
                gpus.append(current_gpu)
            current_gpu = {"name": stripped}
            continue

        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()

            if key == "chipset_model":
                current_gpu["chipset_model"] = value
            elif key == "type":
                current_gpu["type"] = value
            elif key == "vram" or key == "vram_(total)":
                current_gpu["vram"] = value
            elif key == "vendor":
                current_gpu["vendor"] = value
            elif key == "metal_support" or key == "metal_family":
                current_gpu["metal_support"] = value
            elif key == "total_number_of_cores":
                current_gpu["gpu_cores"] = value

    if current_gpu:
        gpus.append(current_gpu)

    return {
        "devices": gpus,
        "count": len(gpus),
        "source": "system_profiler",
    }


def detect_gpu():
    """
    Waterfall for macOS GPU:
      1. PyTorch MPS check (is it actually usable?)
      2. system_profiler (what hardware is there?)
      3. Safe default
    """
    framework_info = _gpu_via_pytorch_mps()
    hardware_info = _gpu_via_system_profiler()

    # Determine acceleration mode
    is_apple_silicon = _cpu_arch() == "arm64"

    if framework_info and framework_info.get("mps_available"):
        accel_mode = "METAL_ACCELERATED"
    elif is_apple_silicon:
        # Hardware is there but PyTorch MPS not installed/available
        accel_mode = "METAL_CAPABLE_NO_FRAMEWORK"
    else:
        accel_mode = "CPU_ONLY"

    result = {
        "acceleration_mode": accel_mode,
        "is_apple_silicon": is_apple_silicon,
        "framework_check": framework_info,
        "hardware": hardware_info,
    }

    if result["framework_check"] is None and result["hardware"] is None:
        result["source"] = "safe_default"
        result["hardware"] = {
            "devices": [],
            "count": 0,
            "source": "safe_default",
        }

    return result


# ---------------------------------------------------------------------------
# OS Info
# ---------------------------------------------------------------------------

def detect_os():
    """Gather macOS system info."""
    info = {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
    }

    # macOS-specific: get friendly version name
    try:
        mac_ver = platform.mac_ver()
        if mac_ver[0]:
            info["macos_version"] = mac_ver[0]
    except Exception:
        pass

    return info


# ---------------------------------------------------------------------------
# Wiring Engine — translate raw data into app-usable profile
# ---------------------------------------------------------------------------

def build_profile(cpu, ram, gpu):
    """
    Translate detected hardware into an actionable profile
    for the LLM inference app.
    """
    logical = cpu.get("logical_cores", 2)
    physical = cpu.get("physical_cores") or logical
    total_ram_gb = ram.get("total_gb", 4.0)

    # Worker count: leave 1 core free for the OS / main thread
    worker_threads = max(1, logical - 1)

    # Compute threads: use physical cores for heavy work
    compute_threads = max(1, physical - 1)

    # Memory limit: tiered approach based on total RAM
    if total_ram_gb >= 16:
        memory_fraction = 0.80
    elif total_ram_gb >= 8:
        memory_fraction = 0.70
    else:
        memory_fraction = 0.60
    memory_limit_gb = round(total_ram_gb * memory_fraction, 2)

    # GPU acceleration
    accel_mode = gpu.get("acceleration_mode", "CPU_ONLY")
    use_gpu = accel_mode in ("METAL_ACCELERATED", "CUDA_ACCELERATED")

    # Apple Silicon unified memory — GPU shares system RAM
    if cpu.get("is_apple_silicon") and use_gpu:
        gpu_memory_note = "unified_memory (GPU shares system RAM)"
        gpu_memory_gb = memory_limit_gb  # same pool
    else:
        gpu_memory_note = "discrete_or_none"
        gpu_memory_gb = 0

    return {
        "worker_threads": worker_threads,
        "compute_threads": compute_threads,
        "memory_limit_gb": memory_limit_gb,
        "memory_fraction": memory_fraction,
        "use_gpu": use_gpu,
        "acceleration_mode": accel_mode,
        "gpu_memory_gb": gpu_memory_gb,
        "gpu_memory_note": gpu_memory_note,
    }


# ---------------------------------------------------------------------------
# Main — run detection and write config
# ---------------------------------------------------------------------------

def run_detection():
    """Run full hardware detection and return structured results."""
    cpu = detect_cpu()
    ram = detect_ram()
    gpu = detect_gpu()
    os_info = detect_os()
    profile = build_profile(cpu, ram, gpu)

    config = {
        "detection_timestamp": datetime.now(timezone.utc).isoformat(),
        "detection_platform": "macos",
        "os": os_info,
        "cpu": cpu,
        "ram": ram,
        "gpu": gpu,
        "profile": profile,
    }

    return config


def write_config(config, output_path=None):
    """Write config dict to hw_config.json alongside this script."""
    if output_path is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_path = os.path.join(script_dir, "hw_config.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    return output_path


def main():
    # Guard: warn if not on macOS (still runs, but results may be partial)
    current_os = platform.system()
    if current_os != "Darwin":
        print(f"[WARNING] This script is built for macOS. "
              f"Detected: {current_os}. Results may be incomplete.")

    print("Running hardware detection...")
    config = run_detection()

    path = write_config(config)
    print(f"Config written to: {path}")

    # Print summary
    p = config["profile"]
    cpu = config["cpu"]
    ram = config["ram"]
    gpu = config["gpu"]

    print("\n--- Hardware Summary ---")
    print(f"  CPU:    {cpu['brand']}")
    print(f"          {cpu['logical_cores']} logical / "
          f"{cpu['physical_cores']} physical cores "
          f"({cpu['architecture']})")
    print(f"  RAM:    {ram['total_gb']} GB total")
    print(f"  GPU:    {gpu['acceleration_mode']}")

    if gpu.get("hardware") and gpu["hardware"].get("devices"):
        for dev in gpu["hardware"]["devices"]:
            name = dev.get("chipset_model") or dev.get("name", "unknown")
            vram = dev.get("vram", "shared/unified")
            print(f"          -> {name} (VRAM: {vram})")

    print(f"\n--- App Profile ---")
    print(f"  Workers:       {p['worker_threads']} threads")
    print(f"  Compute:       {p['compute_threads']} threads")
    print(f"  Memory limit:  {p['memory_limit_gb']} GB "
          f"({int(p['memory_fraction'] * 100)}% of total)")
    print(f"  GPU accel:     {p['use_gpu']} ({p['acceleration_mode']})")

    if p["gpu_memory_gb"] > 0:
        print(f"  GPU memory:    {p['gpu_memory_gb']} GB "
              f"({p['gpu_memory_note']})")


if __name__ == "__main__":
    main()
