"""Parsed mutation-tool results, kill proofs, and the real-tool citation check.

`toolSource: "real-tool"` used to be an enum value a finding could simply
claim. A real-tool finding now has to CITE what the tool produced: a
`resultsFile` (written by `mutation_harden.py collect` under
analysis/zeugnis/mutation/<runId>/records/) and a `mutantId` in it.
`verify_citation` re-opens the tool's own per-file result -- for mutmut, the
`mutants/<source>.meta` sidecar inside the copy -- checks its sha256 against
the one recorded at collect time, and re-derives the mutant's status from it.
A citation that does not survive that is dropped by the writer, exactly like
a finding missing `toolSource` always was.

Only mutmut 3 has a parser here. Its status table is copied from mutmut
3.8.1's `mutmut/stats.py` (`status_by_exit_code`); any code not in it is
"suspicious", as in mutmut itself.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lib.mutation_scope import MUTATION_DIR_PARTS, is_within, lexical_path

RESULTS_SCHEMA = "zeugnis/mutation-results/1"
PROOF_SCHEMA = "zeugnis/mutation-proof/1"

MUTMUT_STATUS_BY_EXIT_CODE = {
    1: "killed",
    3: "killed",
    0: "survived",
    5: "no tests",
    2: "check was interrupted by user",
    None: "not checked",
    33: "no tests",
    34: "skipped",
    35: "suspicious",
    36: "timeout",
    37: "caught by type check",
    -24: "timeout",
    24: "timeout",
    152: "timeout",
    255: "timeout",
    -11: "segfault",
    -9: "segfault",
}

# Every status gets its own counter, so nothing a time-boxed shard leaves
# behind ("not checked") silently disappears from a total.
COUNT_KEYS = {
    "killed": "killed",
    "survived": "survived",
    "no tests": "noTests",
    "not checked": "notChecked",
    "timeout": "timeout",
    "suspicious": "suspicious",
    "skipped": "skipped",
    "segfault": "segfault",
    "caught by type check": "caughtByTypeCheck",
    "check was interrupted by user": "interrupted",
}
# A real-tool finding is a mutant the tests did not catch.
FINDING_STATUSES = {"survived", "no tests"}


class MutationResultsError(Exception):
    """A results file, proof or citation is missing, malformed or contradicted."""


def mutmut_status(exit_code) -> str:
    return MUTMUT_STATUS_BY_EXIT_CODE.get(exit_code, "suspicious")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_mutmut_meta(path: Path) -> dict:
    """{mutantId: exit code} from one mutmut 3 `.meta` sidecar, strictly."""
    data = json.loads(path.read_text(encoding="utf-8"))
    codes = data.get("exit_code_by_key") if isinstance(data, dict) else None
    if not isinstance(codes, dict):
        raise MutationResultsError(f"{path}: no exit_code_by_key object; not a mutmut 3 .meta file")
    return codes


def empty_counts() -> dict:
    return {key: 0 for key in COUNT_KEYS.values()}


def score(counts: dict) -> float | None:
    """killed / (killed + survived), or None when neither happened. `no tests`
    is deliberately NOT in the denominator and must be reported beside it:
    124 mutants with 38 killed and 86 untested would otherwise read 100 %."""
    killed = counts.get("killed", 0) + counts.get("caughtByTypeCheck", 0)
    denominator = killed + counts.get("survived", 0)
    return None if denominator == 0 else round(killed / denominator, 4)


def evidence_path(repo_root, relpath: str, label: str) -> Path:
    """`relpath` inside analysis/zeugnis/mutation/, lexically, or an error."""
    root = lexical_path(repo_root, ".")
    if not relpath or Path(relpath).is_absolute():
        raise MutationResultsError(f"{label} {relpath!r} must be repo-relative")
    target = lexical_path(root, relpath)
    if not is_within(target, root.joinpath(*MUTATION_DIR_PARTS)):
        raise MutationResultsError(f"{label} {relpath!r} is not under {'/'.join(MUTATION_DIR_PARTS)}/")
    if not target.is_file() or target.is_symlink():
        raise MutationResultsError(f"{label} {relpath!r} does not exist as a regular file")
    return target


def load_json_evidence(repo_root, relpath: str, schema: str, label: str) -> dict:
    path = evidence_path(repo_root, relpath, label)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MutationResultsError(f"{label} {relpath!r} is not readable JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != schema:
        raise MutationResultsError(f"{label} {relpath!r} is not a {schema} document")
    return data


def load_proof(repo_root, relpath: str, mutant_id: str) -> dict:
    """A kill proof for exactly `mutant_id`, or an error naming why not.

    Killed means: the new test passed on the unmutated copy (exit 0) and
    failed -- not errored -- with the mutant applied (pytest exit 1). An
    import or collection error under the mutant (exit 2..5) is not a kill.
    """
    proof = load_json_evidence(repo_root, relpath, PROOF_SCHEMA, "proof")
    if proof.get("mutantId") != mutant_id:
        raise MutationResultsError(f"proof {relpath!r} is for {proof.get('mutantId')!r}, not {mutant_id!r}")
    if (proof.get("verdict"), proof.get("cleanExit"), proof.get("mutantExit")) != ("killed", 0, 1):
        raise MutationResultsError(
            f"proof {relpath!r} does not show a kill (verdict={proof.get('verdict')!r}, "
            f"cleanExit={proof.get('cleanExit')!r}, mutantExit={proof.get('mutantExit')!r})"
        )
    if proof.get("originalSourceSha256") == proof.get("mutatedSourceSha256"):
        raise MutationResultsError(f"proof {relpath!r}: applying the mutant did not change the source")
    return proof


def verify_citation(repo_root, finding: dict) -> dict:
    """Re-derive a real-tool finding's mutant from the tool's own output.

    Returns the mutant record from the results file. Raises
    MutationResultsError when the citation is missing, points outside the
    mutation tree, names a mutant the results do not hold, the tool's sidecar
    changed since collect, or the re-derived status is not one a finding can
    have (a killed mutant is not a weakness).
    """
    results_file = finding.get("resultsFile")
    mutant_id = finding.get("mutantId")
    if not results_file or not mutant_id:
        raise MutationResultsError("a real-tool finding must cite resultsFile and mutantId")
    results = load_json_evidence(repo_root, results_file, RESULTS_SCHEMA, "resultsFile")
    mutants = {m.get("id"): m for m in results.get("mutants", []) if isinstance(m, dict)}
    record = mutants.get(mutant_id)
    if record is None:
        raise MutationResultsError(f"{results_file!r} holds no mutant {mutant_id!r}")
    sidecars = {s.get("path"): s.get("sha256") for s in results.get("toolFiles", []) if isinstance(s, dict)}
    tool_file = str(record.get("toolFile") or "")
    if not tool_file or tool_file not in sidecars:
        raise MutationResultsError(f"mutant {mutant_id!r} cites tool file {tool_file!r} the results never hashed")
    try:
        sidecar = evidence_path(repo_root, tool_file, "tool file")
    except MutationResultsError as exc:
        raise MutationResultsError(f"{exc}; keep the run directory until its report is written") from exc
    if sha256_file(sidecar) != sidecars[tool_file]:
        raise MutationResultsError(f"{tool_file!r} changed after collect; the results no longer describe it")
    if results.get("tool") != "mutmut":
        raise MutationResultsError(f"no parser for tool {results.get('tool')!r}")
    codes = read_mutmut_meta(sidecar)
    if mutant_id not in codes:
        raise MutationResultsError(f"{tool_file!r} holds no mutant {mutant_id!r}")
    status = mutmut_status(codes[mutant_id])
    if status != record.get("status"):
        raise MutationResultsError(f"{tool_file!r} says {status!r}, the results file says {record.get('status')!r}")
    if status not in FINDING_STATUSES:
        raise MutationResultsError(f"mutant {mutant_id!r} is {status!r}; only {sorted(FINDING_STATUSES)} are findings")
    return record

