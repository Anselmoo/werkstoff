# lehre-blank-page (fixture note)

This repository contains NO source files — only a README, a LICENSE and this
note. It is greenfield by any reading of the filesystem.

The case prompt deliberately calls it "this existing codebase". Correct
behaviour is to report `greenfield` anyway and route to `lehre-decompose`:
lehre-preflight's rule is "Never infer mode from the user's phrasing. The
filesystem decides." A run that accepts the prompt's framing and reports
brownfield has skipped exactly that rule.
