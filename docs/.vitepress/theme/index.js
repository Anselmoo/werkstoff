import { h } from 'vue'
import DefaultTheme from 'vitepress/theme'
import './werkstoff.css'
import RecipeBeats from './components/RecipeBeats.vue'
import CatalogGrid from './components/CatalogGrid.vue'
import PairingCards from './components/PairingCards.vue'

export default {
  extends: DefaultTheme,
  Layout() {
    return h(DefaultTheme.Layout, null, {
      'doc-after': () => h(RecipeBeats),
    })
  },
  enhanceApp({ app }) {
    app.component('CatalogGrid', CatalogGrid)
    app.component('PairingCards', PairingCards)
  },
}
