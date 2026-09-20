<script setup>
import { computed } from 'vue'
import AgentAvatar from '../team-panel/AgentAvatar.vue'
import ArtifactCard from './ArtifactCard.vue'

const props = defineProps({ product: { type: Object, required: true } })
const emit = defineEmits(['preview'])

const card = computed(() => ({
  markdown: props.product.markdown,
  meta: { title: props.product.title },
}))
</script>

<template>
  <section class="product-card">
    <header class="turn-head">
      <AgentAvatar agent-type="finalize" status="finished" :size="40" />
      <span class="role">排版官</span>
    </header>
    <ArtifactCard :card="card" finished @preview="emit('preview', card)" />
  </section>
</template>

<style scoped>
.product-card {
  width: 100%;
}

.turn-head {
  display: flex;
  min-height: 32px;
  align-items: center;
  gap: var(--ch-space-2);
  margin-bottom: var(--ch-space-3);
}

.turn-head :deep(.agent-avatar) {
  box-shadow: var(--ch-shadow-bubble);
}

.turn-head .role {
  color: var(--ch-text);
  font: 500 16px/1 var(--ch-font-sans);
  letter-spacing: 0;
}
</style>
