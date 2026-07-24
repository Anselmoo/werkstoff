#!/usr/bin/env python3
"""Build an immutable, parallel-safe repository research snapshot.

This file is the RRT-managed source copied into every plugin bundle. It uses
only the Python standard library so installed plugins remain self-contained.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import sqlite3
import sys
import tempfile
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "2.0"
LOCK_TTL_SECONDS = 120
LOCK_WAIT_SECONDS = 30
LANG_EXTENSIONS = {
    ".py": "python", ".ts": "typescript", ".tsx": "typescript", ".js": "javascript",
    ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript", ".go": "go",
    ".rs": "rust", ".cpp": "cpp", ".hpp": "cpp", ".c": "c", ".h": "c",
    ".java": "java", ".kt": "kotlin", ".kts": "kotlin", ".swift": "swift",
    ".rb": "ruby", ".php": "php", ".cs": "csharp", ".scala": "scala", ".sc": "scala",
    ".dart": "dart", ".lua": "lua", ".r": "r", ".sh": "shell", ".bash": "shell",
    ".zsh": "shell", ".ps1": "powershell", ".psm1": "powershell", ".psd1": "powershell",
    ".pl": "perl", ".pm": "perl", ".t": "perl", ".erl": "erlang", ".hrl": "erlang",
    ".hs": "haskell", ".lhs": "haskell", ".ml": "ocaml", ".mli": "ocaml",
    ".fs": "fsharp", ".fsx": "fsharp", ".f90": "fortran", ".f95": "fortran",
    ".f03": "fortran", ".f08": "fortran", ".jl": "julia", ".groovy": "groovy",
    ".clj": "clojure", ".cljc": "clojure", ".cljs": "clojure", ".ex": "elixir",
    ".exs": "elixir", ".nim": "nim", ".zig": "zig", ".cr": "crystal", ".v": "v",
    ".sql": "sql", ".html": "html", ".htm": "html", ".css": "css", ".scss": "scss",
    ".sass": "sass", ".less": "less", ".svg": "svg", ".vue": "vue", ".svelte": "svelte",
    ".astro": "astro", ".json": "json", ".jsonc": "json", ".json5": "json",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".ini": "ini", ".cfg": "ini",
    ".conf": "ini", ".properties": "properties", ".xml": "xml", ".xsd": "xml",
    ".xsl": "xml", ".xslt": "xml", ".graphql": "graphql", ".gql": "graphql",
    ".proto": "protobuf", ".md": "markdown", ".markdown": "markdown", ".rst": "rst",
    ".tf": "hcl", ".tfvars": "hcl", ".hcl": "hcl", ".rego": "rego",
    ".jinja": "jinja", ".jinja2": "jinja", ".njk": "jinja",
}
IGNORE_DIRS = {
    ".git", ".serena", ".venv", "__pycache__", "analysis", "build", "coverage", "dist",
    "node_modules", "vendor", ".next", ".cache",
}
TEXT_LIMIT_BYTES = 2_000_000


@dataclass
class Symbol:
    name: str
    kind: str
    file: str
    line: int
    signature: str
    doc_summary: str = ""
    scope: str = "global"
    language: str = "unknown"


@dataclass
class FileRecord:
    file: str
    language: str
    role: str
    size_bytes: int
    modified_ns: int
    digest: str


@dataclass
class SymbolIndex:
    version: str = SCHEMA_VERSION
    plugin_name: str = "self-assess"
    repo_root: str = "."
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    files_scanned: int = 0
    total_symbols: int = 0
    source_fingerprint: str = ""
    generation_id: str = ""
    symbols: list[Symbol] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def role_for(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    if {"test", "tests", "__tests__", "fixtures"} & parts or name.startswith("test_") or name.endswith("_test.py"):
        return "test"
    if name in {"package.json", "pyproject.toml", "cargo.toml", "go.mod", "composer.json", "gemfile", "pom.xml"}:
        return "manifest"
    if path.suffix.lower() in {".json", ".jsonc", ".json5", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".properties"}:
        return "config"
    if path.suffix.lower() in {".md", ".markdown", ".rst"}:
        return "doc"
    return "source"


def iter_source_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root, dirs, names in os.walk(repo_root):
        dirs[:] = [name for name in dirs if name not in IGNORE_DIRS and not name.startswith(".")]
        for name in names:
            path = Path(root, name)
            if path.suffix.lower() in LANG_EXTENSIONS and path.is_file():
                files.append(path)
    return sorted(files)


def catalog_files(repo_root: Path) -> tuple[list[FileRecord], dict[str, str]]:
    records: list[FileRecord] = []
    contents: dict[str, str] = {}
    for path in iter_source_files(repo_root):
        relative = path.relative_to(repo_root).as_posix()
        try:
            raw = path.read_bytes()
            stat = path.stat()
        except OSError:
            continue
        digest = hashlib.sha256(raw).hexdigest()
        records.append(FileRecord(
            file=relative,
            language=LANG_EXTENSIONS[path.suffix.lower()],
            role=role_for(Path(relative)),
            size_bytes=len(raw),
            modified_ns=stat.st_mtime_ns,
            digest=digest,
        ))
        if len(raw) <= TEXT_LIMIT_BYTES:
            contents[relative] = raw.decode("utf-8", errors="ignore")
    return records, contents


def fingerprint(records: list[FileRecord]) -> str:
    digest = hashlib.sha256()
    for record in records:
        digest.update(f"{record.file}\0{record.digest}\0".encode("utf-8"))
    return digest.hexdigest()


def scan_python_file(path: Path, repo_root: Path, content: str) -> list[Symbol]:
    relative = path.relative_to(repo_root).as_posix()
    try:
        tree = ast.parse(content, filename=relative)
    except SyntaxError:
        return []
    symbols: list[Symbol] = []

    class Visitor(ast.NodeVisitor):
        current_class: str | None = None

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            doc = (ast.get_docstring(node) or "").split("\n", 1)[0][:100]
            symbols.append(Symbol(node.name, "class", relative, node.lineno, f"class {node.name}", doc, "global", "python"))
            previous = self.current_class
            self.current_class = node.name
            self.generic_visit(node)
            self.current_class = previous

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.function(node, False)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            self.function(node, True)

        def function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
            doc = (ast.get_docstring(node) or "").split("\n", 1)[0][:100]
            name = f"{self.current_class}.{node.name}" if self.current_class else node.name
            args = ", ".join(argument.arg for argument in node.args.args)
            prefix = "async def" if is_async else "def"
            symbols.append(Symbol(name, "method" if self.current_class else "function", relative, node.lineno,
                                  f"{prefix} {node.name}({args})", doc, self.current_class or "global", "python"))
            self.generic_visit(node)

    Visitor().visit(tree)
    return symbols


GENERIC_PATTERNS = (
    (r"(?:export\s+)?(?:async\s+)?function\s+([A-Za-z0-9_$]+)", "function"),
    (r"(?:export\s+)?class\s+([A-Za-z0-9_$]+)", "class"),
    (r"\b(?:interface|struct|enum)\s+([A-Za-z0-9_$]+)", "interface"),
    (r"\b(?:fn|func|def)\s+([A-Za-z0-9_$]+)", "function"),
    (r"^(#{1,4})\s+(.+)$", "section"),
)


def scan_generic_file(path: Path, repo_root: Path, content: str, language: str) -> list[Symbol]:
    relative = path.relative_to(repo_root).as_posix()
    symbols: list[Symbol] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        for pattern, kind in GENERIC_PATTERNS:
            match = re.search(pattern, line)
            if match:
                name = match.group(2) if kind == "section" else match.group(1)
                symbols.append(Symbol(name, kind, relative, line_number, line[:120], language=language))
                break
        for flag in re.finditer(r"--([a-z0-9_-]{2,30})", line):
            symbols.append(Symbol(f"--{flag.group(1)}", "cli_flag", relative, line_number, line[:100],
                                  "CLI argument reference", "inline", language))
    return symbols


def build_index(repo_root: Path, plugin_name: str, records: list[FileRecord], contents: dict[str, str], generation_id: str) -> SymbolIndex:
    symbols: list[Symbol] = []
    for record in records:
        path = repo_root / record.file
        content = contents.get(record.file)
        if content is None:
            continue
        if record.language == "python":
            symbols.extend(scan_python_file(path, repo_root, content))
        else:
            symbols.extend(scan_generic_file(path, repo_root, content, record.language))
    unique = {(symbol.name, symbol.file, symbol.line): symbol for symbol in symbols}
    return SymbolIndex(
        plugin_name=plugin_name,
        repo_root=str(repo_root),
        files_scanned=len(records),
        total_symbols=len(unique),
        source_fingerprint=fingerprint(records),
        generation_id=generation_id,
        symbols=list(unique.values()),
    )


def write_fts(path: Path, contents: dict[str, str]) -> bool:
    try:
        connection = sqlite3.connect(path)
        try:
            connection.execute("CREATE VIRTUAL TABLE search USING fts5(path UNINDEXED, line UNINDEXED, content)")
            for file, content in contents.items():
                connection.executemany(
                    "INSERT INTO search(path, line, content) VALUES (?, ?, ?)",
                    ((file, line_number, line) for line_number, line in enumerate(content.splitlines(), start=1) if line.strip()),
                )
            connection.commit()
        finally:
            connection.close()
        return True
    except sqlite3.Error:
        path.unlink(missing_ok=True)
        return False


def query_fts(path: Path, query: str, limit: int) -> list[dict[str, Any]]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        rows = connection.execute(
            "SELECT path, line, snippet(search, 2, '[', ']', '...', 16) FROM search WHERE search MATCH ? LIMIT ?",
            (query, limit),
        ).fetchall()
    finally:
        connection.close()
    return [{"file": file, "line": line, "snippet": snippet} for file, line, snippet in rows]


def artifact_manifest(plugin_name: str, run_id: str, source_fingerprint: str, fts_available: bool, run_dir: Path) -> dict[str, Any]:
    artifacts = [
        {"path": "symbol_index.json", "kind": "symbol_index", "format": "json", "producer": "build_symbol_index"},
        {"path": "file_catalog.json", "kind": "file_catalog", "format": "json", "producer": "build_symbol_index"},
        {"path": "evidence_index.json", "kind": "evidence_index", "format": "json", "producer": "build_symbol_index"},
    ]
    if fts_available:
        artifacts.append({"path": "search.sqlite", "kind": "lexical_index", "format": "sqlite-fts5", "producer": "build_symbol_index"})
    return {
        "version": SCHEMA_VERSION,
        "plugin_name": plugin_name,
        "generation_id": run_id,
        "generated_at": utc_now(),
        "source_fingerprint": source_fingerprint,
        "status": "complete",
        "capabilities": {"fts_available": fts_available},
        "artifacts": artifacts,
    }


class BuildLock:
    def __init__(self, path: Path, wait_seconds: int = LOCK_WAIT_SECONDS, ttl_seconds: int = LOCK_TTL_SECONDS) -> None:
        self.path, self.wait_seconds, self.ttl_seconds = path, wait_seconds, ttl_seconds

    def __enter__(self) -> "BuildLock":
        deadline = time.monotonic() + self.wait_seconds
        payload = {"pid": os.getpid(), "host": socket.gethostname(), "started_at": utc_now(), "expires_at": time.time() + self.ttl_seconds}
        while True:
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    json.dump(payload, handle)
                return self
            except FileExistsError:
                existing = read_json(self.path) or {}
                try:
                    expired = float(existing.get("expires_at", 0)) < time.time()
                    old_enough = time.time() - self.path.stat().st_mtime > self.ttl_seconds
                except FileNotFoundError:
                    continue
                # A competing process creates the lock before it writes the JSON payload.
                # Treat that short-lived malformed state as live, not stale.
                if existing and expired or not existing and old_enough:
                    self.path.unlink(missing_ok=True)
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"timed out waiting for cache lock: {self.path}")
                time.sleep(0.1)

    def __exit__(self, *_: object) -> None:
        self.path.unlink(missing_ok=True)


def current_snapshot(cache_root: Path, plugin_name: str) -> dict[str, Any] | None:
    pointer = read_json(cache_root / "current.json")
    if not pointer or pointer.get("plugin_name") != plugin_name:
        return None
    run_dir = cache_root / "runs" / str(pointer.get("generation_id", ""))
    index = read_json(run_dir / "symbol_index.json")
    if not index or index.get("source_fingerprint") != pointer.get("source_fingerprint"):
        return None
    return pointer


def publish_snapshot(repo_root: Path, plugin_name: str, records: list[FileRecord], contents: dict[str, str], no_fts: bool) -> dict[str, Any]:
    cache_root = repo_root / "analysis" / plugin_name
    runs_dir = cache_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    temporary_dir = Path(tempfile.mkdtemp(prefix=".building-", dir=runs_dir))
    try:
        index = build_index(repo_root, plugin_name, records, contents, run_id)
        atomic_write(temporary_dir / "symbol_index.json", index.to_json())
        atomic_write(temporary_dir / "file_catalog.json", json.dumps({
            "version": SCHEMA_VERSION, "plugin_name": plugin_name, "generation_id": run_id,
            "source_fingerprint": index.source_fingerprint, "files": [asdict(record) for record in records],
        }, indent=2, sort_keys=True) + "\n")
        atomic_write(temporary_dir / "evidence_index.json", json.dumps({
            "version": SCHEMA_VERSION, "plugin_name": plugin_name, "generation_id": run_id,
            "source_fingerprint": index.source_fingerprint, "evidence": [],
        }, indent=2, sort_keys=True) + "\n")
        fts_available = not no_fts and write_fts(temporary_dir / "search.sqlite", contents)
        manifest = artifact_manifest(plugin_name, run_id, index.source_fingerprint, fts_available, temporary_dir)
        atomic_write(temporary_dir / "artifact_manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        final_records, _ = catalog_files(repo_root)
        if fingerprint(final_records) != index.source_fingerprint:
            raise RuntimeError("source changed during snapshot build; retry after edits settle")
        final_dir = runs_dir / run_id
        os.replace(temporary_dir, final_dir)
        pointer = {
            "version": SCHEMA_VERSION, "plugin_name": plugin_name, "generation_id": run_id,
            "source_fingerprint": index.source_fingerprint, "published_at": utc_now(), "status": "complete",
        }
        atomic_write(cache_root / "current.json", json.dumps(pointer, indent=2, sort_keys=True) + "\n")
        atomic_write(cache_root / "symbol_index.json", index.to_json())
        atomic_write(cache_root / "artifact_manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        serena_root = repo_root / ".serena"
        if serena_root.exists():
            atomic_write(serena_root / "cache" / plugin_name / "symbol_index.json", index.to_json())
        return pointer
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise


def build_or_reuse(repo_root: Path, plugin_name: str, no_fts: bool) -> tuple[dict[str, Any], bool]:
    cache_root = repo_root / "analysis" / plugin_name
    cache_root.mkdir(parents=True, exist_ok=True)
    with BuildLock(cache_root / ".symbol-index.lock"):
        records, contents = catalog_files(repo_root)
        source_fingerprint = fingerprint(records)
        current = current_snapshot(cache_root, plugin_name)
        if current and current.get("source_fingerprint") == source_fingerprint:
            return current, True
        pointer = publish_snapshot(repo_root, plugin_name, records, contents, no_fts)
        return pointer, False


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a parallel-safe repository research snapshot")
    parser.add_argument("--repo-path", default=".")
    parser.add_argument("--plugin-name", default="self-assess")
    parser.add_argument("--output", help="Compatibility output path for symbol_index.json")
    parser.add_argument("--no-fts", action="store_true", help="Skip SQLite FTS5 creation")
    parser.add_argument("--query", help="Query the published FTS index instead of building")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    repo_root = Path(args.repo_path).resolve()
    cache_root = repo_root / "analysis" / args.plugin_name
    if args.query:
        current = current_snapshot(cache_root, args.plugin_name)
        if not current:
            raise SystemExit("no valid published snapshot; build the index first")
        database = cache_root / "runs" / current["generation_id"] / "search.sqlite"
        if not database.exists():
            raise SystemExit("FTS is unavailable for the published snapshot")
        print(json.dumps(query_fts(database, args.query, args.limit), indent=2))
        return
    pointer, reused = build_or_reuse(repo_root, args.plugin_name, args.no_fts)
    if args.output:
        source = cache_root / "runs" / pointer["generation_id"] / "symbol_index.json"
        atomic_write(Path(args.output), source.read_text(encoding="utf-8"))
    action = "reused" if reused else "built"
    print(f"[{args.plugin_name}] {action} snapshot {pointer['generation_id']} ({pointer['source_fingerprint'][:12]})")


if __name__ == "__main__":
    main()
