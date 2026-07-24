<script setup>
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps({
  sessions: { type: Array, required: true },
  activeId: { type: String, default: null },
  streamingMap: { type: Object, default: () => ({}) },
  activeWorking: { type: Boolean, default: false },
  activeCompleted: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'create', 'delete', 'rename'])

const searchText = ref('')
const editingId = ref(null)
const editingText = ref('')
const inputRef = ref(null)

const filteredSessions = computed(() => {
  const keyword = searchText.value.trim().toLocaleLowerCase()
  if (!keyword) return props.sessions
  return props.sessions.filter((session) => session.title.toLocaleLowerCase().includes(keyword))
})

function startRename(session, event) {
  event.stopPropagation()
  editingId.value = session.id
  editingText.value = session.title
  nextTick(() => {
    inputRef.value?.focus()
    inputRef.value?.select()
  })
}

function commitRename() {
  if (!editingId.value) return
  const id = editingId.value
  const title = editingText.value.trim()
  editingId.value = null
  if (!title) return
  const current = props.sessions.find((session) => session.id === id)
  if (current && current.title !== title) emit('rename', { id, title })
}

function cancelRename() {
  editingId.value = null
  editingText.value = ''
}

function onRenameKeydown(event) {
  if (event.key === 'Enter') {
    event.preventDefault()
    commitRename()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    cancelRename()
  }
}

function handleDelete(session, event) {
  event.stopPropagation()
  if (props.streamingMap[session.id]) return
  if (confirm(`确定删除「${session.title}」？`)) emit('delete', session.id)
}

function handleSelect(session) {
  if (editingId.value !== session.id) emit('select', session.id)
}

watch(
  () => props.activeId,
  () => {
    if (editingId.value && editingId.value !== props.activeId) cancelRename()
  },
)
</script>

<template>
  <aside class="sidebar" aria-label="会话侧栏">
    <div class="sidebar-inner">
    <button class="new-chat" type="button" @click="emit('create')">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
      <span>新建会话</span>
    </button>

    <label class="search">
      <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
      <input v-model="searchText" type="search" placeholder="搜索会话" aria-label="搜索会话" />
    </label>

    <div class="session-list">
      <article
        v-for="session in filteredSessions"
        :key="session.id"
        :class="['session', { active: session.id === activeId }]"
        tabindex="0"
        @click="handleSelect(session)"
        @keydown.enter="handleSelect(session)"
      >
        <span
          :class="['session-dot', { 'is-working': streamingMap[session.id] || (session.id === activeId && activeWorking) }]"
          aria-hidden="true"
        ></span>
        <div class="session-content">
          <input
            v-if="editingId === session.id"
            ref="inputRef"
            v-model="editingText"
            class="rename-input"
            maxlength="60"
            @blur="commitRename"
            @click.stop
            @keydown="onRenameKeydown"
          />
          <template v-else>
            <strong>{{ session.title }}</strong>
            <span
              v-if="streamingMap[session.id] || (session.id === activeId && activeWorking)"
              class="session-status"
            >
              创作中
            </span>
          </template>
        </div>
        <div v-if="editingId !== session.id" class="session-actions">
          <button type="button" aria-label="重命名会话" title="重命名" @click="startRename(session, $event)">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9" /><path d="m16.5 3.5 4 4L7 21l-4 1 1-4L16.5 3.5Z" /></svg>
          </button>
          <button
            type="button"
            aria-label="删除会话"
            title="删除"
            :disabled="!!streamingMap[session.id]"
            @click="handleDelete(session, $event)"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14M10 11v6M14 11v6" /></svg>
          </button>
        </div>
      </article>
      <p v-if="filteredSessions.length === 0" class="empty">
        {{ searchText ? '没有匹配的会话' : '暂无会话' }}
      </p>
    </div>
    </div>
  </aside>
</template>

<style scoped>
.sidebar {
  height: 100%;
  flex-shrink: 0;
  overflow: hidden;
  background: var(--ch-surface);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.sidebar-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--ch-space-3);
}

