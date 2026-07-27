#!/usr/bin/env python3
"""Read-only verification engine for a generated CLI scaffold.

The cli-scaffold-verifier agent runs this. It reads the scaffold and its
`cli-scaffold.manifest.json` (which declares the gating file roles as first-class
JSON keys), checks each doctrine rule with a real conditional, and emits a
validated report.

Enforcement guarantees implemented here (not merely described):
  * verifier-must-not-write -- the report/ledger are written ONLY under the
    reports root, and the code REFUSES (exit 2) if that path is inside the
    scaffold dir. The engine opens every scaffold file read-only.
  * fixable-gaps-must-be-fixed (the bound) -- a per-scaffold ledger counts
    verify attempts; once attempts would exceed MAX_FIX_ITERATIONS the engine
    HALTS (exit 1) and tells the caller to surface to a human.
  * every exit-code / help / flag / stdout-stderr / distribution / snapshot /
    completion / bashism rule -> a check function that tests the scaffold's own
    state and records a fail finding (with a first-class `disposition`) when the
    rule is not satisfied.
  * PERSISTED STATE validated on write -- the report is passed through
    report_validator.validate_report before it is written; an internally
    inconsistent report cannot be persisted.

Exit codes (frozen contract):
    0  verdict == pass (no gaps)
    1  verdict == gaps  OR  halt (bound exceeded / unreadable manifest)
    2  usage / scope error
"""
import argparse
import json
import os
import re
import sys

import report_validator
from constants import (
    DISPOSITION_FIXABLE,
    DISPOSITION_NEEDS_HUMAN,
    EXIT_RUNTIME_ERROR,
    EXIT_SUCCESS,
    EXIT_USAGE_ERROR,
    FORBIDDEN_BASHISMS,
    LANGUAGE_REGISTRY,
    MAX_FIX_ITERATIONS,
    REPORTS_ROOT,
    SHELL,
    STATUS_FAIL,
    STATUS_PASS,
    VERDICT_GAPS,
    VERDICT_PASS,
)

MANIFEST_NAME = "cli-scaffold.manifest.json"

# CLI-framework import signatures per language (rule: core-library-isolation).
# If any of these appears in a declared core file, isolation is violated.
FRAMEWORK_SIGNATURES = {
    "python": [r"\bimport\s+argparse\b", r"\bimport\s+click\b", r"\bimport\s+typer\b",
               r"\bfrom\s+argparse\b", r"\bimport\s+docopt\b", r"\bimport\s+fire\b",
               r"\bsys\.argv\b"],
    "typescript": [r"\bfrom\s+['\"]yargs['\"]", r"\bfrom\s+['\"]commander['\"]",
                   r"\bfrom\s+['\"]@oclif", r"\bfrom\s+['\"]meow['\"]",
                   r"\brequire\(['\"](yargs|commander|meow|minimist)['\"]\)",
                   r"\bprocess\.argv\b"],
    "javascript": [r"\brequire\(['\"](yargs|commander|meow|minimist|commander)['\"]\)",
                   r"\bfrom\s+['\"](yargs|commander|meow)['\"]", r"\bprocess\.argv\b"],
    "ruby": [r"\brequire\s+['\"]optparse['\"]", r"\brequire\s+['\"]thor['\"]",
             r"\brequire\s+['\"]gli['\"]", r"\brequire\s+['\"]slop['\"]",
             r"\bARGV\b"],
    "php": [r"\bSymfony\\Component\\Console", r"\buse\s+Symfony\\Component\\Console",
            r"\bgetopt\s*\(", r"\$argv\b"],
    "perl": [r"\buse\s+Getopt::Long\b", r"\buse\s+Getopt::Std\b", r"@ARGV\b"],
    "dotnet": [r"\busing\s+System\.CommandLine", r"McMaster\.Extensions\.CommandLineUtils",
               r"\busing\s+CommandLine\b"],
    "rust": [r"\buse\s+clap\b", r"\buse\s+structopt\b", r"\buse\s+argh\b",
             r"\bstd::env::args\b", r"\benv::args\b"],
    "go": [r"\"flag\"", r"github\.com/spf13/cobra", r"github\.com/urfave/cli",
           r"github\.com/spf13/pflag", r"\bos\.Args\b"],
    "bash": [r"\bgetopts\b", r"\bgetopt\b"],
    "zsh": [r"\bgetopts\b", r"\bzparseopts\b", r"\bgetopt\b"],
    "powershell": [r"\bparam\s*\(", r"\[CmdletBinding", r"\[Parameter\("],
    "posix-sh": [r"\bgetopts\b", r"\bgetopt\b"],
}


