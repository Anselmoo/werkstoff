<script setup>
import { computed, reactive } from 'vue'
import { useData, withBase } from 'vitepress'

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
      <article
        v-for="pairing in filteredPairings"
        :key="pairing.id"
        class="pairing-card"
        :data-beat="pairing.beat"
      >
        <header class="pairing-header">
          <h3 class="pairing-name">
            <code>{{ pairing.skillA }}</code>
            <span class="plus" aria-hidden="true">+</span>
            <code>{{ pairing.skillB }}</code>
          </h3>
          <div class="pairing-badges">
            <span class="badge badge-beat">{{ BEAT_LABELS[pairing.beat] ?? pairing.beat }}</span>
            <span class="badge badge-source" :data-source="pairing.source">{{
              SOURCE_LABELS[pairing.source] ?? pairing.source
            }}</span>
          </div>
        </header>

        <section class="pairing-section">
          <h4>Why</h4>
          <p>{{ pairing.why }}</p>
        </section>

        <section class="pairing-section">
          <h4>How</h4>
          <p>{{ pairing.how }}</p>
        </section>

        <section v-if="pairing.prompt" class="pairing-section">
          <h4>Example prompt</h4>
          <blockquote class="pairing-prompt">
            <p>{{ pairing.prompt }}</p>
          </blockquote>
        </section>

        <section class="pairing-section pairing-dos-donts">
          <div class="dos">
            <h4>Do</h4>
            <ul>
              <li v-for="(item, i) in pairing.dos" :key="i">{{ item }}</li>
            </ul>
          </div>
          <div class="donts">
            <h4>Don't</h4>
            <ul>
              <li v-for="(item, i) in pairing.donts" :key="i">{{ item }}</li>
            </ul>
          </div>
        </section>

        <footer v-if="pairing.grounding" class="pairing-footer">
          <p class="grounding">{{ pairing.grounding }}</p>
          <p v-if="pairing.recipeUrl" class="recipe-link">
            From <a :href="withBase(pairing.recipeUrl)">{{ pairing.recipeTask }}</a>
          </p>
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
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 1.25rem;
  margin-top: 1rem;
}

.pairing-card {
  border: 1px solid var(--vp-c-divider);
  border-left-width: 3px;
  border-left-style: solid;
  border-radius: var(--wk-radius-panel, 8px);
  background: var(--vp-c-bg-soft);
  padding: 1.1rem 1.3rem 1.3rem;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.pairing-header {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.pairing-name {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.5;
}

.pairing-name code {
  font-size: 0.85em;
}

.pairing-name .plus {
  color: var(--vp-c-text-3);
  margin: 0 0.15rem;
}

.pairing-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.badge {
  border-radius: 999px;
  padding: 0.05rem 0.6rem;
  font-size: 0.72rem;
  border: 1px solid var(--vp-c-divider);
  color: var(--vp-c-text-2);
}

.badge-source[data-source='superpowers'] {
  border-color: var(--vp-c-divider);
  background: transparent;
  color: var(--vp-c-text-1);
}
.dark .badge-source[data-source='superpowers'] {
  border-color: var(--wk-muted);
  color: var(--wk-text);
}

.badge-source[data-source='claude-plugins-official'] {
  border-color: var(--wk-silica);
  background: rgba(52, 138, 217, 0.08);
  color: var(--vp-c-text-1);
}
.dark .badge-source[data-source='claude-plugins-official'] {
  background: rgba(52, 138, 217, 0.14);
  color: var(--wk-text);
}

.pairing-section h4 {
  margin: 0 0 0.3rem;
  font-size: 0.78rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--vp-c-text-3);
}

.pairing-section p {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.5;
}

.pairing-prompt {
  margin: 0;
  border-left: 3px solid var(--vp-c-brand-1);
  border-radius: var(--wk-radius-sm, 4px);
  padding: 0.4rem 0.75rem;
  background: var(--vp-c-bg-alt);
}
.dark .pairing-prompt {
  border-left-color: var(--wk-accent);
}

.pairing-prompt p {
  font-size: 0.88rem;
  font-style: italic;
}

.pairing-dos-donts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.pairing-dos-donts h4 {
  padding-left: 0.6rem;
  border-left: 2px solid var(--wk-status-good);
}

.donts h4 {
  border-left-color: var(--wk-status-bad);
}

.pairing-dos-donts ul {
  margin: 0;
  padding-left: 1.1rem;
  font-size: 0.85rem;
  line-height: 1.45;
  color: var(--vp-c-text-2);
}

.pairing-dos-donts li + li {
  margin-top: 0.35rem;
}

.pairing-footer {
  border-top: 1px solid var(--vp-c-divider);
  padding-top: 0.6rem;
  margin-top: 0.1rem;
}

.pairing-footer p {
  margin: 0;
}

.grounding {
  font-size: 0.82rem;
  color: var(--vp-c-text-3);
}

.recipe-link {
  font-size: 0.82rem;
  margin-top: 0.3rem !important;
}

/* One aerogel chemistry per beat, same technique werkstoff.css already uses
   for the catalog's category colors: base step for the border, a low-alpha
   tint for the card background, -light in dark mode / -deep in light mode
   for anything read as text (both verified to clear 4.5:1 in werkstoff.css's
   own header comment). Beat is never conveyed by color alone: the label text
   in the badge and the filter button stays regardless of this card's hue. */
.pairing-card[data-beat='inspect'] {
  border-left-color: var(--wk-silica);
  background: rgba(52, 138, 217, 0.05);
}
.dark .pairing-card[data-beat='inspect'] {
  background: rgba(52, 138, 217, 0.1);
}

.pairing-card[data-beat='split'] {
  border-left-color: var(--wk-chromia);
  background: rgba(8, 147, 92, 0.05);
}
.dark .pairing-card[data-beat='split'] {
  background: rgba(8, 147, 92, 0.1);
}

.pairing-card[data-beat='execute'] {
  border-left-color: var(--wk-neodymia);
  background: rgba(171, 109, 198, 0.05);
}
.dark .pairing-card[data-beat='execute'] {
  background: rgba(171, 109, 198, 0.1);
}

.pairing-card[data-beat='verify'] {
  border-left-color: var(--wk-samaria);
  background: rgba(171, 143, 0, 0.05);
}
.dark .pairing-card[data-beat='verify'] {
  background: rgba(171, 143, 0, 0.1);
}

@media (max-width: 520px) {
  .pairing-dos-donts {
    grid-template-columns: 1fr;
  }
}
</style>
