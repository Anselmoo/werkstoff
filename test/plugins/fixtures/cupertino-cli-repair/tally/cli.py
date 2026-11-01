"""tally -- count words or lines in a file.

usage: python3 -m tally.cli {words,lines,legacy-chars} FILE
"""
import argparse
import sys
from pathlib import Path


def count_words(text: str) -> int:
    return len(text.split())


def count_lines(text: str) -> int:
    return len(text.splitlines())


def legacy_chars(text: str) -> int:
    # Deprecated in 2.0 and announced for removal; nothing calls it any more.
    return len(text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="tally")
    parser.add_argument("cmd", choices=["words", "lines", "legacy-chars"])
    parser.add_argument("file")
    args = parser.parse_args(argv)
    text = Path(args.file).read_text(encoding="utf-8")
    fn = {"words": count_words, "lines": count_lines, "legacy-chars": legacy_chars}[args.cmd]
    print(fn(text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
