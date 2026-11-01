#!/usr/bin/env python3
"""Delete files for an approved `delete` item -- by script, reversibly, never by a model's `rm`.

usage: apply_delete.py [-h] --item ID [--accept-references] | --restore [--item ID]

Deleting is part of repairing: dead code, a superseded chart, a stale config. It is
also the operation a model is least trusted to do by hand, so the guard denies `rm`,
`git rm`, `mv`, `unlink` and `find -delete` while a repair run is active, and this
script is the only route:

  1. the item must be in the APPROVED changeset, be active, and have op "delete";
  2. each path is searched for by name and stem across the objective's scope; any
     file that still mentions it is listed, and the delete is REFUSED unless the
     user accepted those references (--accept-references, after showing them);
  3. the file moves to .cupertino/repair/<run>/trash/<path> and is recorded in
     trash/manifest.json with its sha256, the item, the reason and the references;
  4. --restore puts every trashed file (or one item's) back and checks the hash.

Exit: 0 done; 1 refused; 2 bad usage.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from repair_lib import (  # noqa: E402
    RepairError,
    active_run,
    approved_changeset,
    project_root,
    read_json,
    rel_posix,
    run_dir,
    scope_files,
    sha256_file,
    write_json,
)

TEXT_SUFFIXES = {".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".htm", ".css", ".scss", ".json", ".md", ".toml",
                 ".yaml", ".yml", ".cfg", ".ini", ".sh", ".c", ".h", ".rs", ".go", ".java", ".vue", ".svelte", ".mk",
                 ".txt", ".ld", ".s", ".S"}


def references(root: Path, rel: str, scope: list[str]) -> list[str]:
    """Files in scope that mention the target's file name or (for code) its import stem."""
    name = Path(rel).name
    stem = Path(rel).stem
    pats = [re.escape(name)]
    if len(stem) >= 4:
        pats.append(rf"\b{re.escape(stem)}\b")
    rx = re.compile("|".join(pats))
    hits = []
    for other in scope_files(root, scope):
        if other == rel:
            continue
        p = root / other
        if p.suffix not in TEXT_SUFFIXES and p.name not in ("Makefile", "Dockerfile"):
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                hits.append(f"{other}:{n}: {line.strip()[:160]}")
                break
    return hits


def delete(root: Path, run_id: str, item_id: str, accept_refs: bool) -> dict:
    rdir = run_dir(root, run_id)
    changeset = approved_changeset(root, run_id)
    item = next((i for i in changeset["items"] if i["id"] == item_id), None)
    if item is None:
        raise RepairError(f"no item {item_id!r} in the approved changeset")
    if item["op"] != "delete":
        raise RepairError(f"item {item_id} is a {item['op']}, not a delete")
    active = rdir / "active-item"
    if not active.is_file() or active.read_text(encoding="utf-8").strip() != item_id:
        raise RepairError(f"item {item_id} is not active -- repair_state.py start-item {item_id} first")
    objective = read_json(rdir / "objective.json")
    manifest_path = rdir / "trash" / "manifest.json"
    manifest = read_json(manifest_path) if manifest_path.is_file() else {"entries": []}
    plan = []
    for raw in item["paths"]:
        rel = rel_posix(root, raw)
        src = root / rel
        if not src.is_file():
            raise RepairError(f"{rel} does not exist (already deleted, or never was)")
        refs = references(root, rel, objective["scope"])
        if refs and not accept_refs:
            raise RepairError(f"{rel} is still referenced -- show these to the user; rerun with --accept-references only if they "
                              "agree each is dead or is changed by another approved item:\n  " + "\n  ".join(refs))
        plan.append((rel, src, refs))
    done = []
    for rel, src, refs in plan:
        dest = rdir / "trash" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256_file(src)
        shutil.move(str(src), str(dest))
        manifest["entries"].append({"path": rel, "sha256": digest, "item": item_id, "reason": item.get("rationale", ""),
                                    "evidence": item.get("evidence", ""), "referencesAccepted": refs,
                                    "at": datetime.datetime.now(datetime.UTC).isoformat(), "restored": False})
        done.append(rel)
    write_json(manifest_path, manifest)
    return {"ok": True, "item": item_id, "deleted": done, "trash": str(rdir / "trash")}


def restore(root: Path, run_id: str, item_id: str | None) -> dict:
    rdir = run_dir(root, run_id)
    manifest_path = rdir / "trash" / "manifest.json"
    manifest = read_json(manifest_path)
    restored = []
    for e in manifest["entries"]:
        if e["restored"] or (item_id and e["item"] != item_id):
            continue
        src, dest = rdir / "trash" / e["path"], root / e["path"]
        if dest.exists():
            raise RepairError(f"cannot restore {e['path']}: a file is already there")
        if sha256_file(src) != e["sha256"]:
            raise RepairError(f"trashed copy of {e['path']} changed since deletion; refusing to restore it blind")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
        e["restored"] = True
        restored.append(e["path"])
    write_json(manifest_path, manifest)
    return {"ok": True, "restored": restored}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="apply_delete.py", description="Reversible, script-only delete for an approved item.",
                                     epilog="exit 0 done, 1 refused, 2 bad usage")
    parser.add_argument("--item")
    parser.add_argument("--accept-references", action="store_true")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--run", help="run id (default: the active run)")
    args = parser.parse_args(argv)
    if not args.restore and not args.item:
        parser.error("--item is required unless --restore")
    root = project_root()
    try:
        run_id = args.run or active_run(root)
        if not run_id:
            raise RepairError("no repair run is active")
        out = restore(root, run_id, args.item) if args.restore else delete(root, run_id, args.item, args.accept_references)
    except RepairError as err:
        print(f"apply_delete: {err}", file=sys.stderr)
        return 1
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
