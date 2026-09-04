import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitepress'
import { CATEGORY_ORDER, CATEGORY_LABELS } from './data/catalog.categories.mjs'
import { isProsePage, PROSE_PAGE_KEY } from './theme/composables/useProsePage.js'

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

// Drops a leading `---`/`---` YAML block, returning the markdown body. Line-wise
// for the reason readRecipeFrontmatter() above already documents: a dotall regex
// spanning a file full of dots and newlines is this repo's signature silent
// failure. Mirrors test/docs/docs_ux_audit.py's frontmatter_and_body() so both
// halves of the prose-page predicate read exactly the same text.
function stripFrontmatter(source) {
  const lines = source.split('\n')
  if (lines[0]?.trim() !== '---') return source
  for (let i = 1; i < lines.length; i += 1) {
    if (lines[i].trim() === '---') return lines.slice(i + 1).join('\n')
  }
  return source
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

  // Stamp every page with the long-page treatment's prose/component verdict.
  //
  // This runs here, at build time, for one reason that is not a preference: the
  // predicate needs the markdown BODY, and the browser never has it. Three of
  // the four signals live in frontmatter, but the fourth -- a globally
  // registered component invoked in the body -- is what identifies
  // docs/catalog/index.md, whose frontmatter is indistinguishable from prose
  // and whose body is `<CatalogGrid />`. Deriving this client-side from the
  // rendered DOM instead would have to happen after hydration, which would put
  // the terminal node into the server-rendered HTML and then take it away
  // again: a hydration mismatch, and a mark that is briefly wrong on every load.
  //
  // The verdict is read back by DocEnd.vue and by useBreathers.js via
  // PROSE_PAGE_KEY. Neither re-derives it, and neither falls back to the
  // frontmatter-only half if the stamp is missing -- absent stamp means no
  // mark anywhere, which is the failure the docs UX audit's C4 wiring
  // assertion names out loud rather than the failure nobody sees.
  transformPageData(pageData, { siteConfig }) {
    // `filePath`, not `relativePath`. The two differ for every entry in
    // `rewrites` above: relativePath is the DESTINATION route
    // (orchestration/index.md), which is not a file on disk, while filePath is
    // the source VitePress actually read (orchestration/README.md). Reading
    // relativePath silently withheld both marks from exactly those two pages --
    // a wrong-file read that resolved to "no such file" rather than to an error.
    const relative = pageData.filePath || pageData.relativePath
    const source = path.join(siteConfig.srcDir, relative)
    if (!fs.existsSync(source)) {
      // Fail closed AND loud. Withholding the marks quietly is what the bug
      // above already did once; a page whose source cannot be read is a real
      // defect in this config, not a page to skip. Escape hatch, if a future
      // virtual page ever legitimately has no source: give it explicit
      // `layout:` frontmatter and exclude it here by name, on the record.
      throw new Error(
        `[werkstoff] transformPageData: no source file for page '${relative}' ` +
          `(looked in ${siteConfig.srcDir}). The long-page treatment cannot be scoped ` +
          'without the markdown body -- see theme/composables/useProsePage.js.',
      )
    }
    const body = stripFrontmatter(fs.readFileSync(source, 'utf-8'))
    pageData.frontmatter[PROSE_PAGE_KEY] = isProsePage(pageData.frontmatter, body)
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
          { text: 'Report-viewer standard', link: '/plugin-authoring/references/report-viewer-standard' },
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
