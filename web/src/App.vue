<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, defineAsyncComponent } from 'vue'
import ChatWindow from './main-panel/ChatWindow.vue'
import InputBar from './main-panel/InputBar.vue'
import ManuscriptHeader from './main-panel/ManuscriptHeader.vue'
import SessionSidebar from './SessionSidebar.vue'
import NavDock from './NavDock.vue'
import {
  listSessions,
  createSession,
  deleteSession,
  renameSession,
  fetchMessages,
  streamChat,
  getIntentState,
  getIntentConfirmations,
  confirmIntent,
  reopenIntent,
  chooseOption,
  fetchOptionHistory,
} from './api.js'
import { useTraceStore } from './composables/useTraceStore.js'
import { useTaskPolling } from './composables/useTaskPolling.js'
import { mergeAssistantHistory } from './composables/messageHistory.js'
import { planTaskCards, planIntentCards, planOptionCards } from './composables/taskCardProjection.js'
import { replaceAnchoredCards } from './composables/anchoredCards.js'
import TeamPanel from './team-panel/TeamPanel.vue'
import { ROLE_FULL } from './team-panel/roleMeta.js'
import MemoryPanel from './main-panel/MemoryPanel.vue'

const uiReviewMode = import.meta.env.DEV && new URLSearchParams(window.location.search).has('ui-review')
const FlowReviewHarness = uiReviewMode ? defineAsyncComponent(() => import('./dev/FlowReviewHarness.vue')) : null

const traceStore = useTraceStore()
const taskPolling = useTaskPolling()

const chatWindowRef = ref(null)
const sessions = ref([])
const messagesBySession = reactive({})
const streamingBySession = reactive({})
const intentStateBySession = reactive({})
const intentConfirmationsBySession = reactive({})
const optionPromptsBySession = reactive({})
const activeId = ref(null)
const inputBarRef = ref(null)
const leftRailOpen = ref(true)
const rightRailOpen = ref(false)
const settingsOpen = ref(false)
const memoryOpen = ref(false)
const memoryEditorOpen = ref(false)
const activeMemory = ref(null)
const memoryRefreshKey = ref(0)
const consoleOpen = ref(false)

const focusedTaskId = ref(null)

function onTaskFocus(taskId) {
  focusedTaskId.value = taskId
}

function openSettings() {
  if (settingsOpen.value) {
    collapseSidebar()
    return
  }
  consoleOpen.value = false
  memoryOpen.value = false
  memoryEditorOpen.value = false
  activeMemory.value = null
  rightRailOpen.value = false
  settingsOpen.value = true
  leftRailOpen.value = true
}

function openMemory() {
  if (memoryOpen.value) {
    collapseSidebar()
    return
  }
  settingsOpen.value = false
  consoleOpen.value = false
  memoryOpen.value = true
  leftRailOpen.value = true
}

function openConsole() {
  if (consoleOpen.value) {
    collapseSidebar()
    return
  }
  settingsOpen.value = false
  memoryOpen.value = false
  memoryEditorOpen.value = false
  consoleOpen.value = true
  leftRailOpen.value = true
}

function editMemory(memory) {
  activeMemory.value = memory
  memoryEditorOpen.value = true
}

function createMemory() {
  activeMemory.value = null
  memoryEditorOpen.value = true
}

function closeMemoryEditor() {
  memoryEditorOpen.value = false
  activeMemory.value = null
}

function refreshMemories(memory) {
  activeMemory.value = memory || null
  memoryRefreshKey.value += 1
}

function toggleSidebar() {
  if (settingsOpen.value || memoryOpen.value || consoleOpen.value) {
    settingsOpen.value = false
    memoryOpen.value = false
    memoryEditorOpen.value = false
    consoleOpen.value = false
    activeMemory.value = null
    leftRailOpen.value = true
    return
  }
  if (leftRailOpen.value) {
    collapseSidebar()
  } else {
    leftRailOpen.value = true
  }
}

