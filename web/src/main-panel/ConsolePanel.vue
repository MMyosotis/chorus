<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import { getTestMode, setTestMode, getModelLists, getOptions, setOptions } from '../api.js'

const props = defineProps({
  activeId: { type: String, default: null },
  traceStore: { type: Object, required: true },
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['update:open'])

const tab = ref('trace')

function close() {
  emit('update:open', false)
}

const testModeEnabled = ref(false)
const testModeLoading = ref(false)
const testModeError = ref('')

async function refreshTestMode() {
  try {
    testModeEnabled.value = await getTestMode()
    testModeError.value = ''
  } catch (e) {
    testModeError.value = e.message || '请求失败'
  }
}

async function toggleTestMode() {
  testModeLoading.value = true
  testModeError.value = ''
  try {
    testModeEnabled.value = await setTestMode(!testModeEnabled.value)
  } catch (e) {
    testModeError.value = e.message || '切换失败'
  } finally {
    testModeLoading.value = false
  }
}

const chatModels = ref([])
const imageModels = ref([])
const chatModel = ref('')
const imageModel = ref('')
const webSearch = ref(true)
const modelsLoading = ref(false)
const modelsError = ref('')
const saving = ref(false)

async function loadModels() {
  modelsLoading.value = true
  modelsError.value = ''
  try {
    const [lists, opts] = await Promise.all([getModelLists(), getOptions()])
    chatModels.value = lists.chat_models || []
    imageModels.value = lists.image_models || []
    chatModel.value = opts.chat_model
    imageModel.value = opts.image_model
    webSearch.value = !!opts.web_search
  } catch (e) {
    modelsError.value = e.message || '加载模型选项失败'
  } finally {
    modelsLoading.value = false
  }
}

async function persistOptions(patch) {
  if (saving.value) return
  saving.value = true
  modelsError.value = ''
  try {
    const opts = await setOptions(patch)
    chatModel.value = opts.chat_model
    imageModel.value = opts.image_model
    webSearch.value = !!opts.web_search
  } catch (e) {
    modelsError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

function onChatModel(e) {
  chatModel.value = e.target.value
  persistOptions({ chat_model: e.target.value })
}
function onImageModel(e) {
  imageModel.value = e.target.value
  persistOptions({ image_model: e.target.value })
}
function onWebSearch(e) {
  webSearch.value = e.target.checked
  persistOptions({ web_search: e.target.checked })
}

const traces = computed(() => props.traceStore.getTraces(props.activeId))

const tracesBySource = computed(() => {
  const all = traces.value
  const groups = new Map()
  for (const t of all) {
    let key, label
    if (t.source === 'supervisor') {
      key = 'supervisor'
      label = 'supervisor'
    } else if (t.source === 'scheduler') {
      key = 'scheduler'
      label = 'scheduler'
    } else {
      key = 'task:' + (t.task_id || '?')
      label = (t.source || 'subagent') + ' · ' + (t.task_id || '?')
    }
    if (!groups.has(key)) groups.set(key, { key, label, items: [] })
    groups.get(key).items.push(t)
  }
  return [...groups.values()]
})

const CONSOLE_POLL = 1500
let consoleTimer = null

function startConsolePoll() {
  if (consoleTimer || !props.activeId) return
  props.traceStore.pollFromServer(props.activeId)
  consoleTimer = setInterval(() => {
    if (props.activeId) props.traceStore.pollFromServer(props.activeId)
  }, CONSOLE_POLL)
}

function stopConsolePoll() {
  if (consoleTimer) {
    clearInterval(consoleTimer)
    consoleTimer = null
  }
}

watch(() => props.open, (o) => {
  if (o) {
    startConsolePoll()
    loadModels()
    refreshTestMode()
  } else {
    stopConsolePoll()
  }
})
watch(() => props.activeId, (sid) => {
  if (!props.open || !sid) return
  props.traceStore.clearTrace(sid)
  props.traceStore.loadFromServer(sid)
})
onBeforeUnmount(stopConsolePoll)

function clearCurrentTrace() {
  if (!props.activeId) return
  if (!confirm('清空当前会话的 trace？')) return
  props.traceStore.clearTrace(props.activeId)
}

onMounted(refreshTestMode)

function fmtTs(created_at) {
  if (!created_at) return ''
  const d = new Date(created_at * 1000)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  const ms = String(d.getMilliseconds()).padStart(3, '0')
  return `${hh}:${mm}:${ss}.${ms}`
}

function shortJson(v) {
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}

function previewText(s, max = 200) {
  if (typeof s !== 'string') return s
  if (s.length <= max) return s
  return s.slice(0, max) + '…'
}

const ROLE_COLOR = {
  system: '#71717a',
  user: '#3b5a72',
  assistant: '#16a34a',
  tool: '#2c4a5e',
}

function roleColor(role) {
  return ROLE_COLOR[role] || '#71717a'
}

function renderMessageContent(m) {
  if (typeof m.content === 'string') return [{ kind: 'text', text: m.content }]
  if (Array.isArray(m.content)) {
    return m.content.map((part) => {
      if (typeof part === 'string') return { kind: 'text', text: part }
      if (part && part.type === 'text') return { kind: 'text', text: part.text || '' }
      if (part && part.type === 'image_url') {
        const url = part.image_url?.url || part.image_url || ''
        return { kind: 'image', url }
      }
      return { kind: 'text', text: shortJson(part) }
    })
  }
  if (m.content && typeof m.content === 'object' && m.content.__truncated) {
    return [{ kind: 'truncated', size: m.content.size, head: m.content.head }]
  }
  if (m.content == null) return []
  return [{ kind: 'text', text: shortJson(m.content) }]
}
</script>

<template>
  <transition name="console-slide">
    <aside v-if="open" class="console-panel" role="dialog" aria-label="控制台">
      <header class="console-header">
        <div class="tabs">
          <button :class="{ active: tab === 'settings' }" @click="tab = 'settings'">设置</button>
          <button :class="{ active: tab === 'trace' }" @click="tab = 'trace'">
            Trace <span v-if="traces.length" class="count">{{ traces.length }}</span>
          </button>
        </div>
        <button class="close-btn" @click="close" title="关闭">×</button>
      </header>

      <section v-if="tab === 'settings'" class="console-body">
        <div v-if="modelsLoading" class="hint">加载中...</div>
        <div v-else-if="modelsError" class="error-hint">{{ modelsError }}</div>
        <template v-else>
          <div class="group-title">模型</div>
          <label class="setting-row">
            <div class="setting-label"><strong>对话模型</strong></div>
            <select class="opt-select" :value="chatModel" :disabled="saving" @change="onChatModel">
              <option v-for="m in chatModels" :key="m.id" :value="m.id">{{ m.id }}</option>
            </select>
          </label>
          <label class="setting-row">
            <div class="setting-label"><strong>生图模型</strong></div>
            <select class="opt-select" :value="imageModel" :disabled="saving" @change="onImageModel">
              <option v-for="m in imageModels" :key="m.id" :value="m.id">{{ m.id }}</option>
            </select>
          </label>
          <div class="group-title">功能</div>
          <div class="setting-row">
            <div class="setting-label"><strong>联网搜索</strong></div>
            <label class="switch">
              <input type="checkbox" :checked="webSearch" :disabled="saving" @change="onWebSearch" />
              <span class="slider"></span>
            </label>
          </div>
        </template>
        <div class="setting-row">
          <div class="setting-label">
            <strong>图像测试模式</strong>
            <small>开启后 generate_image 返回固定 URL，不调用真实 API。</small>
          </div>
          <label class="switch">
            <input type="checkbox" :checked="testModeEnabled" @change="toggleTestMode"
              :disabled="testModeLoading" />
            <span class="slider"></span>
          </label>
        </div>
        <div v-if="testModeError" class="error-hint">{{ testModeError }}</div>
      </section>

      <section v-else class="console-body trace-body">
        <div class="trace-toolbar">
          <span class="hint">当前会话的 LLM 请求/响应、工具调用 trace</span>
          <button class="text-btn" @click="clearCurrentTrace" :disabled="!traces.length">清空</button>
        </div>
        <div v-if="!traces.length" class="empty-hint">暂无 trace。发条消息试试。</div>

        <details v-for="g in tracesBySource" :key="g.key" class="iter-group src-group" open>
          <summary>
            <span class="iter-title">{{ g.label }}</span>
            <span class="iter-meta"><span class="iter-count">{{ g.items.length }} 事件</span></span>
          </summary>
          <div v-for="(it, idx) in g.items" :key="idx" class="trace-item" :class="`phase-${it.phase}`">
            <div class="trace-head">
              <span class="phase-tag">{{ it.phase }}</span>
              <span class="ts">{{ fmtTs(it.created_at) }}</span>
            </div>

            <template v-if="it.phase === 'model_request'">
              <div class="kv">
                <span class="k">model</span>
                <span class="v">{{ it.payload?.model }}</span>
              </div>
              <details class="sub">
                <summary>messages ({{ (it.payload?.messages || []).length }})</summary>
                <div v-for="(m, mi) in it.payload?.messages || []" :key="mi" class="msg-row"
                  :style="{ borderLeftColor: roleColor(m.role) }">
                  <div class="msg-role" :style="{ color: roleColor(m.role) }">{{ m.role }}</div>
                  <div v-for="(p, pi) in renderMessageContent(m)" :key="pi" class="msg-part">
                    <pre v-if="p.kind === 'text'" class="text-block">{{ p.text }}</pre>
                    <img v-else-if="p.kind === 'image'" :src="p.url" class="thumb" alt="" />
                    <div v-else-if="p.kind === 'truncated'" class="truncated">
                      [已截断，{{ p.size }} 字节] {{ p.head }}…
                    </div>
                  </div>
                  <div v-if="m.tool_calls" class="tool-calls">
                    <div v-for="(tc, ti) in m.tool_calls" :key="ti" class="tool-call-line">
                      <span class="mono">{{ tc.function?.name || tc.name }}</span>
                      <span class="mono dim">({{ previewText(tc.function?.arguments || '', 120) }})</span>
                    </div>
                  </div>
                  <div v-if="m.tool_call_id" class="kv">
                    <span class="k">tool_call_id</span>
                    <span class="v mono dim">{{ m.tool_call_id }}</span>
                  </div>
                </div>
              </details>
              <details class="sub">
                <summary>tools ({{ (it.payload?.tools || []).length }})</summary>
                <pre class="text-block">{{ shortJson(it.payload?.tools) }}</pre>
              </details>
            </template>

            <template v-else-if="it.phase === 'model_response'">
              <div class="kv">
                <span class="k">finish_reason</span>
                <span class="v badge" :class="`badge-${it.payload?.finish_reason}`">
                  {{ it.payload?.finish_reason || '—' }}
                </span>
              </div>
              <pre v-if="it.payload?.content" class="text-block">{{ it.payload.content }}</pre>
              <div v-if="(it.payload?.tool_calls || []).length" class="sub-block">
                <div class="sub-title">tool_calls</div>
                <div v-for="(tc, ti) in it.payload.tool_calls" :key="ti" class="tool-call-line">
                  <span class="mono">{{ tc.name }}</span>
                  <span class="mono dim">({{ previewText(tc.arguments, 200) }})</span>
                </div>
              </div>
              <details v-if="(it.payload?.thinking_segments || []).length" class="sub">
                <summary>thinking_segments ({{ it.payload.thinking_segments.length }})</summary>
                <pre class="text-block">{{ shortJson(it.payload.thinking_segments) }}</pre>
              </details>
            </template>

            <template v-else-if="it.phase === 'tool_call'">
              <div class="kv">
                <span class="k">tool</span>
                <span class="v mono">{{ it.payload?.name }}</span>
              </div>
              <div class="kv">
                <span class="k">id</span>
                <span class="v mono dim">{{ it.payload?.tool_call_id }}</span>
              </div>
              <pre class="text-block">{{ shortJson(it.payload?.arguments) }}</pre>
            </template>

            <template v-else-if="it.phase === 'tool_result'">
              <div class="kv">
                <span class="k">tool</span>
                <span class="v mono">{{ it.payload?.name }}</span>
                <span v-if="it.payload?.duration_ms != null" class="dur">{{ it.payload.duration_ms }}ms</span>
              </div>
              <pre class="text-block">{{ previewText(it.payload?.content || '', 4000) }}</pre>
            </template>

            <template v-else>
              <pre v-if="it.payload" class="text-block">{{ shortJson(it.payload) }}</pre>
            </template>
          </div>
        </details>
      </section>
    </aside>
  </transition>
</template>

<style scoped>
.console-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 480px;
  max-width: 90vw;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(24px) saturate(170%);
  -webkit-backdrop-filter: blur(24px) saturate(170%);
  border-left: 1px solid var(--ch-border);
  box-shadow: -12px 0 32px rgba(0, 0, 0, 0.06);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-size: 13px;
  color: var(--ch-text);
}

@media (max-width: 600px) {
  .console-panel {
    width: 100vw;
    max-width: 100vw;
  }
}

.console-slide-enter-active,
.console-slide-leave-active {
  transition: transform 0.22s ease;
}

.console-slide-enter-from,
.console-slide-leave-to {
  transform: translateX(100%);
}

.console-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border-bottom: 1px solid var(--ch-border);
  background: var(--ch-bg-cool);
  flex-shrink: 0;
}

.tabs {
  display: flex;
  gap: 4px;
}

.tabs button {
  background: transparent;
  border: 1px solid transparent;
  padding: 4px 10px;
  border-radius: 6px;
  cursor: pointer;
  color: var(--ch-muted);
  font-size: 13px;
}

.tabs button:hover {
  color: var(--ch-text);
}

.tabs button.active {
  background: color-mix(in srgb, var(--ch-primary) 8%, transparent);
  border-color: transparent;
  color: var(--ch-text);
  font-weight: 500;
}

.count {
  display: inline-block;
  margin-left: 4px;
  padding: 0 6px;
  background: var(--ch-primary);
  color: #fff;
  border-radius: 10px;
  font-size: 11px;
  line-height: 16px;
  vertical-align: 1px;
}

.close-btn {
  background: transparent;
  border: none;
  font-size: 22px;
  line-height: 1;
  color: var(--ch-muted);
  cursor: pointer;
  padding: 0 6px;
}

.close-btn:hover {
  color: var(--ch-text);
}

.console-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 2px;
}