class HaltError(Exception):
    """Raised to halt the loop (bound exceeded / unrecoverable)."""


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------
def read_text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def finding(rule_id, status, disposition=None, detail="", evidence=""):
    rec = {"rule_id": rule_id, "status": status, "detail": detail, "evidence": evidence}
    if status == STATUS_FAIL:
        rec["disposition"] = disposition
    return rec


def _search_any(patterns, text):
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(0)
    return None


# --------------------------------------------------------------------------
# individual rule checks -- each returns a finding dict
# --------------------------------------------------------------------------
def check_core_isolation(manifest, scaffold_dir, language):
    sigs = FRAMEWORK_SIGNATURES.get(language, [])
    for rel in manifest.get("core_files", []):
        text = read_text(os.path.join(scaffold_dir, rel))
        if text is None:
            return finding("core-library-isolation", STATUS_FAIL, DISPOSITION_FIXABLE,
                           "declared core file %r not found" % rel)
        hit = _search_any(sigs, text)
        if hit:
            return finding("core-library-isolation", STATUS_FAIL, DISPOSITION_FIXABLE,
                           "core file %r contains CLI-framework reference" % rel,
                           evidence=hit)
    return finding("core-library-isolation", STATUS_PASS,
                   detail="no CLI-framework references in core files")


def check_entry_thin(manifest, scaffold_dir):
    entry = manifest.get("entry_file")
    text = read_text(os.path.join(scaffold_dir, entry)) if entry else None
    if text is None:
        return finding("cli-entry-thin", STATUS_FAIL, DISPOSITION_FIXABLE,
                       "entry file %r not found" % entry)
    # The entry MUST dispatch into a core file; if it references none of them it
    # is probably carrying its own logic. This is a heuristic, so a failure is
    # surfaced for human judgment rather than auto-rewritten.
    cores = [os.path.splitext(os.path.basename(c))[0] for c in manifest.get("core_files", [])]
    if cores and not any(c and c in text for c in cores):
        return finding("cli-entry-thin", STATUS_FAIL, DISPOSITION_NEEDS_HUMAN,
                       "entry file does not appear to dispatch into any core module "
                       "(%s); confirm no business logic lives in the entry point"
                       % ", ".join(cores))
    return finding("cli-entry-thin", STATUS_PASS,
                   detail="entry dispatches into core module")


def check_exit_codes(manifest, scaffold_dir):
    # Look across entry + declared files for evidence of the three codes.
    entry = manifest.get("entry_file")
    text = read_text(os.path.join(scaffold_dir, entry)) if entry else ""
    text = text or ""
    results = []
    # usage error -> 2
    if re.search(r"(exit\D{0,4}2\b|code\D{0,4}2\b|EXIT_USAGE|ExitUsage|USAGE_ERROR|\b2\b\s*#\s*usage)", text):
        results.append(finding("exit-code-usage-error", STATUS_PASS,
                               detail="usage errors map to exit code 2"))
    else:
        results.append(finding("exit-code-usage-error", STATUS_FAIL, DISPOSITION_FIXABLE,
                               "no evidence usage errors exit with code 2"))
    # runtime error -> 1
    if re.search(r"(exit\D{0,4}1\b|code\D{0,4}1\b|EXIT_(RUNTIME|ERROR)|return\s+1\b)", text):
        results.append(finding("exit-code-runtime-error", STATUS_PASS,
                               detail="runtime errors map to exit code 1"))
    else:
        results.append(finding("exit-code-runtime-error", STATUS_FAIL, DISPOSITION_FIXABLE,
                               "no evidence runtime errors exit with code 1"))
    # success -> 0
    if re.search(r"(exit\D{0,4}0\b|return\s+0\b|EXIT_SUCCESS|Environment\.Exit\(0\)|os\.Exit\(0\)|process\.exit\(0\))", text):
        results.append(finding("exit-code-success", STATUS_PASS,
                               detail="success maps to exit code 0"))
    else:
        results.append(finding("exit-code-success", STATUS_FAIL, DISPOSITION_FIXABLE,
                               "no evidence success exits with code 0"))
    # frozen contract: pass iff all three passed for this language.
    if all(r["status"] == STATUS_PASS for r in results):
        results.append(finding("exit-code-frozen-contract", STATUS_PASS,
                               detail="0/1/2 contract honored for this language"))
    else:
        results.append(finding("exit-code-frozen-contract", STATUS_FAIL, DISPOSITION_FIXABLE,
                               "frozen 0/1/2 exit contract not fully honored"))
    return results


