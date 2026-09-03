<script setup>
import { computed } from 'vue'
import { useData } from 'vitepress'
import CopyButton from './CopyButton.vue'
import DoDontList from './DoDontList.vue'
import BeatSkillRefs from './BeatSkillRefs.vue'
import PromptFence from './PromptFence.vue'
import { useClipboardCopy } from '../composables/useClipboardCopy'

// Placed in each recipe's markdown BODY as `<RecipeBeats />`, not mounted in a
// VitePress layout slot. theme/index.js carries the full rationale for why no
// slot works here; the short version is that `doc-after` renders below the
// prev/next footer (which is how 37 recipes shipped with their Beats under the
// navigation) and `doc-footer-before` renders inside a contentinfo <footer>.
// Only a body mount lands inside <main>.
//
// Because a missing component renders nothing at all and raises no error,
// tools/catalog-validator/validate_catalog.py fails CI when a recipe body omits
// it -- that check is what makes body mounting safe rather than forgettable.
//
// `openingPrompt`, `dos` and `donts` are OPTIONAL recipe frontmatter keys, each
// independently guarded, so a recipe carrying any subset of the three renders
// exactly as it did before they existed.
const { frontmatter } = useData()

// Shared with PairingCards.vue's per-card copy buttons -- see
// ../composables/useClipboardCopy.js for the clipboard-write-with-fallback
// logic itself. This page has exactly one copy button, so a single fixed
// sentinel id stands in for the per-pairing id PairingCards uses.
const { copiedId, failedId, copy } = useClipboardCopy()
const OPENING_PROMPT_ID = 'opening-prompt'
const openingPromptStatus = computed(() => {
  if (copiedId.value === OPENING_PROMPT_ID) return 'copied'
  if (failedId.value === OPENING_PROMPT_ID) return 'failed'
  return 'idle'
})
function copyOpeningPrompt(event) {
  copy(OPENING_PROMPT_ID, frontmatter.value.openingPrompt, event)
}

const hasDosOrDonts = computed(
  () => (frontmatter.value.dos?.length ?? 0) > 0 || (frontmatter.value.donts?.length ?? 0) > 0,
)

// "Which plugins do I need installed for this recipe?" -- answerable from
// data already on the page (beats[].skill's `plugin:skill` namespace) and,
// per the infodesign brief's cold read (docs/orchestration/README.md 1.3),
// currently answered nowhere on the site. Order preserves first-appearance
// order in the beats list rather than sorting alphabetically, so it reads
// left-to-right the same way the beats do below it.
const pluginRequirements = computed(() => {
  const seen = []
  for (const beat of frontmatter.value.beats ?? []) {
    const namespace = beat.skill?.split(':')[0]
    if (namespace && !seen.includes(namespace)) seen.push(namespace)
  }
  return seen
})
</script>