function collapseSidebar() {
  settingsOpen.value = false
  memoryOpen.value = false
  memoryEditorOpen.value = false
  consoleOpen.value = false
  activeMemory.value = null
  leftRailOpen.value = false
}

function onArtifactFocus(task) {
  chatWindowRef.value?.scrollToTask(task?.id)
}

const messages = computed(() => messagesBySession[activeId.value] || [])
const streaming = computed(() => !!streamingBySession[activeId.value])
const activeGraph = computed(() => taskPolling.getGraph(activeId.value))
const hasActiveTask = computed(() => !!activeGraph.value?.active)
const activeCompleted = computed(() => (activeGraph.value?.tasks || []).some((task) => task.agent_type === 'finalize' && task.status === 'finished'))
const activeIntentState = computed(() => intentStateBySession[activeId.value] || null)
const activeConfirmations = computed(() => intentConfirmationsBySession[activeId.value] || [])
const activeConfirmation = computed(() => activeConfirmations.value.find((confirmation) => confirmation.status === 'open') || null)
const activeOptionPrompt = computed(() =>
  (optionPromptsBySession[activeId.value] || []).find((prompt) => prompt.status === 'open') || null
)
const awaitingConfirm = computed(() => !!activeConfirmation.value)
const awaitingOption = computed(() => !!activeOptionPrompt.value)
const activeTitle = computed(() => {
  const c = sessions.value.find((x) => x.id === activeId.value)
  return c ? c.title : ''
})
const activeSessionUpdatedAt = computed(() => {
  const c = sessions.value.find((x) => x.id === activeId.value)
  return c ? c.updated_at : null
})
const currentTask = computed(() => (activeGraph.value?.tasks || []).find((task) => ['running', 'awaiting_confirm', 'failed'].includes(task.status)) || null)
const stageKicker = computed(() => {
  if (awaitingOption.value) return '等待选择'
  if (awaitingConfirm.value) return '等待确认'
  const task = currentTask.value
  if (task) {
    if (task.status === 'failed') return `${ROLE_FULL[task.agent_type] || task.agent_type} · 需要处理`
    return `${ROLE_FULL[task.agent_type] || task.agent_type} · ${task.status === 'awaiting_confirm' ? '等待确认' : '执行中'}`
  }
  const completedFinal = (activeGraph.value?.tasks || []).find((task) => task.agent_type === 'finalize' && task.status === 'finished')
  return completedFinal ? '已完成' : '自由对话'
})

