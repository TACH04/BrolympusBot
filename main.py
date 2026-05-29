import argparse
import sys
import os
import logging

# Add src to python path if not already there
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.logging_config import setup_logging

def start_bot(start_sd: bool = True):
    from bot.discord_bot import bot
    from integrations.stable_diffusion import start_stable_diffusion_server, stop_stable_diffusion_server
    
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables.")
        sys.exit(1)
        
    # Start Stable Diffusion server if configured
    sd_process = start_stable_diffusion_server(start_sd=start_sd)
    
    try:
        print("Starting Discord bot...")
        bot.run(DISCORD_TOKEN, log_handler=None)
    finally:
        # Guarantee server shutdown even if bot crashes or is interrupted
        if sd_process:
            stop_stable_diffusion_server(sd_process)

def main():
    parser = argparse.ArgumentParser(description="CalGuy Application Entry Point")
    parser.add_argument("--no-image", action="store_true", help="Do not start the Stable Diffusion image generation server")
    
    args = parser.parse_args()
    setup_logging()
    
    start_bot(start_sd=not args.no_image)

if __name__ == "__main__":
    main()
