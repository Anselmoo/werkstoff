<script setup>
import { computed, reactive } from 'vue'
import { useData, withBase } from 'vitepress'
import CopyButton from './CopyButton.vue'
import DoDontList from './DoDontList.vue'
import { useClipboardCopy } from '../composables/useClipboardCopy'

// Frontmatter-driven, like RecipeBeats -- all of this page's data lives on
// the one page that renders it, so a data loader (CatalogGrid's approach)
// would be aggregating across a single file for no reason.
const { frontmatter } = useData()
const pairings = computed(() => frontmatter.value.pairings ?? [])

const BEAT_ORDER = ['inspect', 'split', 'execute', 'verify']
const BEAT_LABELS = {
  inspect: 'Inspect and research',
  split: 'Split into workstreams',
  execute: 'Execute in parallel',
  verify: 'Verify',
}
const SOURCE_LABELS = {
  superpowers: 'superpowers',
  'claude-plugins-official': 'claude-plugins-official',
}

// No filter active by default, matching CatalogGrid: the first render shows
// every card, and the filter buttons are a progressive enhancement.
const activeBeat = reactive({ value: null })
const activeSource = reactive({ value: null })

function toggleBeat(beat) {
  activeBeat.value = activeBeat.value === beat ? null : beat
}
function toggleSource(source) {
  activeSource.value = activeSource.value === source ? null : source
}

// Present in fixed beat order, but only beats that actually have a card --
// same reasoning as CatalogGrid's category filter.
const beats = computed(() => BEAT_ORDER.filter((b) => pairings.value.some((p) => p.beat === b)))
const sources = computed(() => [...new Set(pairings.value.map((p) => p.source))])

const filteredPairings = computed(() =>
  pairings.value.filter((p) => {
    if (activeBeat.value && p.beat !== activeBeat.value) return false
    if (activeSource.value && p.source !== activeSource.value) return false
    return true
  }),
)

// `why` is one YAML scalar, but the field-note layout wants its first
// sentence bold (the stake) and anything after it in a calmer register.
// Split on the first sentence-ending punctuation FOLLOWED BY WHITESPACE --
// deliberately not just any ".", since every real `why` in this file has at
// least one filename ("CLAUDE.md", "SKILL.md") and one quoted aside ending
// in a period with no trailing space, and a bare `\.` split would fracture
// on those. A `why` with no internal sentence break (most of them) falls
// through to the no-match branch and renders whole as the stake, which is
// the correct behavior, not a bug -- there's nothing to demote.
function splitStake(why) {
  const match = /^(.*?[.!?])\s+(.*)$/s.exec(why ?? '')
  if (!match) return { stake: why ?? '', rest: '' }
  return { stake: match[1], rest: match[2] }
}

// Copy-to-clipboard for the example prompt, with a visible confirmation --
// a click that changes nothing the user can see is exactly the "silent
// state change" this repo's own design review process (cupertino-council)
// treats as a usability veto. The actual clipboard-write-with-fallback
// logic now lives in ../composables/useClipboardCopy.js (see that file's
// comment for why a silent .then() with no .catch() was rejected) so
// RecipeBeats.vue's opening-prompt button can share it instead of
// duplicating it. One composable instance here is shared by every card on
// the page, preserving the original behavior: copiedId/failedId are keyed
// by pairing id, not per-card state.
const { copiedId, failedId, copy } = useClipboardCopy()
</script>

