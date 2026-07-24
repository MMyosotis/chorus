<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  state: { type: Object, default: null },
  archived: { type: Boolean, default: false },
})
const emit = defineEmits(['confirm', 'revise'])
const locking = ref(false)

const clean = (value, fallback = '待补充') => {
  const text = value == null ? '' : String(value).trim()
  return text || fallback
}

const title = computed(() => clean(props.state?.topic, '请确认这次创作方向'))
const meta = computed(() => [
  clean(props.state?.platform),
  clean(props.state?.format),
  props.state?.image_count != null ? `${props.state.image_count} 张配图` : '配图待定',
])
const direction = computed(() => clean(props.state?.style, '风格自由发挥'))
const notes = computed(() =>
  Object.entries(props.state?.extra || {})
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim())
    .slice(0, 4)
    .map(([label, value]) => ({
      label,
      value: Array.isArray(value) ? value.join('、') : String(value),
    }))
)

function decide(type) {
  if (locking.value || props.archived) return
  locking.value = true
  emit(type)
}
</script>

<template>
  <section class="intent-confirm" :class="{ archived }">
    <header class="card-head">
      <div class="head-copy">
        <p>选题签发</p>
      </div>
      <span class="status">{{ archived ? '已签发' : '待确认' }}</span>
    </header>

    <div class="brief">
      <span class="eyebrow">本次创作方向</span>
      <h2>{{ title }}</h2>
      <div class="meta" aria-label="创作规格">
        <span v-for="item in meta" :key="item">{{ item }}</span>
      </div>
    </div>

    <div class="direction">
      <div>
        <small>表达气质</small>
        <p>{{ direction }}</p>
      </div>
    </div>

    <section v-if="notes.length" class="focus">
      <header class="focus-head">
        <span class="section-title">创作重点</span>
        <span class="section-meta">已整理 {{ notes.length }} 项</span>
      </header>
      <dl>
        <div v-for="note in notes" :key="note.label">
          <dt>{{ note.label }}</dt>
          <dd>{{ note.value }}</dd>
        </div>
      </dl>
    </section>

    <footer class="actions">
      <p v-if="archived" class="archived-note">选题已进入创作流程</p>
      <template v-else>
        <button class="revise" type="button" :disabled="locking" @click="decide('revise')">
          继续调整
        </button>
        <button class="confirm" type="button" :disabled="locking" @click="decide('confirm')">
          确认并开始创作
        </button>
      </template>
    </footer>
  </section>
</template>

<style scoped>
.intent-confirm {
  position: relative;
  width: 100%;
  padding: var(--ch-space-4);
  overflow: hidden;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-sm);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.head-copy {
  min-width: 0;
}

.head-copy p {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
}

.status {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  gap: 8px;
  margin-left: auto;
  padding: 0 8px;
  border-radius: var(--ch-radius-pill);
  background: var(--ch-warning-soft);
  color: var(--ch-warning-text);
  font: 600 12px/1 var(--ch-font-sans);
}

.archived .status {
  background: var(--ch-success-soft);
  color: var(--ch-success-text);
}

.brief {
  padding: 32px 0 24px;
}

.eyebrow {
  color: var(--ch-text-muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
}

.brief h2 {
  max-width: 680px;
  margin: 8px 0 16px;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  letter-spacing: 0;
}

.meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.meta span {
  display: inline-flex;
  min-height: 32px;
  align-items: center;
  padding: 0 8px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface-2);
  color: var(--ch-text-secondary);
  font: 500 12px/1 var(--ch-font-sans);
}

.direction {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface-3);
}

.direction small {
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.direction p {
  margin: 8px 0 0;
  color: var(--ch-text);
  font-size: 14px;
  font-weight: 500;
  line-height: 1.5;
}

.focus {
  overflow: hidden;
  margin-top: 24px;
  border-top: 1px solid var(--ch-border);
  border-bottom: 1px solid var(--ch-border);
}

.focus-head {
  display: flex;
  min-height: 56px;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid var(--ch-border);
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.5;
}

.section-meta {
  margin-left: auto;
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.focus dl {
  margin: 0;
  padding: 0 16px;
}

.focus dl > div {
  display: grid;
  grid-template-columns: 80px minmax(0, 1fr);
  gap: 16px;
  padding: 16px 0;
  border-bottom: 1px solid var(--ch-border);
}

.focus dl > div:last-child {
  border-bottom: 0;
}

.focus dt {
  color: var(--ch-text-muted);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
}

.focus dd {
  margin: 0;
  color: var(--ch-text-secondary);
  font-size: 14px;
  line-height: 1.5;
}

.focus + .actions {
  padding-top: 24px;
  border-top: 0;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 24px;
  border-top: 1px solid var(--ch-border);
}

.actions button {
  min-height: 40px;
  padding: 0 16px;
  border-radius: var(--ch-radius-btn);
  font: 600 14px/1 var(--ch-font-sans);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease);
}

.actions button:disabled {
  cursor: default;
  opacity: .5;
}

.revise {
  border: 1px solid var(--ch-border-strong);
  background: var(--ch-surface);
  color: var(--ch-text);
}

.revise:hover:not(:disabled) {
  background: var(--ch-surface-2);
}

.confirm {
  border: 0;
  background: var(--ch-accent);
  color: var(--ch-on-accent);
}

.confirm:hover:not(:disabled) {
  background: var(--ch-accent-hover);
}

.archived-note {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 auto 0 0;
  color: var(--ch-success-text);
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 700px) {
  .intent-confirm {
    padding: 16px;
  }

  .section-meta {
    display: none;
  }

  .brief {
    padding: 24px 0;
  }

  .focus dl > div {
    grid-template-columns: 64px minmax(0, 1fr);
    gap: 8px;
  }

  .actions {
    flex-wrap: wrap;
  }

  .actions button {
    flex: 1 1 auto;
  }
}
</style>
