<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, defineAsyncComponent } from 'vue'
import ChatWindow from './main-panel/ChatWindow.vue'
import InputBar from './main-panel/InputBar.vue'
import ManuscriptHeader from './main-panel/ManuscriptHeader.vue'
import SessionSidebar from './SessionSidebar.vue'
import {
  listSessions,
  createSession,
  deleteSession,
  renameSession,
  fetchMessages,
  streamChat,
  getIntentState,
  confirmIntent,
  reopenIntent,
  resumeSession,
} from './api.js'
import { useTraceStore } from './composables/useTraceStore.js'
import { useTaskPolling } from './composables/useTaskPolling.js'
import { mergeAssistantHistory } from './composables/messageHistory.js'
import { planTaskCards, planIntentCard } from './composables/taskCardProjection.js'
import TeamPanel from './team-panel/TeamPanel.vue'
import { ROLE_FULL, stepOf } from './team-panel/roleMeta.js'

const uiReviewMode = import.meta.env.DEV && new URLSearchParams(window.location.search).has('ui-review')
const FlowReviewHarness = uiReviewMode ? defineAsyncComponent(() => import('./dev/FlowReviewHarness.vue')) : null

const traceStore = useTraceStore()
const taskPolling = useTaskPolling()

const chatWindowRef = ref(null)
const sessions = ref([])
const messagesBySession = reactive({})
const streamingBySession = reactive({})
const intentStateBySession = reactive({})
const activeId = ref(null)
const inputBarRef = ref(null)
const leftRailOpen = ref(false)
const rightRailOpen = ref(false)

const focusedTaskId = ref(null)

function onTaskFocus(taskId) {
  focusedTaskId.value = taskId
}

const messages = computed(() => messagesBySession[activeId.value] || [])
const streaming = computed(() => !!streamingBySession[activeId.value])
const activeGraph = computed(() => taskPolling.getGraph(activeId.value))
const hasActiveTask = computed(() => !!activeGraph.value?.active)
const activeCompleted = computed(() => (activeGraph.value?.tasks || []).some((task) => task.agent_type === 'finalize' && task.status === 'finished'))
const activeIntentState = computed(() => intentStateBySession[activeId.value] || null)
const awaitingConfirm = computed(() => activeIntentState.value?.intent_status === 'ready_to_confirm')
const activeTitle = computed(() => {
  const c = sessions.value.find((x) => x.id === activeId.value)
  return c ? c.title : ''
})
const activeSessionUpdatedAt = computed(() => {
  const c = sessions.value.find((x) => x.id === activeId.value)
  return c ? c.updated_at : null
})
const paperDate = computed(() => {
  const date = new Date((activeSessionUpdatedAt.value || Date.now() / 1000) * 1000)
  const months = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
  return {
    short: `${months[date.getMonth()]} ${String(date.getDate()).padStart(2, '0')}`,
    full: `${date.getFullYear()} · ${months[date.getMonth()]} ${String(date.getDate()).padStart(2, '0')}`,
  }
})
const currentTask = computed(() => (activeGraph.value?.tasks || []).find((task) => ['running', 'awaiting_confirm', 'failed'].includes(task.status)) || null)
const stageKicker = computed(() => {
  if (awaitingConfirm.value) return 'STORY COMMISSION'
  const task = currentTask.value
  if (task) {
    if (task.status === 'failed') return `${ROLE_FULL[task.agent_type] || task.agent_type} · RECOVERY`
    return `${ROLE_FULL[task.agent_type] || task.agent_type} · ${task.status === 'awaiting_confirm' ? 'PROOF' : 'WORKING'}`
  }
  const completedFinal = (activeGraph.value?.tasks || []).find((task) => task.agent_type === 'finalize' && task.status === 'finished')
  return completedFinal ? 'FINAL COPY' : 'CONVERSATION'
})
const paperPage = computed(() => {
  if (currentTask.value) return String(stepOf(currentTask.value.agent_type)).padStart(2, '0')
  const completedFinal = (activeGraph.value?.tasks || []).some((task) => task.agent_type === 'finalize' && task.status === 'finished')
  return String(completedFinal ? stepOf('finalize') : 1).padStart(2, '0')
})
const headlineDeck = computed(() => activeIntentState.value?.goal || '一份正在编辑、校样与签认的创作稿件')

