<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import SessionSidebar from './components/SessionSidebar.vue'
import ChatPanel from './components/ChatPanel.vue'
import { health, listSessions, createSession, renameSession, deleteSession } from './api/index.js'

const sessions = ref([])
const activeId = ref('')
const busy = ref(false)
const connecting = ref(true)
const modelReady = ref(false)
const connectionError = ref('')

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
    await refresh()
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
    await renameSession(session.id, value.trim())
    await refresh()
  } catch (error) { if (error instanceof Error) ElMessage.error(error.message) }
}
async function remove(id) {
  if (busy.value) return
  try {
    await ElMessageBox.confirm('会删除这段对话及其全部记忆。', '删除对话', {
      confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning',
    })
    await deleteSession(id)
    await refresh()
    if (activeId.value === id) select(sessions.value[0]?.id || '')
    ElMessage.success('对话已删除')
  } catch (error) { if (error instanceof Error) ElMessage.error(error.message) }
}
async function afterMessage() {
  try { await refresh() } catch (error) { ElMessage.error(error.message) }
}
</script>

<template>
  <div class="app-layout">
    <SessionSidebar :sessions="sessions" :active-id="activeId" :busy="busy || connecting"
      @create="create" @select="select" @rename="rename" @delete="remove" />
    <main class="workspace">
      <div v-if="connectionError" class="connection-error" role="alert">
        {{ connectionError }} <el-button @click="initialize">重新连接</el-button>
      </div>
      <div v-else-if="connecting" class="welcome"><span class="eyebrow">SMARTCHAT</span><h1>正在连接智聊</h1></div>
      <ChatPanel v-else-if="activeId" :key="activeId" :session-id="activeId"
        :title="sessions.find(s => s.id === activeId)?.title || '新对话'" :model-ready="modelReady"
        @busy="busy = $event" @complete="afterMessage" />
      <div v-else class="welcome">
        <span class="brand-orb">聊</span><span class="eyebrow">你的电商客服助手</span>
        <h1>从一个问题开始</h1><p>查订单、了解天气、精确计算，<br />让每一段对话都有记忆。</p>
        <el-button type="primary" size="large" @click="create">开始新对话</el-button>
        <small>订单、天气与优惠券为教学模拟数据</small>
      </div>
    </main>
  </div>
</template>
