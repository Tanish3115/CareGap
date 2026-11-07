def safe_text(value):
    """Reject PostgreSQL-incompatible NUL before persistence, without logging values."""
    if isinstance(value, str) and "\x00" in value:
        raise ValueError("Text contains an unsupported control character")
    if isinstance(value, dict):
        for key, item in value.items():
            safe_text(key)
            safe_text(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            safe_text(item)
    return value