.setting-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.setting-label strong {
  font-weight: 500;
  color: var(--ch-text);
  font-size: 13px;
}

.setting-label small {
  color: var(--ch-muted);
  font-size: 11.5px;
  line-height: 1.5;
}

.group-title {
  font-family: var(--ch-serif);
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ch-primary-2);
  margin: 0 2px 8px;
  padding-top: 14px;
  border-top: 1px solid var(--ch-border);
}

.group-title:first-child {
  border-top: none;
  padding-top: 0;
}

.opt-select {
  appearance: none;
  -webkit-appearance: none;
  align-self: center;
  padding: 6px 28px 6px 10px;
  border: 1px solid var(--ch-border-2);
  border-radius: var(--ch-radius-sm);
  font-size: 13px;
  color: var(--ch-body);
  background-color: var(--ch-surface);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%233b5a72' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  cursor: pointer;
  transition: border-color 0.18s, box-shadow 0.18s;
}

.opt-select:hover {
  border-color: var(--ch-primary);
}

.opt-select:focus {
  outline: none;
  border-color: var(--ch-primary);
  box-shadow: 0 0 0 4px color-mix(in srgb, var(--ch-primary) 14%, transparent);
}

.text-btn {
  background: transparent;
  border: none;
  color: var(--ch-primary);
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
}

