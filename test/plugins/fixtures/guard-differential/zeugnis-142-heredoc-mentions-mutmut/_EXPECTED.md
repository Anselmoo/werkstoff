# zeugnis-142-heredoc-mentions-mutmut

The pair of `zeugnis-142-mutmut-run-working-tree`. The Bash command writes a notes
file through a heredoc whose BODY contains the line `mutmut run`. Nothing runs
mutmut: the body is text `cat` reads.

## old=allow

At base `9a80186` the guard did not gate `mutmut run` at all, so this was allowed.

## new=allow (the fix did not become a blanket gate)

The fixed guard segments multi-line commands line by line for its copy-only check,
which would read that body line as a command. `_strip_heredoc_bodies` drops the
lines between `<<'EOF'` and `EOF` first, so the only commands seen are `cat` and
nothing after it. This keeps the #73 false-positive class (a mention is not an
invocation) closed for the new rule as well.
