<script setup>
import { computed, ref } from 'vue'

import { ROLE_LABELS, badgeOf } from './roleMeta.js'

const props = defineProps({
  task: { type: Object, required: true }, // get_graph 的 task 项
})
const emit = defineEmits(['expand'])

const expanded = ref(false)
const busyIdx = ref(0)
const showBusy = ref(false)

const roleName = computed(() => ROLE_LABELS[props.task.agent_type] || props.task.agent_type)
const badge = computed(() => badgeOf(props.task.status))
const narrative = computed(() => props.task.narrative || {})
const busyLines = computed(() => narrative.value.busy_lines || [])

function toggleExpand() {
  expanded.value = !expanded.value
  if (expanded.value) emit('expand', props.task.id)
}

function cycleBusy() {
  if (!busyLines.value.length) return
  busyIdx.value = (busyIdx.value + 1) % busyLines.value.length
}
</script>

<template>
  <div class="role-card" :class="badge.cls">
    <div class="role-head" @click="toggleExpand">
      <span class="role-avatar">{{ roleName.slice(0, 1) }}</span>
      <div class="role-info">
        <span class="role-name">{{ narrative.role_name || roleName }}</span>
        <span class="role-badge" :class="badge.cls">{{ badge.label }}</span>
      </div>
    </div>

    <!-- 工作中：话术轮播（点开才看，不强制） -->
    <div v-if="task.status === 'running' && busyLines.length" class="role-line">
      <button class="line-toggle" @click="showBusy = !showBusy">
        {{ showBusy ? '收起' : '看在忙什么' }}
      </button>
      <div v-if="showBusy" class="busy-line" @click="cycleBusy">
        {{ busyLines[busyIdx] }}
      </div>
    </div>

    <!-- awaiting：弹引导语，把用户引向主面板 HIL 卡片（自身不放按钮/列表） -->
    <div v-else-if="task.status === 'awaiting_confirm' && narrative.awaiting_line" class="role-line guide">
      {{ narrative.awaiting_line }}
    </div>

    <!-- 已完成：总结 -->
    <div v-else-if="task.status === 'finished' && narrative.done_line" class="role-line done">
      {{ narrative.done_line }}
    </div>

    <div v-if="task.error" class="role-error">{{ task.error }}</div>
  </div>
</template>

<style scoped>
.role-card {
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  background: #fff;
  padding: 10px 12px;
  transition: box-shadow 0.18s, border-color 0.18s;
}
.role-card.running { border-color: rgba(99, 102, 241, 0.4); box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.08); }
.role-card.waiting { border-color: rgba(251, 191, 36, 0.5); }
.role-card.done { border-color: rgba(52, 211, 153, 0.4); }
.role-card.failed { border-color: rgba(248, 113, 113, 0.5); }
.role-head { display: flex; align-items: center; gap: 10px; cursor: pointer; }
.role-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, #818cf8, #6366f1);
  color: #fff; display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 500; flex-shrink: 0;
}
.role-info { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.role-name { font-size: 14px; color: #1e293b; font-weight: 500; }
.role-badge { font-size: 12px; padding: 1px 6px; border-radius: 4px; width: fit-content; }
.role-badge.idle { background: #f1f5f9; color: #64748b; }
.role-badge.running { background: rgba(99, 102, 241, 0.12); color: #6366f1; }
.role-badge.waiting { background: rgba(251, 191, 36, 0.18); color: #b45309; }
.role-badge.done { background: rgba(52, 211, 153, 0.18); color: #047857; }
.role-badge.failed, .role-badge.cancelled { background: rgba(248, 113, 113, 0.15); color: #b91c1c; }
.role-line { margin-top: 8px; font-size: 13px; color: #475569; }
.role-line.guide { color: #b45309; font-weight: 500; }
.role-line.done { color: #047857; }
.line-toggle {
  border: none; background: transparent; color: #6366f1;
  cursor: pointer; font-size: 12px; padding: 0;
}
.busy-line { margin-top: 4px; cursor: pointer; }
.role-error { margin-top: 6px; font-size: 12px; color: #b91c1c; }
</style>