<template>
  <div v-if="pairings.length" class="pairing-cards">
    <div class="pairing-filters">
      <div class="filter-group" role="group" aria-label="Filter by beat">
        <button
          v-for="beat in beats"
          :key="beat"
          type="button"
          class="filter-button"
          :aria-pressed="activeBeat.value === beat"
          @click="toggleBeat(beat)"
        >
          {{ BEAT_LABELS[beat] ?? beat }}
        </button>
      </div>

      <div class="filter-group" role="group" aria-label="Filter by source">
        <button
          v-for="source in sources"
          :key="source"
          type="button"
          class="filter-button"
          :aria-pressed="activeSource.value === source"
          @click="toggleSource(source)"
        >
          {{ SOURCE_LABELS[source] ?? source }}
        </button>
      </div>
    </div>

    <p class="result-count" aria-live="polite">
      {{ filteredPairings.length }} of {{ pairings.length }} pairings
    </p>

    <div class="pairing-list">
      <article v-for="pairing in filteredPairings" :key="pairing.id" class="pairing-card">
        <header class="pairing-head">
          <code>{{ pairing.skillA }}</code>
          <svg class="join-glyph" width="26" height="16" viewBox="0 0 26 16" aria-hidden="true">
            <path d="M2 3 L8 13 L13 5" />
            <path d="M13 5 L18 13 L24 3" />
            <circle cx="13" cy="5" r="2.1" />
          </svg>
          <code>{{ pairing.skillB }}</code>
        </header>

        <div class="pairing-meta">
          <span class="chip chip-beat" :data-beat="pairing.beat">{{
            BEAT_LABELS[pairing.beat] ?? pairing.beat
          }}</span>
          <span class="chip chip-source" :data-source="pairing.source">{{
            SOURCE_LABELS[pairing.source] ?? pairing.source
          }}</span>
        </div>

        <p class="stake">{{ splitStake(pairing.why).stake }}</p>
        <p v-if="splitStake(pairing.why).rest" class="stake-rest">
          {{ splitStake(pairing.why).rest }}
        </p>

        <div class="pairing-row">
          <span class="row-label">How</span>
          <p>{{ pairing.how }}</p>
        </div>

        <div v-if="pairing.prompt" class="prompt-row" data-copy-scope>
          <div class="prompt-row-head">
            <span class="row-label">Example prompt</span>
            <CopyButton
              :status="
                copiedId === pairing.id ? 'copied' : failedId === pairing.id ? 'failed' : 'idle'
              "
              @click="copy(pairing.id, pairing.prompt, $event)"
            />
          </div>
          <pre class="prompt-code" data-copy-target><code>{{ pairing.prompt }}</code></pre>
        </div>

        <DoDontList :dos="pairing.dos" :donts="pairing.donts" />

        <footer v-if="pairing.grounding" class="pairing-foot">
          {{ pairing.grounding }}
          <template v-if="pairing.recipeUrl">
            &middot; from <a :href="withBase(pairing.recipeUrl)">{{ pairing.recipeTask }}</a>
          </template>
        </footer>
      </article>
    </div>
  </div>
</template>

<style scoped>
.pairing-filters {
  display: flex;
  flex-wrap: wrap;
  gap: 1.5rem;
  margin: 1.5rem 0;
}

.filter-group {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.filter-button {
  border: 1px solid var(--vp-c-divider);
  border-radius: 999px;
  padding: 0.25rem 0.85rem;
  font-size: 0.85rem;
  background: var(--vp-c-bg-soft);
  color: var(--vp-c-text-1);
  cursor: pointer;
}

.filter-button[aria-pressed='true'] {
  border-color: var(--vp-c-brand-1);
  font-weight: 600;
}

.result-count {
  color: var(--vp-c-text-2);
  font-size: 0.9rem;
}

.pairing-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 1.25rem;
  margin-top: 1rem;
}

/* ---- Field-note card: one bold stake line up top, everything else in a
   calmer register below it, nothing hidden. See docs/orchestration/
   references/pairings.md's design-comparison mockup (session artifact) for
   the council brief this shape came out of. ---- */
.pairing-card {
  border: 1px solid var(--vp-c-divider);
  border-radius: var(--wk-radius-panel, 8px);
  background: var(--vp-c-bg-soft);
  padding: 1.4rem 1.5rem 1.5rem;
}

.pairing-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.pairing-head code {
  font-weight: 700;
  font-size: 0.98rem;
  letter-spacing: -0.01em;
}

/* The site's own value-stream mark (docs/public/logo.svg: a stroke that
   terminates at a gold node -- "the halt this project is built around"),
   reused at connector scale for the one moment this whole page exists for:
   two skills joining into one move. */
