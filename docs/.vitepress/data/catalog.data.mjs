import { createContentLoader } from 'vitepress'
import { CATEGORY_ORDER } from './catalog.categories.mjs'

function categoryRank(category) {
  const index = CATEGORY_ORDER.indexOf(category)
  return index === -1 ? CATEGORY_ORDER.length : index
}

// docs/catalog/index.md and docs/catalog/_UNRESOLVED.md carry no `category`
// frontmatter field, so filtering on its presence excludes them without
// hand-naming either file.
export default createContentLoader('catalog/**/*.md', {
  transform(rawData) {
    return rawData
      .filter((page) => page.frontmatter && page.frontmatter.category)
      .map((page) => ({
        url: page.url,
        task: page.frontmatter.task,
        category: page.frontmatter.category,
        summary: page.frontmatter.summary,
        external: page.frontmatter.external ?? [],
        // Consumed by BeatSkillRefs.vue, which inverts this array across
        // every recipe (skill -> the recipes that place it in a beat) to
        // render "also in N other recipes" on the recipe page itself. Kept
        // as the raw per-recipe list here, not pre-inverted, because the
        // inversion is cheap (a few hundred entries total) and doing it at
        // the single call site keeps this loader's output shape identical
        // to what a recipe's own frontmatter already asserts.
        skills: Array.isArray(page.frontmatter.beats)
          ? page.frontmatter.beats.map((b) => b.skill)
          : [],
        beatCount: Array.isArray(page.frontmatter.beats) ? page.frontmatter.beats.length : 0,
      }))
      .sort((a, b) => {
        const categoryDiff = categoryRank(a.category) - categoryRank(b.category)
        if (categoryDiff !== 0) return categoryDiff
        return a.task.localeCompare(b.task)
      })
  },
})
