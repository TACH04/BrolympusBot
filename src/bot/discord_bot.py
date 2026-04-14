import discord
from discord.ext import commands
import os
import json
import time
import asyncio
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
import aiohttp
from agents.agent import GeneralAgent

# Configure logging
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_file = 'discord_bot.log'

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

logger = logging.getLogger('bot.discord_bot')

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

if not DISCORD_TOKEN or DISCORD_TOKEN == "your_bot_token_here":
    logger.error("DISCORD_TOKEN is not set in .env")
    exit(1)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Session Management
SESSION_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'sessions')
SESSION_TTL_DAYS = int(os.getenv("SESSION_TTL_DAYS", "7"))
# Max number of recent messages whose image data is persisted to disk
SESSION_IMAGE_TURNS_KEPT = int(os.getenv("SESSION_IMAGE_TURNS_KEPT", "3"))


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.tasks = {}
        self.http_session = None
        self._init_lock = asyncio.Lock()
        os.makedirs(SESSION_DIR, exist_ok=True)

    # ------------------------------------------------------------------
    # Session access
    # ------------------------------------------------------------------

    async def get_session(self, channel_id: int):
        """Returns the (GeneralAgent, asyncio.Lock) for a given channel."""
        if channel_id in self.sessions:
            session = self.sessions[channel_id]
            session['last_access'] = asyncio.get_event_loop().time()
            return session['agent'], session['lock']

        async with self._init_lock:
            # Double-check after acquiring the lock to avoid redundant loads
            if channel_id not in self.sessions:
                agent = GeneralAgent()
                loaded = await self._load_session(channel_id, agent)
                if loaded:
                    logger.info(f"Restored persisted session for channel {channel_id}.")
                else:
                    logger.info(f"Creating new session for channel {channel_id}.")
                self.sessions[channel_id] = {
                    'agent': agent,
                    'lock': asyncio.Lock(),
                    'last_access': asyncio.get_event_loop().time()
                }

        session = self.sessions[channel_id]
        session['last_access'] = asyncio.get_event_loop().time()
        return session['agent'], session['lock']

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _session_path(self, channel_id: int) -> str:
        return os.path.join(SESSION_DIR, f"{channel_id}.json")

    async def save_session(self, channel_id: int):
        """Serialize and save the current session to disk."""
        if channel_id not in self.sessions:
            return
        agent = self.sessions[channel_id]['agent']
        try:
            messages = self._prune_images_for_storage(agent.get_history())
            payload = {
                "channel_id": channel_id,
                "saved_at": time.time(),
                "messages": messages,
            }
            path = self._session_path(channel_id)
            
            def do_save():
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(payload, f, ensure_ascii=False)
            
            await asyncio.to_thread(do_save)
            logger.debug(f"Session saved for channel {channel_id} ({len(messages)} messages).")
        except Exception as e:
            logger.error(f"Failed to save session for channel {channel_id}: {e}")

    async def _load_session(self, channel_id: int, agent: GeneralAgent) -> bool:
        """Load a persisted session from disk into the given agent. Returns True on success."""
        path = self._session_path(channel_id)
        
        exists = await asyncio.to_thread(os.path.exists, path)
        if not exists:
            return False
            
        try:
            def do_load():
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            
            payload = await asyncio.to_thread(do_load)
            messages = payload.get("messages", [])
            if not messages:
                return False
            agent.load_history(messages)
            return True
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Session file corrupted for channel {channel_id}, deleting: {e}")
            await self.delete_session_file(channel_id)
            return False
        except Exception as e:
            logger.error(f"Failed to load session for channel {channel_id}: {e}")
            return False

    async def delete_session_file(self, channel_id: int):
        """Remove the persisted session file for a channel."""
        path = self._session_path(channel_id)
        exists = await asyncio.to_thread(os.path.exists, path)
        if exists:
            try:
                await asyncio.to_thread(os.remove, path)
                logger.info(f"Deleted session file for channel {channel_id}.")
            except Exception as e:
                logger.error(f"Failed to delete session file for channel {channel_id}: {e}")

    # ------------------------------------------------------------------
    # Storage management
    # ------------------------------------------------------------------

    def _prune_images_for_storage(self, messages: list[dict]) -> list[dict]:
        """
        Strip image data from all but the most recent SESSION_IMAGE_TURNS_KEPT
        user messages. This keeps disk usage manageable while preserving recent
        visual context.
        """
        # Find indices of user messages that have images, newest first
        image_msg_indices = [
            i for i, m in enumerate(messages)
            if m.get("role") == "user" and m.get("images")
        ]
        # Keep images only for the last N turns
        keep_indices = set(image_msg_indices[-SESSION_IMAGE_TURNS_KEPT:])

        pruned = []
        for i, msg in enumerate(messages):
            m = dict(msg)
            if m.get("images") and i not in keep_indices:
                m = {k: v for k, v in m.items() if k != "images"}
            pruned.append(m)
        return pruned

    async def _cleanup_old_sessions(self):
        """Delete session files that haven't been updated within SESSION_TTL_DAYS."""
        cutoff = time.time() - SESSION_TTL_DAYS * 86400
        removed = 0
        try:
            def get_old_files():
                to_remove = []
                for fname in os.listdir(SESSION_DIR):
                    if not fname.endswith('.json'):
                        continue
                    fpath = os.path.join(SESSION_DIR, fname)
                    if os.path.getmtime(fpath) < cutoff:
                        to_remove.append(fpath)
                return to_remove

            old_files = await asyncio.to_thread(get_old_files)
            for fpath in old_files:
                await asyncio.to_thread(os.remove, fpath)
                removed += 1
                
            if removed:
                logger.info(f"Cleaned up {removed} expired session file(s) (TTL={SESSION_TTL_DAYS}d).")
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")

    async def close(self):
        """Close the shared HTTP session."""
        if self.http_session:
            await self.http_session.close()
            logger.info("Shared HTTP session closed.")