.text-btn:disabled {
  color: var(--ch-border-2);
  cursor: not-allowed;
}

.text-btn:hover:not(:disabled) {
  text-decoration: underline;
}

.error-hint {
  margin-top: 10px;
  padding: 8px 10px;
  background: var(--ch-red-soft);
  border: 1px solid color-mix(in srgb, var(--ch-red) 30%, var(--ch-border));
  border-radius: 6px;
  color: var(--ch-red);
  font-size: 12px;
}

/* iOS 风格开关 */
.switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  flex-shrink: 0;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  inset: 0;
  background: var(--ch-border-2);
  border-radius: 20px;
  transition: 0.2s;
  cursor: pointer;
}

.slider::before {
  content: '';
  position: absolute;
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background: #fff;
  border-radius: 50%;
  transition: 0.2s;
}

input:checked + .slider {
  background: var(--ch-orange);
}

input:checked + .slider::before {
  transform: translateX(16px);
}

input:disabled + .slider {
  opacity: 0.6;
  cursor: not-allowed;
}

.trace-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.hint {
  color: var(--ch-faint);
  font-size: 12px;
}

.src-group > .trace-item .text-block {
  max-height: 200px;
  overflow-y: auto;
}

.empty-hint {
  text-align: center;
  color: var(--ch-faint);
  padding: 40px 0;
  font-size: 13px;
}

