<script setup>
import { onMounted, ref } from 'vue'
import { listMemories, createMemory, updateMemory, deleteMemory } from '../api.js'

const emit = defineEmits(['close'])

const VISIBLE_TO_OPTIONS = [
  { value: 'supervisor', label: '主编辑' },
  { value: 'idea', label: '选题官' },
  { value: 'script', label: '文案官' },
  { value: 'image', label: '配图官' },
  { value: 'finalize', label: '汇总官' },
]

const KIND_OPTIONS = [
  { value: 'reference', label: '参考' },
  { value: 'performance', label: '已验证' },
]

const memories = ref([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const draftId = ref(null)
const editing = ref(false)
const draft = ref(emptyDraft())

function emptyDraft() {
  return { description: '', content: '', platform: '', visible_to: [], kind: 'reference' }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    memories.value = await listMemories()
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

function select(memory) {
  draftId.value = memory.id
  editing.value = true
  draft.value = {
    description: memory.description,
    content: memory.content,
    platform: memory.platform.join(', '),
    visible_to: [...memory.visible_to],
    kind: memory.kind,
  }
}

function startNew() {
  draftId.value = null
  editing.value = true
  draft.value = emptyDraft()
}

function toggleVisible(value) {
  const set = new Set(draft.value.visible_to)
  if (set.has(value)) set.delete(value)
  else set.add(value)
  draft.value.visible_to = [...set]
}

async function save() {
  if (saving.value) return
  if (!draft.value.description.trim()) {
    error.value = '描述不能为空'
    return
  }
  saving.value = true
  error.value = ''
  const body = {
    description: draft.value.description.trim(),
    content: draft.value.content,
    platform: draft.value.platform.split(',').map((seg) => seg.trim()).filter(Boolean),
    visible_to: draft.value.visible_to,
    kind: draft.value.kind,
  }
  try {
    if (draftId.value) {
      await updateMemory(draftId.value, body)
    } else {
      const created = await createMemory(body)
      draftId.value = created.id
    }
    await load()
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

async function remove() {
  if (!draftId.value || saving.value) return
  if (!confirm('删除这条记忆？')) return
  saving.value = true
  error.value = ''
  try {
    await deleteMemory(draftId.value)
    draftId.value = null
    editing.value = false
    draft.value = emptyDraft()
    await load()
  } catch (e) {
    error.value = e.message || '删除失败'
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <Teleport to="body">
  <div class="memory-overlay" @click.self="emit('close')">
    <div class="memory-panel" role="dialog" aria-label="创作者记忆管理">
      <header class="memory-header">
        <h2>创作者记忆</h2>
        <button type="button" class="icon-btn" aria-label="关闭" @click="emit('close')">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
        </button>
      </header>

      <div class="memory-body">
        <aside class="memory-list">
          <button type="button" class="new-btn" @click="startNew">+ 新增记忆</button>
          <div v-if="loading" class="hint">加载中...</div>
          <div v-else-if="!memories.length" class="hint">暂无记忆</div>
          <ul v-else>
            <li
              v-for="memory in memories"
              :key="memory.id"
              :class="{ active: memory.id === draftId }"
              @click="select(memory)"
            >
              <div class="item-desc">{{ memory.description }}</div>
              <div class="item-meta">
                <span
                  v-for="platform in memory.platform"
                  :key="platform"
                  class="tag tag-platform"
                >{{ platform }}</span>
                <span class="tag" :class="memory.kind === 'performance' ? 'tag-performance' : 'tag-reference'">
                  {{ memory.kind === 'performance' ? '已验证' : '参考' }}
                </span>
              </div>
            </li>
          </ul>
        </aside>

        <section class="memory-editor">
          <div v-if="!editing" class="editor-placeholder">
            选择左侧条目编辑，或点击「新增记忆」
          </div>
          <template v-else>
            <label class="field">
              <span class="field-label">描述</span>
              <input v-model="draft.description" type="text" class="text-input" placeholder="一句话概括这条记忆" />
            </label>
            <label class="field">
              <span class="field-label">正文</span>
              <textarea v-model="draft.content" rows="6" class="text-area" placeholder="详细内容"></textarea>
            </label>
            <label class="field">
              <span class="field-label">平台（逗号分隔，留空表示通用）</span>
              <input v-model="draft.platform" type="text" class="text-input" placeholder="如 xiaohongshu, web-blog" />
            </label>
            <div class="field">
              <span class="field-label">可见角色</span>
              <div class="checkbox-row">
                <label v-for="opt in VISIBLE_TO_OPTIONS" :key="opt.value" class="checkbox">
                  <input
                    type="checkbox"
                    :checked="draft.visible_to.includes(opt.value)"
                    @change="toggleVisible(opt.value)"
                  />
                  <span>{{ opt.label }}</span>
                </label>
              </div>
            </div>
            <label class="field">
              <span class="field-label">类型</span>
              <select v-model="draft.kind" class="text-input">
                <option v-for="opt in KIND_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
              </select>
            </label>
            <div v-if="error" class="error-hint">{{ error }}</div>
            <div class="editor-actions">
              <button type="button" class="danger-btn" :disabled="saving || !draftId" @click="remove">删除</button>
              <button type="button" class="primary-btn" :disabled="saving" @click="save">保存</button>
            </div>
          </template>
        </section>
      </div>
    </div>
  </div>
  </Teleport>
</template>

<style scoped>
.memory-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--ch-z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ch-space-5);
  background: color-mix(in srgb, var(--ch-text) 40%, transparent);
}

.memory-panel {
  width: 100%;
  max-width: 720px;
  height: 80vh;
  display: flex;
  flex-direction: column;
  background: var(--ch-surface);
  border-radius: var(--ch-radius-panel);
  box-shadow: var(--ch-shadow-preview);
  overflow: hidden;
}

.memory-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--ch-space-3) var(--ch-space-4);
  border-bottom: 1px solid var(--ch-border);
}

.memory-header h2 {
  margin: 0;
  font-size: var(--ch-text-lg);
  font-weight: var(--ch-font-semibold);
  color: var(--ch-text);
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
  color: var(--ch-text-muted);
  cursor: pointer;
}

.icon-btn:hover {
  background: var(--ch-surface-2);
  color: var(--ch-text);
}

.icon-btn svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
}

.memory-body {
  flex: 1;
  display: flex;
  min-height: 0;
}

.memory-list {
  width: 264px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--ch-border);
  background: var(--ch-surface-2);
}

.new-btn {
  margin: var(--ch-space-3);
  padding: var(--ch-space-2) var(--ch-space-3);
  border: 1px dashed var(--ch-border-strong);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface);
  color: var(--ch-accent);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-medium);
  cursor: pointer;
}

