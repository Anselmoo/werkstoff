# ui-missing-alt

Seeded-defect fixture for self-assess-ui-audit's behavior test. Each block in
`index.html` carries exactly one known accessibility/UI defect the audit must
catch. Do not "fix" the defects in `index.html` — they are the oracle. Keep
line numbers stable when editing; the harness asserts on the finding text, not
on lines.

EXPECTED FINDINGS (the harness asserts the audit surfaces these):

- a11y img-no-alt — `index.html` (the logo image)
- semantics div-onclick — `index.html` (the Submit div)
- a11y input-no-label — `index.html` (the email input)
- hardcoded-value hardcoded-color — `index.html` (`.drifted` color literal)

EXPECTED NON-FINDINGS (false-positive guardrails):

- the labelled password input
- the decorative image with `alt=""`
