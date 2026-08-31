<script setup>
import { computed } from 'vue'
import { useData } from 'vitepress'
import CopyButton from './CopyButton.vue'
import DoDontList from './DoDontList.vue'
import BeatSkillRefs from './BeatSkillRefs.vue'
import { useClipboardCopy } from '../composables/useClipboardCopy'

// Injected globally via the `doc-after` slot (see theme/index.js) so it
// renders after every page's markdown body. It must stay inert on any page
// whose frontmatter carries no `beats` -- that's what makes global injection
// safe rather than recipe-page-only. `openingPrompt`, `dos`, and `donts` are
// all OPTIONAL recipe frontmatter keys nested inside that same outer guard:
// a recipe carrying none of them still renders exactly as it did before
// they existed, and each one's own sub-template is independently guarded so
// a recipe can carry any subset of the three.
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
    <ol class="beats-list">
      <li v-for="(beat, index) in frontmatter.beats" :key="`${beat.skill}-${index}`" class="beat">
        <BeatSkillRefs :skill="beat.skill" />
        <p class="beat-why">{{ beat.why }}</p>
        <!--
          Demoted, not deleted: the per-beat prompt stays in the DOM (closed
          <details> still renders its text for in-page find and the local
          search index) but no longer competes with the opening prompt for
          "which of these do I paste?" -- see infodesign brief S4. The
          summary names the job rather than saying "Show more": this prompt
          is for running the beat on its own, standalone, which is a real
          and different use from the opening prompt (the brief cites
          andon-verify/andon-propose as the standing example of a leaf run
          this way). Native <details>/<summary>: keyboard-operable and
          announced by screen readers with no ARIA required.
        -->
        <details v-if="beat.prompt" class="disclosure beat-prompt-disclosure">
          <summary>Run this beat on its own</summary>
          <blockquote class="beat-prompt">
            <p>{{ beat.prompt }}</p>
          </blockquote>
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
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--vp-c-divider);
}

.beats-list {
  padding-left: 1.25rem;
}

.beat {
  margin-bottom: 1.25rem;
}

.beat-why {
  color: var(--vp-c-text-2);
  margin: 0.25rem 0;
}

.beat-prompt {
  margin: 0.5rem 0 0;
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
</style>
