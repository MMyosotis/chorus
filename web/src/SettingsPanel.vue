<script setup>
import { onMounted, ref } from 'vue'
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
const modelsLoading = ref(false)
const modelsError = ref('')
const saving = ref(false)

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
  } catch (e) {
    modelsError.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

function onChatModel(event) {
  chatModel.value = event.target.value
  persistOptions({ chat_model: event.target.value })
}

function onImageModel(event) {
  imageModel.value = event.target.value
  persistOptions({ image_model: event.target.value })
}

function onWebSearch(event) {
  webSearch.value = event.target.checked
  persistOptions({ web_search: event.target.checked })
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
})
</script>

<template>
  <section class="sidebar-inner settings-panel" aria-label="设置">
    <header class="settings-header">
      <h2>设置</h2>
      <button type="button" class="sidebar-collapse" aria-label="收起侧栏" title="收起侧栏" @click="emit('collapse')">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3.5" y="4" width="17" height="16" rx="3" />
          <path d="M10.5 4v16" />
        </svg>
      </button>
    </header>

    <div class="settings-body">
      <div v-if="modelsLoading" class="hint">加载中...</div>
      <div v-else-if="modelsError" class="error-hint">{{ modelsError }}</div>
      <template v-else>
        <div class="group-title">模型</div>
        <label class="setting-row">
          <div class="setting-label"><strong>对话模型</strong></div>
          <select class="opt-select" :value="chatModel" :disabled="saving" @change="onChatModel">
            <option v-for="model in chatModels" :key="model.id" :value="model.id">{{ model.id }}</option>
          </select>
        </label>
        <label class="setting-row">
          <div class="setting-label"><strong>生图模型</strong></div>
          <select class="opt-select" :value="imageModel" :disabled="saving" @change="onImageModel">
            <option v-for="model in imageModels" :key="model.id" :value="model.id">{{ model.id }}</option>
          </select>
        </label>
        <div class="group-title">功能</div>
        <div class="setting-row">
          <div class="setting-label"><strong>联网搜索</strong></div>
          <label class="switch">
            <input type="checkbox" :checked="webSearch" :disabled="saving" @change="onWebSearch" />
            <span class="slider"></span>
          </label>
        </div>
      </template>

      <div class="setting-row">
        <div class="setting-label">
          <strong>图像测试模式</strong>
          <small>开启后 generate_image 返回固定 URL，不调用真实 API。</small>
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
  padding: 32px 16px 16px;
  color: var(--ch-text);
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  padding: 0 0 var(--ch-space-3);
  border-bottom: 1px solid var(--ch-border);
}

.settings-header h2 {
  margin: 0;
  font-size: var(--ch-text-xl);
  font-weight: var(--ch-font-semibold);
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
  width: 22px;
  height: 22px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--ch-space-3) 0 0;
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

.opt-select {
  max-width: 190px;
  appearance: none;
  -webkit-appearance: none;
  padding: var(--ch-space-2) var(--ch-space-4) var(--ch-space-2) var(--ch-space-2);
  border: 1px solid var(--ch-border-strong);
  border-radius: var(--ch-radius-btn);
  background-color: var(--ch-surface);
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23475569' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  color: var(--ch-text-secondary);
  cursor: pointer;
  font-size: var(--ch-text-sm);
}

.opt-select:focus {
  outline: none;
  border-color: var(--ch-accent);
  box-shadow: var(--ch-shadow-focus);
}

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