<template>
  <div v-if="frontmatter.beats && frontmatter.beats.length" class="recipe-beats vp-doc">
    <template v-if="frontmatter.openingPrompt">
      <h2 id="start-here">Start here</h2>
      <div class="opening-prompt" data-copy-scope>
        <div class="opening-prompt-head">
          <span class="row-label">One prompt to start</span>
          <CopyButton :status="openingPromptStatus" @click="copyOpeningPrompt" />
        </div>
        <pre class="opening-prompt-code" data-copy-target><code>{{ frontmatter.openingPrompt }}</code></pre>
      </div>
    </template>

    <p v-if="pluginRequirements.length" class="plugin-requirements">
      <span class="row-label">Needs</span>
      <span class="requirements-list">
        <template v-for="(namespace, i) in pluginRequirements" :key="namespace"
          ><code>{{ namespace }}</code
          ><span v-if="i < pluginRequirements.length - 1">, </span></template
        >
      </span>
    </p>

    <h2 id="beats">Beats</h2>
    <p class="beats-lead">
      Run these in order. Each prompt is copy-pasteable straight into Claude Code.
    </p>

    <ol class="beats-list">
      <li v-for="(beat, index) in frontmatter.beats" :key="`${beat.skill}-${index}`" class="beat">
        <BeatSkillRefs :skill="beat.skill" />
        <p class="beat-why">{{ beat.why }}</p>
        <!--
          Demoted, not deleted: the per-beat prompt stays in the DOM (a closed
          <details> still renders its text for in-page find and the local search
          index) but no longer competes with the opening prompt for "which of
          these do I paste?". The summary names the job rather than saying "Show
          more" -- this prompt is for running the beat standalone, a real and
          different use from the opening prompt.

          The body is a PromptFence, not a blockquote: prompts render as real
          `language-prompt` code fences, the convention werkstoff.css calls the
          docs' signature element, and that is what carries a working copy
          button. Native <details>/<summary> keeps it keyboard-operable and
          screen-reader-announced with no ARIA of our own.
        -->
        <details v-if="beat.prompt" class="disclosure beat-prompt-disclosure">
          <summary>Run this beat on its own</summary>
          <PromptFence :text="beat.prompt" />
        </details>
      </li>
    </ol>

    <template v-if="frontmatter.grounding">
      <h2 id="worked-example">Worked example</h2>
      <!--
        Demoted for the same reason as the per-beat prompts: `grounding` is
        20-minute material (a rationale for the beat order, sometimes a note
        about this repo's own internals rather than a runnable example) that
        was rendering at 2-minute depth. The summary says what it actually
        is -- "Grounded in" -- rather than promising a worked example the
        field does not always keep.
      -->
      <details class="disclosure grounding-disclosure">
        <summary>Grounded in — why this beat order is trustworthy</summary>
        <p class="grounding">{{ frontmatter.grounding }}</p>
      </details>
    </template>

    <template v-if="hasDosOrDonts">
      <h2 id="do-dont">Do / Don't</h2>
      <DoDontList :dos="frontmatter.dos ?? []" :donts="frontmatter.donts ?? []" />
    </template>
  </div>
</template>

<style scoped>
.recipe-beats {
  margin-top: 2.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid var(--vp-c-divider);
}

.beats-lead {
  color: var(--vp-c-text-2);
  margin-top: 0.5rem;
}

/* Counter-driven numbering rather than a plain <ol> marker: the step number is
 * the one piece of information a reader scanning a fixed chain needs first, and
 * a default marker sits too far from the skill id to read as a sequence. */
.beats-list {
  list-style: none;
  padding-left: 0;
  counter-reset: beat;
}

.beat {
  counter-increment: beat;
  position: relative;
  padding-left: 2.5rem;
  margin-bottom: 1.75rem;
}

.beat::before {
  content: counter(beat);
  position: absolute;
  left: 0;
  top: 0.1rem;
  width: 1.75rem;
  height: 1.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--vp-c-default-soft);
  color: var(--vp-c-text-1);
  font-size: 0.85rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.beat-skill {
  margin: 0;
}

.beat-why {
  color: var(--vp-c-text-2);
  margin: 0.35rem 0 0.6rem;
}

.grounding {
  color: var(--vp-c-text-2);
  margin: 0.5rem 0 0;
}

/* Shared by the per-beat prompt disclosure and the grounding disclosure.
   Kept visually quiet -- no border, no background -- so a closed summary
   reads as a small text affordance next to `beat-why`/the "Worked example"
   heading rather than as a competing card. */
.disclosure > summary {
  cursor: pointer;
  color: var(--vp-c-text-3);
  font-size: 0.85rem;
  list-style-position: outside;
}
.disclosure > summary:hover {
  color: var(--vp-c-text-2);
}
.disclosure > summary:focus-visible {
  outline: 2px solid var(--vp-c-brand-1);
  outline-offset: 2px;
}

.beat-prompt-disclosure {
  margin-top: 0.4rem;
}

.grounding-disclosure > summary {
  margin-top: 0.5rem;
}

.plugin-requirements {
  margin: 0 0 1.5rem;
}

.requirements-list code {
  font-size: 0.85em;
}
.requirements-list code:not(:first-child) {
  margin-left: 0.15rem;
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

.opening-prompt {
  margin: 1rem 0 1.75rem;
}

.opening-prompt-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem;
}

.opening-prompt-code {
  margin: 0.5rem 0 0;
  border-left: 3px solid var(--wk-samaria);
  background: rgba(207, 182, 86, 0.1);
  border-radius: var(--wk-radius-sm, 4px);
  padding: 0.6rem 0.85rem;
  overflow-x: auto;
  white-space: pre-wrap;
}
.dark .opening-prompt-code {
  border-left-color: var(--wk-samaria-light);
  background: rgba(207, 182, 86, 0.08);
}

.opening-prompt-code code {
  font-size: 0.86rem;
  font-family: var(--vp-font-family-mono);
  color: var(--vp-c-text-1);
  background: none;
  padding: 0;
}

/* The fence carries its own accent border from werkstoff.css; pull it back in
 * line with the step column so the chain reads as one left edge. */
.beat :deep(div[class*='language-']) {
  margin: 0.5rem 0 0;
}
</style>
