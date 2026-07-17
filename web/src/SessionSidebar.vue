<script setup>
import { ref, nextTick, watch } from 'vue'

const props = defineProps({
  sessions: { type: Array, required: true },
  activeId: { type: String, default: null },
  streamingMap: { type: Object, default: () => ({}) },
  activeWorking: { type: Boolean, default: false },
  activeCompleted: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'create', 'delete', 'rename'])

const editingId = ref(null)
const editingText = ref('')
const inputRef = ref(null)

function formatRel(ts) {
  if (!ts) return ''
  const now = Date.now() / 1000
  const diff = Math.max(0, now - ts)
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 172800) return '昨天'
  if (diff < 604800) return `${Math.floor(diff / 86400)} 天前`
  if (diff < 1209600) return '上周'
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

const MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
function formatIssueDate(ts) {
  if (!ts) return { short: '—', full: '—' }
  const d = new Date(ts * 1000)
  return {
    short: `${MONTHS[d.getMonth()]} ${String(d.getDate()).padStart(2, '0')}`,
    full: `${d.getFullYear()}/${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')}`,
  }
}

function startRename(c, e) {
  e.stopPropagation()
  editingId.value = c.id
  editingText.value = c.title
  nextTick(() => {
    if (inputRef.value) {
      inputRef.value.focus()
      inputRef.value.select()
    }
  })
}

function commitRename() {
  if (!editingId.value) return
  const id = editingId.value
  const title = editingText.value.trim()
  editingId.value = null
  if (!title) return
  const cur = props.sessions.find((c) => c.id === id)
  if (cur && cur.title === title) return
  emit('rename', { id, title })
}

function cancelRename() {
  editingId.value = null
  editingText.value = ''
}

function onKey(e) {
  if (e.key === 'Enter') {
    e.preventDefault()
    commitRename()
  } else if (e.key === 'Escape') {
    e.preventDefault()
    cancelRename()
  }
}

function handleDelete(c, e) {
  e.stopPropagation()
  if (props.streamingMap[c.id]) return
  if (!confirm(`确定删除「${c.title}」？`)) return
  emit('delete', c.id)
}

function handleSelect(c) {
  if (editingId.value === c.id) return
  emit('select', c.id)
}

watch(
  () => props.activeId,
  () => {
    if (editingId.value && editingId.value !== props.activeId) {
      cancelRename()
    }
  }
)
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="name">稿搭<span class="en">GAODA · EDITORIAL</span></div>
    </div>
    <button class="new-btn" @click="emit('create')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <path d="M12 5v14M5 12h14" />
      </svg>
      新建稿件
    </button>
    <div class="section-title">稿件 · COPY</div>
    <div class="session-list">
      <div
        v-for="(c, idx) in sessions"
        :key="c.id"
        :class="['sess', { active: c.id === activeId }]"
        @click="handleSelect(c)"
      >
        <div class="sess-main">
          <div class="issue-meta">
            <span>VOL. {{ String(Math.max(1, sessions.length - idx)).padStart(2, '0') }}</span>
            <span v-if="streamingMap[c.id] || (c.id === activeId && activeWorking)" class="live"><i></i>创作中</span>
            <span v-else>{{ c.id === activeId ? (activeCompleted ? '已完成' : '当前稿') : '已完成' }}</span>
          </div>
          <div class="sess-row">
            <input
              v-if="editingId === c.id"
              ref="inputRef"
              v-model="editingText"
              class="rename-input"
              maxlength="60"
              @keydown="onKey"
              @blur="commitRename"
              @click.stop
            />
            <span v-else class="t">{{ c.title }}</span>
          </div>
          <div class="meta">
            <span class="date-short">{{ formatIssueDate(c.updated_at).short }}</span>
            <span class="date-full">{{ formatIssueDate(c.updated_at).full }}</span>
          </div>
        </div>
        <div v-if="editingId !== c.id" class="session-actions">
          <button class="icon-btn" title="重命名" @click="startRename(c, $event)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
            </svg>
          </button>
          <button class="icon-btn" title="删除" :disabled="!!streamingMap[c.id]" @click="handleDelete(c, $event)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6 18 20a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
              <path d="M10 11v6M14 11v6" />
              <path d="M9 6V4a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
            </svg>
          </button>
        </div>
      </div>
      <div v-if="sessions.length === 0" class="empty">暂无会话</div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: var(--ch-rail);
  flex-shrink: 0;
  padding: var(--ch-left-rail-padding);
  background: var(--ch-canvas);
  border-right: 1px solid rgba(110, 103, 93, 0.34);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.brand {
  margin: 0;
  padding: 0 0 32px;
  border: 0;
  flex-shrink: 0;
}

.name {
  font-family: var(--ch-serif);
  font-weight: 700;
  font-size: 34px;
  line-height: .95;
  color: var(--ch-text);
  letter-spacing: 0.12em;
}
.name .en {
  display: block;
  line-height: 1.2;
  font-family: var(--ch-sans);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.28em;
  color: var(--ch-meta);
  margin-top: 12px;
}

