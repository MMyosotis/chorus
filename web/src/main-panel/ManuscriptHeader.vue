<script setup>
defineProps({
  date: { type: String, required: true },
  page: { type: String, required: true },
  kicker: { type: String, required: true },
  title: { type: String, required: true },
  deck: { type: String, required: true },
})
</script>

<template>
  <header class="manuscript-header">
    <div class="manuscript-dateline">
      <span>LIVE MANUSCRIPT</span>
      <span>{{ date }}</span>
      <span>P. {{ page }}</span>
    </div>
    <div class="manuscript-headline">
      <span class="manuscript-kicker">{{ kicker }}</span>
      <h1>{{ title }}</h1>
      <p>{{ deck }}</p>
      <div class="manuscript-byline"><span>文 / 稿搭编辑部</span><span>CITY NOTES · VOL. 07</span></div>
    </div>
  </header>
</template>

<style scoped>
.manuscript-header {
  position: relative;
  display: block;
  height: auto;
  flex-shrink: 0;
  margin: -20px calc(-1 * var(--ch-paper-pad)) 0;
  padding: 34px var(--ch-paper-pad) 0;
  border: 0;
  background: transparent;
  color: var(--ch-text);
}
.manuscript-dateline {
  height: auto;
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 10px;
  padding: 11px 2px;
  border-top: 6px double var(--ch-text);
  border-bottom: 1px solid rgba(27, 25, 22, .72);
  color: var(--ch-body);
  font: var(--ch-folio-weight) var(--ch-folio-size)/1 var(--ch-serif);
  font-variant-numeric: lining-nums tabular-nums;
  letter-spacing: var(--ch-folio-tracking);
}
.manuscript-dateline > span { font: inherit; letter-spacing: inherit; }
.manuscript-dateline span:nth-child(2) { text-align: center; }
.manuscript-dateline span:last-child { text-align: right; }
.manuscript-headline { position: relative; padding: 30px 0 28px; }
.manuscript-kicker { display: block; color: var(--ch-warm); font: 600 var(--t-micro)/1.2 var(--ch-serif); letter-spacing: .14em; text-transform: uppercase; }
.manuscript-headline h1 { max-width: 100%; margin: 8px 0 6px; color: var(--ch-text); font: 700 clamp(28px, 2.7vw, 40px)/1.32 var(--ch-serif); letter-spacing: .04em; overflow-wrap: anywhere; }
.manuscript-headline p { max-width: 640px; margin: 0; color: var(--ch-body); font: 500 14px/1.8 var(--ch-serif); letter-spacing: .025em; }
.manuscript-byline { display: flex; align-items: center; justify-content: space-between; gap: 18px; margin-top: 18px; padding-top: 9px; border-top: 1px solid rgba(27, 25, 22, .58); color: var(--ch-meta); font: 500 10px/1.4 var(--ch-serif); font-variant-numeric: lining-nums tabular-nums; letter-spacing: .08em; }
.manuscript-byline span:last-child { text-align: right; }
@media (max-width: 780px) {
  .manuscript-header { padding-inline: 28px; }
  .manuscript-dateline { grid-template-columns: 1fr auto; }
  .manuscript-dateline span:nth-child(2) { display: none; }
}
</style>
