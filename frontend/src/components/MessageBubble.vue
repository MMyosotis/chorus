<script setup>
import { computed } from 'vue'

const props = defineProps({
  role: { type: String, required: true },
  content: { type: String, required: true },
  showCursor: { type: Boolean, default: false },
})

const formattedContent = computed(() => {
  return props.content
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\n/g, '<br>')
})
</script>

<template>
  <div :class="['bubble-row', role]">
    <div :class="['bubble', role]">
      <span class="text" v-html="formattedContent"></span>
      <span v-if="showCursor" class="cursor">|</span>
    </div>
  </div>
</template>

<style scoped>
.bubble-row {
  display: flex;
}

.bubble-row.user {
  justify-content: flex-end;
}

.bubble-row.assistant {
  justify-content: flex-start;
}

.bubble {
  max-width: 75%;
  padding: 10px 16px;
  border-radius: 16px;
  line-height: 1.6;
  font-size: 15px;
  word-break: break-word;
}

.bubble.user {
  background: #3b82f6;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.bubble.assistant {
  background: #f1f5f9;
  color: #1e293b;
  border-bottom-left-radius: 4px;
}

.cursor {
  display: inline;
  animation: blink 0.8s step-end infinite;
  color: inherit;
  font-weight: 200;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
