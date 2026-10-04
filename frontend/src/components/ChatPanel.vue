<script setup>
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Promotion, Loading } from '@element-plus/icons-vue'
import { getMessages, sendChat, sendStream } from '../api/index.js'

const props = defineProps({ sessionId: String, title: String, modelReady: Boolean })
const emit = defineEmits(['busy', 'complete'])
const messages = ref([])
const input = ref('')
const mode = ref('auto')
const stream = ref(true)
const loading = ref(false)
const historyLoading = ref(true)
const historyError = ref('')
const messageList = ref(null)
let controller
const examples = [
  { label: '订单进度', message: '订单 DD20240001 现在是什么状态？' },
  { label: '天气与发货', message: '长沙今天天气怎么样，适合发货吗？' },
  { label: '精确计算', message: '帮我算一下 3874*239' },
  { label: '优惠券查询', message: 'WELCOME10 优惠券能用吗？' },
]
async function scroll() {
  await nextTick()
  if (messageList.value) messageList.value.scrollTop = messageList.value.scrollHeight
}
async function loadHistory() {
  historyLoading.value = true
  historyError.value = ''
  try { messages.value = (await getMessages(props.sessionId)).messages }
  catch (error) { historyError.value = error.message }
  finally { historyLoading.value = false; scroll() }
}
onMounted(loadHistory)
onUnmounted(() => controller?.abort())

async function send(retryText) {
  if (loading.value || historyLoading.value || historyError.value) return
  const text = typeof retryText === 'string' ? retryText : input.value.trim()
  if (!text || text.length > 2000) { ElMessage.warning('请输入1—2000个字符'); return }
  loading.value = true
  emit('busy', true)
  input.value = ''
  const user = { role: 'user', content: text, pending: true }
  const answer = { role: 'assistant', content: '', pending: true, tools_used: [] }
  messages.value.push(user, answer)
  const index = messages.value.length - 1
  await scroll()
  try {
    if (mode.value === 'chat' && stream.value) {
      controller = new AbortController()
      const timer = setTimeout(() => controller.abort(), 120000)
      try {
        await sendStream(text, props.sessionId, delta => {
          messages.value[index].content += delta
          scroll()
        }, controller.signal)
      } finally { clearTimeout(timer) }
    } else {
      const result = await sendChat(mode.value, text, props.sessionId)
      Object.assign(messages.value[index], {
        content: result.reply, tools_used: result.tools_used || [], route: result.route || mode.value,
      })
    }
    await loadHistory()
    emit('complete')
  } catch (error) {
    messages.value[index].failed = true
    messages.value[index].retryText = text
    messages.value[index].error = error.name === 'AbortError' ? '请求已中断或超时，请重试' : error.message
    input.value = text
    ElMessage.error(messages.value[index].error)
  } finally {
    loading.value = false
    emit('busy', false)
    scroll()
  }
}
function handleKey(event) {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing && event.keyCode !== 229) {
    event.preventDefault()
    send()
  }
}
</script>

<template>
  <section class="chat-panel">
    <header class="chat-header">
      <div><span class="eyebrow">SMARTCHAT / 对话</span><h2>{{ title }}</h2></div>
      <span class="service-state"><span class="status-dot" :class="{ warning: !modelReady }"></span>{{ modelReady ? '模型已配置' : '模型待配置' }}</span>
    </header>
    <div class="chat-toolbar">
      <el-radio-group v-model="mode" :disabled="loading" aria-label="对话模式">
        <el-radio-button value="auto">自动路由</el-radio-button>
        <el-radio-button value="chat">普通对话</el-radio-button>
        <el-radio-button value="agent">智能体</el-radio-button>
      </el-radio-group>
      <div class="stream-control"><el-switch v-model="stream" :disabled="loading || mode !== 'chat'" aria-label="流式输出" />
        <span>{{ mode === 'chat' ? '流式输出' : '流式仅适用于普通对话' }}</span></div>
    </div>
    <div ref="messageList" class="chat-body" aria-live="polite">
      <div v-if="historyError" class="history-error" role="alert">{{ historyError }} <el-button @click="loadHistory">重新加载</el-button></div>
      <div v-else-if="historyLoading" class="history-error">正在恢复对话…</div>
      <div v-else-if="!messages.length" class="conversation-start">
        <span class="brand-orb small">聊</span><h1>你好，有什么可以帮你？</h1>
        <p>自动选择回答方式，记住这一段对话。</p>
        <div class="example-grid"><button v-for="example in examples" :key="example.label" @click="input = example.message">
          <strong>{{ example.label }} <span>↗</span></strong><small>{{ example.message }}</small>
        </button></div>
      </div>
      <article v-for="(message, index) in messages" :key="message.id || `pending-${index}`" class="message" :class="message.role">
        <span class="avatar">{{ message.role === 'user' ? '我' : '聊' }}</span>
        <div class="message-content"><div class="message-label">{{ message.role === 'user' ? '你' : '智聊助手' }}
          <span v-if="message.route" class="route-tag">{{ message.route === 'agent' ? '工具回答' : '普通回答' }}</span></div>
          <div v-if="message.tools_used?.length" class="tool-tags"><span v-for="tool in message.tools_used" :key="tool">⚙ {{ tool }}</span></div>
          <div class="message-text" :class="{ incomplete: message.failed }">{{ message.content }}</div>
          <div v-if="loading && index === messages.length - 1 && !message.content" class="thinking"><el-icon class="is-loading"><Loading /></el-icon>正在处理你的问题…</div>
          <div v-if="message.failed" class="failed-message">{{ message.error }}<span>本轮未确认完成，请以刷新后的记录为准</span>
            <el-button size="small" :disabled="loading" @click="send(message.retryText)">重试</el-button></div>
        </div>
      </article>
    </div>
    <footer class="composer">
      <div v-if="!modelReady" class="model-warning">模型尚未配置，可以管理会话；对话需要本地 API Key。</div>
      <div class="composer-box"><el-input v-model="input" type="textarea" :rows="2" :maxlength="2000" resize="none"
        aria-label="消息内容" placeholder="输入问题，Enter 发送，Shift+Enter 换行" :disabled="loading || historyLoading || !!historyError" @keydown="handleKey" />
        <el-button type="primary" :icon="Promotion" :loading="loading" :disabled="!input.trim() || historyLoading || !!historyError" aria-label="发送消息" @click="send()">发送</el-button>
      </div>
      <div class="composer-note"><span>订单、天气与优惠券为教学模拟数据，请勿用于真实业务决策</span><span>{{ input.length }} / 2000</span></div>
    </footer>
  </section>
</template>
