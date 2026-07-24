<script setup>
import { ref, watch, nextTick, computed, onMounted, onUnmounted } from 'vue'
import MessageBubble from './MessageBubble.vue'
import HilCard from './HilCard.vue'
import ArtifactCard from './ArtifactCard.vue'
import PlatformPreviewShell from './PlatformPreviewShell.vue'
import RunningPanel from './RunningPanel.vue'
import RecoveryCard from './RecoveryCard.vue'
import ConfirmedCard from './ConfirmedCard.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  streaming: { type: Boolean, default: false },
  sessionId: { type: String, default: '' },
  sessionUpdatedAt: { type: Number, default: null },
  intentState: { type: Object, default: null },
})

defineEmits(['hil-confirmed', 'hil-retried', 'hil-cancelled', 'intent-confirm', 'intent-revise'])

const container = ref(null)
const stickToBottom = ref(false)
let lastScrollPosition = null

function usesPageScroll(el) {
  return el && getComputedStyle(el).overflowY === 'visible'
}

function onScroll() {
  const el = container.value
  if (!el) return
  const pageScroll = usesPageScroll(el)
  const currentPosition = pageScroll ? window.scrollY : el.scrollTop
  const movedUp = lastScrollPosition !== null && currentPosition < lastScrollPosition
  const distanceFromBottom = pageScroll
    ? document.documentElement.scrollHeight - window.scrollY - window.innerHeight
    : el.scrollHeight - el.scrollTop - el.clientHeight

  if (movedUp) stickToBottom.value = false
  else if (distanceFromBottom < 80) stickToBottom.value = true
  lastScrollPosition = currentPosition
}

function scrollToBottom(behavior = 'auto') {
  const el = container.value
  if (!el) return
  if (usesPageScroll(el)) window.scrollTo({ top: document.documentElement.scrollHeight, behavior })
  else el.scrollTo({ top: el.scrollHeight, behavior })
}

function followBottom(behavior = 'auto') {
  stickToBottom.value = true
  lastScrollPosition = usesPageScroll(container.value) ? window.scrollY : container.value?.scrollTop ?? 0
  scrollToBottom(behavior)
}

defineExpose({ scrollToBottom, followBottom })

const previewTask = ref(null)
function openPreview(task) { previewTask.value = task }

function messageKey(msg, idx) {
  return msg.id || `${msg.kind || msg.role}:${msg.task?.id || idx}`
}

const MONTH_EN = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']

const datelineEn = computed(() => {
  const ts = props.sessionUpdatedAt
  if (!ts) return ''
  const date = new Date(ts * 1000)
  return `${date.getFullYear()} · ${MONTH_EN[date.getMonth()]} ${String(date.getDate()).padStart(2, '0')}`
})

const datelineTime = computed(() => {
  const ts = props.sessionUpdatedAt
  if (!ts) return ''
  const date = new Date(ts * 1000)
  const hour = date.getHours()
  const minute = date.getMinutes()
  const period = hour < 6 ? '凌晨' : hour < 12 ? '上午' : hour < 14 ? '中午' : hour < 18 ? '午后' : '入夜'
  const h12 = hour % 12 === 0 ? 12 : hour % 12
  return `${period} ${h12}:${String(minute).padStart(2, '0')}`
})

const displayMessages = computed(() => {
  const result = []
  for (const message of props.messages) {
    if (message.kind === 'intent-confirm') {
      const previous = result[result.length - 1]
      if (previous && previous.role === 'assistant' && !previous.kind) {
        result[result.length - 1] = { ...previous, intentState: message.state }
        continue
      }
    }
    result.push(message)
  }
  return result
})

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))