function makeEmptyAssistant(id) {
  return {
    role: 'assistant',
    content: '',
    thinking: { state: 'idle' },
    tools: { state: 'idle', items: [] },
    created_at: Date.now() / 1000,
    id: id || null,
    messageIds: id ? [id] : [],
    suspended: false,
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
          activeId.value = null
          focusedTaskId.value = null
          taskPolling.stop()
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

async function loadOptionHistory(id) {
  try {
    optionPromptsBySession[id] = await fetchOptionHistory(id)
  } catch {
    optionPromptsBySession[id] = []
  }
}

async function loadIntentConfirmations(id) {
  try {
    intentConfirmationsBySession[id] = await getIntentConfirmations(id)
  } catch {
    intentConfirmationsBySession[id] = []
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
  // 窄屏侧栏为覆盖层，切换后收起以展示对话；桌面端则保持用户展开状态。
  if (window.matchMedia('(max-width: 780px)').matches) leftRailOpen.value = false
  const [messagesReady] = await Promise.all([loadMessages(id), loadIntentState(id), loadIntentConfirmations(id), loadOptionHistory(id)])
  if (selectionToken !== sessionSelectionToken) return
  if (!messagesReady) {
    if (sessions.value.length > 0) await selectSession(sessions.value[0].id)
    else {
      activeId.value = null
      focusedTaskId.value = null
      taskPolling.stop()
    }
    alert('该会话已过期，已自动切换')
    return
  }
  // 先恢复目标会话的任务图，再一次性切换稿纸，避免阶段卡延迟注入造成二次定位
  await taskPolling.start(id)
  if (selectionToken !== sessionSelectionToken) return
  injectTaskCards(id)
  injectIntentCard(id)
  injectOptionCard(id)
  await commitSessionSwitch(id, selectionToken)
}

async function forceReloadMessages(id) {
  try {
    const [raw, prompts, confirmations] = await Promise.all([fetchMessages(id), fetchOptionHistory(id), getIntentConfirmations(id)])
    messagesBySession[id] = mergeAssistantHistory(raw)
    optionPromptsBySession[id] = prompts
    intentConfirmationsBySession[id] = confirmations
    injectTaskCards(id)
    injectIntentCard(id)
    injectOptionCard(id)
  } catch {
    // 轮询期间忽略
  }
}

const TASK_CARD_KINDS = new Set(['hil', 'postcard', 'recovery', 'confirmed', 'running'])

function injectTaskCards(id) {
  const list = messagesBySession[id]
  if (!list) return
  const plan = planTaskCards(taskPolling.getGraph(id))
  // 运行卡复用旧实例只更新数据；单独插会抢到前序卡片之前。
  const existing = new Map(
    list.filter((message) => TASK_CARD_KINDS.has(message.kind)).map((message) => [message.id, message]),
  )
  replaceAnchoredCards(
    list,
    (message) => TASK_CARD_KINDS.has(message.kind),
    plan.map((card) => {
      const prior = existing.get(card.id)
      if (!prior || card.kind !== 'running') return card
      prior.task = card.task
      return prior
    }),
  )
}

function injectIntentCard(id) {
  const list = messagesBySession[id]
  if (!list) return
  replaceAnchoredCards(
    list,
    (message) => message.kind === 'intent-confirm',
    planIntentCards((intentConfirmationsBySession[id] || []).filter((confirmation) => confirmation.status === 'answered')),
  )
}

function injectOptionCard(id) {
  const list = messagesBySession[id]
  if (!list) return
  replaceAnchoredCards(
    list,
    (message) => message.kind === 'option',
    planOptionCards((optionPromptsBySession[id] || []).filter((prompt) => prompt.status === 'answered')),
  )
}

watch(() => intentConfirmationsBySession[activeId.value], () => {
  if (activeId.value) injectIntentCard(activeId.value)
}, { deep: true })

watch(() => optionPromptsBySession[activeId.value], () => {
  if (activeId.value) injectOptionCard(activeId.value)
}, { deep: true })

taskPolling.configure({
  isStreaming: (sid) => !!streamingBySession[sid],
  reloadMessages: forceReloadMessages,
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
    intentConfirmationsBySession[meta.id] = []
    optionPromptsBySession[meta.id] = []
    activeId.value = meta.id
    loadIntentState(meta.id)
    return meta.id
  } catch (e) {
    alert(`新建失败: ${e.message}`)
    return null
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
  delete intentConfirmationsBySession[id]
  delete optionPromptsBySession[id]
  if (wasActive) {
    if (sessions.value.length > 0) {
      activeId.value = sessions.value[0].id
      await Promise.all([loadMessages(activeId.value), loadIntentState(activeId.value), loadIntentConfirmations(activeId.value), loadOptionHistory(activeId.value)])
    } else {
      activeId.value = null
      focusedTaskId.value = null
      taskPolling.stop()
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

  function startNewAssistant(id) {
    list.push(makeEmptyAssistant(id))
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

  // 尾部无正文气泡：仅流式过程态残留才丢弃。挂起气泡（带工具/确认卡）保留作宿主
  function dropTrailingEmptyBubble() {
    if (list.length < 2) return
    const last = list[list.length - 1]
    if (last.role !== 'assistant' || last.kind) return
    if (last.content && last.content.trim()) return
    if (last.suspended || (last.tools && last.tools.items.length)) return
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
      if (payload.state?.intent_status === 'ready_to_confirm') {
        const confirmations = intentConfirmationsBySession[sessionId] || (intentConfirmationsBySession[sessionId] = [])
        const openIdx = confirmations.findIndex((confirmation) => confirmation.status === 'open')
        const confirmation = { ...payload.state, status: 'open' }
        if (openIdx >= 0) confirmations.splice(openIdx, 1, confirmation)
        else confirmations.push(confirmation)
      }
      return
    }
    if (payload.type === 'option_prompt') {
      const prompts = optionPromptsBySession[sessionId] || (optionPromptsBySession[sessionId] = [])
      const openIdx = prompts.findIndex((prompt) => prompt.status === 'open')
      const prompt = {
        prompt_id: payload.prompt_id,
        message_id: payload.message_id,
        questions: payload.questions,
        status: 'open',
      }
      if (openIdx >= 0) prompts.splice(openIdx, 1, prompt)
      else prompts.push(prompt)
      return
    }

    if (payload.type === 'message_start') {
      finalizeCurrent()
      // resume 续写挂起气泡：跳过尾部注入卡（确认卡/阶段卡），最近一条真实消息若为挂起助手气泡则复用
      let lastIdx = list.length - 1
      while (lastIdx >= 0 && list[lastIdx].kind) lastIdx--
      const last = list[lastIdx]
      if (last && last.role === 'assistant' && last.suspended) {
        assistantIdx = lastIdx
        last.suspended = false
        // 每轮请求一开始就展示同一条气泡内的过程提示；工具状态会在调用时覆盖它。
        last.thinking.state = 'running'
        pendingRoundSep = true
        return
      }
      const c = cur()
      // 同回合复用当前气泡：纯工具轮不新建，工具挂到本回合气泡上
      if (!c) {
        startNewAssistant(payload.id)
        cur().thinking.state = 'running'
      } else {
        c.thinking.state = 'running'
        if (c.content) pendingRoundSep = true
      }
    } else if (payload.type === 'suspend') {
      const c = cur()
      if (c) c.suspended = true
    } else if (payload.type === 'reasoning') {
      const c = ensureAssistant()
      if (c.thinking.state !== 'running') c.thinking.state = 'running'
    } else if (payload.type === 'reasoning_done') {
      const c = cur()
      if (!c) return
      // 思考段结束不翻转状态：酝酿中持续到正文出现，避免回跳铺纸中
    } else if (payload.type === 'token') {
      const c = ensureAssistant()
      // 正文持续输出本身就是最直接的进度反馈，避免与状态条重复。
      c.thinking.state = 'idle'
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

function onStarterPick(text) {
  inputBarRef.value?.prefill(text)
}

async function onSend(text) {
  if (!text.trim() || hasActiveTask.value || activeCompleted.value) return
  const sessionId = activeId.value || await onCreate()
  if (!sessionId || streamingBySession[sessionId]) return

  const list = messagesBySession[sessionId] || (messagesBySession[sessionId] = [])
  list.push({ role: 'user', content: text, created_at: Date.now() / 1000 })
  await nextTick()
  chatWindowRef.value?.followBottom('smooth')
  await runAssistantStream(sessionId, (onEvent) => streamChat(sessionId, text, onEvent))
}

async function onIntentConfirm() {
  const sessionId = activeId.value
  if (!sessionId || streamingBySession[sessionId] || hasActiveTask.value) return
  const confirmation = activeConfirmation.value
  if (confirmation) {
    confirmation.status = 'answered'
    confirmation.answer = { signal: 'confirm', label: '确认并开始创作' }
  }
  await runAssistantStream(sessionId, (onEvent) => confirmIntent(sessionId, onEvent))
}

async function onIntentRevise() {
  const sessionId = activeId.value
  if (!sessionId || streamingBySession[sessionId] || hasActiveTask.value) return
  const confirmation = activeConfirmation.value
  if (confirmation) {
    confirmation.status = 'answered'
    confirmation.answer = { signal: 'reopen', label: '继续调整' }
  }
  await runAssistantStream(sessionId, (onEvent) => reopenIntent(sessionId, onEvent))
}

async function onOptionChoose(payload) {
  const sessionId = activeId.value
  if (!sessionId || streamingBySession[sessionId] || hasActiveTask.value) return
  const prompt = activeOptionPrompt.value
  if (prompt) {
    prompt.status = 'answered'
    prompt.answers = payload.answers.map((submitted, index) => {
      const question = prompt.questions[index]
      const selected = question?.options.find((option) => option.signal === submitted.signal)
      return {
        signal: submitted.signal,
        label: selected?.label || '补充你的想法',
        ...(submitted.custom_text ? { custom_text: submitted.custom_text } : {}),
      }
    })
  }
  await runAssistantStream(sessionId, (onEvent) => chooseOption(sessionId, payload, onEvent))
}

onMounted(async () => {
  if (uiReviewMode) return
  try {
    const list = await listSessions()
    sessions.value = list
  } catch {
    sessions.value = []
  }
  if (sessions.value.length > 0) {
    // 复用会话切换完整路径，让刷新后的任务图靠轮询恢复
    await selectSession(sessions.value[0].id)
  }
})
</script>

<template>
  <FlowReviewHarness v-if="uiReviewMode" />
  <template v-else>
  <div class="app-shell" :class="{ 'sidebar-open': leftRailOpen, 'settings-open': settingsOpen, 'memory-open': memoryOpen, 'trace-open': consoleOpen }">
    <NavDock
      :sidebar-open="leftRailOpen"
      :settings-open="settingsOpen"
      :memory-open="memoryOpen"
      :console-open="consoleOpen"
      @toggle-sidebar="toggleSidebar"
      @open-settings="openSettings"
      @open-memory="openMemory"
      @open-console="openConsole"
    />
    <SessionSidebar
      :class="{ 'is-open': leftRailOpen }"
      :sessions="sessions"
      :active-id="activeId"
      :streaming-map="streamingBySession"
      :active-working="hasActiveTask || awaitingConfirm || awaitingOption || streaming"
      :active-completed="activeCompleted"
      :settings-open="settingsOpen"
      :memory-open="memoryOpen"
      :memory-refresh-key="memoryRefreshKey"
      :selected-memory-id="activeMemory?.id || null"
      :console-open="consoleOpen"
      :trace-store="traceStore"
      :task-graph="activeGraph"
      :expanded="leftRailOpen || settingsOpen || memoryOpen || consoleOpen"
      @select="selectSession"
      @create="onCreate"
      @delete="onDelete"
      @rename="onRename"
      @memory-edit="editMemory"
      @memory-create="createMemory"
      @collapse="collapseSidebar"
    />
    <div class="memory-editor-shell" :class="{ 'is-open': memoryEditorOpen }">
      <Transition name="memory-editor">
        <MemoryPanel
          v-if="memoryEditorOpen"
          :key="activeMemory?.id || 'new-memory'"
          :memory="activeMemory"
          @close="closeMemoryEditor"
          @saved="refreshMemories"
          @deleted="refreshMemories(null); closeMemoryEditor()"
        />
      </Transition>
    </div>
    <main class="main-panel">
      <nav class="mobile-bar" aria-label="移动端栏目导航">
        <button type="button" @click="leftRailOpen = true">会话</button>
        <strong>{{ activeTitle || '未命名会话' }}</strong>
        <button type="button" @click="rightRailOpen = true">团队</button>
      </nav>
      <div class="paper-stage">
        <Transition name="paper-swap" @before-leave="pinLeavingPaper">
          <article :key="activeId || 'empty'" class="paper-shell">
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
              @option-choose="onOptionChoose"
              @starter-pick="onStarterPick"
            >
              <template #scroll-header>
                <ManuscriptHeader :kicker="stageKicker" :title="activeTitle || '未命名稿件'" />
              </template>
            </ChatWindow>
          </article>
        </Transition>
        <InputBar
          ref="inputBarRef"
          :streaming="streaming"
          :has-active-task="hasActiveTask"
          :awaiting-confirm="awaitingConfirm"
          :awaiting-option="awaitingOption"
          :archived="activeCompleted"
          :intent-confirmation="activeConfirmation"
          :option-prompt="activeOptionPrompt"
          @send="onSend"
          @intent-confirm="onIntentConfirm"
          @intent-revise="onIntentRevise"
          @option-choose="onOptionChoose"
        />
      </div>
    </main>
    <TeamPanel
      v-if="!memoryEditorOpen"
      :class="{ 'is-open': rightRailOpen }"
      :graph="activeGraph"
      :chief-working="streaming"
      :focused-task-id="focusedTaskId"
      :intent-state="activeIntentState"
      @focus="onTaskFocus"
      @focus-task="onArtifactFocus"
    />
    <button v-if="leftRailOpen || rightRailOpen" class="rail-scrim" type="button" aria-label="关闭侧栏" @click="leftRailOpen = false; rightRailOpen = false"></button>
  </div>
  </template>
</template>

<style scoped>
.app-shell {
  --ch-sidebar-width: 0px;
  --ch-memory-editor-rail: var(--ch-session-rail);
  --ch-trace-rail: var(--ch-session-rail);
  --ch-sidebar-motion-duration: 320ms;
  --ch-sidebar-motion-ease: cubic-bezier(.2, .72, .25, 1);
  display: flex;
  min-height: 100dvh;
  width: 100%;
  overflow: clip;
  align-items: flex-start;
  background: var(--ch-canvas-gradient);
}

.app-shell.sidebar-open {
  --ch-sidebar-width: var(--ch-session-rail);
}

.app-shell.trace-open {
  --ch-sidebar-width: var(--ch-trace-rail);
}

.main-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  height: 100dvh;
  overflow: hidden;
  padding: 24px var(--ch-space-5);
}

.mobile-bar { display: none; }
.rail-scrim { display: none; }

:global(body:has(.app-shell)) { overflow: hidden; }

.paper-stage {
  position: relative;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  width: min(100%, var(--ch-main-column));
  margin: 0 auto;
}

.paper-shell {
  position: relative;
  z-index: 1;
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  overflow: visible;
}

@media (min-width: 781px) {
  .app-shell {
    --ch-memory-editor-rail: clamp(320px, 30vw, 400px);
    --ch-trace-rail: clamp(360px, 32vw, 460px);
  }

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
    position: absolute;
    inset: 0;
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

  .memory-editor-shell {
    position: sticky;
    top: 0;
    width: 0;
    height: 100dvh;
    flex: 0 0 0;
    overflow: clip;
    transition: width 360ms cubic-bezier(.16, .84, .26, 1),
      flex-basis 360ms cubic-bezier(.16, .84, .26, 1);
  }

  .memory-editor-shell :deep(.memory-panel) {
    position: absolute;
    inset: 0;
  }

  .memory-editor-shell.is-open {
    width: var(--ch-memory-editor-rail);
    flex-basis: var(--ch-memory-editor-rail);
  }

  .memory-editor-enter-active {
    will-change: opacity, transform;
    transition: opacity 220ms ease-out,
      transform 360ms cubic-bezier(.16, .84, .26, 1);
  }

  .memory-editor-leave-active {
    will-change: opacity, transform;
    transition: opacity 120ms ease-out,
      transform 300ms cubic-bezier(.22, .8, .25, 1);
  }

  .memory-editor-enter-from {
    opacity: 0;
    transform: translateX(-22px);
  }

  .memory-editor-leave-to {
    opacity: 0;
    transform: translateX(22px);
    pointer-events: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .paper-swap-enter-active,
  .paper-swap-leave-active {
    transition: none;
  }
}

@media (min-width: 1181px) {
  .app-shell > :deep(.nav-dock),
  .app-shell > :deep(.sidebar),
  .app-shell > :deep(.team-panel),
  .memory-editor-shell {
    position: sticky;
    top: 0;
    height: 100dvh;
  }

  .app-shell > :deep(.sidebar) {
    width: var(--ch-sidebar-width);
    transition: width var(--ch-sidebar-motion-duration) var(--ch-sidebar-motion-ease);
  }

  .app-shell > :deep(.team-panel) {
    transition: flex-basis var(--ch-duration-normal) var(--ch-ease-out),
      opacity var(--ch-duration-fast) var(--ch-ease-out),
      width var(--ch-duration-normal) var(--ch-ease-out);
  }

  .app-shell.trace-open > :deep(.team-panel) {
    flex: 0 0 0;
    width: 0;
    opacity: 0;
    overflow: hidden;
  }

}

@media (min-width: 781px) and (max-width: 1180px) {
  .app-shell > :deep(.nav-dock),
  .app-shell > :deep(.sidebar),
  .memory-editor-shell {
    position: sticky;
    top: 0;
    height: 100dvh;
  }

  .app-shell > :deep(.sidebar) {
    width: var(--ch-sidebar-width);
    transition: width var(--ch-sidebar-motion-duration) var(--ch-sidebar-motion-ease);
  }
}

@media (max-width: 1180px) {
  :deep(.team-panel) { display: none; }
}

@media (max-width: 780px) {
  .main-panel { padding: 0; }
  .mobile-bar {
    flex: 0 0 52px;
    display: grid;
    grid-template-columns: auto minmax(0, 1fr) auto;
    align-items: center;
    gap: var(--ch-space-2);
    padding: 0 var(--ch-space-3);
    background: var(--ch-surface);
    border-bottom: 1px solid var(--ch-border);
  }
  .mobile-bar button {
    min-height: 36px;
    padding: 0 var(--ch-space-2);
    border: 0;
    background: transparent;
    color: var(--ch-accent);
    font: 600 var(--ch-text-xs)/1 var(--ch-font-sans);
    cursor: pointer;
  }
  .mobile-bar strong {
    min-width: 0;
    overflow: hidden;
    font: 600 var(--ch-text-sm)/1.3 var(--ch-font-sans);
    text-align: center;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .rail-scrim {
    position: fixed;
    z-index: var(--ch-z-overlay);
    inset: 0;
    display: block;
    min-height: 0;
    border: 0;
    background: var(--ch-overlay-soft);
  }
  :deep(.sidebar) {
    position: fixed;
    z-index: var(--ch-z-modal);
    top: 0;
    left: 0;
    bottom: 0;
    width: min(300px, 88vw);
    transform: translateX(-104%);
    transition: transform var(--ch-duration-normal) var(--ch-ease-out);
    box-shadow: var(--ch-shadow-soft-hover);
  }
  :deep(.sidebar.is-open) { transform: translateX(0); }
  :deep(.team-panel) {
    display: flex;
    position: fixed;
    z-index: var(--ch-z-modal);
    top: 0;
    right: 0;
    bottom: 0;
    width: min(300px, 90vw);
    transform: translateX(104%);
    transition: transform var(--ch-duration-normal) var(--ch-ease-out);
    box-shadow: var(--ch-shadow-lg);
  }
  :deep(.team-panel.is-open) { transform: translateX(0); }
}

@media (prefers-reduced-motion: reduce) {
  .app-shell > :deep(.sidebar),
  .memory-editor-shell,
  .memory-editor-enter-active,
  .memory-editor-leave-active {
    transition: none;
  }
}
</style>
