<script setup>
import { ref, nextTick, watch } from 'vue'

const props = defineProps({
  sessions: { type: Array, required: true },
  activeId: { type: String, default: null },
  streamingMap: { type: Object, default: () => ({}) },
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
      <div class="mark">稿</div>
      <div class="name">稿搭</div>
    </div>
    <button class="new-btn" @click="emit('create')">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <path d="M12 5v14M5 12h14" />
      </svg>
      新建会话
    </button>
    <div class="session-list">
      <div
        v-for="c in sessions"
        :key="c.id"
        :class="['sess', { active: c.id === activeId }]"
        @click="handleSelect(c)"
      >
        <div class="sess-main">
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
            <template v-if="streamingMap[c.id]">
              <span class="dot-pulse" aria-hidden="true"></span>
              <span>创作中</span>
            </template>
            <span v-else>{{ formatRel(c.updated_at) }}</span>
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
  width: 270px;
  flex-shrink: 0;
  background: var(--ch-bg-cool);
  border-right: 1px solid var(--ch-border);
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 18px 14px;
  flex-shrink: 0;
}

.mark {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--ch-primary);
  color: #fff;
  display: grid;
  place-items: center;
  font-family: var(--ch-serif);
  font-weight: 700;
  font-size: 15px;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--ch-primary) 30%, transparent);
  flex-shrink: 0;
}

.name {
  font-family: var(--ch-serif);
  font-weight: 600;
  font-size: 17px;
  color: var(--ch-text);
  letter-spacing: 0.02em;
}

.new-btn {
  margin: 0 14px 12px;
  padding: 9px 12px;
  border: 1px dashed var(--ch-border-2);
  border-radius: var(--ch-radius-sm);
  background: transparent;
  color: var(--ch-body);
  font-size: 13px;
  font-weight: 500;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color 0.15s, color 0.15s, background 0.15s;
}

.new-btn:hover {
  border-color: var(--ch-primary);
  color: var(--ch-primary);
  background: var(--ch-primary-soft);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 12px;
  scrollbar-width: thin;
}

.sess {
  position: relative;
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--ch-radius-sm);
  border: 1px solid transparent;
  cursor: pointer;
  margin-bottom: 2px;
  transition: background 0.12s, border-color 0.12s;
  box-sizing: border-box;
}

.sess:hover {
  background: color-mix(in srgb, var(--ch-text) 4%, transparent);
}

.sess.active {
  background: var(--ch-primary-soft);
  border-color: color-mix(in srgb, var(--ch-primary) 20%, transparent);
}

.sess.active::before {
  content: "";
  position: absolute;
  left: -10px;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: var(--ch-primary);
  border-radius: 2px;
}

.sess-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.sess-row {
  display: flex;
  align-items: center;
  min-width: 0;
  min-height: 22px;
}

.t {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-family: var(--ch-serif);
  font-size: 13.5px;
  font-weight: 500;
  color: var(--ch-text);
  letter-spacing: 0.01em;
}

.sess.active .t {
  color: var(--ch-primary-2);
}

.rename-input {
  flex: 1;
  min-width: 0;
  padding: 2px 6px;
  border: 1px solid var(--ch-border-2);
  border-radius: 4px;
  font-size: 13.5px;
  outline: none;
  font-family: inherit;
  background: var(--ch-surface);
  color: var(--ch-text);
}

.meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  color: var(--ch-faint);
}

.dot-pulse {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--ch-orange);
  animation: pulse 1.4s ease-in-out infinite;
  flex-shrink: 0;
}

@keyframes pulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

.session-actions {
  display: none;
  gap: 2px;
  flex-shrink: 0;
}

.sess:hover .session-actions {
  display: flex;
}

.icon-btn {
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--ch-muted);
  cursor: pointer;
  padding: 0;
  transition: background 0.15s, color 0.15s;
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
  font-size: 13px;
}
</style>
