<script setup>
import { computed } from 'vue'
import { ROLE_LABELS } from '../team-panel/roleMeta.js'

const props = defineProps({ task: { type: Object, default: null } })

const progress = computed(() => props.task?.current_activity?.progress_json || null)
const preview = computed(() => props.task?.current_activity?.artifact_preview_json || null)
const artifacts = computed(() => props.task?.artifacts || null)
const isImage = computed(() => props.task?.agent_type === 'image')
</script>

<template>
  <div v-if="task" class="work-card">
    <div class="wc-head">
      <span class="wc-role">{{ ROLE_LABELS[task.agent_type] || task.agent_type }}</span>
      <!-- image running：current/total 计数进度条 -->
      <span v-if="isImage && progress" class="wc-progress">第 {{ progress.current }}/{{ progress.total }} {{ progress.unit }}</span>
    </div>
    <!-- 当前活动产物预览（images / text_blocks） -->
    <div v-if="preview?.type === 'images' && preview.items?.length" class="wc-images">
      <figure v-for="(img, i) in preview.items" :key="i" class="wc-img">
        <img :src="img.url" :alt="img.caption || ''" loading="lazy" />
        <figcaption v-if="img.caption">{{ img.caption }}</figcaption>
      </figure>
    </div>
    <!-- 产物已落（awaiting_confirm/finished）：完整预览 -->
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
.work-card { border: 1px solid #e2e8f0; border-radius: 10px; background: #fff; padding: 10px 12px; }
.wc-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.wc-role { font-size: 13px; font-weight: 500; color: #1e293b; }
.wc-progress { font-size: 12px; color: #6366f1; font-weight: 500; }
.wc-images { display: flex; flex-wrap: wrap; gap: 8px; }
.wc-img { margin: 0; }
.wc-img img { width: 96px; height: 96px; object-fit: cover; border-radius: 8px; }
.wc-img figcaption { font-size: 11px; color: #64748b; }
.wc-blocks .block { margin: 4px 0; font-size: 13px; color: #475569; }
.wc-blocks .block.heading { font-weight: 500; color: #1e293b; }
</style>
