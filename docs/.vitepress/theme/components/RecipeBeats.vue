<script setup>
import { useData } from 'vitepress'
import PromptFence from './PromptFence.vue'

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
const { frontmatter } = useData()
</script>

<template>
  <div v-if="frontmatter.beats && frontmatter.beats.length" class="recipe-beats vp-doc">
    <h2 id="beats">Beats</h2>
    <p class="beats-lead">
      Run these in order. Each prompt is copy-pasteable straight into Claude Code.
    </p>

    <ol class="beats-list">
      <li v-for="(beat, index) in frontmatter.beats" :key="`${beat.skill}-${index}`" class="beat">
        <p class="beat-skill"><code>{{ beat.skill }}</code></p>
        <p class="beat-why">{{ beat.why }}</p>
        <PromptFence v-if="beat.prompt" :text="beat.prompt" />
      </li>
    </ol>

    <template v-if="frontmatter.grounding">
      <h2 id="worked-example">Worked example</h2>
      <p class="grounding">{{ frontmatter.grounding }}</p>
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

.beat-skill code {
  font-size: 0.95em;
}

.beat-why {
  color: var(--vp-c-text-2);
  margin: 0.35rem 0 0.6rem;
}

.grounding {
  color: var(--vp-c-text-2);
}

/* The fence carries its own accent border from werkstoff.css; pull it back in
 * line with the step column so the chain reads as one left edge. */
.beat :deep(div[class*='language-']) {
  margin: 0.5rem 0 0;
}
</style>
