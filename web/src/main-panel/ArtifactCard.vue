<script setup>
import { computed } from 'vue'

const props = defineProps({
  task: { type: Object, required: true },
  review: { type: Boolean, default: false },
})

defineEmits(['preview'])

const card = computed(() => props.task.artifacts || {})

const platformLabel = computed(() => {
  const ref = props.task.artifacts?.meta?.preview_ref || ''
  return String(ref).split('/')[0] || 'web-blog'
})

const firstParagraph = computed(() => {
  const section = (card.value.sections || []).find((s) => s.kind === 'paragraph' && s.text)
  const text = String(section?.text || '').replace(/\n/g, ' ').trim()
  return text.length > 80 ? text.slice(0, 80) + '…' : text
})

const isFinished = computed(() => props.task.status === 'finished')
</script>

<template>
  <section class="artifact-wrap">
    <div v-if="isFinished" class="finish">
      <div class="finish-mark">✓</div>
      <div><h2>创作完成</h2><p>最终成品已装订</p></div>
    </div>
    <div class="artifact-card" :class="{ 'is-review': review }">
      <img v-if="card.cover && card.cover.url" :src="card.cover.url" :alt="card.cover.caption || ''" class="ac-cover" loading="lazy" />
      <div class="ac-body">
        <div class="ac-platform">{{ platformLabel }}</div>
        <h3 v-if="card.title" class="ac-title">{{ card.title }}</h3>
        <p v-if="firstParagraph" class="ac-excerpt">{{ firstParagraph }}</p>
        <button class="ac-expand" @click="$emit('preview')">展开预览</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.artifact-wrap { width: 100%; }
.finish { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; padding: 18px 0; border-top: 1px solid var(--ch-green); border-bottom: 1px solid var(--ch-green); color: var(--ch-green); text-align: left; }
.finish-mark { width: 36px; height: 36px; display: grid; place-items: center; border: 1px solid currentColor; border-radius: 50%; font: 600 16px/1 var(--ch-sans); }
.finish h2 { margin: 0; font: 600 16px/1.4 var(--ch-serif); }
.finish p { margin: 4px 0 0; color: var(--ch-muted); font: 500 11px/1.4 var(--ch-serif); }
.artifact-card { display: flex; gap: 16px; padding: 16px; border: 1px solid var(--ch-border-2); border-radius: 4px; background: transparent; }
.artifact-card.is-review { border-color: var(--ch-green); }
.ac-cover { width: 120px; height: 80px; object-fit: cover; flex-shrink: 0; border-radius: 2px; }
.ac-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 6px; }
.ac-platform { font: 500 11px/1.4 var(--ch-sans); color: var(--ch-muted); letter-spacing: .12em; text-transform: uppercase; }
.ac-title { margin: 0; font: 600 16px/1.4 var(--ch-serif); color: var(--ch-text); }
.ac-excerpt { margin: 0; font: 500 13px/1.6 var(--ch-serif); color: var(--ch-body); }
.ac-expand { align-self: flex-start; margin-top: 4px; padding: 6px 14px; border: 1px solid var(--ch-border-2); border-radius: 2px; background: transparent; color: var(--ch-text); font: 500 12px/1 var(--ch-sans); cursor: pointer; }
.ac-expand:hover { border-color: var(--ch-green); color: var(--ch-green); }
</style>