.new-chat {
  width: 100%;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ch-space-2);
  flex-shrink: 0;
  margin-bottom: var(--ch-space-3);
  padding: 0 var(--ch-space-3);
  border: 0;
  border-radius: var(--ch-radius-btn);
  background: var(--ch-accent-gradient);
  color: var(--ch-on-accent);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-semibold);
  cursor: pointer;
  transition: box-shadow var(--ch-duration-fast) var(--ch-ease);
}

.new-chat:hover {
  box-shadow: var(--ch-shadow-md);
}

.new-chat svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
}

.search {
  height: 40px;
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
  flex-shrink: 0;
  margin-bottom: var(--ch-space-2);
  padding: 0 var(--ch-space-2);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface-2);
  color: var(--ch-text-muted);
  transition: border-color var(--ch-duration-fast) var(--ch-ease),
    background var(--ch-duration-fast) var(--ch-ease),
    box-shadow var(--ch-duration-fast) var(--ch-ease);
}

.search:focus-within {
  border-color: var(--ch-accent);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-focus);
}

.search svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
}

.search input {
  width: 100%;
  min-width: 0;
  padding: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  line-height: var(--ch-leading-normal);
}

.search input::placeholder {
  color: var(--ch-text-faint);
}

.search input::-webkit-search-cancel-button {
  display: none;
}

.session-list {
  flex: 1;
  overflow-y: auto;
  scrollbar-width: none;
}

.session-list::-webkit-scrollbar {
  display: none;
}

.session {
  position: relative;
  width: 100%;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
  height: 40px;
  padding: 0 var(--ch-space-2);
  border-radius: var(--ch-radius-btn);
  cursor: pointer;
  outline: none;
  transition: background var(--ch-duration-fast) var(--ch-ease);
}

.session:hover,
.session:focus-visible {
  background: var(--ch-surface-2);
}

.session.active {
  background: var(--ch-accent-soft);
}

.session.active::before {
  content: "";
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 3px;
  border-radius: var(--ch-radius-pill);
  background: var(--ch-accent);
}

.session-dot {
  width: 8px;
  height: 8px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--ch-text-faint);
  transition: background var(--ch-duration-fast) var(--ch-ease);
}

.session.active .session-dot {
  background: var(--ch-accent);
}

.session-dot.is-working {
  background: var(--ch-accent);
  box-shadow: 0 0 0 3px var(--ch-accent-soft);
  animation: pulse 1.6s ease-in-out infinite;
}

.session-content {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
}

.session-content strong,
.session-content span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-content strong {
  min-width: 0;
  flex: 1;
  color: var(--ch-text-secondary);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-medium);
  line-height: var(--ch-leading-tight);
}

.session.active .session-content strong {
  color: var(--ch-accent-soft-text);
  font-weight: var(--ch-font-semibold);
}

.session-status {
  flex-shrink: 0;
  color: var(--ch-accent);
  font-size: var(--ch-text-xs);
  font-weight: var(--ch-font-medium);
}

.session-actions {
  display: none;
  align-items: center;
  flex-shrink: 0;
  gap: var(--ch-space-1);
}

.session:hover .session-actions,
.session:focus-within .session-actions {
  display: flex;
}

.session-actions button {
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: var(--ch-radius-btn);
  background: transparent;
  color: var(--ch-text-faint);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease),
    color var(--ch-duration-fast) var(--ch-ease);
}

.session-actions button:hover:not(:disabled) {
  background: var(--ch-surface-3);
  color: var(--ch-text);
}

.session-actions button:disabled {
  opacity: .4;
  cursor: not-allowed;
}

.session-actions svg {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.rename-input {
  width: 100%;
  height: 32px;
  padding: 0 var(--ch-space-2);
  border: 1px solid var(--ch-accent);
  border-radius: var(--ch-radius-btn);
  outline: none;
  background: var(--ch-surface);
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  line-height: var(--ch-leading-tight);
  box-shadow: var(--ch-shadow-focus);
}

.empty {
  margin: 0;
  padding: var(--ch-space-4) var(--ch-space-2);
  color: var(--ch-text-faint);
  font-size: var(--ch-text-xs);
  text-align: center;
}

@keyframes pulse {
  0%, 100% { opacity: .4; }
  50% { opacity: 1; }
}

@media (max-height: 800px) {
  .sidebar-inner { padding: var(--ch-space-2); }
  .new-chat { margin-bottom: var(--ch-space-2); }
}
</style>
