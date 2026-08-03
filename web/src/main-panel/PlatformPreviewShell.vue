<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'
import { getSkillFile } from '../api.js'
import { renderPostCardHTML, renderInline, parseFrontMatter, firstImageUrl, firstParagraphText, imageUrls, plainTextPostContent } from '../composables/renderPostCard.js'
import { bindShell } from '../composables/bindShell.js'

const props = defineProps({
  card: { type: Object, required: true },
  previewRef: { type: String, default: '' },
  stylesheetRef: { type: String, default: '' },
})
const emit = defineEmits(['close'])

const previewHost = ref(null)
const error = ref('')
let previewRoot = null

function onPreviewClick(event) {
  const control = event.target instanceof Element ? event.target.closest('[data-preview-close]') : null
  if (control) {
    event.preventDefault()
    emit('close')
    return
  }
  const galleryControl = event.target instanceof Element ? event.target.closest('[data-preview-gallery-step], [data-preview-gallery-index]') : null
  if (galleryControl) setGalleryImage(galleryControl)
}

function setGalleryImage(control) {
  const gallery = control.closest('[data-preview-gallery]')
  if (!gallery) return
  const images = [...gallery.querySelectorAll('[data-preview-gallery-image]')]
  if (!images.length) return
  const activeIndex = Math.max(0, images.findIndex((image) => image.classList.contains('is-active')))
  const step = Number(control.dataset.previewGalleryStep)
  const requestedIndex = Number(control.dataset.previewGalleryIndex)
  const nextIndex = Number.isFinite(step)
    ? (activeIndex + step + images.length) % images.length
    : Number.isFinite(requestedIndex) ? Math.min(Math.max(requestedIndex, 0), images.length - 1) : activeIndex
  if (nextIndex === activeIndex) return
  const direction = Number.isFinite(step) ? Math.sign(step) : Math.sign(nextIndex - activeIndex)
  const suffix = direction >= 0 ? 'right' : 'left'
  const leavingSuffix = direction >= 0 ? 'left' : 'right'
  images.forEach((image) => image.classList.remove('is-active', 'is-entering-left', 'is-entering-right', 'is-leaving-left', 'is-leaving-right'))
  images[activeIndex].classList.add(`is-leaving-${leavingSuffix}`)
  images[nextIndex].classList.add('is-active', `is-entering-${suffix}`)
  gallery.querySelectorAll('[data-preview-gallery-index]').forEach((dot) => {
    dot.classList.toggle('is-active', Number(dot.dataset.previewGalleryIndex) === nextIndex)
  })
  const count = gallery.querySelector('[data-preview-gallery-count]')
  if (count) count.textContent = `${nextIndex + 1} / ${images.length}`
}

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

function renderPreview(html, css, card, format) {
  const fm = parseFrontMatter(card.markdown)
  const tags = Array.isArray(fm.tags) ? fm.tags : (fm.tags ? [fm.tags] : [])
  const galleryImages = imageUrls(card).map((url, index) => ({ url, index, number: index + 1, state: index === 0 ? ' is-active' : '' }))
  const summary = fm.summary || firstParagraphText(card.markdown)
  const slots = {
    title: renderInline(card.meta.title, format),
    author: fm.author || '内容作者',
    cover_url: firstImageUrl(card),
    summary: renderInline(summary, format),
    body: renderPostCardHTML(card, { format }),
    plain_body: plainTextPostContent(card),
    tags,
    has_tags: tags.length > 0,
    gallery_images: galleryImages,
    has_gallery_images: galleryImages.length > 0,
    has_no_gallery_images: galleryImages.length === 0,
    gallery_count: galleryImages.length || 1,
  }
  const bound = bindShell(html, slots)
  if (!previewHost.value) return
  if (!previewRoot || previewRoot.host !== previewHost.value) {
    previewRoot = previewHost.value.attachShadow({ mode: 'open' })
    previewRoot.addEventListener('click', onPreviewClick)
  }
  previewRoot.innerHTML = `<style>${css} :host { display: block; margin: 0; padding: 0; border-radius: inherit; overflow: hidden; } .preview-document { display: block; width: 100%; height: 100%; min-width: 0; min-height: 0; margin: 0 !important; padding: 0 !important; overflow: hidden; border-radius: inherit; }</style><div class="preview-document">${bound}</div>`
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
    await nextTick()
    renderPreview(html, css, props.card, format)
  } catch (e) {
    error.value = `平台外壳加载失败：${e.message}`
  }
}

onMounted(() => {
  load()
})
watch(() => [props.previewRef, props.stylesheetRef, props.card], load)
</script>

<template>
  <div v-if="error" class="platform-error">{{ error }}</div>
  <div
    v-else
    ref="previewHost"
    class="platform-preview-host"
  ></div>
</template>

<style scoped>
.platform-preview-host { display: block; width: 100%; height: 100%; min-width: 0; min-height: 0; overflow: hidden; border-radius: inherit; background: var(--ch-surface); }
.platform-error { display: grid; width: 100%; height: 100%; min-width: 0; min-height: 0; place-items: center; padding: 24px; color: var(--ch-danger); font-size: 14px; text-align: center; border: 1px dashed var(--ch-border-strong); }
</style>