session_manager = SessionManager()

# Supported image MIME types for vision
IMAGE_MIME_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/gif", "image/webp"}
MAX_IMAGES_PER_MESSAGE = 5

async def download_images(attachments) -> list[bytes]:
    """Download image attachments from a Discord message and return them as a list of bytes."""
    image_bytes_list = []
    
    # MIME types to filenames extension fallback
    valid_exts = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}
    
    image_attachments = []
    for a in attachments:
        is_image = False
        if a.content_type:
            mime = a.content_type.split(';')[0].strip().lower()
            if mime in IMAGE_MIME_TYPES:
                is_image = True
        
        # Fallback to extension if content_type is missing or generic
        if not is_image and a.filename:
            ext = os.path.splitext(a.filename.lower())[1]
            if ext in valid_exts:
                is_image = True
                
        if is_image:
            image_attachments.append(a)

    image_attachments = image_attachments[:MAX_IMAGES_PER_MESSAGE]

    if not image_attachments:
        if attachments:
            logger.info(f"Skipped {len(attachments)} attachments (none matched image types).")
        return []

    if not session_manager.http_session:
        session_manager.http_session = aiohttp.ClientSession()
        logger.info("Initialized shared HTTP session for image downloads.")

    session = session_manager.http_session
    for attachment in image_attachments:
        try:
            async with session.get(attachment.url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    image_bytes_list.append(data)
                    logger.info(f"Downloaded image attachment: {attachment.filename} ({len(data)} bytes)")
                else:
                    logger.warning(f"Failed to download attachment {attachment.filename}: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Error downloading attachment {attachment.filename}: {e}")

    return image_bytes_list

@bot.event
async def on_ready():
    if not session_manager.http_session:
        session_manager.http_session = aiohttp.ClientSession()
        logger.info("Initialized shared HTTP session on bot ready.")
    
    # Start background cleanup of old sessions
    asyncio.create_task(session_manager._cleanup_old_sessions())
    
    logger.info(f'✅ Logged in as {bot.user.name} ({bot.user.id})')
    logger.info(f'Connected to {len(bot.guilds)} server(s):')
    for guild in bot.guilds:
        logger.info(f' - {guild.name} (ID: {guild.id})')
    
    logger.info('Bot is ready to receive commands!')
    logger.info('------')

@bot.command(name='help')
async def help_cmd(ctx):
    """Displays this help message."""
    help_text = """**Brolympus Bot Commands:**
`!clear` - Reset my conversation context immediately.
`!rebase <new prompt>` - Reset conversation context and completely replace my system prompt.
`!stop` - Interrupt the current active task.
`!session` - Display current session details (model, message count, idle time).
`!help` - Display this message.

Just mention me or talk directly to me to check and modify the squad's Google Calendar!"""
    await ctx.send(help_text)

@bot.command(name='stop')
async def stop_cmd(ctx):
    """Interrupt the current active task."""
    channel_id = ctx.channel.id
    if channel_id in session_manager.tasks:
        task = session_manager.tasks[channel_id]
        if not task.done():
            task.cancel()
            logger.info(f"User {ctx.author} stopped task in channel {channel_id}.")
            await ctx.send("🛑 Stopping current task...")
        else:
            await ctx.send("No active task to stop.")
    else:
        await ctx.send("No active task to stop.")

@bot.command(name='clear')
async def clear_cmd(ctx):
    """Reset the conversation context."""
    logger.info(f"User {ctx.author} ran !clear command in channel {ctx.channel.id}.")
    agent, lock = await session_manager.get_session(ctx.channel.id)
    async with lock:
        agent.reset()
        await session_manager.delete_session_file(ctx.channel.id)
        await ctx.send("✅ Conversation context for this channel has been cleared.")

@bot.command(name='rebase')
async def rebase_cmd(ctx, *, new_prompt: str = None):
    """Reset the conversation context and replace the system prompt."""
    if not new_prompt:
        await ctx.send("❌ You must provide a new prompt. Usage: `!rebase <new prompt>`")
        return

    logger.info(f"User {ctx.author} ran !rebase command in channel {ctx.channel.id}.")
    agent, lock = await session_manager.get_session(ctx.channel.id)
    async with lock:
        agent.rebase(new_prompt)
        await session_manager.delete_session_file(ctx.channel.id)
        await session_manager.save_session(ctx.channel.id)
        await ctx.send("✅ Conversation reset and system instructions updated!")

@bot.command(name='session')
async def session_cmd(ctx):
    """Display current session details."""
    logger.info(f"User {ctx.author} ran !session command in channel {ctx.channel.id}.")
    agent, _ = await session_manager.get_session(ctx.channel.id)
    info = agent.get_session_info()
    idle_str = f"{info['idle_seconds']} seconds"
    if info['idle_seconds'] > 60:
        idle_str = f"{info['idle_seconds'] // 60} min {info['idle_seconds'] % 60} sec"
    
    msg = (f"**Session Info (Channel Context):**\n"
           f"- Model: `{info['model']}`\n"
           f"- Message Count: `{info['message_count']}`\n"
           f"- Estimated Tokens: `{info.get('estimated_tokens', '?')}` / 8000\n"
           f"- Memory Compressions: `{info.get('compression_count', 0)}`\n"
           f"- Idle Time: `{idle_str}`")
    await ctx.send(msg)

@bot.event
async def on_message(message):
    # Don't respond to ourselves
    if message.author == bot.user:
        return

    # Process commands first (like !help, !clear, !session)
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    # Check if the bot is mentioned or if it's a DM
    is_dm = isinstance(message.channel, discord.DMChannel)
    is_mentioned = bot.user in message.mentions
    
    # Diagnostic logging for server interaction
    if not is_dm and is_mentioned:
        logger.info(f"Mentioned in channel {message.channel.id} of guild {message.guild.id}. Attachments: {len(message.attachments)}")
        for i, a in enumerate(message.attachments):
            logger.info(f" - Attachment {i}: {a.filename} (content_type: {a.content_type})")

    # If not mentioned and not a DM, ignore the message
    if not (is_dm or is_mentioned):
        return
    
    # Strip the mention from the message content to avoid confusing the agent
    content = message.content
    if is_mentioned:
        # discord.py's message.content includes the mention. 
        # We replace the bot's mention (both <@ID> and <@!ID> formats) with empty string
        mention_str = bot.user.mention
        content = content.replace(mention_str, '').strip()
        # Also handle the variant mention with '!' which sometimes appears
        content = content.replace(mention_str.replace('<@', '<@!'), '').strip()

    # Download any image attachments
    images = await download_images(message.attachments)

    # If the message has no text and no images after stripping the mention, don't respond
    if not content and not images and is_mentioned:
        await message.reply("How can I help the squad today? (Type `!help` for commands)")
        return
    
    # If there's no text at all (pure image, no mention text) don't respond to non-DM/non-mention
    if not content and images and is_mentioned:
        content = "What do you see in this image?"

    # Handle reply in a separate task so it can be cancelled
    task = asyncio.create_task(process_and_reply(message, content, is_mentioned, images))
    session_manager.tasks[message.channel.id] = task
    
    try:
        await task
    except asyncio.CancelledError:
        logger.info(f"Task for channel {message.channel.id} was cancelled.")
        # Optional: We could send a message here, but !stop command already sends one.
    except Exception as e:
        logger.exception(f"Error in task for channel {message.channel.id}: {e}")
    finally:
        if session_manager.tasks.get(message.channel.id) == task:
            del session_manager.tasks[message.channel.id]

async def process_and_reply(message, content, is_mentioned, images: list = None):
    sender_name = message.author.display_name
    server_name = message.guild.name if message.guild else "DM"
    channel_name = message.channel.name if hasattr(message.channel, 'name') else "DM"
    
    logger.info(f"Processing message from {sender_name} in [{server_name} | #{channel_name}]: '{content}'")
    
    agent, lock = await session_manager.get_session(message.channel.id)
    
    # Use a lock to process channel messages sequentially
    if lock.locked():
        wait_msg = await message.reply("*(Waiting for my turn to process your request...)*")
    else:
        wait_msg = None

    async with lock:
        if wait_msg:
            try:
                await wait_msg.delete()
            except:
                pass
                
        response_msg = await message.reply("*(Thinking...)*")
        current_content = ""
        created_event_links = []
        last_edit_time = asyncio.get_event_loop().time()
        tools_used = []
        
        try:
            async for event in agent.chat_step(content, sender_name=sender_name, images=images or []):
                if event['type'] == 'status':
                    # Always show status until the actual streaming response starts
                    if not current_content:
                        try:
                            await response_msg.edit(content=f"*({event['content']})*")
                        except Exception as e:
                            logger.warning(f"Failed to edit status: {e}")
                elif event['type'] == 'debug_event':
                    # Surface scraping/summarization progress to the user
                    if not current_content and event.get('category') == 'scraping':
                        try:
                            await response_msg.edit(content=f"*({event['content']})*")
                        except Exception as e:
                            logger.warning(f"Failed to edit debug status: {e}")
                elif event['type'] == 'tool_call':
                    logger.info(f"Agent requested tool call: {event['tool']} with args: {event['args']}")
                    tools_used.append(event['tool'])
                    if not current_content:
                        try:
                            await response_msg.edit(content=f"*(Calling tool: {event['tool']}...)*")
                        except Exception as e:
                            logger.warning(f"Failed to edit tool call status: {e}")
                elif event['type'] == 'stream_chunk':
                    current_content += event['content']
                    now = asyncio.get_event_loop().time()
                    # Edit every 1 second to avoid rate limits
                    if now - last_edit_time > 1.2: # increased slightly for safety
                        try:
                            await response_msg.edit(content=current_content)
                            last_edit_time = now
                        except discord.errors.HTTPException as e:
                            logger.warning(f"Ignored HTTPException during message edit update: {e}")
                            pass # Ignore temporary edit failures
                elif event['type'] == 'tool_result':
                    logger.debug(f"Tool {event['tool']} returned: {event['result']}")
                    if event['tool'] == 'create_event':
                        import re
                        # Look for the URL pattern in the create_event result
                        match = re.search(r'(https://www\.google\.com/calendar/event\?eid=[\w]+)', event['result'])
                        if match:
                            created_event_links.append(match.group(1))
                            logger.info(f"Captured calendar link for embed: {match.group(1)}")
                    pass # Silent on result, wait for the agent to talk
                elif event['type'] == 'message':
                    logger.info(f"Agent generated response (Tokens: {event.get('tokens', 'N/A')}): '{event.get('content', '')}'")
                elif event['type'] == 'error':
                    logger.error(f"Agent generated an error: {event['content']}")
                    await message.reply(f"❌ Error: {event['content']}")
                    break
                    
            # Final update to ensure we didn't miss the last chunks
            # Try to embed the link in the text using markdown if "Google Calendar" is mentioned
            if created_event_links and current_content:
                link = created_event_links[0] # Grab the first created link
                if "Google Calendar" in current_content:
                    current_content = current_content.replace("Google Calendar", f"[Google Calendar]({link})")
                else:
                    current_content += f"\n\n[View Event on Google Calendar]({link})"
                    
            # Save session to disk after each successful response
            await session_manager.save_session(message.channel.id)

            if current_content:
                # Append tools used if any
                if tools_used:
                    from collections import Counter
                    # Count tools while preserving order of first appearance
                    counts = Counter(tools_used)
                    unique_tools = []
                    for t in tools_used:
                        if t not in unique_tools:
                            unique_tools.append(t)
                    
                    tool_parts = []
                    for t in unique_tools:
                        count = counts[t]
                        if count > 1:
                            tool_parts.append(f"`{t}` (x{count})")
                        else:
                            tool_parts.append(f"`{t}`")
                    
                    current_content += f"\n\n*Tools used: {', '.join(tool_parts)}*"
    
                try:
                    await response_msg.edit(content=current_content)
                except discord.errors.NotFound:
                    # Message might have been deleted
                    pass
            elif not current_content:
                 # Fallback if no content was generated
                 logger.warning("No content was generated by the agent.")
                 try:
                    await response_msg.edit(content="I'm sorry, I couldn't generate a response.")
                 except discord.errors.NotFound:
                    pass
                
        except asyncio.CancelledError:
            # Re-raise to be caught by the outer try-except
            raise
        except Exception as e:
            logger.exception(f"An unexpected error occurred during chat step: {e}")
            await message.reply(f"❌ An error occurred: {e}")

if __name__ == '__main__':
    logger.info("Starting Discord bot...")
    bot.run(DISCORD_TOKEN)
