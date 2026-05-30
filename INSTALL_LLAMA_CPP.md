# Installation Guide for llama-cpp-python

A practical guide for installing llama-cpp-python across different operating systems and hardware configurations. Covers CPU-only and GPU-accelerated builds.

---

## Python Code — Same Across All Platforms

Regardless of OS or backend, the Python API is identical:

```python
from llama_cpp import Llama

m = Llama(
    model_path="path/to/model.gguf",
    n_ctx=4096,
    n_gpu_layers=-1,   # -1 = offload all layers to GPU
                       #  0 = CPU only
                       # >0 = offload that many layers
)
```

The only thing that changes is how you install the package.

---

## Summary Table

| OS | Target | Extra Install | CMAKE_ARGS | Complexity |
|----|--------|---------------|------------|------------|
| Windows | CPU | VS Build Tools | `-DGGML_AVX2=ON ...` | High |
| Windows | GPU (NVIDIA) | VS Build Tools + CUDA Toolkit | `-DGGML_CUDA=ON` | High |
| Linux | CPU | `build-essential cmake` | None needed | Low |
| Linux | GPU (NVIDIA) | `nvidia-cuda-toolkit` | `-DGGML_CUDA=ON` | Low |
| macOS | CPU | Xcode CLI tools | None needed | Trivial |
| macOS | GPU (Metal) | Xcode CLI tools | None (Metal is default) | Trivial |

---

## Windows

### CPU Build

A practical guide based on real installation issues encountered when setting up llama-cpp-python for the Local LLM server. Covers the happy path plus every edge case we hit and how to fix it.

#### TL;DR — Decision Tree

```
1. Try the official prebuilt wheel from PyPI
   └─ Works? Done.
   └─ Crash on model load (0xc000001d)? → Step 2

2. Try the GitHub-hosted prebuilt wheel
   └─ Works? Done.
   └─ Same crash? → Step 3

3. Build from source with CPU-specific flags (most reliable fix)
```

#### Prerequisites

- **Windows 10/11 x64**
- **Python 3.10, 3.11, or 3.12** (64-bit). Verify with:
  ```cmd
  python --version
  python -c "import struct; print(struct.calcsize('P') * 8, 'bit')"
  ```
  Should print `Python 3.x.x` and `64 bit`.
- **A GGUF model file** placed somewhere accessible (e.g., `C:\ml_models\Llama-3.1-8B-Instruct-Q4_K_M.gguf`).
- **At least 4 GB of free disk space** if you'll be building from source (the source tarball is ~70 MB but expands to several hundred MB during compilation).
- **Stable internet connection** — pip downloads ~70 MB for the source build.

> **Tip:** It's strongly recommended to do everything inside a virtual environment. See the "Using a Virtual Environment" section below — you can set it up first and run all subsequent commands inside it.

#### Step 0 — Check Your CPU's Instruction Set

Before installing anything, find out what your CPU supports. This determines which builds will work.

```cmd
pip install py-cpuinfo
python -c "import cpuinfo; print([f for f in cpuinfo.get_cpu_info()['flags'] if 'avx' in f or 'fma' in f or 'f16c' in f])"
```

