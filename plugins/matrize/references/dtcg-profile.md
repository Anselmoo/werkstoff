# DTCG profile

The source of truth is a plain [DTCG](https://www.designtokens.org/tr/2025.10/format)
token file at `<root>/system/tokens.json`. **No extension to the specification, no custom
schema.** Every formatter this plugin ships — and every off-the-shelf tool that reads
DTCG — must be able to read it.

## Motion and gradients are native. Do not invent types for them.

The commonest mistake here is assuming the spec stops at colour and spacing and building
a private motion format. It does not:

| concept | `$type` | value shape |
|---|---|---|
| duration | `duration` | `{ "value": 200, "unit": "ms" }` — `ms` or `s` |
| easing | `cubicBezier` | `[0.5, 0, 1, 1]` — P1 and P2 |
| motion as a whole | `transition` | `{ duration, delay, timingFunction }`, each a value or a `{ref}` |
| gradient | `gradient` | array of `{ color, position }` stops |
| shadow | `shadow` | single, layered, inset, and mixed-reference forms |
| dimension | `dimension` | `{ "value": 16, "unit": "px" }` — also carries motion *distance* |
| colour | `color` | `{ "colorSpace": "srgb", "components": [r, g, b], "alpha"?, "hex"? }` |
| weight | `fontWeight` | `1`–`1000`, or a recognised keyword |

So of the four motion properties this plugin requires coverage of — duration, easing,
distance, staggering — three are native and distance is an ordinary `dimension`.

**Staggering has no type, and should not get one.** A stagger is a *rule* about how
several animations relate, not a value a component consumes. It belongs in `LEXIKON.md`
with its anti-rule, not in the token file.

## Where this plugin's own content lives

DTCG has no slot for `purpose`, `rule`, `anti-rule`, provenance, or the two grades. The
specification's sanctioned answer is `$extensions`, keyed by a reverse-domain string, and
that is exactly what is used — so a formatter that does not know matrize reads past it
harmlessly instead of failing.

```json
{
  "color": {
    "action": {
      "$type": "color",
      "$value": { "colorSpace": "srgb", "components": [0.98, 0.18, 0.10], "hex": "#FA2E1A" },
      "$description": "The single dominant action colour. One per view, never two.",
      "$extensions": {
        "com.werkstoff.matrize": {
          "role": "dominant-action",
          "purpose": "Von Restorff Effect — a lone dissimilar element is what reads as the action",
          "rule": "Exactly one dominant action colour per view.",
          "antiRule": "Two dominants in one view and neither reads as the action.",
          "card": "CARD-007",
          "reliability": "A",
          "rights": "R1",
          "contrast": { "onPaper": 3.81, "passesAA": false, "passesAALarge": true }
        }
      }
    }
  }
}
```

Three conventions worth stating, because each is easy to get subtly wrong:

- **`$description` carries the human sentence.** It is the field every other tool will
  surface, so put the rule there in plain language and keep the structured duplicate in
  `$extensions`.
- **`$deprecated`** takes `true` or an explanation string. Use the string form — a token
  deprecated without a stated replacement generates exactly the question the lexicon was
  supposed to answer.
- **Groups carry `$type` as a default** and support `$extends`, so a whole group's
  provenance need not be repeated per token.

## What validation enforces

`scripts/validate_tokens.py` checks, mechanically:

1. every token has a `$type` the profile above names;
2. every `$value` matches that type's shape;
3. every reference `{a.b.c}` resolves, and no cycle exists;
4. every token carries `com.werkstoff.matrize.card`, `reliability` and `rights`;
5. **no token's sole provenance is a grade-C card** — this is the mechanical form of "a
   value supported solely by a screenshot is not a token", so it cannot be argued with;
6. every colour token in a role that can carry text has a computed `contrast` block,
   because contrast is arithmetic and there is no excuse for asserting it.

## The one thing never to do

Never treat an emitted CSS, SCSS or Tailwind file as input. They are formatter output. A
hand edit there is lost on the next emit, and — worse — it makes the source untrue while
everything continues to look correct.
