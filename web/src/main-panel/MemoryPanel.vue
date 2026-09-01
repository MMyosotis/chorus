<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ChevronDown, X } from '@lucide/vue'
import { createMemory, deleteMemory, updateMemory } from '../api.js'
import AgentAvatar from '../team-panel/AgentAvatar.vue'

const props = defineProps({
  memory: { type: Object, default: null },
})
const emit = defineEmits(['close', 'saved', 'deleted'])

const VISIBLE_TO_OPTIONS = [
  { value: 'supervisor', avatar: 'chief', label: '主编辑' },
  { value: 'idea', avatar: 'idea', label: '选题官' },
  { value: 'script', avatar: 'script', label: '文案官' },
  { value: 'image', avatar: 'image', label: '配图官' },
  { value: 'finalize', avatar: 'finalize', label: '汇总官' },
]
const PLATFORM_OPTIONS = ['博客', '小红书']
const LEGACY_PLATFORM_MAP = { '网页博客': '博客', 'web-blog': '博客' }
const KIND_OPTIONS = [
  { value: 'reference', label: '参考' },
  { value: 'performance', label: '已验证' },
]

const saving = ref(false)
const error = ref('')
const draft = ref(emptyDraft())
const openSelect = ref(null)
const editingExisting = computed(() => !!props.memory?.id)

function emptyDraft() {
  return { description: '', content: '', platform: '博客', visible_to: [], kind: 'reference' }
}

function normalizePlatform(platforms) {
  const value = platforms?.[0]
  if (PLATFORM_OPTIONS.includes(value)) return value
  return LEGACY_PLATFORM_MAP[value] || '博客'
}

function syncDraft(memory) {
  error.value = ''
  draft.value = memory
    ? {
        description: memory.description,
        content: memory.content,
        platform: normalizePlatform(memory.platform),
        // 空 = 全员可见，编辑器里回填为全选展示
        visible_to: memory.visible_to.length ? [...memory.visible_to] : VISIBLE_TO_OPTIONS.map((opt) => opt.value),
        kind: memory.kind,
      }
    : emptyDraft()
}

watch(() => props.memory, syncDraft, { immediate: true })

function toggleSelect(name) {
  openSelect.value = openSelect.value === name ? null : name
}

function chooseSelect(name, value) {
  draft.value[name] = value
  openSelect.value = null
}

function closeSelectOnOutsideClick(event) {
  if (!event.target.closest('.custom-select')) openSelect.value = null
}

function closeSelectOnEscape(event) {
  if (event.key === 'Escape') openSelect.value = null
}

onMounted(() => {
  document.addEventListener('click', closeSelectOnOutsideClick)
  document.addEventListener('keydown', closeSelectOnEscape)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeSelectOnOutsideClick)
  document.removeEventListener('keydown', closeSelectOnEscape)
})

function toggleVisible(value) {
  const selected = new Set(draft.value.visible_to)
  if (selected.has(value)) selected.delete(value)
  else selected.add(value)
  draft.value.visible_to = [...selected]
}

function requestClose() {
  if (!saving.value) emit('close')
}