function makeEmptyAssistant() {
  return {
    role: 'assistant',
    content: '',
    thinking: { state: 'idle' },
    tools: { state: 'idle', items: [] },
    created_at: Date.now() / 1000,
  }
}

async function loadMessages(id) {
  if (messagesBySession[id]) {
    traceStore.loadFromServer(id)
    return true
  }
  try {
    const raw = await fetchMessages(id)
    messagesBySession[id] = mergeAssistantHistory(raw)
    traceStore.loadFromServer(id)
    return true
  } catch (e) {
    if (e.status === 404) {
      // 该会话已被后端清理
      sessions.value = sessions.value.filter((c) => c.id !== id)
      delete messagesBySession[id]
      delete streamingBySession[id]
      if (activeId.value === id) {
        if (sessions.value.length > 0) {
          activeId.value = sessions.value[0].id
          await loadMessages(activeId.value)
        } else {
          await onCreate()
        }
        alert('该会话已过期，已自动切换')
      }
      return false
    } else {
      messagesBySession[id] = []
      return true
    }
  }
}

async function loadIntentState(id) {
  try {
    intentStateBySession[id] = await getIntentState(id)
  } catch {
    intentStateBySession[id] = null
  }
}

let sessionSelectionToken = 0

function pinLeavingPaper(el) {
  if (
    !window.matchMedia('(min-width: 781px)').matches ||
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ) return
  const rect = el.getBoundingClientRect()
  Object.assign(el.style, {
    position: 'fixed',
    top: `${rect.top}px`,
    left: `${rect.left}px`,
    width: `${rect.width}px`,
    margin: '0',
  })
}

async function commitSessionSwitch(id, selectionToken) {
  if (selectionToken !== sessionSelectionToken) return
  activeId.value = id
  focusedTaskId.value = null
}

async function selectSession(id) {
  if (!id || id === activeId.value) return
  const selectionToken = ++sessionSelectionToken
  leftRailOpen.value = false
  const [messagesReady] = await Promise.all([loadMessages(id), loadIntentState(id)])
  if (selectionToken !== sessionSelectionToken) return
  if (!messagesReady) {
    if (sessions.value.length > 0) await selectSession(sessions.value[0].id)
    else await onCreate()
    alert('该会话已过期，已自动切换')
    return
  }
  // 先恢复目标会话的任务图，再一次性切换稿纸，避免阶段卡延迟注入造成二次定位
  await taskPolling.start(id)
  if (selectionToken !== sessionSelectionToken) return
  injectTaskCards(id)
  injectIntentCard(id)
  await commitSessionSwitch(id, selectionToken)
}

async function forceReloadMessages(id) {
  try {
    const raw = await fetchMessages(id)
    messagesBySession[id] = mergeAssistantHistory(raw)
    injectTaskCards(id)
    injectIntentCard(id)
  } catch {
    // 轮询期间忽略
  }
}

const REMOVABLE_KINDS = new Set(['hil', 'postcard', 'recovery', 'proof-register'])
const RUNNING_KIND = 'running'

function injectTaskCards(id) {
  const list = messagesBySession[id]
  if (!list) return
  const plan = planTaskCards(taskPolling.getGraph(id))
  for (let i = list.length - 1; i >= 0; i--) {
    if (REMOVABLE_KINDS.has(list[i].kind)) list.splice(i, 1)
  }
  // 运行卡原址刷新进度，避免轮询每 tick 重建闪烁
  const runningCard = plan.find((c) => c.kind === RUNNING_KIND) || null
  const runningIdx = list.findIndex((m) => m.kind === RUNNING_KIND)
  if (runningCard) {
    if (runningIdx >= 0) list[runningIdx].task = runningCard.task
    else list.push(runningCard)
  } else if (runningIdx >= 0) {
    list.splice(runningIdx, 1)
  }
  for (const card of plan) {
    if (card.kind === RUNNING_KIND) continue
    if (card.kind === 'proof-register') {
      const idx = list.findIndex((m) => m.kind === RUNNING_KIND)
      list.splice(idx >= 0 ? idx : list.length, 0, card)
    } else {
      list.push(card)
    }
  }
}

