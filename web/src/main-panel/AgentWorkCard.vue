<script setup>
import { computed } from 'vue'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({ task: { type: Object, default: null } })

const payload = computed(() => props.task?.current_activity?.payload || null)
const progress = computed(() => payload.value?.total ? payload.value : null)
const preview = computed(() => payload.value?.items?.length ? payload.value : null)
const artifacts = computed(() => props.task?.artifacts || null)
const isImage = computed(() => props.task?.agent_type === 'image')
</script>

<template>
  <div class="work-card">
    <div class="wc-head">
      <span class="wc-role">{{ ROLE_LABELS[task.agent_type] || task.agent_type }}</span>
      <span v-if="isImage && progress" class="wc-progress">第 {{ progress.current }}/{{ progress.total }} {{ progress.unit }}</span>
    </div>
    <div v-if="preview?.items?.length" class="wc-images">
      <figure v-for="(img, i) in preview.items" :key="i" class="wc-img">
        <img :src="img.url" :alt="img.caption || ''" loading="lazy" />
        <figcaption v-if="img.caption">{{ img.caption }}</figcaption>
      </figure>
    </div>
    <div v-else-if="artifacts && task.status !== 'running'" class="wc-artifacts">
      <div v-if="task.agent_type === 'image'" class="wc-images">
        <figure v-for="(img, i) in artifacts.images || []" :key="i" class="wc-img">
          <img :src="img.url" :alt="img.caption || ''" loading="lazy" />
        </figure>
      </div>
      <div v-else-if="task.agent_type === 'script'" class="wc-blocks">
        <div v-for="(b, i) in artifacts.blocks || []" :key="i" :class="['block', b.kind]">{{ b.text }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.work-card { border: 1px solid var(--ch-border); border-radius: var(--ch-radius-sm); background: var(--ch-surface); padding: 10px 12px; }
.wc-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.wc-role { font-size: 13px; font-weight: 500; color: var(--ch-text); }
.wc-progress { font-size: 12px; color: var(--ch-orange); font-weight: 600; }
.wc-images { display: flex; flex-wrap: wrap; gap: 8px; }
.wc-img { margin: 0; }
.wc-img img { width: 96px; height: 96px; object-fit: cover; border-radius: var(--ch-radius-sm); }
.wc-img figcaption { font-size: 11px; color: var(--ch-muted); }
.wc-blocks .block { margin: 4px 0; font-size: 13px; color: var(--ch-body); }
.wc-blocks .block.heading { font-weight: 600; color: var(--ch-text); }
</style>
