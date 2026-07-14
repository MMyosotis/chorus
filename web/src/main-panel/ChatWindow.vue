<script setup>
import { ref, watch, nextTick, computed } from 'vue'
import MessageBubble from './MessageBubble.vue'
import HilCard from './HilCard.vue'
import PostCard from './PostCard.vue'
import RunningPanel from './RunningPanel.vue'
import RecoveryCard from './RecoveryCard.vue'
import IntentConfirmCard from './IntentConfirmCard.vue'
import ConvFold from './ConvFold.vue'

const props = defineProps({
  messages: { type: Array, required: true },
  streaming: { type: Boolean, default: false },
  sessionId: { type: String, default: '' },
  sessionUpdatedAt: { type: Number, default: null },
})

defineEmits(['hil-confirmed', 'hil-retried', 'hil-cancelled', 'intent-confirm', 'intent-revise'])

const container = ref(null)
// 用户是否贴在底部（贴底时才自动跟随新内容滚底）
const stickToBottom = ref(true)

function onScroll() {
  const el = container.value
  if (!el) return
  stickToBottom.value = el.scrollHeight - el.scrollTop - el.clientHeight < 80
}

function scrollToBottom() {
  const el = container.value
  if (!el) return
  el.scrollTop = el.scrollHeight
  stickToBottom.value = true
}

const datelineDate = computed(() => {
  const ts = props.sessionUpdatedAt
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const digits = ['〇', '一', '二', '三', '四', '五', '六', '七', '八', '九']
  const year = String(d.getFullYear()).split('').map((n) => digits[Number(n)]).join('')
  const month = d.getMonth() + 1
  const day = d.getDate()
  const cnMonth = month < 10 ? digits[month] : `十${month === 10 ? '' : digits[month - 10]}`
  const cnDay = day < 10 ? digits[day] : day < 20 ? `十${day === 10 ? '' : digits[day - 10]}` : `${digits[Math.floor(day / 10)]}十${day % 10 === 0 ? '' : digits[day % 10]}`
  return `${year} · ${cnMonth}月${cnDay}日`
})

const datelineTime = computed(() => {
  const ts = props.sessionUpdatedAt
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const hour = d.getHours()
  const minute = d.getMinutes()
  const period = hour < 6 ? '凌晨' : hour < 12 ? '上午' : hour < 14 ? '中午' : hour < 18 ? '午后' : '入夜'
  const h12 = hour % 12 === 0 ? 12 : hour % 12
  return `${period} ${h12}:${String(minute).padStart(2, '0')}`
})

// 确认意图后建图：以第一条含 create_plan 工具调用的助手消息为锚点，锚点及之前折叠成「与助手的讨论」。
// 锚点正在流式吐字时先正常显示；流式结束或历史拉回时即折叠，一旦折叠不再展开。
const anchorIdx = computed(() =>
  props.messages.findIndex(
    (m) =>
      m.role === 'assistant' &&
      (m.tools?.items || []).some((it) => it.name === 'create_plan')
  )
)

const anchorFolded = ref(false)

const foldGroup = computed(() => {
  const msgs = props.messages
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
  { flush: 'sync' }
)

watch(
  () =>
    props.messages.map((m) => {
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
    }),
  () => {
    if (!stickToBottom.value) return
    nextTick(() => {
      if (container.value) {
        container.value.scrollTop = container.value.scrollHeight
      }
    })
  },
  { deep: true }
)

// 切换会话：重置跟随态并滚到底
watch(
  () => props.sessionId,
  () => {
    stickToBottom.value = true
    anchorFolded.value = false
    nextTick(() => {
      if (container.value) container.value.scrollTop = container.value.scrollHeight
    })
  }
)
</script>

<template>
  <div ref="container" class="chat-window" @scroll="onScroll">
    <div class="chat-inner">
      <div v-if="datelineDate" class="letterhead">
        <div class="lh-date">{{ datelineDate }}</div>
        <div v-if="datelineTime" class="lh-sub">{{ datelineTime }} · 致 稿搭</div>
      </div>
      <ConvFold v-if="foldGroup.folded.length" :messages="foldGroup.folded" />
      <div v-if="foldGroup.folded.length" class="rule" aria-hidden="true"></div>
      <template v-for="(msg, idx) in foldGroup.rest" :key="msg.id || idx">
        <div
          v-if="msg.role === 'user' && !msg.kind"
          class="round-divider"
          aria-hidden="true"
        ></div>
        <HilCard
          v-if="msg.kind === 'hil'"
          :task="msg.task"
          :session-id="sessionId"
          @confirmed="$emit('hil-confirmed', $event)"
          @retried="$emit('hil-retried', $event)"
          @cancelled="$emit('hil-cancelled', $event)"
        />
        <PostCard v-else-if="msg.kind === 'postcard'" :task="msg.task" />
        <RunningPanel v-else-if="msg.kind === 'running'" :task="msg.task" />
        <RecoveryCard
          v-else-if="msg.kind === 'recovery'"
          :task="msg.task"
          :session-id="sessionId"
          @retried="$emit('hil-retried', $event)"
          @cancelled="$emit('hil-cancelled', $event)"
        />
        <IntentConfirmCard
          v-else-if="msg.kind === 'intent-confirm'"
          :state="msg.state"
          @confirm="$emit('intent-confirm')"
          @revise="$emit('intent-revise')"
        />
        <MessageBubble
          v-else
          :role="msg.role"
          :content="msg.content"
          :thinking="msg.thinking"
          :tools="msg.tools"
          :active="streaming && idx === foldGroup.rest.length - 1 && msg.role === 'assistant'"
        />
      </template>
      <div v-if="messages.length === 0" class="empty-hint">
        <p>发送消息开始对话</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.chat-window {
  flex: 1;
  overflow-y: auto;
  padding: 34px 16px 10px;
  background: transparent;
  scrollbar-gutter: stable both-edges;
}

.chat-inner {
  max-width: var(--ch-runtime-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
}

.round-divider {
  display: none;
}

.rule {
  border-top: 1px dashed var(--ch-border-2);
  margin: var(--ch-turn-gap, 24px) 0;
}

.letterhead {
  text-align: center;
  margin-bottom: 16px;
  font-family: var(--ch-serif);
}

.lh-date {
  font-size: 15px;
  font-weight: 500;
  color: var(--ch-primary-2);
  letter-spacing: 2px;
  line-height: 1.4;
}

.lh-sub {
  font-size: 12px;
  color: var(--ch-faint);
  letter-spacing: 1.5px;
  margin-top: 6px;
  font-feature-settings: "onum" 1;
  line-height: 1;
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 240px;
  color: var(--ch-faint);
  font-size: 16px;
  letter-spacing: 0.5px;
}

.chat-inner :deep(.hil-card) {
  margin: 4px 0;
}

.chat-inner :deep(.post-card),
.chat-inner :deep(.recovery-card),
.chat-inner :deep(.intent-confirm),
.chat-inner :deep(.running) {
  margin: 18px 0;
}
</style>
