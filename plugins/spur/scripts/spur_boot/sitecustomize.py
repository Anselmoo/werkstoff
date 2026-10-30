"""spur's in-process Python adapter, loaded as `sitecustomize` by every traced interpreter.

Not run by hand. `spur_trace.py run` prepends this directory to PYTHONPATH and sets
SPUR_TRACE_DIR; `site` then imports this module before the main script, in the root process
and in every Python child that inherits the environment. That inheritance is the whole
child-process mechanism: nothing is patched, wrapped or rewritten.

What it records, per process, into SPUR_TRACE_DIR/proc-<pid>-<ns>.json:
- calls of the project's OWN functions (code under SPUR_ROOT), aggregated into a
  calling-context tree of (count, cumulative ns), via `sys.monitoring` (3.12+);
- file I/O via `sys.addaudithook`: an input is hashed (sha256) at its first read-open,
  before any in-place rewrite; an output is hashed before each spawn and at exit;
- spawned commands (argv only).

What it never records: environment values (the `env` argument of subprocess.Popen,
os.exec* and os.posix_spawn is dropped on the floor), file contents, or anything under
the interpreter's own prefix, site-packages or __pycache__.

The one rule above the others: the traced program must behave exactly as it would
untraced. noWorkflow rewrote the code it traced, broke the program, and returned exit
0. So every callback here catches its own failure and counts it in `dropped`, which the
report prints; a tracer fault never reaches the traced code.
"""

from __future__ import annotations

import atexit
import hashlib
import importlib.machinery
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
TRACE_ENV = "SPUR_TRACE_DIR"
ROOT_ENV = "SPUR_ROOT"


def _chain_sitecustomize() -> None:
    """Run the sitecustomize this module shadows, if the environment has one.

    Prepending a directory to PYTHONPATH wins the `sitecustomize` import; without this
    the project's own startup hook would silently stop running under the tracer.
    """
    rest = [p for p in sys.path if p and Path(p).resolve() != _HERE]
    spec = importlib.machinery.PathFinder.find_spec("sitecustomize", rest)
    if spec is None or spec.loader is None:
        return
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)