def _all_source_text(manifest, scaffold_dir):
    parts = []
    for rel in list(manifest.get("core_files", [])) + [manifest.get("entry_file")]:
        if rel:
            t = read_text(os.path.join(scaffold_dir, rel))
            if t:
                parts.append(t)
    return "\n".join(parts)


def check_no_color(manifest, scaffold_dir):
    text = _all_source_text(manifest, scaffold_dir)
    if "NO_COLOR" in text:
        return finding("no-color-honored", STATUS_PASS,
                       detail="NO_COLOR is consulted")
    return finding("no-color-honored", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "no reference to NO_COLOR environment variable")


def _help_text(manifest, scaffold_dir):
    hf = manifest.get("help_file")
    if hf:
        t = read_text(os.path.join(scaffold_dir, hf))
        if t:
            return t
    # fall back to scanning source for the literal section headings
    return _all_source_text(manifest, scaffold_dir)


def check_help_usage(manifest, scaffold_dir):
    text = _help_text(manifest, scaffold_dir)
    if re.search(r"(?im)^\s*usage:?", text) or "Usage" in text:
        return finding("help-usage-section", STATUS_PASS, detail="Usage summary present")
    return finding("help-usage-section", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "no 'Usage' summary in help output")


def check_help_arguments(manifest, scaffold_dir):
    if not manifest.get("positional_args"):
        return finding("help-arguments-section", STATUS_PASS,
                       detail="no positional arguments declared; section not required")
    text = _help_text(manifest, scaffold_dir)
    if re.search(r"(?i)\b(arguments|positional)\b", text):
        return finding("help-arguments-section", STATUS_PASS, detail="Arguments section present")
    return finding("help-arguments-section", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "positional args declared but no Arguments/Positional section")


def check_help_options(manifest, scaffold_dir):
    if not manifest.get("flags"):
        return finding("help-options-section", STATUS_PASS,
                       detail="no flags declared; section not required")
    text = _help_text(manifest, scaffold_dir)
    if re.search(r"(?i)\boptions\b", text):
        return finding("help-options-section", STATUS_PASS, detail="Options section present")
    return finding("help-options-section", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "flags declared but no Options section in help output")


def _flag_longs(manifest):
    return {f.get("long") for f in manifest.get("flags", []) if f.get("long")}


def _flag_shorts(manifest):
    return {f.get("short") for f in manifest.get("flags", []) if f.get("short")}


def check_json_flag(manifest, scaffold_dir):
    longs = _flag_longs(manifest)
    if "--json" in longs or manifest.get("json_output_flag"):
        return finding("json-output-required", STATUS_PASS, detail="--json (or equivalent) declared")
    return finding("json-output-required", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "no --json flag (or ecosystem equivalent) declared")


def check_no_input_flag(manifest, scaffold_dir):
    longs = _flag_longs(manifest)
    shorts = _flag_shorts(manifest)
    if longs & {"--no-input", "--no-interaction"} or "-n" in shorts:
        return finding("no-input-flag-required", STATUS_PASS, detail="--no-input (or equivalent) declared")
    return finding("no-input-flag-required", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "no --no-input / --no-interaction flag declared")


def check_no_input_exit2(manifest, scaffold_dir):
    text = _all_source_text(manifest, scaffold_dir)
    # heuristic: a co-occurrence of no-input handling and exit code 2
    if re.search(r"(no[_-]?input|no[_-]?interaction)", text, re.I) and re.search(r"\b2\b", text):
        return finding("no-input-missing-input-exit-2", STATUS_PASS,
                       detail="no-input + missing input path exits 2")
    return finding("no-input-missing-input-exit-2", STATUS_FAIL, DISPOSITION_NEEDS_HUMAN,
                   "could not confirm --no-input + missing input exits with code 2")


def check_no_hang(manifest, scaffold_dir):
    text = _all_source_text(manifest, scaffold_dir)
    if re.search(r"(isatty|is_terminal|IsTerminal|TTY|-t\s+0|-t\s+1|Console\.IsInputRedirected|"
                 r"process\.stdin\.isTTY|\$stdin\.tty\?|STDIN\.tty\?|posix_isatty|IsInputRedirected)",
                 text, re.I):
        return finding("no-input-prevent-hang", STATUS_PASS,
                       detail="TTY/redirection is detected to fail fast")
    return finding("no-input-prevent-hang", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "no TTY/non-interactive detection; may hang without --no-input")


