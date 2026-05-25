#!/bin/bash
set -e

echo "======================================"
echo " BrolympusBot !watch Setup (Jetson Orin)"
echo "======================================"

# 1. Install system dependencies
echo "[1/4] Installing system dependencies (ffmpeg, libsodium-dev)..."
sudo apt update
sudo apt install -y ffmpeg libsodium-dev wget tar jq

# 2. Setup bin directory
mkdir -p ./bin
mkdir -p ./bin/piper

# 3. Download MediaMTX (ARM64)
if [ ! -f "./bin/mediamtx" ]; then
    echo "[2/4] Downloading MediaMTX..."
    MEDIAMTX_VERSION="v1.9.3"
    wget -qO /tmp/mediamtx.tar.gz "https://github.com/bluenviron/mediamtx/releases/download/${MEDIAMTX_VERSION}/mediamtx_${MEDIAMTX_VERSION}_linux_arm64.tar.gz"
    tar -xzf /tmp/mediamtx.tar.gz -C /tmp mediamtx
    mv /tmp/mediamtx ./bin/mediamtx
    chmod +x ./bin/mediamtx
    rm /tmp/mediamtx.tar.gz
    echo "MediaMTX installed to ./bin/mediamtx"
else
    echo "[2/4] MediaMTX already installed."
fi

# 4. Download Piper (ARM64) and voice model
if [ ! -f "./bin/piper/piper" ]; then
    echo "[3/4] Downloading Piper TTS..."
    wget -qO /tmp/piper.tar.gz "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_linux_aarch64.tar.gz"
    tar -xzf /tmp/piper.tar.gz -C ./bin
    rm /tmp/piper.tar.gz
    echo "Piper installed to ./bin/piper/piper"
else
    echo "[3/4] Piper already installed."
fi

if [ ! -f "./bin/piper/en_US-lessac-medium.onnx" ]; then
    echo "Downloading default Piper voice model (en_US-lessac-medium)..."
    wget -qO ./bin/piper/en_US-lessac-medium.onnx "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
    wget -qO ./bin/piper/en_US-lessac-medium.onnx.json "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"
fi

# 5. Install Python dependencies
echo "[4/4] Installing Python dependencies..."
# Assuming we are in a virtual environment, if not it will install to user dir or system
pip install -r requirements.txt

echo "======================================"
echo " Setup Complete!"
echo " "
echo " Next steps:"
echo " 1. Configure OBS to stream to: rtmp://<jetson-ip>/live/stream"
echo "    (Settings -> Stream -> Custom -> Server)"
echo " 2. Add the required variables to your .env file."
echo " 3. Run the bot: python main.py bot"
echo "======================================"
