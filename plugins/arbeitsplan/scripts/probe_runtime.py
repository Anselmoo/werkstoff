#!/usr/bin/env python3
"""Measure the Claude Code runtime behaviours arbeitsplan depends on (ADR 0004).

usage: probe_runtime.py --probe P1|P2|P3|P4|P5|all --out DIR [--n 3] [--model haiku]
                        [--max-budget-usd 0.5] [--timeout 420] [--claude-bin claude] [--home DIR]
       probe_runtime.py --selftest

SPENDS REAL TOKENS (everything but --selftest): every run is a headless `claude -p`
in a scratch git repository outside this one, so this repository's CLAUDE.md never
loads into it. CI runs --selftest only.

WHY. arbeitsplan's installer, handoff and wave interpreter are built on claims about
the runtime, and a claim nobody re-measures is a rule nobody can retire:

  P1  plan mode inside a worktree -- a linked worktree as cwd, and EnterWorktree
      from the primary checkout -- plus two controls that must behave as expected
  P2  resume across EnterWorktree: does `--resume` land in the worktree, recall?
  P3  prompt-cache reuse between sibling agents: same agent type vs different
  P4  an agent type written to .claude/agents/ MID-SESSION: does it resolve, via
      the Agent tool and via a Workflow agent({agentType})? (2.1.281: it did not)
  P5  which commit an `isolation: 'worktree'` agent starts from, when the caller's
      cwd is a linked worktree: the primary's HEAD, the caller's, or the remote's

HOW A VERDICT IS REACHED. The oracle for every probe is a FACT -- a file on disk,
a git sha, an event in the stream-json, a subagent's transcript or a workflow's
run record -- never the model's prose alone. The shapes they are read from were
captured from real runs on CLI 2.1.283 first (ADR 0004, "step 0"), and the
selftest's fabricated inputs are built from those shapes.

  ERROR  the run never really happened: timeout, empty or <200-byte stdout, a
         limit/auth banner, no `result` event, or a failed CONTROL inside a run.
  void   it happened but measured nothing: the model never attempted the thing
         (NO_ATTEMPT), a precondition failed (STAGE_FAILED, ENTER_FAILED, ...).
  Both are excluded from the denominator; the probe re-runs a variant up to --n
  extra times to reach --n valid runs, else INSUFFICIENT. All valid runs agree ->
  HOLDS / CHANGED against the recorded claim, or NEW where there was none. Any
  disagreement -> INCONCLUSIVE. Read the transcript of any verdict before
  recording it: a tally cannot tell a real pass from a lucky one.

A failed sweep must not leave a plausible directory behind: output goes to
<out>.partial/ and is renamed to <out> only at the end, and an existing <out> is
refused. Exit: 0 swept (whatever the verdicts), 1 selftest failed, 2 bad input,
3 not logged in.

STDLIB ONLY. Reuses the vendored subrun.py (auth, clean box, the measured shape of
a permission denial); never edits it -- that copy is an rrt artifact.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import subrun

MIN_BYTES = 200
EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
VOID = {"NO_ATTEMPT", "STAGE_FAILED", "ENTER_FAILED", "PRESENT_AT_START", "NO_SHA",
        "UNCACHEABLE", "TOO_FEW", "UNCLEAR", "WORKFLOW_UNAVAILABLE"}
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
NOT_FOUND_RE = re.compile(r"(?i)not found|unknown agent|no such agent|invalid agent|"
                          r"agent type|does not exist|isn't available|not available")
PLAN_RE = re.compile(r"(?i)plan mode")

# variant -> (probe, what is measured, the recorded claim's label or None, its source)
VARIANTS = {
    "P1a-plan-in-worktree": ("P1", "plan mode, cwd = a linked worktree: is a Write refused?",
                             None, "undocumented (ADR 0002:131)"),
    "P1b-plan-enter-worktree": ("P1", "plan mode, EnterWorktree from primary, then Write",
                                None, "undocumented (ADR 0002:131)"),
    "P1c-control-plan-primary": ("P1", "baseline: plan mode in the primary checkout, to "
                                 "compare P1a/P1b against", None, "plan mode in a plain checkout"),
    "P1d-control-edits-worktree": ("P1", "control: acceptEdits, cwd = a linked worktree",
                                   "WROTE", "acceptEdits writes"),
    "P2-resume-after-enter": ("P2", "--resume from primary of a session that entered a worktree",
                              "RESUMED_WT+RECALL",
                              "docs: a resumed worktree session returns to that worktree"),
    "P3a-cache-agent-same": ("P3", "3 Agent-tool siblings of ONE agent type",
                             "REUSE", "docs: same model/effort/type/tools/cwd share a prefix"),
    "P3b-cache-agent-different": ("P3", "3 Agent-tool siblings of three types (tools differ)",
                                  "NO_REUSE", "docs: a different tool set is a different prefix"),
    "P3c-cache-workflow-same": ("P3", "3 Workflow parallel() siblings of ONE agent type",
                                "REUSE", "docs: workflow fan-out staggers to share the prefix"),
    "P4a-late-agent-tool": ("P4", "a type written mid-session, dispatched by the Agent tool",
                            "NOT_FOUND", "ADR 0002:128, measured on 2.1.281"),
    "P4b-late-workflow": ("P4", "a type written mid-session, used by Workflow agent({agentType})",
                          "NOT_FOUND", "ADR 0002:128, measured on 2.1.281"),
    "P4c-late-agent-tool-wait30": ("P4", "as P4a, waiting 30s instead of 5s after the write, "
                                   "to tell a slow watcher from none", "NOT_FOUND",
                                   "ADR 0002:128, measured on 2.1.281"),
    "P5a-base-agent-remote": ("P5", "Agent-tool isolation:'worktree' from a linked worktree",
                              "PRIMARY", "ADR 0002:127, measured on 2.1.281"),
    "P5b-base-workflow-remote": ("P5", "Workflow agent({isolation:'worktree'}) from a linked worktree",
                                 "PRIMARY", "ADR 0002:127, measured on 2.1.281"),
    "P5c-base-agent-no-remote": ("P5", "as P5a, in a repository with no remote",
                                 "PRIMARY", "ADR 0002:127, measured on 2.1.281"),
    "P5d-base-agent-baseref-head": ("P5", "as P5a, with settings worktree.baseRef = \"head\"",
                                    "PRIMARY", "ADR 0002:127, measured on 2.1.281"),
}


# --- stream-json and transcripts ------------------------------------------------------

def _text_of(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


def parse_events(raw: bytes) -> dict:
    """The facts a verdict may rest on, out of one run's stream-json. Shapes as
    captured on 2.1.283: init carries cwd/session_id/tools/agents; an Agent-tool
    reply arrives as a task_notification `summary`; a refusal is a
    system/permission_denied event (subrun's measured shape)."""
    out = {"init": None, "tool_uses": [], "results": {}, "denials": [],
           "tasks": [], "notes": [], "result": None}
    for line in raw.decode("utf-8", "replace").splitlines():
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        kind, sub = ev.get("type"), ev.get("subtype")
        if kind == "system" and sub == "init":
            out["init"] = ev
        elif kind == "system" and sub == "permission_denied":
            out["denials"].append({"tool": ev.get("tool_name"), "why": ev.get(
                "decision_reason_type"), "message": ev.get("message") or ""})
        elif kind == "system" and sub == "task_started":
            out["tasks"].append(ev)
        elif kind == "system" and sub == "task_notification":
            out["notes"].append(ev)
        elif kind == "result":
            out["result"] = ev
        elif kind in ("assistant", "user"):
            for b in ((ev.get("message") or {}).get("content")) or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "tool_use":
                    out["tool_uses"].append({"id": b.get("id"), "name": b.get("name"),
                                             "input": b.get("input") or {}})
                elif b.get("type") == "tool_result":
                    out["results"][b.get("tool_use_id")] = {
                        "text": _text_of(b.get("content")), "is_error": bool(b.get("is_error"))}
    return out


def final_text(p: dict) -> str:
    r = p.get("result") or {}
    return r.get("result") if isinstance(r.get("result"), str) else ""


def error_reason(raw: bytes, stderr: str, timed_out: bool, p: dict) -> str | None:
    """Why this run never really happened, or None. Same gate as run.sh's ERROR."""
    if timed_out:
        return "timeout"
    if not raw.strip():
        return "empty stdout"
    if len(raw) < MIN_BYTES:
        return f"stdout under {MIN_BYTES} bytes"
    if subrun.BANNER_RE.search(stderr or ""):
        return "auth or limit banner on stderr"
    if p.get("result") is None:
        return "no result event"
    r = p["result"]
    if r.get("is_error") and subrun.BANNER_RE.search(final_text(p) or ""):
        return "auth or limit banner in the result"
    return None


def session_dir(home: Path, sid: str) -> Path | None:
    hits = [d for d in (home / ".claude" / "projects").glob(f"*/{sid}") if d.is_dir()]
    return hits[0] if hits else None


def read_agents(home: Path, sid: str) -> list:
    """Every subagent of a session -- Agent-tool ones under subagents/, Workflow
    ones under subagents/workflows/<runId>/ -- with its type, its first request's
    usage (deduplicated by requestId: one request logs one line per content
    block), the cwd it ran in and the tool results it saw."""
    d = session_dir(home, sid)
    if d is None:
        return []
    found = []
    for meta in sorted((d / "subagents").rglob("agent-*.meta.json")):
        try:
            m = json.loads(meta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        requests, seen, cwd, texts = [], set(), None, []
        tx = meta.with_name(meta.name.replace(".meta.json", ".jsonl"))
        for line in (tx.read_text(encoding="utf-8", errors="replace").splitlines()
                     if tx.is_file() else []):
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            cwd = cwd or e.get("cwd")
            msg = e.get("message") or {}
            u, rid = msg.get("usage"), e.get("requestId")
            if e.get("type") == "assistant" and isinstance(u, dict) and rid not in seen:
                seen.add(rid)
                requests.append({"ts": e.get("timestamp") or "", "input": u.get(
                    "input_tokens") or 0, "read": u.get("cache_read_input_tokens") or 0,
                    "creation": u.get("cache_creation_input_tokens") or 0})
            for b in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    texts.append(_text_of(b.get("content")))
        found.append({"agentType": m.get("agentType"), "cwd": cwd, "requests": requests,
                      "tool_texts": texts, "workflow": "workflows" in meta.parts})
    return found


def read_workflow_runs(home: Path, sid: str) -> list:
    d = session_dir(home, sid)
    if d is None:
        return []
    runs = []
    for f in sorted((d / "workflows").glob("*.json")):
        try:
            runs.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return runs


# --- classifiers: pure, so the selftest can plant every one both ways -------------------

def classify_write(p: dict, wrote: bool) -> str:
    """WROTE / DENIED (the harness refused an attempt) / MODEL_REFUSED (no attempt,
    and the model names plan mode as the reason -- plan mode in force at the
    instruction layer, the only layer a `-p` run reaches: MEASURED on 2.1.283,
    haiku will not attempt the call even when told the harness decides) /
    NO_ATTEMPT (void: no attempt and no reason given)."""
    if wrote:
        return "WROTE"
    edit_ids = {t["id"] for t in p["tool_uses"] if t["name"] in EDIT_TOOLS}
    if any(d["tool"] in EDIT_TOOLS for d in p["denials"]) or any(
            p["results"].get(i, {}).get("is_error") for i in edit_ids):
        return "DENIED"
    if not edit_ids and PLAN_RE.search(final_text(p)):
        return "MODEL_REFUSED"
    return "NO_ATTEMPT"


def classify_enter_then_write(p: dict, entered: bool, wrote: bool) -> str:
    """P1b. A plan-mode refusal of EnterWorktree itself is a finding, not void."""
    tried = [t for t in p["tool_uses"] if t["name"] == "EnterWorktree"]
    if not tried:
        return "MODEL_REFUSED" if PLAN_RE.search(final_text(p)) else "NO_ATTEMPT"
    if not entered:
        return "ENTER_DENIED" if any(d["tool"] == "EnterWorktree" for d in p["denials"]) \
            else "ENTER_FAILED"
    return classify_write(p, wrote)


def classify_resume(p: dict, sid: str, code: str, primary: str, worktrees: list) -> str:
    init = p.get("init") or {}
    if init.get("session_id") != sid or "No conversation found" in final_text(p):
        return "NOT_RESUMED"
    pwd = None
    for t in p["tool_uses"]:
        if t["name"] == "Bash":
            first = (p["results"].get(t["id"], {}).get("text") or "").strip().splitlines()
            if first and first[0].startswith("/"):
                pwd = first[0].strip()
    where = os.path.realpath(pwd or init.get("cwd") or "")
    if any(where == w or where.startswith(w + os.sep) for w in worktrees):
        loc = "WT"
    elif where == primary:
        loc = "PRIMARY"
    else:
        loc = "ELSEWHERE"
    return f"RESUMED_{loc}{'+RECALL' if code in final_text(p) else '-RECALL'}"


def classify_cache(agents: list, min_creation: int = 1024) -> str:
    """Siblings, oldest first. REUSE when every later sibling's first request
    reads at least the base's read plus 80% of what the base had to create --
    i.e. it read the base's freshly written prefix, not just a warm preamble."""
    firsts = sorted((a["requests"][0] for a in agents if a["requests"]), key=lambda r: r["ts"])
    if len(firsts) < 2:
        return "TOO_FEW"
    base = firsts[0]
    if base["creation"] < min_creation:
        return "UNCACHEABLE"
    hits = [r["read"] >= base["read"] + 0.8 * base["creation"] for r in firsts[1:]]
    return "REUSE" if all(hits) else "NO_REUSE" if not any(hits) else "PARTIAL"


def classify_late(*, at_start: list, staged: bool, early: str, late: str | None,
                  nonce_early: str, nonce_late: str, name: str) -> str:
    """P4. `early`/`late` are what the two dispatches returned (reply or error
    text); `late` is None when the late type was never dispatched."""
    if name in (at_start or []):
        return "PRESENT_AT_START"
    if not staged:
        return "STAGE_FAILED"
    if nonce_early not in (early or ""):
        return "ERROR"  # the control failed: nothing about the late type is measured
    if late is None:
        return "NO_ATTEMPT"
    if nonce_late in late:
        return "RESOLVES"
    return "NOT_FOUND" if NOT_FOUND_RE.search(late) else "UNCLEAR"


def classify_base(texts: list, shas: dict) -> str:
    """P5. The first 40-hex sha the isolated agent's Bash printed, against the
    known commits: {'PRIMARY': A, 'CALLER': B, 'REMOTE': R}."""
    for t in texts:
        for m in SHA_RE.findall(t or ""):
            for label, sha in shas.items():
                if sha and m == sha:
                    return label
            return "OTHER"
    return "NO_SHA"


def aggregate(labels: list, n: int, expected: str | None) -> dict:
    valid = [x for x in labels if x not in VOID and x != "ERROR"]
    rec = {"labels": labels, "valid": len(valid), "errors": labels.count("ERROR"),
           "void": sum(1 for x in labels if x in VOID)}
    if len(valid) < n:
        return {**rec, "verdict": "INSUFFICIENT", "label": None}
    used = valid[:n]
    if len(set(used)) > 1:
        return {**rec, "verdict": "INCONCLUSIVE", "label": None}
    label = used[0]
    verdict = "NEW" if expected is None else "HOLDS" if label == expected else "CHANGED"
    return {**rec, "verdict": verdict, "label": label}


# --- running one headless session ------------------------------------------------------

class Ctx:
    def __init__(self, args, out: Path):
        self.claude, self.model, self.budget = args.claude_bin, args.model, args.max_budget_usd
        self.timeout, self.home, self.out = args.timeout, Path(args.home), out
        self.env = {**os.environ, "GIT_AUTHOR_NAME": "probe", "GIT_AUTHOR_EMAIL": "probe@local",
                    "GIT_COMMITTER_NAME": "probe", "GIT_COMMITTER_EMAIL": "probe@local"}
        self.version = None


def settings_file(ctx: Ctx, where: Path, allow: list, extra: dict | None = None) -> Path:
    """The clean box (no installed plugin, no personal skill) plus the allow rules
    a probe needs -- in a settings file, not --allowedTools, whose parsing of a
    rule with a space in it (`Bash(bash x.sh)`) is not something to guess at."""
    path = where / "settings.json"
    subrun.write_clean_box_settings(path, ctx.home)
    cfg = json.loads(path.read_text())
    cfg["permissions"] = {"allow": list(allow)}
    cfg.update(extra or {})
    path.write_text(json.dumps(cfg, indent=1))
    return path


def run_claude(ctx: Ctx, prompt: str, cwd: Path, *, mode: str, settings: Path, label: str,
               session_id: str | None = None, resume: str | None = None) -> dict:
    argv = [ctx.claude, "-p", prompt, "--model", ctx.model, "--output-format", "stream-json",
            "--verbose", "--settings", str(settings), "--strict-mcp-config",
            "--permission-mode", mode, "--max-budget-usd", str(ctx.budget)]
    if session_id:
        argv += ["--session-id", session_id]
    if resume:
        argv += ["--resume", resume]
    timed_out = False
    try:
        proc = subprocess.run(argv, cwd=cwd, env=ctx.env, capture_output=True,
                              stdin=subprocess.DEVNULL, timeout=ctx.timeout)
        raw, err = proc.stdout, proc.stderr.decode("utf-8", "replace")
    except subprocess.TimeoutExpired as exc:
        raw, err, timed_out = exc.stdout or b"", (exc.stderr or b"").decode(
            "utf-8", "replace"), True
    dest = ctx.out / label
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.with_suffix(".jsonl").write_bytes(raw)
    dest.with_suffix(".stderr").write_text(err)
    p = parse_events(raw)
    if p["init"] and not ctx.version:
        ctx.version = p["init"].get("claude_code_version")
    return {"p": p, "error": error_reason(raw, err, timed_out, p), "argv": argv}


def git(cwd: Path, env: dict, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True,
                          check=True).stdout.strip()


def scratch_repo(root: Path, env: dict, files: dict | None = None) -> Path:
    repo = root / "repo"
    repo.mkdir(parents=True)
    git(repo, env, "init", "-q", "-b", "main")
    (repo / "README").write_text("probe\n")
    for rel, text in (files or {}).items():
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        (repo / rel).write_text(text)
    git(repo, env, "add", "-A")
    git(repo, env, "commit", "-qm", "seed")
    return repo


def agent_md(name: str, body: str, tools: str = "Read") -> str:
    return (f"---\nname: {name}\ndescription: Probe agent {name}. Replies as its body says.\n"
            f"model: haiku\ntools: {tools}\n---\n{body}\n")


def worktrees_of(repo: Path, env: dict) -> list:
    out = git(repo, env, "worktree", "list", "--porcelain")
    return [os.path.realpath(ln[9:]) for ln in out.splitlines()
            if ln.startswith("worktree ") and os.path.realpath(ln[9:]) != os.path.realpath(repo)]


def found_anywhere(root: Path, name: str) -> bool:
    return any(".git" not in p.parts for p in root.rglob(name))


# --- the probes -------------------------------------------------------------------------

def run_p1(ctx: Ctx, variant: str, tag: str, tmp: Path) -> tuple:
    nonce = uuid.uuid4().hex[:12]
    fname = f"probe-{nonce}.txt"
    repo = scratch_repo(tmp, ctx.env)
    linked = tmp / "wt"
    git(repo, ctx.env, "worktree", "add", "-q", str(linked), "-b", "probe-wt")
    in_wt = variant in ("P1a-plan-in-worktree", "P1d-control-edits-worktree")
    cwd = linked if in_wt else repo
    mode = "acceptEdits" if variant == "P1d-control-edits-worktree" else "plan"
    write = (f"Use the Write tool to create the file {fname} in the current working directory "
             f"with the exact content {nonce}. Call the Write tool now even if you are in plan "
             "mode: this is a measurement of what happens. Do not use any other tool. If the "
             "write is refused, reply REFUSED and stop.")
    prompt = (f"First use the EnterWorktree tool with name 'probe-{nonce[:6]}'. Then: {write}"
              if variant == "P1b-plan-enter-worktree" else write)
    r = run_claude(ctx, prompt, cwd, mode=mode, settings=settings_file(ctx, tmp, []),
                   label=tag, session_id=str(uuid.uuid4()))
    if r["error"]:
        return "ERROR", {"error": r["error"]}
    wrote = found_anywhere(tmp, fname)
    if variant == "P1b-plan-enter-worktree":
        entered = bool(worktrees_of(repo, ctx.env)[1:])  # beyond ../wt
        label = classify_enter_then_write(r["p"], entered, wrote)
    else:
        label = classify_write(r["p"], wrote)
    return label, {"wrote": wrote, "denials": r["p"]["denials"], "cwd": str(cwd),
                   "mode": (r["p"]["init"] or {}).get("permissionMode")}


def run_p2(ctx: Ctx, variant: str, tag: str, tmp: Path) -> tuple:
    code = uuid.uuid4().hex[:10]
    repo = scratch_repo(tmp, ctx.env)
    sid = str(uuid.uuid4())
    first = run_claude(ctx, f"Use the EnterWorktree tool with name 'probe-{code[:6]}'. Then "
                            f"remember this code word for later: {code}. Reply with exactly DONE.",
                       repo, mode="acceptEdits", settings=settings_file(ctx, tmp, []),
                       label=tag + "-a", session_id=sid)
    if first["error"]:
        return "ERROR", {"error": "first run: " + first["error"]}
    wts = worktrees_of(repo, ctx.env)
    if not wts:
        return "ENTER_FAILED", {"tools": [t["name"] for t in first["p"]["tool_uses"]]}
    second = run_claude(ctx, "State the code word I gave you earlier. Then run the Bash command "
                             "`pwd` and report its output.", repo, mode="acceptEdits",
                        settings=settings_file(ctx, tmp, ["Bash(pwd)"]), label=tag + "-b",
                        resume=sid)
    if second["error"] and "No conversation found" not in (final_text(second["p"]) or ""):
        return "ERROR", {"error": "resume run: " + second["error"]}
    label = classify_resume(second["p"], sid, code, os.path.realpath(repo), wts)
    return label, {"worktrees": wts, "init_cwd": (second["p"]["init"] or {}).get("cwd"),
                   "resumed_sid": (second["p"]["init"] or {}).get("session_id"), "sid": sid}


FILLER = "\n".join(f"Reference paragraph {i}: this text only makes the prompt long enough to "
                   f"cache; it carries no instruction and no answer. Line {i} of 400."
                   for i in range(400))


def run_p3(ctx: Ctx, variant: str, tag: str, tmp: Path) -> tuple:
    nonce = uuid.uuid4().hex[:12]
    tools = {"probe-cache-a": "Read", "probe-cache-b": "Read, Grep", "probe-cache-c": "Read, Glob"}
    files = {f".claude/agents/{n}.md": agent_md(n, f"Run token {nonce}.\n{FILLER}\n"
                                                   "Reply with exactly: OK", t)
             for n, t in tools.items()}
    files[".claude/workflows/probe-cache.js"] = (
        "export const meta = { name: 'probe-cache', description: 'three identical siblings' }\n"
        "const r = await parallel([0, 1, 2].map((i) => () => agent('ok?', "
        "{ agentType: 'probe-cache-a', model: 'haiku', label: 'sib' + i })))\n"
        "return { replies: r }\n")
    repo = scratch_repo(tmp, ctx.env, files)
    sid = str(uuid.uuid4())
    if variant == "P3c-cache-workflow-same":
        prompt = ("Use the Workflow tool to run the saved workflow at scriptPath "
                  ".claude/workflows/probe-cache.js. Reply DONE when it completes.")
        allow = ["Workflow"]
    else:
        types = (["probe-cache-a"] * 3 if variant == "P3a-cache-agent-same"
                 else ["probe-cache-a", "probe-cache-b", "probe-cache-c"])
        prompt = ("In ONE single message, call the Agent tool three times in parallel, with "
                  f"subagent_type {types[0]!r}, {types[1]!r} and {types[2]!r} and the prompt "
                  "'ok?' each. Wait for all three, then reply DONE.")
        allow = []
    r = run_claude(ctx, prompt, repo, mode="acceptEdits",
                   settings=settings_file(ctx, tmp, allow), label=tag, session_id=sid)
    if r["error"]:
        return "ERROR", {"error": r["error"]}
    agents = [a for a in read_agents(ctx.home, sid) if str(a["agentType"]).startswith(
        "probe-cache")]
    if variant == "P3c-cache-workflow-same" and "Workflow" not in ((r["p"]["init"] or {}).get(
            "tools") or []):
        return "WORKFLOW_UNAVAILABLE", {}
    return classify_cache(agents), {"firsts": [a["requests"][:1] for a in agents],
                                    "types": [a["agentType"] for a in agents]}


def run_p4(ctx: Ctx, variant: str, tag: str, tmp: Path) -> tuple:
    ne, nl = "EARLY-" + uuid.uuid4().hex[:10], "LATE-" + uuid.uuid4().hex[:10]
    files = {
        ".claude/agents/probe-early.md": agent_md("probe-early", f"Reply with exactly: {ne}"),
        ".probe/late.md": agent_md("probe-late", f"Reply with exactly: {nl}"),
        ".probe/stage.sh": "mkdir -p .claude/agents\ncp .probe/late.md "
                           ".claude/agents/probe-late.md\n"
                           f"sleep {30 if variant.endswith('wait30') else 5}\necho STAGED\n",
        ".claude/workflows/probe-late.js": (
            "export const meta = { name: 'probe-late', description: 'early then late type' }\n"
            "const early = await agent('token?', { agentType: 'probe-early', model: 'haiku', "
            "label: 'early' })\n"
            "let late\n"
            "try {\n"
            "  late = await agent('token?', { agentType: 'probe-late', model: 'haiku', "
            "label: 'late' })\n"
            "} catch (e) {\n"
            "  late = 'ERROR: ' + String(e && e.message ? e.message : e)\n"
            "}\n"
            "return { early: early, late: late === null ? 'ERROR: null result' : late }\n"),
    }
    repo = scratch_repo(tmp, ctx.env, files)
    sid = str(uuid.uuid4())
    stage = "Run the Bash command `bash .probe/stage.sh` and wait for it to finish."
    if variant == "P4b-late-workflow":
        prompt = (f"Do these steps in order. 1) {stage} 2) Use the Workflow tool to run the saved "
                  "workflow at scriptPath .claude/workflows/probe-late.js. 3) When it completes, "
                  "reply DONE.")
        allow = ["Bash(bash .probe/stage.sh)", "Workflow"]
    else:
        prompt = (f"Do these steps in order. 1) {stage} 2) Use the Agent tool with subagent_type "
                  "'probe-early' and the prompt 'token?', and wait for its reply. 3) Use the "
                  "Agent tool with subagent_type 'probe-late' and the prompt 'token?', and wait "
                  "for its reply. 4) Reply with both replies, one per line.")
        allow = ["Bash(bash .probe/stage.sh)"]
    r = run_claude(ctx, prompt, repo, mode="acceptEdits", settings=settings_file(ctx, tmp, allow),
                   label=tag, session_id=sid)
    if r["error"]:
        return "ERROR", {"error": r["error"]}
    p = r["p"]
    staged = (repo / ".claude" / "agents" / "probe-late.md").is_file()
    at_start = (p["init"] or {}).get("agents") or []
    if variant == "P4b-late-workflow":
        if "Workflow" not in ((p["init"] or {}).get("tools") or []):
            return "WORKFLOW_UNAVAILABLE", {}
        runs = read_workflow_runs(ctx.home, sid)
        res = (runs[-1].get("result") if runs else None) or {}
        early, late = str(res.get("early") or ""), (str(res["late"]) if "late" in res else None)
        if not runs:
            late = None
        evidence = {"workflow": [{k: w.get(k) for k in ("status", "result")} for w in runs]}
    else:
        replies = {}
        for t in p["tool_uses"]:
            if t["name"] in ("Agent", "Task"):
                typ = t["input"].get("subagent_type")
                res = p["results"].get(t["id"], {})
                note = next((n for n in p["notes"] if n.get("tool_use_id") == t["id"]), None)
                replies[typ] = (note or {}).get("summary") or res.get("text") or ""
        early, late = replies.get("probe-early", ""), replies.get("probe-late")
        evidence = {"replies": replies}
    label = classify_late(at_start=at_start, staged=staged, early=early, late=late,
                          nonce_early=ne, nonce_late=nl, name="probe-late")
    return label, {**evidence, "agents_at_start": at_start, "staged": staged}


def run_p5(ctx: Ctx, variant: str, tag: str, tmp: Path) -> tuple:
    files = {
        ".claude/agents/probe-sha.md": agent_md(
            "probe-sha", "Run the Bash command `git rev-parse HEAD` and reply with its output "
                         "only.", "Bash"),
        ".claude/workflows/probe-sha.js": (
            "export const meta = { name: 'probe-sha', description: 'isolated agent reports HEAD' }\n"
            "const sha = await agent('go', { agentType: 'probe-sha', model: 'haiku', "
            "isolation: 'worktree', label: 'sha' })\n"
            "return { sha: sha }\n"),
    }
    repo = scratch_repo(tmp, ctx.env, files)
    shas = {"REMOTE": None}
    if variant != "P5c-base-agent-no-remote":
        bare = tmp / "remote.git"
        git(tmp, ctx.env, "init", "-q", "--bare", "-b", "main", str(bare))
        git(repo, ctx.env, "remote", "add", "origin", str(bare))
        git(repo, ctx.env, "push", "-q", "origin", "main")
        git(repo, ctx.env, "remote", "set-head", "origin", "main")
        shas["REMOTE"] = git(repo, ctx.env, "rev-parse", "HEAD")
    (repo / "primary.txt").write_text("A\n")
    git(repo, ctx.env, "add", "-A")
    git(repo, ctx.env, "commit", "-qm", "A: unpushed on the primary")
    shas["PRIMARY"] = git(repo, ctx.env, "rev-parse", "HEAD")
    linked = tmp / "wt"
    git(repo, ctx.env, "worktree", "add", "-q", str(linked), "-b", "feat")
    (linked / "caller.txt").write_text("B\n")
    git(linked, ctx.env, "add", "-A")
    git(linked, ctx.env, "commit", "-qm", "B: on the caller's branch")
    shas["CALLER"] = git(linked, ctx.env, "rev-parse", "HEAD")
    sid = str(uuid.uuid4())
    if variant == "P5b-base-workflow-remote":
        prompt = ("Use the Workflow tool to run the saved workflow at scriptPath "
                  ".claude/workflows/probe-sha.js. Reply with the value of its 'sha' field.")
        allow = ["Workflow", "Bash(git rev-parse HEAD)"]
    else:
        prompt = ("Use the Agent tool with subagent_type 'probe-sha', isolation 'worktree' and "
                  "the prompt 'go'. Wait for its reply and repeat it.")
        allow = ["Bash(git rev-parse HEAD)"]
    # worktree.baseRef ("fresh" = the remote's default branch, the default; "head")
    # is the documented knob; P5d sets it, the others leave the default.
    extra = {"worktree": {"baseRef": "head"}} if variant == "P5d-base-agent-baseref-head" else None
    r = run_claude(ctx, prompt, linked, mode="acceptEdits",
                   settings=settings_file(ctx, tmp, allow, extra), label=tag, session_id=sid)
    if r["error"]:
        return "ERROR", {"error": r["error"]}
    agents = [a for a in read_agents(ctx.home, sid) if a["agentType"] == "probe-sha"]
    texts = [t for a in agents for t in a["tool_texts"]]
    label = classify_base(texts, shas)
    return label, {"shas": shas, "agent_cwds": [a["cwd"] for a in agents]}


RUNNERS = {"P1": run_p1, "P2": run_p2, "P3": run_p3, "P4": run_p4, "P5": run_p5}


def sweep(ctx: Ctx, variants: list, n: int) -> dict:
    summary = {}
    for v in variants:
        probe, what, expected, source = VARIANTS[v]
        labels, runs = [], []
        attempt = 0
        while len([x for x in labels if x not in VOID and x != "ERROR"]) < n and attempt < 2 * n:
            attempt += 1
            tag = f"{v}/run{attempt}"
            with tempfile.TemporaryDirectory(prefix=f"probe-{v}-") as td:
                try:
                    label, evidence = RUNNERS[probe](ctx, v, tag, Path(td))
                except (subprocess.CalledProcessError, OSError) as exc:
                    label, evidence = "ERROR", {"error": f"setup: {exc}"}
            labels.append(label)
            runs.append({"run": tag, "label": label, "evidence": evidence})
            print(f"  {tag}: {label}", flush=True)
        summary[v] = {"probe": probe, "what": what, "claim": expected, "source": source,
                      **aggregate(labels, n, expected), "runs": runs}
    return summary


def write_report(out: Path, summary: dict, ctx: Ctx, n: int) -> None:
    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%d %H:%M UTC")
    (out / "summary.json").write_text(json.dumps(
        {"cli": ctx.version, "model": ctx.model, "n": n, "when": stamp, "variants": summary},
        indent=2) + "\n")
    lines = [f"# runtime probes -- CLI {ctx.version}, model {ctx.model}, N={n}, {stamp}", "",
             "| variant | claim | labels | valid | ERROR | void | verdict |",
             "|---|---|---|---|---|---|---|"]
    for v, s in summary.items():
        lines.append(f"| {v} | {s['claim'] or '—'} | {' '.join(s['labels'])} | {s['valid']} | "
                     f"{s['errors']} | {s['void']} | {s['verdict']}"
                     f"{' ' + s['label'] if s['label'] else ''} |")
    (out / "summary.md").write_text("\n".join(lines) + "\n")


# --- selftest ------------------------------------------------------------------------------

def _stream(*events: dict) -> bytes:
    pad = {"type": "system", "subtype": "thinking_tokens", "pad": "x" * MIN_BYTES}
    return "\n".join(json.dumps(e) for e in (pad, *events)).encode()


def _tu(i: str, name: str, **inp) -> dict:
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "id": i, "name": name, "input": inp}]}}


