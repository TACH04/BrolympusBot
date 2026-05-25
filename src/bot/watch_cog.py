import os
import discord
from discord.ext import commands, tasks
import asyncio
import logging
from pathlib import Path

from integrations.media_stream import StreamCapture, resize_for_vlm
from integrations.vlm_manager import describe_frame
from integrations.tts_manager import get_tts_provider

logger = logging.getLogger(__name__)

class WatchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.stream_url = os.getenv("WATCH_STREAM_URL", "rtmp://localhost/live/stream")
        self.interval = int(os.getenv("WATCH_INTERVAL_SECONDS", "5"))
        
        self.capture = None
        self.tts_provider = get_tts_provider()
        
        self.commentary_task = None
        self.busy_event = asyncio.Event()
        self.busy_event.clear() # cleared = not busy
        
        self.mediamtx_process = None

    async def _start_mediamtx(self):
        """Starts the mediamtx subprocess if it's not running."""
        mediamtx_bin = os.path.join(os.getcwd(), 'bin', 'mediamtx')
        config_path = os.path.join(os.getcwd(), 'bin', 'mediamtx.yml')
        
        if not os.path.exists(mediamtx_bin):
            logger.warning("mediamtx binary not found. Stream capture may fail if external server isn't running.")
            return
            
        logger.info("Starting mediamtx subprocess...")
        self.mediamtx_process = await asyncio.create_subprocess_exec(
            mediamtx_bin, config_path,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )

    async def _stop_mediamtx(self):
        if self.mediamtx_process:
            logger.info("Terminating mediamtx subprocess...")
            self.mediamtx_process.terminate()
            await self.mediamtx_process.wait()
            self.mediamtx_process = None

    def _get_ffmpeg_filter(self) -> str:
        """Returns the FFmpeg filter string based on preset."""
        preset = os.getenv("WATCH_VOICE_FILTER", "announcer").lower()
        
        presets = {
            "announcer": "aecho=0.6:0.7:40:0.25,asetrate=44100*1.15,atempo=0.87",
            "chipmunk": "asetrate=44100*1.4,atempo=0.71",
            "movie_trailer": "asetrate=44100*0.75,atempo=1.33,aecho=0.8:0.9:100:0.4",
            "robot": "afftfilt=real='hypot(re\,im)*sin(0)':imag='hypot(re\,im)*cos(0)',aecho=0.6:0.6:10:0.3"
        }
        
        return presets.get(preset, preset) # fallback to raw string if no preset matches

    @commands.command(name='watch')
    async def watch_cmd(self, ctx, *, game_hint: str = ""):
        """Joins your voice channel and starts live commentary."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be in a voice channel first.")
            return

        voice_channel = ctx.author.voice.channel

        if ctx.voice_client:
            await ctx.voice_client.move_to(voice_channel)
        else:
            await voice_channel.connect()

        # Start MediaMTX if we manage it
        await self._start_mediamtx()

        # Start Capture
        if self.capture:
            self.capture.stop()
        self.capture = StreamCapture(self.stream_url)
        self.capture.start()

        # Start loop
        if self.commentary_task and not self.commentary_task.done():
            self.commentary_task.cancel()
            
        self.busy_event.clear()
        self.commentary_task = asyncio.create_task(self._commentary_loop(ctx.voice_client, game_hint))

        await ctx.send(f"👁️ Brolympus is watching you play {game_hint or 'the game'}. Commence suffering.")

    @commands.command(name='unwatch')
    async def unwatch_cmd(self, ctx):
        """Stops live commentary and leaves the voice channel."""
        if self.commentary_task:
            self.commentary_task.cancel()
            self.commentary_task = None
            
        if self.capture:
            self.capture.stop()
            self.capture = None
            
        if ctx.voice_client:
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            await ctx.voice_client.disconnect()
            
        await self._stop_mediamtx()

        await ctx.send("🛑 I have seen enough.")

    async def _commentary_loop(self, voice_client: discord.VoiceClient, game_hint: str):
        logger.info("Commentary loop started.")
        while True:
            await asyncio.sleep(self.interval)
            
            if self.busy_event.is_set():
                logger.debug("Bot is busy analyzing or speaking, skipping frame capture.")
                continue
                
            frame = self.capture.get_latest_frame()
            if frame is None:
                logger.debug("No frame available yet.")
                continue
                
            # We have a frame, mark busy
            self.busy_event.set()
            
            try:
                # 1. Resize and get bytes
                image_bytes = resize_for_vlm(frame, width=640)
                
                # 2. VLM Inference
                text = await describe_frame(image_bytes, game_hint)
                if not text:
                    self.busy_event.clear()
                    continue
                    
                # 3. TTS Synthesis
                wav_path = await self.tts_provider.synthesize(text)
                
                # 4. Play Audio
                self._play_audio(voice_client, wav_path)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Error in commentary loop: {e}")
                self.busy_event.clear()

    def _play_audio(self, voice_client: discord.VoiceClient, wav_path: Path):
        """Plays the audio file using discord's FFmpegPCMAudio, then cleans up."""
        if voice_client.is_playing():
            voice_client.stop()
            
        options = ""
        ff_filter = self._get_ffmpeg_filter()
        if ff_filter:
            options = f'-af "{ff_filter}"'
            
        def after_playing(error):
            if error:
                logger.error(f"Error playing audio: {error}")
            
            # Clean up the temp wav file
            try:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
            except Exception as e:
                logger.error(f"Failed to delete temp wav {wav_path}: {e}")
                
            # We are done speaking, clear busy event
            self.busy_event.clear()

        # Run the player
        try:
            source = discord.FFmpegPCMAudio(str(wav_path), options=options)
            voice_client.play(source, after=after_playing)
        except Exception as e:
            logger.error(f"Failed to start FFmpegPCMAudio: {e}")
            self.busy_event.clear()
            
            # Cleanup immediately if it failed to start
            if os.path.exists(wav_path):
                os.remove(wav_path)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        # Auto cleanup if bot is disconnected by admin
        if member == self.bot.user and before.channel is not None and after.channel is None:
            if self.commentary_task:
                self.commentary_task.cancel()
                self.commentary_task = None
            if self.capture:
                self.capture.stop()
                self.capture = None
            asyncio.create_task(self._stop_mediamtx())
