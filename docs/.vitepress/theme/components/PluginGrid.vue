<script setup>
import { withBase } from 'vitepress'

// Static, not a data loader: twelve plugins, added by hand when a plugin ships,
// same reasoning CatalogGrid.vue gives for reading straight off the
// filesystem -- except here there IS no per-plugin frontmatter to aggregate
// (docs/plugins/<name>.md is a one-line @include stub), so a loader would
// just re-encode this exact list from a second source. One list, hand-kept.
const PLUGINS = [
  {
    name: 'befund',
    url: '/plugins/befund',
    summary:
      'Makes a codebase describe its own health, with every finding tied to file:line evidence, and edits source only behind an authorization recorded on disk.',
  },
  {
    name: 'zeugnis',
    url: '/plugins/zeugnis',
    summary:
      'Audits code that looks right and is not, and counts a finding only after an independent pass has re-checked it.',
  },
  {
    name: 'zirkel',
    url: '/plugins/zirkel',
    summary:
      'Makes sure a complex or ambiguous task is clarified, explored and decomposed before anyone starts executing it.',
  },
  {
    name: 'cupertino',
    url: '/plugins/cupertino',
    summary:
      'A design and craft discipline rooted in Steve Jobs\' documented decisions, run as a fixed lifecycle of stages from experience to ship, not a menu of design techniques.',
  },
  {
    name: 'arbeitsplan',
    url: '/plugins/arbeitsplan',
    summary:
      'Turns a described change into a budgeted workflow, builds it several independent ways at once, and lands exactly one result.',
  },
  {
    name: 'andon',
    url: '/plugins/andon',
    summary:
      'Hardens a repository stage by stage, proving each handoff between stages and halting rather than advancing past one it cannot prove.',
  },
  {
    name: 'cli-scaffold',
    url: '/plugins/cli-scaffold',
    summary:
      'Generates a production-grade command-line application in one of 12 languages, built against one five-pillar architecture doctrine and checked against it before you see it.',
  },
  {
    name: 'passung',
    url: '/plugins/passung',
    summary:
      'Finds a convention your codebase follows two or more valid ways, picks the one that should become canon, and aligns every divergent site to it with a provable equivalence check.',
  },
  {
    name: 'takt',
    url: '/plugins/takt',
    summary:
      'Refuses an edit or dispatch that runs ahead of a step the repository said must come first.',
  },
  {
    name: 'lehre',
    url: '/plugins/lehre',
    summary:
      'Researches a code style, pattern and architecture doctrine, then denies the write that would violate it.',
  },
  {
    name: 'nacharbeit',
    url: '/plugins/nacharbeit',
    summary:
      'Reviews a Claude Code plugin against the official Anthropic standard, then reworks the mechanical and local-rewrite share of what falls short.',
  },
  {
    name: 'matrize',
    url: '/plugins/matrize',
    summary:
      'Derives a design system once from reference exemplars you admire, names every element, and emits it to any target.',
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
