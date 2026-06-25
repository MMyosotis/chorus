<script setup>
import { ref, onMounted, watch } from 'vue'
import { getModelLists, getOptions, setOptions } from './api.js'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['update:open'])

const chatModels = ref([])
const imageModels = ref([])
const chatModel = ref('')
const imageModel = ref('')
const webSearch = ref(true)
const loading = ref(true)
const error = ref('')
const saving = ref(false)

async function load() {
  loading.value = true
  error.value = ''
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
}

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

function close() {
  emit('update:open', false)
}

watch(() => props.open, (o) => { if (o) load() })
onMounted(load)
</script>

<template>
  <div v-if="open" class="settings-overlay" @click.self="close">
    <div class="settings-panel">
      <div class="settings-header">
        <span>设置</span>
        <button class="settings-close" @click="close">关闭</button>
      </div>
      <div class="settings-body">
        <div v-if="loading" class="s-hint">加载中...</div>
        <div v-else-if="error" class="s-error">{{ error }}</div>
        <template v-else>
          <label class="s-row">
            <span class="opt-label">对话模型</span>
            <select class="opt-select" :value="chatModel" :disabled="saving" @change="onChatModel">
              <option v-for="m in chatModels" :key="m.id" :value="m.id">{{ m.id }}</option>
            </select>
          </label>
          <label class="s-row">
            <span class="opt-label">生图模型</span>
            <select class="opt-select" :value="imageModel" :disabled="saving" @change="onImageModel">
              <option v-for="m in imageModels" :key="m.id" :value="m.id">{{ m.id }}</option>
            </select>
          </label>
          <label class="s-switch-row">
            <span class="opt-label">联网搜索</span>
            <span class="switch">
              <input type="checkbox" :checked="webSearch" :disabled="saving" @change="onWebSearch" />
              <span class="slider"></span>
            </span>
          </label>
          <div class="s-hint">子 Agent 按角色模型由后端 SUBAGENT_MODELS 配置，此处仅展示对话/生图模型与搜索开关。</div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-overlay {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.25);
  z-index: 40; display: flex; align-items: center; justify-content: center;
}
.settings-panel {
  width: 420px; max-width: 90vw; background: #fff; border-radius: 12px;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.18); overflow: hidden;
}
.settings-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid #e2e8f0; font-weight: 500; color: #1e293b;
}
.settings-close { border: none; background: transparent; color: #64748b; cursor: pointer; font-size: 14px; }
.settings-body { padding: 18px; display: flex; flex-direction: column; gap: 14px; }
.s-row { display: flex; align-items: center; justify-content: space-between; font-size: 14px; color: #334155; }
.s-switch-row { display: flex; align-items: center; justify-content: space-between; cursor: pointer; }
.opt-label { color: #64748b; font-size: 13px; user-select: none; }
.opt-select {
  appearance: none; -webkit-appearance: none;
  padding: 5px 28px 5px 10px; border: 1px solid #cbd5e1; border-radius: 8px;
  font-size: 13px; color: #334155; background: #fff; cursor: pointer;
}
.s-hint { font-size: 12px; color: #94a3b8; }
.s-error { font-size: 13px; color: #b91c1c; }

.switch { position: relative; display: inline-block; width: 36px; height: 20px; flex-shrink: 0; }
.switch input { opacity: 0; width: 0; height: 0; }
.slider {
  position: absolute; inset: 0; background: #cbd5e1; border-radius: 20px; transition: 0.2s; cursor: pointer;
}
.slider::before {
  content: ''; position: absolute; height: 16px; width: 16px; left: 2px; bottom: 2px;
  background: #fff; border-radius: 50%; transition: 0.2s;
}
.switch input:checked + .slider { background: linear-gradient(135deg, #6366f1, #818cf8); }
.switch input:checked + .slider::before { transform: translateX(16px); }
.switch input:disabled + .slider { opacity: 0.6; cursor: not-allowed; }
</style>
