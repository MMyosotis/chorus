// 悬浮显示完整文本：仅当内容被截断（出现省略号）时才弹出。
// 浮层挂到 body 用 position:fixed，绕开文本元素 overflow:hidden 的裁剪。
let tipEl = null

function ensureTip() {
  if (tipEl) return tipEl
  tipEl = document.createElement('div')
  tipEl.className = 'ch-tip'
  document.body.appendChild(tipEl)
  return tipEl
}

function show(el, text) {
  if (!text) return
  const truncated = el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight
  if (!truncated) return
  const tip = ensureTip()
  tip.textContent = text
  tip.classList.add('visible')
  const rect = el.getBoundingClientRect()
  const margin = 8
  const tw = tip.offsetWidth
  const th = tip.offsetHeight
  let left = rect.left
  let top = rect.bottom + 6
  if (left + tw > window.innerWidth - margin) left = window.innerWidth - tw - margin
  if (left < margin) left = margin
  if (top + th > window.innerHeight - margin) top = rect.top - th - 6
  tip.style.left = `${Math.round(left)}px`
  tip.style.top = `${Math.round(top)}px`
}

function hide() {
  tipEl?.classList.remove('visible')
}

export const vTip = {
  mounted(el, binding) {
    el._tipText = binding.value ?? ''
    el._tipEnter = () => show(el, el._tipText)
    el._tipLeave = hide
    el.addEventListener('mouseenter', el._tipEnter)
    el.addEventListener('mouseleave', el._tipLeave)
  },
  updated(el, binding) {
    el._tipText = binding.value ?? ''
  },
  unmounted(el) {
    el.removeEventListener('mouseenter', el._tipEnter)
    el.removeEventListener('mouseleave', el._tipLeave)
    hide()
  },
}