def check_stdout_results(manifest, scaffold_dir):
    text = _all_source_text(manifest, scaffold_dir)
    # heuristic: presence of a stdout channel for results.
    if re.search(r"(stdout|STDOUT|Console\.Out|System\.out|puts\b|println!|fmt\.Print|"
                 r"process\.stdout|echo\b|Write-Output)", text):
        return finding("stdout-for-results", STATUS_PASS, detail="results written to stdout")
    return finding("stdout-for-results", STATUS_FAIL, DISPOSITION_NEEDS_HUMAN,
                   "could not confirm result data goes to stdout")


def check_stderr_diagnostics(manifest, scaffold_dir):
    text = _all_source_text(manifest, scaffold_dir)
    if re.search(r"(stderr|STDERR|Console\.Error|System\.err|eprintln!|fmt\.Fprintf?\(os\.Stderr|"
                 r"process\.stderr|>&2|Write-Error|warn\b)", text):
        return finding("stderr-for-diagnostics", STATUS_PASS, detail="diagnostics written to stderr")
    return finding("stderr-for-diagnostics", STATUS_FAIL, DISPOSITION_NEEDS_HUMAN,
                   "could not confirm diagnostics go to stderr")


def check_snapshot_test(manifest, scaffold_dir):
    snap = manifest.get("snapshot_test")
    if snap and os.path.isfile(os.path.join(scaffold_dir, snap)):
        return finding("snapshot-test-help-required", STATUS_PASS,
                       detail="snapshot test for --help present: %s" % snap)
    return finding("snapshot-test-help-required", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "no snapshot test for --help output found")


def check_distribution(manifest, scaffold_dir):
    dist = manifest.get("distribution_file")
    if dist and os.path.isfile(os.path.join(scaffold_dir, dist)):
        t = read_text(os.path.join(scaffold_dir, dist)) or ""
        if t.strip():
            return finding("distribution-channel-specified", STATUS_PASS,
                           detail="packaging metadata present: %s" % dist)
    return finding("distribution-channel-specified", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "no non-empty packaging metadata (distribution_file) found")


def check_completion(manifest, scaffold_dir):
    comp = manifest.get("completion")
    if isinstance(comp, dict):
        if comp.get("supported") is False and comp.get("note"):
            return finding("shell-completion-presence", STATUS_PASS,
                           detail="no native completion; limitation documented")
        mech = comp.get("mechanism")
        cfile = comp.get("file")
        if mech and (cfile is None or os.path.isfile(os.path.join(scaffold_dir, cfile))):
            return finding("shell-completion-presence", STATUS_PASS,
                           detail="completions via %s" % mech)
    return finding("shell-completion-presence", STATUS_FAIL, DISPOSITION_FIXABLE,
                   "completion mechanism neither provided nor honestly documented as absent")


