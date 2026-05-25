import os
import asyncio
import tempfile
import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

class TTSProvider(ABC):
    @property
    @abstractmethod
    def sample_rate(self) -> int:
        """Returns the native sample rate of this TTS provider's audio output."""
        pass

    @abstractmethod
    async def synthesize(self, text: str) -> Path:
        """
        Synthesizes text to a WAV file.
        Returns the Path to the temporary WAV file.
        The caller is responsible for deleting the file after playing it.
        """
        pass

class PiperProvider(TTSProvider):
    @property
    def sample_rate(self) -> int:
        return 22050

    def __init__(self):
        # Default to the binary downloaded by the setup script
        self.piper_bin = os.path.join(os.getcwd(), 'bin', 'piper', 'piper')
        
        # Load config from env
        voice_model_name = os.getenv("PIPER_VOICE_MODEL", "en_US-lessac-medium")
        if not voice_model_name.endswith(".onnx"):
            voice_model_name += ".onnx"
            
        self.model_path = os.path.join(os.getcwd(), 'bin', 'piper', voice_model_name)
        
        if not os.path.exists(self.piper_bin):
            logger.warning(f"Piper binary not found at {self.piper_bin}. Did you run setup_watch.sh?")
        if not os.path.exists(self.model_path):
            logger.warning(f"Piper model not found at {self.model_path}.")

    async def synthesize(self, text: str) -> Path:
        # Create a temp file
        fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix="piper_tts_")
        os.close(fd) # Close it so piper can write to it
        
        # Build the command
        cmd = [
            self.piper_bin,
            "--model", self.model_path,
            "--output_file", temp_path
        ]
        
        logger.debug(f"Running Piper: {' '.join(cmd)}")
        
        try:
            # We must pass the text via stdin
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Write text and wait for completion
            stdout, stderr = await process.communicate(input=text.encode('utf-8'))
            
            if process.returncode != 0:
                logger.error(f"Piper failed with code {process.returncode}: {stderr.decode()}")
                # Return empty wav or raise? We'll just return the path (which might be empty/invalid)
                # But it's safer to raise an exception or handle it in the caller.
                # If we raise, the caller catches and ignores/logs
                raise RuntimeError(f"Piper TTS failed: {stderr.decode()}")
                
            return Path(temp_path)
            
        except Exception as e:
            logger.error(f"Error during Piper synthesis: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise

class KokoroProvider(TTSProvider):
    @property
    def sample_rate(self) -> int:
        return 24000

    def __init__(self):
        self.voice = os.getenv("KOKORO_VOICE", "af_heart")
        self.speed = float(os.getenv("KOKORO_SPEED", "1.0"))
        
        try:
            from kokoro_onnx import Kokoro
            # Assumes the model is downloaded to standard location or provided
            # The kokoro_onnx library typically requires kokoro-v0_19.onnx and voices.json
            model_path = os.getenv("KOKORO_MODEL_PATH", "kokoro-v0_19.onnx")
            voices_path = os.getenv("KOKORO_VOICES_PATH", "voices.json")
            
            if not os.path.exists(model_path):
                logger.warning(f"Kokoro model not found at {model_path}. You need to download it.")
                
            self.kokoro = Kokoro(model_path, voices_path)
            logger.info("Kokoro initialized successfully.")
        except ImportError:
            logger.error("kokoro-onnx package is not installed. Run: pip install kokoro-onnx soundfile")
            self.kokoro = None
        except Exception as e:
            logger.error(f"Failed to initialize Kokoro: {e}")
            self.kokoro = None

    async def synthesize(self, text: str) -> Path:
        if not self.kokoro:
            raise RuntimeError("Kokoro is not properly initialized.")
            
        import soundfile as sf
        
        # Create a temp file
        fd, temp_path = tempfile.mkstemp(suffix=".wav", prefix="kokoro_tts_")
        os.close(fd)
        
        try:
            # We run this in a thread since it might be blocking CPU work
            def _generate():
                samples, sample_rate = self.kokoro.create(
                    text, voice=self.voice, speed=self.speed, lang="en-us"
                )
                sf.write(temp_path, samples, sample_rate)
                
            await asyncio.to_thread(_generate)
            return Path(temp_path)
        except Exception as e:
            logger.error(f"Error during Kokoro synthesis: {e}")
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise


def get_tts_provider() -> TTSProvider:
    """Factory function to get the configured TTS provider."""
    provider_name = os.getenv("TTS_PROVIDER", "piper").lower()
    
    if provider_name == "kokoro":
        logger.info("Using Kokoro TTS Provider")
        return KokoroProvider()
    else:
        logger.info("Using Piper TTS Provider")
        return PiperProvider()
