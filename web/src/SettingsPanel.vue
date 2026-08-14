<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ChevronDown, PanelLeft } from '@lucide/vue'
import { getModelLists, getOptions, getTestMode, setOptions, setTestMode } from './api.js'

const emit = defineEmits(['collapse'])

const testModeEnabled = ref(false)
const testModeLoading = ref(false)
const testModeError = ref('')
const chatModels = ref([])
const imageModels = ref([])
const chatModel = ref('')
const imageModel = ref('')
const webSearch = ref(true)
const memoryEnabled = ref(true)
const modelsLoading = ref(false)
const modelsError = ref('')
const saving = ref(false)
const openModelMenu = ref(null)

async function refreshTestMode() {
  try {
    testModeEnabled.value = await getTestMode()
    testModeError.value = ''
  } catch (e) {
    testModeError.value = e.message || '请求失败'
  }
}

async function loadModels() {
  modelsLoading.value = true
  modelsError.value = ''
  try {
    const [lists, opts] = await Promise.all([getModelLists(), getOptions()])
    chatModels.value = lists.chat_models || []
    imageModels.value = lists.image_models || []
    chatModel.value = opts.chat_model
    imageModel.value = opts.image_model
    webSearch.value = !!opts.web_search
    memoryEnabled.value = opts.memory_enabled !== false
  } catch (e) {
    modelsError.value = e.message || '加载模型选项失败'
  } finally {
    modelsLoading.value = false
  }
}

async function persistOptions(patch) {
  if (saving.value) return
  saving.value = true
  modelsError.value = ''
  try {
    const opts = await setOptions(patch)
    chatModel.value = opts.chat_model
    imageModel.value = opts.image_model
    webSearch.value = !!opts.web_search
    memoryEnabled.value = opts.memory_enabled !== false
  } catch (e) {
    modelsError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

function toggleModelMenu(kind) {
  if (saving.value) return
  openModelMenu.value = openModelMenu.value === kind ? null : kind
}

function chooseModel(kind, modelId) {
  if (saving.value) return
  openModelMenu.value = null
  if (kind === 'chat') {
    chatModel.value = modelId
    persistOptions({ chat_model: modelId })
  } else {
    imageModel.value = modelId
    persistOptions({ image_model: modelId })
  }
}

function closeModelMenuOnOutsideClick(event) {
  if (!event.target.closest('.model-select')) openModelMenu.value = null
}

function closeModelMenuOnEscape(event) {
  if (event.key === 'Escape') openModelMenu.value = null
}

function onWebSearch(event) {
  webSearch.value = event.target.checked
  persistOptions({ web_search: event.target.checked })
}

function onMemory(event) {
  memoryEnabled.value = event.target.checked
  persistOptions({ memory_enabled: event.target.checked })
}

async function toggleTestMode() {
  testModeLoading.value = true
  testModeError.value = ''
  try {
    testModeEnabled.value = await setTestMode(!testModeEnabled.value)
  } catch (e) {
    testModeError.value = e.message || '切换失败'
  } finally {
    testModeLoading.value = false
  }
}

onMounted(() => {
  loadModels()
  refreshTestMode()
  document.addEventListener('click', closeModelMenuOnOutsideClick)
  document.addEventListener('keydown', closeModelMenuOnEscape)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', closeModelMenuOnOutsideClick)
  document.removeEventListener('keydown', closeModelMenuOnEscape)
})
</script>

<template>
  <section class="sidebar-inner settings-panel" aria-label="设置">
    <header class="settings-header">
      <h2>设置</h2>
      <button type="button" class="sidebar-collapse" aria-label="收起侧栏" title="收起侧栏" @click="emit('collapse')">
        <PanelLeft aria-hidden="true" />
      </button>
    </header>

    <div class="settings-body">
      <div v-if="modelsLoading" class="hint">加载中...</div>
      <div v-else-if="modelsError" class="error-hint">{{ modelsError }}</div>
      <template v-else>
        <div class="group-title">模型</div>
        <label class="setting-row model-row">
          <div class="setting-label"><strong>对话</strong></div>
          <div class="model-select">
            <button type="button" class="model-trigger" :aria-expanded="openModelMenu === 'chat'" aria-haspopup="listbox" :disabled="saving" @click="toggleModelMenu('chat')">
              <span>{{ chatModel }}</span>
              <ChevronDown aria-hidden="true" />
            </button>
            <Transition name="model-menu">
              <div v-if="openModelMenu === 'chat'" class="model-menu" role="listbox" aria-label="对话模型">
                <button v-for="model in chatModels" :key="model.id" type="button" role="option" :aria-selected="chatModel === model.id" :class="{ selected: chatModel === model.id }" @click="chooseModel('chat', model.id)"><span>{{ model.id }}</span></button>
              </div>
            </Transition>
          </div>
        </label>
        <label class="setting-row model-row">
          <div class="setting-label"><strong>生图</strong></div>
          <div class="model-select">
            <button type="button" class="model-trigger" :aria-expanded="openModelMenu === 'image'" aria-haspopup="listbox" :disabled="saving" @click="toggleModelMenu('image')">
              <span>{{ imageModel }}</span>
              <ChevronDown aria-hidden="true" />
            </button>
            <Transition name="model-menu">
              <div v-if="openModelMenu === 'image'" class="model-menu" role="listbox" aria-label="生图模型">
                <button v-for="model in imageModels" :key="model.id" type="button" role="option" :aria-selected="imageModel === model.id" :class="{ selected: imageModel === model.id }" @click="chooseModel('image', model.id)"><span>{{ model.id }}</span></button>
              </div>
            </Transition>
          </div>
        </label>
        <div class="group-title">功能</div>
        <div class="setting-row">
          <div class="setting-label"><strong>联网搜索</strong></div>
          <label class="switch">
            <input type="checkbox" :checked="webSearch" :disabled="saving" @change="onWebSearch" />
            <span class="slider"></span>
          </label>
        </div>
        <div class="setting-row">
          <div class="setting-label">
            <strong>作者记忆</strong>
          </div>
          <label class="switch">
            <input type="checkbox" :checked="memoryEnabled" :disabled="saving" @change="onMemory" />
            <span class="slider"></span>
          </label>
        </div>
      </template>

      <div class="setting-row">
        <div class="setting-label">
          <strong>图像测试</strong>
        </div>
        <label class="switch">
          <input type="checkbox" :checked="testModeEnabled" :disabled="testModeLoading" @change="toggleTestMode" />
          <span class="slider"></span>
        </label>
      </div>
      <div v-if="testModeError" class="error-hint">{{ testModeError }}</div>
    </div>

  </section>
</template>

<style scoped>
.settings-panel {
  height: 100%;
  min-width: 0;
  width: 100%;
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding: 24px 16px 16px;
  color: var(--ch-text);
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  min-height: 28px;
  margin-bottom: var(--ch-space-4);
  padding: 0;
}

.settings-header h2 {
  margin: 0;
  font-size: var(--ch-text-lg);
  font-weight: var(--ch-font-bold);
  letter-spacing: .3px;
}

.sidebar-collapse {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
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

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ch-space-3);
  padding: var(--ch-space-3) 0;
}

.setting-label {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: var(--ch-space-1);
}

.setting-label strong {
  color: var(--ch-text);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-medium);
}

