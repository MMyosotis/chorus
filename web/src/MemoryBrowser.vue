<script setup>
import { ref, watch } from 'vue'
import { PanelLeft, Plus } from '@lucide/vue'
import { listMemories } from './api.js'

const props = defineProps({
  refreshKey: { type: Number, default: 0 },
  selectedId: { type: String, default: null },
})
const emit = defineEmits(['collapse', 'edit', 'create'])

const memories = ref([])
const loading = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    memories.value = await listMemories()
  } catch (e) {
    error.value = e.message || '加载记忆失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.refreshKey, load, { immediate: true })
</script>

<template>
  <section class="sidebar-inner memory-browser" aria-label="记忆">
    <header class="sidebar-header">
      <h2 class="sidebar-title">记忆</h2>
      <button type="button" class="sidebar-collapse" aria-label="收起侧栏" title="收起侧栏" @click="emit('collapse')">
        <PanelLeft aria-hidden="true" />
      </button>
    </header>
    <button type="button" class="new-memory" @click="emit('create')"><Plus aria-hidden="true" /><span>添加记忆</span></button>
    <div class="memory-list">
      <p v-if="loading" class="hint">加载中…</p>
      <p v-else-if="error" class="error-hint">{{ error }}</p>
      <p v-else-if="!memories.length" class="hint">暂无记忆</p>
      <button v-for="memory in memories" v-else :key="memory.id" type="button" :class="['memory-item', memory.id === selectedId ? 'active' : null]" @click="emit('edit', memory)">
        <strong>{{ memory.description }}</strong>
        <small>{{ memory.kind === 'performance' ? '已验证' : '参考' }}<template v-if="memory.platform.length"> · {{ memory.platform.join('、') }}</template></small>
      </button>
    </div>
  </section>
</template>

<style scoped>
.memory-browser { min-width: 0; flex: 1; flex-direction: column; padding: 24px 16px 16px; }.sidebar-header { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; min-height: 28px; margin-bottom: var(--ch-space-4); }.sidebar-title { margin: 0; color: var(--ch-text); font-size: var(--ch-text-lg); font-weight: var(--ch-font-bold); letter-spacing: .3px; }.sidebar-collapse { width: 32px; height: 32px; display: inline-flex; align-items: center; justify-content: center; flex-shrink: 0; padding: 0; border: 0; border-radius: var(--ch-radius-btn); background: transparent; color: var(--ch-text-faint); cursor: pointer; }.sidebar-collapse:hover { background: var(--ch-surface-2); color: var(--ch-text); }.sidebar-collapse svg { width: 20px; height: 20px; transform: translateX(6px); fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }.new-memory svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
.new-memory { display: flex; align-items: center; justify-content: center; gap: var(--ch-space-2); width: 100%; height: 44px; margin-bottom: var(--ch-space-5); padding: 0 var(--ch-space-3); border: 1px dashed var(--ch-border-strong); border-radius: var(--ch-radius-bar-btn); background: var(--ch-surface); color: var(--ch-accent); font-size: var(--ch-text-sm); font-weight: var(--ch-font-medium); }.new-memory:hover { border-color: var(--ch-accent); background: var(--ch-accent-soft); }
.memory-list { min-height: 0; flex: 1; display: flex; flex-direction: column; gap: var(--ch-space-1); overflow-y: auto; scrollbar-width: none; }.memory-list::-webkit-scrollbar { display: none; }.memory-item { width: 100%; display: flex; flex-direction: column; gap: var(--ch-space-1); padding: var(--ch-space-2); border: 0; border-radius: var(--ch-radius-list); background: transparent; color: var(--ch-text); text-align: left; cursor: pointer; }.memory-item:hover { background: var(--ch-surface-2); }.memory-item.active { background: var(--ch-accent-soft-gradient); }.memory-item strong { overflow: hidden; font-size: var(--ch-text-sm); font-weight: var(--ch-font-semibold); text-overflow: ellipsis; white-space: nowrap; }.memory-item.active strong { color: var(--ch-accent); font-size: var(--ch-text-sm); }.memory-item small { overflow: hidden; color: var(--ch-text-faint); font-size: var(--ch-text-xs); text-overflow: ellipsis; white-space: nowrap; }.hint,.error-hint { margin: 0; padding: var(--ch-space-3) var(--ch-space-2); color: var(--ch-text-muted); font-size: var(--ch-text-sm); }.error-hint { color: var(--ch-danger-text); }
@media (max-height: 800px) { .new-memory { margin-bottom: var(--ch-space-3); } }
</style>
