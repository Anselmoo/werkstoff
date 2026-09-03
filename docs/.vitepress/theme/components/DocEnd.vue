<script setup>
/**
 * The terminal node: the gold node of the logo mark, alone, once per prose page,
 * at the one place on a page where the mark's own meaning -- the stroke has
 * terminated -- is literally true. See werkstoff.css's `.wk-doc-end` block for
 * why it is not stamped at every h2, and for the contrast measurements.
 *
 * Two things this component owes that file, both enforced here:
 *   1. the element carries class `wk-doc-end`;
 *   2. it renders NOTHING unless the page is prose.
 *
 * (2) is the whole reason this component exists rather than a `::after` on
 * `.vp-doc`. RecipeBeats.vue is injected through the same `doc-after` slot, so
 * an unscoped node lands before the beats -- in the middle of all 37 recipe
 * pages, which is precisely where the mark's meaning is false.
 *
 * The verdict is NOT recomputed here. It is stamped at build time by
 * config.mjs's transformPageData(), which is the only place the markdown body
 * is readable -- and the body is what identifies docs/catalog/index.md, whose
 * frontmatter is indistinguishable from prose but whose body is `<CatalogGrid />`.
 * Reading the stamp with a strict `=== true` fails CLOSED: if the stamp ever
 * stops being written the mark disappears everywhere, loudly, rather than
 * appearing in the wrong place quietly. docs_ux_audit.py's C4 wiring assertion
 * is the named escape hatch that reports it.
 *
 * aria-hidden + role="presentation" + no text: a screen reader announces
 * nothing. The document already ends; this only says so visually.
 */
import { computed } from 'vue'
import { useData } from 'vitepress'
import { PROSE_PAGE_KEY } from '../composables/useProsePage.js'

const { frontmatter } = useData()

const isProse = computed(() => frontmatter.value?.[PROSE_PAGE_KEY] === true)
</script>

<template>
  <div v-if="isProse" class="wk-doc-end" aria-hidden="true" role="presentation" />
</template>
