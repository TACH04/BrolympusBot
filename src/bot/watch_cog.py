import os
import discord
from discord.ext import commands
import asyncio
import logging
from pathlib import Path
import json
import random
import string
from aiohttp import web

from integrations.vlm_manager import describe_frame
from integrations.tts_manager import get_tts_provider

logger = logging.getLogger(__name__)

REGISTRY_FILE = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'watch_registry.json')

class WatchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tts_provider = get_tts_provider()
        
        self.busy_event = asyncio.Event()
        self.busy_event.clear()
        
        self.active_watcher_id = None
        self.game_hint = ""
        self.voice_client = None
        
        # In-memory mapping of PIN -> Discord User ID (TTL can be added if needed)
        self.pending_tokens = {}
        
        self.registry = self._load_registry()
        
        self.personality = "announcer"
        self.commentary_history = []
        
        self.app = web.Application()
        self.app.router.add_post('/agent/register', self.handle_register)
        self.app.router.add_get('/agent/status', self.handle_status)
        self.app.router.add_post('/agent/frame', self.handle_frame)
        self.runner = None
        self.site = None

    def _load_registry(self):
        try:
            if os.path.exists(REGISTRY_FILE):
                with open(REGISTRY_FILE, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load watch registry: {e}")
        return {}

    def _save_registry(self):
        try:
            os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
            with open(REGISTRY_FILE, 'w') as f:
                json.dump(self.registry, f)
        except Exception as e:
            logger.error(f"Failed to save watch registry: {e}")

    async def cog_load(self):
        logger.info("Starting aiohttp server for Watch client agents on port 5002...")
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', 5002)
        await self.site.start()

    async def cog_unload(self):
        logger.info("Stopping aiohttp server...")
        if self.runner:
            await self.runner.cleanup()

    # --- HTTP Endpoints ---

    async def handle_register(self, request):
        try:
            data = await request.json()
            pin = data.get("pin")
            device_id = data.get("device_id")
            
            if not pin or not device_id:
                return web.json_response({"status": "error", "message": "Missing pin or device_id"}, status=400)
                
            if pin in self.pending_tokens:
                user_id = self.pending_tokens[pin]
                self.registry[device_id] = user_id
                self._save_registry()
                del self.pending_tokens[pin]
                
                # Fetch user for a nice message if possible
                user = self.bot.get_user(user_id)
                username = user.display_name if user else str(user_id)
                
                return web.json_response({
                    "status": "success",
                    "discord_username": username
                })
            else:
                return web.json_response({"status": "error", "message": "Invalid or expired PIN"}, status=400)
        except Exception as e:
            logger.error(f"Error in handle_register: {e}")
            return web.json_response({"status": "error", "message": "Internal server error"}, status=500)

    async def handle_status(self, request):
        device_id = request.query.get("device_id")
        if not device_id or device_id not in self.registry:
            return web.json_response({"watching": False, "error": "Unregistered device"})
            
        user_id = self.registry[device_id]
        
        if self.active_watcher_id == user_id:
            return web.json_response({
                "watching": True,
                "game_hint": self.game_hint
            })
        else:
            return web.json_response({"watching": False})

    async def handle_frame(self, request):
        device_id = request.query.get("device_id")
        if not device_id or device_id not in self.registry:
            return web.json_response({"status": "error", "message": "Unregistered device"}, status=403)
            
        user_id = self.registry[device_id]
        if self.active_watcher_id != user_id:
            return web.json_response({"status": "error", "message": "Not currently watching this user"}, status=400)

        if self.busy_event.is_set():
            return web.json_response({"status": "busy"})

        try:
            # Read frame bytes from multipart or raw body
            # For simplicity, assume the agent sends raw bytes with Content-Type: image/jpeg
            # or we can read it from a multipart form. Let's support raw bytes for efficiency.
            image_bytes = await request.read()
            if not image_bytes:
                 return web.json_response({"status": "error", "message": "Empty body"}, status=400)
            
            # Set busy immediately so subsequent frames are rejected while processing
            self.busy_event.set()
            
            # Fire and forget processing task
            active_window = request.query.get("active_window", "")
            asyncio.create_task(self._process_frame(image_bytes, self.game_hint, self.voice_client, active_window=active_window))
            
            return web.json_response({"status": "processing"})
            
        except Exception as e:
            logger.error(f"Error handling frame upload: {e}")
            self.busy_event.clear()
            return web.json_response({"status": "error"}, status=500)

    # --- Processing Pipeline ---

    async def _process_frame(self, image_bytes: bytes, game_hint: str, vc: discord.VoiceClient, active_window: str = ""):
        """Processes the frame, generates commentary, and speaks it. Safely isolated."""
        wav_path = None
        try:
            # Save the frame to a debug file on the Jetson to verify capture is working
            debug_dir = os.path.join(os.getcwd(), 'data')
            os.makedirs(debug_dir, exist_ok=True)
            debug_path = os.path.join(debug_dir, 'last_received_frame.jpg')
            with open(debug_path, 'wb') as f:
                f.write(image_bytes)
            logger.info(f"Saved incoming frame to {debug_path} ({len(image_bytes)} bytes)")

            # 1. VLM Inference (pass personality, recent commentary history, and active window)
            text = await describe_frame(image_bytes, game_hint, self.personality, list(self.commentary_history), active_window=active_window)
            if not text:
                return
                
            # Add to history to prevent word/phrase repetition in upcoming frames
            self.commentary_history.append(text)
            if len(self.commentary_history) > 3:
                self.commentary_history.pop(0)
                
            # 2. TTS Synthesis
            wav_path = await self.tts_provider.synthesize(text)
            
            # 3. Play Audio
            if vc and vc.is_connected():
                self._play_audio(vc, wav_path)
            else:
                logger.warning("Voice client disconnected before audio could play.")
                
        except Exception as e:
            logger.error(f"Error in vision pipeline: {e}", exc_info=True)
        finally:
            # If play_audio succeeds, it clears busy_event in its after_callback.
            # If we failed before playing or voice client is disconnected, clear it here.
            if not vc or not vc.is_playing():
                self.busy_event.clear()
                if wav_path and os.path.exists(wav_path):
                    try:
                        os.remove(wav_path)
                    except Exception:
                        pass

    def _get_ffmpeg_filter(self, base_rate: int) -> str:
        preset = os.getenv("WATCH_VOICE_FILTER", "announcer").lower()
        presets = {
            "announcer": f"aecho=0.6:0.7:40:0.25,asetrate={base_rate}*1.15,atempo=0.87",
            "chipmunk": f"asetrate={base_rate}*1.4,atempo=0.71",
            "movie_trailer": f"asetrate={base_rate}*0.75,atempo=1.33,aecho=0.8:0.9:100:0.4",
            "robot": "afftfilt=real='hypot(re\,im)*sin(0)':imag='hypot(re\,im)*cos(0)',aecho=0.6:0.6:10:0.3"
        }
        filter_str = presets.get(preset, preset)
        # Ensure we always resample to Discord's native 48000 Hz at the end of the filter chain
        if filter_str and not filter_str.endswith("aresample=48000"):
            filter_str += ",aresample=48000"
        return filter_str

    def _play_audio(self, voice_client: discord.VoiceClient, wav_path: Path):
        if voice_client.is_playing():
            voice_client.stop()
            
        base_rate = getattr(self.tts_provider, 'sample_rate', 22050)
        options = ""
        ff_filter = self._get_ffmpeg_filter(base_rate)
        if ff_filter:
            options = f'-af "{ff_filter}"'
            
        def after_playing(error):
            if error:
                logger.error(f"Error playing audio: {error}")
            try:
                if wav_path and os.path.exists(wav_path):
                    os.remove(wav_path)
            except Exception as e:
                logger.error(f"Failed to delete temp wav {wav_path}: {e}")
                
            self.busy_event.clear()

        try:
            source = discord.FFmpegPCMAudio(str(wav_path), options=options)
            voice_client.play(source, after=after_playing)
        except Exception as e:
            logger.error(f"Failed to start FFmpegPCMAudio: {e}")
            self.busy_event.clear()
            if wav_path and os.path.exists(wav_path):
                 os.remove(wav_path)

    # --- Discord Commands ---

    @commands.command(name='register_watch')
    async def register_watch_cmd(self, ctx):
        """Generates a PIN to link your desktop agent."""
        pin = ''.join(random.choices(string.digits, k=6))
        self.pending_tokens[pin] = ctx.author.id
        
        # Clean up old tokens simply (prevent memory leak if abused)
        if len(self.pending_tokens) > 100:
             self.pending_tokens.clear()
             self.pending_tokens[pin] = ctx.author.id
             
        try:
            await ctx.author.send(f"🔐 Your Brolympus Agent PIN is: **{pin}**\n\nEnter this in the agent tray app to link your device.")
            await ctx.send("✅ I've DMed you a registration PIN!")
        except discord.Forbidden:
            await ctx.send(f"❌ I can't DM you! Please enable DMs from server members, or use this PIN here (and delete it after): **{pin}**")

    @commands.command(name='watch')
    async def watch_cmd(self, ctx, *, game_hint: str = ""):
        """Starts watching the user's stream via their agent."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel first.")
            return

        # Check if they have a registered device
        if ctx.author.id not in self.registry.values():
            await ctx.send("❌ You haven't linked a capture agent yet. Type `!register_watch` first!")
            return

        voice_channel = ctx.author.voice.channel
        if ctx.voice_client:
            await ctx.voice_client.move_to(voice_channel)
            self.voice_client = ctx.voice_client
        else:
            self.voice_client = await voice_channel.connect()

        self.active_watcher_id = ctx.author.id
        self.game_hint = game_hint
        self.busy_event.clear()

        await ctx.send(f"👁️ Brolympus is now watching <@{ctx.author.id}> play {game_hint or 'the game'}. Agent should start capturing.")

    @commands.command(name='unwatch')
    async def unwatch_cmd(self, ctx):
        """Stops watching and leaves voice."""
        self.active_watcher_id = None
        self.busy_event.clear()
        
        if ctx.voice_client:
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            self.voice_client = None

        await ctx.send("🛑 I have stopped watching.")

    @commands.command(name='personality')
    async def personality_cmd(self, ctx, name: str = None):
        """Changes or displays the active watch personality."""
        available = ["announcer", "savage", "grandma", "analyst", "coach"]
        
        if not name:
            await ctx.send(f"🎭 **Current Personality**: `{self.personality}`\nAvailable options: " + ", ".join([f"`{a}`" for a in available]) + "\nUsage: `!personality <name>`")
            return
            
        name = name.lower()
        if name not in available:
            await ctx.send(f"❌ Unknown personality. Choose from: " + ", ".join([f"`{a}`" for a in available]))
            return
            
        self.personality = name
        self.commentary_history.clear() # Clear history on change to get a fresh start
        await ctx.send(f"🎭 Changed watch personality to: **{name}**")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Auto cleanup if bot is disconnected by admin
        if member == self.bot.user and before.channel is not None and after.channel is None:
            self.active_watcher_id = None
            self.busy_event.clear()
            self.voice_client = None
