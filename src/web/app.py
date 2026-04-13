from flask import Flask, render_template, request, jsonify, Response
from flask_cors import CORS
from agents.agent import GeneralAgent
import json
import logging
from logging.handlers import RotatingFileHandler
import asyncio
import os
import base64

app = Flask(__name__)
CORS(app)

# Configure logging
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file = 'web_app.log'

# Set up Rotating File Handler (5 MB max size, 5 backup files)
file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(logging.INFO)

# Set up Console Handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(logging.INFO)

# Get the root logger and add handlers
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)

logger = logging.getLogger('web.app')

# Mute noisy Werkzeug logs
werkzeug_log = logging.getLogger('werkzeug')
werkzeug_log.setLevel(logging.ERROR)

logger.info("Initializing GeneralAgent in app.py...")
agent = GeneralAgent()
logger.info("GeneralAgent initialized.")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    """Handles chat messages via Server-Sent Events for live updates."""
    data = request.json
    user_input = data.get("message", "")
    image_b64_list = data.get("images", [])  # list of base64-encoded image strings

    # Decode images from base64
    image_bytes_list = []
    for b64 in image_b64_list:
        try:
            # Strip data-URL prefix if present (e.g. "data:image/png;base64,...")
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            image_bytes_list.append(base64.b64decode(b64))
        except Exception as e:
            logger.warning(f"Failed to decode image: {e}")

    if not user_input and not image_bytes_list:
        logger.warning("Empty message received at /api/chat")
        return jsonify({"error": "No message provided"}), 400

    if not user_input and image_bytes_list:
        user_input = "What do you see in this image?"

    logger.info(f"Received chat request: '{user_input}' with {len(image_bytes_list)} image(s)")

    def generate():
        # Create a new event loop to run the async generator synchronously for Flask
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        gen = agent.chat_step(user_input, images=image_bytes_list if image_bytes_list else None)

        full_response = ""

        try:
            while True:
                try:
                    event = loop.run_until_complete(gen.__anext__())

                    if event['type'] == 'tool_call':
                        logger.info(f"Agent tool call: {event['tool']} with args: {event['args']}")
                    elif event['type'] == 'message':
                        full_response = event.get('content', '')
                        logger.info(f"Agent final response: '{full_response[:100]}...' (Tokens: {event.get('tokens', 'N/A')})")
                    elif event['type'] == 'error':
                        logger.error(f"Agent error: {event['content']}")

                    yield f"data: {json.dumps(event)}\n\n"
                except StopAsyncIteration:
                    break
        except Exception as e:
            logger.exception(f"Unexpected error in stream generation: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
        finally:
            loop.close()
            logger.info("Chat stream generation completed.")

    return Response(generate(), mimetype="text/event-stream")

@app.route("/api/history", methods=["GET"])
def history():
    logger.info("History requested.")
    return jsonify(agent.get_history())

@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({
        "OLLAMA_NUM_CTX": int(os.getenv("OLLAMA_NUM_CTX", "32768")),
        "MODEL": os.getenv("OLLAMA_MODEL", "qwen3-coder:30b")
    })

@app.route("/api/reset", methods=["POST"])
def reset():
    logger.info("Context reset requested via web API.")
    agent.reset()
    return jsonify({"status": "success"})

if __name__ == "__main__":
    PORT = 5001
    logger.info(f"Starting CalGuy Web UI on http://localhost:{PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)
