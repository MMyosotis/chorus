<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import SettingsPanel from './SettingsPanel.vue'

const props = defineProps({
  sessions: { type: Array, required: true },
  activeId: { type: String, default: null },
  streamingMap: { type: Object, default: () => ({}) },
  activeWorking: { type: Boolean, default: false },
  activeCompleted: { type: Boolean, default: false },
  settingsOpen: { type: Boolean, default: false },
  expanded: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'create', 'delete', 'rename', 'collapse'])

const searchText = ref('')
const editingId = ref(null)
const editingText = ref('')
const inputRef = ref(null)
const openMenuId = ref(null)
const menuPosition = ref({ top: 0, left: 0 })
const visiblePane = ref(props.settingsOpen ? 'settings' : 'sessions')

const filteredSessions = computed(() => {
  const keyword = searchText.value.trim().toLocaleLowerCase()
  if (!keyword) return props.sessions
  return props.sessions.filter((session) => session.title.toLocaleLowerCase().includes(keyword))
})

function startRename(session, event) {
  event.stopPropagation()
  openMenuId.value = null
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
  openMenuId.value = null
  if (props.streamingMap[session.id]) return
  if (confirm(`确定删除「${session.title}」？`)) emit('delete', session.id)
}

function handleSelect(session) {
  openMenuId.value = null
  if (editingId.value !== session.id) emit('select', session.id)
}

function toggleSessionMenu(session, event) {
  event.stopPropagation()
  if (openMenuId.value === session.id) {
    openMenuId.value = null
    return
  }
  const rect = event.currentTarget.getBoundingClientRect()
  menuPosition.value = {
    top: Math.round(rect.top),
    left: Math.round(rect.right + 8),
  }
  openMenuId.value = session.id
}

function closeSessionMenu(event) {
  if (event.type === 'keydown' && event.key !== 'Escape') return
  openMenuId.value = null
}

watch(
  () => props.activeId,
  () => {
    if (editingId.value && editingId.value !== props.activeId) cancelRename()
    if (openMenuId.value && openMenuId.value !== props.activeId) openMenuId.value = null
  },
)

watch(
  () => [props.expanded, props.settingsOpen],
  ([expanded, settingsOpen]) => {
    // 收起时保留当前栏目，避免设置页先切回会话列表再被收起。
    if (expanded) visiblePane.value = settingsOpen ? 'settings' : 'sessions'
  },
)

onMounted(() => {
  document.addEventListener('click', closeSessionMenu)
  document.addEventListener('keydown', closeSessionMenu)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeSessionMenu)
  document.removeEventListener('keydown', closeSessionMenu)
})
</script>

<template>
  <aside
    class="sidebar"
    :class="{
      'is-settings-open': settingsOpen,
      'is-settings-pane': visiblePane === 'settings',
    }"
    aria-label="会话侧栏"
  >
    <Transition name="sidebar-reveal">
      <div v-if="expanded" class="sidebar-stage">
        <Transition name="sidebar-content" mode="out-in">
          <SettingsPanel v-if="visiblePane === 'settings'" key="settings" @collapse="emit('collapse')" />

          <div v-else key="sessions" class="sidebar-inner session-browser">
        <header class="sidebar-header">
          <h2 class="sidebar-title">稿搭</h2>
          <button type="button" class="sidebar-collapse" aria-label="收起侧栏" title="收起侧栏" @click="emit('collapse')">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3.5" y="4" width="17" height="16" rx="3" />
              <path d="M10.5 4v16" />
            </svg>
          </button>
        </header>
        <button class="new-chat" type="button" @click="emit('create')">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
          <span>新建会话</span>
        </button>

        <label class="search">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></svg>
          <input v-model="searchText" type="search" placeholder="搜索会话" aria-label="搜索会话" />
        </label>

        <div class="section-label">会话列表</div>

        <div class="session-list">
          <article
            v-for="session in filteredSessions"
            :key="session.id"
            :class="['session', { active: session.id === activeId }]"
            tabindex="0"
            @click="handleSelect(session)"
            @keydown.enter="handleSelect(session)"
          >
            <svg
              :class="['session-icon', { 'is-working': streamingMap[session.id] || (session.id === activeId && activeWorking) }]"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <path d="M5 18 3.5 21l4-1.5H16a5 5 0 0 0 5-5V9a5 5 0 0 0-5-5H8a5 5 0 0 0-5 5v5a4.9 4.9 0 0 0 2 4Z" />
              <g v-if="session.id === activeId">
                <circle cx="9" cy="12" r=".6" />
                <circle cx="13" cy="12" r=".6" />
              </g>
            </svg>
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
              <button
                type="button"
                class="session-menu-trigger"
                aria-label="会话更多操作"
                :aria-expanded="openMenuId === session.id"
                aria-haspopup="menu"
                @click="toggleSessionMenu(session, $event)"
              >
                <svg class="session-menu-ellipsis" viewBox="0 0 18 6" aria-hidden="true" shape-rendering="geometricPrecision">
                  <circle cx="3" cy="3" r="1.5" />
                  <circle cx="9" cy="3" r="1.5" />
                  <circle cx="15" cy="3" r="1.5" />
                </svg>
              </button>
              <Teleport to="body">
                <div
                  v-if="openMenuId === session.id"
                  class="session-menu"
                  :style="{ top: `${menuPosition.top}px`, left: `${menuPosition.left}px` }"
                  role="menu"
                  @click.stop
                >
                  <button type="button" role="menuitem" @click="startRename(session, $event)">
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M17 3L21 7L8 20H4V16L17 3Z" />
                    </svg>
                    <span>重命名</span>
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    class="is-danger"
                    :disabled="!!streamingMap[session.id]"
                    @click="handleDelete(session, $event)"
                  >
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M3 6H5H21" />
                      <path d="M8 6V4C8 3.46957 8.21071 2.96086 8.58579 2.58579C8.96086 2.21071 9.46957 2 10 2H14C14.5304 2 15.0391 2.21071 15.4142 2.58579C15.7893 2.96086 16 3.46957 16 4V6M19 6V20C19 20.5304 18.7893 21.0391 18.4142 21.4142C18.0391 21.7893 17.5304 22 17 22H7C6.46957 22 5.96086 21.7893 5.58579 21.4142C5.21071 21.0391 5 20.5304 5 20V6H19Z" />
                      <path d="M10 11V17" />
                      <path d="M14 11V17" />
                    </svg>
                    <span>删除</span>
                  </button>
                </div>
              </Teleport>
            </div>
          </article>
          <p v-if="filteredSessions.length === 0" class="empty">
            {{ searchText ? '没有匹配的会话' : '暂无会话' }}
          </p>
        </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </aside>
