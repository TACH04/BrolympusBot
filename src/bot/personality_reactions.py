import os
import json
import logging
import asyncio
import re
import shutil
import discord
import ollama
from integrations.stable_diffusion import generate_local_image

logger = logging.getLogger('bot.personality_reactions')

STANDARD_EMOTIONS = ["neutral", "laughing", "smirking", "facepalm", "eyeroll", "confused", "glaring", "shocked"]

def get_current_personality() -> dict:
    personality_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'current_personality.json'))
    if os.path.exists(personality_path):
        try:
            with open(personality_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading current_personality.json: {e}")
    return {}

def get_cache_dir(personality_name: str) -> str:
    sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', personality_name.lower())
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'reaction_cache'))
    return os.path.join(base_dir, sanitized)

def map_to_standard_emotion(emotion: str) -> str:
    emotion = emotion.lower().strip()
    
    # Direct match first
    for std in STANDARD_EMOTIONS:
        if std in emotion:
            return std
            
    # Semantic mapping
    mappings = {
        "smile": "neutral",
        "happy": "laughing",
        "grin": "laughing",
        "giggle": "laughing",
        "snicker": "laughing",
        "smug": "smirking",
        "wink": "smirking",
        "annoyed": "eyeroll",
        "frustrated": "facepalm",
        "sad": "confused",
        "puzzled": "confused",
        "thinking": "confused",
        "angry": "glaring",
        "scowling": "glaring",
        "surprised": "shocked",
        "astounded": "shocked"
    }
    
    for k, v in mappings.items():
        if k in emotion:
            return v
            
    return "neutral"

async def determine_reaction_emotion(user_message: str, bot_response: str) -> str:
    prompt = (
        f"Based on the following conversation, determine a single brief facial expression/reaction "
        f"for the bot (e.g. 'laughing', 'smirking', 'facepalm', 'eyeroll', 'confused', 'glaring', 'grinning', 'shocked').\n"
        f"User said: {user_message}\n"
        f"Bot replied: {bot_response}\n\n"
        f"Output ONLY the single reaction term (1-3 words max). No preamble, explanation, or punctuation."
    )
    
    try:
        client = ollama.AsyncClient()
        response = await client.chat(
            model=os.getenv("OLLAMA_MODEL", "qwen3-coder:30b"),
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs only single reaction words/phrases."},
                {"role": "user", "content": prompt}
            ]
        )
        msg = response.get('message', {})
        if hasattr(msg, 'model_dump'):
            msg = msg.model_dump()
        content = msg.get('content', '').strip()
        # Clean any trailing punctuation or newlines
        content = content.replace(".", "").replace("!", "").strip()
        return content if content else "neutral"
    except Exception as e:
        logger.error(f"Failed to determine reaction emotion: {e}")
        return "neutral"

def clean_avatar_prompt(avatar_prompt: str) -> str:
    expressions = [
        "smiling", "smile", "happy", "neutral expression", "sad", "angry", 
        "serious expression", "laughing", "smirking", "grinning", "scowling",
        "looking neutral", "smiling warmly", "cheerful expression", "smiling brightly"
    ]
    parts = [p.strip() for p in avatar_prompt.split(',')]
    cleaned_parts = [p for p in parts if p.lower() not in expressions and not any(exp in p.lower() for exp in expressions)]
    return ", ".join(cleaned_parts)

def get_reaction_prompt(avatar_prompt: str, emotion: str) -> str:
    cleaned_base = clean_avatar_prompt(avatar_prompt)
    
    emotion_tags = {
        "neutral": "neutral expression",
        "facepalm": "facepalm, looking frustrated, hand on face",
        "eyeroll": "eyeroll, rolling eyes, looking annoyed",
        "laughing": "laughing, big open mouth smile",
        "smirking": "smirking, smug expression",
        "confused": "confused expression, head tilted, puzzled",
        "glaring": "glaring, frowning, angry expression",
        "shocked": "shocked, surprised expression, wide eyes",
    }
    
    tag = emotion_tags.get(emotion, "neutral expression")
    return f"{cleaned_base}, {tag}"

async def batch_generate_reactions(p: dict):
    name = p.get("name", "unknown")
    target_dir = get_cache_dir(name)
    base_cache_dir = os.path.dirname(target_dir)
    
    # 1. Clean up old caches
    if os.path.exists(base_cache_dir):
        for item in os.listdir(base_cache_dir):
            item_path = os.path.join(base_cache_dir, item)
            if os.path.isdir(item_path) and item_path != target_dir:
                try:
                    shutil.rmtree(item_path)
                    logger.info(f"Cleaned up old cache directory: {item_path}")
                except Exception as e:
                    logger.error(f"Failed to remove old cache {item_path}: {e}")
                    
    # Ensure our target dir exists
    os.makedirs(target_dir, exist_ok=True)
    
    base_prompt = p.get('avatar_prompt', 'portrait of a cool robot, neon accents, gym background')
    logger.info(f"Starting batch generation for personality: {name}")
    
    for emotion in STANDARD_EMOTIONS:
        file_path = os.path.join(target_dir, f"{emotion}.png")
        if os.path.exists(file_path):
            continue
            
        prompt = get_reaction_prompt(base_prompt, emotion)
        logger.info(f"Batch generating {emotion} reaction...")
        
        img_result = await generate_local_image(prompt, extra_negative_prompt="nsfw, naked, nude, suggestive, gore, text, words, logo")
        if img_result.get("status") == "success":
            img_path = img_result.get("image_path")
            if img_path and os.path.exists(img_path):
                try:
                    shutil.move(img_path, file_path)
                    logger.info(f"Saved {emotion} reaction to {file_path}")
                except Exception as e:
                    logger.error(f"Failed to move {img_path} to {file_path}: {e}")
        else:
            logger.error(f"Failed to batch generate {emotion}: {img_result.get('message')}")

async def generate_and_send_reaction_image(message: discord.Message, user_content: str, bot_response: str):
    try:
        p = get_current_personality()
        name = p.get("name", "unknown")
        
        # Determine emotion
        raw_emotion = await determine_reaction_emotion(user_content, bot_response)
        mapped_emotion = map_to_standard_emotion(raw_emotion)
        logger.info(f"Determined reaction emotion: '{raw_emotion}' -> mapped to '{mapped_emotion}'")
        
        cache_dir = get_cache_dir(name)
        target_file = os.path.join(cache_dir, f"{mapped_emotion}.png")
        neutral_file = os.path.join(cache_dir, "neutral.png")
        
        file_to_send = None
        if os.path.exists(target_file):
            file_to_send = target_file
        elif os.path.exists(neutral_file):
            logger.info(f"Mapped reaction {mapped_emotion}.png not ready, falling back to neutral.png")
            file_to_send = neutral_file
            
        if file_to_send:
            try:
                with open(file_to_send, 'rb') as f:
                    discord_file = discord.File(f, filename='reaction.png')
                    await message.reply(file=discord_file)
                logger.info("Successfully sent reaction image.")
            except Exception as e:
                logger.error(f"Failed to send image to Discord: {e}")
        else:
            logger.info("No reaction image available in cache (not even neutral). Skipping reaction.")
            
    except Exception as e:
        logger.exception(f"Error in generate_and_send_reaction_image task: {e}")
