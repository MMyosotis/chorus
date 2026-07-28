<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import ChatWindow from '../main-panel/ChatWindow.vue'
import InputBar from '../main-panel/InputBar.vue'
import ManuscriptHeader from '../main-panel/ManuscriptHeader.vue'
import TeamPanel from '../team-panel/TeamPanel.vue'

const stages = [
  { id: 'conversation', label: '00 前期对话', type: 'conversation', phase: 0 },
  { id: 'thinking', label: '00A 主编 · 思考中', type: 'thinking', phase: 0 },
  { id: 'intent', label: '01 题旨签发', type: 'intent', phase: 0 },
  { id: 'idea-run', label: '02 选题 · 执行', type: 'run', phase: 1 },
  { id: 'idea-review', label: '03 选题 · 校样', type: 'review', phase: 1 },
  { id: 'script-run', label: '04 写稿 · 执行', type: 'run', phase: 2 },
  { id: 'script-review', label: '05 写稿 · 校样', type: 'review', phase: 2 },
  { id: 'image-run', label: '06 配图 · 执行', type: 'run', phase: 3 },
  { id: 'image-review', label: '07 配图 · 校样', type: 'review', phase: 3 },
  { id: 'finalize-run', label: '08 整合 · 执行', type: 'run', phase: 4 },
  { id: 'finalize-review', label: '09 整合 · 校样', type: 'review', phase: 4 },
  { id: 'complete', label: '10 完成交付', type: 'complete', phase: 5 },
  { id: 'recovery', label: '异常 · 配图恢复', type: 'recovery', phase: 3 },
  { id: 'option', label: '工具 · 选项征询', type: 'option', phase: 0 },
]

const currentIndex = ref(0)
const current = computed(() => stages[currentIndex.value])

function setStage(index) {
  currentIndex.value = Math.max(0, Math.min(stages.length - 1, Number(index)))
}

onMounted(() => {
  const id = location.hash.slice(1)
  const index = stages.findIndex((stage) => stage.id === id)
  if (index >= 0) currentIndex.value = index
})

const stageCardSelector = {
  thinking: '.status-card.thinking',
  intent: '.intent-confirm',
  run: '.running-panel',
  review: '.hil-card',
  complete: '.artifact-wrap:not(.review)',
  recovery: '.recovery-card',
}

watch(current, async (stage) => {
  history.replaceState(null, '', `${location.pathname}${location.search}#${stage.id}`)
  await nextTick()
  requestAnimationFrame(() => {
    const selector = stageCardSelector[stage.type]
    if (selector) document.querySelector(selector)?.scrollIntoView({ block: 'center' })
  })
})

const intentState = computed(() => ({
  intent_status: ['conversation', 'thinking'].includes(current.value.type) ? 'capturing' : current.value.type === 'intent' ? 'ready_to_confirm' : current.value.type === 'complete' ? 'confirmed' : 'dispatched',
  topic: '从一个人的停留体验切入城市空间，以观察和情绪组织内容，避开广告式卖点罗列。',
  platform: '小红书',
  format: '图文探店',
  style: '真实、克制、有观察感',
  image_count: 3,
  extra: {
    感受: '一个人安静停留，不赶时间',
    店铺: '由选题编辑选择合适的小众咖啡馆',
    叙事: '从停留体验切入，以空间观察和城市情绪组织内容',
    禁用: '不使用硬广表达，不堆砌卖点',
  },
  progress_percent: ['conversation', 'thinking'].includes(current.value.type) ? 58 : 100,
}))

function art(label, from, to) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 600"><defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop stop-color="${from}"/><stop offset="1" stop-color="${to}"/></linearGradient><filter id="n"><feTurbulence baseFrequency=".72" numOctaves="3" stitchTiles="stitch"/><feColorMatrix values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 .08 0"/></filter></defs><rect width="480" height="600" fill="url(#g)"/><rect width="480" height="600" filter="url(#n)" opacity=".55"/><path d="M70 420h340M105 120v300M375 150v270" stroke="#f8f5ed" stroke-opacity=".45" stroke-width="2"/><text x="240" y="300" text-anchor="middle" fill="#fffdf8" font-family="serif" font-size="25" letter-spacing="5">${label}</text></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

