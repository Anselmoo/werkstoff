def slugify(text):
    out = text.strip().lower().replace(' ', '-')
    return ''.join(ch for ch in out if ch.isalnum() or ch == '-')
