<script setup>
// 创作团队角色栏（Task 5 填充角色卡列表）。当前占位。
defineProps({ graph: { type: Object, default: null } })
</script>

<template>
  <aside class="team-panel">
    <div class="team-placeholder">创作团队栏（Task 5 填充）</div>
  </aside>
</template>

<style scoped>
.team-panel {
  width: 260px;
  flex-shrink: 0;
  border-left: 1px solid rgba(226, 232, 240, 0.55);
  background: rgba(255, 255, 255, 0.5);
  overflow-y: auto;
}
.team-placeholder {
  padding: 24px 16px;
  color: #94a3b8;
  font-size: 13px;
  text-align: center;
}
</style>