watch(
  () => ({
    structure: props.messages.map((m, idx) => messageKey(m, idx)).join('|'),
    content: props.messages.map((m) => {
      const tItems = m.tools?.items || []
      const toolsSig = tItems
        .map((t) => `${t.content?.length ?? 0}:${t.duration_ms ?? ''}`)
        .join(',')
      return (
        m.content +
        '|' +
        (m.thinking?.state ?? 'idle') +
        '|' +
        (m.tools?.state ?? 'idle') +
        '|' +
        tItems.length +
        '|' +
        toolsSig
      )
    }).join('\u0001'),
  }),
  () => {
    if (!stickToBottom.value) return
    nextTick(() => {
      const el = container.value
      if (!el || !stickToBottom.value) return
      if (usesPageScroll(el)) window.scrollTo({ top: document.documentElement.scrollHeight })
      else el.scrollTop = el.scrollHeight
    })
  },
  { deep: true }
)

watch(
  () => props.sessionId,
  () => {
    nextTick(() => {
      scrollToBottom()
    })
  }
)
</script>

<template>
  <div ref="container" class="chat-window" @scroll="onScroll">
    <slot name="scroll-header"></slot>
    <div class="chat-inner">
      <TransitionGroup name="flow-stage" tag="div" class="flow-list">
        <div v-for="(msg, idx) in displayMessages" :key="messageKey(msg, idx)" class="flow-entry">
          <HilCard
            v-if="msg.kind === 'hil'"
            :task="msg.task"
            :session-id="sessionId"
            @confirmed="$emit('hil-confirmed', $event)"
            @retried="$emit('hil-retried', $event)"
            @cancelled="$emit('hil-cancelled', $event)"
            @preview-task="openPreview"
          />
          <ArtifactCard v-else-if="msg.kind === 'postcard'" :task="msg.task" @preview="openPreview(msg.task)" />
          <ConfirmedCard v-else-if="msg.kind === 'confirmed'" :task="msg.task" />
          <RunningPanel v-else-if="msg.kind === 'running'" :task="msg.task" />
          <RecoveryCard
            v-else-if="msg.kind === 'recovery'"
            :task="msg.task"
            :session-id="sessionId"
            @retried="$emit('hil-retried', $event)"
            @cancelled="$emit('hil-cancelled', $event)"
          />
          <MessageBubble
            v-else
            :role="msg.role"
            :content="msg.content"
            :created-at="msg.created_at"
            :thinking="msg.thinking"
            :tools="msg.tools"
            :intent-state="msg.intentState"
            :suspended="msg.suspended"
            :active="streaming && idx === displayMessages.length - 1 && msg.role === 'assistant'"
            @intent-confirm="$emit('intent-confirm')"
            @intent-revise="$emit('intent-revise')"
          />
        </div>
      </TransitionGroup>
      <div v-if="messages.length === 0" class="empty-hint">
        <div class="empty-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z"/><path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14z"/></svg>
        </div>
        <h2>今天想创作什么？</h2>
        <p>描述你的想法，我会和创作团队一起把它变成完整作品。</p>
        <div class="starter-grid">
          <button type="button"><span class="starter-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l1.6 4.4L18 9l-4.4 1.6L12 15l-1.6-4.4L6 9l4.4-1.6L12 3z"/><path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14z"/></svg></span><b>策划选题</b><small>从一个想法梳理内容方向</small></button>
          <button type="button"><span class="starter-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/></svg></span><b>创作文案</b><small>生成结构清晰的发布内容</small></button>
          <button type="button"><span class="starter-icon"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="9" cy="9" r="1.6"/><path d="M21 15l-5-5L5 21"/></svg></span><b>视觉构思</b><small>探索画面风格与配图方案</small></button>
        </div>
      </div>
    </div>
    <Transition name="preview-modal">
      <div v-if="previewTask" class="preview-overlay" @click.self="previewTask = null">
        <div class="preview-frame">
          <button class="preview-close" type="button" aria-label="关闭预览" @click="previewTask = null">✕</button>
          <PlatformPreviewShell
            :card="previewTask.artifacts || {}"
            :preview-ref="previewTask.artifacts?.meta?.preview_ref"
            :stylesheet-ref="previewTask.artifacts?.meta?.stylesheet_ref"
          />
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 24px var(--ch-paper-pad) 144px;
  background: transparent;
  scrollbar-gutter: stable both-edges;
}

