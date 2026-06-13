<script setup>
import { ref, nextTick, watch } from 'vue'

const props = defineProps({
  conversations: { type: Array, required: true },
  activeId: { type: String, default: null },
  streamingMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['select', 'create', 'delete', 'rename'])

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
  const cur = props.conversations.find((c) => c.id === id)
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
      <svg class="logo" viewBox="2 2 96 96" xmlns="http://www.w3.org/2000/svg">
        <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" stroke-width="6" />
        <path
          d="M25 45 L33 18 L50 32 L67 18 L75 55 Q45 55 35 80"
          fill="none"
          stroke="currentColor"
          stroke-width="6"
          stroke-linecap="square"
          stroke-linejoin="miter"
        />
        <circle cx="42" cy="42" r="4" fill="currentColor" />
        <circle cx="58" cy="42" r="4" fill="currentColor" />
      </svg>
      <span class="brand-title">氛围猫猫</span>
    </div>
    <div class="sidebar-header">
      <button class="new-btn" @click="emit('create')">+ 新对话</button>
    </div>
    <div class="conv-list">
      <div
        v-for="c in conversations"
        :key="c.id"
        :class="['conv-item', { active: c.id === activeId }]"
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
        <span v-else class="conv-title">{{ c.title }}</span>

        <div v-if="editingId !== c.id" class="conv-actions">
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
      <div v-if="conversations.length === 0" class="empty">暂无会话</div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  width: 260px;
  flex-shrink: 0;
  background: #fff;
  border-right: 1px solid #e2e8f0;
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 28px 16px 8px;
  flex-shrink: 0;
}

.logo {
  width: 1.2em;
  height: 1.2em;
  font-size: 26px;
  color: #3b82f6;
  display: block;
}

.brand-title {
  font-family: 'ZCOOL QingKe HuangYou', cursive;
  font-size: 26px;
  font-weight: 400;
  letter-spacing: 1px;
  color: #3b82f6;
}

.sidebar-header {
  padding: 14px 14px 10px;
  flex-shrink: 0;
}

.new-btn {
  width: 100%;
  padding: 9px 12px;
  border: none;
  border-radius: 8px;
  background: #3b82f6;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.18s;
}
.new-btn:hover {
  background: #2563eb;
}

.conv-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 14px 12px;
  scrollbar-width: thin;
}

.conv-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  color: #1e293b;
  transition: background 0.15s;
  margin-bottom: 2px;
}

.conv-item:hover {
  background: #f1f5f9;
}

.conv-item.active {
  background: #eff6ff;
}

.conv-title {
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
  border: 1px solid #3b82f6;
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
  background: #3b82f6;
  flex-shrink: 0;
  animation: pulseDot 1.2s ease-in-out infinite;
}

@keyframes pulseDot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.4; transform: scale(0.8); }
}

.conv-actions {
  display: none;
  gap: 2px;
  flex-shrink: 0;
}

.conv-item:hover .conv-actions {
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
  background: #e2e8f0;
  color: #1e293b;
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