const ideaTask = {
  id: 'audit-idea', agent_type: 'idea', status: 'finished', title: '城市里，藏着一杯慢下来的时间',
  artifacts: { selected: 1, candidates: [
    { index: 1, title: '城市里，藏着一杯慢下来的时间', angle: '从时间感切入空间体验', reason: '以“慢下来的一小时”串联街道、空间、咖啡与人的状态，避开广告式卖点罗列。' },
    { index: 2, title: '不赶时间的人，会在这里坐到天黑', angle: '从店内人物切入生活观察', reason: '叙述不同陌生人在空间中的安静共处。' },
    { index: 3, title: '一条老街，三种咖啡香', angle: '以散步路线组织轻攻略', reason: '信息密度更高，适合偏实用的收藏型读者。' },
  ] },
}

const scriptBlocks = [
  { kind: 'title', text: '城市里，藏着一杯慢下来的时间' },
  { kind: 'heading', text: '不是每一家咖啡馆，都急着被看见' },
  { kind: 'paragraph', text: '拐进梧桐路最安静的那一段，车声像被旧墙挡在身后。木门没有醒目的招牌，只贴着一张写了今日豆单的小纸。我原本只想喝完就走，最后却在靠窗的位置坐了整个下午。' },
  { kind: 'heading', text: '一杯手冲，把下午还给自己' },
  { kind: 'paragraph', text: '热水落下时，柑橘和烤坚果的气味慢慢散开。这里没有催促拍照的布景，也没有必须完成的打卡动作；你可以看书，也可以什么都不做。' },
  { kind: 'quote', text: '没有网红打卡的喧嚣，却有着独属于自己的节奏。' },
  { kind: 'paragraph', text: '离开时，城市仍然很快。但那一个小时像被单独装订起来。' },
]
const scriptTask = { id: 'audit-script', agent_type: 'script', status: 'finished', title: '最终文案 VERSION 01', artifacts: { char_count: 936, blocks: scriptBlocks } }

const images = [
  { url: art('OLD STREET', '#8f7861', '#3e4d47'), caption: '老街远景，人物刚进入画面' },
  { url: art('POUR OVER', '#7c523f', '#c0a77f'), caption: '手冲近景与木桌纹理' },
  { url: art('WINDOW', '#506a69', '#c9bda6'), caption: '窗边独坐，侧面自然光' },
]
const imageTask = { id: 'audit-image', agent_type: 'image', status: 'finished', title: '三帧视觉叙事方案', artifacts: { images } }
const finalTask = {
  id: 'audit-finalize', agent_type: 'finalize', status: 'finished', title: '小红书图文交付主稿',
  artifacts: {
    cover: images[0], title: '城市里，藏着一杯慢下来的时间',
    sections: [
      { kind: 'paragraph', text: scriptBlocks[2].text },
      { kind: 'paragraph', text: scriptBlocks[4].text },
      { kind: 'quote', text: '真正让人想再来的，也许不是某一种风味，而是这里允许你暂时不回应世界。' },
    ],
    tags: ['#上海咖啡馆', '#一个人也很好', '#城市漫游', '#松弛感'],
    summary: '最终成品已统一标题、正文、图片顺序与发布信息。',
    meta: {
      preview_ref: 'web-blog/preview/desktop.html',
      stylesheet_ref: 'web-blog/preview/desktop.css',
    },
  },
}

const taskTemplates = [ideaTask, scriptTask, imageTask, finalTask]
const roleNames = ['选题官', '文案编辑', '视觉编辑', '汇总编辑']
const stageKicker = computed(() => {
  if (['conversation', 'thinking'].includes(current.value.type)) return 'CONVERSATION'
  if (current.value.type === 'intent') return 'STORY COMMISSION'
  if (current.value.type === 'complete') return 'FINAL COPY'
  if (current.value.type === 'recovery') return '视觉编辑 · RECOVERY'
  if (current.value.type === 'option') return 'OPTION PROMPT · DEV'
  return `${roleNames[current.value.phase - 1]} · ${current.value.type === 'review' ? 'PROOF' : 'WORKING'}`
})
const runningCopy = [
  ['正在比较城市情绪、空间体验与平台传播角度', '正在形成候选方向', 0, 3, '个候选'],
  ['正在把已确认选题写成完整小红书稿件', '正在润色第二段', 824, 0, ''],
  ['正在根据定稿规划并生成三张连续叙事配图', '正在生成 FIG. 02', 0, 1, '张完成'],
  ['正在统一标题、正文、配图顺序与发布信息', '正在检查图文节奏', 0, 76, '%'],
]

