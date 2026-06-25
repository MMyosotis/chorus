<script setup>
// 模型配置面板（Task 10 迁入 ModelOptionsBar 逻辑）。当前占位。
defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['update:open'])
function close() {
  emit('update:open', false)
}
</script>

<template>
  <div v-if="open" class="settings-panel">
    <div class="settings-header">
      <span>设置</span>
      <button class="settings-close" @click="close">关闭</button>
    </div>
    <div class="settings-body">模型配置待迁入（Task 10）</div>
  </div>
</template>

<style scoped>
.settings-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 420px;
  max-width: 90vw;
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(15, 23, 42, 0.18);
  z-index: 50;
  overflow: hidden;
}
.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid #e2e8f0;
  font-weight: 500;
  color: #1e293b;
}
.settings-close {
  border: none;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font-size: 14px;
}
.settings-body {
  padding: 18px;
  color: #64748b;
  font-size: 14px;
}
</style>
