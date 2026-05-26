import os
import base64
import re
import logging
import ollama

import json

logger = logging.getLogger(__name__)

def load_watch_personalities() -> dict:
    """Loads all watch personalities from prompts/watch_personalities.json."""
    personalities_path = os.path.join(os.getcwd(), 'prompts', 'watch_personalities.json')
    if os.path.exists(personalities_path):
        try:
            with open(personalities_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load personalities from {personalities_path}: {e}")
    else:
        logger.error(f"Personalities file not found: {personalities_path}")
    return {}

def extract_banned_words(history: list) -> str:
    if not history:
        return ""
    
    stopwords = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with", "by", 
        "of", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", 
        "do", "does", "did", "i", "you", "he", "she", "it", "we", "they", "me", "him", 
        "her", "us", "them", "my", "your", "his", "their", "this", "that", "these", 
        "those", "what", "which", "who", "whom", "this", "that", "bro", "player", "gaming", 
        "screenshot", "right", "now", "just", "is", "about", "like", "of", "in", "on", "to"
    }
    
    words = set()
    for sentence in history:
        # Lowercase and extract alphanumeric words
        clean_words = re.findall(r'\b[a-z]{3,15}\b', sentence.lower())
        for w in clean_words:
            if w not in stopwords:
                words.add(w)
                
    if not words:
        return ""
    return ", ".join(sorted(words))

async def describe_frame(
    image_bytes: bytes, 
    game_hint: str = "", 
    personality: str = "announcer", 
    history: list = None,
    active_window: str = ""
) -> str:
    """
    Sends a frame to the Vision Language Model via Ollama.
    Returns a short punchy commentary line.
    """
    if not image_bytes:
        return ""
        
    model = os.getenv("WATCH_VISION_MODEL", "gemma4:e4b")
    
    # Load personality prompts from the dedicated JSON file
    personalities = load_watch_personalities()
    pers_data = personalities.get(personality.lower())
    if not pers_data:
        # Fallback to announcer
        pers_data = personalities.get("announcer", {})
        
    system_prompt = pers_data.get("system_prompt", "")
    examples = pers_data.get("examples", [])
    
    # Check if a custom prompt file exists for this personality (overrides default JSON)
    custom_path = os.path.join(os.getcwd(), 'prompts', f'personality_{personality.lower()}.txt')
    if os.path.exists(custom_path):
        try:
            with open(custom_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read().strip()
                examples = [] # Clear examples if custom overridden
        except Exception as e:
            logger.warning(f"Failed to read custom personality file {custom_path}: {e}")
            
    # Format and append examples
    if examples:
        system_prompt += "\n\nExamples of your style and length constraint (max 12 words):\n"
        for ex in examples:
            system_prompt += f"- \"{ex}\"\n"
            
    # Inject context
    context_parts = []
    if game_hint:
        context_parts.append(f"The game being played is believed to be: {game_hint}.")
    if active_window:
        context_parts.append(f"The user's active OS window title is: \"{active_window}\".")
        
    if context_parts:
        system_prompt += "\n\nContext:\n" + "\n".join([f"- {part}" for part in context_parts])
        
    # Inject commentary history and soft constraints to prevent repeating words across frames
    if history:
        history_str = "\n".join([f"- {h}" for h in history])
        banned_words = extract_banned_words(history)
        system_prompt += (
            f"\n\nYour recent comments were:\n{history_str}"
        )
        if banned_words:
            system_prompt += (
                f"\n\nTo ensure variety, please avoid repeating key terms or concepts from those recent comments. "
                f"Specifically, try not to use these words in your response: {banned_words}."
            )
 
    client = ollama.AsyncClient()
    
    # Base64 encode the image
    b64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    # Structure messages utilizing separate system and user roles
    messages = [
        {
            'role': 'system',
            'content': system_prompt
        },
        {
            'role': 'user',
            'content': "Describe this screenshot in your personality's voice.",
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
                "repeat_penalty": 1.5,     # Heavily penalize repeating tokens (Ollama standard)
                "repeat_last_n": 128,      # Look back 128 tokens for repetitions
                "presence_penalty": 1.5,   # Discourage repeating words/topics
                "frequency_penalty": 1.5,  # Discourage repeating words/topics
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
