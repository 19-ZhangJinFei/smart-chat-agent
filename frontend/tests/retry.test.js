import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ApiError, responseError, createCooldown } from '../src/api/errors.js'
import { beginTurn, settleTurn } from '../src/api/turn.js'
import { consumeSSE } from '../src/api/stream.js'

test('HTTP和SSE限流保留状态和服务器等待时间，拒绝不等同于未知完成状态', async () => {
  const failure = responseError(429, { message: '请求过于频繁', data: { retry_after: 17 } })
  assert.equal(failure.status, 429)
  assert.equal(failure.retryAfter, 17)
  assert.equal(failure.notAccepted, true)
  assert.equal(new ApiError('网络断开').notAccepted, false)
  await assert.rejects(consumeSSE(new Response(JSON.stringify({ message: '请求过于频繁' }), {
    status: 429, headers: { 'Retry-After': '9' },
  }), () => {}), error => error.status === 429 && error.retryAfter === 9 && error.notAccepted)
})

test('冷却窗口不会被重复点击延长，到期后可以重试', () => {
  let now = 100
  const state = createCooldown(() => now)
  state.block(5)
  now += 2001
  assert.equal(state.remaining(), 3)
  assert.throws(() => state.ensureAvailable(), error => error.status === 429 && error.retryAfter === 3)
  now = 5100
  assert.equal(state.remaining(), 0)
  assert.doesNotThrow(() => state.ensureAvailable())
})

test('重试只替换被拒绝的占位，不删除已保存或状态未知的历史', () => {
  const messages = [{ id: 1, role: 'user', content: '计算1/0' },
    { id: 2, role: 'assistant', content: '失败' }]
  let index = beginTurn(messages, '计算1/0')
  Object.assign(messages[index], { failed: true, notAccepted: true, retryText: '计算1/0' })
  index = beginTurn(messages, '计算1/0')
  assert.equal(messages.length, 4)
  assert.equal(messages[0].id, 1)
  const saved = { messages: [{ id: 3, role: 'user', content: '计算1/0' },
    { id: 4, role: 'assistant', content: '不能除零' }] }
  settleTurn(messages, index, saved)
  assert.deepEqual(messages.map(m => m.id), [1, 2, 3, 4])
  index = beginTurn(messages, '状态未知')
  Object.assign(messages[index], { failed: true, notAccepted: false, retryText: '状态未知' })
  beginTurn(messages, '状态未知')
  assert.equal(messages.length, 8)
})

test('流式保存确认要等待DONE，跨块元数据可以恢复完整问答', async () => {
  const saved = { session: { id: 'a', history_version: 1 }, messages: [
    { id: 1, role: 'user', content: '你好' }, { id: 2, role: 'assistant', content: '中文' },
  ] }
  const encoded = new TextEncoder().encode(`data: {"delta":"中文"}\n\ndata: ${JSON.stringify({ saved })}\n\ndata: [DONE]\n\n`)
  const body = new ReadableStream({ start(controller) {
    for (const byte of encoded) controller.enqueue(new Uint8Array([byte]))
    controller.close()
  } })
  assert.deepEqual(await consumeSSE(new Response(body, {
    headers: { 'Content-Type': 'text/event-stream' },
  }), () => {}), saved)
  await assert.rejects(consumeSSE(new Response(`data: ${JSON.stringify({ saved })}\n\n`, {
    headers: { 'Content-Type': 'text/event-stream' },
  }), () => {}), /未完成/)
})

test('缺失或异常Retry-After使用有界的默认等待时间', () => {
  assert.equal(responseError(429, {}).retryAfter, 60)
  assert.equal(responseError(429, {}, 'not-a-date').retryAfter, 60)
  assert.equal(responseError(429, {}, '1.5').retryAfter, 2)
})
