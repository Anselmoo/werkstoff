<script setup>
import { useData } from 'vitepress'

// Placed at the top of each recipe's markdown BODY as `<RecipeHeader />`, so
// the title and lead sit above the prose and inside <main>. See theme/index.js
// for why a layout slot is not used.
//
// Recipe pages carry their title in frontmatter `task:` and previously rendered
// no <h1> at all -- measured, not assumed: the rendered page reported
// `document.querySelectorAll('.VPDoc h1').length === 0`. VitePress does not
// synthesise a heading from frontmatter, so without this the sidebar knew the
// recipe's name and the page itself never stated it.
//
// Inert on any page whose frontmatter carries no `task`; a recipe that omits
// the component fails CI via tools/catalog-validator/validate_catalog.py.
const { frontmatter } = useData()
</script>

<template>
  <div v-if="frontmatter.task" class="recipe-header vp-doc">
    <h1>{{ frontmatter.task }}</h1>
    <p v-if="frontmatter.summary" class="recipe-summary">{{ frontmatter.summary }}</p>
    <p v-if="frontmatter.external && frontmatter.external.length" class="recipe-external">
      <span class="recipe-external-label">Also uses</span>
      <code v-for="name in frontmatter.external" :key="name">{{ name }}</code>
    </p>
  </div>
</template>

<style scoped>
.recipe-header {
  margin-bottom: 1.5rem;
}

.recipe-summary {
  color: var(--vp-c-text-2);
  font-size: 1.05em;
  line-height: 1.7;
  margin-top: 0.5rem;
}

.recipe-external {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
}

.recipe-external-label {
  font-size: 0.8em;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--vp-c-text-3);
}

.recipe-external code {
  font-size: 0.85em;
}
</style>
