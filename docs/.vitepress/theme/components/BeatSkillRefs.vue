<script setup>
import { computed } from 'vue'
import { withBase, useData } from 'vitepress'
import { data as recipes } from '../../data/catalog.data.mjs'

// Renders one beat's skill id as a cross-reference into the rest of the
// catalog, using the `skills` array catalog.data.mjs already computes
// (lines 22-24) and no component read before this one. See "The reveal" in
// the infodesign brief: `andon:andon-verify` alone appears in 14 of 37
// recipes, and 21 skills span more than one category -- the strongest
// evidence a beat is trustworthy is that unrelated tasks reach for the same
// skill at the same moment, and a reader standing on one recipe had no way
// to find that out.
const props = defineProps({ skill: { type: String, required: true } })
const { page } = useData()

// Inverted at module scope, once per page load (not once per beat -- every
// <BeatSkillRefs> on the page shares this same Map instance). 37 recipes x
// a handful of skills each is trivial to invert on every render; a
// dedicated data loader would only add a second place this logic could
// drift from catalog.data.mjs's own shape.
const bySkill = new Map()
for (const recipe of recipes) {
  for (const skill of recipe.skills) {
    if (!bySkill.has(skill)) bySkill.set(skill, [])
    bySkill.get(skill).push(recipe)
  }
}

// page.relativePath is "catalog/<category>/<file>.md"; recipe.url is
// "/catalog/<category>/<file>" under this site's cleanUrls: true config.
// Compare on the normalised path, never on task text, which carries no
// uniqueness guarantee.
const currentUrl = computed(() => '/' + page.value.relativePath.replace(/\.md$/, ''))

const others = computed(() => (bySkill.get(props.skill) ?? []).filter((r) => r.url !== currentUrl.value))
</script>

<template>
  <!-- A skill used nowhere else falls through to the original inert markup
       -- no disclosure opens onto an empty list. -->
  <p v-if="!others.length" class="beat-skill"><code>{{ skill }}</code></p>
  <details v-else class="beat-skill skill-refs">
    <summary>
      <code>{{ skill }}</code>
      <span class="ref-count"
        >also in {{ others.length }} other recipe<span v-if="others.length !== 1">s</span></span
      >
    </summary>
    <ul>
      <li v-for="other in others" :key="other.url">
        <a :href="withBase(other.url)">{{ other.task }}</a>
      </li>
    </ul>
  </details>
</template>

<style scoped>
/* Matches the plain-text sizing the inert (no-cross-references) branch used
   before this component existed, so a skill that happens to be unique
   doesn't visually shift relative to one that isn't. */
.beat-skill code {
  font-size: 0.95em;
}

.skill-refs {
  margin: 0;
}
.skill-refs > summary {
  cursor: pointer;
  list-style-position: outside;
}
.skill-refs > summary:focus-visible {
  outline: 2px solid var(--vp-c-brand-1);
  outline-offset: 2px;
}
.ref-count {
  margin-left: 0.5rem;
  font-size: 0.78rem;
  color: var(--vp-c-text-3);
}
.skill-refs ul {
  margin: 0.35rem 0 0;
  padding-left: 1.5rem;
  font-size: 0.88rem;
}
</style>
