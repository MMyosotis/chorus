<script setup>
import { computed } from 'vue'
import { firstImageUrl, firstParagraphText } from '../composables/renderPostCard.js'

const props = defineProps({
  task: { type: Object, required: true },
  review: { type: Boolean, default: false },
})

defineEmits(['preview'])

const card = computed(() => props.task.artifacts || {})

const platformLabel = computed(() => props.task.artifacts.meta.preview_ref.split('/')[0])

const coverUrl = computed(() => firstImageUrl(card.value))

const title = computed(() => card.value.meta?.title || '')

const firstParagraph = computed(() => {
  const text = firstParagraphText(card.value.markdown)
  return text.length > 80 ? text.slice(0, 80) + '…' : text
})

const isFinished = computed(() => props.task.status === 'finished')
</script>

<template>
  <section class="artifact-wrap" :class="{ review }">
    <div v-if="isFinished" class="finish">
      <div><h2>创作完成</h2><p>标题、正文和配图已经整理完毕</p></div>
      <span>已完成</span>
    </div>
    <div class="artifact-card">
      <img v-if="coverUrl" :src="coverUrl" class="ac-cover" loading="lazy" />
      <div class="ac-body">
        <div class="ac-platform">发布到 {{ platformLabel }}</div>
        <h3 v-if="title" class="ac-title">{{ title }}</h3>
        <p v-if="firstParagraph" class="ac-excerpt">{{ firstParagraph }}</p>
        <button class="ac-expand" @click="$emit('preview')">查看完整成品</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.artifact-wrap {
  width: 100%;
  padding: var(--ch-space-4);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-soft);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}
.artifact-wrap.review {
  padding: var(--ch-space-3);
  border: 0;
  border-radius: var(--ch-radius-list);
  box-shadow: none;
  background: var(--ch-muted-gradient);
}
.finish {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--ch-border);
  text-align: left;
}
.finish h2 { margin: 0; font-size: 18px; font-weight: 600; line-height: 1.3; }
.finish p { margin: 8px 0 0; color: var(--ch-text-muted); font-size: 12px; line-height: 1.5; }
.finish > span {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 8px;
  border-radius: var(--ch-radius-pill);
  background: var(--ch-success-soft);
  color: var(--ch-success-text);
  font: 600 12px/1 var(--ch-font-sans);
  white-space: nowrap;
}
.artifact-card { display: flex; align-items: stretch; gap: 20px; }
.ac-cover { width: 160px; aspect-ratio: 4 / 3; object-fit: cover; flex-shrink: 0; border-radius: var(--ch-radius-card); }
.ac-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.ac-platform { color: var(--ch-text-muted); font-size: 12px; font-weight: 500; line-height: 1.5; }
.ac-title { margin: 0; font-size: 18px; font-weight: 600; line-height: 1.3; color: var(--ch-text); }
.ac-excerpt { margin: 0; color: var(--ch-text-secondary); font-size: 14px; line-height: 1.5; }
.ac-expand {
  align-self: flex-start;
  min-height: 40px;
  margin-top: auto;
  padding: 0 16px;
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface);
  color: var(--ch-text);
  font: 600 14px/1 var(--ch-font-sans);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease);
}
.ac-expand:hover { border-color: var(--ch-text-faint); background: var(--ch-surface); }
@media (max-width: 620px) {
  .artifact-wrap { padding: 16px; }
  .artifact-card { flex-direction: column; }
  .ac-cover { width: 100%; }
}
</style>
