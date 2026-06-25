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
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  background: #fff;
  overflow: hidden;
  margin: 12px 0;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
}
.pc-cover { width: 100%; max-height: 320px; object-fit: cover; display: block; }
.pc-title { font-size: 18px; font-weight: 600; color: #1e293b; margin: 14px 16px 8px; }
.pc-sections { padding: 0 16px 8px; }
.pc-heading { font-size: 15px; font-weight: 600; color: #334155; margin: 12px 0 4px; }
.pc-paragraph { font-size: 14px; color: #475569; line-height: 1.7; margin: 6px 0; }
.pc-list { font-size: 13px; color: #475569; white-space: pre-wrap; margin: 6px 0; font-family: inherit; }
.pc-quote {
  border-left: 3px solid #818cf8; padding: 6px 12px; margin: 8px 0;
  color: #64748b; font-size: 14px; background: #f8fafc; border-radius: 0 6px 6px 0;
}
.pc-image { margin: 8px 0; }
.pc-image img { width: 100%; border-radius: 8px; }
.pc-image figcaption { font-size: 12px; color: #94a3b8; margin-top: 4px; }
.pc-tags { padding: 4px 16px 8px; display: flex; flex-wrap: wrap; gap: 6px; }
.pc-tag {
  font-size: 12px; color: #6366f1; background: rgba(99, 102, 241, 0.08);
  padding: 2px 8px; border-radius: 10px;
}
.pc-summary { padding: 8px 16px 14px; font-size: 13px; color: #94a3b8; border-top: 1px solid #f1f5f9; margin: 0; }
</style>