const graph = computed(() => {
  if (current.value.phase === 0) return null
  const tasks = taskTemplates.map((template, index) => {
    let status = 'pending'
    if (current.value.type === 'complete') status = 'finished'
    else if (current.value.type === 'recovery') status = index < 2 ? 'finished' : index === 2 ? 'failed' : 'pending'
    else if (index + 1 < current.value.phase) status = 'finished'
    else if (index + 1 === current.value.phase) status = current.value.type === 'run' ? 'running' : 'awaiting_confirm'
    return { ...template, status }
  })
  return { active: tasks.some((task) => ['running', 'awaiting_confirm'].includes(task.status)), tasks }
})

const discussion = [
  { id: 'audit-user-1', role: 'user', content: '我想做一篇适合小红书发布的城市咖啡馆探店，整体不要太像广告。', created_at: 1784088240 },
  { id: 'audit-assistant-1', role: 'assistant', content: '可以。我会把重点放在真实体验和城市情绪上。最想突出哪种感受？是否已有具体店铺？需要多少张配图？', created_at: 1784088248, thinking: { state: 'idle' }, tools: { state: 'idle', items: [] } },
  { id: 'audit-user-2', role: 'user', content: '突出一个人待着的松弛感，具体店铺你来定，配三张图。', created_at: 1784088360 },
]
const commissionNote = { id: 'audit-assistant-2', role: 'assistant', content: '明白。我把这一轮沟通整理成了选题签发单。你可以直接签发，也可以退回补充；签发后我再建立创作计划。', created_at: 1784088540, thinking: { state: 'idle' }, tools: { state: 'idle', items: [] } }
const planNote = { ...commissionNote, content: '题旨已经签发，我已按签发内容建立四阶段创作计划。', tools: { state: 'idle', items: [{ name: 'create_plan', display: '建立创作计划', content: '已建立选题、写稿、配图、整合四个阶段', duration_ms: 620 }] } }

function activeTask() {
  const phase = current.value.phase
  const base = taskTemplates[phase - 1]
  if (!base) return null
  if (current.value.type === 'run') {
    const [aside, activity, chars, units, label] = runningCopy[phase - 1]
    return { ...base, status: 'running', progress: { aside, activity_kind: phase === 3 ? 'drawing' : 'thinking', activity_line: activity, activity_started_at: Date.now() / 1000 - 8, composing_chars: chars, composing_units: units, composing_label: label } }
  }
  if (current.value.type === 'review') return { ...base, status: 'awaiting_confirm' }
  return base
}

const optionScenarios = [
  {
    headline: '场景 A · 3 选项 + 允许自定义',
    intro: '默认形态：三个候选方向，用户也可补充自己的想法。',
    prompt: {
      question: '这一篇想从哪个角度切入城市咖啡馆？',
      allow_custom: true,
      options: [
        { signal: '0', label: '一个人的松弛感', description: '从独处体验切入，突出安静停留与城市情绪。' },
        { signal: '1', label: '一条街三种咖啡香', description: '以散步路线组织轻攻略，信息密度更高。' },
        { signal: '2', label: '手冲与豆单', description: '聚焦冲煮细节与风味，偏专业向读者。' },
      ],
    },
  },
  {
    headline: '场景 B · 4 选项 + 不可自定义',
    intro: '四选一封闭征询：用户只能从给定方向里挑。',
    prompt: {
      question: '配图整体走哪种视觉调性？',
      allow_custom: false,
      options: [
        { signal: '0', label: '胶片质感', description: '低饱和、颗粒感，偏怀旧。' },
        { signal: '1', label: '清新明亮', description: '高调、自然光，偏日常。' },
        { signal: '2', label: '暗调情绪', description: '低调、窗边侧光，偏氛围。' },
        { signal: '3', label: '极简留白', description: '大量负空间，偏杂志感。' },
      ],
    },
  },
  {
    headline: '场景 C · 长文案换行',
    intro: '问题与描述都偏长，检查换行与溢出。',
    prompt: {
      question: '如果读者只能记住一句话，你希望这篇内容留给他的是哪种感受？是安静、是被理解、还是想立刻出发？',
      allow_custom: true,
      options: [
        { signal: '0', label: '安静地被城市接住', description: '强调一个人在陌生空间里找到节奏的踏实感，适合情绪向选题。' },
        { signal: '1', label: '被一种风味说服', description: '强调专业度与风味记忆，适合偏攻略与种草的读者。' },
        { signal: '2', label: '想立刻出门走走', description: '强调行动召唤与场景代入，适合引流与传播向内容。' },
      ],
    },
  },
]

