import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitepress'
import { CATEGORY_ORDER, CATEGORY_LABELS } from './data/catalog.categories.mjs'

// Project site at https://anselmoo.github.io/werkstoff/. VitePress prepends this
// to themeConfig.logo for us, but NOT to raw `head` entries, so the favicon href
// interpolates it explicitly rather than hardcoding the path twice.
const base = '/werkstoff/'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const catalogDir = path.join(__dirname, '..', 'catalog')

// Reads just the `task:` and `category:` scalar frontmatter fields from one recipe
// file, line by line inside the `---`/`---` block. Deliberately NOT a regex spanning
// the whole file -- this repo's CLAUDE.md documents exactly why a dotall/spanning
// pattern over content containing dots and newlines silently matches the wrong thing
// (or nothing) and reports success anyway.
function readRecipeFrontmatter(filePath) {
  const lines = fs.readFileSync(filePath, 'utf-8').split('\n')
  let inFrontmatter = false
  let task = null
  let category = null
  for (const line of lines) {
    if (line.trim() === '---') {
      if (!inFrontmatter) {
        inFrontmatter = true
        continue
      }
      break // closing delimiter -- stop reading, ignore the markdown body
    }
    if (!inFrontmatter) continue
    if (task === null) {
      const match = /^task:\s*"?(.*?)"?\s*$/.exec(line)
      if (match) task = match[1]
    }
    if (category === null) {
      const match = /^category:\s*(\S+)\s*$/.exec(line)
      if (match) category = match[1]
    }
  }
  return { task, category }
}

// Builds the "Prompt catalog" sidebar section directly from
// docs/catalog/<category>/*.md, so it can never drift from the recipes that
// actually exist on disk. Fails the build loudly rather than shipping a wrong or
// empty sidebar -- see the CLAUDE.md section on code that silently does nothing.
function buildCatalogSidebar() {
  const sections = []
  let total = 0

  for (const category of CATEGORY_ORDER) {
    const dir = path.join(catalogDir, category)
    if (!fs.existsSync(dir)) continue

    const files = fs
      .readdirSync(dir)
      .filter((name) => name.endsWith('.md'))
      .sort()

    const items = files.map((file) => {
      const filePath = path.join(dir, file)
      const { task, category: fmCategory } = readRecipeFrontmatter(filePath)

      if (fmCategory !== category) {
        throw new Error(
          `docs/.vitepress/config.mjs: ${path.relative(path.join(__dirname, '..', '..'), filePath)} ` +
            `declares category: "${fmCategory}" but lives under the "${category}" directory. ` +
            'Fix the frontmatter or move the file.',
        )
      }
      if (!task) {
        throw new Error(
          `docs/.vitepress/config.mjs: ${path.relative(path.join(__dirname, '..', '..'), filePath)} ` +
            'has no task: frontmatter field.',
        )
      }

      total += 1
      return { text: task, link: `/catalog/${category}/${file.replace(/\.md$/, '')}` }
    })

    items.sort((a, b) => a.text.localeCompare(b.text))
    sections.push({ text: CATEGORY_LABELS[category] ?? category, collapsed: true, items })
  }

  if (total === 0) {
    throw new Error(
      'docs/.vitepress/config.mjs: buildCatalogSidebar() found zero recipes under docs/catalog/<category>/*.md.',
    )
  }

  return sections
}

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
    ['meta', { name: 'theme-color', content: '#348ad9' }],
  ],

  // Not published. These two pilot records name an internal host, an internal
  // repository, and an absolute path on that host. `catalog/_UNRESOLVED.md` is an
  // internal working note that leaks this machine's absolute paths the same way.
  // They stay in the repo and on GitHub unchanged; they are simply not built into
  // an indexed public site. Delete a line to publish that file.
  srcExclude: ['andon-pilot-findings.md', 'andon-pilot-handoff.md', 'catalog/_UNRESOLVED.md'],

  rewrites: {
    'orchestration/README.md': 'orchestration/index.md',
    'plugin-authoring/README.md': 'plugin-authoring/index.md',
  },

  themeConfig: {
    logo: '/logo.svg',

    nav: [
      { text: 'Prompt catalog', link: '/catalog/' },
      { text: 'Orchestration', link: '/orchestration/' },
      { text: 'Authoring', link: '/plugin-authoring/' },
      { text: 'Plugins', link: 'https://github.com/Anselmoo/werkstoff#plugins' },
    ],

    sidebar: [
      {
        text: 'Start here',
        items: [
          { text: 'Prompt catalog', link: '/catalog/' },
          { text: 'Prompt index by plugin', link: '/prompt-index' },
          { text: 'Orchestration overview', link: '/orchestration/' },
        ],
      },
      {
        text: 'Prompt catalog',
        collapsed: false,
        items: buildCatalogSidebar(),
      },
      {
        text: 'Orchestration',
        collapsed: false,
        items: [
          { text: 'Overview', link: '/orchestration/' },
          { text: 'Prompt catalog', link: '/catalog/' },
          { text: 'Routing between pipelines', link: '/orchestration/references/routing' },
          { text: 'Review gates', link: '/orchestration/references/gates' },
          { text: 'Delegation and model tiers', link: '/orchestration/references/delegation' },
          { text: 'Composition hazards', link: '/orchestration/references/hazards' },
          { text: 'Pairings', link: '/orchestration/references/pairings' },
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