.new-btn:hover {
  border-color: var(--ch-accent);
  background: var(--ch-accent-soft);
}

.memory-list ul {
  flex: 1;
  margin: 0;
  padding: 0 var(--ch-space-2) var(--ch-space-3);
  overflow-y: auto;
  list-style: none;
}

.memory-list li {
  padding: var(--ch-space-2) var(--ch-space-3);
  border-radius: var(--ch-radius-btn);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease);
}

.memory-list li:hover {
  background: var(--ch-surface);
}

.memory-list li.active {
  background: var(--ch-accent-soft);
}

.item-desc {
  font-size: var(--ch-text-sm);
  color: var(--ch-text);
  line-height: 1.5;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ch-space-1);
  margin-top: var(--ch-space-1);
}

.tag {
  padding: 2px var(--ch-space-2);
  border-radius: var(--ch-radius-btn);
  font-size: var(--ch-text-xs);
  line-height: 1.5;
}

.tag-platform {
  background: var(--ch-surface);
  border: 1px solid var(--ch-border);
  color: var(--ch-text-secondary);
}

.tag-performance {
  background: var(--ch-accent-soft);
  color: var(--ch-accent-soft-text);
}

.tag-reference {
  background: var(--ch-muted-gradient);
  color: var(--ch-text-secondary);
}

.hint {
  padding: var(--ch-space-3);
  color: var(--ch-text-muted);
  font-size: var(--ch-text-sm);
}

.memory-editor {
  flex: 1;
  padding: var(--ch-space-4);
  overflow-y: auto;
}

.editor-placeholder {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ch-text-muted);
  font-size: var(--ch-text-sm);
}

.field {
  display: flex;
  flex-direction: column;
  gap: var(--ch-space-2);
  margin-bottom: var(--ch-space-3);
}

.field-label {
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-medium);
  color: var(--ch-text-secondary);
}

.text-input,
.text-area {
  padding: var(--ch-space-2) var(--ch-space-3);
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface);
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  font-family: var(--ch-font-sans);
  line-height: 1.5;
}

.text-area {
  resize: vertical;
}

.text-input:focus,
.text-area:focus {
  outline: none;
  border-color: var(--ch-accent);
  box-shadow: var(--ch-shadow-focus);
}

.checkbox-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ch-space-3);
}

.checkbox {
  display: inline-flex;
  align-items: center;
  gap: var(--ch-space-1);
  font-size: var(--ch-text-sm);
  color: var(--ch-text-secondary);
  cursor: pointer;
}

.editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--ch-space-2);
  margin-top: var(--ch-space-3);
}

.primary-btn,
.danger-btn {
  padding: var(--ch-space-2) var(--ch-space-4);
  border: 0;
  border-radius: var(--ch-radius-btn);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-medium);
  cursor: pointer;
}

.primary-btn {
  background: var(--ch-accent);
  color: var(--ch-on-accent);
}

.primary-btn:hover:not(:disabled) {
  background: var(--ch-accent-hover);
}

.danger-btn {
  background: transparent;
  color: var(--ch-danger);
  border: 1px solid var(--ch-danger);
}

.danger-btn:hover:not(:disabled) {
  background: var(--ch-danger-soft);
}

.primary-btn:disabled,
.danger-btn:disabled {
  opacity: .5;
  cursor: not-allowed;
}

.error-hint {
  margin-bottom: var(--ch-space-2);
  padding: var(--ch-space-2) var(--ch-space-3);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-danger-soft);
  color: var(--ch-danger-text);
  font-size: var(--ch-text-xs);
}
</style>
