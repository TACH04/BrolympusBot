import logging
import datetime
import shutil
import re
from logging.handlers import RotatingFileHandler

# ANSI Escape Codes
GREY = "\033[90m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
BOLD = "\033[1m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RESET = "\033[0m"

# Map logger prefixes to component tags and colors
COMPONENT_TAGS = {
    "bot.discord_bot": ("[DISCORD]", MAGENTA),
    "integrations.stable_diffusion": ("[STABLE_DIFF]", CYAN),
    "integrations.google_calendar": ("[GOOGLE_CAL]", GREEN),
    "integrations.web_search": ("[WEB_SEARCH]", BLUE),
    "integrations.jetson_memory": ("[JETSON_MEM]", YELLOW),
    "agents.main_harness": ("[HARNESS]", MAGENTA),
    "agents.research_agent": ("[RESEARCHER]", BLUE),
    "web.app": ("[WEB_APP]", YELLOW),
    "httpx": ("[HTTPX]", BLUE),
    "werkzeug": ("[WERKZEUG]", GREY),
    "tools": ("[TOOLS]", GREEN),
}

DEFAULT_TAG = ("[SYSTEM]", GREY)
TAG_WIDTH = 13

class BeautifulConsoleFormatter(logging.Formatter):
    def format(self, record):
        # 1. Format Timestamp (HH:MM:SS)
        dt = datetime.datetime.fromtimestamp(record.created)
        timestamp = f"{GREY}{dt.strftime('%H:%M:%S')}{RESET}"

        # 2. Format Level
        level_name = record.levelname
        # Map custom levels
        if "success" in record.getMessage().lower():
             level_name = "SUCCESS"
             
        if level_name == "INFO":
            level_str = f"{CYAN}[INFO   ]{RESET}"
        elif level_name == "SUCCESS":
             level_str = f"{GREEN}[SUCCESS]{RESET}"
        elif level_name in ("WARNING", "WARN"):
            level_str = f"{YELLOW}[WARN   ]{RESET}"
        elif level_name in ("ERROR", "CRITICAL"):
            level_str = f"{BOLD}{RED}[ERROR  ]{RESET}"
        else:
             level_str = f"{GREY}[{level_name[:7]:<7}]{RESET}"

        # 3. Component Tag
        tag_text, tag_color = DEFAULT_TAG
        for prefix, (t_text, t_color) in COMPONENT_TAGS.items():
            if record.name.startswith(prefix):
                tag_text, tag_color = t_text, t_color
                break
        
        # Override HTTP tag if it's an HTTP request
        msg = record.getMessage()
        if "HTTP Request" in msg or record.name == "httpx":
             level_str = f"{BLUE}[HTTP   ]{RESET}"

        comp_str = f"{tag_color}{tag_text:<{TAG_WIDTH}}{RESET}"

        # 4. Parse and Condense Message
        # Flatten newlines
        msg = msg.replace('\n', ' ')

        # Condense specific verbose messages
        if "HTTP Request: " in msg:
            # e.g. HTTP Request: POST http://127.0.0.1:11434/api/chat "HTTP/1.1 200 OK"
            match = re.match(r'HTTP Request:\s+([A-Z]+)\s+(https?://[^\s"]+)\s+"HTTP/[0-9.]+\s+([^"]+)"', msg)
            if match:
                method, url, status = match.groups()
                # extract path
                from urllib.parse import urlparse
                parsed = urlparse(url)
                msg = f"{method} {parsed.path} \u2794 {status}"
        elif "Successfully generated image and saved to: " in msg:
             msg = msg.replace("Successfully generated image and saved to: ", "Generated image \u2794 ")
        elif "Successfully uploaded generated image to Discord" in msg:
             msg = "Uploaded generated image to Discord"
        elif "Deleted temporary image file: " in msg:
             msg = msg.replace("Deleted temporary image file: ", "Cleaned up temp file: ")

        # 5. Dynamic Truncation
        term_width = shutil.get_terminal_size().columns
        # Calculate plain text length of prefix (Timestamp | Level | Tag | )
        # "HH:MM:SS | [XXXXXXX] | [XXXXXXXXXXXXX] | "
        prefix_len = 8 + 3 + 9 + 3 + TAG_WIDTH + 3
        max_msg_len = term_width - prefix_len
        
        if max_msg_len > 10 and len(msg) > max_msg_len:
             msg = msg[:max_msg_len - 3] + "..."

        return f"{timestamp} | {level_str} | {comp_str} | {msg}"


def setup_logging(mode: str):
    """
    Sets up the central logging configuration.
    mode: 'bot' or 'web'
    """
    root_logger = logging.getLogger()
    
    # Remove all existing handlers to prevent duplicates
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(logging.INFO)

    # File Handler (Verbose, plain text)
    log_file = "discord_bot.log" if mode == "bot" else "web_app.log"
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)

    # Console Handler (Beautiful, colored, 1-liner)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(BeautifulConsoleFormatter())
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    # Mute noisy loggers
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('discord').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)

