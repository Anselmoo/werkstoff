# takt beats (fixture)

This repository declares one beat, so takt is active here.

```json
{
  "beats": [
    {
      "id": "ui-before-council",
      "tools": ["Write", "Edit", "MultiEdit"],
      "paths": ["*.tsx", "*.jsx", "*.vue", "*.svelte", "src/ui/*"],
      "require": ".takt/council-done",
      "reason": "cupertino-council runs before UI code, never after."
    }
  ]
}
```
