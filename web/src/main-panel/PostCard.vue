<script setup>
import { computed } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  task: { type: Object, required: true },
  review: { type: Boolean, default: false },
})

const card = computed(() => props.task.artifacts || {})

function listItems(section) {
  return String(section.text || '').split('\n').map((item) => item.trim()).filter(Boolean)
}

function renderInline(text) {
  return DOMPurify.sanitize(marked.parseInline(text || ''))
}

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
      <h2 v-if="card.title" class="pc-title" v-html="renderInline(card.title)"></h2>

      <div class="pc-sections">
        <template v-for="(s, i) in (card.sections || [])" :key="i">
          <h3 v-if="s.kind === 'heading'" class="pc-heading" v-html="renderInline(s.text)"></h3>
          <p v-else-if="s.kind === 'paragraph'" class="pc-paragraph" v-html="renderInline(s.text)"></p>
          <ul v-else-if="s.kind === 'list'" class="pc-list">
            <li v-for="(item, itemIndex) in listItems(s)" :key="itemIndex" v-html="renderInline(item)"></li>
          </ul>
          <div v-else-if="s.kind === 'table' && s.table" class="pc-table-wrap">
            <table class="pc-table">
              <thead><tr><th v-for="(cell, cellIndex) in s.table.headers" :key="cellIndex" v-html="renderInline(cell)"></th></tr></thead>
              <tbody><tr v-for="(row, rowIndex) in s.table.rows" :key="rowIndex"><td v-for="(cell, cellIndex) in row" :key="cellIndex" v-html="renderInline(cell)"></td></tr></tbody>
            </table>
          </div>
          <blockquote v-else-if="s.kind === 'quote'" class="pc-quote" v-html="renderInline(s.text)"></blockquote>
          <hr v-else-if="s.kind === 'divider'" class="pc-divider">
          <figure v-else-if="s.kind === 'image' && s.image && s.image.url" class="pc-image">
            <img :src="s.image.url" :alt="s.image.caption || ''" loading="lazy" />
            <figcaption v-if="s.image.caption">{{ s.image.caption }}</figcaption>
          </figure>
        </template>
      </div>

      <div v-if="(card.tags || []).length" class="pc-tags">
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
.pc-sections { max-width: 680px; display: flex; flex-direction: column; align-items: stretch; padding: 0; }
.pc-heading { margin: 12px 0 7px; color: var(--ch-text); font: 600 16px/1.55 var(--ch-serif); }
.pc-heading:first-child { margin-top: 0; }
.pc-paragraph { margin: 0 0 12px; color: var(--ch-body); font: 500 14px/1.9 var(--ch-serif); letter-spacing: .005em; }
.pc-copy :deep(strong) { color: var(--ch-text); font-weight: 600; }
.pc-list { margin: 2px 0 15px; padding-left: 22px; color: var(--ch-body); font: 500 14px/1.85 var(--ch-serif); list-style: disc outside; }
.pc-list li { margin: 4px 0; padding-left: 2px; }
.pc-table-wrap { width: 100%; margin: 3px 0 19px; overflow-x: auto; }
.pc-table { width: 100%; border-collapse: collapse; color: var(--ch-body); font: 500 12px/1.65 var(--ch-serif); }
.pc-table th, .pc-table td { padding: 8px 10px; border: 0; border-bottom: 1px dotted var(--ch-border-2); text-align: left; vertical-align: top; }
.pc-table th { border-top: 1px solid var(--ch-border-2); border-bottom-style: solid; color: var(--ch-text); font-weight: 600; }
.pc-table tbody tr:last-child td { border-bottom-style: solid; }
.pc-quote {
  margin: 18px 0 20px; padding: 13px 18px; border: 0; border-top: 1px solid var(--ch-border-2); border-bottom: 1px solid var(--ch-border-2);
  color: var(--ch-text); font: 600 16px/1.75 var(--ch-serif); text-align: center; background: transparent;
}
.pc-divider { width: 100%; margin: 10px 0 18px; border: 0; border-top: 1px dashed var(--ch-border-2); }
.pc-image { margin: 8px 0 18px; }
.pc-image img { width: 100%; display: block; }
.pc-image figcaption { font-family: var(--ch-sans); font-size: var(--t-eyebrow); color: var(--ch-meta); margin-top: 4px; }
.pc-tags { max-width: 680px; margin: 4px 0 0; padding: 12px 0 0; display: flex; flex-wrap: wrap; gap: 6px 14px; border-top: 1px solid var(--ch-border-2); }
.pc-tag {
  font-family: var(--ch-serif); font-size: 11px; line-height: 1.6; color: var(--ch-primary-2); background: transparent;
  padding: 0;
}

@media (max-width: 780px) {
  .pc-quote { margin: 18px 0; padding-left: 14px; }
}
</style>