function injectIntentCard(id) {
  const list = messagesBySession[id]
  if (!list) return
  for (let i = list.length - 1; i >= 0; i--) {
    if (list[i].kind === 'intent-confirm') list.splice(i, 1)
  }
  const card = planIntentCard(intentStateBySession[id])
  if (card) list.push(card)
}

watch(activeIntentState, () => {
  if (activeId.value) injectIntentCard(activeId.value)
})

taskPolling.configure({
  isStreaming: (sid) => !!streamingBySession[sid],
  reloadMessages: forceReloadMessages,
  onPipelineFinished: (sid) => {
    if (streamingBySession[sid]) return
    runAssistantStream(sid, (onEvent) => resumeSession(sid, onEvent))
  },
})

function onHilConfirmed(taskId) {
  const sid = activeId.value
  if (!sid) return
  forceReloadMessages(sid)
}
function onHilRetried(taskId) {
  const sid = activeId.value
  if (!sid) return
  taskPolling.start(sid) // 重跑后重新轮询跟踪进度
}
function onHilCancelled(sid) {
  taskPolling.stop()
  forceReloadMessages(sid)
}

async function onCreate() {
  try {
    const meta = await createSession()
    sessions.value.unshift(meta)
    messagesBySession[meta.id] = []
    intentStateBySession[meta.id] = null
    activeId.value = meta.id
    loadIntentState(meta.id)
  } catch (e) {
    alert(`新建失败: ${e.message}`)
  }
}

async function onDelete(id) {
  try {
    await deleteSession(id)
  } catch (e) {
    alert(`删除失败: ${e.message}`)
    return
  }
  const wasActive = activeId.value === id
  sessions.value = sessions.value.filter((c) => c.id !== id)
  delete messagesBySession[id]
  delete streamingBySession[id]
  delete intentStateBySession[id]
  if (wasActive) {
    if (sessions.value.length > 0) {
      activeId.value = sessions.value[0].id
      await Promise.all([loadMessages(activeId.value), loadIntentState(activeId.value)])
    } else {
      await onCreate()
    }
  }
}

async function onRename({ id, title }) {
  try {
    const meta = await renameSession(id, title)
    const idx = sessions.value.findIndex((c) => c.id === id)
    if (idx >= 0) sessions.value[idx] = { ...sessions.value[idx], ...meta }
  } catch (e) {
    alert(`重命名失败: ${e.message}`)
  }
}

function bumpSession(id) {
  const idx = sessions.value.findIndex((c) => c.id === id)
  if (idx > 0) {
    const [it] = sessions.value.splice(idx, 1)
    it.updated_at = Date.now() / 1000
    sessions.value.unshift(it)
  } else if (idx === 0) {
    sessions.value[0].updated_at = Date.now() / 1000
  }
}

