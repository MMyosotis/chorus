<script setup>
import { computed, ref } from 'vue'
import { ChevronRight, FileText, Heart, Image, Monitor } from '@lucide/vue'

const props = defineProps({
  state: { type: Object, default: null },
  hideActions: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})
const emit = defineEmits(['confirm', 'revise'])
const locking = ref(false)
const archived = computed(() => props.state?.status === 'answered')

const clean = (value, fallback = '待补充') => {
  const text = value == null ? '' : String(value).trim()
  return text || fallback
}

const title = computed(() => clean(props.state?.topic, '请确认这次创作方向'))
const meta = computed(() => [
  { label: '发布平台', value: clean(props.state?.platform), icon: 'platform' },
  { label: '内容体裁', value: clean(props.state?.format), icon: 'format' },
  { label: '表达风格', value: clean(props.state?.style, '风格自由发挥'), icon: 'style' },
  {
    label: '配图规划',
    value: props.state?.image_count != null ? `${props.state.image_count} 张` : '待确定',
    icon: 'image',
  },
])
const notes = computed(() =>
  Object.entries(props.state?.extra || {})
    .filter(([, value]) => value !== null && value !== undefined && String(value).trim())
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

defineExpose({
  confirm: () => decide('confirm'),
  revise: () => decide('revise'),
})
</script>

<template>
  <section class="intent-confirm" :class="{ archived, compact }">
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
    </div>
    <div class="meta" aria-label="创作规格">
      <div v-for="item in meta" :key="item.label" class="meta-item">
        <span class="meta-icon" aria-hidden="true">
          <Monitor v-if="item.icon === 'platform'" />
          <FileText v-else-if="item.icon === 'format'" />
          <Heart v-else-if="item.icon === 'style'" />
          <Image v-else />
        </span>
        <span class="meta-copy">
          <span class="meta-label">{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </span>
      </div>
    </div>

    <section v-if="notes.length" class="focus">
      <header class="section-heading focus-head">
        <span class="section-title">补充要求</span>
        <span class="section-meta">{{ notes.length }} 项</span>
      </header>
      <dl class="focus-list">
        <div v-for="(note, index) in notes" :key="note.label" class="focus-item">
          <span class="focus-marker" aria-hidden="true">{{ String(index + 1).padStart(2, '0') }}</span>
          <dt>{{ note.label }}</dt>
          <dd>{{ note.value }}</dd>
        </div>
      </dl>
    </section>

    <footer v-if="!archived && !hideActions" class="actions">
      <button class="revise" type="button" :disabled="locking" @click="decide('revise')">
        继续调整
      </button>
      <button class="confirm" type="button" :disabled="locking" @click="decide('confirm')">
        确认并开始创作
        <ChevronRight aria-hidden="true" />
      </button>
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
  box-shadow: var(--ch-shadow-soft);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 24px;
}

.head-copy {
  min-width: 0;
}

.card-head h2 {
  margin: 0;
  font-size: var(--ch-text-xl);
  font-weight: 600;
  line-height: var(--ch-leading-snug);
  overflow-wrap: anywhere;
}

.card-head p {
  margin: 8px 0 0;
  color: var(--ch-text-muted);
  font-size: var(--ch-text-md);
  line-height: 1.5;
}

.status {
  flex: 0 0 auto;
  margin-left: auto;
}

.brief {
  margin: 0;
  padding: var(--ch-space-4);
  border: 1px solid var(--ch-accent-border);
  border-radius: var(--ch-radius-list);
  background: color-mix(in srgb, var(--ch-accent) 5%, var(--ch-surface));
}

.section-heading {
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
}

.brief h2 {
  max-width: 760px;
  margin: var(--ch-space-2) 0 0;
  font-size: var(--ch-text-xl);
  font-weight: 600;
  line-height: 1.4;
  letter-spacing: -.01em;
}

.meta {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--ch-space-3);
  margin-top: var(--ch-space-3);
}

.meta-item {
  display: flex;
  min-width: 0;
  min-height: 96px;
  align-items: center;
  gap: 16px;
  padding: 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-list);
  background: var(--ch-surface);
}

.meta-copy,
.meta-item strong {
  min-width: 0;
}

.meta-copy {
  overflow: hidden;
}

.meta-label,
.meta-item strong {
  display: block;
}

.meta-label {
  color: var(--ch-text-muted);
  font-size: var(--ch-text-xs);
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.meta-icon {
  width: 32px;
  height: 32px;
  display: grid;
  flex: 0 0 32px;
  place-items: center;
  border-radius: var(--ch-radius-btn);
  background: var(--ch-accent-soft);
}

.meta-icon svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: var(--ch-accent);
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-width: 1.8;
}

.meta-item strong {
  margin-top: 4px;
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  font-weight: 600;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.focus {
  margin-top: var(--ch-space-4);
  padding: var(--ch-space-3) 0 0;
}

.focus-head {
  min-height: auto;
  margin-bottom: var(--ch-space-3);
}

.section-title {
  min-width: 0;
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  font-weight: 600;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brief .section-title {
  color: var(--ch-accent);
}

.section-meta {
  margin-left: auto;
  color: var(--ch-text-muted);
  font-size: 12px;
  line-height: 1.5;
}

.focus-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--ch-space-2);
  margin: 0;
  padding: 0;
}

.focus-item {
  min-width: 0;
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 16px;
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface);
}

.focus-marker {
  flex: 0 0 24px;
  color: var(--ch-accent);
  font-family: var(--ch-font-mono);
  font-size: 12px;
  font-weight: 600;
  line-height: 1;
}

.focus dt {
  color: var(--ch-text-secondary);
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
}

.focus dd {
  flex: 1 1 auto;
  min-width: 0;
  margin: 0;
  color: var(--ch-text-secondary);
  font-size: 14px;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin: 16px 0 0;
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

/* 输入区确认步骤采用紧凑规格，避免遮住过多对话。 */
.intent-confirm.compact {
  padding: 24px;
  border-color: color-mix(in srgb, var(--ch-border-strong) 72%, white);
  box-shadow: var(--ch-shadow-soft);
}

.compact .head-copy h2 {
  font-size: var(--ch-text-lg);
}

.compact .head-copy p {
  display: block;
  margin-top: 4px;
  font-size: var(--ch-text-xs);
}

.compact .brief h2 {
  margin: 8px 0 0;
  font-size: var(--ch-text-md);
}

.compact .meta-item {
  min-height: 76px;
  padding: 16px;
}

.compact .focus {
  margin-top: 16px;
  padding: 16px 0 0;
}

.compact .focus-head {
  margin-bottom: 8px;
}

.compact .focus-item {
  padding: 0 16px;
}

.compact .focus dt,
.compact .focus dd {
  font-size: var(--ch-text-xs);
}

.compact .actions {
  margin-top: 16px;
}

.compact .actions button {
  min-height: 36px;
  padding: 0 14px;
}

@media (max-width: 700px) {
  .intent-confirm {
    padding: 16px;
  }

  .intent-confirm.compact {
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

  .focus-list {
    grid-template-columns: 1fr;
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