async function save() {
  if (saving.value) return
  if (!draft.value.description.trim()) {
    error.value = '描述不能为空'
    return
  }
  saving.value = true
  error.value = ''
  const visibleTo = draft.value.visible_to
  const body = {
    description: draft.value.description.trim(),
    content: draft.value.content,
    platform: [draft.value.platform],
    // 全选时存空数组，保持「空 = 全员可见」的存储语义
    visible_to: visibleTo.length === VISIBLE_TO_OPTIONS.length ? [] : visibleTo,
    kind: draft.value.kind,
  }
  try {
    const memory = editingExisting.value
      ? await updateMemory(props.memory.id, body)
      : await createMemory(body)
    emit('saved', memory || { ...body, id: props.memory?.id })
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!props.memory?.id || saving.value) return
  if (!confirm('删除这条记忆？')) return
  saving.value = true
  error.value = ''
  try {
    await deleteMemory(props.memory.id)
    emit('deleted')
  } catch (e) {
    error.value = e.message || '删除失败'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <aside class="memory-panel" aria-label="记忆详情">
    <div class="memory-body">
      <div class="memory-surface">
        <header class="memory-header">
          <div>
            <h2>{{ editingExisting ? '编辑记忆' : '添加记忆' }}</h2>
          </div>
          <button type="button" class="icon-btn" aria-label="关闭详情" title="关闭详情" @click="requestClose">
            <X aria-hidden="true" />
          </button>
        </header>

        <div class="memory-editor">
          <label class="field">
            <span class="field-label">描述</span>
            <input v-model="draft.description" type="text" class="text-input" placeholder="一句话概括这条记忆" />
          </label>
          <label class="field">
            <span class="field-label">正文</span>
            <textarea v-model="draft.content" rows="5" class="text-area" placeholder="详细内容"></textarea>
          </label>

          <div class="field-row settings-row">
              <label class="field">
                <span class="field-label">平台</span>
                <div class="custom-select">
                  <button
                    type="button"
                    class="select-trigger"
                    :aria-expanded="openSelect === 'platform'"
                    aria-haspopup="listbox"
                    @click="toggleSelect('platform')"
                  >
                    <span>{{ draft.platform }}</span>
                    <ChevronDown aria-hidden="true" />
                  </button>
                  <Transition name="select-menu">
                    <div v-if="openSelect === 'platform'" class="select-menu" role="listbox" aria-label="平台">
                      <button
                        v-for="platform in PLATFORM_OPTIONS"
                        :key="platform"
                        type="button"
                        role="option"
                        :aria-selected="draft.platform === platform"
                        :class="{ selected: draft.platform === platform }"
                        @click="chooseSelect('platform', platform)"
                      >{{ platform }}</button>
                    </div>
                  </Transition>
                </div>
              </label>
              <label class="field">
                <span class="field-label">类型</span>
                <div class="custom-select">
                  <button
                    type="button"
                    class="select-trigger"
                    :aria-expanded="openSelect === 'kind'"
                    aria-haspopup="listbox"
                    @click="toggleSelect('kind')"
                  >
                    <span>{{ KIND_OPTIONS.find((opt) => opt.value === draft.kind)?.label }}</span>
                    <ChevronDown aria-hidden="true" />
                  </button>
                  <Transition name="select-menu">
                    <div v-if="openSelect === 'kind'" class="select-menu" role="listbox" aria-label="类型">
                      <button
                        v-for="opt in KIND_OPTIONS"
                        :key="opt.value"
                        type="button"
                        role="option"
                        :aria-selected="draft.kind === opt.value"
                        :class="{ selected: draft.kind === opt.value }"
                        @click="chooseSelect('kind', opt.value)"
                      >{{ opt.label }}</button>
                    </div>
                  </Transition>
                </div>
              </label>
          </div>
          <div class="field role-field">
            <span class="field-label">可见角色</span>
            <div class="role-picker" role="group" aria-label="可见角色">
                <button
                  v-for="opt in VISIBLE_TO_OPTIONS"
                  :key="opt.value"
                  type="button"
                  class="role-option"
                  :class="{ selected: draft.visible_to.includes(opt.value) }"
                  :aria-pressed="draft.visible_to.includes(opt.value)"
                  @click="toggleVisible(opt.value)"
                >
                  <AgentAvatar :agent-type="opt.avatar" :inactive="!draft.visible_to.includes(opt.value)" :size="40" />
                  <span>{{ opt.label }}</span>
                </button>
            </div>
          </div>
          <div v-if="error" class="error-hint">{{ error }}</div>
        </div>
        <footer class="editor-actions">
          <button v-if="editingExisting" type="button" class="danger-btn" :disabled="saving" @click="remove">删除</button>
          <span class="action-spacer"></span>
          <button type="button" class="secondary-btn" :disabled="saving" @click="requestClose">取消</button>
          <button type="button" class="primary-btn" :disabled="saving" @click="save">{{ saving ? '保存中…' : '保存' }}</button>
        </footer>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.memory-panel {
  width: var(--ch-memory-editor-rail, var(--ch-session-rail));
  height: 100%;
  display: flex;
  flex: 0 0 var(--ch-memory-editor-rail, var(--ch-session-rail));
  flex-direction: column;
  overflow: hidden;
  border-right: 1px solid var(--ch-border);
  background: var(--ch-surface-glass-soft);
}

.memory-body,
.memory-surface {
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.memory-body {
  box-sizing: border-box;
  padding: 24px var(--ch-space-3) var(--ch-space-3);
}

.memory-surface { overflow: visible; background: var(--ch-surface); }

.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  min-height: 28px;
  margin-bottom: var(--ch-space-4);
  padding: 0;
}

.memory-header h2 {
  margin: 0;
  color: var(--ch-text);
  font-size: var(--ch-text-lg);
  font-weight: var(--ch-font-bold);
}

.icon-btn {
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
}

.icon-btn:hover { background: var(--ch-surface-2); color: var(--ch-text); }
.icon-btn svg { width: 24px; height: 24px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; }

.memory-editor {
  min-height: 0;
  flex: 1;
  padding: 0;
  overflow: visible;
}

.field { min-width: 0; display: flex; flex-direction: column; gap: var(--ch-space-2); margin: 0 0 var(--ch-space-4); }
.field-label { color: var(--ch-text-secondary); font-size: var(--ch-text-sm); font-weight: var(--ch-font-medium); }
.field-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--ch-space-3); }
.settings-row { margin-top: var(--ch-space-5); }

.text-input,
.text-area {
  box-sizing: border-box;
  width: 100%;
  padding: var(--ch-space-2) var(--ch-space-3);
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface);
  color: var(--ch-text);
  font: inherit;
  font-size: var(--ch-text-sm);
  line-height: 1.5;
  transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease);
}