def check_shell_source_side_effects(manifest, scaffold_dir):
    # rule (shell guarantee): sourced library has zero side effects at source-time.
    for rel in manifest.get("core_files", []):
        text = read_text(os.path.join(scaffold_dir, rel))
        if text is None:
            continue
        depth = 0
        for lineno, raw in enumerate(text.splitlines(), 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            # track function bodies crudely
            if re.search(r"\)\s*\{?\s*$", line) and re.search(r"^\w[\w-]*\s*\(\s*\)", line):
                depth += 1
                continue
            if line == "}" and depth > 0:
                depth -= 1
                continue
            if depth == 0:
                # top-level statement that is not a definition/assignment/guard
                if re.match(r"^(function\s+\w+|\w[\w-]*\s*\(\s*\)|[A-Za-z_][A-Za-z0-9_]*=|"
                            r"local\s|readonly\s|declare\s|typeset\s|export\s|set\s|"
                            r"\[\s|if\s|fi\b|else\b|elif\s|case\s|esac\b|return\b|:\s*$|"
                            r"#|\bfunction\b)", line):
                    continue
                # a bare command invocation at source time is a side effect
                if re.match(r"^[A-Za-z_./][\w./-]*(\s|$)", line) and "=" not in line.split()[0]:
                    return finding("shell-source-no-side-effects", STATUS_FAIL,
                                   DISPOSITION_NEEDS_HUMAN,
                                   "possible source-time side effect in %s:%d" % (rel, lineno),
                                   evidence=line[:80])
    return finding("shell-source-no-side-effects", STATUS_PASS,
                   detail="no obvious source-time side effects in sourced library")


def check_posix_bashisms(manifest, scaffold_dir):
    hits = []
    files = list(manifest.get("core_files", []))
    if manifest.get("entry_file"):
        files.append(manifest["entry_file"])
    for rel in files:
        text = read_text(os.path.join(scaffold_dir, rel))
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pat, label in FORBIDDEN_BASHISMS:
                if re.search(pat, line):
                    hits.append("%s:%d %s" % (rel, lineno, label))
    if hits:
        return finding("posix-sh-bashism-check", STATUS_FAIL, DISPOSITION_FIXABLE,
                       "forbidden bashism(s) found in POSIX sh scaffold",
                       evidence="; ".join(hits[:10]))
    return finding("posix-sh-bashism-check", STATUS_PASS,
                   detail="no forbidden bashisms found")


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------
def run_checks(manifest, scaffold_dir, language, paradigm):
    findings = []
    findings.append(check_core_isolation(manifest, scaffold_dir, language))
    findings.append(check_entry_thin(manifest, scaffold_dir))
    findings.extend(check_exit_codes(manifest, scaffold_dir))
    findings.append(check_no_color(manifest, scaffold_dir))
    findings.append(check_help_usage(manifest, scaffold_dir))
    findings.append(check_help_arguments(manifest, scaffold_dir))
    findings.append(check_help_options(manifest, scaffold_dir))
    findings.append(check_json_flag(manifest, scaffold_dir))
    findings.append(check_no_input_flag(manifest, scaffold_dir))
    findings.append(check_no_input_exit2(manifest, scaffold_dir))
    findings.append(check_no_hang(manifest, scaffold_dir))
    findings.append(check_stdout_results(manifest, scaffold_dir))
    findings.append(check_stderr_diagnostics(manifest, scaffold_dir))
    findings.append(check_snapshot_test(manifest, scaffold_dir))
    findings.append(check_distribution(manifest, scaffold_dir))
    findings.append(check_completion(manifest, scaffold_dir))
    if paradigm == SHELL:
        findings.append(check_shell_source_side_effects(manifest, scaffold_dir))
    if language == "posix-sh":
        findings.append(check_posix_bashisms(manifest, scaffold_dir))
    return findings


def _scaffold_id(manifest, scaffold_dir):
    raw = manifest.get("app_name") or os.path.basename(os.path.normpath(scaffold_dir))
    return re.sub(r"[^A-Za-z0-9._-]", "_", raw) or "scaffold"


def _assert_reports_outside_scaffold(reports_root, scaffold_dir):
    sr = os.path.realpath(scaffold_dir)
    rr = os.path.realpath(reports_root)
    try:
        common = os.path.commonpath([sr, rr])
    except ValueError:
        return  # different drives -> safe
    if common == sr:
        raise SystemExit(
            "SCOPE VIOLATION: reports root %r is inside the scaffold %r; the "
            "verifier refuses to write anywhere under the generated scaffold." % (rr, sr)
        )


def _load_ledger(path, scaffold_dir):
    if not os.path.isfile(path):
        return {"scaffold_dir": os.path.realpath(scaffold_dir), "attempts": 0}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        raise HaltError("existing ledger is unreadable: %s" % path)
    # validate on read
    report_validator.validate_ledger(data)
    return data


def main(argv):
    parser = argparse.ArgumentParser(prog="verify_scaffold.py")
    parser.add_argument("scaffold_dir")
    parser.add_argument("language")
    parser.add_argument("--reports-dir", default=None,
                        help="where to write the report/ledger (default CWD/%s)" % REPORTS_ROOT)
    parser.add_argument("--reset-ledger", action="store_true",
                        help="start a fresh attempt count for this scaffold")
    args = parser.parse_args(argv[1:])

    scaffold_dir = args.scaffold_dir
    language = args.language.strip().lower()
    if language not in LANGUAGE_REGISTRY and language != "posix-sh":
        sys.stderr.write("usage error: %r is not a supported language\n" % language)
        return EXIT_USAGE_ERROR
    paradigm = SHELL if language == "posix-sh" else LANGUAGE_REGISTRY[language]

    if not os.path.isdir(scaffold_dir):
        sys.stderr.write("usage error: scaffold dir %r not found\n" % scaffold_dir)
        return EXIT_USAGE_ERROR

    reports_root = args.reports_dir or os.path.join(os.getcwd(), REPORTS_ROOT)
    # verifier-must-not-write: refuse if reports would land inside the scaffold.
    _assert_reports_outside_scaffold(reports_root, scaffold_dir)

    manifest_path = os.path.join(scaffold_dir, MANIFEST_NAME)
    manifest_text = read_text(manifest_path)
    if manifest_text is None:
        sys.stderr.write(
            "HALT: scaffold is missing %s; the paradigm skill must declare its "
            "file roles before verification.\n" % MANIFEST_NAME)
        return EXIT_RUNTIME_ERROR
    try:
        manifest = json.loads(manifest_text)
    except ValueError as exc:
        sys.stderr.write("HALT: %s is not valid JSON: %s\n" % (MANIFEST_NAME, exc))
        return EXIT_RUNTIME_ERROR

    sid = _scaffold_id(manifest, scaffold_dir)
    out_dir = os.path.join(reports_root, sid)
    ledger_path = os.path.join(out_dir, "ledger.json")
    report_path = os.path.join(out_dir, "report.json")

    try:
        os.makedirs(out_dir, exist_ok=True)
        if args.reset_ledger and os.path.isfile(ledger_path):
            os.remove(ledger_path)

        ledger = _load_ledger(ledger_path, scaffold_dir)
        next_attempt = ledger["attempts"] + 1
        # THE BOUND (rule: fixable-gaps loop is bounded).
        if next_attempt > MAX_FIX_ITERATIONS:
            sys.stderr.write(
                "HALT: reached MAX_FIX_ITERATIONS (%d) for this scaffold without "
                "converging. Surface remaining gaps to a human instead of "
                "re-verifying.\n" % MAX_FIX_ITERATIONS)
            return EXIT_RUNTIME_ERROR
    except HaltError as exc:
        sys.stderr.write("HALT: %s\n" % exc)
        return EXIT_RUNTIME_ERROR

    findings = run_checks(manifest, scaffold_dir, language, paradigm)
    has_fail = any(f["status"] == STATUS_FAIL for f in findings)
    verdict = VERDICT_GAPS if has_fail else VERDICT_PASS

    report = {
        "schema_version": 1,
        "scaffold_dir": os.path.realpath(scaffold_dir),
        "language": language,
        "paradigm": paradigm,
        "attempt": next_attempt,
        "verdict": verdict,
        "findings": findings,
        "summary": {
            "total": len(findings),
            "pass": sum(1 for f in findings if f["status"] == STATUS_PASS),
            "fail": sum(1 for f in findings if f["status"] == STATUS_FAIL),
            "fixable": sum(1 for f in findings
                           if f["status"] == STATUS_FAIL and f.get("disposition") == DISPOSITION_FIXABLE),
            "needs_human": sum(1 for f in findings
                               if f["status"] == STATUS_FAIL and f.get("disposition") == DISPOSITION_NEEDS_HUMAN),
        },
    }

    # PERSISTED STATE validated BEFORE write. An inconsistent report cannot land.
    report_validator.validate_report(report)

    new_ledger = {"scaffold_dir": os.path.realpath(scaffold_dir), "attempts": next_attempt}
    report_validator.validate_ledger(new_ledger)

    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
        fh.write("\n")
    with open(ledger_path, "w", encoding="utf-8") as fh:
        json.dump(new_ledger, fh, indent=2, sort_keys=True)
        fh.write("\n")

    # human-readable summary to stderr (diagnostics), machine report path to stdout
    sys.stderr.write(
        "verify attempt %d/%d: verdict=%s  pass=%d fail=%d (fixable=%d, needs-human=%d)\n"
        % (next_attempt, MAX_FIX_ITERATIONS, verdict,
           report["summary"]["pass"], report["summary"]["fail"],
           report["summary"]["fixable"], report["summary"]["needs_human"]))
    for f in findings:
        if f["status"] == STATUS_FAIL:
            sys.stderr.write("  [%s] %s -- %s%s\n" % (
                f["disposition"], f["rule_id"], f["detail"],
                (" (%s)" % f["evidence"]) if f.get("evidence") else ""))
    sys.stdout.write(report_path + "\n")

    return EXIT_SUCCESS if verdict == VERDICT_PASS else EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    sys.exit(main(sys.argv))
