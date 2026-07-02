<script setup>
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
import { getTestMode, setTestMode } from '../api.js'

const props = defineProps({
  activeId: { type: String, default: null },
  traceStore: { type: Object, required: true },
  open: { type: Boolean, default: false },
})
const emit = defineEmits(['update:open'])

const tab = ref('trace') // 'settings' | 'trace'

function close() {
  emit('update:open', false)
}

// 测试模式状态
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

// trace 数据：当前会话的列表
const traces = computed(() => props.traceStore.getTraces(props.activeId))

// 按来源分组树：supervisor / 各 task(task_id) / scheduler（spec 6.8）
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

// 打开时轮询拉 subagent/scheduler trace（不连 SSE，靠轮询补）；关闭即停
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
  if (o) startConsolePoll()
  else stopConsolePoll()
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

// ---- TraceItem 渲染辅助 ----

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
  system: '#64748b',
  user: '#6366f1',
  assistant: '#10b981',
  tool: '#4f46e5',
}

function roleColor(role) {
  return ROLE_COLOR[role] || '#64748b'
}

// 单条 message 内容渲染：content 可能是 string，也可能是 array（multimodal）
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

        <!-- 按来源分组树（supervisor / 各 task / scheduler），组内按 created_at 时间顺序 -->
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

            <!-- model_request: 显示 messages + tools schema -->
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

            <!-- model_response: 显示 finish_reason + content + tool_calls -->
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

            <!-- tool_call -->
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

            <!-- tool_result -->
            <template v-else-if="it.phase === 'tool_result'">
              <div class="kv">
                <span class="k">tool</span>
                <span class="v mono">{{ it.payload?.name }}</span>
                <span v-if="it.payload?.duration_ms != null" class="dur">{{ it.payload.duration_ms }}ms</span>
              </div>
              <pre class="text-block">{{ previewText(it.payload?.content || '', 4000) }}</pre>
            </template>

            <!-- schedule（scheduler 派发/CAS/zombie 事件）-->
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
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(24px) saturate(170%);
  -webkit-backdrop-filter: blur(24px) saturate(170%);
  border-left: 1px solid rgba(226, 232, 240, 0.7);
  box-shadow: -16px 0 40px rgba(30, 41, 59, 0.10), -2px 0 8px rgba(30, 41, 59, 0.05);
  z-index: 1000;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  font-size: 13px;
  color: #1e293b;
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
  border-bottom: 1px solid rgba(226, 232, 240, 0.6);
  background: rgba(248, 250, 252, 0.6);
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
  color: #64748b;
  font-size: 13px;
}

.tabs button:hover {
  color: #1e293b;
}

.tabs button.active {
  background: #ffffff;
  border-color: rgba(226, 232, 240, 0.8);
  color: #1e293b;
  font-weight: 500;
  box-shadow: 0 1px 3px rgba(30, 41, 59, 0.06);
}

.count {
  display: inline-block;
  margin-left: 4px;
  padding: 0 6px;
  background: linear-gradient(135deg, #6366f1, #818cf8);
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
  color: #64748b;
  cursor: pointer;
  padding: 0 6px;
}

.close-btn:hover {
  color: #1e293b;
}

.console-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

/* settings tab */
.setting-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
}

.setting-label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.setting-label small {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.text-btn {
  background: transparent;
  border: none;
  color: #6366f1;
  cursor: pointer;
  font-size: 12px;
  padding: 2px 4px;
}

.text-btn:disabled {
  color: #cbd5e1;
  cursor: not-allowed;
}

.text-btn:hover:not(:disabled) {
  text-decoration: underline;
}

.error-hint {
  margin-top: 10px;
  padding: 8px 10px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 6px;
  color: #b91c1c;
  font-size: 12px;
}

/* iOS-style switch */
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
  background: #cbd5e1;
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
  background: linear-gradient(135deg, #6366f1, #818cf8);
}

input:checked + .slider::before {
  transform: translateX(16px);
}

input:disabled + .slider {
  opacity: 0.6;
  cursor: not-allowed;
}

/* trace tab */
.trace-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.hint {
  color: #94a3b8;
  font-size: 12px;
}

.src-group > .trace-item .text-block {
  max-height: 200px;
  overflow-y: auto;
}

.empty-hint {
  text-align: center;
  color: #94a3b8;
  padding: 40px 0;
  font-size: 13px;
}

.iter-group {
  margin-bottom: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.iter-group > summary {
  cursor: pointer;
  padding: 8px 12px;
  background: #f8fafc;
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
  color: #1e293b;
}

.iter-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.iter-count {
  color: #64748b;
}

.trace-item {
  padding: 8px 12px;
  border-top: 1px solid #f1f5f9;
  border-left: 2px solid transparent;
}

.trace-item.phase-model_request {
  border-left-color: #6366f1;
}

.trace-item.phase-model_response {
  border-left-color: #10b981;
}

.trace-item.phase-tool_call,
.trace-item.phase-tool_result {
  border-left-color: #4f46e5;
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
  color: #475569;
}

.phase-model_request .phase-tag { color: #4f46e5; }
.phase-model_response .phase-tag { color: #059669; }
.phase-tool_call .phase-tag,
.phase-tool_result .phase-tag { color: #4f46e5; }

.ts {
  font-size: 11px;
  color: #94a3b8;
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
  color: #94a3b8;
  min-width: 80px;
  flex-shrink: 0;
}

.kv .v {
  color: #1e293b;
  word-break: break-all;
}

.dim {
  color: #94a3b8;
}

.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
}

.dur {
  font-size: 11px;
  color: #64748b;
  margin-left: auto;
}

.badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  background: #f1f5f9;
  color: #475569;
}

.badge-tool_calls { background: #ede9fe; color: #6d28d9; }
.badge-stop { background: #d1fae5; color: #047857; }
.badge-error { background: #fee2e2; color: #b91c1c; }

.text-block {
  margin: 4px 0;
  padding: 6px 8px;
  background: #f8fafc;
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 11.5px;
  line-height: 1.5;
  color: #334155;
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
  color: #64748b;
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
  color: #94a3b8;
  margin-bottom: 4px;
}

.msg-row {
  margin: 4px 0;
  padding: 4px 8px;
  border-left: 2px solid #cbd5e1;
  background: #fafbfc;
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
  color: #94a3b8;
  font-style: italic;
  padding: 4px 6px;
  background: #f1f5f9;
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