function createStreamHandler(sessionId) {
  const list = messagesBySession[sessionId] || (messagesBySession[sessionId] = [])

  let assistantIdx = -1
  const cur = () => (assistantIdx >= 0 ? list[assistantIdx] : null)

  // 打字机队列：token 按字入队，rAF 每帧逐字追加，避免三四个字一起蹦出
  const charQueue = []
  let typingRaf = null
  // 同回合后续轮次正文前的空行分隔，待首个 token 落地再吐，避免提前空行
  let pendingRoundSep = false

  function drainQueue() {
    typingRaf = null
    const c = cur()
    if (!c || charQueue.length === 0) return
    // 追赶步长：堆积越多每帧出字越多，纯逐字时每帧 1 字
    const step = Math.max(1, Math.ceil(charQueue.length / 6))
    c.content += charQueue.splice(0, step).join('')
    if (charQueue.length > 0) scheduleTyping()
  }
  function scheduleTyping() {
    if (typingRaf) return
    typingRaf = requestAnimationFrame(drainQueue)
  }
  function flushTyping() {
    if (typingRaf) {
      cancelAnimationFrame(typingRaf)
      typingRaf = null
    }
    const c = cur()
    if (c && charQueue.length > 0) {
      c.content += charQueue.splice(0).join('')
    }
  }

  function startNewAssistant() {
    list.push(makeEmptyAssistant())
    assistantIdx = list.length - 1
  }
  function ensureAssistant() {
    if (!cur()) startNewAssistant()
    return cur()
  }
  function finalizeCurrent() {
    // 收尾前把队列剩余字一次性吐出，避免最后几个字丢失或拖到流结束
    flushTyping()
    const c = cur()
    if (!c) return
    // 状态条仅在进行时显示，结束即消失
    if (c.thinking.state === 'running') c.thinking.state = 'idle'
    if (c.tools.state === 'running') c.tools.state = 'idle'
  }

  // 尾部无正文气泡：仅流式过程态残留，直接丢弃
  function dropTrailingEmptyBubble() {
    if (list.length < 2) return
    const last = list[list.length - 1]
    if (last.role !== 'assistant' || last.kind) return
    if (last.content && last.content.trim()) return
    list.splice(list.length - 1, 1)
    assistantIdx = -1
  }

  const onEvent = (payload) => {
    // trace 事件直接入 store，不走气泡逻辑
    if (payload.type === 'trace') {
      traceStore.addTrace(sessionId, payload)
      return
    }
    if (payload.type === 'intent_state') {
      intentStateBySession[sessionId] = payload.state
      return
    }

    if (payload.type === 'message_start') {
      finalizeCurrent()
      const c = cur()
      // 同回合复用当前气泡：纯工具轮不新建，工具挂到本回合气泡上
      if (!c) startNewAssistant()
      else if (c.content) pendingRoundSep = true
    } else if (payload.type === 'reasoning') {
      const c = ensureAssistant()
      if (c.thinking.state !== 'running') c.thinking.state = 'running'
    } else if (payload.type === 'reasoning_done') {
      const c = cur()
      if (!c) return
      // 思考段结束不翻转状态：酝酿中持续到正文出现，避免回跳铺纸中
    } else if (payload.type === 'token') {
      ensureAssistant()
      if (pendingRoundSep) {
        charQueue.push('\n\n')
        pendingRoundSep = false
      }
      // 按 Unicode code point 拆字，避免拆坏中文/emoji 代理对
      charQueue.push(...Array.from(payload.content || ''))
      scheduleTyping()
    } else if (payload.type === 'tool_call') {
      const c = ensureAssistant()
      const tools = c.tools
      tools.state = 'running'
      tools.items.push({
        id: payload.id,
        name: payload.name,
        arguments: payload.arguments || {},
        duration_ms: null,
        content: '',
        display: payload.display || payload.name,
        running_label: payload.running_label || null,
      })
    } else if (payload.type === 'tool_result') {
      const c = cur()
      if (!c) return
      const tools = c.tools
      const item =
        tools.items.find((it) => it.id === payload.tool_call_id) ||
        tools.items.find((it) => it.name === payload.name && it.duration_ms === null)
      if (item) {
        item.duration_ms = payload.duration_ms
        item.content = payload.content
      }
      // 全部工具已落定则退出工具态
      if (tools.state === 'running' && !tools.items.some((it) => it.duration_ms == null)) {
        tools.state = 'idle'
      }
    } else if (payload.type === 'title_update') {
      const idx = sessions.value.findIndex((c) => c.id === payload.id)
      if (idx >= 0) {
        sessions.value[idx] = {
          ...sessions.value[idx],
          title: payload.title,
        }
      }
    } else if (payload.type === 'done') {
      finalizeCurrent()
      dropTrailingEmptyBubble()
      streamingBySession[sessionId] = false
      // 重拉取回非流式落库的气泡并续轮询
      forceReloadMessages(sessionId).finally(() => taskPolling.start(sessionId))
    } else if (payload.type === 'busy') {
      // 活跃任务准入拒绝的瞬时信号：不解禁输入框、不注入气泡，进度由任务图反映
      streamingBySession[sessionId] = false
    } else if (payload.type === 'archived') {
      // 定稿存档拒收：停流式、不建气泡，输入框由定稿态锁死
      streamingBySession[sessionId] = false
    } else if (payload.type === 'error') {
      // 错误覆盖正文前丢弃队列、停掉打字机，避免残帧把旧字符写回
      charQueue.length = 0
      if (typingRaf) {
        cancelAnimationFrame(typingRaf)
        typingRaf = null
      }
      ensureAssistant().content = `[错误] ${payload.content}`
      streamingBySession[sessionId] = false
    }
  }

  return { onEvent, finalizeCurrent, dropTrailingEmptyBubble }
}

