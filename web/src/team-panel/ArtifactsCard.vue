<script setup>
import { computed } from 'vue'
import { Archive, ChevronRight, FileCode2, Image, Lightbulb } from '@lucide/vue'
import { planArtifacts } from '../composables/artifactsProjection.js'
import { ROLE_LABELS } from './roleMeta.js'

const props = defineProps({ tasks: { type: Array, default: () => [] } })
const emit = defineEmits(['focus-task'])

const rows = computed(() => planArtifacts(props.tasks))
const hasRows = computed(() => rows.value.length > 0)

function focusTask(row) { emit('focus-task', row.task) }
</script>

<template>
  <section class="artifacts-card" aria-labelledby="artifacts-title">
    <header class="artifacts-head">
      <h2 id="artifacts-title">创作产出</h2>
    </header>

    <p v-if="!hasRows" class="artifacts-empty">尚无产出，创作开始后这里会汇总每步成果</p>

    <TransitionGroup v-else name="artifact-row" tag="ul" class="artifacts-list">
      <li v-for="row in rows" :key="row.kind">
        <button
          type="button"
          class="artifact-row"
          :aria-label="`跳转到${ROLE_LABELS[row.kind]}卡片`"
          @click="focusTask(row)"
        >
          <span class="artifact-icon" aria-hidden="true">
            <Lightbulb v-if="row.kind === 'idea'" />
            <FileCode2 v-else-if="row.kind === 'script'" />
            <Image v-else-if="row.kind === 'image'" />
            <Archive v-else />
          </span>
          <div class="artifact-body">
            <span class="artifact-role">{{ ROLE_LABELS[row.kind] }}</span>

            <p v-if="row.kind === 'idea'" class="artifact-text" :title="row.title">
              {{ row.title || '已确定选题' }}
            </p>

            <p v-else-if="row.kind === 'script'" class="artifact-text">
              {{ row.charCount }} 字 · {{ row.blockCount }} 段
            </p>

            <template v-else-if="row.kind === 'image'">
              <p class="artifact-text">{{ row.images.length }} 张配图</p>
            </template>

            <template v-else-if="row.kind === 'finalize'">
              <p class="artifact-text">{{ row.title || '已交付成品' }}</p>
            </template>
          </div>
          <span class="artifact-arrow" aria-hidden="true">
            <ChevronRight />
          </span>
        </button>
      </li>
    </TransitionGroup>
  </section>
</template>

<style scoped>
.artifacts-card {
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.artifacts-head {
  display: flex;
  align-items: center;
}

.artifacts-head h2 {
  margin: 0;
  color: var(--ch-ink);
  font-size: 18px;
  font-weight: 600;
  line-height: 24px;
}

.artifacts-empty {
  margin: var(--ch-space-3) 0 0;
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 18px;
}

.artifacts-list {
  list-style: none;
  margin: var(--ch-space-3) 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--ch-space-3);
}

.artifact-row {
  position: relative;
  width: 100%;
  border: 0;
  margin: 0;
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) 14px;
  gap: var(--ch-space-3);
  align-items: center;
  padding-right: var(--ch-space-2);
  color: inherit;
  font: inherit;
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.artifact-row-enter-active,
.artifact-row-leave-active,
.artifact-row-move {
  transition: opacity var(--ch-duration-normal) var(--ch-ease-out),
    transform var(--ch-duration-normal) var(--ch-ease-out);
}

.artifact-row-enter-from,
.artifact-row-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.artifact-row-leave-active {
  position: absolute;
  width: 100%;
}

.artifact-row::before {
  position: absolute;
  inset: -6px -8px;
  z-index: 0;
  border-radius: var(--ch-radius-list);
  background: transparent;
  content: "";
  transition: background var(--ch-duration-fast) var(--ch-ease);
}

.artifact-row:hover::before,
.artifact-row:focus-visible::before {
  background: var(--ch-muted-gradient);
}

.artifact-row:focus-visible {
  outline: 2px solid var(--ch-focus-ring, var(--ch-border-strong));
  outline-offset: 4px;
}

.artifact-icon {
  position: relative;
  z-index: 1;
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--ch-muted-gradient);
  color: var(--ch-text-faint);
}

.artifact-icon svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.artifact-body {
  position: relative;
  z-index: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.artifact-role {
  color: var(--ch-text-muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
}

.artifact-text {
  margin: 0;
  overflow: hidden;
  color: var(--ch-text);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-arrow {
  position: relative;
  z-index: 1;
  width: 14px;
  height: 14px;
  color: var(--ch-text-secondary);
  opacity: 0;
  transition:
    color var(--ch-duration-fast) var(--ch-ease),
    opacity var(--ch-duration-fast) var(--ch-ease),
    transform var(--ch-duration-fast) var(--ch-ease);
}

.artifact-arrow svg {
  display: block;
  width: 100%;
  height: 100%;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.artifact-row:hover .artifact-arrow,
.artifact-row:focus-visible .artifact-arrow {
  opacity: 1;
  transform: translateX(2px);
}

@media (prefers-reduced-motion: reduce) {
  .artifact-row::before,
  .artifact-arrow,
  .artifact-row { scroll-behavior: auto; }
}
</style>
