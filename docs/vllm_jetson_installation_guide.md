# NVIDIA Jetson Orin: vLLM Installation & Configuration Guide

This guide describes how to install and run **vLLM** on the **NVIDIA Jetson Orin (64GB)** platform. It uses the official, highly-optimized Docker container maintained by NVIDIA specifically for JetPack 6.x and ARM64/Ampere architecture.

Building vLLM from source on ARM64 is extremely resource-intensive and error-prone due to custom Triton, PyTorch, and xformers requirements. **Running via the container is the officially recommended path.**

---

## Prerequisites

Before setting up vLLM, ensure your Jetson Orin meets the following requirements:

1. **JetPack Version**: **JetPack 6.x** (typically comes with CUDA 12.2+ and Ubuntu 22.04 LTS).
2. **NVIDIA Container Toolkit**: Must be installed and configured. Test that Docker can access the GPU:
   ```bash
   docker run --runtime nvidia --rm nvcr.io/nvidia/k8s-device-plugin:v0.14.0 nvidia-smi
   ```
   If you see the GPU details (Jetson AGX Orin / Ampere), the runtime is configured properly.
3. **Hugging Face Account & Token**: The Gemma model family requires accepting their license terms. Create a token in your Hugging Face account settings (Read access is sufficient) to allow vLLM to download the model weights.

---

## Installation & Setup Steps

### Step 1: Clean Up Existing Ollama Service
To avoid port conflicts and free up unified memory:
```bash
# If Ollama is running as a standard system service
sudo systemctl stop ollama
sudo systemctl disable ollama

# If Ollama is running as a docker service (e.g. ollama-docker)
sudo systemctl stop ollama-docker
sudo systemctl disable ollama-docker
```

---

### Step 2: Set Up Hugging Face Credentials
Make sure your Hugging Face token is saved so the Docker container can access it to authenticate Gemma model downloads.

Create or update the Hugging Face configuration on your system:
```bash
mkdir -p ~/.cache/huggingface
# Save your token
echo "your_huggingface_token_here" > ~/.cache/huggingface/token
```
*(Replace `your_huggingface_token_here` with your actual Hugging Face token. This file is read by the Hugging Face library inside the container).*

---

### Step 3: Create the systemd Service File
Creating a systemd service allows vLLM to run reliably in the background, automatically restart if it crashes, start on system boot, and integrate with the bot's automated memory management helper.

Save the following content to `/etc/systemd/system/vllm-docker.service` (e.g., run `sudo nano /etc/systemd/system/vllm-docker.service`):

```ini
[Unit]
Description=vLLM OpenAI-Compatible API Server Container
After=docker.service
Requires=docker.service

[Service]
TimeoutStartSec=0
Restart=always
# Make sure any older stale containers are cleaned up before starting
ExecStartPre=-/usr/bin/docker stop vllm-server
ExecStartPre=-/usr/bin/docker rm vllm-server
# Launch the container
ExecStart=/usr/bin/docker run --name vllm-server \
  --runtime nvidia \
  --network host \
  --shm-size=8g \
  -v /home/iamfyi2025/.cache/huggingface:/root/.cache/huggingface \
  -e HF_TOKEN_PATH=/root/.cache/huggingface/token \
  ghcr.io/nvidia-ai-iot/vllm:latest-jetson-orin \
  python3 -m vllm.entrypoints.openai.api_server \
  --model huihui-ai/Huihui-gemma-4-E4B-it-abliterated \
  --port 8000 \
  --gpu-memory-utilization 0.45 \
  --max-model-len 8192 \
  --trust-remote-code
ExecStop=/usr/bin/docker stop vllm-server

[Install]
WantedBy=multi-user.target
```

---

### Step 4: Register and Start the Service
Activate the newly created systemd service:

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable the service to start automatically on boot
sudo systemctl enable vllm-docker

# Start the service right now
sudo systemctl start vllm-docker
```

---

### Step 5: Monitor Startup & Download Logs
vLLM will automatically download the model weights from Hugging Face on its first run. Because this model is ~8GB, the download may take a few minutes depending on your internet connection.

Track the progress and startup status:
```bash
# View active container output
docker logs -f vllm-server
```
Look for the following log output to confirm it has successfully initialized:
```text
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

---

### Step 6: Verify Endpoint Connectivity
Once the server is running, you can test it directly from the Jetson terminal using curl:

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "huihui-ai/Huihui-gemma-4-E4B-it-abliterated",
    "messages": [
      {"role": "user", "content": "Explain memory bandwidth in one sentence."}
    ],
    "max_tokens": 50
  }'
```

You should receive a JSON response containing the generated text choice in the standard OpenAI completions format.
