"""Pure helpers for splitting assistant text to fit Discord message limits."""

DISCORD_MAX_MESSAGE_LENGTH = 2000


def split_text(text: str, max_len: int = DISCORD_MAX_MESSAGE_LENGTH) -> tuple[str, str]:
    """
    Split text into (head, tail) with len(head) <= max_len and head + tail == text.
    Prefers breaking after the last newline within head, else last whitespace, else hard cut.
    """
    if not text:
        return "", ""
    if len(text) <= max_len:
        return text, ""
    window = text[:max_len]
    nl = window.rfind("\n")
    if nl != -1:
        return text[: nl + 1], text[nl + 1 :]
    sp = -1
    for i in range(len(window) - 1, -1, -1):
        if window[i].isspace():
            sp = i
            break
    if sp != -1:
        return text[: sp + 1], text[sp + 1 :]
    return text[:max_len], text[max_len:]