def _tr(i: str, text: str, err: bool = False) -> dict:
    return {"type": "user", "message": {"content": [
        {"type": "tool_result", "tool_use_id": i, "content": text, "is_error": err}]}}


def _init(**kw) -> dict:
    return {"type": "system", "subtype": "init", "cwd": "/r", "session_id": "S", "tools": [],
            "agents": [], **kw}


def _res(text: str = "done", **kw) -> dict:
    return {"type": "result", "subtype": "success", "result": text, "is_error": False, **kw}


def _deny(tool: str) -> dict:
    return {"type": "system", "subtype": "permission_denied", "tool_name": tool,
            "decision_reason_type": "mode", "message": f"Cannot use {tool} while in plan mode."}


def _cases(clf: dict, tmp: Path) -> list:
    """(name, got, want). `clf` maps a classifier name to the function under
    test, so sabotage can swap one for a constant and watch the table go red."""
    P = parse_events
    wr, enter, res = clf["write"], clf["enter"], clf["resume"]
    cache, late, base, agg, err = clf["cache"], clf["late"], clf["base"], clf["agg"], clf["err"]
    wt = str(tmp / "wt")
    c = [
        ("write: file on disk", wr(P(_stream(_init(), _tu("1", "Write"), _res())), True), "WROTE"),
        ("write: plan-mode denial event", wr(P(_stream(_init(), _tu("1", "Write"), _deny("Write"),
                                                        _res())), False), "DENIED"),
        ("write: tool_result error", wr(P(_stream(_init(), _tu("1", "Edit"), _tr("1", "no", True),
                                                   _res())), False), "DENIED"),
        ("write: never attempted, no reason", wr(P(_stream(_init(), _res("I cannot"))), False),
         "NO_ATTEMPT"),
        ("write: the model cites plan mode", wr(P(_stream(_init(), _res(
            "Plan mode is active; I can't write that file."))), False), "MODEL_REFUSED"),
        ("enter: refused by plan mode", enter(P(_stream(_init(), _tu("1", "EnterWorktree"),
                                                        _deny("EnterWorktree"), _res())),
                                              False, False), "ENTER_DENIED"),
        ("enter: entered, then write refused", enter(P(_stream(
            _init(), _tu("1", "EnterWorktree"), _tu("2", "Write"), _deny("Write"), _res())),
            True, False), "DENIED"),
        ("enter: entered, then wrote", enter(P(_stream(_init(), _tu("1", "EnterWorktree"),
                                                       _res())), True, True), "WROTE"),
        ("enter: never tried", enter(P(_stream(_init(), _res())), False, False), "NO_ATTEMPT"),
        ("enter: never tried, citing plan mode", enter(P(_stream(_init(), _res(
            "Plan mode is active, EnterWorktree is not read-only."))), False, False),
         "MODEL_REFUSED"),
        ("resume: lands in the worktree, recalls", res(P(_stream(
            _init(session_id="S", cwd="/r"), _tu("1", "Bash", command="pwd"),
            _tr("1", wt + "\n"), _res("code c0de, pwd shown"))), "S", "c0de", "/r", [wt]),
         "RESUMED_WT+RECALL"),
        ("resume: lands in primary, forgot", res(P(_stream(
            _init(session_id="S", cwd="/r"), _res("no idea"))), "S", "c0de", "/r", [wt]),
         "RESUMED_PRIMARY-RECALL"),
        ("resume: a different session", res(P(_stream(_init(session_id="T"), _res())), "S", "x",
                                            "/r", [wt]), "NOT_RESUMED"),
    ]

    def ag(*firsts) -> list:
        return [{"requests": [{"ts": f"t{i}", "input": 10, "read": r, "creation": k}]}
                for i, (r, k) in enumerate(firsts)]

    c += [
        ("cache: siblings read the base's prefix", cache(ag((0, 6000), (6000, 10), (6100, 0))),
         "REUSE"),
        ("cache: siblings create their own", cache(ag((500, 6000), (500, 6000), (500, 6000))),
         "NO_REUSE"),
        ("cache: one of two", cache(ag((0, 6000), (6000, 0), (0, 6000))), "PARTIAL"),
        ("cache: base too small to cache", cache(ag((0, 0), (0, 0))), "UNCACHEABLE"),
        ("cache: one sibling", cache(ag((0, 6000))), "TOO_FEW"),
    ]
    kw = {"at_start": ["probe-early"], "staged": True, "early": "EARLY-1", "nonce_early":
          "EARLY-1", "nonce_late": "LATE-1", "name": "probe-late"}
    c += [
        ("late: resolves", late(**{**kw, "late": "LATE-1"}), "RESOLVES"),
        ("late: not found", late(**{**kw, "late": "Agent type 'probe-late' not found"}),
         "NOT_FOUND"),
        ("late: the control failed", late(**{**kw, "early": "?", "late": "LATE-1"}), "ERROR"),
        ("late: present at start", late(**{**kw, "at_start": ["probe-late"], "late": "LATE-1"}),
         "PRESENT_AT_START"),
        ("late: never staged", late(**{**kw, "staged": False, "late": "LATE-1"}), "STAGE_FAILED"),
        ("late: never dispatched", late(**{**kw, "late": None}), "NO_ATTEMPT"),
    ]
    a, b, r = "a" * 40, "b" * 40, "c" * 40
    shas = {"PRIMARY": a, "CALLER": b, "REMOTE": r}
    c += [
        ("base: primary", base([f"{a}\n"], shas), "PRIMARY"),
        ("base: caller", base([f"HEAD is {b}"], shas), "CALLER"),
        ("base: remote", base([r], shas), "REMOTE"),
        ("base: none printed", base(["error"], shas), "NO_SHA"),
        ("base: an unknown commit", base(["d" * 40], shas), "OTHER"),
    ]
    c += [
        ("agg: all agree with the claim", agg(["X", "X", "X"], 3, "X")["verdict"], "HOLDS"),
        ("agg: all agree against it", agg(["Y", "Y", "Y"], 3, "X")["verdict"], "CHANGED"),
        ("agg: no prior claim", agg(["Y", "Y", "Y"], 3, None)["verdict"], "NEW"),
        ("agg: disagreement", agg(["X", "Y", "X"], 3, "X")["verdict"], "INCONCLUSIVE"),
        ("agg: ERROR and void never count", agg(["ERROR", "NO_ATTEMPT", "X", "X"], 3, "X")[
            "verdict"], "INSUFFICIENT"),
        ("agg: ERROR excluded, 3 valid", agg(["ERROR", "X", "X", "X"], 3, "X")["verdict"],
         "HOLDS"),
    ]
    good = _stream(_init(), _res())
    c += [
        ("err: a clean run", err(good, "", False, P(good)), None),
        ("err: timeout", err(good, "", True, P(good)) is not None, True),
        ("err: empty stdout", err(b"", "", False, P(b"")) is not None, True),
        ("err: tiny stdout", err(b'{"type":"result"}', "", False, P(b'{"type":"result"}'))
         is not None, True),
        ("err: banner", err(good, "Failed to authenticate", False, P(good)) is not None, True),
        ("err: no result event", err(_stream(_init()), "", False, P(_stream(_init())))
         is not None, True),
    ]
    return c


