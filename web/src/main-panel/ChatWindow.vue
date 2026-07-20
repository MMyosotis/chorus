<script setup>
import { ref, watch, nextTick, computed, onMounted, onUnmounted } from 'vue'
import MessageBubble from './MessageBubble.vue'
import HilCard from './HilCard.vue'
import ArtifactCard from './ArtifactCard.vue'
import PlatformPreviewShell from './PlatformPreviewShell.vue'
import RunningPanel from './RunningPanel.vue'
import RecoveryCard from './RecoveryCard.vue'
import ConvFold from './ConvFold.vue'
import ProofRegister from './ProofRegister.vue'

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

// 确认意图后建图：首张阶段卡前的最后一条普通对话为锚点，锚点及之前折叠成「与助手的前期讨论」，
// 阶段卡本身留在主流程显示。流式中无阶段卡不折叠，结束后即折叠且不再展开。
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

const anchorIdx = computed(() => {
  const stageIdx = displayMessages.value.findIndex((m) => STAGE_KINDS.has(m.kind))
  return stageIdx > 0 ? stageIdx - 1 : -1
})

const anchorFolded = ref(false)
const switchingSession = ref(false)
const STAGE_KINDS = new Set(['running', 'hil', 'recovery', 'postcard', 'proof-register'])
const latestStageKey = computed(() => {
  const message = [...props.messages].reverse().find((item) => STAGE_KINDS.has(item.kind))
  return message ? messageKey(message, 0) : ''
})

onMounted(() => window.addEventListener('scroll', onScroll, { passive: true }))
onUnmounted(() => window.removeEventListener('scroll', onScroll))

function scrollToLatestStage(el, behavior = 'auto') {
  const entries = Array.from(el.querySelectorAll('.flow-entry'))
  const target = entries.reverse().find((entry) => {
    const divider = entry.querySelector(':scope > .stage-divider')
    return !!divider
  })
  if (!target) return false
  if (usesPageScroll(el)) {
    const targetBox = target.getBoundingClientRect()
    window.scrollTo({ top: Math.max(0, window.scrollY + targetBox.top - 26), behavior })
    return true
  }
  const containerBox = el.getBoundingClientRect()
  const targetBox = target.getBoundingClientRect()
  const top = Math.max(0, el.scrollTop + targetBox.top - containerBox.top - 4)
  el.scrollTo({ top, behavior })
  return true
}

const foldGroup = computed(() => {
  const msgs = displayMessages.value
  const idx = anchorIdx.value
  if (idx <= 0) return { folded: [], rest: msgs }
  if (anchorFolded.value) return { folded: msgs.slice(0, idx + 1), rest: msgs.slice(idx + 1) }
  return { folded: msgs.slice(0, idx), rest: msgs.slice(idx) }
})

// 锚点存在且非流式即折叠：同步触发，流式翻转当下就收，避开重拉消息异步替换的时序；只置真保证粘性
watch(
  () => anchorIdx.value > 0 && !props.streaming,
  (shouldFold) => {
    if (shouldFold) anchorFolded.value = true
  },
  { flush: 'sync', immediate: true }
)

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

// 切换会话：有阶段成品时落在阶段页首，纯对话才落到最新消息。
watch(
  () => props.sessionId,
  () => {
    switchingSession.value = true
    anchorFolded.value = anchorIdx.value > 0 && !props.streaming
    nextTick(() => {
      const el = container.value
      if (el) {
        if (latestStageKey.value) scrollToLatestStage(el)
        else scrollToBottom()
      }
      requestAnimationFrame(() => {
        switchingSession.value = false
      })
    })
  }
)
</script>