async function runAssistantStream(sessionId, streamFactory) {
  streamingBySession[sessionId] = true
  const handler = createStreamHandler(sessionId)
  const { done } = streamFactory(handler.onEvent)
  await done
  handler.finalizeCurrent()
  handler.dropTrailingEmptyBubble()
  streamingBySession[sessionId] = false
  bumpSession(sessionId)
}

async function onSend(text) {
  const sessionId = activeId.value
  if (!sessionId) return
  if (!text.trim() || streamingBySession[sessionId] || hasActiveTask.value || activeCompleted.value) return

  const list = messagesBySession[sessionId] || (messagesBySession[sessionId] = [])
  list.push({ role: 'user', content: text, created_at: Date.now() / 1000 })
  await nextTick()
  chatWindowRef.value?.followBottom('smooth')
  await runAssistantStream(sessionId, (onEvent) => streamChat(sessionId, text, onEvent))
}

async function onIntentConfirm() {
  const sessionId = activeId.value
  if (!sessionId || streamingBySession[sessionId] || hasActiveTask.value) return
  await runAssistantStream(sessionId, (onEvent) => confirmIntent(sessionId, onEvent))
}

async function onIntentRevise() {
  const sessionId = activeId.value
  if (!sessionId || streamingBySession[sessionId] || hasActiveTask.value) return
  await runAssistantStream(sessionId, (onEvent) => reopenIntent(sessionId, onEvent))
}

onMounted(async () => {
  if (uiReviewMode) return
  try {
    const list = await listSessions()
    sessions.value = list
  } catch {
    sessions.value = []
  }
  if (sessions.value.length === 0) {
    await onCreate()
  } else {
    // 复用会话切换完整路径，让刷新后的任务图靠轮询恢复
    await selectSession(sessions.value[0].id)
  }
})
</script>

<template>
  <FlowReviewHarness v-if="uiReviewMode" />
  <template v-else>
  <div class="app-shell">
    <SessionSidebar
      :class="{ 'is-open': leftRailOpen }"
      :sessions="sessions"
      :active-id="activeId"
      :streaming-map="streamingBySession"
      :active-working="hasActiveTask || awaitingConfirm || streaming"
      :active-completed="activeCompleted"
      @select="selectSession"
      @create="onCreate"
      @delete="onDelete"
      @rename="onRename"
    />
    <main class="main-panel">
      <nav class="mobile-bar" aria-label="移动端栏目导航">
        <button type="button" @click="leftRailOpen = true">稿件</button>
        <strong>{{ activeTitle || '未命名稿件' }}</strong>
        <button type="button" @click="rightRailOpen = true">题旨与目录</button>
      </nav>
      <div class="paper-stage">
        <Transition name="paper-swap" @before-leave="pinLeavingPaper">
          <article :key="activeId || 'empty'" class="paper-shell manuscript-paper">
            <ChatWindow
              ref="chatWindowRef"
              :messages="messages"
              :streaming="streaming"
              :session-id="activeId || ''"
              :session-updated-at="activeSessionUpdatedAt"
              :intent-state="activeIntentState"
              @hil-confirmed="onHilConfirmed"
              @hil-retried="onHilRetried"
              @hil-cancelled="onHilCancelled"
              @intent-confirm="onIntentConfirm"
              @intent-revise="onIntentRevise"
            >
              <template #scroll-header>
                <ManuscriptHeader :date="paperDate.full" :page="paperPage" :kicker="stageKicker" :title="activeTitle || '未命名稿件'" :deck="headlineDeck" />
              </template>
            </ChatWindow>
          </article>
        </Transition>
        <InputBar ref="inputBarRef" :streaming="streaming" :has-active-task="hasActiveTask" :awaiting-confirm="awaitingConfirm" :archived="activeCompleted" @send="onSend" />
      </div>
    </main>
    <TeamPanel
      :class="{ 'is-open': rightRailOpen }"
      :graph="activeGraph"
      :focused-task-id="focusedTaskId"
      :intent-state="activeIntentState"
      @focus="onTaskFocus"
    />
    <button v-if="leftRailOpen || rightRailOpen" class="rail-scrim" type="button" aria-label="关闭侧栏" @click="leftRailOpen = false; rightRailOpen = false"></button>
  </div>
  </template>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100dvh;
  width: 100%;
  overflow: visible;
  align-items: flex-start;
  background: var(--ch-canvas);
  padding: 0;
  gap: 0;
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: visible;
  min-height: 100dvh;
  padding: 26px;
  background: var(--ch-canvas);
  border: none;
  box-shadow: none;
}

