<script setup>
import { ref, watch, nextTick, computed, onMounted, onUnmounted } from 'vue'
import { BookOpen, Image as ImageIcon, PenLine } from '@lucide/vue'
import MessageBubble from './MessageBubble.vue'
import HilCard from './HilCard.vue'
import ArtifactCard from './ArtifactCard.vue'
import PlatformPreviewShell from './PlatformPreviewShell.vue'
import RunningPanel from './RunningPanel.vue'
import RecoveryCard from './RecoveryCard.vue'
import ConfirmedCard from './ConfirmedCard.vue'
import AgentAvatar from '../team-panel/AgentAvatar.vue'
import { ROLE_FULL } from '../team-panel/roleMeta.js'
import { containsMessageId } from '../composables/messageHistory.js'

const props = defineProps({
  messages: { type: Array, required: true },
  streaming: { type: Boolean, default: false },
  sessionId: { type: String, default: '' },
  sessionUpdatedAt: { type: Number, default: null },
  intentState: { type: Object, default: null },
})

defineEmits(['hil-confirmed', 'hil-retried', 'hil-cancelled', 'intent-confirm', 'intent-revise', 'option-choose'])

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

function scrollToTask(taskId) {
  if (!taskId) return
  nextTick(() => {
    const target = [...(container.value?.querySelectorAll('[data-task-id]') || [])]
      .find((element) => element.dataset.taskId === String(taskId))
    target?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

defineExpose({ scrollToBottom, followBottom, scrollToTask, openPreview })

const previewTask = ref(null)
function openPreview(task) { previewTask.value = task }

function messageKey(msg, idx) {
  return msg.id || `${msg.kind || msg.role}:${msg.task?.id || idx}`
}

function taskRoleLabel(task) {
  return ROLE_FULL[task?.agent_type] || task?.agent_type || ''
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
      if (
        previous && previous.role === 'assistant' && !previous.kind &&
        containsMessageId(previous, message.anchorMessageId)
      ) {
        result[result.length - 1] = {
          ...previous,
          recaps: [...(previous.recaps || []), { id: message.id, intentState: message.state }],
        }
        continue
      }
      result.push({ ...message, content: '', recaps: [{ id: message.id, intentState: message.state }] })
      continue
    }
    if (message.kind === 'option') {
      const previous = result[result.length - 1]
      if (
        previous && previous.role === 'assistant' && !previous.kind &&
        containsMessageId(previous, message.anchorMessageId)
      ) {
        result[result.length - 1] = {
          ...previous,
          recaps: [...(previous.recaps || []), { id: message.id, optionPrompt: message.prompt }],
        }
        continue
      }
      result.push({ ...message, content: '', recaps: [{ id: message.id, optionPrompt: message.prompt }] })
      continue
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
        <div v-for="(msg, idx) in displayMessages" :key="messageKey(msg, idx)" class="flow-entry" :data-task-id="msg.task?.id">
          <div v-if="msg.kind === 'hil'" class="hil-panel">
            <header class="task-turn-head">
              <AgentAvatar :agent-type="msg.task.agent_type" status="finished" :size="36" />
              <span>{{ taskRoleLabel(msg.task) }}</span>
            </header>
            <HilCard
              :task="msg.task"
              :session-id="sessionId"
              @confirmed="$emit('hil-confirmed', $event)"
              @retried="$emit('hil-retried', $event)"
              @preview-task="openPreview"
            />
          </div>
          <ArtifactCard v-else-if="msg.kind === 'postcard'" :task="msg.task" @preview="openPreview(msg.task)" />
          <ConfirmedCard v-else-if="msg.kind === 'confirmed'" :task="msg.task" />
          <RunningPanel v-else-if="msg.kind === 'running'" :task="msg.task" />
          <div v-else-if="msg.kind === 'recovery'" class="recovery-panel">
            <header class="task-turn-head">
              <AgentAvatar :agent-type="msg.task.agent_type" status="finished" :size="36" />
              <span>{{ taskRoleLabel(msg.task) }}</span>
            </header>
            <RecoveryCard
              :task="msg.task"
              :session-id="sessionId"
              @retried="$emit('hil-retried', $event)"
              @cancelled="$emit('hil-cancelled', $event)"
            />
          </div>
          <MessageBubble
            v-else
            :role="msg.role"
            :content="msg.content || ''"
            :thinking="msg.thinking"
            :tools="msg.tools"
            :recaps="msg.recaps"
            :suspended="msg.suspended"
            :active="streaming && idx === displayMessages.length - 1 && msg.role === 'assistant'"
            @intent-confirm="$emit('intent-confirm')"
            @intent-revise="$emit('intent-revise')"
            @option-choose="$emit('option-choose', $event)"
          />
        </div>
      </TransitionGroup>
      <div v-if="messages.length === 0" class="empty-hint">
        <div class="empty-mark" aria-hidden="true">
          <svg viewBox="0 0 18 18" aria-hidden="true">
            <path d="M8 1.5C8 5.25 10.75 9 13.5 9C10.75 9 8 12.75 8 16.5C8 12.75 5.25 9 2.5 9C5.25 9 8 5.25 8 1.5Z" />
            <path d="M14.5 11.5C14.5 12.75 15.4 14 16.3 14C15.4 14 14.5 15.25 14.5 16.5C14.5 15.25 13.6 14 12.7 14C13.6 14 14.5 12.75 14.5 11.5Z" />
          </svg>
        </div>
        <h2>今天想创作什么？</h2>
        <p>描述你的想法，我会和创作团队一起把它变成完整作品。</p>
        <div class="starter-grid">
          <button type="button"><span class="starter-icon starter-icon-topic"><BookOpen aria-hidden="true" /></span><b>策划选题</b><small>从一个想法梳理内容方向</small></button>
          <button type="button"><span class="starter-icon"><PenLine aria-hidden="true" /></span><b>创作文案</b><small>生成结构清晰的发布内容</small></button>
          <button type="button"><span class="starter-icon"><ImageIcon aria-hidden="true" /></span><b>视觉构思</b><small>探索画面风格与配图方案</small></button>
        </div>
      </div>
    </div>
    <Transition name="preview-modal">
      <div v-if="previewTask" class="preview-overlay" @click.self="previewTask = null">
        <div class="preview-frame">
          <PlatformPreviewShell
            :card="previewTask.artifacts || {}"
            :preview-ref="previewTask.artifacts?.meta?.preview_ref"
            :stylesheet-ref="previewTask.artifacts?.meta?.stylesheet_ref"
            @close="previewTask = null"
          />
        </div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.chat-window {
  flex: 1;
  min-height: 0;
  width: calc(100% + 2 * var(--ch-space-5));
  margin-inline: calc(-1 * var(--ch-space-5));
  overflow-y: auto;
  padding: 0 var(--ch-space-5) var(--ch-space-5);
  background: transparent;
  scrollbar-width: none;
}
.chat-window::-webkit-scrollbar { display: none; }

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
  width: 56px;
  height: 56px;
  margin-bottom: 24px;
  display: grid;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--ch-accent) 10%, var(--ch-border));
  border-radius: 50%;
  background: var(--ch-accent-subtle);
  color: var(--ch-accent);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--ch-accent) 8%, transparent);
}
.empty-mark svg { width: 32px; height: 32px; fill: currentColor; stroke: none; }
.empty-hint h2 { margin: 0; color: var(--ch-text); font: 600 24px/1.3 var(--ch-font-sans); }
.empty-hint > p { max-width: 480px; margin: 0 0 24px; color: var(--ch-text-faint); font: 400 14px/1.6 var(--ch-font-sans); }
.starter-grid { width: min(100%, 704px); display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.starter-grid button { min-height: 152px; display: flex; flex-direction: column; align-items: flex-start; padding: 24px; border: 1px solid var(--ch-border); border-radius: 16px; background: var(--ch-surface); color: var(--ch-text); text-align: left; cursor: default; box-shadow: none; }
.starter-grid .starter-icon { display: inline-flex; margin-bottom: 24px; color: var(--ch-accent); }
.starter-grid .starter-icon svg { width: 24px; height: 24px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
.starter-grid .starter-icon-topic svg { width: 24px; height: 24px; }
.starter-grid b { margin-bottom: 8px; font: 600 16px/1.4 var(--ch-font-sans); }
.starter-grid small {
  align-self: stretch;
  min-width: 0;
  overflow: hidden;
  color: var(--ch-text-muted);
  font: 400 14px/1.5 var(--ch-font-sans);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chat-inner :deep(.hil-card),
.chat-inner :deep(.recovery-card),
.chat-inner :deep(.running),
.chat-inner :deep(.confirmed-card),
.chat-inner :deep(.artifact-wrap:not(.review)) {
  margin: 0 0 var(--ch-space-8);
}
.chat-inner :deep(.intent-confirm) {
  margin: 16px 0 0;
}

.hil-panel {
  width: 100%;
}

.recovery-panel {
  width: 100%;
}

.task-turn-head {
  display: flex;
  min-height: 32px;
  align-items: center;
  gap: var(--ch-space-2);
  margin-bottom: var(--ch-space-3);
}

.task-turn-head :deep(.agent-avatar) {
  box-shadow: var(--ch-shadow-bubble);
}

.task-turn-head > span {
  color: var(--ch-text);
  font: 500 16px/1 var(--ch-font-sans);
  letter-spacing: 0;
}

.preview-overlay { position: fixed; inset: 0; z-index: 80; display: flex; align-items: center; justify-content: center; padding: 24px; background: var(--ch-overlay); overflow: hidden; }
.preview-frame { position: relative; width: min(100%, 880px); height: min(680px, calc(100dvh - 40px)); overflow: hidden; background: var(--ch-surface); border-radius: var(--ch-radius-card); box-shadow: var(--ch-shadow-lg); }
.preview-modal-enter-active, .preview-modal-leave-active { transition: opacity .2s; }
.preview-modal-enter-from, .preview-modal-leave-to { opacity: 0; }
@media (max-width: 780px) {
  .chat-window { width: 100%; margin-inline: 0; padding: 24px 16px; }
  .empty-hint { min-height: 480px; padding: 48px 0; }
  .starter-grid { grid-template-columns: 1fr; }
  .starter-grid button { min-height: 96px; padding: 16px; }
  .starter-grid .starter-icon { margin-bottom: 8px; }
}
</style>
