<script setup>
import { computed, ref } from 'vue'
import { planArtifacts } from '../composables/artifactsProjection.js'
import { ROLE_LABELS } from './roleMeta.js'

const props = defineProps({ tasks: { type: Array, default: () => [] } })
const emit = defineEmits(['preview-task'])

const rows = computed(() => planArtifacts(props.tasks))
const hasRows = computed(() => rows.value.length > 0)

const previewSrc = ref('')
function openImage(url) { if (url) previewSrc.value = url }
function closeImage() { previewSrc.value = '' }
function openFinalize(row) { emit('preview-task', row.task) }
</script>

<template>
  <section class="artifacts-card" aria-labelledby="artifacts-title">
    <header class="artifacts-head">
      <h2 id="artifacts-title">创作产出</h2>
    </header>

    <p v-if="!hasRows" class="artifacts-empty">尚无产出，创作开始后这里会汇总每步成果</p>

    <ul v-else class="artifacts-list">
      <li v-for="row in rows" :key="row.kind" class="artifact-row">
        <span class="artifact-icon" aria-hidden="true">
          <svg v-if="row.kind === 'idea'" viewBox="0 0 24 24">
            <path d="M9 18h6M10 22h4M8.4 14.6A7 7 0 1 1 15.6 14.6C14.6 15.4 14 16.1 14 17h-4c0-.9-.6-1.6-1.6-2.4Z" />
          </svg>
          <svg v-else-if="row.kind === 'script'" viewBox="0 0 24 24">
            <path d="M6 3h8l4 4v14H6zM14 3v5h4M9 13h6M9 17h6" />
          </svg>
          <svg v-else-if="row.kind === 'image'" viewBox="0 0 24 24">
            <rect x="3" y="4" width="18" height="16" rx="2" />
            <circle cx="8.5" cy="9" r="1.5" />
            <path d="m4 17 5-5 3 3 2-2 6 6" />
          </svg>
          <svg v-else viewBox="0 0 24 24">
            <path d="M4 7h16v13H4zM3 4h18v3H3zM9 11h6" />
          </svg>
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
          <svg viewBox="0 0 24 24"><path d="m9 5 7 7-7 7" /></svg>
        </span>
      </li>
    </ul>

    <Teleport to="body">
      <div v-if="previewSrc" class="image-overlay" @click="closeImage">
        <img :src="previewSrc" alt="配图预览" />
        <button type="button" class="overlay-close" aria-label="关闭预览" @click.stop="closeImage">
          <svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" /></svg>
        </button>
      </div>
    </Teleport>
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
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) 14px;
  gap: var(--ch-space-3);
  align-items: start;
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

.artifact-row:hover::before {
  background: var(--ch-surface-3);
}

.artifact-icon {
  position: relative;
  z-index: 1;
  width: 32px;
  height: 32px;
  margin-top: 8px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--ch-accent-soft);
  color: var(--ch-accent-soft-text);
}

.artifact-icon svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.5;
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
  margin-top: 11px;
  color: var(--ch-text-faint);
  opacity: .55;
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

.artifact-row:hover .artifact-arrow {
  color: var(--ch-ink);
  opacity: 1;
  transform: translateX(2px);
}

.image-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ch-space-6);
  background: var(--ch-overlay-strong);
  backdrop-filter: blur(8px);
  cursor: zoom-out;
}

.image-overlay img {
  max-width: min(90vw, 720px);
  max-height: 80vh;
  border-radius: var(--ch-radius-card);
  object-fit: contain;
}

.overlay-close {
  position: absolute;
  top: 24px;
  right: 24px;
  width: 36px;
  height: 36px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: var(--ch-overlay-control);
  color: var(--ch-on-accent);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background .2s ease-out;
}

.overlay-close:hover {
  background: var(--ch-overlay-control-hover);
}

.overlay-close svg {
  width: 18px;
  height: 18px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
}

@media (prefers-reduced-motion: reduce) {
  .artifact-row::before,
  .artifact-arrow,
  .overlay-close { transition: none; }
}
</style>
