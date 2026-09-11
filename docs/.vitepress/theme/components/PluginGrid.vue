<script setup>
import { withBase } from 'vitepress'

// Static, not a data loader: eleven plugins, added by hand when a plugin ships,
// same reasoning CatalogGrid.vue gives for reading straight off the
// filesystem -- except here there IS no per-plugin frontmatter to aggregate
// (docs/plugins/<name>.md is a one-line @include stub), so a loader would
// just re-encode this exact list from a second source. One list, hand-kept.
const PLUGINS = [
  {
    name: 'self-assess',
    url: '/plugins/self-assess',
    summary:
      'Codebase self-assessment: stage/wire mapping, docs-vs-code drift, CI/CD topology, house-rules enforcement, multi-repo dashboard.',
  },
  {
    name: 'confab',
    url: '/plugins/confab',
    summary:
      'Catches AI confabulation: hallucinated dependencies, assertion-less tests, contract drift, unreliable agentic loops.',
  },
  {
    name: 'compass',
    url: '/plugins/compass',
    summary:
      'A prompt-engineering technique library composed by compass-solve into a clarify → explore → decompose → execute → revise pipeline.',
  },
  {
    name: 'cupertino',
    url: '/plugins/cupertino',
    summary: 'A Steve-Jobs-grounded design and craft discipline for a project’s whole lifecycle.',
  },
  {
    name: 'andon',
    url: '/plugins/andon',
    summary:
      'An evidence-grounded harden-and-advance loop: propose maximally, verify adversarially, never advance past an unproven wire.',
  },
  {
    name: 'cli-scaffold',
    url: '/plugins/cli-scaffold',
    summary: 'Scaffolds production-grade CLIs across 12 languages against a frozen five-pillar doctrine.',
  },
  {
    name: 'codebase-consistency',
    url: '/plugins/codebase-consistency',
    summary: 'Harmonizes undocumented pattern variants in an already-modern, live codebase.',
  },
  {
    name: 'takt',
    url: '/plugins/takt',
    summary: 'Enforces declared beat order at the tool-call layer; inert until a repo declares its beats.',
  },
  {
    name: 'lehre',
    url: '/plugins/lehre',
    summary: 'Researches a code style, pattern and architecture doctrine, then denies the write that would violate it.',
  },
  {
    name: 'nacharbeit',
    url: '/plugins/nacharbeit',
    summary: 'Reworks a Claude Code plugin to the Anthropic standard: a calibrated review of seven surfaces, then a locked, blind-verified fix pass.',
  },
  {
    name: 'vorbild',
    url: '/plugins/vorbild',
    summary:
      'Derives a named, platform-neutral design system from reference exemplars \u2014 measured, graded for trust and rights, then emitted to any target.',
  },
]
</script>

<template>
  <div class="plugin-grid">
    <a
      v-for="p in PLUGINS"
      :key="p.name"
      class="plugin-card"
      :href="withBase(p.url)"
    >
      <h3 class="plugin-name"><code>{{ p.name }}</code></h3>
      <p class="plugin-summary">{{ p.summary }}</p>
    </a>
  </div>
</template>

<style scoped>
/* Same card recipe CatalogGrid.vue's `.recipe-card` already proved -- a
   reader who just saw that grid should recognise this as the same kind of
   object, not a third visual language on one page. */
.plugin-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1rem;
  margin: 1.5rem 0;
}

.plugin-card {
  display: block;
  border: 1px solid var(--vp-c-divider);
  border-radius: 12px;
  padding: 1.1rem 1.25rem;
  background: var(--vp-c-bg-soft);
  color: inherit;
  text-decoration: none;
  transition: border-color var(--wk-transition-fast, 120ms ease), transform var(--wk-transition-fast, 120ms ease);
}

.plugin-card:hover,
.plugin-card:focus-visible {
  border-color: var(--vp-c-brand-1);
  transform: translateY(-2px);
}

@media (prefers-reduced-motion: reduce) {
  .plugin-card {
    transition: border-color var(--wk-transition-fast, 120ms ease);
  }
  .plugin-card:hover,
  .plugin-card:focus-visible {
    transform: none;
  }
}

.plugin-name {
  margin: 0 0 0.5rem;
  font-size: 1rem;
}

.plugin-name code {
  font-size: 0.95em;
}

.plugin-summary {
  margin: 0;
  color: var(--vp-c-text-2);
  font-size: 0.88rem;
  line-height: 1.55;
}
</style>
