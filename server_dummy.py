"""
Dummy Server — Hardware-Aware LLM Config Demo

This script demonstrates the full flow:
  1. Run hardware detection (hw_detect.py)
  2. Write hw_config.json
  3. Translate hardware into model params (model_config.py)
  4. Write model_config.json
  5. Load the config and print what the real server would use

No FastAPI, no model loading — just the config pipeline.

Compare with the original Web_llm/server.py which hardcodes:
  n_ctx=2048, n_threads=10, n_gpu_layers=20
"""

import json
import os

from hw_detect import run_detection, write_config
from model_config import build_model_config, write_model_config


def get_model_params():
    """
    Full pipeline: detect hardware -> build config -> return params.

    Returns a dict with the llama-cpp-python parameters:
      {
        "n_ctx": 2048,
        "n_threads": 7,
        "n_gpu_layers": -1,
        "reasoning": { ... }
      }
    """
    # Step 1: Detect hardware
    print("[1/3] Detecting hardware...")
    hw_config = run_detection()

    # Step 2: Write hw_config.json (so it can be inspected / reused)
    hw_path = write_config(hw_config)
    print(f"[2/3] Hardware config written to: {hw_path}")

    # Step 3: Translate hardware into model parameters
    model_config = build_model_config(hw_config)
    mc_path = write_model_config(model_config)
    print(f"[3/3] Model config written to: {mc_path}")

    return model_config, hw_config


def print_comparison(model_config, hw_config):
    """Show what the hardcoded server uses vs what we'd auto-detect."""
    # Original hardcoded values from Web_llm/server.py
    hardcoded = {
        "n_ctx": 2048,
        "n_threads": 10,
        "n_gpu_layers": 20,
    }

    auto = {
        "n_ctx": model_config["n_ctx"],
        "n_threads": model_config["n_threads"],
        "n_gpu_layers": model_config["n_gpu_layers"],
    }

    cpu = hw_config.get("cpu", {})
    ram = hw_config.get("ram", {})
    profile = hw_config.get("profile", {})

    print("\n" + "=" * 60)
    print("  HARDWARE-AWARE CONFIG vs HARDCODED CONFIG")
    print("=" * 60)

    print(f"\n  Machine: {cpu.get('brand', 'unknown')}")
    print(f"  Cores:   {cpu.get('physical_cores', '?')} physical / "
          f"{cpu.get('logical_cores', '?')} logical")
    print(f"  RAM:     {ram.get('total_gb', '?')} GB total, "
          f"{ram.get('available_gb', '?')} GB available")
    print(f"  GPU:     {profile.get('acceleration_mode', 'unknown')}")

    print(f"\n  {'Parameter':<16} {'Hardcoded':<12} {'Auto-detected':<14} {'Why'}")
    print(f"  {'-'*16} {'-'*12} {'-'*14} {'-'*30}")

    for key in ["n_ctx", "n_threads", "n_gpu_layers"]:
        hc = hardcoded[key]
        ad = auto[key]
        ad_display = "ALL" if ad == -1 else str(ad)
        reason = model_config["reasoning"][key]

        # Flag if hardcoded value is problematic for this machine
        flag = ""
        if key == "n_threads" and hc > cpu.get("logical_cores", 99):
            flag = " ⚠️  exceeds available cores!"
        elif key == "n_gpu_layers" and hc > 0 and not profile.get("use_gpu"):
            flag = " ⚠️  no GPU available!"

        print(f"  {key:<16} {str(hc):<12} {ad_display:<14} {reason}")
        if flag:
            print(f"  {'':>44}{flag}")

    print(f"\n  Memory budget: {profile.get('recommended_memory_gb', '?')} GB "
          f"(safe to use right now)")
    print(f"  Memory max:    {profile.get('memory_limit_gb', '?')} GB "
          f"(theoretical limit)")
    print("=" * 60)


def main():
    model_config, hw_config = get_model_params()
    print_comparison(model_config, hw_config)

    # This is what the real server would use instead of hardcoded values:
    print("\n--- What the server would pass to Llama() ---")
    print(f"  Llama(")
    print(f"      model_path=MODEL_PATH,")
    print(f"      n_ctx={model_config['n_ctx']},")
    print(f"      n_threads={model_config['n_threads']},")
    n_gpu = model_config['n_gpu_layers']
    print(f"      n_gpu_layers={n_gpu},  "
          f"{'# all layers' if n_gpu == -1 else ''}")
    print(f"      verbose=False,")
    print(f"  )")


if __name__ == "__main__":
    main()
