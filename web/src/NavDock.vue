<script setup>
defineProps({
  sidebarOpen: { type: Boolean, default: false },
  settingsOpen: { type: Boolean, default: false },
})
defineEmits(['toggle-sidebar', 'open-settings'])
</script>

<template>
  <nav class="nav-dock" aria-label="主导航">
    <button type="button" class="dock-logo" aria-label="稿搭">
      <svg viewBox="0 0 18 18" aria-hidden="true">
        <defs>
          <linearGradient id="dockLogoGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stop-color="var(--ch-on-ink)" />
            <stop offset="100%" stop-color="var(--ch-on-ink)" />
          </linearGradient>
        </defs>
        <path d="M8 1.5C8 5.25 10.75 9 13.5 9C10.75 9 8 12.75 8 16.5C8 12.75 5.25 9 2.5 9C5.25 9 8 5.25 8 1.5Z" fill="url(#dockLogoGrad)" />
        <path d="M14.5 11.5C14.5 12.75 15.4 14 16.3 14C15.4 14 14.5 15.25 14.5 16.5C14.5 15.25 13.6 14 12.7 14C13.6 14 14.5 12.75 14.5 11.5Z" fill="var(--ch-on-ink)" />
      </svg>
    </button>

    <div class="dock-nav">
      <button
        type="button"
        class="dock-item"
        :class="{ active: sidebarOpen && !settingsOpen }"
        aria-label="会话"
        :aria-pressed="sidebarOpen && !settingsOpen"
        @click="$emit('toggle-sidebar')"
      >
        <svg viewBox="0 0 24 24"><path d="M8 18c-2.8 0-5-2.3-5-5.1V10c0-3.3 2.7-6 6-6h6c3.3 0 6 2.7 6 6v2.9c0 2.8-2.2 5.1-5 5.1h-1.4L12 20l-2.6-2H8Z"></path><circle cx="9" cy="11" r=".8"></circle><circle cx="15" cy="11" r=".8"></circle></svg>
      </button>

      <button type="button" class="dock-item" aria-label="模版">
        <svg viewBox="0 0 24 24"><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"></path><path d="m4.5 7.8 7.5 4.3 7.5-4.3M12 12.1V21"></path></svg>
      </button>

      <button type="button" class="dock-item" aria-label="团队">
        <svg viewBox="0 0 24 24"><circle cx="8.3" cy="8" r="3"></circle><circle cx="16.5" cy="9" r="2.4"></circle><path d="M2.8 20c.3-4 2-6 5.5-6s5.3 2 5.6 6M13.7 15.3c3.8-.4 6 1.2 6.5 4.7"></path></svg>
      </button>

    </div>

    <div class="dock-spacer" aria-hidden="true"></div>

    <div class="dock-footer">
      <button
        type="button"
        class="dock-item"
        :class="{ active: settingsOpen }"
        aria-label="设置"
        :aria-pressed="settingsOpen"
        @click="$emit('open-settings')"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 13a7.97 7.97 0 0 0 0-2l2-1.5-2-3.4-2.4.9a8 8 0 0 0-1.7-1L15 3.5H9l-.3 2.5a8 8 0 0 0-1.7 1l-2.4-.9-2 3.4L4.6 11a7.97 7.97 0 0 0 0 2l-2 1.5 2 3.4 2.4-.9a8 8 0 0 0 1.7 1l.3 2.5h6l.3-2.5a8 8 0 0 0 1.7-1l2.4.9 2-3.4-2-1.5Z" />
        </svg>
      </button>

      <button type="button" class="dock-item dock-profile" aria-label="账户">
        <span>稿</span>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.nav-dock {
  width: var(--ch-nav-rail);
  flex: 0 0 var(--ch-nav-rail);
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 24px 0 16px;
  border-right: 1px solid var(--ch-ink);
  background: var(--ch-ink);
  font-family: var(--ch-font-sans);
}

.dock-logo {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  margin-bottom: 32px;
  border: 0;
  background: transparent;
  cursor: default;
}

.dock-logo svg {
  width: 36px;
  height: 36px;
  stroke: none;
}

.dock-nav {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
  width: 100%;
}

.dock-item {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: var(--ch-radius-icon-btn);
  background: transparent;
  color: color-mix(in srgb, var(--ch-on-ink) 72%, transparent);
  cursor: pointer;
  transition: background var(--ch-duration-fast) var(--ch-ease),
    color var(--ch-duration-fast) var(--ch-ease);
}

.dock-item:hover {
  background: var(--ch-ink-hover);
  color: var(--ch-on-ink);
}

.dock-item.active {
  background: var(--ch-accent);
  color: var(--ch-on-accent);
}

.dock-item svg {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.7;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.dock-spacer {
  flex: 1;
}

.dock-footer {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 24px;
}

.dock-profile {
  background: var(--ch-accent);
  color: var(--ch-on-accent);
  font-size: var(--ch-text-sm);
  font-weight: var(--ch-font-semibold);
}

.dock-profile:hover {
  background: var(--ch-accent-hover);
  color: var(--ch-on-accent);
}

.dock-profile span {
  line-height: 1;
}

@media (max-width: 780px) {
  .nav-dock { display: none; }
}
</style>
