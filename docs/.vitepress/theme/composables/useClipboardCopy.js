import { ref } from 'vue'

// Copy-to-clipboard with a genuine failure path, extracted out of
// PairingCards.vue (the only place this worked before this file existed) so
// RecipeBeats.vue's "Start here" opening-prompt button can share the exact
// same behavior instead of carrying a second, divergent copy of it.
//
// The Clipboard API can reject even in a perfectly normal browser (denied
// permission, an insecure context, no support at all) -- confirmed live: it
// rejects unconditionally in this project's own sandboxed preview. A
// `.then()` with no `.catch()` would make that failure silent, which is
// exactly the defect this repo's silent-failure-hunter pairing exists to
// catch, so on rejection this falls back to selecting the source text
// instead of doing nothing.
//
// One call site (PairingCards) needs a single copiedId/failedId pair shared
// across every card on the page -- exactly the pre-refactor behavior, kept
// unchanged here -- while RecipeBeats calls this once for its one button.
// Either way, `id` is caller-chosen: a pairing's own id, or a fixed sentinel
// string for a page with only one copy button.
export function useClipboardCopy() {
  const copiedId = ref(null)
  const failedId = ref(null)
  let copyTimeout = null

  function selectFallbackText(button) {
    // The fallback selects whatever the caller marked as the copy source,
    // found by walking up to the nearest `[data-copy-scope]` ancestor and
    // querying the `[data-copy-target]` inside it -- generic DOM contract
    // instead of hardcoding a class name, so both RecipeBeats' single
    // opening-prompt block and PairingCards' per-card prompt rows can use
    // it unmodified.
    const scope = button.closest('[data-copy-scope]')
    const target = scope?.querySelector('[data-copy-target]')
    const selection = window.getSelection()
    // getSelection() returns null in some non-standard/restricted contexts
    // (MDN). Skipping the select there still leaves the button's own
    // "Selected -- ⌘C" state as the user-visible signal that clipboard
    // access failed -- an unguarded throw here would instead break the
    // whole .catch() chain and leave the button silently stuck on "Copy".
    if (!target || !selection) return
    const range = document.createRange()
    range.selectNodeContents(target)
    selection.removeAllRanges()
    selection.addRange(range)
  }

  function copy(id, text, event) {
    const button = event.currentTarget
    const settle = (target) => {
      clearTimeout(copyTimeout)
      copyTimeout = setTimeout(() => {
        copiedId.value = null
        failedId.value = null
      }, 2000)
      target.value = id
    }
    const onFail = () => {
      selectFallbackText(button)
      settle(failedId)
    }
    if (!navigator.clipboard?.writeText) {
      onFail()
      return
    }
    navigator.clipboard
      .writeText(text)
      .then(() => settle(copiedId))
      .catch(onFail)
  }

  return { copiedId, failedId, copy }
}
