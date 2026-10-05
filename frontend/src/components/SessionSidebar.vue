<script setup>
import { Plus, Edit, Delete, ChatDotRound } from '@element-plus/icons-vue'
defineProps({ sessions: Array, activeId: String, busy: Boolean })
const emit = defineEmits(['create', 'select', 'rename', 'delete'])
</script>

<template>
  <aside class="sidebar">
    <div class="brand"><span class="brand-icon">聊</span><div><strong>智聊</strong><small>SMARTCHAT</small></div></div>
    <el-button class="new-chat" type="primary" :icon="Plus" :disabled="busy" @click="emit('create')">新建对话</el-button>
    <div class="section-label">对话记录 <span>{{ sessions.length }}</span></div>
    <nav class="session-list" aria-label="会话列表">
      <div v-for="session in sessions" :key="session.id" class="session-item" :class="{ active: activeId === session.id }">
        <button class="session-select" :disabled="busy" :aria-label="`打开对话 ${session.title}`" @click="emit('select', session.id)">
          <el-icon><ChatDotRound /></el-icon><span>{{ session.title }}</span>
        </button>
        <button class="session-action" :disabled="busy" :aria-label="`修改标题 ${session.title}`" @click="emit('rename', session)"><el-icon><Edit /></el-icon></button>
        <button class="session-action" :disabled="busy" :aria-label="`删除对话 ${session.title}`" @click="emit('delete', session.id)"><el-icon><Delete /></el-icon></button>
      </div>
      <p v-if="!sessions.length" class="sidebar-empty">你的第一段对话<br />将从这里开始</p>
    </nav>
    <div class="sidebar-note"><span class="status-dot"></span>记忆存储在本地数据库<p>天气联网检索 · 订单及优惠券为模拟</p></div>
    <footer>智聊 SmartChat <span>v1.0</span></footer>
  </aside>
</template>