<template>
  <div ref="container" class="chat-window" @scroll="onScroll">
    <slot name="scroll-header"></slot>
    <div class="chat-inner">
      <div v-if="!foldGroup.folded.length" class="component-divider">会话 · CORRESPONDENCE</div>
      <Transition name="archive-fold" :css="!switchingSession">
        <div v-if="foldGroup.folded.length" class="archive-block">
          <div class="component-divider">会话 · CORRESPONDENCE</div>
          <ConvFold :messages="foldGroup.folded" :intent-state="intentState" />
        </div>
      </Transition>
      <TransitionGroup name="flow-stage" tag="div" class="flow-list" :css="!switchingSession">
        <div v-for="(msg, idx) in foldGroup.rest" :key="messageKey(msg, idx)" class="flow-entry">
          <div
            v-if="msg.role === 'user' && !msg.kind"
            class="round-divider"
            aria-hidden="true"
          ></div>
          <div v-if="msg.kind === 'running'" class="component-divider stage-divider">执行进度 · PRODUCTION</div>
          <div v-else-if="msg.kind === 'hil'" class="component-divider stage-divider">校样确认 · PROOF</div>
          <div v-else-if="msg.kind === 'recovery'" class="component-divider stage-divider">配图 · 异常恢复 / RECOVERY</div>
          <div v-else-if="msg.kind === 'postcard'" class="component-divider stage-divider">成品 · 最终定稿 / FINAL</div>
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
          <ProofRegister v-else-if="msg.kind === 'proof-register'" :tasks="msg.tasks" />
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
            :active="streaming && idx === foldGroup.rest.length - 1 && msg.role === 'assistant'"
            @intent-confirm="$emit('intent-confirm')"
            @intent-revise="$emit('intent-revise')"
          />
        </div>
      </TransitionGroup>
      <div v-if="messages.length === 0" class="empty-hint">
        <p>发送消息开始对话</p>
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
  padding: 20px var(--ch-paper-pad) 112px;
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
.archive-block { min-width: 0; }
.archive-fold-enter-active { transition: opacity .26s cubic-bezier(.2,.72,.25,1), transform .26s cubic-bezier(.2,.72,.25,1); }
.archive-fold-leave-active { transition: opacity .16s ease-in, transform .16s ease-in; }
.archive-fold-enter-from { opacity: 0; transform: translateY(8px); }
.archive-fold-leave-to { opacity: 0; transform: translateY(-5px); }

.component-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 40px 0 20px;
  color: var(--ch-warm);
  font: 600 var(--ch-chat-label-size)/1 var(--ch-serif);
  letter-spacing: .08em;
}
.component-divider::before {
  content: "";
  width: 7px;
  height: 7px;
  border: 1.5px solid rgba(141, 51, 37, .82);
  transform: rotate(45deg);
}
.stage-divider { margin: 40px 0 20px; }

@media (min-width: 781px) {
  .component-divider,
  .stage-divider { margin: 40px 0 13px; }
}

.round-divider {
  display: none;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 240px;
  color: var(--ch-faint);
  font-size: var(--t-title);
  letter-spacing: 0.5px;
}

.chat-inner :deep(.hil-card) {
  margin: 36px 0 16px;
}

.chat-inner :deep(.post-card),
.chat-inner :deep(.recovery-card),
.chat-inner :deep(.running) {
  margin: 36px 0 16px;
}
.chat-inner :deep(.intent-confirm) {
  margin: 18px 0 0;
}

.preview-overlay { position: fixed; inset: 0; z-index: 80; display: flex; align-items: flex-start; justify-content: center; padding: 40px 20px; background: rgba(27, 25, 22, .5); overflow-y: auto; }
.preview-frame { position: relative; width: min(100%, 880px); background: var(--ch-paper, #fffdf8); padding: 28px 24px 24px; box-shadow: 0 20px 60px rgba(0, 0, 0, .3); }
.preview-close { position: absolute; top: 6px; right: 6px; width: 32px; height: 32px; border: 0; background: transparent; color: var(--ch-muted); font-size: 18px; line-height: 1; cursor: pointer; }
.preview-close:hover { color: var(--ch-text); }
.preview-modal-enter-active, .preview-modal-leave-active { transition: opacity .2s; }
.preview-modal-enter-from, .preview-modal-leave-to { opacity: 0; }
.flow-entry:has(> .stage-divider) :deep(.hil-card),
.flow-entry:has(> .stage-divider) :deep(.post-card),
.flow-entry:has(> .stage-divider) :deep(.recovery-card),
.flow-entry:has(> .stage-divider) :deep(.running) { margin: 0 0 16px; }

@media (max-width: 780px) {
  .chat-window { padding-inline: 28px; }
}
</style>
