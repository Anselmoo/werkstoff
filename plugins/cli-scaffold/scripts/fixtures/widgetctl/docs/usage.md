# Using widgetctl

`widgetctl` writes data to stdout and diagnostics to stderr, so it composes:

```sh
widgetctl --json | jq '.widgets[].id'
```
