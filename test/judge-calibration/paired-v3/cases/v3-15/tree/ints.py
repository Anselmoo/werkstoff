def parse_ints(text):
    """Comma-separated integers: '3, 14, 15' -> [3, 14, 15]."""
    return [int(field) for field in text.split(",") if field.strip()]
