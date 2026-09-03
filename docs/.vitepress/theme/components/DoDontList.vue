<script setup>
// The do/don't renderer, extracted out of PairingCards.vue (the only place
// it existed before this component) so RecipeBeats.vue's per-recipe
// `dos`/`donts` frontmatter can render with the exact same markup and marks
// instead of a second, divergent copy.
defineProps({
  dos: { type: Array, default: () => [] },
  donts: { type: Array, default: () => [] },
})
</script>

<template>
  <div class="dd-row">
    <ul class="do">
      <li v-for="(item, i) in dos" :key="i">
        <span class="mark" aria-hidden="true">&check;</span>{{ item }}
      </li>
    </ul>
    <ul class="dont">
      <li v-for="(item, i) in donts" :key="i">
        <span class="mark" aria-hidden="true">&times;</span>{{ item }}
      </li>
    </ul>
  </div>
</template>

<style scoped>
.dd-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.5rem 1.5rem;
  border-top: 1px solid var(--vp-c-divider);
  padding: 0.85rem 0;
}

.dd-row ul {
  list-style: none;
  margin: 0;
  padding: 0;
  font-size: 0.85rem;
  color: var(--vp-c-text-2);
}

.dd-row li {
  display: flex;
  gap: 0.5rem;
  line-height: 1.45;
}
.dd-row li + li {
  margin-top: 0.5rem;
}

.mark {
  flex: none;
  font-weight: 700;
  width: 1.1em;
  text-align: center;
}
.do .mark {
  color: var(--wk-status-good);
}
.dont .mark {
  color: var(--wk-status-bad);
}

@media (max-width: 480px) {
  .dd-row {
    grid-template-columns: 1fr;
  }
}
</style>
