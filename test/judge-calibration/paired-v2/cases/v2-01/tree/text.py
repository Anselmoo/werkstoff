import re


def slugify(title):
    s = re.sub(r'[\s-]+', '-', title.strip().lower())
    return s.strip('-')