.mobile-bar { display: none; }
.rail-scrim { display: none; }

:global(body:has(.app-shell)) { overflow-y: auto; }

.paper-stage {
  position: relative;
  width: min(100%, 880px);
  margin: 0 auto;
}

.paper-shell {
  position: relative;
  z-index: 1;
  width: 100%;
  margin: 0;
}

.paper-shell :deep(.chat-window) {
  flex: 0 0 auto;
  overflow: visible;
  scrollbar-gutter: auto;
}

@media (min-width: 781px) {
  .paper-swap-enter-active,
  .paper-swap-leave-active {
    backface-visibility: hidden;
  }

  .paper-swap-enter-active {
    z-index: 2;
    will-change: opacity;
    transition: opacity 280ms cubic-bezier(.2, .72, .25, 1);
  }

  .paper-swap-leave-active {
    z-index: 1;
    will-change: opacity;
    transition: opacity 180ms ease-in;
    pointer-events: none;
  }

  .paper-swap-enter-from {
    opacity: 0;
  }

  .paper-swap-leave-to {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .paper-swap-enter-active,
  .paper-swap-leave-active {
    transition: none;
  }
}

@media (min-width: 1181px) {
  .app-shell > :deep(.sidebar),
  .app-shell > :deep(.team-panel) {
    position: sticky;
    top: 0;
    height: 100dvh;
  }

  .paper-stage :deep(.input-bar) {
    position: fixed;
    left: 50%;
    width: min(calc(100vw - 2 * var(--ch-rail) - 104px), 828px);
  }
}

@media (min-width: 781px) and (max-width: 1180px) {
  .app-shell > :deep(.sidebar) {
    position: sticky;
    top: 0;
    height: 100dvh;
  }

  .paper-stage :deep(.input-bar) {
    position: fixed;
    left: calc((100vw + 224px) / 2);
    width: min(calc(100vw - 328px), 828px);
  }
}

@media (max-width: 780px) {
  .main-panel { padding: 0; }
  .paper-shell { box-shadow: none; }
  .paper-shell::before { left: 14px; }
}

@media (max-width: 1180px) {
  :deep(.team-panel) { display: none; }
}

@media (max-width: 780px) {
  :deep(.team-panel) {
    display: flex;
    position: fixed;
    z-index: 60;
    top: 0;
    right: 0;
    bottom: 0;
    width: min(300px, 90vw);
    transform: translateX(104%);
    transition: transform .24s ease-out;
    box-shadow: -14px 0 38px rgba(27, 25, 22, .14);
  }
  :deep(.team-panel.is-open) { transform: translateX(0); }
  .mobile-bar {
    flex: 0 0 52px;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: 8px;
    padding: 0 12px;
    border-bottom: 1px solid var(--ch-border-2);
    background: rgba(232, 226, 215, .97);
  }
  .mobile-bar button { min-height: 38px; padding: 0 8px; border: 0; border-bottom: 1px solid transparent; background: transparent; color: var(--ch-warm); font: 600 11px/1 var(--ch-serif); cursor: pointer; }
  .mobile-bar button:hover { border-bottom-color: currentColor; }
  .mobile-bar strong { min-width: 0; overflow: hidden; font: 600 13px/1.3 var(--ch-serif); text-align: center; text-overflow: ellipsis; white-space: nowrap; }
  .paper-shell { height: calc(100% - 52px); }
  .rail-scrim { position: fixed; z-index: 55; inset: 0; display: block; min-height: 0; border: 0; background: rgba(27, 25, 22, .32); }
  :deep(.sidebar) { position: fixed; z-index: 60; top: 0; left: 0; bottom: 0; width: min(300px, 88vw); transform: translateX(-104%); transition: transform .24s ease-out; box-shadow: 14px 0 38px rgba(27, 25, 22, .14); }
  :deep(.sidebar.is-open) { transform: translateX(0); }
}
</style>
