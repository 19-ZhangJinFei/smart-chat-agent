import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createSSEParser, consumeSSE } from '../src/api/stream.js'

test('中文跨事件块和CRLF不丢数据', () => {
  let text = ''
  const parser = createSSEParser(delta => { text += delta })
  const raw = 'data: {"delta":"你好"}\r\n\r\ndata: {"delta":"世界"}\n\ndata: [DONE]\n\n'
  for (const char of raw) parser.push(char)
  parser.finish()
  assert.equal(text, '你好世界')
})
test('服务器错误和缺少DONE不能算成功', () => {
  const parser = createSSEParser(() => {})
  assert.throws(() => parser.push('data: {"error":"失败"}\n\n'), /失败/)
  assert.throws(() => createSSEParser(() => {}).finish(), /未完成/)
})
test('HTTP错误先于读取流处理', async () => {
  await assert.rejects(consumeSSE(new Response(JSON.stringify({ message: '请求过于频繁' }), {
    status: 429, headers: { 'Content-Type': 'application/json' },
  }), () => {}), /过于频繁/)
})
test('中文UTF8字节拆分正确解码', async () => {
  const bytes = new TextEncoder().encode('data: {"delta":"中文"}\n\ndata: [DONE]\n\n')
  const stream = new ReadableStream({ start(controller) {
    for (const byte of bytes) controller.enqueue(new Uint8Array([byte]))
    controller.close()
  } })
  let text = ''
  await consumeSSE(new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } }), delta => { text += delta })
  assert.equal(text, '中文')
})
