<script setup>
import { ref, nextTick, watch } from 'vue'

const props = defineProps({
  sessions: { type: Array, required: true },
  activeId: { type: String, default: null },
  streamingMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['select', 'create', 'delete', 'rename', 'open-settings'])

const editingId = ref(null)
const editingText = ref('')
const inputRef = ref(null)

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
      <span class="brand-title">稿搭</span>
    </div>
    <div class="sidebar-header">
      <button class="new-btn" @click="emit('create')">新对话</button>
    </div>
    <div class="session-list">
      <div
        v-for="c in sessions"
        :key="c.id"
        :class="['session-item', { active: c.id === activeId }]"
        @click="handleSelect(c)"
      >
        <span v-if="streamingMap[c.id]" class="pulse" aria-hidden="true"></span>

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
        <span v-else class="session-title">{{ c.title }}</span>

        <div v-if="editingId !== c.id" class="session-actions">
          <button
            class="icon-btn"
            title="重命名"
            @click="startRename(c, $event)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 20h9" />
              <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4Z" />
            </svg>
          </button>
          <button
            class="icon-btn"
            title="删除"
            :disabled="!!streamingMap[c.id]"
            @click="handleDelete(c, $event)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
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
    <div class="sidebar-footer">
      <button class="settings-btn" @click="emit('open-settings')">设置</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 270px;
  flex-shrink: 0;
  background: #f7f8fb;
  border: none;
  border-right: 1px solid var(--ch-border);
  border-radius: 0;
  box-shadow: none;
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
}

.brand {
  display: flex;
  align-items: center;
  padding: 24px 20px 8px;
  flex-shrink: 0;
}

.brand-title {
  font-size: 28px;
  line-height: 1.2;
  font-weight: 760;
  color: #172033;
}

.sidebar-header {
  padding: 10px 20px 12px;
  flex-shrink: 0;
}

.new-btn {
  width: 230px;
  height: 38px;
  border: 1px solid #d6dbea;
  border-radius: 10px;
  background: #ffffff;
  color: #172033;
  font-size: 14px;
  font-weight: 650;
  cursor: pointer;
  box-shadow: none;
  transition: background 0.2s, border-color 0.2s;
}
.new-btn:hover {
  background: #f8fafc;
  border-color: #c8d1e5;
}
.new-btn:active {
  background: #f3f6fa;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 2px 20px 12px;
  scrollbar-width: thin;
}

.sidebar-footer {
  padding: 10px 20px 20px;
}

.settings-btn {
  width: 230px;
  height: 36px;
  border: 1px solid transparent;
  background: transparent;
  color: #667085;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: background 0.15s, color 0.15s;
}
.settings-btn:hover {
  background: #eef2f7;
  color: #344054;
}

.session-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 11px 14px;
  min-height: 54px;
  border-radius: 12px;
  cursor: pointer;
  font-size: 14px;
  color: #1e293b;
  transition: background 0.16s, box-shadow 0.16s;
  margin-bottom: 8px;
  box-sizing: border-box;
}

.session-item:hover {
  background: #ffffff;
  box-shadow: inset 0 0 0 1px rgba(214, 220, 234, 0.9);
}

.session-item.active {
  background: #ffffff;
  box-shadow: inset 0 0 0 1px #cfd7e8;
}

.session-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rename-input {
  flex: 1;
  min-width: 0;
  padding: 2px 6px;
  border: 1px solid #c9d3e3;
  border-radius: 4px;
  font-size: 14px;
  outline: none;
  font-family: inherit;
  background: #fff;
  color: #1e293b;
}

.pulse {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #667085;
  flex-shrink: 0;
  box-shadow: 0 0 0 0 rgba(102, 112, 133, 0.35);
  animation: pulseDot 1.2s ease-in-out infinite;
}

@keyframes pulseDot {
  0%   { opacity: 1; transform: scale(1); box-shadow: 0 0 5px 1px rgba(102, 112, 133, 0.3); }
  50%  { opacity: 0.55; transform: scale(0.9); box-shadow: 0 0 2px 0 rgba(102, 112, 133, 0.14); }
  100% { opacity: 1; transform: scale(1); box-shadow: 0 0 5px 1px rgba(102, 112, 133, 0.3); }
}

.session-actions {
  display: none;
  gap: 2px;
  flex-shrink: 0;
}

.session-item:hover .session-actions {
  display: flex;
}

.icon-btn {
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  padding: 0;
}

.icon-btn:hover:not(:disabled) {
  background: #eef2f7;
  color: #344054;
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.empty {
  text-align: center;
  color: #94a3b8;
  padding: 24px 12px;
  font-size: 13px;
}
</style>
