<script setup>
import { computed } from 'vue'

const props = defineProps({
  task: { type: Object, required: true },
  review: { type: Boolean, default: false },
})

const card = computed(() => props.task.artifacts || {})
const issueDate = computed(() => {
  const raw = props.task.finished_at || props.task.updated_at || props.task.created_at
  const date = raw ? new Date(typeof raw === 'number' && raw < 1e12 ? raw * 1000 : raw) : new Date()
  if (Number.isNaN(date.getTime())) return 'CURRENT DRAFT'
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y} / ${m} / ${d}`
})
</script>

<template>
  <section class="post-wrap">
    <div v-if="task.status === 'finished'" class="finish">
      <div class="finish-mark">✓</div><div><h2>创作完成</h2><p>最终成品已装订</p></div>
    </div>
  <div class="post-card" :class="{ 'is-review': review }">
    <img
      v-if="card.cover && card.cover.url"
      :src="card.cover.url"
      :alt="card.cover.caption || ''"
      class="pc-cover"
      loading="lazy"
    />
    <div class="pc-meta"><span>FINAL COPY · VOL. 07</span><span>{{ issueDate }}</span></div>

    <div class="pc-copy">
      <h2 v-if="card.title" class="pc-title">{{ card.title }}</h2>

      <div class="pc-sections">
        <template v-for="(s, i) in card.sections || []" :key="i">
          <h3 v-if="s.kind === 'heading'" class="pc-heading">{{ s.text }}</h3>
          <p v-else-if="s.kind === 'paragraph'" class="pc-paragraph">{{ s.text }}</p>
          <pre v-else-if="s.kind === 'list'" class="pc-list">{{ s.text }}</pre>
          <blockquote v-else-if="s.kind === 'quote'" class="pc-quote">{{ s.text }}</blockquote>
          <figure v-else-if="s.kind === 'image' && s.image" class="pc-image">
            <img :src="s.image.url" :alt="s.image.caption || ''" loading="lazy" />
            <figcaption v-if="s.image.caption">{{ s.image.caption }}</figcaption>
          </figure>
        </template>
      </div>

      <div v-if="card.tags && card.tags.length" class="pc-tags">
        <span v-for="(t, i) in card.tags" :key="i" class="pc-tag">{{ t }}</span>
      </div>
    </div>
  </div>
  </section>
</template>

<style scoped>
.post-wrap { width: 100%; }
.finish { display: flex; align-items: center; gap: 16px; margin-bottom: 20px; padding: 18px 0; border-top: 1px solid var(--ch-green); border-bottom: 1px solid var(--ch-green); color: var(--ch-green); text-align: left; }
.finish-mark { width: 36px; height: 36px; display: grid; place-items: center; border: 1px solid currentColor; border-radius: 50%; color: var(--ch-green); font: 600 16px/1 var(--ch-sans); }
.finish h2 { margin: 0; font: 600 16px/1.4 var(--ch-serif); }.finish p { margin: 4px 0 0; color: var(--ch-muted); font: 500 11px/1.4 var(--ch-serif); }
.post-card {
  border: 0;
  border-radius: 0;
  background: transparent;
  overflow: hidden;
  margin: 4px 0;
  box-shadow: none;
}
.pc-cover { width: 100%; aspect-ratio: 16/7; min-height: 230px; object-fit: cover; display: block; }
.pc-meta { min-height: 31px; display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 9px 1px; border-bottom: 1px solid var(--ch-border-2); color: var(--ch-muted); font: 500 var(--ch-chat-meta-size)/1.35 var(--ch-serif); font-variant-numeric: lining-nums tabular-nums; letter-spacing: .12em; }
.pc-copy { padding: 25px 2px 0; }
.pc-title {
  font-size: 31px;
  font-family: var(--ch-serif);
  font-weight: 700;
  line-height: 1.34;
  color: var(--ch-text);
  margin: 0 0 17px;
}
.pc-sections { display: grid; grid-template-columns: minmax(0, 1.22fr) minmax(0, .78fr); column-gap: 28px; align-items: start; padding: 0; }
.pc-heading { font-family: var(--ch-display); font-size: var(--t-title); font-weight: 600; color: var(--ch-text); margin: 14px 0 6px; }
.pc-paragraph { grid-column: 1; font-family: var(--ch-serif); font-size: 14px; color: var(--ch-body); line-height: 1.9; margin: 0 0 12px; }
.pc-list { font-family: var(--ch-serif); font-size: var(--t-meta); color: var(--ch-body); white-space: pre-wrap; margin: 6px 0; }
.pc-quote {
  grid-column: 2; grid-row: 1 / span 3; border-left: 2px solid var(--ch-warm); padding: 0 0 0 16px; margin: 0;
  color: var(--ch-text); font-family: var(--ch-serif); font-size: 16px; line-height: 1.75; background: transparent;
}
.pc-image { grid-column: 1 / -1; margin: 8px 0; }
.pc-image img { width: 100%; display: block; }
.pc-image figcaption { font-family: var(--ch-sans); font-size: var(--t-eyebrow); color: var(--ch-meta); margin-top: 4px; }
.pc-tags { margin: 10px 0 0; padding: 12px 0 0; display: flex; flex-wrap: wrap; gap: 12px; border: 0; }
.pc-tag {
  font-family: var(--ch-serif); font-size: 10px; color: var(--ch-primary-2); background: transparent;
  padding: 0;
}

@media (max-width: 780px) {
  .pc-sections { display: block; }
  .pc-quote { margin: 18px 0; padding-left: 14px; }
}
</style>
