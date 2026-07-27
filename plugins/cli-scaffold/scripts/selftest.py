#!/usr/bin/env python3
"""End-to-end self-test of the cli-scaffold enforcement layer.

Runs the guards and asserts they refuse what they must refuse. Exit 0 = all
enforcement behaves; non-zero = a guard regressed. Intended for CI / a quick
`python3 scripts/selftest.py`.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(args, cwd=None):
    p = subprocess.run([sys.executable] + args, cwd=cwd,
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


FAILURES = []


def expect(cond, msg):
    if not cond:
        FAILURES.append(msg)
        print("  FAIL:", msg)
    else:
        print("  ok:", msg)


def main():
    r = os.path.join(HERE, "lang_router.py")
    ws = os.path.join(HERE, "write_scope.py")
    vs = os.path.join(HERE, "verify_scaffold.py")
    di = os.path.join(HERE, "check_doctrine_isolation.py")

    print("router:")
    code, out, _ = run([r, "rust"])
    expect(code == 0 and json.loads(out)["paradigm"] == "compiled", "rust -> compiled")
    code, _, _ = run([r, "java"])
    expect(code != 0, "unsupported java refused")
    code, _, _ = run([r, "shell"])
    expect(code != 0, "ambiguous 'shell' refused")
    code, out, _ = run([r, "sh"])
    expect(code == 0 and json.loads(out)["paradigm"] == "shell", "posix sh -> shell")

    print("write scope:")
    code, _, _ = run([ws, "../evil"])
    expect(code != 0, "traversal refused")
    code, _, _ = run([ws, "/etc/passwd"])
    expect(code != 0, "absolute path refused")
    code, out, _ = run([ws, "good", "--base", tempfile.gettempdir()])
    expect(code == 0 and out.strip().endswith("/generated-clis/good"), "valid name accepted")

    print("doctrine isolation:")
    code, _, _ = run([di])
    expect(code == 0, "paradigm skills do not duplicate doctrine")

    print("verifier (bad scaffold -> gaps, bounded loop):")
    with tempfile.TemporaryDirectory() as tmp:
        app = os.path.join(tmp, "badapp")
        os.makedirs(os.path.join(app, "src"))
        with open(os.path.join(app, "cli-scaffold.manifest.json"), "w") as fh:
            json.dump({"language": "rust", "app_name": "badapp",
                       "core_files": ["src/lib.rs"], "entry_file": "src/main.rs",
                       "distribution_file": "Cargo.toml", "snapshot_test": None,
                       "flags": [], "positional_args": [], "completion": None}, fh)
        with open(os.path.join(app, "src", "lib.rs"), "w") as fh:
            fh.write("use clap::Parser; pub fn run(){}\n")  # framework import in core
        with open(os.path.join(app, "src", "main.rs"), "w") as fh:
            fh.write("fn main(){}\n")
        reports = os.path.join(tmp, "reports")
        code, out, err = run([vs, app, "rust", "--reports-dir", reports, "--reset-ledger"])
        expect(code == 1, "bad scaffold -> verdict gaps (exit 1)")
        report = json.load(open(out.strip()))
        rules = {f["rule_id"]: f for f in report["findings"]}
        expect(rules["core-library-isolation"]["status"] == "fail",
               "core isolation violation detected")
        expect(rules["core-library-isolation"]["disposition"] == "fixable",
               "isolation violation is fixable")
        # exhaust the bounded loop
        halted = False
        for _ in range(6):
            code, _, err = run([vs, app, "rust", "--reports-dir", reports])
            if "MAX_FIX_ITERATIONS" in err:
                halted = True
                break
        expect(halted, "fix loop halts at MAX_FIX_ITERATIONS")

        print("verifier refuses to write inside the scaffold:")
        code, _, err = run([vs, app, "rust", "--reports-dir", os.path.join(app, "r")])
        expect(code != 0 and "SCOPE VIOLATION" in err, "reports-in-scaffold refused")

    print()
    if FAILURES:
        print("SELFTEST FAILED: %d check(s) regressed" % len(FAILURES))
        return 1
    print("SELFTEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
