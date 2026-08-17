<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Ellipsis, MessageCircle, MessageCircleMore, PanelLeft, Pencil, Plus, Search, Trash2 } from '@lucide/vue'
import SettingsPanel from './SettingsPanel.vue'
import MemoryBrowser from './MemoryBrowser.vue'
import ConsolePanel from './main-panel/ConsolePanel.vue'

const props = defineProps({
  sessions: { type: Array, required: true },
  activeId: { type: String, default: null },
  streamingMap: { type: Object, default: () => ({}) },
  activeWorking: { type: Boolean, default: false },
  activeCompleted: { type: Boolean, default: false },
  settingsOpen: { type: Boolean, default: false },
  memoryOpen: { type: Boolean, default: false },
  consoleOpen: { type: Boolean, default: false },
  traceStore: { type: Object, required: true },
  taskGraph: { type: Object, default: null },
  memoryRefreshKey: { type: Number, default: 0 },
  selectedMemoryId: { type: String, default: null },
  expanded: { type: Boolean, default: false },
})

const emit = defineEmits(['select', 'create', 'delete', 'rename', 'collapse', 'memory-edit', 'memory-create'])

const searchText = ref('')
const editingId = ref(null)
const editingText = ref('')
const inputRef = ref(null)
const openMenuId = ref(null)
const menuPosition = ref({ top: 0, left: 0 })
const visiblePane = ref(props.settingsOpen ? 'settings' : props.memoryOpen ? 'memory' : props.consoleOpen ? 'trace' : 'sessions')

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
  () => [props.expanded, props.settingsOpen, props.memoryOpen, props.consoleOpen],
  ([expanded, settingsOpen, memoryOpen, consoleOpen]) => {
    // 收起时保留当前栏目，避免设置页先切回会话列表再被收起。
    if (expanded) visiblePane.value = settingsOpen ? 'settings' : memoryOpen ? 'memory' : consoleOpen ? 'trace' : 'sessions'
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
    }"
    aria-label="会话侧栏"
  >
    <Transition name="sidebar-reveal">
      <div v-if="expanded" class="sidebar-stage">
        <Transition name="sidebar-pane">
          <section v-if="visiblePane === 'settings'" key="settings" class="sidebar-pane">
            <SettingsPanel @collapse="emit('collapse')" />
          </section>

          <section v-else-if="visiblePane === 'memory'" key="memory" class="sidebar-pane">
            <MemoryBrowser
              :refresh-key="memoryRefreshKey"
              :selected-id="selectedMemoryId"
              @collapse="emit('collapse')"
              @edit="emit('memory-edit', $event)"
              @create="emit('memory-create')"
            />
          </section>

          <section v-else-if="visiblePane === 'trace'" key="trace" class="sidebar-pane">
            <ConsolePanel
              :open="true"
              :active-id="activeId"
              :trace-store="traceStore"
              :task-graph="taskGraph"
              @close="emit('collapse')"
            />
          </section>

          <section v-else key="sessions" class="sidebar-pane">
            <div class="sidebar-inner session-browser">
              <header class="sidebar-header">
                <h2 class="sidebar-title">稿搭</h2>
                <button type="button" class="sidebar-collapse" aria-label="收起侧栏" title="收起侧栏" @click="emit('collapse')">
                  <PanelLeft aria-hidden="true" />
                </button>
              </header>
              <button class="new-chat" type="button" @click="emit('create')">
                <Plus aria-hidden="true" />
                <span>新建会话</span>
              </button>

              <label class="search">
                <Search aria-hidden="true" />
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
            <component
              :is="session.id === activeId ? MessageCircleMore : MessageCircle"
              :class="['session-icon', { 'is-working': streamingMap[session.id] || (session.id === activeId && activeWorking) }]"
              aria-hidden="true"
            />
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
                <Ellipsis class="session-menu-ellipsis" aria-hidden="true" />
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
                    <Pencil aria-hidden="true" />
                    <span>重命名</span>
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    class="is-danger"
                  :disabled="!!streamingMap[session.id]"
                  @click="handleDelete(session, $event)"
                >
                    <Trash2 aria-hidden="true" />
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
          </section>
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
  width: 20px;
  height: 20px;
  transform: translateX(6px);
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
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

/* 桌面端由外层收拢宽度，内容层保留自身宽度。 */
@media (min-width: 781px) {
  .sidebar-stage {
    width: var(--ch-sidebar-width);
    transition: width var(--ch-sidebar-motion-duration) var(--ch-sidebar-motion-ease);
  }

}

.sidebar-reveal-enter-active,
.sidebar-reveal-leave-active {
  transition: opacity 160ms var(--ch-sidebar-motion-ease);
}

.sidebar-reveal-enter-from,
.sidebar-reveal-leave-to {
  opacity: 0;
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

.sidebar-pane {
  position: absolute;
  inset: 0;
  display: flex;
  overflow: hidden;
  background: var(--ch-surface-glass-soft);
  border-right: 1px solid var(--ch-border);
}

.sidebar-pane-enter-active {
  z-index: 2;
  will-change: opacity, transform;
  transition: opacity 220ms ease-out,
    transform 360ms cubic-bezier(.16, .84, .26, 1);
}

.sidebar-pane-leave-active {
  z-index: 1;
  will-change: opacity, transform;
  transition: opacity 120ms ease-out,
    transform 300ms cubic-bezier(.22, .8, .25, 1);
}

.sidebar-pane-enter-from {
  opacity: 0;
  transform: translateX(-22px);
}

.sidebar-pane-leave-to {
  opacity: 0;
  transform: translateX(22px);
  pointer-events: none;
}

@media (prefers-reduced-motion: reduce) {
  .sidebar-reveal-enter-active,
  .sidebar-reveal-leave-active,
  .sidebar-pane-enter-active,
  .sidebar-pane-leave-active {
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
  margin-bottom: var(--ch-space-5);
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
  border: 1px solid color-mix(in srgb, var(--ch-border-strong) 70%, white);
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
  box-shadow: none;
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
  margin: 0 0 var(--ch-space-2);
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
  height: 16px;
  display: block;
  flex: 0 0 16px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
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
  box-shadow: 0 6px 18px color-mix(in srgb, var(--ch-text) 7%, transparent),
    0 1px 3px color-mix(in srgb, var(--ch-text) 4%, transparent);
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
  border: 0;
  border-radius: var(--ch-radius-btn);
  outline: none;
  background: var(--ch-surface);
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  line-height: var(--ch-leading-tight);
  box-shadow: none;
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
  .new-chat { margin-bottom: var(--ch-space-3); }
}
</style>