.iter-group {
  margin-bottom: 12px;
  background: var(--ch-surface);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-sm);
  overflow: hidden;
}

.iter-group > summary {
  cursor: pointer;
  padding: 8px 12px;
  background: var(--ch-bg-cool);
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
  list-style: none;
}

.iter-group > summary::-webkit-details-marker,
.iter-group > summary::marker {
  display: none;
  content: '';
}

.iter-title {
  font-weight: 500;
  color: var(--ch-text);
}

.iter-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.iter-count {
  color: var(--ch-muted);
}

.trace-item {
  padding: 8px 12px;
  border-top: 1px solid var(--ch-border);
  border-left: 2px solid transparent;
}

.trace-item.phase-model_request {
  border-left-color: var(--ch-primary);
}

.trace-item.phase-model_response {
  border-left-color: var(--ch-green);
}

.trace-item.phase-tool_call,
.trace-item.phase-tool_result {
  border-left-color: var(--ch-primary-2);
}

.trace-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.phase-tag {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--ch-body);
}

.phase-model_request .phase-tag { color: var(--ch-primary); }
.phase-model_response .phase-tag { color: var(--ch-green); }
.phase-tool_call .phase-tag,
.phase-tool_result .phase-tag { color: var(--ch-primary-2); }

.ts {
  font-size: 11px;
  color: var(--ch-faint);
  font-family: ui-monospace, monospace;
}

