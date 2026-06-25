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
      <svg class="logo" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <defs>
          <!-- 极浅纵向渐变：上方略亮、底部略深，制造柔和光泽而非立体感 -->
          <linearGradient id="lk-logo-bg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="#7c83f3" />
            <stop offset="100%" stop-color="#5860e0" />
          </linearGradient>
        </defs>

        <!-- 耳朵 -->
        <path d="M26 30 L33 10 L48 26 Z" fill="url(#lk-logo-bg)" />
        <path d="M74 30 L67 10 L52 26 Z" fill="url(#lk-logo-bg)" />

        <!-- 圆角方框主体 -->
        <rect x="14" y="20" width="72" height="70" rx="22" fill="url(#lk-logo-bg)" />

        <!-- 猫脸：两眼 + 鼻 -->
        <ellipse cx="38" cy="52" rx="4.2" ry="6.5" fill="#ffffff" />
        <ellipse cx="62" cy="52" rx="4.2" ry="6.5" fill="#ffffff" />
        <path d="M47 66 L53 66 L50 71 Z" fill="#ffffff" fill-opacity="0.92" />
      </svg>
      <span class="brand-title">稿搭</span>
    </div>
    <div class="sidebar-header">
      <button class="new-btn" @click="emit('create')">+ 新对话</button>
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
  width: 260px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.66);
  backdrop-filter: blur(22px) saturate(160%);
  -webkit-backdrop-filter: blur(22px) saturate(160%);
  border-right: 1px solid rgba(226, 232, 240, 0.6);
  box-shadow: 1px 0 0 rgba(255, 255, 255, 0.5) inset;
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
  width: 30px;
  height: 30px;
  display: block;
  border-radius: 9px;
  filter: drop-shadow(0 1px 2px rgba(30, 41, 59, 0.10))
          drop-shadow(0 3px 8px rgba(99, 102, 241, 0.28));
}

.brand-title {
  font-family: 'ZCOOL QingKe HuangYou', cursive;
  font-size: 26px;
  font-weight: 400;
  letter-spacing: 1px;
  background: linear-gradient(120deg, #6366f1, #7c83f3);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.sidebar-header {
  padding: 14px 14px 10px;
  flex-shrink: 0;
}

.new-btn {
  width: 100%;
  padding: 9px 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #818cf8);
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  box-shadow: 0 6px 16px rgba(99, 102, 241, 0.30), 0 1px 2px rgba(99, 102, 241, 0.20);
  transition: box-shadow 0.2s, filter 0.2s;
}
.new-btn:hover {
  filter: brightness(1.05);
  box-shadow: 0 8px 22px rgba(99, 102, 241, 0.38), 0 1px 2px rgba(99, 102, 241, 0.24);
}
.new-btn:active {
  filter: brightness(0.97);
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 4px 14px 12px;
  scrollbar-width: thin;
}

.sidebar-footer {
  padding: 8px 14px 12px;
  border-top: 1px solid rgba(226, 232, 240, 0.6);
}

.settings-btn {
  width: 100%;
  padding: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  transition: background 0.15s, border-color 0.15s;
}
.settings-btn:hover {
  background: #f8fafc;
  border-color: rgba(129, 140, 248, 0.4);
  color: #6366f1;
}

.session-item {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 12px;
  min-height: 42px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  color: #1e293b;
  transition: background 0.16s, box-shadow 0.16s;
  margin-bottom: 2px;
  box-sizing: border-box;
}

.session-item:hover {
  background: rgba(99, 102, 241, 0.05);
  box-shadow: inset 0 0 0 1px rgba(129, 140, 248, 0.12);
}

.session-item.active {
  background: rgba(99, 102, 241, 0.10);
  box-shadow: inset 0 0 0 1px rgba(129, 140, 248, 0.35), 0 4px 14px rgba(99, 102, 241, 0.12);
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
  border: 1px solid #6366f1;
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
  background: #818cf8;
  flex-shrink: 0;
  box-shadow: 0 0 0 0 rgba(129, 140, 248, 0.5);
  animation: pulseDot 1.2s ease-in-out infinite;
}

@keyframes pulseDot {
  0%   { opacity: 1; transform: scale(1); box-shadow: 0 0 6px 1px rgba(129, 140, 248, 0.55); }
  50%  { opacity: 0.5; transform: scale(0.85); box-shadow: 0 0 2px 0 rgba(129, 140, 248, 0.2); }
  100% { opacity: 1; transform: scale(1); box-shadow: 0 0 6px 1px rgba(129, 140, 248, 0.55); }
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
  background: rgba(99, 102, 241, 0.09);
  color: #6366f1;
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
