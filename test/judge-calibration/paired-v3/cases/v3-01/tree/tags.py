def parse_tags(text):
    """Split a comma-separated tag list: 'Python, Rust' -> ['python', 'rust']."""
    return [t.strip().lower() for t in text.split(",") if t]