function optionMessages() {
  const items = []
  for (const scenario of optionScenarios) {
    items.push({ id: `audit-option-intro-${scenario.prompt.options.length}`, role: 'assistant', content: `**${scenario.headline}**\n\n${scenario.intro}`, thinking: { state: 'idle' }, tools: { state: 'idle', items: [] } })
    items.push({ id: `audit-option-card-${scenario.prompt.options.length}`, kind: 'option', role: 'assistant', prompt: scenario.prompt })
  }
  return items
}

const messages = computed(() => {
  if (current.value.type === 'conversation') return discussion
  if (current.value.type === 'thinking') {
    return [
      ...discussion,
      {
        id: 'audit-assistant-thinking',
        role: 'assistant',
        content: '',
        created_at: 1784088420,
        thinking: { state: 'running' },
        tools: { state: 'idle', items: [] },
      },
    ]
  }
  if (current.value.type === 'intent') return [...discussion, commissionNote, { id: 'audit-intent', kind: 'intent-confirm', role: 'assistant', state: intentState.value }]
  if (current.value.type === 'option') return optionMessages()
  const items = [
    ...discussion,
    planNote,
    { id: 'audit-intent', kind: 'intent-confirm', role: 'assistant', state: intentState.value },
  ]
  const confirmed = current.value.type === 'complete' ? taskTemplates.slice(0, 3) : current.value.type === 'recovery' ? taskTemplates.slice(0, 2) : taskTemplates.slice(0, Math.max(0, current.value.phase - 1))
  for (const task of confirmed) {
    items.push({ id: `audit-confirmed-${task.id}`, kind: 'confirmed', role: 'assistant', task })
  }
  if (current.value.type === 'run') items.push({ id: `audit-${current.value.id}`, kind: 'running', role: 'assistant', task: activeTask() })
  if (current.value.type === 'review') items.push({ id: `audit-${current.value.id}`, kind: 'hil', role: 'assistant', task: activeTask() })
  if (current.value.type === 'complete') items.push({ id: 'audit-complete', kind: 'postcard', role: 'assistant', task: finalTask })
  if (current.value.type === 'recovery') items.push({ id: 'audit-recovery', kind: 'recovery', role: 'assistant', task: { ...imageTask, status: 'failed', error: '第 2 张图生成超时；已完成的题旨、选题、完整文案和第 1 张图片均已保留。' } })
  return items
})
</script>

<template>
  <div class="audit-shell" :data-audit-stage="current.id">
    <aside class="audit-nav">
      <div class="audit-mast"><strong>全流程校样</strong><small>FLOW PROOF · DEV</small></div>
      <label for="audit-stage">审阅阶段</label>
      <select id="audit-stage" :value="currentIndex" @change="setStage($event.target.value)">
        <option v-for="(stage, index) in stages" :key="stage.id" :value="index">{{ stage.label }}</option>
      </select>
      <div class="audit-steps">
        <button v-for="(stage, index) in stages" :key="stage.id" type="button" :class="{ current: index === currentIndex }" :aria-current="index === currentIndex ? 'step' : undefined" @click="setStage(index)">
          <span>{{ String(index).padStart(2, '0') }}</span>{{ stage.label.replace(/^\d+\s*/, '') }}
        </button>
      </div>
      <div class="audit-pager"><button type="button" :disabled="currentIndex === 0" @click="setStage(currentIndex - 1)">← 上一步</button><button type="button" :disabled="currentIndex === stages.length - 1" @click="setStage(currentIndex + 1)">下一步 →</button></div>
    </aside>

    <main class="audit-main">
      <article class="audit-paper manuscript-paper">
        <ChatWindow :messages="messages" :streaming="current.type === 'thinking'" :session-id="'ui-flow-review'" :session-updated-at="1784088240" :intent-state="intentState">
          <template #scroll-header>
            <ManuscriptHeader :kicker="stageKicker" title="城市小众咖啡馆探店" />
          </template>
        </ChatWindow>
        <InputBar :streaming="current.type === 'thinking'" :has-active-task="current.type === 'run'" :awaiting-confirm="current.type === 'intent'" />
      </article>
    </main>

    <TeamPanel :graph="graph" :intent-state="intentState" />
  </div>
