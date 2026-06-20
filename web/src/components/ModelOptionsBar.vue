<script setup>
import { ref, onMounted } from 'vue'
import { getModelLists, getOptions, setOptions } from '../api.js'

const chatModels = ref([])
const imageModels = ref([])
const chatModel = ref('')
const imageModel = ref('')
const webSearch = ref(true)
const loading = ref(true)
const error = ref('')
const saving = ref(false)

onMounted(async () => {
  try {
    const [lists, opts] = await Promise.all([getModelLists(), getOptions()])
    chatModels.value = lists.chat_models || []
    imageModels.value = lists.image_models || []
    chatModel.value = opts.chat_model
    imageModel.value = opts.image_model
    webSearch.value = !!opts.web_search
  } catch (e) {
    error.value = e.message || '加载模型选项失败'
  } finally {
    loading.value = false
  }
})

async function persist(patch) {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    const opts = await setOptions(patch)
    chatModel.value = opts.chat_model
    imageModel.value = opts.image_model
    webSearch.value = !!opts.web_search
  } catch (e) {
    error.value = e.message || '保存失败'
  } finally {
    saving.value = false
  }
}

function onChatModel(e) {
  chatModel.value = e.target.value
  persist({ chat_model: e.target.value })
}

function onImageModel(e) {
  imageModel.value = e.target.value
  persist({ image_model: e.target.value })
}

function onWebSearch(e) {
  webSearch.value = e.target.checked
  persist({ web_search: e.target.checked })
}
</script>

<template>
  <div class="options-bar">
    <div class="options-inner">
      <template v-if="loading">
        <span class="options-hint">加载模型选项…</span>
      </template>
      <template v-else>
        <label class="opt-field">
          <span class="opt-label">对话模型</span>
          <select
            class="opt-select"
            :value="chatModel"
            :disabled="saving"
            @change="onChatModel"
          >
            <option v-for="m in chatModels" :key="m.id" :value="m.id">{{ m.id }}</option>
          </select>
        </label>

        <label class="opt-field">
          <span class="opt-label">生图模型</span>
          <select
            class="opt-select"
            :value="imageModel"
            :disabled="saving"
            @change="onImageModel"
          >
            <option v-for="m in imageModels" :key="m.id" :value="m.id">{{ m.id }}</option>
          </select>
        </label>

        <label class="opt-switch">
          <span class="opt-label">联网搜索</span>
          <span class="switch">
            <input type="checkbox" :checked="webSearch" :disabled="saving" @change="onWebSearch" />
            <span class="slider"></span>
          </span>
        </label>
      </template>
      <span v-if="error" class="options-error">{{ error }}</span>
    </div>
  </div>
</template>

<style scoped>
.options-bar {
  flex: 1;
  min-width: 0;
}

.options-inner {
  display: flex;
  align-items: center;
  gap: 14px;
  flex-wrap: wrap;
}

.options-hint {
  color: #94a3b8;
  font-size: 12px;
}

.opt-field {
  display: flex;
  align-items: center;
  gap: 6px;
}

.opt-label {
  color: #64748b;
  font-size: 12px;
  white-space: nowrap;
  user-select: none;
}

.opt-select {
  appearance: none;
  -webkit-appearance: none;
  padding: 5px 28px 5px 10px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 10px;
  font-size: 13px;
  font-family: inherit;
  color: #334155;
  background: rgba(255, 255, 255, 0.86)
    url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%236366f1' stroke-width='3' stroke-linecap='round' stroke-linejoin='round'><polyline points='6 9 12 15 18 9'/></svg>")
    no-repeat right 8px center;
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, background 0.2s;
}

.opt-select:hover:not(:disabled) {
  border-color: rgba(129, 140, 248, 0.5);
}

.opt-select:focus {
  outline: none;
  border-color: rgba(129, 140, 248, 0.7);
  box-shadow: 0 0 0 3px rgba(129, 140, 248, 0.14);
}

.opt-select:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.opt-switch {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

/* iOS-style switch（与 ConsolePanel 一致） */
.switch {
  position: relative;
  display: inline-block;
  width: 36px;
  height: 20px;
  flex-shrink: 0;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  inset: 0;
  background: #cbd5e1;
  border-radius: 20px;
  transition: 0.2s;
  cursor: pointer;
}

.slider::before {
  content: '';
  position: absolute;
  height: 16px;
  width: 16px;
  left: 2px;
  bottom: 2px;
  background: #fff;
  border-radius: 50%;
  transition: 0.2s;
}

.switch input:checked + .slider {
  background: linear-gradient(135deg, #6366f1, #818cf8);
}

.switch input:checked + .slider::before {
  transform: translateX(16px);
}

.switch input:disabled + .slider {
  opacity: 0.6;
  cursor: not-allowed;
}

.options-error {
  color: #b91c1c;
  font-size: 12px;
}
</style>
