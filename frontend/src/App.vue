<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SessionSidebar from './components/SessionSidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
import { health, listSessions, createSession, renameSession, deleteSession } from './api/index.js'
import { useCooldown } from './composables/useCooldown.js'

const sessions = ref([])
const activeId = ref('')
const busy = ref(false)
const connecting = ref(true)
const modelReady = ref(false)
const weatherReady = ref(false)
const connectionError = ref('')
const retrySeconds = useCooldown()

async function refresh() {
  sessions.value = (await listSessions()).sessions
}
function select(id) {
  if (busy.value) return
  activeId.value = id
  localStorage.setItem('smartchat-active', id)
}
async function initialize() {
  connecting.value = true
  connectionError.value = ''
  try {
    const status = await health()
    modelReady.value = status.model_configured
    weatherReady.value = status.weather_configured
    await refresh()
    const remembered = localStorage.getItem('smartchat-active')
    select(sessions.value.find(s => s.id === remembered)?.id || sessions.value[0]?.id || '')
  } catch (error) {
    connectionError.value = error.message
  } finally { connecting.value = false }
}
onMounted(initialize)

async function create() {
  if (busy.value) return
  try {
    const result = await createSession()
    afterMessage(result.session)
    select(result.session.id)
  } catch (error) { ElMessage.error(error.message) }
}
async function rename(session) {
  if (busy.value) return
  try {
    const { value } = await ElMessageBox.prompt('为这段对话设置一个标题', '修改标题', {
      inputValue: session.title, inputValidator: value => value?.trim().length > 0 && value.trim().length <= 80,
      inputErrorMessage: '标题应为1—80个字符', confirmButtonText: '保存', cancelButtonText: '取消',
    })
    const result = await renameSession(session.id, value.trim())
    afterMessage(result.session)
  } catch (error) { if (error instanceof Error) ElMessage.error(error.message) }
}
async function remove(id) {
  if (busy.value) return
  try {
    await ElMessageBox.confirm('会删除这段对话及其全部记忆。', '删除对话', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await deleteSession(id)
    sessions.value = sessions.value.filter(s => s.id !== id)
    if (activeId.value === id) select(sessions.value[0]?.id || '')
    ElMessage.success('对话已删除')
  } catch (error) { if (error instanceof Error) ElMessage.error(error.message) }
}
function afterMessage(session) {
  if (!session) return
  const index = sessions.value.findIndex(s => s.id === session.id)
  if (index >= 0) sessions.value[index] = session
  else sessions.value.push(session)
  sessions.value.sort((a, b) => b.updated_at.localeCompare(a.updated_at) || a.id.localeCompare(b.id))
}
</script>

<template>
  <div class="app-layout">
    <SessionSidebar :sessions="sessions" :active-id="activeId" :busy="busy || connecting || retrySeconds > 0"
      @create="create" @select="select" @rename="rename" @delete="remove" />
    <main class="workspace">
      <div v-if="connectionError" class="connection-error" role="alert">
        {{ connectionError }} <el-button :disabled="retrySeconds > 0" @click="initialize">{{ retrySeconds ? `等待 ${retrySeconds} 秒` : '重新连接' }}</el-button>
      </div>
      <div v-else-if="connecting" class="welcome"><span class="eyebrow">SMARTCHAT</span><h1>正在连接智聊</h1></div>
      <ChatPanel v-else-if="activeId" :key="activeId" :session-id="activeId"
        :title="sessions.find(s => s.id === activeId)?.title || '新对话'" :model-ready="modelReady" :weather-ready="weatherReady"
        @busy="busy = $event" @complete="afterMessage" />
      <div v-else class="welcome">
        <span class="brand-orb">聊</span><span class="eyebrow">你的电商客服助手</span>
        <h1>从一个问题开始</h1><p>查订单、了解天气、精确计算，<br />让每一段对话都有记忆。</p>
        <el-button type="primary" size="large" @click="create">开始新对话</el-button>
        <small>订单与优惠券为模拟数据；天气联网检索，以来源为准</small>
      </div>
    </main>
  </div>
</template>
