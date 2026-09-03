/**
 * One predicate, three consumers: DocEnd.vue (the terminal node), useBreathers.js
 * (the injected breathers), and config.mjs's transformPageData(), which is where
 * it actually runs.
 *
 * A "prose page" is one whose reading experience is decided by prose rhythm
 * rather than by a Vue component. The distinction is load-bearing rather than
 * cosmetic: RecipeBeats.vue is injected globally through the same `doc-after`
 * slot the terminal node uses, so an unscoped node lands in the MIDDLE of all
 * 37 recipe pages -- before the beats, not after the document.
 *
 * The four signals below are the same ones the components themselves gate on,
 * and they are deliberately identical to test/docs/docs_ux_audit.py's
 * is_component_rendered(). C4's wiring assertion in that file cross-checks the
 * two sides against each other; they must not drift apart independently.
 *
 *   layout    -- anything other than the default/'doc' (docs/index.md -> 'home')
 *   beats     -- RecipeBeats.vue's own v-if guard; 25 catalog recipes
 *   pairings  -- PairingCards.vue's data source; orchestration/references/pairings.md
 *   body tags -- a globally registered component invoked in the markdown body.
 *                docs/catalog/index.md carries NONE of the frontmatter keys
 *                above and is still a component page, because its body is
 *                `<CatalogGrid />`. Frontmatter alone cannot see that, which is
 *                why the predicate takes the body too and why it is evaluated
 *                at build time (see config.mjs) rather than in the browser.
 */

/**
 * Globally registered component tags whose presence in a page BODY means the
 * page belongs to a component, not to prose.
 *
 * This list must cover every component registered in theme/index.js's
 * enhanceApp(). It is not derived from that file at runtime because the theme
 * entry imports this module, not the other way round -- so the invariant is
 * enforced from outside instead: docs_ux_audit.py reads enhanceApp()'s
 * `app.component('X', ...)` calls live and fails C4 if any registered tag is
 * missing here. Registering a component without listing it here would silently
 * mis-scope both marks on that page; the audit is what stops that being silent.
 */
export const COMPONENT_TAGS = ['CatalogGrid', 'PairingCards']

/**
 * @param {Record<string, unknown>} frontmatter parsed page frontmatter
 * @param {string|null} body raw markdown body, when available. Passing null
 *   evaluates only the frontmatter half of the predicate -- correct for a
 *   caller that genuinely has no body, wrong for one that does.
 * @returns {boolean} true when the page is prose the long-page treatment owns
 */
export function isProsePage(frontmatter, body = null) {
  const fm = frontmatter ?? {}
  if (fm.layout != null && fm.layout !== 'doc') return false
  if (fm.beats) return false
  if (fm.pairings) return false
  if (typeof body === 'string') {
    // Anchored to `<Tag` followed by a word boundary. Deliberately not a
    // pattern spanning the whole body -- see CLAUDE.md's defect table on
    // regexes that look correct and silently match nothing.
    for (const tag of COMPONENT_TAGS) {
      if (new RegExp(`<${tag}\\b`).test(body)) return false
    }
  }
  return true
}

/**
 * The frontmatter key config.mjs's transformPageData() stamps the verdict into,
 * and the only thing the browser-side consumers are allowed to read. They must
 * NOT re-derive the predicate from frontmatter alone as a fallback: the body
 * half is unavailable in the browser, so a fallback would quietly put the
 * terminal node on docs/catalog/index.md. Absent stamp => not prose => no mark.
 * That is failing closed; the audit's wiring assertion is the escape hatch that
 * names it if the stamp ever stops being written.
 */
export const PROSE_PAGE_KEY = 'wkProsePage'
