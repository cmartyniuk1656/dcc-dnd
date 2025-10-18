import re


_ILLEGAL_FS_CHARS = re.compile(r'[<>:"/\\|?*]')


def sanitize_title_for_fs(title: str) -> str:
    """Return a filesystem-safe representation of a wiki title."""
    safe = _ILLEGAL_FS_CHARS.sub("_", title or "")
    safe = safe.strip()
    if not safe:
        return "item"
    # Windows does not allow names ending with dot or space.
    safe = safe.rstrip(". ")
    if not safe:
        return "item"
    return safe