.setting-label small,
.hint {
  color: var(--ch-text-muted);
  font-size: var(--ch-text-xs);
  line-height: 1.5;
}

.group-title {
  margin: 0 0 var(--ch-space-2);
  padding-top: var(--ch-space-3);
  border-top: 1px solid var(--ch-border);
  color: var(--ch-accent-active);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-semibold);
}

.group-title:first-child {
  padding-top: 0;
  border-top: 0;
}

.model-select {
  position: relative;
  width: 168px;
  min-width: 168px;
}

.model-row .setting-label { flex: 0 0 40px; }

.model-trigger {
  box-sizing: border-box;
  width: 100%;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ch-space-2);
  padding: 0 var(--ch-space-3);
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-btn);
  background: var(--ch-surface);
  color: var(--ch-text-secondary);
  font: inherit;
  font-size: var(--ch-text-sm);
  text-align: left;
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease), border-color var(--ch-duration-fast) var(--ch-ease);
}

.model-trigger > span,
.model-menu button > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-trigger > span { min-width: 0; flex: 1; }
.model-trigger:hover { border-color: var(--ch-text-faint); }
.model-trigger:focus-visible,.model-trigger[aria-expanded='true'] { outline: none; border-color: var(--ch-accent); background: color-mix(in srgb, var(--ch-accent) 3%, var(--ch-surface)); }
.model-trigger:disabled { cursor: not-allowed; opacity: .5; }
.model-trigger svg { width: 12px; height: 12px; flex: 0 0 auto; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.3; transition: transform var(--ch-duration-fast) var(--ch-ease); }
.model-trigger[aria-expanded='true'] svg { color: var(--ch-accent); transform: rotate(180deg); }
.model-menu { position: absolute; z-index: var(--ch-z-dropdown); top: calc(100% + var(--ch-space-1)); right: 0; left: 0; display: grid; gap: var(--ch-space-1); padding: var(--ch-space-2); border: 1px solid color-mix(in srgb, var(--ch-border-strong) 70%, white); border-radius: var(--ch-radius-list); background: var(--ch-surface); box-shadow: 0 6px 18px color-mix(in srgb, var(--ch-text) 7%, transparent), 0 1px 3px color-mix(in srgb, var(--ch-text) 4%, transparent); }
.model-menu button { min-width: 0; min-height: 40px; padding: 0 var(--ch-space-2); border: 0; border-radius: var(--ch-radius-btn); background: transparent; color: var(--ch-text-secondary); font: var(--ch-font-medium) var(--ch-text-sm)/1 var(--ch-font-sans); text-align: left; cursor: pointer; }.model-menu button > span { display: block; }.model-menu button.selected { color: var(--ch-accent); }.model-menu button:hover { background: var(--ch-accent-soft); color: var(--ch-accent); }.model-menu-enter-active,.model-menu-leave-active { transition: opacity var(--ch-duration-fast) var(--ch-ease), transform var(--ch-duration-fast) var(--ch-ease); }.model-menu-enter-from,.model-menu-leave-to { opacity: 0; transform: translateY(-4px); }

.switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  flex-shrink: 0;
}

.switch input {
  width: 0;
  height: 0;
  opacity: 0;
}

.slider {
  position: absolute;
  inset: 0;
  border-radius: var(--ch-radius-pill);
  background: var(--ch-border-strong);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease);
}

.slider::before {
  position: absolute;
  bottom: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--ch-surface);
  content: '';
  transition: transform var(--ch-duration-fast) var(--ch-ease);
}

input:checked + .slider { background: var(--ch-accent); }
input:checked + .slider::before { transform: translateX(16px); }
input:disabled + .slider { cursor: not-allowed; opacity: .6; }

.error-hint {
  margin-top: var(--ch-space-2);
  padding: var(--ch-space-2);
  border: 1px solid color-mix(in srgb, var(--ch-danger) 30%, var(--ch-border));
  border-radius: var(--ch-radius-btn);
  background: var(--ch-danger-soft);
  color: var(--ch-danger);
  font-size: var(--ch-text-xs);
}
</style>
