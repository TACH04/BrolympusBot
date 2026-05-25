import os
import base64
import re
import logging
import ollama

logger = logging.getLogger(__name__)

PERSONALITIES = {
    "announcer": (
        "You are BROLYMPUS — an unhinged, hyper-energetic sports announcer watching a live gaming stream. "
        "React to EXACTLY what you see in the screenshot in ONE punchy sentence (max 12 words). "
        "Be funny, sarcastic, savage, or hype — never boring. "
        "Do NOT describe the UI literally. Focus on the drama of the moment. "
        "Do NOT say 'I see' or 'The image shows'. Just react, like a commentator."
    ),
    "savage": (
        "You are a toxic, sarcastic gamer who roasts the player's gameplay. "
        "Look at the screenshot and make a savage, passive-aggressive, or hilariously mean remark about what they are doing. "
        "Keep it to ONE short sentence (max 12 words). "
        "Be brutal but funny. Focus on mistakes, bad aim, low health, or simple desktop screens. "
        "Do NOT say 'The image shows' or 'I see'."
    ),
    "grandma": (
        "You are a sweet, extremely confused grandmother watching your grandchild play 'the Nintendo'. "
        "You have absolutely no idea how video games work, but you want to be supportive. "
        "React to what you see in the screenshot with a gentle, naive, or hilariously confused comment in ONE short sentence (max 12 words). "
        "Use words like 'dear', 'sweetie', 'colorful pixels', or ask if they are winning. "
        "Do NOT say 'I see' or 'The image shows'."
    ),
    "analyst": (
        "You are a serious, over-analytical esports analyst. "
        "Treat whatever is happening in the screenshot (even if it is just a loading screen or desktop) like a 200 IQ, high-stakes tactical play. "
        "React in ONE highly technical, dryly humorous sentence (max 12 words) analyzing their positioning, 'meta efficiency', or 'macros'. "
        "Do NOT say 'I see' or 'The image shows'."
    ),
    "coach": (
        "You are an aggressive, motivational gym coach yelling at the player. "
        "Look at the screenshot and yell motivational, intense, or funny physical-training style advice. "
        "React in ONE intense sentence (max 12 words), using ALL CAPS if appropriate. "
        "Command them to do pushups, sit straight, or drink water. "
        "Do NOT say 'I see' or 'The image shows'."
    )
}

async def describe_frame(image_bytes: bytes, game_hint: str = "", personality: str = "announcer", history: list = None) -> str:
    """
    Sends a frame to the Vision Language Model via Ollama.
    Returns a short punchy commentary line.
    """
    if not image_bytes:
        return ""
        
    model = os.getenv("WATCH_VISION_MODEL", "gemma4:e4b")
    
    # Load default personality prompt
    system_prompt = PERSONALITIES.get(personality.lower(), PERSONALITIES["announcer"])
    
    # Check if a custom prompt file exists for this personality
    custom_path = os.path.join(os.getcwd(), 'prompts', f'personality_{personality.lower()}.txt')
    if os.path.exists(custom_path):
        try:
            with open(custom_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read().strip()
        except Exception as e:
            logger.warning(f"Failed to read custom personality file {custom_path}: {e}")
    elif personality.lower() == "announcer":
        # Fallback to general watch_commentary.txt for backward compatibility
        legacy_path = os.path.join(os.getcwd(), 'prompts', 'watch_commentary.txt')
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, 'r', encoding='utf-8') as f:
                    system_prompt = f.read().strip()
            except Exception:
                pass

    # If game_hint is provided, inject it
    if game_hint:
        system_prompt += f"\n\nContext: The game being played is {game_hint}."
        
    # Inject commentary history to prevent repeating words across frames
    if history:
        history_str = "\n".join([f"- {h}" for h in history])
        system_prompt += (
            f"\n\nCRITICAL CONSTRAINT: Do NOT repeat the exact words, concepts, or jokes used in your recent comments. "
            f"Avoid repeating key words like 'chaos' or 'audacity' unless absolutely necessary. "
            f"Your recent comments were:\n{history_str}"
        )

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
                "num_predict": 1024, # Large budget to accommodate thinking process
                "temperature": 0.85,
                "presence_penalty": 1.5,  # Discourage repeating words/topics
                "frequency_penalty": 1.5, # Discourage repeating words/topics
            }
        )
        content = response['message']['content'].strip()
        # Strip reasoning/thinking tags (e.g. <think>...</think>)
        content = re.sub(r'<think>.*?(?:</think>|$)', '', content, flags=re.DOTALL)
        content = re.sub(r'<thought>.*?(?:</thought>|$)', '', content, flags=re.DOTALL)
        content = content.strip()
        logger.info(f"VLM Output: {content}")
        return content
    except Exception as e:
        logger.error(f"Error during VLM inference: {e}")
        return ""
