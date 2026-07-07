<script setup>
import { computed } from 'vue'

import RoleCard from './RoleCard.vue'
import IntentStateCard from './IntentStateCard.vue'

const props = defineProps({
  graph: { type: Object, default: null },
  focusedTaskId: { type: String, default: null },
  intentState: { type: Object, default: null },
  hasActiveTask: { type: Boolean, default: false },
})
const emit = defineEmits(['focus', 'confirm', 'revise', 'stop-and-revise'])

const tasks = computed(() => props.graph?.tasks || [])
const hasIntent = computed(() => !!props.intentState)

function onFocus(id) {
  emit('focus', id)
}
</script>

<template>
  <aside class="team-panel">
    <IntentStateCard
      v-if="hasIntent"
      :state="intentState"
      :has-active-task="hasActiveTask"
      @confirm="$emit('confirm')"
      @revise="$emit('revise')"
      @stop-and-revise="$emit('stop-and-revise')"
    />
    <div v-if="!tasks.length && !hasIntent" class="team-empty">暂无创作任务</div>
    <template v-if="tasks.length">
      <div class="team-head">
        <div class="h">创作团队</div>
        <div class="sub">{{ tasks.length }} 个角色 · 流水线协作中</div>
      </div>
      <section class="role-list">
        <RoleCard
          v-for="t in tasks"
          :key="t.id"
          :task="t"
          :focused="t.id === focusedTaskId"
          @focus="onFocus(t.id)"
        />
      </section>
      <div class="legend">
        <span><i class="dot-running"></i>工作中</span>
        <span><i class="dot-waiting"></i>待确认</span>
        <span><i class="dot-done"></i>已完成</span>
        <span><i class="dot-idle"></i>排队</span>
      </div>
    </template>
  </aside>
</template>

<style scoped>
.team-panel {
  width: 280px;
  flex-shrink: 0;
  border-left: 1px solid var(--ch-border);
  background: var(--ch-team-surface);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

/* 顶部意图卡固定不压 */
.team-panel > :deep(.intent-card) {
  flex-shrink: 0;
  margin: 14px 14px 0;
}

.team-head {
  flex-shrink: 0;
  padding: 18px 18px 12px;
}

.team-head .h {
  font-family: var(--ch-serif);
  font-weight: 600;
  font-size: 16px;
  color: var(--ch-text);
  letter-spacing: 0.02em;
}

.team-head .sub {
  font-size: 11.5px;
  color: var(--ch-faint);
  margin-top: 2px;
}

.role-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 14px 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: thin;
}

.legend {
  flex-shrink: 0;
  padding: 10px 16px;
  border-top: 1px solid var(--ch-border);
  font-size: 11px;
  color: var(--ch-faint);
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.legend span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.legend i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot-running { background: var(--ch-orange); }
.dot-waiting { background: var(--ch-primary); }
.dot-done { background: var(--ch-green); }
.dot-idle { background: var(--ch-faint); }

.team-empty {
  color: var(--ch-faint);
  font-size: 13px;
  text-align: center;
  padding: 40px 0 0;
}
</style>
