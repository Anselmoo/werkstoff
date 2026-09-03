#!/usr/bin/env python3
"""Behavioural tests for lehre_guard: does it actually DENY, and actually ALLOW.

    python3 plugins/lehre/hooks/test_lehre_guard.py

"The hook exists" and "the hook fires" are different claims, and this repo has
shipped the first while believing the second. Every case here builds a real
temporary repository, feeds a real PreToolUse payload on stdin, and asserts on
the process exit code AND on the stdout JSON shape the runtime requires -- a
deny that omits hookSpecificOutput.hookEventName is discarded by the runtime,
so a guard can deny correctly and still be ignored.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

GUARD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lehre_guard.py")
FAILS: list[str] = []

RULESET = {
    "version": 1,
    "provenance": "lehre",
    "mode": "greenfield",
    "units": [
        {"id": "contracts", "paths": ["src/contracts/*"], "depends_on": [], "reason": "Seams first."},
        {"id": "api", "paths": ["src/api/*"], "depends_on": ["contracts"],
         "reason": "The API is written against a settled contract, never ahead of one."},
    ],
    "rules": [
        {"id": "no-api-to-db", "severity": "blocking", "sourceMode": "scaffolded-default",
         "rationale": "The API layer talks to services, never to the database session directly.",
         "authority": {"source": "Clean Architecture, dependency rule"},
         "check": {"kind": "python-import", "paths": ["src/api/*"], "forbid": ["src.db.*"]}},
        {"id": "no-bare-except", "severity": "blocking", "sourceMode": "scaffolded-default",
         "rationale": "A bare except swallows KeyboardInterrupt and SystemExit.",
         "authority": {"source": "PEP 8, Programming Recommendations"},
         "check": {"kind": "python-construct", "paths": ["*.py"], "forbid": ["bare-except"]}},
        {"id": "no-utils-dumping-ground", "severity": "blocking", "sourceMode": "scaffolded-default",
         "rationale": "A module named utils accretes unrelated code and has no owner.",
         "authority": {"source": "Clean Code, ch.2 Meaningful Names"},
         "check": {"kind": "forbid-path", "paths": ["utils.py", "utils/*"]}},
        {"id": "prefer-logging", "severity": "advisory", "sourceMode": "scaffolded-default",
         "rationale": "print() cannot be levelled, filtered, or redirected.",
         "authority": {"source": "Python logging HOWTO"},
         "check": {"kind": "python-construct", "paths": ["*.py"], "forbid": ["print-call"]}},
    ],
}


def run(cwd, payload, env_extra=None):
    env = dict(os.environ)
    env.pop("LEHRE_DISABLE_GUARD", None)
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run([sys.executable, GUARD], input=json.dumps(payload),
                          capture_output=True, text=True, cwd=cwd, env=env, timeout=30)
    return proc


def make_repo(with_ruleset=True, done_units=()):
    root = tempfile.mkdtemp(prefix="lehre-test-")
    os.makedirs(os.path.join(root, "src", "api"), exist_ok=True)
    os.makedirs(os.path.join(root, "src", "contracts"), exist_ok=True)
    if with_ruleset:
        os.makedirs(os.path.join(root, ".lehre", "units"), exist_ok=True)
        with open(os.path.join(root, ".lehre", "ruleset.json"), "w", encoding="utf-8") as fh:
            json.dump(RULESET, fh)
        for unit in done_units:
            open(os.path.join(root, ".lehre", "units", f"{unit}.done"), "w").close()
    return root


def expect_deny(label, proc, must_mention=None):
    if proc.returncode != 2:
        FAILS.append(f"{label}: expected exit 2, got {proc.returncode}. stderr={proc.stderr[:200]!r}")
        return
    try:
        out = json.loads(proc.stdout)
    except (json.JSONDecodeError, ValueError):
        FAILS.append(f"{label}: stdout is not JSON: {proc.stdout[:200]!r}")
        return
    spec = out.get("hookSpecificOutput", {})
    if spec.get("hookEventName") != "PreToolUse":
        FAILS.append(f"{label}: missing hookSpecificOutput.hookEventName -- runtime would DISCARD this deny")
    if spec.get("permissionDecision") != "deny":
        FAILS.append(f"{label}: permissionDecision != deny")
    if not spec.get("permissionDecisionReason"):
        FAILS.append(f"{label}: no permissionDecisionReason")
    if not proc.stderr.strip():
        FAILS.append(f"{label}: nothing on stderr")
    if must_mention and must_mention not in json.dumps(out):
        FAILS.append(f"{label}: reason does not mention {must_mention!r}")


def expect_allow(label, proc):
    if proc.returncode != 0:
        FAILS.append(f"{label}: expected exit 0, got {proc.returncode}. stderr={proc.stderr[:300]!r}")


def write(path, content):
    return {"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}


# -- INERTNESS: a repo that never opted in is never policed -----------------
bare = make_repo(with_ruleset=False)
expect_allow("inert repo: forbidden import allowed",
             run(bare, write("src/api/h.py", "from src.db.session import get\n")))
expect_allow("inert repo: forbidden path allowed", run(bare, write("utils.py", "x = 1\n")))

# -- ORDER GATE -------------------------------------------------------------
fresh = make_repo()
expect_deny("api before contracts validated",
            run(fresh, write("src/api/h.py", "x = 1\n")), must_mention="contracts")
expect_allow("contracts itself has no unmet dependency",
             run(fresh, write("src/contracts/c.py", "x = 1\n")))
expect_allow("file in no unit is not order-gated",
             run(fresh, write("README.md", "hello")))

ready = make_repo(done_units=["contracts"])
expect_allow("api allowed once contracts validated",
             run(ready, write("src/api/h.py", "x = 1\n")))

# -- RULE GATE --------------------------------------------------------------
expect_deny("layering violation denied",
            run(ready, write("src/api/h.py", "from src.db.session import get\n")),
            must_mention="no-api-to-db")
expect_deny("bare except denied",
            run(ready, write("src/contracts/c.py", "try:\n    pass\nexcept:\n    pass\n")),
            must_mention="no-bare-except")
expect_deny("forbidden path denied",
            run(ready, write("utils.py", "x = 1\n")), must_mention="no-utils-dumping-ground")

# -- ADVISORY RULES MUST NOT BLOCK -----------------------------------------
expect_allow("advisory print() is not a write-time denial",
             run(ready, write("src/contracts/c.py", "print('hi')\n")))

# -- FAIL-CLOSED ------------------------------------------------------------
expect_deny("undeterminable path denied once opted in",
            run(ready, {"tool_name": "Write", "tool_input": {"content": "x = 1\n"}}))
expect_deny("unparseable python denied when a blocking AST rule applies",
            run(ready, write("src/contracts/c.py", "def f(:\n")), must_mention="no-bare-except")
broken = make_repo(done_units=["contracts"])
with open(os.path.join(broken, ".lehre", "ruleset.json"), "w", encoding="utf-8") as fh:
    fh.write("{not json")
expect_deny("malformed ruleset denies rather than degrading to no rules",
            run(broken, write("src/api/h.py", "x = 1\n")))
foreign = make_repo(done_units=["contracts"])
with open(os.path.join(foreign, ".lehre", "ruleset.json"), "w", encoding="utf-8") as fh:
    json.dump({**RULESET, "provenance": "modernize"}, fh)
expect_deny("foreign-provenance ruleset refused",
            run(foreign, write("src/api/h.py", "x = 1\n")))

# -- ESCAPE HATCH -----------------------------------------------------------
expect_allow("named escape hatch works",
             run(ready, write("utils.py", "x = 1\n"), {"LEHRE_DISABLE_GUARD": "1"}))

# -- EDIT / MULTIEDIT reconstruct the WHOLE file, not the fragment ----------
target = os.path.join(ready, "src", "contracts", "existing.py")
with open(target, "w", encoding="utf-8") as fh:
    fh.write("import os\n\n\ndef go():\n    return PLACEHOLDER\n")
expect_deny("edit introducing a bare except denied",
            run(ready, {"tool_name": "Edit", "tool_input": {
                "file_path": "src/contracts/existing.py",
                "old_string": "    return PLACEHOLDER",
                "new_string": "    try:\n        return 1\n    except:\n        return 0"}}),
            must_mention="no-bare-except")
expect_allow("benign edit allowed",
             run(ready, {"tool_name": "Edit", "tool_input": {
                 "file_path": "src/contracts/existing.py",
                 "old_string": "    return PLACEHOLDER",
                 "new_string": "    return 1"}}))
expect_deny("edit whose old_string is absent cannot be reconstructed -> denied",
            run(ready, {"tool_name": "Edit", "tool_input": {
                "file_path": "src/contracts/existing.py",
                "old_string": "NOT PRESENT ANYWHERE",
                "new_string": "x"}}))

api_target = os.path.join(ready, "src", "api", "svc.py")
with open(api_target, "w", encoding="utf-8") as fh:
    fh.write("import src.services.thing\n\nVALUE = 1\n")
expect_deny("multiedit adding a forbidden import denied",
            run(ready, {"tool_name": "MultiEdit", "tool_input": {"edits": [
                {"file_path": "src/api/svc.py", "old_string": "VALUE = 1", "new_string": "VALUE = 2"},
                {"file_path": "src/api/svc.py", "old_string": "import src.services.thing",
                 "new_string": "import src.services.thing\nfrom src.db.session import get"}]}}),
            must_mention="no-api-to-db")

# -- NON-EDIT TOOLS ARE NOT THIS HOOK'S BUSINESS ----------------------------
expect_allow("Read is allowed", run(ready, {"tool_name": "Read", "tool_input": {"file_path": "utils.py"}}))
expect_allow("unreadable stdin is never policed",
             subprocess.run([sys.executable, GUARD], input="not json",
                            capture_output=True, text=True, cwd=ready, timeout=30))

if FAILS:
    print("\n".join(f"  FAIL {f}" for f in FAILS))
    print(f"{len(FAILS)} case(s) failed")
    sys.exit(1)
print("lehre_guard: denies what it must, allows what it must")