.kv {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 2px 0;
  font-size: 12px;
}

.kv .k {
  color: var(--ch-faint);
  min-width: 80px;
  flex-shrink: 0;
}

.kv .v {
  color: var(--ch-text);
  word-break: break-all;
}

.dim {
  color: var(--ch-faint);
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
}

.dur {
  font-size: 11px;
  color: var(--ch-muted);
  margin-left: auto;
}

.badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  background: var(--ch-bg-cool);
  color: var(--ch-body);
}

.badge-tool_calls { background: var(--ch-primary-soft); color: var(--ch-primary); }
.badge-stop { background: var(--ch-green-soft); color: var(--ch-green); }
.badge-error { background: var(--ch-red-soft); color: var(--ch-red); }

.text-block {
  margin: 4px 0;
  padding: 6px 8px;
  background: var(--ch-bg-cool);
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  line-height: 1.5;
  color: var(--ch-body);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow: auto;
}

.sub {
  margin: 4px 0;
}

.sub > summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--ch-muted);
  user-select: none;
  padding: 2px 0;
  list-style: none;
}

.sub > summary::-webkit-details-marker,
.sub > summary::marker {
  display: none;
  content: '';
}

.sub > summary::before {
  content: '▸ ';
  display: inline-block;
  transition: transform 0.15s;
}

.sub[open] > summary::before {
  content: '▾ ';
}

.sub-block {
  margin: 6px 0;
}

.sub-title {
  font-size: 11px;
  color: var(--ch-faint);
  margin-bottom: 4px;
}

.msg-row {
  margin: 4px 0;
  padding: 4px 8px;
  border-left: 2px solid var(--ch-border-2);
  background: var(--ch-bg-cool);
  border-radius: 0 4px 4px 0;
}

.msg-role {
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 2px;
}

.msg-part {
  margin: 2px 0;
}

.thumb {
  max-width: 120px;
  max-height: 120px;
  border-radius: 4px;
  display: block;
}

.truncated {
  font-size: 11px;
  color: var(--ch-faint);
  font-style: italic;
  padding: 4px 6px;
  background: var(--ch-bg-cool);
  border-radius: 3px;
}

.tool-calls {
  margin-top: 4px;
}

.tool-call-line {
  font-size: 11.5px;
  padding: 2px 0;
  word-break: break-all;
}
</style>