</template>

<style scoped>
:global(body:has(.audit-shell)) { overflow-y: auto; }
.audit-shell { display: flex; width: 100%; min-height: 100dvh; overflow: visible; align-items: flex-start; background: var(--ch-canvas); }
.audit-nav { position: sticky; top: 0; width: var(--ch-rail); height: 100dvh; flex: 0 0 var(--ch-rail); display: flex; flex-direction: column; padding: var(--ch-space-4) var(--ch-space-3) var(--ch-space-3); border-right: 1px solid var(--ch-border); background: var(--ch-canvas); }
.audit-mast { display: grid; gap: var(--ch-space-2); margin-bottom: var(--ch-space-4); }.audit-mast strong { font: 700 24px/1.25 var(--ch-font-sans); letter-spacing: .08em; }.audit-mast small { color: var(--ch-text-muted); font: 600 12px/1.2 var(--ch-font-sans); letter-spacing: .16em; }
.audit-nav label { margin-bottom: var(--ch-space-2); color: var(--ch-accent); font: 600 12px/1.2 var(--ch-font-sans); letter-spacing: .08em; }
.audit-nav select { width: 100%; height: 40px; padding: 0 var(--ch-space-2); border: 1px solid var(--ch-border-strong); border-radius: var(--ch-radius-btn); background: var(--ch-surface); color: var(--ch-text); font: 500 12px/1 var(--ch-font-sans); }
.audit-steps { flex: 1; min-height: 0; margin-top: var(--ch-space-4); overflow-y: auto; border-top: 1px solid var(--ch-border-strong); }.audit-steps button { width: 100%; min-height: 40px; display: grid; grid-template-columns: 24px 1fr; align-items: center; padding: 0 var(--ch-space-1); border: 0; border-bottom: 1px dashed var(--ch-border); background: transparent; color: var(--ch-text-secondary); text-align: left; font: 500 12px/1.3 var(--ch-font-sans); cursor: pointer; transition: color .18s ease, background-color .18s ease; }.audit-steps button span { color: var(--ch-text-muted); font-variant-numeric: tabular-nums; }.audit-steps button.current { background: var(--ch-accent-soft); color: var(--ch-accent-soft-text); font-weight: 600; }.audit-steps button.current span { color: var(--ch-accent-soft-text); }
.audit-pager { display: grid; grid-template-columns: 1fr 1fr; gap: var(--ch-space-2); margin-top: var(--ch-space-3); }.audit-pager button { min-width: 0; min-height: 32px; padding: 0 var(--ch-space-2); border: 1px solid var(--ch-border-strong); border-radius: var(--ch-radius-btn); background: transparent; color: var(--ch-text-secondary); font: 600 12px/1 var(--ch-font-sans); cursor: pointer; }.audit-pager button:disabled { opacity: .3; cursor: default; }
.audit-main { flex: 1; min-width: 0; padding: var(--ch-space-4); overflow: visible; }
.audit-paper :deep(.chat-window) { flex: 0 0 auto; overflow: visible; scrollbar-gutter: auto; }
.audit-paper :deep(.input-bar) {
  position: fixed;
  left: calc(var(--ch-rail) + (100% - var(--ch-rail) - var(--ch-right-rail)) / 2);
  transform: translateX(-50%);
  width: calc(100% - var(--ch-rail) - var(--ch-right-rail) - 48px);
}
.audit-shell > :deep(.team-panel) { position: sticky; top: 0; height: 100dvh; }
@media(min-width:781px) and (max-width:1180px){
  .audit-nav{width:var(--ch-rail);flex-basis:var(--ch-rail)}
  .audit-shell > :deep(.team-panel){display:none}
  .audit-paper :deep(.input-bar){
    left:calc((100% + var(--ch-rail)) / 2);
    width:calc(100% - var(--ch-rail) - 48px);
  }
}
@media(max-width:780px){
  .audit-nav{display:none}
  .audit-main{padding:0}
  .audit-paper{width:100%}
}
</style>
