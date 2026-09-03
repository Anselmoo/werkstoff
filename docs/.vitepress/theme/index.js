import { defineComponent, h, nextTick, onMounted, watch } from 'vue'
import DefaultTheme from 'vitepress/theme'
import { useData, useRoute } from 'vitepress'
import './werkstoff.css'
import RecipeBeats from './components/RecipeBeats.vue'
import DocEnd from './components/DocEnd.vue'
import CatalogGrid from './components/CatalogGrid.vue'
import PairingCards from './components/PairingCards.vue'
import { applyBreathers, docBlockRoot } from './composables/useBreathers.js'
import { PROSE_PAGE_KEY } from './composables/useProsePage.js'

/**
 * The long-page treatment's host. Both marks hang off this one component:
 * the terminal node through the `doc-after` slot, and the breathers through
 * the two lifecycle hooks below.
 *
 * WHY A COMPONENT AND NOT enhanceApp(): breathers are inserted into the live
 * DOM, and enhanceApp() runs BEFORE the app mounts. Inserting there races
 * hydration, and the failure is silent and destructive rather than merely
 * absent -- a measured run dropped the trailing <ul> of
 * andon-behavior-contract.md from the client DOM entirely (96 top-level blocks
 * live against 97 in the server-rendered HTML) while the page still looked
 * fine. onMounted fires after this component's whole subtree, Content
 * included, has hydrated, so there is nothing left to race.
 *
 * BOTH hooks are required and neither is redundant:
 *   - onMounted covers the first page load, once, after hydration.
 *   - the route watcher covers every subsequent navigation. VitePress is an
 *     SPA; a mount-only version silently does nothing from the second page
 *     onward, which is the failure shape CLAUDE.md catalogues.
 *
 * The route watcher is a watcher rather than router.onAfterRouteChange on
 * purpose: that hook fires before Vue has patched the DOM, and chaining it
 * from enhanceApp() would reintroduce the hydration race on first load. The
 * nextTick below is what puts either path after the patch.
 */
const WerkstoffLayout = defineComponent({
  name: 'WerkstoffLayout',
  setup() {
    const { frontmatter } = useData()
    const route = useRoute()

    const refresh = async () => {
      await nextTick()
      // One macrotask hop, and it is a guarantee rather than a timing guess:
      // app.mount() and the hydration it drives run to completion inside a
      // single task, so anything setTimeout schedules from within that task is
      // ordered strictly after it. nextTick alone is NOT enough here -- it only
      // reaches the end of the current microtask flush, which on first load is
      // still inside hydration. See the hydration note above for what mutating
      // the DOM one beat too early actually did.
      await new Promise((resolve) => setTimeout(resolve, 0))
      applyBreathers(docBlockRoot(), frontmatter.value?.[PROSE_PAGE_KEY] === true)
    }

    onMounted(refresh)
    watch(() => route.path, refresh)

    // The order in the slot is load-bearing: RecipeBeats renders the beat sheet
    // on the 37 recipe pages, DocEnd renders the terminal node on the 16 prose
    // pages, and the two sets are disjoint by construction (isProsePage()
    // returns false for anything carrying `beats`). The node therefore always
    // lands after the document, never in the middle of it.
    return () =>
      h(DefaultTheme.Layout, null, {
        'doc-after': () => [h(RecipeBeats), h(DocEnd)],
      })
  },
})

export default {
  extends: DefaultTheme,
  Layout: WerkstoffLayout,
  enhanceApp({ app }) {
    app.component('CatalogGrid', CatalogGrid)
    app.component('PairingCards', PairingCards)
  },
}