class _Tracer:
    """All per-process state. One instance, created only when SPUR_TRACE_DIR is set."""

    WANTED = frozenset({
        "open", "os.rename", "os.remove", "subprocess.Popen",
        "os.exec", "os.posix_spawn", "os.spawn", "os.system",
    })
    WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

    def __init__(self, out_dir: Path, root: Path) -> None:
        self.out_dir = out_dir
        self.root = root
        self.started_ns = time.time_ns()
        self.pid = os.getpid()
        self.busy = threading.local()
        self.dropped = 0
        self.dropped_why: dict[str, int] = {}
        excluded = {sys.prefix, sys.base_prefix, sys.exec_prefix, str(_HERE.parent), str(out_dir)}
        self.excluded = tuple(str(Path(p).resolve()) for p in excluded if p)
        self.own_cache: dict[object, bool] = {}
        self.inputs: dict[str, dict] = {}
        self.code: dict[str, str | None] = {}
        self.written: dict[str, int] = {}
        self.versions: dict[str, list[dict]] = {}
        self.removed: list[dict] = []
        self.renames: list[dict] = []
        self.spawns: list[dict] = []
        self.threads: dict[int, dict] = {}
        self.stacks: dict[int, list] = {}
        self.exit: dict = {"code": None, "how": "not observed"}
        self.main_file: str | None = None
        self.calls_available = False
        self.flushed = False

    # -- helpers ---------------------------------------------------------------------

    def drop(self, why: str) -> None:
        self.dropped += 1
        self.dropped_why[why] = self.dropped_why.get(why, 0) + 1

    def norm(self, raw) -> str | None:
        if isinstance(raw, bytes):
            raw = os.fsdecode(raw)
        if not isinstance(raw, (str, os.PathLike)):
            return None  # an int fd, or None: nothing nameable to hash
        # normpath collapses `..` lexically. Path.resolve() would follow symlinks and
        # touch the filesystem, which changes what gets recorded for a link.
        return os.path.normpath(Path(raw).absolute())

    def skip(self, path: str) -> bool:
        if path.startswith(("/dev/", "/proc/", "/sys/")):
            return True
        if path.startswith(self.excluded):
            return True
        parts = Path(path).parts
        return "__pycache__" in parts or "site-packages" in parts or ".git" in parts

    def sha256(self, path: str) -> str | None:
        h = hashlib.sha256()
        try:
            with Path(path).open("rb") as fh:
                for block in iter(lambda: fh.read(1 << 20), b""):
                    h.update(block)
        except OSError:
            return None
        return h.hexdigest()

    # -- file I/O (audit hook) -------------------------------------------------------

    def audit(self, event: str, args: tuple) -> None:
        if event not in self.WANTED or getattr(self.busy, "on", False):
            return
        self.busy.on = True
        try:
            self._audit(event, args)
        except Exception as exc:  # a tracer fault must never abort the traced open()
            self.drop(f"audit {event}: {type(exc).__name__}")
        finally:
            self.busy.on = False

    def _audit(self, event: str, args: tuple) -> None:
        if event == "open":
            path = self.norm(args[0])
            if path is None or self.skip(path):
                return
            mode, flags = args[1], args[2] or 0
            if mode is None:  # os.open(): the flags carry the intent
                writes = bool(flags & self.WRITE_FLAGS)
                reads = (flags & (os.O_WRONLY | os.O_RDWR)) != os.O_WRONLY
            else:
                writes = any(c in mode for c in "wax+")
                reads = "r" in mode or ("a" in mode and "+" in mode)
            if reads and path not in self.written and path not in self.inputs and path not in self.code:
                self._record_read(path)
            if writes:
                self.written.setdefault(path, time.time_ns())
        elif event == "os.rename":
            src, dst = self.norm(args[0]), self.norm(args[1])
            if src is None or dst is None:
                return
            self.renames.append({"from": src, "to": dst, "t": time.time_ns()})
            self.written.pop(src, None)
            if not self.skip(dst):
                self.written[dst] = time.time_ns()
        elif event == "os.remove":
            path = self.norm(args[0])
            if path is None or self.skip(path):
                return
            self.written.pop(path, None)
            self.removed.append({"path": path, "t": time.time_ns()})
        else:
            self._record_spawn(event, args)

    def _record_read(self, path: str) -> None:
        p = Path(path)
        try:
            st = p.stat()
        except OSError:
            return  # the open() itself will fail; nothing was read
        if not p.is_file():
            return
        if p.suffix in (".py", ".pyc", ".pyi"):
            # Imports raise `open` for every module. Code is provenance too, but it is
            # not data: it goes in its own list and never into the hash chain.
            self.code[path] = self.sha256(path)
            return
        self.inputs[path] = {"sha256": self.sha256(path), "t": time.time_ns(), "mtime_ns": st.st_mtime_ns}

    def _record_spawn(self, event: str, args: tuple) -> None:
        # Commit outputs BEFORE the child runs, so a child that reads a file this
        # process just wrote is compared against what it actually saw.
        self.commit()
        if event == "subprocess.Popen":
            argv = args[1]
            cwd = args[2]
        elif event == "os.system":
            argv, cwd = args[0], None
        else:  # os.exec / os.posix_spawn / os.spawn: (path, argv, env, ...)
            argv, cwd = (args[1] if len(args) > 1 else args[0]), None
        if isinstance(argv, (str, bytes, os.PathLike)):
            argv = [os.fsdecode(argv)]
            shell = True
        else:
            argv = [os.fsdecode(a) if isinstance(a, (bytes, os.PathLike)) else str(a) for a in argv]
            shell = event == "os.system"
        self.spawns.append({
            "argv": argv, "shell": shell, "via": event, "t": time.time_ns(),
            "cwd": self.norm(cwd) if cwd is not None else str(Path.cwd()),
        })
        if event == "os.exec":
            # exec replaces this process image: atexit will never run.
            self.exit = {"code": None, "how": "replaced by exec"}
            self.flush()

    def commit(self) -> None:
        now = time.time_ns()
        for path in list(self.written):
            if not Path(path).is_file():
                continue
            sha = self.sha256(path)
            seen = self.versions.setdefault(path, [])
            if not seen or seen[-1]["sha256"] != sha:
                seen.append({"sha256": sha, "t": now})

    # -- calls (sys.monitoring) ------------------------------------------------------

    def own(self, code) -> bool:
        hit = self.own_cache.get(code)
        if hit is None:
            fn = code.co_filename
            if fn.startswith("<"):
                hit = False
            else:
                path = os.path.normpath(Path(fn).absolute())
                hit = path.startswith(str(self.root) + os.sep) and not self.skip(path)
            self.own_cache[code] = hit
        return hit

    def node_key(self, code) -> tuple:
        return (code.co_filename, code.co_firstlineno, code.co_qualname)

    def push(self, code, count: bool) -> None:
        tid = threading.get_ident()
        stack = self.stacks.setdefault(tid, [])
        if stack:
            parent = stack[-1][0]
        else:
            parent = self.threads.setdefault(tid, {"children": {}})
        key = self.node_key(code)
        node = parent["children"].get(key)
        if node is None:
            node = parent["children"][key] = {"key": key, "calls": 0, "ns": 0, "children": {}}
        if count:
            node["calls"] += 1
        stack.append((node, time.perf_counter_ns(), code))

    def pop(self, code, exc=None) -> None:
        stack = self.stacks.get(threading.get_ident())
        if not stack:
            return
        now = time.perf_counter_ns()
        # A frame we never saw push (entered before monitoring started) must not
        # unwind the whole stack: pop only if `code` is actually on it.
        if not any(entry[2] is code for entry in stack):
            return
        while stack:
            node, t0, c = stack.pop()
            node["ns"] += now - t0
            if c is code:
                break
        if not stack and code.co_name == "<module>" and code.co_filename == self.main_file:
            if exc is None:
                self.exit = {"code": 0, "how": "returned"}
            elif isinstance(exc, SystemExit):
                c = exc.code
                self.exit = {"code": c if isinstance(c, int) else (0 if c is None else 1), "how": "sys.exit"}
            else:
                self.exit = {"code": 1, "how": f"uncaught {type(exc).__name__}"}

    def install_monitoring(self) -> None:
        mon = getattr(sys, "monitoring", None)
        if mon is None:
            return  # 3.11: calls unavailable, I/O still recorded; the report says which
        tool = next((i for i in (mon.PROFILER_ID, mon.OPTIMIZER_ID, 3, 4) if mon.get_tool(i) is None), None)
        if tool is None:
            self.drop("no free sys.monitoring tool id")
            return
        mon.use_tool_id(tool, "spur")
        ev, disable = mon.events, mon.DISABLE

        def start(code, _off):
            try:
                if not self.own(code):
                    return disable
                self.push(code, count=True)
            except Exception as exc:
                self.drop(f"PY_START: {type(exc).__name__}")
            return None

        def resume(code, _off):
            try:
                if not self.own(code):
                    return disable
                self.push(code, count=False)
            except Exception as exc:
                self.drop(f"PY_RESUME: {type(exc).__name__}")
            return None

        def ret(code, _off, _val):
            try:
                if not self.own(code):
                    return disable
                self.pop(code)
            except Exception as exc:
                self.drop(f"PY_RETURN: {type(exc).__name__}")
            return None

        def unwind(code, _off, exc):
            # PY_UNWIND is not a local event: it is never disabled, only ignored.
            try:
                if self.own(code):
                    self.pop(code, exc)
            except Exception as err:
                self.drop(f"PY_UNWIND: {type(err).__name__}")

        def throw(code, _off, _exc):
            try:
                if self.own(code):
                    self.push(code, count=False)
            except Exception as err:
                self.drop(f"PY_THROW: {type(err).__name__}")

        mon.register_callback(tool, ev.PY_START, start)
        mon.register_callback(tool, ev.PY_RESUME, resume)
        mon.register_callback(tool, ev.PY_RETURN, ret)
        mon.register_callback(tool, ev.PY_YIELD, ret)
        mon.register_callback(tool, ev.PY_UNWIND, unwind)
        mon.register_callback(tool, ev.PY_THROW, throw)
        mon.set_events(tool, ev.PY_START | ev.PY_RESUME | ev.PY_RETURN | ev.PY_YIELD | ev.PY_UNWIND | ev.PY_THROW)
        self.calls_available = True

    # -- output ----------------------------------------------------------------------

    def tree(self, node: dict) -> list:
        out = []
        for child in node["children"].values():
            fn, line, qual = child["key"]
            out.append({
                "fn": qual, "file": fn, "line": line, "calls": child["calls"],
                "ns": child["ns"], "children": self.tree(child),
            })
        return out

    def flush(self) -> None:
        if self.flushed or os.getpid() != self.pid:
            return
        self.busy.on = True
        try:
            self.commit()
            # Frames still open at exit (daemon threads, os._exit paths) close at now.
            now = time.perf_counter_ns()
            for stack in self.stacks.values():
                for node, t0, _c in stack:
                    node["ns"] += now - t0
            record = {
                "schema": "spur/proc/1",
                "pid": self.pid, "ppid": os.getppid(),
                # orig_argv[0] can be a framework binary (macOS); the interpreter a
                # reader would type is sys.executable.
                "argv": [sys.executable or "python", *list(getattr(sys, "orig_argv", sys.argv))[1:]],
                "cwd": str(Path.cwd()), "python": sys.version.split()[0],
                "startedNs": self.started_ns, "endedNs": time.time_ns(),
                "callsAvailable": self.calls_available,
                "threads": [self.tree(t) for t in self.threads.values()],
                "inputs": self.inputs, "code": self.code,
                "outputs": self.versions, "removed": self.removed, "renames": self.renames,
                "spawns": self.spawns, "exit": self.exit,
                "dropped": self.dropped, "droppedWhy": self.dropped_why,
            }
            name = f"proc-{self.pid}-{self.started_ns}.json"
            tmp = self.out_dir / (name + ".part")
            tmp.write_text(json.dumps(record), encoding="utf-8")
            tmp.replace(self.out_dir / name)
            self.flushed = True
        except Exception as exc:
            # Nothing to count into any more: the record is what failed. Say so on
            # stderr, once, and let the program's own exit status stand.
            sys.stderr.write(f"spur: could not write trace for pid {self.pid}: {exc}\n")
        finally:
            self.busy.on = False

    def after_fork(self) -> None:
        """A forked child inherits this object; it is a new process with its own record."""
        self.__init__(self.out_dir, self.root)
        self.main_file = None


def _install() -> None:
    out = os.environ.get(TRACE_ENV)
    if not out:
        return
    root = os.environ.get(ROOT_ENV) or str(Path.cwd())
    tracer = _Tracer(Path(out), Path(os.path.normpath(Path(root).absolute())))
    main = sys.argv[0] if sys.argv and sys.argv[0] not in ("", "-c", "-m") else None
    if main:
        tracer.main_file = os.path.normpath(Path(main).absolute())
    sys.addaudithook(tracer.audit)
    tracer.install_monitoring()
    atexit.register(tracer.flush)
    os.register_at_fork(after_in_child=tracer.after_fork)


_install()
_chain_sitecustomize()