</template>

<style scoped>
.sidebar {
  position: relative;
  height: 100%;
  flex-shrink: 0;
  overflow: hidden;
  background: var(--ch-surface-glass-soft);
  border-right: 1px solid var(--ch-border);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}

.sidebar-collapse {
  width: 32px;
  height: 32px;
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

.sidebar-collapse:hover {
  background: var(--ch-surface-2);
  color: var(--ch-text);
}

.sidebar-collapse svg {
  width: 24px;
  height: 24px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.sidebar-inner {
  height: 100%;
  display: flex;
  padding: 24px 16px 16px;
}

.sidebar-stage {
  width: 100%;
  height: 100%;
}

/* 桌面端由外层收拢宽度，内容层保留自身宽度。 */
@media (min-width: 781px) {
  .sidebar-stage {
    width: var(--ch-session-rail);
  }

  .sidebar.is-settings-pane .sidebar-stage {
    width: min(480px, calc(100vw - var(--ch-nav-rail)));
  }
}

.sidebar-reveal-enter-active {
  will-change: opacity, transform;
  transition: opacity var(--ch-sidebar-motion-duration) var(--ch-sidebar-motion-ease),
    transform var(--ch-sidebar-motion-duration) var(--ch-sidebar-motion-ease);
}

.sidebar-reveal-leave-active {
  will-change: opacity, transform;
  transition: opacity var(--ch-sidebar-motion-duration) var(--ch-sidebar-motion-ease),
    transform var(--ch-sidebar-motion-duration) var(--ch-sidebar-motion-ease);
  pointer-events: none;
}

.sidebar-reveal-enter-from {
  opacity: 0;
  transform: translateX(-28px);
}

.sidebar-reveal-leave-to {
  opacity: 0;
  transform: translateX(16px);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  min-height: 28px;
  margin-bottom: var(--ch-space-4);
}

.session-browser {
  min-width: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.sidebar-content-enter-active,
.sidebar-content-leave-active {
  will-change: opacity, transform;
  transition: opacity 260ms cubic-bezier(.22, .8, .25, 1),
    transform 260ms cubic-bezier(.22, .8, .25, 1);
}

.sidebar-content-enter-from {
  opacity: 0;
  transform: translateX(-12px);
}

.sidebar-content-leave-to {
  opacity: 0;
  transform: translateX(12px);
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-reveal-enter-active,
  .sidebar-reveal-leave-active,
  .sidebar-content-enter-active,
  .sidebar-content-leave-active {
    transition: none;
  }
}

.sidebar-title {
  margin: 0;
  font-size: var(--ch-text-lg);
  font-weight: var(--ch-font-bold);
  letter-spacing: .3px;
}

.new-chat {
  width: 100%;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--ch-space-2);
  flex-shrink: 0;
  margin-bottom: var(--ch-space-3);
  padding: 0 var(--ch-space-3);
  border: 1px solid var(--ch-ink);
  border-radius: var(--ch-radius-bar-btn);
  background: var(--ch-ink);
  box-shadow: var(--ch-shadow-sm);
  color: var(--ch-on-ink);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-semibold);
  cursor: pointer;
  transition: box-shadow var(--ch-duration-fast) var(--ch-ease),
    border-color var(--ch-duration-fast) var(--ch-ease);
}

.new-chat:hover {
  border-color: var(--ch-ink-hover);
  background: var(--ch-ink-hover);
  box-shadow: var(--ch-shadow-md);
}

.new-chat svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: var(--ch-on-ink);
  stroke-width: 2;
  stroke-linecap: round;
}

