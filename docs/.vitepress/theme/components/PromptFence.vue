<script setup>
// Renders a recipe prompt as a REAL VitePress code fence rather than a blockquote.
//
// Why the markup is replicated so literally: VitePress's copy button is not part
// of the fence markup at all. `useCopyCode` registers ONE delegated listener on
// window and matches `div[class*="language-"] > button.copy`, then reaches the
// text via `el.nextElementSibling?.nextElementSibling` -- button, then the lang
// span, then <pre>. Any element inserted or omitted between them silently copies
// the wrong node or nothing, with no error. So the child order below is a
// contract with vitepress/dist/client/app/composables/copyCode.js, not styling.
//
// The `language-prompt` class is what earns the accent border already defined in
// werkstoff.css ("The prompt fences are the docs' signature element"). Marking
// these blocks any other way would make the catalog the one place in the docs
// where a copy-pasteable prompt does not look like one.
const props = defineProps({ text: { type: String, required: true } })

// Shiki emits one `<span class="line">` per source line and VitePress's copy
// path reads textContent, so splitting here reproduces both the visual line
// breaks and the copied text exactly.
const lines = props.text.replace(/\n+$/, '').split('\n')
</script>

<template>
  <div class="language-prompt vp-adaptive-theme">
    <button title="Copy Code" class="copy"></button>
    <span class="lang">prompt</span>
    <pre class="shiki shiki-themes github-light github-dark vp-code"><code><span
      v-for="(line, i) in lines" :key="i" class="line"><span>{{ line }}</span>{{ i < lines.length - 1 ? '\n' : '' }}</span></code></pre>
  </div>
</template>
