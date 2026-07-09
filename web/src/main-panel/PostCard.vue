<script setup>
import { computed } from 'vue'

const props = defineProps({ task: { type: Object, required: true } })

const card = computed(() => props.task.artifacts || {})
</script>

<template>
  <div class="post-card">
    <img
      v-if="card.cover && card.cover.url"
      :src="card.cover.url"
      :alt="card.cover.caption || ''"
      class="pc-cover"
      loading="lazy"
    />
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
    <p v-if="card.summary" class="pc-summary">{{ card.summary }}</p>
  </div>
</template>

<style scoped>
.post-card {
  border: none;
  border-radius: var(--ch-radius-md);
  background: transparent;
  overflow: hidden;
  margin: 4px 0;
  box-shadow: none;
}
.pc-cover { width: 100%; max-height: 320px; object-fit: cover; display: block; }
.pc-title {
  font-size: 22px;
  font-family: var(--ch-serif);
  font-weight: 600;
  color: var(--ch-text);
  margin: 18px 22px 10px;
}
.pc-sections { padding: 0 22px 12px; }
.pc-heading { font-size: 16px; font-weight: 700; color: var(--ch-text); margin: 14px 0 6px; }
.pc-paragraph { font-size: 14px; color: var(--ch-body); line-height: 1.75; margin: 6px 0; }
.pc-list { font-size: 13px; color: var(--ch-body); white-space: pre-wrap; margin: 6px 0; font-family: inherit; }
.pc-quote {
  border-left: 3px solid var(--ch-primary); padding: 8px 12px; margin: 10px 0;
  color: var(--ch-body); font-size: 14px; background: var(--ch-primary-soft); border-radius: 0 var(--ch-radius-sm) var(--ch-radius-sm) 0;
}
.pc-image { margin: 8px 0; }
.pc-image img { width: 100%; border-radius: var(--ch-radius-lg); }
.pc-image figcaption { font-size: 12px; color: var(--ch-faint); margin-top: 4px; }
.pc-tags { padding: 4px 22px 10px; display: flex; flex-wrap: wrap; gap: 6px; }
.pc-tag {
  font-size: 12px; color: var(--ch-primary-2); background: var(--ch-primary-soft);
  padding: 2px 10px; border-radius: 999px;
}
.pc-summary { padding: 10px 22px 16px; font-size: 13px; color: var(--ch-faint); border-top: 1px solid var(--ch-border); margin: 0; }
</style>
