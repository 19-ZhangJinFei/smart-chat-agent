/** 将来源URL显示为安全链接；正文仍用Vue文本插值，不执行HTML。 */
export function splitLinks(text = '') {
  const parts = []
  const pattern = /https?:\/\/[^\s<>"'\[\]()（），。；！？]+/g
  let start = 0
  for (const match of text.matchAll(pattern)) {
    const url = match[0].replace(/[.,;]+$/, '')
    try {
      if (!new URL(url).hostname) continue
    } catch { continue }
    if (match.index > start) parts.push({ text: text.slice(start, match.index) })
    parts.push({ text: url, url })
    start = match.index + url.length
  }
  if (start < text.length) parts.push({ text: text.slice(start) })
  return parts
}
