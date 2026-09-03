<script setup>
// Purely presentational half of the shared copy-to-clipboard pattern -- the
// actual clipboard call and its fallback live in
// ../composables/useClipboardCopy.js so this button can be reused by both
// PairingCards.vue (one button per card, all sharing one composable
// instance -- the pre-refactor behavior) and RecipeBeats.vue (a single
// button for the opening prompt) without a second copy of either piece.
defineProps({
  // 'idle' | 'copied' | 'failed' -- the caller derives this from whatever
  // id/state shape its own useClipboardCopy() call returns.
  status: { type: String, default: 'idle' },
})
defineEmits(['click'])
</script>

<template>
  <button type="button" class="copy-button" @click="$emit('click', $event)">
    {{ status === 'copied' ? 'Copied' : status === 'failed' ? 'Selected — ⌘C' : 'Copy' }}
  </button>
</template>

<style scoped>
.copy-button {
  border: 1px solid var(--vp-c-divider);
  border-radius: 4px;
  background: transparent;
  color: var(--vp-c-text-2);
  font-size: 0.72rem;
  padding: 0.1rem 0.5rem;
  cursor: pointer;
  line-height: 1.6;
}
.copy-button:hover {
  border-color: var(--vp-c-brand-1);
  color: var(--vp-c-text-1);
}
</style>
