<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  state: { type: Object, default: null },
})
const emit = defineEmits(['confirm', 'revise'])
const locking = ref(false)
const archived = computed(() => props.state?.status === 'answered')

const clean = (value, fallback = '待补充') => {
  const text = value == null ? '' : String(value).trim()
  return text || fallback
}

const title = computed(() => clean(props.state?.topic, '请确认这次创作方向'))
const direction = computed(() => clean(props.state?.style, '风格自由发挥'))
const meta = computed(() => [
  { label: '发布平台', value: clean(props.state?.platform) },
  { label: '内容体裁', value: clean(props.state?.format) },
  {
    label: '配图规划',
    value: props.state?.image_count != null ? `${props.state.image_count} 张` : '待确定',
  },
])
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
  if (locking.value || archived.value) return
  locking.value = true
  emit(type)
}
</script>

<template>
  <section class="intent-confirm" :class="{ archived }">
    <header class="card-head">
      <div class="head-copy">
        <h2>确认创作意图</h2>
        <p>确认本次创作的方向与要求</p>
      </div>
      <span class="status ch-status-pill" :class="archived ? 'is-complete' : 'is-awaiting'">
        <i aria-hidden="true"></i>{{ archived ? '已确认' : '待确认' }}
      </span>
    </header>

    <div class="brief">
      <div class="section-heading">
        <span class="section-title">主题方向</span>
      </div>
      <h2>{{ title }}</h2>
      <div class="meta" aria-label="创作规格">
        <div v-for="item in meta" :key="item.label" class="meta-item">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>
      <div class="direction">
        <span>表达风格</span>
        <strong>{{ direction }}</strong>
      </div>
    </div>

    <section v-if="notes.length" class="focus">
      <header class="section-heading focus-head">
        <span class="section-title">补充要求</span>
        <span class="section-meta">{{ notes.length }} 项</span>
      </header>
      <dl>
        <div v-for="note in notes" :key="note.label">
          <dt>{{ note.label }}</dt>
          <dd>{{ note.value }}</dd>
        </div>
      </dl>
    </section>

    <footer v-if="!archived" class="actions">
      <button class="revise" type="button" :disabled="locking" @click="decide('revise')">
        继续调整
      </button>
      <button class="confirm" type="button" :disabled="locking" @click="decide('confirm')">
        确认并开始创作
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6" /></svg>
      </button>
    </footer>
  </section>
</template>

<style scoped>
.intent-confirm {
  position: relative;
  width: 100%;
  padding: var(--ch-space-5);
  overflow: hidden;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-soft);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: var(--ch-space-4);
  padding-bottom: var(--ch-space-3);
  border-bottom: 1px solid var(--ch-border);
}

.head-copy {
  min-width: 0;
}

.head-copy h2 {
  margin: 0;
  font-size: var(--ch-text-lg);
  font-weight: 600;
  line-height: var(--ch-leading-snug);
}

.head-copy p {
  margin: 8px 0 0;
  color: var(--ch-text-muted);
  font-size: var(--ch-text-sm);
  line-height: 1.5;
}

.status {
  flex: 0 0 auto;
  margin-left: auto;
}

.brief {
  margin: 0;
  padding: 0;
  border: 0;
}

.section-heading {
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
}

.section-heading::before {
  width: 4px;
  height: 16px;
  flex: 0 0 4px;
  border-radius: var(--ch-radius-pill);
  background: var(--ch-accent);
  content: "";
}

.brief h2 {
  max-width: 760px;
  margin: var(--ch-space-3) 0 var(--ch-space-4);
  font-size: var(--ch-text-lg);
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: -.01em;
}

.meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--ch-space-3);
}

.meta-item {
  display: flex;
  min-width: 0;
  min-height: 72px;
  flex-direction: column;
  justify-content: center;
  padding: var(--ch-space-2) var(--ch-space-3);
  border-radius: var(--ch-radius-list);
  background: var(--ch-surface-2);
}

.meta-item span,
.meta-item strong {
  display: block;
}

.meta-item span {
  color: var(--ch-text-muted);
  font-size: var(--ch-text-xs);
  line-height: 1.5;
}

.meta-item strong {
  margin-top: 4px;
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  font-weight: 600;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.direction {
  display: flex;
  min-height: 72px;
  flex-direction: column;
  justify-content: center;
  margin-top: var(--ch-space-3);
  padding: var(--ch-space-2) var(--ch-space-3);
  border-radius: var(--ch-radius-list);
  background: var(--ch-surface-2);
}

.direction span {
  color: var(--ch-text-muted);
  font-size: var(--ch-text-xs);
  line-height: 1.5;
}

.direction strong {
  margin-top: 4px;
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  font-weight: 600;
  line-height: 1.5;
  overflow-wrap: anywhere;
}

.focus {
  margin-top: var(--ch-space-3);
  overflow: hidden;
  border-bottom: 1px solid var(--ch-border);
}

.focus-head {
  min-height: 48px;
  border-bottom: 1px solid var(--ch-border);
}

.section-title {
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
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
  padding: 0 var(--ch-space-2);
}

.focus dl > div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
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

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin: var(--ch-space-4) 0 0;
  background: var(--ch-surface);
}

.actions button {
  display: inline-flex;
  min-height: 40px;
  align-items: center;
  justify-content: center;
  gap: 6px;
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
  background: var(--ch-ink);
  color: var(--ch-on-ink);
}

.confirm:hover:not(:disabled) {
  background: var(--ch-ink-hover);
}

.confirm svg {
  width: 15px;
  height: 15px;
  fill: none;
  stroke: currentColor;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 2;
}

@media (max-width: 700px) {
  .intent-confirm {
    padding: 16px;
  }

  .section-meta {
    display: none;
  }

  .brief h2 {
    font-size: var(--ch-text-lg);
  }

  .meta {
    grid-template-columns: repeat(2, minmax(0, 1fr));
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

@media (max-width: 460px) {
  .meta {
    grid-template-columns: 1fr;
  }
}
</style>
