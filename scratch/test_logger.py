import sys
import os
sys.path.append(os.path.abspath('src'))
from core.logging_config import setup_logging
import logging

setup_logging("web")
logger1 = logging.getLogger("bot.discord_bot")
logger2 = logging.getLogger("integrations.stable_diffusion")
logger3 = logging.getLogger("httpx")

logger1.info("Starting up discord bot...")
logger2.info("Generating image for prompt: 'A highly detailed, cinematic, and photorealistic image of a slightly chubby young woman. She is depicted in a scholarly setting...'")
logger2.info("Successfully generated image and saved to: /tmp/tmphblewcby.png")
logger1.info("Successfully uploaded generated image to Discord")
logger1.info("Deleted temporary image file: /tmp/tmphblewcby.png")
logger3.info('HTTP Request: POST http://127.0.0.1:11434/api/chat "HTTP/1.1 200 OK"')
