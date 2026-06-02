import os
import json
import logging
import asyncio
import discord
import ollama
from integrations.stable_diffusion import generate_local_image

logger = logging.getLogger('bot.personality_reactions')

def get_current_personality() -> dict:
    personality_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'current_personality.json'))
    if os.path.exists(personality_path):
        try:
            with open(personality_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading current_personality.json: {e}")
    return {}

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
    
    # Map common reaction descriptions to stable diffusion tags
    emotion_tags = {
        "facepalm": "facepalm, looking frustrated, hand on face",
        "eyeroll": "eyeroll, rolling eyes, looking annoyed",
        "laughing": "laughing, big open mouth smile",
        "smirking": "smirking, smug expression",
        "confused": "confused expression, head tilted, puzzled",
        "glaring": "glaring, frowning, angry expression",
        "shocked": "shocked, surprised expression, wide eyes",
        "thinking": "thinking expression, hand on chin, looking pensive",
        "thumbs up": "thumbs up gesture, smiling, friendly",
        "shrugging": "shrugging, hands up, neutral expression",
        "crying": "crying, tears, sad expression",
        "yawning": "yawning, tired expression, hand covering mouth",
        "screaming": "screaming, terrified, wide open mouth",
        "wink": "winking, friendly expression, one eye closed",
    }
    
    emotion_lower = emotion.lower().strip()
    tag = emotion_lower
    for k, v in emotion_tags.items():
        if k in emotion_lower:
            tag = v
            break
            
    return f"{cleaned_base}, {tag}"

async def generate_and_send_reaction_image(message: discord.Message, user_content: str, bot_response: str):
    try:
        # Load personality details
        p = get_current_personality()
        # Fallback if no personality is set
        base_prompt = p.get('avatar_prompt', 'portrait of a cool robot, neon accents, gym background')
        
        # 1. Determine reaction emotion
        emotion = await determine_reaction_emotion(user_content, bot_response)
        logger.info(f"Determined reaction emotion for message: {emotion}")
        
        # 2. Formulate prompt
        prompt = get_reaction_prompt(base_prompt, emotion)
        logger.info(f"Generating reaction image with prompt: {prompt}")
        
        # 3. Generate image
        # Stable Diffusion can take a bit, so we do this completely in background
        img_result = await generate_local_image(prompt, extra_negative_prompt="nsfw, naked, nude, suggestive, gore, text, words, logo")
        if img_result.get("status") == "success":
            img_path = img_result.get("image_path")
            if img_path and os.path.exists(img_path):
                try:
                    with open(img_path, 'rb') as f:
                        discord_file = discord.File(f, filename='reaction.png')
                        # Reply directly to the bot's own message
                        await message.reply(file=discord_file)
                    logger.info("Successfully sent reaction image.")
                except Exception as e:
                    logger.error(f"Failed to send image to Discord: {e}")
                finally:
                    if os.path.exists(img_path):
                        try:
                            os.remove(img_path)
                            logger.info(f"Cleaned up temporary image: {img_path}")
                        except Exception as e:
                            logger.error(f"Error removing temporary image: {e}")
            else:
                logger.error("Reaction image path does not exist.")
        else:
            logger.error(f"Image generation failed: {img_result.get('message')}")
    except Exception as e:
        logger.exception(f"Error in generate_and_send_reaction_image task: {e}")
