import { defineConfig } from 'vitepress'

// Project site at https://anselmoo.github.io/werkstoff/. VitePress prepends this
// to themeConfig.logo for us, but NOT to raw `head` entries, so the favicon href
// interpolates it explicitly rather than hardcoding the path twice.
const base = '/werkstoff/'

// Project site at https://anselmoo.github.io/werkstoff/ -> base must be '/werkstoff/'.
// `rewrites` maps each section's README.md onto a directory index so the existing
// files keep their names on disk; nothing under docs/ needs renaming or frontmatter.
export default defineConfig({
  title: 'werkstoff',
  description:
    'A workshop of Claude Code plugins, and how they compose with superpowers and the official Anthropic plugin set.',
  base,
  cleanUrls: true,
  lastUpdated: true,
  ignoreDeadLinks: false,

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${base}favicon.svg` }],
    ['meta', { name: 'theme-color', content: '#cc785c' }],
  ],

  // Not published. These two pilot records name an internal host, an internal
  // repository, and an absolute path on that host. They stay in the repo and on
  // GitHub unchanged; they are simply not built into an indexed public site.
  // Delete these two lines to publish them.
  srcExclude: ['andon-pilot-findings.md', 'andon-pilot-handoff.md'],

  rewrites: {
    'orchestration/README.md': 'orchestration/index.md',
    'plugin-authoring/README.md': 'plugin-authoring/index.md',
  },

  themeConfig: {
    logo: '/logo.svg',

    nav: [
      { text: 'Prompt catalog', link: '/orchestration/references/catalog' },
      { text: 'Orchestration', link: '/orchestration/' },
      { text: 'Authoring', link: '/plugin-authoring/' },
      { text: 'Plugins', link: 'https://github.com/Anselmoo/werkstoff#plugins' },
    ],

    sidebar: [
      {
        text: 'Start here',
        items: [
          { text: 'Extended prompt catalog', link: '/orchestration/references/catalog' },
          { text: 'Prompt index by plugin', link: '/prompt-index' },
          { text: 'Orchestration overview', link: '/orchestration/' },
        ],
      },
      {
        text: 'Orchestration',
        collapsed: false,
        items: [
          { text: 'Overview', link: '/orchestration/' },
          { text: 'Extended prompt catalog', link: '/orchestration/references/catalog' },
          { text: 'Routing between pipelines', link: '/orchestration/references/routing' },
          { text: 'Review gates', link: '/orchestration/references/gates' },
          { text: 'Delegation and model tiers', link: '/orchestration/references/delegation' },
          { text: 'Composition hazards', link: '/orchestration/references/hazards' },
          { text: 'Paste-in CLAUDE.md block', link: '/orchestration/references/claude-md-block' },
        ],
      },
      {
        text: 'Plugin authoring',
        collapsed: false,
        items: [
          { text: 'Overview', link: '/plugin-authoring/' },
          { text: 'Craft standards', link: '/plugin-authoring/references/craft-standards' },
          { text: 'Output-shape findings', link: '/plugin-authoring/references/output-shape-findings' },
        ],
      },
      {
        text: 'Findings and plans',
        collapsed: true,
        items: [
          { text: 'Plugin rebuild findings', link: '/plugin-rebuild-findings' },
          { text: 'Benchmark plan', link: '/plugin-benchmark-plan' },
          { text: 'Benchmark phase 1 results', link: '/plugin-benchmark-phase1-results' },
          { text: 'Benchmark phase 2 results', link: '/plugin-benchmark-phase2-results' },
          { text: 'andon behaviour contract', link: '/andon-behavior-contract' },
        ],
      },
    ],

    socialLinks: [{ icon: 'github', link: 'https://github.com/Anselmoo/werkstoff' }],
    search: { provider: 'local' },
    editLink: {
      pattern: 'https://github.com/Anselmoo/werkstoff/edit/main/docs/:path',
      text: 'Edit this page on GitHub',
    },
    outline: [2, 3],
  },
})
