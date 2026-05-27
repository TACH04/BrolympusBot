# Jetson Orin Setup & Troubleshooting Guide

This guide documents the specific configurations, dependencies, and workarounds required to run **Stable Diffusion WebUI** and **Ollama** concurrently on the NVIDIA Jetson Orin (64GB shared memory) platform under JetPack 6.x / CUDA 12.6.

---

## 1. The Unified Memory Challenge

Jetson devices use **Unified Memory** (shared CPU/GPU RAM). Unlike desktop systems, there is no physical VRAM partition. 
* **Fragmentation:** If multiple large models (like Ollama's LLM and Stable Diffusion) are loaded, pinned memory pages block the GPU driver from allocating the massive contiguous blocks of RAM needed for model weights.
* **Launch Order Solution:** To avoid fragmentation, the bot handles model startup sequencing automatically (when `JETSON_MODE=true` is enabled in `.env`):
  1. Stops the Ollama service to free up shared RAM.
  2. Compacts memory using the Linux kernel compactor.
  3. Launches Stable Diffusion so it secures its contiguous allocation first.
  4. Restarts Ollama once SD is confirmed ready.

---

## 2. Virtual Environment Setup (Python 3.10)

Standard `pip` installations will pull down x86 compiled wheels or packages built for different CUDA configurations. You must construct your environment as follows:

```bash
# 1. Create a clean virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install the correct Jetson-specific PyTorch (JP 6.x / CUDA 12.6)
pip install torch torchvision --index-url=https://pypi.jetson-ai-lab.io/jp6/cu126

# 3. Install cuDSS (Required for PyTorch 2.11+ on JetPack 6)
pip install nvidia-cudss-cu12
```

> [!WARNING]
> **Do not** install standard `nvidia-cublas-cu12`, `nvidia-cuda-nvrtc-cu12`, or `cuda-toolkit` packages via pip. These will override the highly-optimized native JetPack libraries on your Jetson and fail with errors like `CUBLAS_STATUS_ALLOC_FAILED`.

---

## 3. Environment Path Variables

The bot and the Stable Diffusion subprocess need to know where the CUDA toolkit and the pip-installed `cudss` libraries live. 

Ensure the following variables are loaded in your terminal/directory environment (e.g., in `~/Documents/BrolympusBot/.envrc`):

```bash
# Set path to the CUDA compiler and runtime
export PATH="/usr/local/cuda-12.6/bin:$PATH"

# Set path to CUDA libraries AND the pip nvidia site-packages directory
export LD_LIBRARY_PATH="/usr/local/cuda-12.6/lib64:/usr/local/cuda-12.6/targets/aarch64-linux/lib:/usr/local/cuda-12.6/extras/CUPTI/lib64:/home/iamfyi2025/Documents/stable-diffusion-webui/.venv/lib/python3.10/site-packages/nvidia/cu12/lib:$LD_LIBRARY_PATH"
```

If you are using `direnv`, run `direnv allow` after updating your `.envrc`.

---

## 4. Jetson Bot Helper Script

To allow the bot to compact memory and control the `ollama-docker` systemd service without requiring password prompts, we use a whitelisted helper script.

### Step 1: Create the helper script
Save the following as `/usr/local/bin/jetson-bot-helper`:

```bash
#!/bin/bash
case "$1" in
  stop-ollama)
    systemctl stop ollama-docker
    ;;
  start-ollama)
    systemctl start ollama-docker
    ;;
  compact)
    sync
    echo 3 > /proc/sys/vm/drop_caches
    echo 1 > /proc/sys/vm/compact_memory
    ;;
  *)
    echo "Usage: $0 {stop-ollama|start-ollama|compact}"
    exit 1
    ;;
esac
```

Make it executable:
```bash
sudo chmod 755 /usr/local/bin/jetson-bot-helper
```

### Step 2: Configure Passwordless Sudo
Create the file `/etc/sudoers.d/jetson-bot-helper`:
```bash
sudo visudo -f /etc/sudoers.d/jetson-bot-helper
```
Add the following line to authorize your bot user:
```text
iamfyi2025 ALL=(root) NOPASSWD: /usr/local/bin/jetson-bot-helper
```

---

## 5. Stable Diffusion Launch Settings

Configure the Stable Diffusion start command in the bot's `.env` to execute the Python launcher directly inside the healthy virtual environment, bypassing the buggy `webui.sh` wrapper:

```env
JETSON_MODE=true
JETSON_HELPER_PATH=/usr/local/bin/jetson-bot-helper

START_STABLE_DIFFUSION_SERVER=true
STABLE_DIFFUSION_START_COMMAND=/home/iamfyi2025/Documents/stable-diffusion-webui/.venv/bin/python3 /home/iamfyi2025/Documents/stable-diffusion-webui/launch.py --api --listen --skip-torch-cuda-test
STABLE_DIFFUSION_WORKING_DIR=/home/iamfyi2025/Documents/stable-diffusion-webui
```