.search {
  height: 44px;
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
  flex-shrink: 0;
  margin-bottom: var(--ch-space-4);
  padding: 0 var(--ch-space-3);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-list);
  background: var(--ch-surface);
  color: var(--ch-text-faint);
  transition: border-color var(--ch-duration-fast) var(--ch-ease),
    box-shadow var(--ch-duration-fast) var(--ch-ease);
}

.search:hover {
  border-color: var(--ch-border-strong);
}

.search:focus-within {
  border-color: var(--ch-accent);
  box-shadow: var(--ch-shadow-focus);
}

.search svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
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

.section-label {
  margin: 0 0 var(--ch-space-3);
  color: var(--ch-text-faint);
  font-size: var(--ch-text-xs);
}

.session-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--ch-space-1);
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
  height: 44px;
  padding: 0 var(--ch-space-3);
  border-radius: var(--ch-radius-list);
  cursor: pointer;
  outline: none;
  transition: background var(--ch-duration-fast) var(--ch-ease);
}

.session:hover,
.session:focus-visible {
  background: var(--ch-surface-2);
}

.session.active {
  background: var(--ch-accent-soft-gradient);
}

.session-icon {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
  color: var(--ch-text-faint);
  transition: color var(--ch-duration-fast) var(--ch-ease);
}

.session.active .session-icon {
  color: var(--ch-accent);
}

.session-icon.is-working {
  color: var(--ch-accent);
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
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-semibold);
  line-height: var(--ch-leading-tight);
}

.session.active .session-content strong {
  color: var(--ch-accent);
}

.session-status {
  flex-shrink: 0;
  color: var(--ch-accent);
  font-size: var(--ch-text-xs);
  font-weight: var(--ch-font-medium);
}

.session-actions {
  display: flex;
  align-items: center;
  flex-shrink: 0;
  visibility: hidden;
}

.session.active .session-actions,
.session:hover .session-actions,
.session:focus-within .session-actions {
  visibility: visible;
}

.session-actions button {
  min-width: 24px;
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--ch-accent);
  cursor: pointer;
}

.session-menu-trigger {
  line-height: 0;
}

.session-menu-trigger .session-menu-ellipsis {
  width: 16px;
  height: 8px;
  display: block;
  flex: 0 0 16px;
  fill: currentColor;
  stroke: none;
}

.session-actions button:disabled {
  opacity: .4;
  cursor: not-allowed;
}

.session-actions svg {
  width: 16px;
  height: 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.session-menu {
  position: fixed;
  z-index: var(--ch-z-dropdown);
  width: 128px;
  display: flex;
  flex-direction: column;
  padding: var(--ch-space-2);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface);
  box-shadow: var(--ch-shadow-dropdown);
}

.session-menu button {
  width: 100%;
  min-height: 32px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: var(--ch-space-2);
  padding: 0 var(--ch-space-2);
  border: 0;
  border-radius: var(--ch-radius-btn);
  outline: 0;
  background: transparent;
  color: var(--ch-text-secondary);
  font-family: var(--ch-font-sans);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-medium);
  cursor: pointer;
}

.session-menu button:hover:not(:disabled),
.session-menu button:focus-visible {
  background: var(--ch-surface-2);
}

.session-menu button:focus-visible {
  outline: 2px solid var(--ch-accent);
  outline-offset: -2px;
}

.session-menu button.is-danger {
  color: var(--ch-danger);
}

.session-menu button svg {
  width: 16px;
  height: 16px;
  flex: 0 0 auto;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.rename-input {
  width: 100%;
  height: 32px;
  padding: 0 var(--ch-space-2);
  border: 1px solid var(--ch-accent);
  border-radius: var(--ch-radius-list);
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
  .sidebar-title { margin-bottom: var(--ch-space-2); }
  .new-chat { margin-bottom: var(--ch-space-2); }
  .search { margin-bottom: var(--ch-space-2); }
}
</style>
