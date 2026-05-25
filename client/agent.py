import os
import sys
import time
import json
import uuid
import threading
import io
import requests
import mss
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import tkinter as tk
from tkinter import simpledialog, messagebox
from plyer import notification

CONFIG_FILE = "config.json"
DEFAULT_SERVER_URL = "http://127.0.0.1:5002"
DEFAULT_CONFIG = {
    "server_url": DEFAULT_SERVER_URL,
    "device_id": str(uuid.uuid4())
}

class Agent:
    def __init__(self):
        self.config = self.load_config()
        self.is_running = True
        self.is_paused = False
        self.is_watching = False
        self.icon = None
        self.sct = mss.mss()
        
        self.worker_thread = threading.Thread(target=self.run_loop, daemon=True)
        self.worker_thread.start()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    cfg = json.load(f)
                    # If config has default localhost URL but executable has a custom baked IP, migrate it
                    if cfg.get("server_url") == "http://127.0.0.1:5002" and DEFAULT_SERVER_URL != "http://127.0.0.1:5002":
                        cfg["server_url"] = DEFAULT_SERVER_URL
                        self.save_config(cfg)
                    return cfg
            except:
                pass
        self.save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    def save_config(self, cfg):
        with open(CONFIG_FILE, 'w') as f:
            json.dump(cfg, f, indent=4)

    def create_image(self, color):
        width = 64
        height = 64
        image = Image.new('RGB', (width, height), color=(255, 255, 255))
        dc = ImageDraw.Draw(image)
        dc.ellipse((8, 8, 56, 56), fill=color)
        return image

    def update_icon(self):
        if not self.icon:
            return
            
        if self.is_paused:
            self.icon.icon = self.create_image("gray")
            self.icon.title = "Brolympus (Paused)"
        elif self.is_watching:
            self.icon.icon = self.create_image("red")
            self.icon.title = "Brolympus (Watching...)"
        else:
            self.icon.icon = self.create_image("green")
            self.icon.title = "Brolympus (Idle)"

    def notify(self, title, message):
        try:
            notification.notify(
                title=title,
                message=message,
                app_name="Brolympus Agent",
                timeout=5
            )
        except:
            pass # Fails gracefully if plyer isn't supported

    def run_loop(self):
        while self.is_running:
            if self.is_paused:
                time.sleep(5)
                continue
                
            try:
                url = f"{self.config['server_url']}/agent/status?device_id={self.config['device_id']}"
                resp = requests.get(url, timeout=5)
                
                if resp.status_code == 200:
                    data = resp.json()
                    watching = data.get("watching", False)
                    
                    if watching and not self.is_watching:
                        self.is_watching = True
                        self.update_icon()
                        self.notify("Brolympus", "The bot is now watching your screen!")
                        
                    elif not watching and self.is_watching:
                        self.is_watching = False
                        self.update_icon()
                        self.notify("Brolympus", "Stopped watching your screen.")
                        
                    if self.is_watching:
                        self.capture_and_send()
                        time.sleep(3) # Wait before next frame
                    else:
                        time.sleep(10) # Idle polling
                else:
                    # Server returned error
                    time.sleep(10)
            except requests.exceptions.RequestException:
                # Can't reach server
                time.sleep(10)
            except Exception as e:
                print(f"Error in loop: {e}")
                time.sleep(10)

    def capture_and_send(self):
        try:
            # Capture primary monitor
            monitor = self.sct.monitors[1]
            sct_img = self.sct.grab(monitor)
            
            # Convert to PIL Image for fast resizing/compression
            img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            
            # Resize to 720p max to save bandwidth
            img.thumbnail((1280, 720), Image.Resampling.LANCZOS)
            
            # Compress to JPEG
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=75)
            jpeg_bytes = buf.getvalue()
            
            # Upload
            url = f"{self.config['server_url']}/agent/frame?device_id={self.config['device_id']}"
            resp = requests.post(
                url,
                data=jpeg_bytes,
                headers={"Content-Type": "image/jpeg"},
                timeout=5
            )
            # If we get busy or ok, it's fine. Ignore response.
        except Exception as e:
            print(f"Capture error: {e}")

    # --- UI Callbacks ---

    def on_register(self, icon, item):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.focus_force()

        # Check if they are still on default localhost
        if "127.0.0.1" in self.config["server_url"] or "localhost" in self.config["server_url"]:
            msg = (
                "Your Server URL is currently set to the default localhost (127.0.0.1).\n\n"
                "If the bot is running on your Jetson Orin (via Tailscale), you must configure "
                "the Jetson's Tailscale IP instead.\n\n"
                "Would you like to set the server URL now?"
            )
            if messagebox.askyesno("Setup Server URL", msg, parent=root):
                root.destroy()
                self.on_set_url(icon, item)
                return

        pin = simpledialog.askstring("Register", "Enter the 6-digit PIN from Discord:", parent=root)
        if pin:
            try:
                url = f"{self.config['server_url']}/agent/register"
                resp = requests.post(url, json={"pin": pin, "device_id": self.config['device_id']}, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    messagebox.showinfo("Success", f"Linked to Discord User: {data.get('discord_username')}", parent=root)
                else:
                    data = resp.json()
                    messagebox.showerror("Error", data.get("message", "Registration failed"), parent=root)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to connect: {e}", parent=root)
        root.destroy()

    def on_set_url(self, icon, item):
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.focus_force()
        new_url = simpledialog.askstring("Server URL", "Enter Jetson Tailscale URL:", initialvalue=self.config["server_url"], parent=root)
        if new_url:
            self.config["server_url"] = new_url
            self.save_config(self.config)
        root.destroy()

    def on_toggle_pause(self, icon, item):
        self.is_paused = not self.is_paused
        self.update_icon()

    def on_exit(self, icon, item):
        self.is_running = False
        icon.stop()

    def setup_tray(self):
        menu = pystray.Menu(
            item('Status: Online', lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item('Register Device...', self.on_register, default=True),
            item('Set Server URL...', self.on_set_url),
            item(lambda _: 'Resume' if self.is_paused else 'Pause Monitoring', self.on_toggle_pause),
            pystray.Menu.SEPARATOR,
            item('Exit', self.on_exit)
        )
        self.icon = pystray.Icon("brolympus", self.create_image("green"), "Brolympus", menu)
        self.icon.run()

if __name__ == "__main__":
    # Ensure Tkinter is available on Windows without bringing up a main window
    agent = Agent()
    agent.setup_tray()
