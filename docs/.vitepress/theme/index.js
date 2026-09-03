import { defineComponent, h, nextTick, onMounted, watch } from 'vue'
import DefaultTheme from 'vitepress/theme'
import { useData, useRoute } from 'vitepress'
import './werkstoff.css'
import RecipeHeader from './components/RecipeHeader.vue'
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

    // RecipeBeats is NOT rendered here -- it is a markdown component now, for
    // the reason the comment below this component explains. Rendering it from a
    // slot as well would emit every recipe's Beats twice.
    //
    // DocEnd uses `doc-footer-before`, not `doc-after`. Both facts below were
    // read out of VPDoc.vue / VPDocFooter.vue, not assumed:
    //   - `doc-after` renders below the WHOLE footer, so the terminal node would
    //     sit under "Edit this page" and prev/next -- marking the end of the
    //     page furniture rather than the end of the document.
    //   - `doc-footer-before` is the first child of <footer class="VPDocFooter">,
    //     i.e. immediately after the prose and before the edit link. Right
    //     visual position.
    //
    // The semantic objection that rules `doc-footer-before` out for RecipeBeats
    // does NOT apply to DocEnd: that objection is that a recipe's own CONTENT
    // would be announced as contentinfo. DocEnd carries aria-hidden="true",
    // role="presentation" and no text, so a screen reader announces nothing at
    // all from it. A purely decorative rule is exactly what may live in a
    // contentinfo landmark.
    //
    // One coupling worth knowing: VPDocFooter is `v-if="showFooter"`. This repo
    // sets lastUpdated and an editLink, so it renders on every doc page -- but a
    // config that turned both off would take the terminal node with it.
    return () =>
      h(DefaultTheme.Layout, null, {
        'doc-footer-before': () => h(DocEnd),
      })
  },
})

// WHY THESE ARE MARKDOWN COMPONENTS AND NOT LAYOUT SLOTS.
//
// RecipeBeats was previously injected globally through the `doc-after` slot,
// which rendered every recipe's Beats BELOW the "Edit this page" link and the
// prev/next buttons. The slot names do not mean what they look like -- VPDoc.vue
// orders its content container as:
//
//     <slot name="doc-before" />         above the body, OUTSIDE <main>
//     <main><Content/></main>            the body
//     <VPDocFooter>                      "Edit this page", prev/next
//       <template #doc-footer-before>    below the body, INSIDE <footer>
//     <slot name="doc-after" />          below the FOOTER
//
// `doc-footer-before` puts it in the right visual place and the wrong semantic
// one: that <footer> is not scoped inside article/aside/main/nav/section, so it
// is a contentinfo landmark, and a recipe's own content would be announced as
// page-footer information. Verified in the rendered DOM, not assumed.
//
// No slot lands inside <main>, because <Content/> fills it. So these are
// registered as global components and placed in each recipe's markdown body,
// which is the only position that is both visually and semantically correct.
// tools/catalog-validator/validate_catalog.py fails the build when a recipe
// omits either one -- a missing component renders nothing at all, and a page
// silently losing its entire Beats section is exactly the class of defect this
// repo's CLAUDE.md is about.
export default {
  extends: DefaultTheme,
  Layout: WerkstoffLayout,
  enhanceApp({ app }) {
    app.component('RecipeHeader', RecipeHeader)
    app.component('RecipeBeats', RecipeBeats)
    app.component('CatalogGrid', CatalogGrid)
    app.component('PairingCards', PairingCards)
  },
}
