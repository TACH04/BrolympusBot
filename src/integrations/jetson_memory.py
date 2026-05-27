import os
import subprocess
import logging

logger = logging.getLogger('integrations.jetson_memory')

# Read Jetson-specific settings from the environment
JETSON_MODE = os.getenv("JETSON_MODE", "false").lower() == "true"
JETSON_HELPER_PATH = os.getenv("JETSON_HELPER_PATH", "/usr/local/bin/jetson-bot-helper")

def _run_helper_command(action: str) -> bool:
    """
    Runs the Jetson helper script with the specified action using sudo.
    Returns True if successful, False otherwise.
    """
    if not JETSON_MODE:
        return True

    if not os.path.exists(JETSON_HELPER_PATH) and JETSON_HELPER_PATH == "/usr/local/bin/jetson-bot-helper":
        # If helper path is default and it doesn't exist, log warning
        logger.warning(
            f"Jetson Mode is enabled, but the helper script was not found at {JETSON_HELPER_PATH}. "
            "Please follow the setup instructions to create it and configure passwordless sudo."
        )
        return False

    cmd = ["sudo", JETSON_HELPER_PATH, action]
    logger.info(f"Running Jetson helper command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        if result.stdout:
            logger.info(f"Helper output: {result.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(
            f"Failed to execute Jetson helper command '{action}': {e.stderr.strip() or str(e)}. "
            "Ensure the helper script is installed at the correct path and configured in /etc/sudoers.d/"
        )
        return False
    except Exception as e:
        logger.error(f"Unexpected error running Jetson helper command: {e}")
        return False

def stop_ollama() -> bool:
    """
    Stops the ollama-docker systemd service.
    """
    logger.info("Stopping Ollama service to free shared GPU/CPU memory...")
    return _run_helper_command("stop-ollama")

def start_ollama() -> bool:
    """
    Starts the ollama-docker systemd service.
    """
    logger.info("Restarting Ollama service now that Stable Diffusion is running...")
    return _run_helper_command("start-ollama")

def compact_memory() -> bool:
    """
    Tells the kernel to drop caches and compact memory to maximize contiguous free pages.
    """
    logger.info("Requesting kernel memory compaction to defragment shared memory...")
    return _run_helper_command("compact")
