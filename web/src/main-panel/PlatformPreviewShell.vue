<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { getSkillFile } from '../api.js'
import { renderPostCardHTML, renderInline } from '../composables/renderPostCard.js'
import { bindShell } from '../composables/bindShell.js'

const props = defineProps({
  card: { type: Object, required: true },
  previewRef: { type: String, default: '' },
  stylesheetRef: { type: String, default: '' },
})

const srcdoc = ref('')
const iframeHeight = ref(0)
const error = ref('')

function resolveResource(ref, fallbackPath) {
  const [name, ...path] = String(ref || '').split('/')
  return name && path.length
    ? { name, path: path.join('/') }
    : { name: 'web-blog', path: fallbackPath }
}

// 极简 key: value 行解析，不引 yaml 库
function parseYaml(text) {
  const cfg = {}
  for (const line of String(text || '').split('\n')) {
    const m = line.match(/^\s*(\w+)\s*:\s*(.+?)\s*$/)
    if (m) cfg[m[1]] = m[2]
  }
  return cfg
}

function buildSrcdoc(html, css, card, format) {
  const tags = card.tags || []
  const slots = {
    title: renderInline(card.title, format),
    cover_url: card.cover?.url || '',
    body: renderPostCardHTML(card, { format }),
    tags,
    has_tags: tags.length > 0,
  }
  const bound = bindShell(html, slots)
  const resizer = `<script>(function(){const send=()=>parent.postMessage({type:'platform-preview-height',h:document.body.scrollHeight},'*');new ResizeObserver(send).observe(document.body);send();})();<\/script>`
  return `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${bound}${resizer}</body></html>`
}

async function load() {
  error.value = ''
  const preview = resolveResource(props.previewRef, 'preview/desktop.html')
  const stylesheet = resolveResource(props.stylesheetRef, 'preview/desktop.css')
  try {
    const [html, css, yaml] = await Promise.all([
      getSkillFile(preview.name, preview.path),
      getSkillFile(stylesheet.name, stylesheet.path),
      getSkillFile(preview.name, 'platform.yaml'),
    ])
    const format = parseYaml(yaml).format || 'markdown'
    srcdoc.value = buildSrcdoc(html, css, props.card, format)
  } catch (e) {
    error.value = `平台外壳加载失败：${e.message}`
  }
}

function onMessage(event) {
  const data = event.data
  if (data && data.type === 'platform-preview-height' && typeof data.h === 'number') {
    iframeHeight.value = data.h
  }
}

onMounted(() => {
  window.addEventListener('message', onMessage)
  load()
})
onBeforeUnmount(() => window.removeEventListener('message', onMessage))
watch(() => [props.previewRef, props.stylesheetRef, props.card], load)
</script>

<template>
  <div class="platform-shell">
    <div v-if="error" class="platform-error">{{ error }}</div>
    <iframe
      v-else
      class="platform-iframe"
      :srcdoc="srcdoc"
      :style="{ height: iframeHeight ? iframeHeight + 'px' : '600px' }"
      sandbox="allow-scripts"
    ></iframe>
  </div>
</template>

<style scoped>
.platform-shell { width: 100%; }
.platform-iframe { width: 100%; border: 0; display: block; background: var(--ch-surface); }
.platform-error { padding: 24px; color: var(--ch-danger); font-size: 14px; text-align: center; border: 1px dashed var(--ch-border-strong); }
</style>