.join-glyph {
  flex: none;
}
.join-glyph path {
  fill: none;
  stroke: var(--wk-silica);
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
.join-glyph circle {
  fill: var(--wk-samaria-light);
}

/* Below ~480px, a long skill name ("code-modernization:business-rules-
   extractor") wraps to two lines on its own, and `flex-wrap` on a still-row
   layout strands the glyph alone on a line between two multi-line blocks --
   the connector reads as orphaned punctuation, not a join. Below that width
   the header switches to a column instead: each name gets its own line to
   wrap within, and the glyph rotates 90deg so the SAME mark still connects
   top-to-bottom instead of left-to-right -- the metaphor survives the
   layout change rather than just surviving the overflow. */
@media (max-width: 480px) {
  .pairing-head {
    flex-direction: column;
    align-items: flex-start;
    flex-wrap: nowrap;
    gap: 0.3rem;
  }
  .join-glyph {
    transform: rotate(90deg);
    margin: 0.05rem 0 0.05rem 0.3rem;
  }
}

.pairing-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin: 0.75rem 0 1.1rem;
}

.chip {
  border-radius: 4px;
  padding: 0.15rem 0.55rem;
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.03em;
}

.chip-source {
  border: 1px solid var(--vp-c-divider);
  color: var(--vp-c-text-2);
}

/* One aerogel chemistry per beat, same technique werkstoff.css already uses
   for the catalog's category colors -- contained to this chip alone, never
   the card's own border or background. VitePress's built-in tip/warning/
   danger/info blocks (werkstoff.css's --vp-custom-block-*-border/-bg) use
   exactly the left-border-plus-tinted-background shape at the CONTAINER
   level for a different taxonomy (severity, not beat); this card was never
   given that shape in the first place, so there's nothing left to collide. */
.chip-beat[data-beat='inspect'] {
  background: rgba(52, 138, 217, 0.14);
  color: var(--wk-silica-deep);
}
.dark .chip-beat[data-beat='inspect'] {
  background: rgba(52, 138, 217, 0.2);
  color: var(--wk-silica-light);
}

.chip-beat[data-beat='split'] {
  background: rgba(8, 147, 92, 0.14);
  color: var(--wk-chromia-deep);
}
.dark .chip-beat[data-beat='split'] {
  background: rgba(8, 147, 92, 0.2);
  color: var(--wk-chromia-light);
}

.chip-beat[data-beat='execute'] {
  background: rgba(171, 109, 198, 0.14);
  color: var(--wk-neodymia-deep);
}
.dark .chip-beat[data-beat='execute'] {
  background: rgba(171, 109, 198, 0.2);
  color: var(--wk-neodymia-light);
}

.chip-beat[data-beat='verify'] {
  background: rgba(171, 143, 0, 0.14);
  color: var(--wk-samaria-deep);
}
.dark .chip-beat[data-beat='verify'] {
  background: rgba(171, 143, 0, 0.2);
  color: var(--wk-samaria-light);
}

.stake {
  font-size: 1.02rem;
  font-weight: 600;
  line-height: 1.45;
  margin: 0 0 0.35rem;
}

.stake-rest {
  font-size: 0.86rem;
  color: var(--vp-c-text-2);
  margin: 0 0 1.2rem;
}
.stake:last-of-type {
  margin-bottom: 1.2rem;
}

.pairing-row,
.prompt-row {
  border-top: 1px solid var(--vp-c-divider);
  padding: 0.85rem 0;
}

.row-label {
  display: block;
  font-size: 0.7rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--vp-c-text-3);
  margin: 0 0 0.35rem;
}

.pairing-row p {
  margin: 0;
  font-size: 0.9rem;
  line-height: 1.5;
}

.prompt-row-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.prompt-code {
  margin: 0.5rem 0 0;
  border-left: 3px solid var(--wk-samaria);
  background: rgba(207, 182, 86, 0.1);
  border-radius: var(--wk-radius-sm, 4px);
  padding: 0.6rem 0.85rem;
  overflow-x: auto;
  white-space: pre-wrap;
}
.dark .prompt-code {
  border-left-color: var(--wk-samaria-light);
  background: rgba(207, 182, 86, 0.08);
}

.prompt-code code {
  font-size: 0.86rem;
  font-family: var(--vp-font-family-mono);
  color: var(--vp-c-text-1);
  background: none;
  padding: 0;
}

.pairing-foot {
  border-top: 1px solid var(--vp-c-divider);
  margin-top: 0.5rem;
  padding-top: 0.75rem;
  font-size: 0.8rem;
  color: var(--vp-c-text-3);
}

.pairing-foot a {
  color: var(--vp-c-brand-1);
}
</style>
