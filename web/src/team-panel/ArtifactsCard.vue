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
        <span class="artifact-check" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 7" /></svg>
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
            <div v-if="row.images.length" class="thumb-strip">
              <button
                v-for="(img, idx) in row.images.slice(0, 3)"
                :key="idx"
                type="button"
                class="thumb"
                @click="openImage(img.url)"
              >
                <img :src="img.url" :alt="img.caption || ''" loading="lazy" />
              </button>
            </div>
          </template>

          <template v-else-if="row.kind === 'finalize'">
            <p class="artifact-text">{{ row.title || '已交付成品' }}</p>
            <div class="finalize-row">
              <button
                v-if="row.cover && row.cover.url"
                type="button"
                class="final-cover"
                @click="openImage(row.cover.url)"
              >
                <img :src="row.cover.url" :alt="row.cover.caption || row.title" loading="lazy" />
              </button>
              <button type="button" class="final-open" @click="openFinalize(row)">
                查看完整成品
              </button>
            </div>
          </template>
        </div>
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
  padding: var(--ch-space-4);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.artifacts-head {
  display: flex;
  align-items: center;
}

.artifacts-head h2 {
  margin: 0;
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
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr);
  gap: var(--ch-space-2);
  align-items: start;
}

.artifact-check {
  width: 20px;
  height: 20px;
  margin-top: 2px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--ch-accent-soft);
  color: var(--ch-accent-soft-text);
}

.artifact-check svg {
  width: 12px;
  height: 12px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.5;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.artifact-body {
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
  color: var(--ch-text-secondary);
  font-size: 14px;
  font-weight: 500;
  line-height: 22px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.thumb-strip {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.thumb {
  width: 40px;
  height: 40px;
  padding: 0;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface-3);
  overflow: hidden;
  cursor: pointer;
  transition: transform .2s ease-out, border-color .2s ease-out;
}

.thumb:hover {
  transform: scale(1.06);
  border-color: var(--ch-accent);
}

.thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.finalize-row {
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
  margin-top: 4px;
}

.final-cover {
  width: 48px;
  height: 36px;
  padding: 0;
  flex: 0 0 auto;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface-3);
  overflow: hidden;
  cursor: pointer;
  transition: transform .2s ease-out, border-color .2s ease-out;
}

.final-cover:hover {
  transform: scale(1.06);
  border-color: var(--ch-accent);
}

.final-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.final-open {
  padding: 0;
  border: none;
  background: none;
  color: var(--ch-accent);
  font-family: inherit;
  font-size: 12px;
  font-weight: 500;
  line-height: 18px;
  cursor: pointer;
  transition: color .2s ease-out;
}

.final-open:hover {
  color: var(--ch-accent-hover);
}

.image-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ch-space-6);
  background: rgba(20, 20, 24, .72);
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
  background: rgba(255, 255, 255, .12);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background .2s ease-out;
}

.overlay-close:hover {
  background: rgba(255, 255, 255, .24);
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
  .thumb, .final-cover, .final-open, .overlay-close { transition: none; }
}
</style>
