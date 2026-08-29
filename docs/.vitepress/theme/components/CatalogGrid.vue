<script setup>
import { computed, reactive } from 'vue'
import { withBase } from 'vitepress'
import { data as recipes } from '../../data/catalog.data.mjs'
import { CATEGORY_ORDER, CATEGORY_LABELS } from '../../data/catalog.categories.mjs'

// Present in fixed order, but only for categories that actually have at
// least one recipe -- a category with zero recipes would otherwise render
// a dead filter button.
const categories = CATEGORY_ORDER.filter((category) =>
  recipes.some((recipe) => recipe.category === category),
)

const EXTERNAL_FILTERS = [
  { key: 'none', label: 'werkstoff only' },
  { key: 'superpowers', label: 'superpowers' },
  { key: 'claude-plugins-official', label: 'claude-plugins-official' },
]

// No filter active in either group by default, so the first render (SSR and
// pre-hydration alike) shows every recipe -- the filter buttons are a
// progressive enhancement layered on top of content that already exists.
const activeCategory = reactive({ value: null })
const activeExternals = reactive(new Set())

function toggleCategory(category) {
  activeCategory.value = activeCategory.value === category ? null : category
}

function toggleExternal(key) {
  if (activeExternals.has(key)) {
    activeExternals.delete(key)
  } else {
    activeExternals.add(key)
  }
}

function matchesExternal(recipe) {
  if (activeExternals.size === 0) return true
  // A recipe should show under EITHER active external filter it matches --
  // OR, not AND -- since a recipe can legitimately carry both tags.
  for (const key of activeExternals) {
    if (key === 'none' && recipe.external.length === 0) return true
    if (key !== 'none' && recipe.external.includes(key)) return true
  }
  return false
}

const filteredRecipes = computed(() =>
  recipes.filter((recipe) => {
    if (activeCategory.value && recipe.category !== activeCategory.value) return false
    return matchesExternal(recipe)
  }),
)
</script>

<template>
  <div class="catalog-grid">
    <div class="catalog-filters">
      <div class="filter-group" role="group" aria-label="Filter by category">
        <button
          v-for="category in categories"
          :key="category"
          type="button"
          class="filter-button"
          :aria-pressed="activeCategory.value === category"
          @click="toggleCategory(category)"
        >
          {{ CATEGORY_LABELS[category] ?? category }}
        </button>
      </div>

      <div class="filter-group" role="group" aria-label="Filter by external pairing">
        <button
          v-for="ext in EXTERNAL_FILTERS"
          :key="ext.key"
          type="button"
          class="filter-button"
          :aria-pressed="activeExternals.has(ext.key)"
          @click="toggleExternal(ext.key)"
        >
          {{ ext.label }}
        </button>
      </div>
    </div>

    <p class="result-count" aria-live="polite">
      {{ filteredRecipes.length }} of {{ recipes.length }} recipes
    </p>

    <div class="recipe-list">
      <article
        v-for="recipe in filteredRecipes"
        :key="recipe.url"
        class="recipe-card"
        :data-category="recipe.category"
      >
        <h3 class="recipe-task">
          <a :href="withBase(recipe.url)">{{ recipe.task }}</a>
        </h3>
        <p class="recipe-summary">{{ recipe.summary }}</p>
        <p class="recipe-meta">
          {{ recipe.beatCount }} beat<span v-if="recipe.beatCount !== 1">s</span>
        </p>
        <div v-if="recipe.external.length" class="ext-badges">
          <span
            v-for="tag in recipe.external"
            :key="tag"
            class="ext-badge"
            :data-external="tag"
            >{{ tag }}</span
          >
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.catalog-filters {
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

.recipe-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1rem;
}

.recipe-card {
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 1rem 1.25rem;
}

.recipe-task {
  margin: 0 0 0.5rem;
  font-size: 1rem;
}

.recipe-summary {
  color: var(--vp-c-text-2);
  font-size: 0.9rem;
  margin: 0 0 0.5rem;
}

.recipe-meta {
  font-size: 0.8rem;
  color: var(--vp-c-text-3);
  margin: 0 0 0.5rem;
}

.ext-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.35rem;
}

.ext-badge {
  border: 1px solid var(--vp-c-divider);
  border-radius: 999px;
  padding: 0.05rem 0.6rem;
  font-size: 0.75rem;
}
</style>
