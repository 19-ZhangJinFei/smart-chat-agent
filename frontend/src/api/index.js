import axios from 'axios'
import { consumeSSE } from './stream.js'

const request = axios.create({ baseURL: '', timeout: 120000 })
request.interceptors.response.use(response => {
  if (response.data.code !== 0) throw new Error(response.data.message || '服务异常')
  return response.data.data
}, error => Promise.reject(new Error(error.response?.data?.message ||
  (error.code === 'ECONNABORTED' ? '请求超时，请稍后重试' : '无法连接服务，请检查后端是否启动'))))

export const health = () => request.get('/api/health')
export const listSessions = () => request.get('/api/sessions')
export const createSession = () => request.post('/api/sessions')
export const renameSession = (id, title) => request.patch(`/api/sessions/${id}`, { title })
export const deleteSession = id => request.delete(`/api/sessions/${id}`)
export const getMessages = id => request.get(`/api/sessions/${id}/messages`)
export const sendChat = (mode, message, id) => request.post({
  auto: '/api/smart/chat', chat: '/api/chat', agent: '/api/agent/chat',
}[mode], { message, session_id: id })

export async function sendStream(message, id, onDelta, signal) {
  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: id }), signal,
    })
    await consumeSSE(response, onDelta)
  } catch (error) {
    if (error instanceof TypeError) throw new Error('网络连接中断，请检查服务和网络后重试')
    if (error instanceof SyntaxError) throw new Error('流式响应格式异常，请刷新记录后重试')
    throw error
  }
}
