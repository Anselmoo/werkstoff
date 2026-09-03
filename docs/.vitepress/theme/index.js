import DefaultTheme from 'vitepress/theme'
import './werkstoff.css'
import RecipeHeader from './components/RecipeHeader.vue'
import RecipeBeats from './components/RecipeBeats.vue'
import CatalogGrid from './components/CatalogGrid.vue'
import PairingCards from './components/PairingCards.vue'

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
  enhanceApp({ app }) {
    app.component('RecipeHeader', RecipeHeader)
    app.component('RecipeBeats', RecipeBeats)
    app.component('CatalogGrid', CatalogGrid)
    app.component('PairingCards', PairingCards)
  },
}