.text-input { height: 44px; }
.text-area { min-height: 112px; resize: none; }
.text-input:focus,.text-area:focus { outline: none; border-color: var(--ch-accent); background: color-mix(in srgb, var(--ch-accent) 3%, var(--ch-surface)); }

.custom-select { position: relative; }
.select-trigger {
  box-sizing: border-box;
  width: 100%;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--ch-space-3);
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface);
  color: var(--ch-text);
  font: inherit;
  font-size: var(--ch-text-sm);
  text-align: left;
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease);
}
.select-trigger:hover { border-color: var(--ch-text-faint); }
.select-trigger:focus-visible,
.select-trigger[aria-expanded='true'] { outline: none; border-color: var(--ch-border-strong); background: var(--ch-surface); }
.select-trigger svg { width: 12px; height: 12px; flex: 0 0 auto; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.3; transition: transform var(--ch-duration-fast) var(--ch-ease); }
.select-trigger[aria-expanded='true'] svg { color: var(--ch-accent); transform: rotate(180deg); }
.select-menu { position: absolute; z-index: var(--ch-z-dropdown); top: calc(100% + var(--ch-space-1)); right: 0; left: 0; display: grid; gap: var(--ch-space-1); padding: var(--ch-space-2); border: 1px solid color-mix(in srgb, var(--ch-border-strong) 70%, white); border-radius: var(--ch-radius-list); background: var(--ch-surface); box-shadow: 0 6px 18px color-mix(in srgb, var(--ch-text) 7%, transparent), 0 1px 3px color-mix(in srgb, var(--ch-text) 4%, transparent); }
.select-menu button { min-height: 40px; padding: 0 var(--ch-space-2); border: 0; border-radius: var(--ch-radius-btn); background: transparent; color: var(--ch-text-secondary); font: var(--ch-font-medium) var(--ch-text-sm)/1 var(--ch-font-sans); text-align: left; cursor: pointer; }.select-menu button.selected { color: var(--ch-accent); }.select-menu button:hover { background: var(--ch-accent-soft); color: var(--ch-accent); }.select-menu-enter-active,.select-menu-leave-active { transition: opacity var(--ch-duration-fast) var(--ch-ease), transform var(--ch-duration-fast) var(--ch-ease); }.select-menu-enter-from,.select-menu-leave-to { opacity: 0; transform: translateY(-4px); }

.role-field { margin-bottom: 0; }
.role-picker { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: var(--ch-space-1); }
.role-option {
  min-width: 0;
  display: grid;
  justify-items: center;
  gap: var(--ch-space-1);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--ch-text-faint);
  font: var(--ch-font-medium) var(--ch-text-xs)/1.2 var(--ch-font-sans);
  cursor: pointer;
}

.role-option:hover { color: var(--ch-text-secondary); }
.role-option.selected { color: var(--ch-accent); }
.role-option :deep(.agent-avatar) { transition: box-shadow var(--ch-duration-fast) var(--ch-ease); }
.role-option.selected :deep(.agent-avatar) { box-shadow: 0 0 0 1px var(--ch-accent); }

.editor-actions {
  display: flex;
  align-items: center;
  gap: var(--ch-space-2);
  flex-shrink: 0;
  padding: var(--ch-space-3) 0 0;
  border-top: 1px solid var(--ch-border);
}

.action-spacer { flex: 1; }
.primary-btn,.secondary-btn,.danger-btn { min-height: 40px; padding: 0 var(--ch-space-4); border-radius: var(--ch-radius-btn); font: 600 var(--ch-text-sm)/1 var(--ch-font-sans); cursor: pointer; transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease), color var(--ch-duration-fast) var(--ch-ease); }
.primary-btn { border: 0; background: var(--ch-ink); color: var(--ch-on-ink); }.primary-btn:hover:not(:disabled) { background: var(--ch-ink-hover); }
.secondary-btn { border: 1px solid var(--ch-border-strong); background: var(--ch-surface); color: var(--ch-text); }.secondary-btn:hover:not(:disabled) { background: var(--ch-surface-2); }
.danger-btn { border: 1px solid var(--ch-danger); background: transparent; color: var(--ch-danger); }.danger-btn:hover:not(:disabled) { background: var(--ch-danger-soft); }
.primary-btn:disabled,.secondary-btn:disabled,.danger-btn:disabled { opacity: .5; cursor: not-allowed; }
.error-hint { margin-top: var(--ch-space-2); padding: var(--ch-space-2) var(--ch-space-3); border-radius: var(--ch-radius-btn); background: var(--ch-danger-soft); color: var(--ch-danger-text); font-size: var(--ch-text-xs); }

@media (max-height: 800px) {
  .settings-row { margin-top: var(--ch-space-3); }
  .text-area { min-height: 96px; }
}
</style>
