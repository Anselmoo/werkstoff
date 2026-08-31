---
task: "Audit supply-chain pinning and dependencies"
category: ci-release
summary: "Separate 'does this package exist' from 'is this reference pinned tightly enough to be reproducible' before trusting either."
openingPrompt: "Audit our dependencies and supply-chain pinning -- check whether every declared package actually exists before trusting the lockfile, run an adversarial security pass over the manifests and workflows, and then prove whether every third-party reference is actually pinned tightly enough to be reproducible rather than assuming it from the CVE scan alone."
external: ["claude-plugins-official"]
beats:
  - skill: "confab:confab-dependency-audit"
    why: "Hallucinated and typosquat-adjacent entries are cheapest to catch at declaration time, before a lockfile blesses them."
    prompt: "audit every dependency in our manifests — I want to know if any of them don't actually exist or look like typosquats"
  - skill: "code-modernization:security-auditor"
    why: "A standalone adversarial leaf; dispatched directly, without adopting the modernization pipeline."
    prompt: "run an adversarial security pass over this repo — OWASP, CVEs in dependencies, secrets, injection"
  - skill: "andon:andon-verify"
    why: "\"Everything is pinned\" is a contract; a float tag silently violates it and only evidence catches that."
    prompt: "we claim every third-party reference is pinned. Prove it or refute it with evidence."
grounding: "every `uses:` reference in `.github/workflows/` is a float tag, not a commit SHA: `actions/checkout@v7`, `anchore/sbom-action@v0`, `actions/attest-build-provenance@v4`, and `pypa/gh-action-pypi-publish@release/v1` — the last a moving branch ref inside the publish path that already emits an SBOM and a provenance attestation."
dos:
  - "Audit every dependency for existence and typosquat-adjacency before the lockfile blesses it -- cheapest to catch at declaration time."
  - "Dispatch a standalone adversarial security pass -- OWASP, CVEs, secrets, injection -- without adopting the whole modernization pipeline."
  - "Prove the pinning claim with evidence -- 'everything is pinned' is a contract, and a float tag violates it silently."
donts:
  - "Don't conflate 'does this package exist' with 'is this reference pinned tightly enough to be reproducible' -- they're different questions with different answers."
  - "Don't trust a `uses:` reference just because it names a version tag -- a float tag like `@v7` or `@release/v1` is not a commit SHA and can move underneath you."
  - "Don't assume dependency existence and pin strength both hold just because one of them was checked."
---

# Audit supply-chain pinning and dependencies

Two different questions hide under one heading. "Does this package exist?" is answerable
against a registry. "Is this reference pinned tightly enough to be reproducible?" is a
policy question about mutable refs, and no werkstoff skill answers it alone.
