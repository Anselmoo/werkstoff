"""Minimal, dependency-free parser for the YAML-subset frontmatter used by
.claude/self-assess.local.md. Deliberately does not depend on PyYAML so the
plugin has zero third-party dependencies.

Supports: flat scalars, one level of nested mapping, and simple lists of
scalars written as `- item` lines. That subset covers every settings field
this plugin's rules reference. Anything more exotic in the file is ignored
rather than guessed at.
"""
import re

_BOOL = {"true": True, "false": False}


def _coerce_scalar(raw):
    raw = raw.strip()
    if raw == "":
        return None
    if raw[0] == raw[-1] and raw[0] in ("'", '"') and len(raw) >= 2:
        return raw[1:-1]
    low = raw.lower()
    if low in _BOOL:
        return _BOOL[low]
    try:
        if re.fullmatch(r"-?\d+", raw):
            return int(raw)
        if re.fullmatch(r"-?\d+\.\d+", raw):
            return float(raw)
    except ValueError:
        pass
    return raw


def parse_frontmatter(text):
    """Return the dict encoded in a leading `---\n...\n---` block, or {} if absent."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.DOTALL)
    if not match:
        return {}
    body = match.group(1)
    lines = body.split("\n")
    root = {}
    stack = [(-1, root)]
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.strip().startswith("#"):
            i += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]

        if stripped.startswith("- "):
            # list item under the last seen key of the current parent
            key = parent.setdefault("__last_key__", None)
            i += 1
            continue

        if ":" not in stripped:
            i += 1
            continue

        key, _, rest = stripped.partition(":")
        key = key.strip()
        rest = rest.strip()

        if rest == "":
            # Could be a nested mapping or a list starting on following lines.
            collected_list = []
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    j += 1
                    continue
                nxt_indent = len(nxt) - len(nxt.lstrip(" "))
                if nxt_indent <= indent:
                    break
                if nxt.strip().startswith("- "):
                    collected_list.append(_coerce_scalar(nxt.strip()[2:]))
                    j += 1
                    continue
                break
            if collected_list:
                parent[key] = collected_list
                i = j
                continue
            nested = {}
            parent[key] = nested
            stack.append((indent, nested))
            i += 1
            continue

        parent[key] = _coerce_scalar(rest)
        i += 1

    root.pop("__last_key__", None)
    return root
