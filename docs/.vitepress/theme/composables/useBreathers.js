/**
 * Breathers: a purely visual pause inserted into long runs of unbroken text
 * blocks. See werkstoff.css's `.wk-breather` block for the design rationale and
 * the contract this file has to satisfy.
 *
 * The one thing worth restating here, because it governs every decision below:
 * a breather carries NO information. Removing every one of them loses nothing.
 * That is what makes a machine-asserted break the author did not write
 * defensible at all -- it is the falsifiable half of a disagreement the design
 * brief deliberately left open, and it is built so it can be deleted.
 *
 * Consequences, all of them enforced below rather than assumed:
 *   - aria-hidden + role="presentation": nothing a screen reader announces.
 *   - no text, no motion, no focusable content: not a tab stop, not a heading,
 *     not a landmark. The document outline is untouched.
 *   - inserted between top-level block siblings only, so the heading tree and
 *     the right-hand rail cannot see it.
 */

/** A run must be at least this many consecutive text blocks to earn a breather. */
export const RUN_MIN = 6

/** Within a qualifying run, insert after every Nth block. */
export const EVERY = 4

/**
 * Tag names that count as an unbroken text block. Deliberately narrow: a table,
 * a code fence, a blockquote, an `hr` and a `::: details` container are all
 * already visual breaks in their own right, so they END a run rather than
 * extend it. A list is ONE block however many items it has -- that is what the
 * DOM says, and the DOM is what the reader sees.
 */
const TEXT_TAGS = new Set(['P', 'UL', 'OL'])

const CLASS = 'wk-breather'

/**
 * The markdown body's block container. VitePress compiles every page to
 * `<template><div>{html}</div></template>` and renders it as
 * `<main><div class="vp-doc"><div>…blocks…</div></div></main>`, so the blocks
 * are grandchildren of `.vp-doc`, not children.
 *
 * Scoped through `main` on purpose: RecipeBeats.vue's root carries BOTH
 * `recipe-beats` and `vp-doc` (it borrows the prose styles), and it lives in
 * the `doc-after` slot, outside `main`. A bare `.vp-doc > div` selector would
 * match it on all 37 recipe pages.
 */
export function docBlockRoot(doc = globalThis.document) {
  return doc?.querySelector?.('.VPDoc main > .vp-doc > div') ?? null
}

/**
 * Insert breathers into `root`, or strip them if the page is not prose.
 *
 * Idempotent by reconstruction rather than by a "have I run?" flag: every
 * existing breather is removed before any is inserted. A flag would be wrong in
 * two ways an SPA actually hits -- Vue may reuse the container element across a
 * route change (a stale flag then skips the new page), and a re-entrant call on
 * the same page would otherwise double the marks.
 *
 * @param {Element|null} root the block container from docBlockRoot()
 * @param {boolean} isProse the page's stamped prose verdict (see useProsePage.js)
 */
export function applyBreathers(root, isProse) {
  if (!root) return 0

  for (const stale of root.querySelectorAll(`:scope > .${CLASS}`)) stale.remove()

  // Not a prose page: the reading rhythm is a component's business, not this
  // file's. Stripping first and returning here is what makes an SPA navigation
  // from a prose page to a component page leave nothing behind.
  if (isProse !== true) return 0

  const runs = []
  let run = []
  for (const el of root.children) {
    if (TEXT_TAGS.has(el.tagName)) {
      run.push(el)
    } else {
      if (run.length >= RUN_MIN) runs.push(run)
      run = []
    }
  }
  if (run.length >= RUN_MIN) runs.push(run)

  let inserted = 0
  for (const blocks of runs) {
    // `< blocks.length - 1` and not `<=`: never after the LAST block of a run.
    // Whatever ended the run -- a heading, an hr, a table -- is already a
    // stronger break than a breather, and stacking them reads as a mistake.
    for (let i = EVERY - 1; i < blocks.length - 1; i += EVERY) {
      const mark = document.createElement('div')
      mark.className = CLASS
      mark.setAttribute('aria-hidden', 'true')
      mark.setAttribute('role', 'presentation')
      blocks[i].after(mark)
      inserted += 1
    }
  }
  return inserted
}