def _transcript_cases(tmp: Path) -> list:
    """read_agents / read_workflow_runs against a fabricated home, in the layout
    captured on 2.1.283."""
    home = tmp / "home"
    sess = home / ".claude" / "projects" / "-tmp-x" / "SID"
    for sub, name, typ, reqs in (("subagents", "agent-1", "probe-cache-a", [(0, 6000)]),
                                 ("subagents/workflows/wf_1", "agent-2", "probe-sha", [(6000, 5)])):
        d = sess / sub
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.meta.json").write_text(json.dumps({"agentType": typ}))
        lines = [json.dumps({"type": "user", "cwd": "/w", "message": {"content": [
            {"type": "tool_result", "tool_use_id": "t", "content": "a" * 40}]}})]
        for i, (read, creation) in enumerate(reqs):
            for _block in range(2):  # one request, logged once per content block
                lines.append(json.dumps({"type": "assistant", "requestId": f"r{i}", "cwd": "/w",
                                         "timestamp": f"t{i}", "message": {"usage": {
                                             "input_tokens": 3, "cache_read_input_tokens": read,
                                             "cache_creation_input_tokens": creation}}}))
        (d / f"{name}.jsonl").write_text("\n".join(lines) + "\n")
    (sess / "workflows").mkdir()
    (sess / "workflows" / "wf_1.json").write_text(json.dumps({"status": "completed",
                                                              "result": {"sha": "x"}}))
    agents = read_agents(home, "SID")
    by = {a["agentType"]: a for a in agents}
    return [
        ("transcripts: both subagent layouts found", sorted(by), ["probe-cache-a", "probe-sha"]),
        ("transcripts: a request counted once, not once per block",
         len(by.get("probe-cache-a", {}).get("requests", [])), 1),
        ("transcripts: workflow agents are marked", by.get("probe-sha", {}).get("workflow"), True),
        ("transcripts: tool results are kept", by.get("probe-sha", {}).get("tool_texts"),
         ["a" * 40]),
        ("transcripts: the workflow run record", read_workflow_runs(home, "SID")[0]["status"],
         "completed"),
        ("transcripts: an unknown session is empty", read_agents(home, "NOPE"), []),
    ]


