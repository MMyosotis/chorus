<script setup>
import { computed } from 'vue'
import { Eye } from '@lucide/vue'
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
    <div v-if="isFinished && !review" class="finish">
      <div><h2>创作完成</h2><p>标题、正文和配图已经整理完毕</p></div>
      <span>已完成</span>
    </div>
    <button
      class="artifact-card"
      type="button"
      :aria-label="title ? `打开《${title}》完整预览` : '打开完整成品预览'"
      @click="$emit('preview')"
    >
      <img v-if="coverUrl" :src="coverUrl" class="ac-cover" loading="lazy" />
      <span class="ac-body">
        <span class="ac-platform">发布到 {{ platformLabel }}</span>
        <span v-if="title" class="ac-title">{{ title }}</span>
        <span v-if="firstParagraph" class="ac-excerpt">{{ firstParagraph }}</span>
        <span class="ac-preview-link">
          打开完整预览
          <Eye aria-hidden="true" />
        </span>
      </span>
    </button>
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
  background: var(--ch-surface-2);
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
.artifact-card {
  width: 100%;
  display: flex;
  align-items: stretch;
  gap: 20px;
  padding: 0;
  border: 1px solid transparent;
  border-radius: var(--ch-radius-list);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color var(--ch-duration-fast) var(--ch-ease), background var(--ch-duration-fast) var(--ch-ease), transform var(--ch-duration-fast) var(--ch-ease);
}
.artifact-card:focus-visible { outline: 0; }
.ac-cover { width: 160px; aspect-ratio: 4 / 3; object-fit: cover; flex-shrink: 0; border-radius: var(--ch-radius-card); }
.ac-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }
.ac-platform { color: var(--ch-text-muted); font-size: 14px; font-weight: 500; line-height: 1.5; }
.ac-title { display: block; color: var(--ch-text); font-size: 18px; font-weight: 600; line-height: 1.3; }
.ac-excerpt {
  display: -webkit-box;
  overflow: hidden;
  color: var(--ch-text-secondary);
  font-size: 14px;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
}
.ac-preview-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  align-self: flex-start;
  margin-top: auto;
  padding-top: 4px;
  color: var(--ch-accent);
  font: 600 14px/1.5 var(--ch-font-sans);
}
.ac-preview-link svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.8; }
@media (max-width: 620px) {
  .artifact-wrap { padding: 16px; }
  .artifact-card { flex-direction: column; }
  .ac-cover { width: 100%; }
}
</style>
