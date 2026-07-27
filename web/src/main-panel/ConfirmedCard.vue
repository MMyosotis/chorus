<script setup>
import AgentAvatar from '../team-panel/AgentAvatar.vue'
import ScriptProof from './ScriptProof.vue'

defineProps({ task: { type: Object, required: true } })
</script>

<template>
  <section class="confirmed-card">
    <header class="confirmed-head">
      <AgentAvatar :agent-type="task.agent_type" status="finished" :size="40" />
    </header>
    <div class="confirmed-body">
      <div v-if="task.agent_type === 'idea'" class="candidates">
        <article
          v-for="candidate in task.artifacts?.candidates || []"
          :key="candidate.index"
          class="candidate"
          :class="{ selected: task.artifacts?.selected === candidate.index }"
        >
          <span>{{ task.artifacts?.selected === candidate.index ? '已采用' : '候选' }}</span>
          <h3>{{ candidate.title }}</h3>
          <p v-if="candidate.angle">{{ candidate.angle }}</p>
          <small v-if="candidate.reason">{{ candidate.reason }}</small>
        </article>
      </div>

      <ScriptProof
        v-else-if="task.agent_type === 'script'"
        :blocks="task.artifacts?.blocks || []"
        compact
      />

      <div v-else-if="task.agent_type === 'image'" class="images">
        <figure v-for="image in task.artifacts?.images || []" :key="image.url">
          <img :src="image.url" :alt="image.caption || ''">
          <figcaption>{{ image.caption }}</figcaption>
        </figure>
      </div>
    </div>
  </section>
</template>

<style scoped>
.confirmed-card { width: 100%; }
.confirmed-head { display: flex; align-items: center; margin-bottom: 8px; min-height: 40px; }
.confirmed-body {
  padding: var(--ch-space-4);
  background: var(--ch-surface);
  border: 1px solid var(--ch-border);
  border-radius: var(--ch-radius-card);
  box-shadow: var(--ch-shadow-sm);
  color: var(--ch-text);
  font-family: var(--ch-font-sans);
}
.candidates { display: grid; gap: 16px; }
.candidate { padding: 16px; border: 1px solid var(--ch-border); border-radius: var(--ch-radius-card); background: var(--ch-surface); }
.candidate.selected { border-color: var(--ch-accent); background: var(--ch-accent-soft); }
.candidate > span { color: var(--ch-text-muted); font-size: 12px; line-height: 1.5; }
.candidate.selected > span { color: var(--ch-accent-soft-text); }
.candidate h3 { margin: 8px 0 0; font-size: 16px; font-weight: 600; line-height: 1.5; }
.candidate p,
.candidate small { display: block; margin: 8px 0 0; color: var(--ch-text-secondary); font-size: 12px; line-height: 1.5; }
.candidate small { color: var(--ch-text-muted); }
.images { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.images figure { min-width: 0; margin: 0; }
.images img { display: block; width: 100%; aspect-ratio: 1 / 1; border-radius: var(--ch-radius-card); object-fit: cover; }
.images figcaption { margin-top: 8px; color: var(--ch-text-muted); font-size: 12px; line-height: 1.5; }
@media (max-width: 700px) {
  .images { grid-template-columns: 1fr; }
}
</style>