def selftest() -> int:
    fails: list = []
    real = {"write": classify_write, "enter": classify_enter_then_write,
            "resume": classify_resume, "cache": classify_cache, "late": classify_late,
            "base": classify_base, "agg": aggregate, "err": error_reason}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for name, got, want in _cases(real, tmp) + _transcript_cases(tmp):
            ok = got == want
            print(f"  {'ok  ' if ok else 'FAIL'} {name}")
            if not ok:
                fails.append(name)
                print(f"       got {got!r}, want {want!r}")
        # Sabotage: each oracle replaced by a constant must turn some case red,
        # or the table cannot see that oracle at all.
        consts = {"write": lambda *a, **k: "WROTE", "enter": lambda *a, **k: "WROTE",
                  "resume": lambda *a, **k: "RESUMED_WT+RECALL",
                  "cache": lambda *a, **k: "REUSE", "late": lambda *a, **k: "RESOLVES",
                  "base": lambda *a, **k: "PRIMARY",
                  "agg": lambda *a, **k: {"verdict": "HOLDS"}, "err": lambda *a, **k: None}
        for key, const in consts.items():
            try:
                red = sum(got != want for _n, got, want in _cases({**real, key: const}, tmp))
            except (KeyError, TypeError):
                red = 1  # a constant the table cannot even consume is caught too
            ok = red > 0
            print(f"  {'ok  ' if ok else 'FAIL'} sabotage: a constant {key} oracle -> "
                  f"{red} case(s) red")
            if not ok:
                fails.append(f"sabotage {key}")
        # End to end through a stub `claude`: the argv, and the refusal of an existing --out.
        stub = tmp / "claude"
        stub.write_text("#!/usr/bin/env python3\nimport json,sys\n"
                        f"open({str(tmp / 'argv.json')!r},'w').write(json.dumps(sys.argv))\n"
                        "print(json.dumps({'type':'system','subtype':'init','cwd':'/x',"
                        "'session_id':'S','claude_code_version':'9.9.9','pad':'x'*300}))\n"
                        "print(json.dumps({'type':'result','subtype':'success',"
                        "'result':'ok','is_error':False}))\n")
        stub.chmod(0o755)
        args = argparse.Namespace(claude_bin=str(stub), model="haiku", max_budget_usd=0.1,
                                  timeout=60, home=str(tmp / "home"))
        ctx = Ctx(args, tmp / "out")
        (tmp / "home").mkdir(exist_ok=True)
        r = run_claude(ctx, "hi", tmp, mode="plan", settings=settings_file(ctx, tmp, ["X"]),
                       label="e2e", session_id="S")
        argv = json.loads((tmp / "argv.json").read_text())
        for name, ok in [
            ("e2e: a clean stub run is not an ERROR", r["error"] is None),
            ("e2e: stream-json, verbose, clean-box settings, strict MCP",
             all(x in argv for x in ("stream-json", "--verbose", "--settings",
                                     "--strict-mcp-config"))),
            ("e2e: the permission mode is passed", argv[argv.index("--permission-mode") + 1]
             == "plan"),
            ("e2e: the CLI version is recorded", ctx.version == "9.9.9"),
            ("e2e: the settings carry the allow rules", json.loads(
                (tmp / "settings.json").read_text())["permissions"]["allow"] == ["X"]),
            ("e2e: the transcript is kept", (tmp / "out" / "e2e.jsonl").is_file()),
        ]:
            print(f"  {'ok  ' if ok else 'FAIL'} {name}")
            if not ok:
                fails.append(name)
        exists = tmp / "exists"
        exists.mkdir()
        code = main(["--probe", "P1", "--out", str(exists), "--claude-bin", str(stub)])
        ok = code == 2
        print(f"  {'ok  ' if ok else 'FAIL'} an existing --out is refused (exit {code})")
        if not ok:
            fails.append("existing --out")
    print()
    if fails:
        print(f"SELFTEST FAILED ({len(fails)}): " + ", ".join(fails))
        return 1
    print("probe_runtime selftest passed (no tokens spent)")
    return 0


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(prog="probe_runtime.py", description=(
        __doc__ or "").split("\n\n")[0], epilog="exit 0 swept, 1 selftest failed, 2 bad input, "
        "3 not logged in")
    parser.add_argument("--probe", choices=["P1", "P2", "P3", "P4", "P5", "all"])
    parser.add_argument("--out", help="a directory that does NOT exist yet")
    parser.add_argument("--n", type=int, default=3, help="valid runs per variant (default 3)")
    parser.add_argument("--model", default="haiku")
    parser.add_argument("--max-budget-usd", type=float, default=0.5)
    parser.add_argument("--timeout", type=int, default=420, help="seconds per claude -p run")
    parser.add_argument("--claude-bin", default="claude")
    parser.add_argument("--home", default=str(Path.home()),
                        help="whose ~/.claude holds the transcripts (default: yours)")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return selftest()
    if not args.probe or not args.out:
        parser.error("--probe and --out are required")
    out = Path(args.out)
    partial = out.with_name(out.name + ".partial")
    if out.exists() or partial.exists():
        print(f"refusing: {out} (or its .partial) already exists -- a previous sweep's output "
              "would be read as this one's", file=sys.stderr)
        return 2
    if Path(args.claude_bin).name == "claude":
        try:
            subrun.check_auth(args.claude_bin)
        except subrun.AuthError as exc:
            print(f"not measurable: {exc}", file=sys.stderr)
            return 3
    variants = [v for v, spec in VARIANTS.items() if args.probe in ("all", spec[0])]
    partial.mkdir(parents=True)
    ctx = Ctx(args, partial)
    summary = sweep(ctx, variants, args.n)
    write_report(partial, summary, ctx, args.n)
    partial.rename(out)
    print((out / "summary.md").read_text())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
