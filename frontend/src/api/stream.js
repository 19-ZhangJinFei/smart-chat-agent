/** SSE事件跨网络块缓冲，完整事件才进行JSON解析。 */
import { responseError } from './errors.js'

export function createSSEParser(onEvent) {
  let buffer = ''
  let completed = false
  let saved = {}
  return {
    push(text) {
      buffer += text
      while (true) {
        const delimiter = /\r?\n\r?\n/.exec(buffer)
        if (!delimiter) break
        const frame = buffer.slice(0, delimiter.index)
        buffer = buffer.slice(delimiter.index + delimiter[0].length)
        const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).replace(/^ /, '')).join('\n')
        if (!data) continue
        if (data === '[DONE]') { completed = true; continue }
        const payload = JSON.parse(data)
        if (payload.error) throw new Error(payload.error)
        if (payload.saved) saved = payload.saved
        if (typeof payload.delta === 'string') onEvent(payload.delta)
      }
    },
    finish() {
      if (!completed) throw new Error('回复未完成，请重试；未完成内容不会保存为成功记录')
      return saved
    },
  }
}

export async function consumeSSE(response, onDelta) {
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw responseError(response.status, error, response.headers.get('retry-after'))
  }
  if (!response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new Error('服务没有返回流式响应')
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  const parser = createSSEParser(onDelta)
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      parser.push(decoder.decode(value, { stream: true }))
    }
    parser.push(decoder.decode())
    return parser.finish()
  } catch (error) {
    await reader.cancel().catch(() => {})
    throw error
  } finally {
    reader.releaseLock()
  }
}
