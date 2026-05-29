import argparse
import sys
import os
import logging

# Add src to python path if not already there
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from core.logging_config import setup_logging

def setup_logging_entry(mode):
    setup_logging(mode)

def start_web():
    from web.app import app
    PORT = int(os.getenv("PORT", 5001))
    print(f"Starting CalGuy Web UI on http://localhost:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)

def start_bot():
    from bot.discord_bot import bot
    from integrations.stable_diffusion import start_stable_diffusion_server, stop_stable_diffusion_server
    
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        print("Error: DISCORD_TOKEN not found in environment variables.")
        sys.exit(1)
        
    # Start Stable Diffusion server if configured
    sd_process = start_stable_diffusion_server()
    
    try:
        print("Starting Discord bot...")
        bot.run(DISCORD_TOKEN)
    finally:
        # Guarantee server shutdown even if bot crashes or is interrupted
        if sd_process:
            stop_stable_diffusion_server(sd_process)

def main():
    parser = argparse.ArgumentParser(description="CalGuy Application Entry Point")
    parser.add_argument("mode", choices=["web", "bot"], help="Which part of the application to start")
    
    args = parser.parse_args()
    setup_logging_entry(args.mode)
    
    if args.mode == "web":
        start_web()
    elif args.mode == "bot":
        start_bot()

if __name__ == "__main__":
    main()
