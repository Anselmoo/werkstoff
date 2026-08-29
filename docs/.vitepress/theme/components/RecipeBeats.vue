<script setup>
import { useData } from 'vitepress'

// Injected globally via the `doc-after` slot (see theme/index.js) so it
// renders after every page's markdown body. It must stay inert on any page
// whose frontmatter carries no `beats` -- that's what makes global injection
// safe rather than recipe-page-only.
const { frontmatter } = useData()
</script>

<template>
  <div v-if="frontmatter.beats && frontmatter.beats.length" class="recipe-beats vp-doc">
    <h2 id="beats">Beats</h2>
    <ol class="beats-list">
      <li v-for="(beat, index) in frontmatter.beats" :key="`${beat.skill}-${index}`" class="beat">
        <p class="beat-skill"><code>{{ beat.skill }}</code></p>
        <p class="beat-why">{{ beat.why }}</p>
        <blockquote v-if="beat.prompt" class="beat-prompt">
          <p>{{ beat.prompt }}</p>
        </blockquote>
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

.beat-skill code {
  font-size: 0.95em;
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
}
</style>
