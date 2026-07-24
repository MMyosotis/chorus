<script setup>
defineProps({
  sidebarOpen: { type: Boolean, default: false },
})
defineEmits(['toggle-sidebar', 'open-settings'])
</script>

<template>
  <nav class="nav-dock" aria-label="主导航">
    <button type="button" class="dock-item dock-logo" aria-label="稿搭">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3Z" />
        <path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15Z" />
      </svg>
    </button>

    <button
      type="button"
      class="dock-item"
      :class="{ active: sidebarOpen }"
      aria-label="会话"
      :aria-pressed="sidebarOpen"
      @click="$emit('toggle-sidebar')"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 5h16v11H8l-4 4V5Z" />
      </svg>
    </button>

    <button type="button" class="dock-item" aria-label="设置" @click="$emit('open-settings')">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 13a7.97 7.97 0 0 0 0-2l2-1.5-2-3.4-2.4.9a8 8 0 0 0-1.7-1L15 3.5H9l-.3 2.5a8 8 0 0 0-1.7 1l-2.4-.9-2 3.4L4.6 11a7.97 7.97 0 0 0 0 2l-2 1.5 2 3.4 2.4-.9a8 8 0 0 0 1.7 1l.3 2.5h6l.3-2.5a8 8 0 0 0 1.7-1l2.4.9 2-3.4-2-1.5Z" />
      </svg>
    </button>

    <div class="dock-spacer" aria-hidden="true"></div>

    <button type="button" class="dock-item dock-profile" aria-label="账户">
      <span>稿</span>
    </button>
  </nav>
</template>

<style scoped>
.nav-dock {
  width: 56px;
  flex: 0 0 56px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: var(--ch-space-2) 0;
  border-right: 1px solid var(--ch-border);
  background: transparent;
  font-family: var(--ch-font-sans);
}

.dock-item {
  width: 40px;
  height: 40px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: 10px;
  background: transparent;
  color: var(--ch-text-muted);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease),
    color var(--ch-duration-fast) var(--ch-ease);
}

.dock-item:hover {
  background: var(--ch-surface-3);
  color: var(--ch-text);
}

.dock-item svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.8;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.dock-logo {
  margin-bottom: var(--ch-space-2);
  border-radius: 12px;
  background: var(--ch-accent-gradient);
  color: var(--ch-on-accent);
}

.dock-logo:hover {
  background: var(--ch-accent-gradient);
  color: var(--ch-on-accent);
  opacity: .92;
}

.dock-logo svg {
  width: 22px;
  height: 22px;
  fill: currentColor;
  stroke: none;
}

.dock-item.active {
  background: var(--ch-accent-soft);
  color: var(--ch-accent-soft-text);
}

.dock-spacer {
  flex: 1;
}

.dock-profile {
  border-radius: 50%;
  background: var(--ch-accent-gradient);
  color: var(--ch-on-accent);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-bold);
}

.dock-profile:hover {
  background: var(--ch-accent-gradient);
  color: var(--ch-on-accent);
  opacity: .92;
}

.dock-profile span {
  line-height: 1;
}

@media (max-width: 780px) {
  .nav-dock { display: none; }
}
</style>