.chat-inner {
  max-width: none;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}

.flow-list {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.flow-entry { width: 100%; min-width: 0; }
.flow-stage-enter-active { transition: opacity .3s cubic-bezier(.2,.72,.25,1), transform .3s cubic-bezier(.2,.72,.25,1); }
.flow-stage-leave-active { position: absolute; width: 100%; transition: opacity .18s ease-in, transform .18s ease-in; pointer-events: none; }
.flow-stage-enter-from { opacity: 0; transform: translateY(12px); }
.flow-stage-leave-to { opacity: 0; transform: translateY(-7px); }
.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 560px;
  padding: 64px 0;
  color: var(--ch-text-faint);
  text-align: center;
}
.empty-mark {
  width: 64px;
  height: 64px;
  margin-bottom: 24px;
  display: grid;
  place-items: center;
  border-radius: var(--ch-radius-card);
  background: var(--ch-accent-gradient);
  color: var(--ch-on-accent);
  box-shadow: 0 12px 28px rgba(99, 102, 241, .22);
}
.empty-mark svg { width: 32px; height: 32px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.empty-hint h2 { margin: 0; color: var(--ch-text); font: 600 28px/1.3 var(--ch-font-sans); }
.empty-hint > p { max-width: 480px; margin: 0 0 24px; color: var(--ch-text-muted); font: 400 14px/1.6 var(--ch-font-sans); }
.starter-grid { width: min(100%, 640px); display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.starter-grid button { min-height: 144px; display: flex; flex-direction: column; align-items: flex-start; padding: 24px; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-card); background: var(--ch-surface); color: var(--ch-text); text-align: left; cursor: default; box-shadow: var(--ch-shadow-sm); }
.starter-grid .starter-icon { display: inline-flex; margin-bottom: 24px; color: var(--ch-accent); }
.starter-grid .starter-icon svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.starter-grid b { margin-bottom: 8px; font: 600 14px/1.4 var(--ch-font-sans); }
.starter-grid small { color: var(--ch-text-muted); font: 400 12px/1.5 var(--ch-font-sans); }

.chat-inner :deep(.hil-card),
.chat-inner :deep(.recovery-card),
.chat-inner :deep(.running),
.chat-inner :deep(.confirmed-card),
.chat-inner :deep(.artifact-wrap:not(.review)) {
  margin: 32px 0 16px;
}
.chat-inner :deep(.intent-confirm) {
  margin: 16px 0 0;
}

.preview-overlay { position: fixed; inset: 0; z-index: 80; display: flex; align-items: flex-start; justify-content: center; padding: 40px 20px; background: rgba(15, 23, 42, .55); overflow-y: auto; }
.preview-frame { position: relative; width: min(100%, 880px); background: var(--ch-surface); padding: 32px 24px 24px; border-radius: var(--ch-radius-card); box-shadow: var(--ch-shadow-lg); }
.preview-close { position: absolute; top: 8px; right: 8px; width: 32px; height: 32px; border: 0; background: transparent; color: var(--ch-text-muted); font-size: 18px; line-height: 1; cursor: pointer; }
.preview-close:hover { color: var(--ch-text); }
.preview-modal-enter-active, .preview-modal-leave-active { transition: opacity .2s; }
.preview-modal-enter-from, .preview-modal-leave-to { opacity: 0; }
@media (max-width: 780px) {
  .chat-window { padding-inline: 16px; }
  .empty-hint { min-height: 480px; padding: 48px 0; }
  .starter-grid { grid-template-columns: 1fr; }
  .starter-grid button { min-height: 96px; padding: 16px; }
  .starter-grid .starter-icon { margin-bottom: 8px; }
}
</style>