(If you'd rather not pollute your system Python with `py-cpuinfo`, do this inside a venv first.)

Look for these flags:

| Flag       | What it means                                  |
|------------|------------------------------------------------|
| `avx`      | Basic AVX support                              |
| `avx2`     | AVX2 (most modern CPUs have this)              |
| `avx512f`  | AVX-512 Foundation                             |
| `fma`      | Fused multiply-add                             |
| `f16c`     | Half-precision float conversion                |

**If you see `avx2` but NOT any `avx512*` flags**, you have an AVX2-only CPU. The default prebuilt wheels often target AVX-512 and will crash on your machine. You'll likely need to build from source. This is especially common when running inside a VM, since hypervisors don't always expose AVX-512 to guests even when the host supports it.

#### Method 1 — Official PyPI Wheel (Try This First)

The simplest approach. Works on most physical machines.

```cmd
pip install llama-cpp-python
```

**Test it:**

Create `test_llm.py`:

```python
from llama_cpp import Llama

print("Loading model...")
m = Llama(
    model_path=r"C:\ml_models\YOUR-MODEL.gguf",
    n_ctx=512,
    n_gpu_layers=0,
    verbose=True,
)
print("OK - model loaded successfully")
```

Run:

```cmd
python test_llm.py
```

If you see `OK - model loaded successfully`, you're done.

**If you see this crash**:

```
Failed to load model: [WinError -1073741795] Windows Error 0xc000001d
AttributeError: 'LlamaModel' object has no attribute 'sampler'
```

That's `STATUS_ILLEGAL_INSTRUCTION` — the binary uses CPU instructions your machine doesn't support. Go to Method 2 or 3.

#### Method 2 — GitHub Prebuilt Wheel

The maintainer publishes a `py3-none-win_amd64` wheel that works across all Python 3.x versions on Windows x64.

```cmd
pip uninstall llama-cpp-python -y
pip install https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.23/llama_cpp_python-0.3.23-py3-none-win_amd64.whl
```

This is the exact wheel we tested with. For a newer version, browse https://github.com/abetlen/llama-cpp-python/releases and pick the file ending in `py3-none-win_amd64.whl`.

Test the same way as Method 1.

If this also crashes with `0xc000001d`, the wheel was likely compiled with AVX-512. Move to Method 3.

#### Method 3 — Build from Source (Definitive Fix)

This compiles the binary specifically for your CPU. Slow but bulletproof.

##### 3.1 Install Build Tools

You need:

- **Visual Studio Build Tools 2022/2026** with the "Desktop development with C++" workload. Download from https://visualstudio.microsoft.com/visual-cpp-build-tools/.
  - In the installer, check "Desktop development with C++"
  - Make sure these components are selected:
    - MSVC v143+ C++ x64/x86 build tools
    - Windows 10/11 SDK
    - C++ CMake tools for Windows

- **CMake** (if not bundled with VS):
  ```cmd
  pip install cmake
  ```

##### 3.2 Enable Windows Long Path Support

The llama.cpp source has deeply nested directories that exceed Windows' 260-character path limit. You'll get errors like:

```
FileNotFoundError: ... \vendor\llama.cpp\tools\server\webui\src\lib\components\app\chat\ChatAttachments\...\ChatAttachmentsListItem.svelte
```

**Fix (one-time, requires admin):**

Open **PowerShell as Administrator**:
- Press `Windows key`, type `PowerShell`
- Right-click **Windows PowerShell** → **Run as administrator**
- Click "Yes" on the UAC prompt

Then run:

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

A successful run prints `LongPathsEnabled : 1` along with registry path info.

**Reboot your machine.** This is required — the registry value is read once at boot by some Windows components, and pip/Python need a fresh process tree to pick it up reliably. Sign-out/sign-in is not enough in all cases.

##### 3.3 Open the Right Terminal

You **must** use the x64 build environment, not regular `cmd` or PowerShell.

**Option A — Use the x64 Native Tools shortcut:**

Start menu → search for "x64 Native Tools Command Prompt for VS 2022" (or 2026) → open it.

**Option B — Activate manually in any cmd window:**

```cmd
"C:\Program Files (x86)\Microsoft Visual Studio\<VERSION>\BuildTools\VC\Auxiliary\Build\vcvars64.bat"
```

Replace `<VERSION>` with whatever folder name VS installed under. This is **not** the marketing year — it's the internal version or year folder, and it varies between installs:

| Marketing name      | Folder name you'll likely see |
|---------------------|-------------------------------|
| VS 2019             | `2019` or `16`                |
| VS 2022             | `2022` or `17`                |
| VS 2026             | `2026` or `18`                |

To find the exact path on your machine:

```cmd
dir "C:\Program Files (x86)\Microsoft Visual Studio"
```

Look for the folder containing `BuildTools` (or `Community`, `Professional`, `Enterprise` if you installed full VS). Then drill in to find `vcvars64.bat`. For example, on the machine this guide was written from, it's:

```
C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvars64.bat
```

**Verify the toolchain:**

```cmd
echo %VSCMD_ARG_TGT_ARCH%
cl
cmake --version
python --version
```

Expected:
- `VSCMD_ARG_TGT_ARCH` → `x64` (NOT `x86`)
- `cl` → `Microsoft (R) C/C++ Optimizing Compiler ... for x64`
- `cmake --version` → `cmake version 3.x` or later
- `python --version` → `Python 3.10/3.11/3.12`

**If `VSCMD_ARG_TGT_ARCH` shows `x86`**: you opened the wrong prompt. Close it and open the **x64 Native Tools** one specifically.

##### 3.4 Set Short Temp Directory (Helps Avoid Path Issues)

Even with long paths enabled, using a short TMP keeps things safer:

```cmd
mkdir C:\tmp
set TMP=C:\tmp
set TEMP=C:\tmp
```

##### 3.5 Set CPU-Specific CMake Flags

Tailor these to your CPU. If you have AVX2 but no AVX-512 (the most common problem case):

```cmd
set CMAKE_ARGS=-DGGML_AVX512=OFF -DGGML_AVX512_VBMI=OFF -DGGML_AVX512_VNNI=OFF -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON
```

**Other configurations:**

| CPU capability                | CMAKE_ARGS                                                                                     |
|-------------------------------|------------------------------------------------------------------------------------------------|
| AVX2 + FMA + F16C (typical)   | `-DGGML_AVX512=OFF -DGGML_AVX2=ON -DGGML_FMA=ON -DGGML_F16C=ON`                                |
| AVX2 only (older CPUs)        | `-DGGML_AVX512=OFF -DGGML_AVX2=ON -DGGML_FMA=OFF -DGGML_F16C=OFF`                              |
| AVX only (very old CPUs)      | `-DGGML_AVX512=OFF -DGGML_AVX2=OFF -DGGML_AVX=ON -DGGML_FMA=OFF -DGGML_F16C=OFF`               |
| Has AVX-512                   | Default — no flags needed                                                                      |

##### 3.6 Verify All Variables Are Set

```cmd
echo TMP=%TMP%
echo TEMP=%TEMP%
echo CMAKE_ARGS=%CMAKE_ARGS%
```

All three should show your values. If `CMAKE_ARGS` is empty, re-run the `set` command.

##### 3.7 Build

```cmd
pip uninstall llama-cpp-python -y
pip install llama-cpp-python --no-cache-dir --no-binary :all: --verbose
```

Expect 5-15 minutes. You'll see CMake configure first, then a long stream of `cl.exe` compiling C++ files. **Don't close the window or open a new one mid-build** — environment variables only persist in the current shell.

**What "normal progress" looks like:**

- First minute: pip downloads the 68 MB tarball, extracts it, runs `cmake` configuration (lots of `-- Found ...` lines).
- Next 5-12 minutes: continuous `cl.exe` output compiling individual `.cpp` files. Long pauses (30+ seconds) between files are normal — the compiler is working.
- Final minute: linking + wheel packaging.

**If progress seems stuck:**

- Check Task Manager. If `cl.exe` is using CPU, the build is fine — just slow.
- If nothing is using CPU and pip is silent for 5+ minutes, the build may be hung. Press `Ctrl+C` and retry.

##### 3.8 Test

```cmd
python test_llm.py
```

If you see `OK - model loaded successfully`, the build works on your hardware.

##### 3.9 Run Your Application

Once the test passes, you can run the actual server (or whatever app uses llama-cpp-python). For this project:

```cmd
cd "<path-to>\Web_local_llm"
python server.py
```

The `/api/load-model` endpoint should now succeed instead of returning a 500 error.

#### Common Errors and Fixes

##### Error: `0xc000001d` / `STATUS_ILLEGAL_INSTRUCTION`

**Cause:** The binary uses CPU instructions your machine doesn't support (typically AVX-512 on a CPU/VM that lacks it).

**Fix:** Build from source with explicit flags (Method 3).

##### Error: `'LlamaModel' object has no attribute 'sampler'`

**Cause:** This is a **secondary** error during cleanup — it appears *after* a primary load failure. Fix the primary failure (usually `0xc000001d` above) and this disappears too.

##### Error: `FileNotFoundError: [Errno 2] ... .svelte`

**Cause:** Source paths exceed Windows' 260-character limit during tarball extraction.

**Fix:** Enable Long Path support in the registry (Section 3.2) and reboot.

##### Error: `cl: command not found` or build fails immediately

**Cause:** You're in regular `cmd`/PowerShell instead of the VS Developer environment, or you're in the x86 prompt instead of x64.

**Fix:** Use the x64 Native Tools Command Prompt, or run `vcvars64.bat`. Verify with `echo %VSCMD_ARG_TGT_ARCH%` (must say `x64`).

##### Error: `LINK : fatal error LNK1112: module machine type 'x86' conflicts with target machine type 'x64'`

**Cause:** Mixing 32-bit and 64-bit toolchains. Same root cause as above.

**Fix:** Make sure you ran `vcvars64.bat` (not `vcvars32.bat`). Confirm `cl` reports "for x64".

##### Error: Build can't find Python.h

**Cause:** Python development headers missing or Python isn't on PATH inside the VS prompt.

**Fix:** Make sure `python --version` works in the same shell. If you installed Python via the Microsoft Store, it may not expose headers — install from python.org instead.

##### Error: `ninja not found`

**Fix:** `pip install ninja`

#### Using a Virtual Environment

Recommended to keep dependencies isolated. Inside your project folder:

```cmd
python -m venv .venv
.venv\Scripts\activate
```

Your prompt will change to show `(.venv)` at the start, confirming activation. Then run any of the install methods above inside the activated venv. The build will install into `.venv\Lib\site-packages\` instead of system Python.

**Important — order of operations for a source build inside a venv:**

1. Open the VS x64 Developer prompt (or run `vcvars64.bat`).
2. Activate the venv: `.venv\Scripts\activate`
3. Set environment variables: `set CMAKE_ARGS=...`, `set TMP=C:\tmp`, etc.
4. Run `pip install ...`

If you set the env vars *before* activating the venv, they're still inherited (since `activate.bat` doesn't clear them) — but it's cleaner to activate first. What you must NOT do is open a fresh shell between any of these steps; `set` does not persist.

**Deactivating later:**

```cmd
deactivate
```

#### Multiple Python Versions

If a wheel is only available for a specific Python version (e.g., `cp311` only):

1. Install the additional Python version from python.org alongside your existing one.
2. Use the Python launcher to create a venv pinned to that version:
   ```cmd
   py -3.11 -m venv .venv
   ```
3. Activate and proceed.

The `py-3.x` launcher is bundled with the python.org installer and lets you target any installed version explicitly.

#### Verifying CPU Build (Optional)

After installation, check what's actually compiled in:

```cmd
python -c "import llama_cpp; print(llama_cpp.llama_print_system_info().decode())"
```

Look at the output line for `AVX = 1 | AVX2 = 1 | AVX512 = 0 | FMA = 1 | F16C = 1 | ...`. The flags should match what you set with `CMAKE_ARGS`.

#### When All Else Fails

If even the source build crashes:

1. Check whether you're in a virtualized environment that masks CPU features:
   ```cmd
   python -c "import cpuinfo; print(cpuinfo.get_cpu_info().get('hypervisor_vendor', 'bare metal'))"
   ```
   If a hypervisor name appears, the VM may be exposing inconsistent CPU flags.

2. Try the most conservative build:
   ```cmd
   set CMAKE_ARGS=-DGGML_AVX512=OFF -DGGML_AVX2=OFF -DGGML_AVX=OFF -DGGML_FMA=OFF -DGGML_F16C=OFF
   pip install llama-cpp-python --no-cache-dir --no-binary :all:
   ```
   This is slow at runtime but maximally compatible.

3. Use a community-built wheel (e.g., from `dougeeai/llama-cpp-python-wheels` on GitHub) targeting your specific CPU profile.

---

### GPU Build (NVIDIA CUDA)

Everything in the CPU Build section above (Method 3) applies **identically**, with two changes:

#### Extra Prerequisite

- Install **CUDA Toolkit 12.x** from https://developer.nvidia.com/cuda-downloads (~3 GB).
- After installation, verify in your VS x64 prompt:
  ```cmd
  nvcc --version
  ```
  Should print `Cuda compilation tools, release 12.x`.

#### Changed Step — CMAKE_ARGS

Instead of the AVX/CPU flags in Section 3.5, set:

```cmd
set CMAKE_ARGS=-DGGML_CUDA=ON
```

Everything else stays the same — VS x64 prompt, long paths, short TMP, the pip install command:

```cmd
pip uninstall llama-cpp-python -y
pip install llama-cpp-python --no-cache-dir --no-binary :all: --verbose
```

#### In Your Python Code

```python
m = Llama(
    model_path=r"C:\ml_models\YOUR-MODEL.gguf",
    n_ctx=4096,
    n_gpu_layers=35,  # offload layers to GPU (use -1 for all)
)
```

| VRAM | Approximate layers for 8B Q4_K_M |
|------|----------------------------------|
| 8 GB | ~33 (full offload)               |
| 4 GB | ~15-20 (partial, rest on CPU)    |

**Performance:** Expect 5-15x faster token generation vs CPU-only.

> **Note:** The old flag `-DLLAMA_CUBLAS=ON` you may see in older guides is deprecated. Use `-DGGML_CUDA=ON`.

---

## Linux

### CPU Build

```bash
# Install build tools (one-time)
sudo apt install build-essential cmake    # Ubuntu/Debian
# or: sudo dnf install gcc-c++ cmake     # Fedora/RHEL

# Install
pip install llama-cpp-python
```

That's it. No special prompts, no long path hacks, no AVX issues (the prebuilt wheels are conservative, and source builds auto-detect your CPU).

If you hit issues, force a source build:

```bash
pip install llama-cpp-python --no-cache-dir --no-binary :all:
```

#### Using a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate

# Then install as above
pip install llama-cpp-python
```

---

### GPU Build (NVIDIA CUDA)

```bash
# 1. Install CUDA Toolkit (one-time)
sudo apt install nvidia-cuda-toolkit      # Ubuntu/Debian
# or download from https://developer.nvidia.com/cuda-downloads

# 2. Verify
nvcc --version

# 3. Install build tools if not already present
sudo apt install build-essential cmake

# 4. Install with CUDA
CMAKE_ARGS="-DGGML_CUDA=ON" pip install llama-cpp-python --no-cache-dir --no-binary :all:
```

Use `n_gpu_layers=-1` in Python to offload everything to GPU.

#### Using a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate

CMAKE_ARGS="-DGGML_CUDA=ON" pip install llama-cpp-python --no-cache-dir --no-binary :all:
```

---

## macOS

### CPU Build

```bash
# Install Xcode command line tools (one-time)
xcode-select --install

# Install
pip install llama-cpp-python
```

Works on both Intel Macs and Apple Silicon (M1/M2/M3/M4).

#### Using a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install llama-cpp-python
```

---

### GPU Build (Metal)

On Apple Silicon, **Metal GPU acceleration is enabled by default**. There's nothing extra to do:

```bash
pip install llama-cpp-python
```

This already compiles with `-DGGML_METAL=ON`. Use `n_gpu_layers=-1` in Python to offload to the Apple GPU.

If you want to be explicit (not required):

```bash
CMAKE_ARGS="-DGGML_METAL=ON" pip install llama-cpp-python
```

> **Note:** Intel Macs don't have Metal compute support for ML workloads — they run CPU-only.

#### Using a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install llama-cpp-python
# Metal is already enabled by default on Apple Silicon
```

---

## Reference

- **Project:** https://github.com/abetlen/llama-cpp-python
- **Releases (prebuilt wheels):** https://github.com/abetlen/llama-cpp-python/releases
- **CMake build options:** https://github.com/ggml-org/llama.cpp/blob/master/docs/build.md
- **CUDA Toolkit download:** https://developer.nvidia.com/cuda-downloads
- **Why `0xc000001d` happens:** AVX/AVX-512 instructions executed on a CPU that doesn't decode them generate `EXCEPTION_ILLEGAL_INSTRUCTION` (NTSTATUS `0xC000001D`).
