import os
import base64
import logging
import ollama

logger = logging.getLogger(__name__)

async def describe_frame(image_bytes: bytes, game_hint: str = "") -> str:
    """
    Sends a frame to the Vision Language Model via Ollama.
    Returns a short punchy commentary line.
    """
    if not image_bytes:
        return ""
        
    model = os.getenv("WATCH_VISION_MODEL", "gemma4:e4b")
    
    # Optional image token tuning (specifically for Gemma models)
    image_tokens = os.getenv("WATCH_IMAGE_TOKENS", "140")
    
    # Read the prompt
    prompt_path = os.path.join(os.getcwd(), 'prompts', 'watch_commentary.txt')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read().strip()
    except FileNotFoundError:
        logger.warning(f"Prompt file not found at {prompt_path}, using default.")
        system_prompt = "React to this game screenshot with a short, funny, 12-word max commentary line."

    # If game_hint is provided, inject it
    if game_hint:
        system_prompt += f"\n\nContext: The game being played is {game_hint}."

    client = ollama.AsyncClient()
    
    # Base64 encode the image
    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    messages = [
        {
            'role': 'user',
            'content': f"{system_prompt}\n\nWhat is happening in this screenshot right now?!",
            'images': [b64_image]
        }
    ]
    
    try:
        logger.debug(f"Sending frame to VLM model {model}...")
        response = await client.chat(
            model=model,
            messages=messages,
            options={
                "num_predict": 150, # Sufficient headroom if model has thinking phase
                "temperature": 0.8,
            }
        )
        content = response['message']['content'].strip()
        logger.info(f"VLM Output: {content}")
        return content
    except Exception as e:
        logger.error(f"Error during VLM inference: {e}")
        return ""
