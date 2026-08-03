#!/usr/bin/env python3
"""End-to-end self-test of the cli-scaffold enforcement layer.

Runs the guards and asserts they refuse what they must refuse. Exit 0 = all
enforcement behaves; non-zero = a guard regressed. Intended for CI / a quick
`python3 scripts/selftest.py`.
"""
import json
import os
import re
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
    bat = os.path.join(HERE, "build_architecture_tree.py")

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

    print("architecture tree — --tokens flag:")
    with tempfile.TemporaryDirectory() as tmp:
        scaffold = os.path.join(tmp, "tinyapp")
        os.makedirs(scaffold)
        with open(os.path.join(scaffold, "cli-scaffold.manifest.json"), "w") as fh:
            json.dump({
                "app_name": "tinyapp", "language": "python",
                "core_files": ["core.py"], "entry_file": "cli.py",
                "distribution_file": "pyproject.toml", "snapshot_test": None,
                "help_file": None, "completion": None,
            }, fh)
        open(os.path.join(scaffold, "core.py"), "w").close()
        open(os.path.join(scaffold, "cli.py"), "w").close()
        open(os.path.join(scaffold, "pyproject.toml"), "w").close()

        template = os.path.join(tmp, "template.html")
        with open(template, "w") as fh:
            fh.write(
                "<html><head><style>/*__TOKENS__*/</style></head>"
                "<body><!--__D3_SUBSET__-->"
                '<script type="module">const DATA = /*__TREE_DATA__*/ null;</script>'
                "</body></html>"
            )
        d3_stub = os.path.join(tmp, "d3.html")
        with open(d3_stub, "w") as fh:
            fh.write("<script>window.d3 = {};</script>")
        tokens_stub = os.path.join(tmp, "tokens.css")
        with open(tokens_stub, "w") as fh:
            fh.write(":root { --status-good: #4c8d5a; }")

        out = os.path.join(tmp, "ARCHITECTURE.html")
        code, stdout, stderr = run([bat, scaffold, "--template", template,
                                     "--d3", d3_stub, "--tokens", tokens_stub,
                                     "--out", out])
        expect(code == 0, "build succeeds with --tokens supplied: " + stderr.strip())
        rendered = open(out).read() if os.path.exists(out) else ""
        expect("--status-good: #4c8d5a" in rendered, "tokens.css content injected")
        expect("/*__TOKENS__*/" not in rendered, "tokens marker fully replaced")

        code, _, err = run([bat, scaffold, "--template", template,
                             "--d3", d3_stub, "--out", out])
        expect(code != 0, "--tokens is required")

    print("architecture tree — token migration:")
    ASSETS = os.path.join(HERE, "..", "assets")
    with tempfile.TemporaryDirectory() as tmp:
        scaffold = os.path.join(tmp, "tinyapp2")
        os.makedirs(scaffold)
        with open(os.path.join(scaffold, "cli-scaffold.manifest.json"), "w") as fh:
            json.dump({
                "app_name": "tinyapp2", "language": "python",
                "core_files": ["core.py"], "entry_file": "cli.py",
                "distribution_file": "pyproject.toml", "snapshot_test": None,
                "help_file": None, "completion": None,
            }, fh)
        open(os.path.join(scaffold, "core.py"), "w").close()
        open(os.path.join(scaffold, "cli.py"), "w").close()
        open(os.path.join(scaffold, "pyproject.toml"), "w").close()

        out = os.path.join(tmp, "ARCHITECTURE.html")
        code, _, err = run([bat, scaffold,
                             "--template", os.path.join(ASSETS, "architecture-tree-viewer.html"),
                             "--d3", os.path.join(ASSETS, "inline-d3.html"),
                             "--tokens", os.path.join(ASSETS, "tokens.css"),
                             "--out", out])
        expect(code == 0, "build succeeds against the real viewer template: " + err.strip())
        rendered = open(out).read() if os.path.exists(out) else ""
        expect(rendered.count("--status-good: #4c8d5a") == 1,
               "shared tokens.css injected exactly once")
        expect(rendered.count("--bg: #1e1e1e") == 1,
               "--bg no longer hand-duplicated in the viewer's own <style> block")
        expect("--role-core: #4c8d5a" in rendered,
               "viewer-local role colors preserved (no shared equivalent to migrate to)")

    print("architecture tree — indented tree rebuild:")
    with tempfile.TemporaryDirectory() as tmp:
        scaffold = os.path.join(tmp, "tinyapp3")
        os.makedirs(scaffold)
        with open(os.path.join(scaffold, "cli-scaffold.manifest.json"), "w") as fh:
            json.dump({
                "app_name": "tinyapp3", "language": "python",
                "core_files": ["core.py"], "entry_file": "cli.py",
                "distribution_file": "pyproject.toml", "snapshot_test": None,
                "help_file": None, "completion": None,
            }, fh)
        open(os.path.join(scaffold, "core.py"), "w").close()
        open(os.path.join(scaffold, "cli.py"), "w").close()
        open(os.path.join(scaffold, "pyproject.toml"), "w").close()

        out = os.path.join(tmp, "ARCHITECTURE.html")
        code, _, err = run([bat, scaffold,
                             "--template", os.path.join(ASSETS, "architecture-tree-viewer.html"),
                             "--d3", os.path.join(ASSETS, "inline-d3.html"),
                             "--tokens", os.path.join(ASSETS, "tokens.css"),
                             "--out", out])
        expect(code == 0, "build succeeds after the mark rebuild: " + err.strip())
        rendered = open(out).read() if os.path.exists(out) else ""
        expect("d3.pack(" not in rendered, "circle-pack layout removed")
        expect("d3.zoom(" not in rendered, "zoom/pan canvas removed")
        expect('id="sidebar"' not in rendered, "click-through sidebar removed")
        expect('id="search"' not in rendered,
               "search box removed (native Cmd/Ctrl+F works on real DOM rows instead)")
        expect('"tree-row"' in rendered, "indented tree rows present")
        expect('"guide"' in rendered, "d3-hierarchy-driven guide lines present")
        expect('"badge"' in rendered, "inline role badges present")

        m = re.search(r'<script type="module">(.*?)</script>', rendered, re.S)
        expect(m is not None, "module script block present")
        if m:
            proc = subprocess.run(["node", "--check", "/dev/stdin"],
                                   input=m.group(1), text=True, capture_output=True)
            expect(proc.returncode == 0,
                   "rendered script has valid JS syntax: " + proc.stderr.strip())

    print("architecture tree — nested directory row order "
          "(regression: pre-order eachBefore, not breadth-first descendants):")
    with tempfile.TemporaryDirectory() as tmp:
        scaffold = os.path.join(tmp, "tinyapp4")
        os.makedirs(os.path.join(scaffold, "src"))
        with open(os.path.join(scaffold, "cli-scaffold.manifest.json"), "w") as fh:
            json.dump({
                "app_name": "tinyapp4", "language": "python",
                "core_files": ["src/core.py"], "entry_file": "cli.py",
                "distribution_file": "pyproject.toml", "snapshot_test": None,
                "help_file": None, "completion": None,
            }, fh)
        open(os.path.join(scaffold, "src", "core.py"), "w").close()
        open(os.path.join(scaffold, "cli.py"), "w").close()
        open(os.path.join(scaffold, "pyproject.toml"), "w").close()
        # Sorts AFTER "src" alphabetically -- a breadth-first bug puts this
        # row before src's own child row; pre-order must not.
        open(os.path.join(scaffold, "zz_after.py"), "w").close()

        out = os.path.join(tmp, "ARCHITECTURE.html")
        code, _, err = run([bat, scaffold,
                             "--template", os.path.join(ASSETS, "architecture-tree-viewer.html"),
                             "--d3", os.path.join(ASSETS, "inline-d3.html"),
                             "--tokens", os.path.join(ASSETS, "tokens.css"),
                             "--out", out])
        expect(code == 0, "build succeeds with a nested subdirectory: " + err.strip())
        rendered = open(out).read() if os.path.exists(out) else ""

        data_m = re.search(r'/\*__TREE_DATA__\*/\s*(\{.*?\})\s*;', rendered, re.S)
        script_m = re.search(r'<script type="module">(.*?)</script>', rendered, re.S)
        expect(data_m is not None, "tree DATA payload present in rendered output")
        expect(script_m is not None, "module script block present")

        if data_m and script_m:
            # Run the LITERAL row-layout lines from the rendered script (not
            # a reimplementation) against the real vendored d3 bundle, so a
            # regression back to `.descendants().filter(...)` in the source
            # is caught by executing the real shipped code, not by an
            # independent Python model of what it should do.
            script = script_m.group(1)
            start_anchor = "const root = d3.hierarchy(DATA.tree, d => d.children);"
            end_anchor = "rows.forEach((d, i) => { d.rowIndex = i; });"
            has_anchors = start_anchor in script and end_anchor in script
            expect(has_anchors, "row-layout lines found in rendered script (anchors intact)")

            if has_anchors:
                start = script.index(start_anchor)
                end = script.index(end_anchor) + len(end_anchor)
                layout_snippet = script[start:end]

                d3_src = open(os.path.join(ASSETS, "inline-d3.html")).read()
                d3_src = d3_src.replace("<script>", "", 1)
                d3_src = d3_src[:d3_src.rfind("</script>")]

                harness = (
                    d3_src + "\n"
                    "const DATA = " + data_m.group(1) + ";\n"
                    + layout_snippet + "\n"
                    "console.log(JSON.stringify(rows.map(d => "
                    "({ path: d.data.name, depth: d.depth, rowIndex: d.rowIndex }))));\n"
                )
                proc = subprocess.run(["node", "-e", harness], capture_output=True, text=True)
                expect(proc.returncode == 0,
                       "row-layout harness executes against the real vendored d3: " + proc.stderr.strip())
                if proc.returncode == 0:
                    rows_out = json.loads(proc.stdout.strip().splitlines()[-1])
                    by_name = {r["path"]: r for r in rows_out}
                    present = "src" in by_name and "core.py" in by_name and "zz_after.py" in by_name
                    expect(present, "fixture nodes present in computed rows")
                    if present:
                        expect(by_name["core.py"]["rowIndex"] == by_name["src"]["rowIndex"] + 1,
                               "nested child renders immediately after its parent directory "
                               "(pre-order, not breadth-first)")
                        expect(by_name["zz_after.py"]["rowIndex"] > by_name["core.py"]["rowIndex"],
                               "a later top-level sibling still renders after the nested child")

    print()
    if FAILURES:
        print("SELFTEST FAILED: %d check(s) regressed" % len(FAILURES))
        return 1
    print("SELFTEST PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
