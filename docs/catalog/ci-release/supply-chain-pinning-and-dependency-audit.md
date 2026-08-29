---
task: "Audit supply-chain pinning and dependencies"
category: ci-release
summary: "Separate 'does this package exist' from 'is this reference pinned tightly enough to be reproducible' before trusting either."
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
---

Two different questions hide under one heading. "Does this package exist?" is answerable
against a registry. "Is this reference pinned tightly enough to be reproducible?" is a
policy question about mutable refs, and no werkstoff skill answers it alone.