.new-btn {
  width: 100%;
  min-height: 44px;
  margin: 0 0 30px;
  padding: 0 12px;
  border: 2px solid var(--ch-warm);
  background: transparent;
  color: var(--ch-warm);
  font-family: var(--ch-serif);
  font-size: 14px;
  font-weight: 600;
  line-height: 1;
  letter-spacing: 0.06em;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}
.new-btn svg { width: 17px; height: 17px; stroke-width: 2.4; }

.new-btn:hover {
  border-color: var(--ch-warm);
  color: var(--ch-warm);
  background: rgba(141, 51, 37, .055);
}

.section-title {
  height: var(--ch-rail-head-height);
  display: flex;
  align-items: center;
  margin: 0;
  padding: 1px 2px 10px;
  border-bottom: 1px solid var(--ch-rail-rule);
  color: var(--ch-warm);
  font: var(--ch-rail-head-weight) var(--ch-rail-head-size)/var(--ch-rail-head-line) var(--ch-serif);
  letter-spacing: var(--ch-rail-head-tracking);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 0 12px;
  scrollbar-width: none;
}
.session-list::-webkit-scrollbar { display: none; }

.sess {
  position: relative;
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 18px 14px 19px;
  border-top: 0;
  border-bottom: 1px solid rgba(116, 107, 94, .45);
  border-left: 0;
  cursor: pointer;
  margin: 0;
  transition: background 0.12s, border-color 0.12s;
  box-sizing: border-box;
}

.sess::before {
  content: "";
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: 0;
  width: 3px;
  z-index: 1;
  background: var(--ch-warm);
  opacity: 0;
  transition: opacity 180ms ease-out;
}

.sess::after {
  content: "";
  position: absolute;
  inset: 8px 0;
  z-index: 0;
  background: rgba(255, 254, 250, .76);
  opacity: 0;
  pointer-events: none;
  transition: opacity 180ms ease-out;
}

.sess:hover {
  background: color-mix(in srgb, var(--ch-text) 4%, transparent);
}

.sess.active {
  margin: 0;
  padding: 18px 14px 19px;
  background: transparent;
}
.sess.active::before,
.sess.active::after {
  opacity: 1;
}

.sess-main {
  position: relative;
  z-index: 2;
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.issue-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 14px;
  color: var(--ch-meta);
  font: 500 var(--ch-rail-meta-size)/14px var(--ch-serif);
  font-variant-numeric: lining-nums tabular-nums;
}
.issue-meta > span {
  display: inline-flex;
  align-items: center;
  height: 14px;
  line-height: 14px;
}
.issue-meta .live { gap: 6px; color: var(--ch-warm); }
.issue-meta .live i { width: 5px; height: 5px; border-radius: 50%; background: currentColor; animation: breathe 1.7s ease-in-out infinite; }

.sess-row {
  display: flex;
  align-items: center;
  min-width: 0;
  height: calc(var(--ch-rail-head-size) * 1.45);
  margin: 9px 0 9px;
}

.t {
  display: block;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--ch-serif);
  font-size: var(--ch-rail-head-size);
  font-weight: 600;
  color: var(--ch-text);
  line-height: 1.45;
  letter-spacing: .025em;
}

.sess.active .t { color: var(--ch-text); }

.rename-input {
  flex: 1;
  min-width: 0;
  padding: 2px 6px;
  border: 1px solid var(--ch-border-2);
  border-radius: 0;
  font-size: var(--t-meta);
  outline: none;
  font-family: inherit;
  background: var(--ch-surface);
  color: var(--ch-text);
}

.meta {
  display: flex;
  align-items: baseline;
  gap: 10px;
  font-family: var(--ch-serif);
  font-size: var(--ch-rail-meta-size);
  font-weight: 500;
  line-height: 1.25;
  color: var(--ch-meta);
  font-variant-numeric: lining-nums tabular-nums;
}
.date-short {
  color: var(--ch-text);
  font: 500 11px/1.25 var(--ch-serif);
  letter-spacing: .04em;
}
.date-full {
  color: var(--ch-meta);
  font: 500 11px/1.3 var(--ch-serif);
  letter-spacing: .02em;
}

.dot-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ch-orange);
  animation: pulse 1.4s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes breathe {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

.session-actions {
  position: absolute;
  z-index: 3;
  top: 50%;
  right: 14px;
  transform: translateY(-50%);
  display: none;
  gap: 2px;
}

.sess:hover .session-actions {
  display: flex;
}

.sess:hover .sess-row {
  padding-right: 60px;
}

.icon-btn {
  width: 22px;
  height: 22px;
  min-height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 0;
  background: transparent;
  color: var(--ch-muted);
  cursor: pointer;
  padding: 0;
  transition: background 0.15s, color 0.15s;
}

@media (max-width: 1180px) {
  .sidebar { width: 224px; padding-inline: 20px; }
}

.icon-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--ch-text) 6%, transparent);
  color: var(--ch-text);
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.empty {
  text-align: center;
  color: var(--ch-faint);
  padding: 24px 12px;
  font-size: var(--t-meta);
}
</style>
