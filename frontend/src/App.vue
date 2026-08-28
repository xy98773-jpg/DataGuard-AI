<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)

// 当前生效模型（模型设置页保存后自动刷新）
const currentModel = ref('')
async function loadModel() {
  try {
    const resp = await fetch('/api/settings/llm')
    const d = await resp.json()
    currentModel.value = d.model ?? ''
  } catch {
    currentModel.value = ''
  }
}
onMounted(loadModel)
</script>

<template>
  <el-container class="app-layout">
    <el-aside width="220px" class="app-aside">
      <div class="app-logo">
        <el-icon :size="22"><DataAnalysis /></el-icon>
        <span>DataGuard AI</span>
      </div>
      <el-menu :default-active="activeMenu" router class="app-menu">
        <el-menu-item index="/dashboard">
          <el-icon><Odometer /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/workflow">
          <el-icon><Share /></el-icon>
          <span>治理工作台</span>
        </el-menu-item>
        <el-menu-item index="/issues">
          <el-icon><Warning /></el-icon>
          <span>问题列表</span>
        </el-menu-item>
        <el-menu-item index="/approval">
          <el-icon><Stamp /></el-icon>
          <span>审批中心</span>
        </el-menu-item>
        <el-menu-item index="/datasource">
          <el-icon><Connection /></el-icon>
          <span>数据源</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>模型设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <span class="app-header-title">企业数据治理 Agent 平台</span>
        <span v-if="currentModel" class="app-model-tag">
          <el-icon><Cpu /></el-icon>&nbsp;当前模型：{{ currentModel }}
        </span>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-layout {
  height: 100%;
}
.app-aside {
  background: #001529;
}
.app-logo {
  height: 60px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
}
.app-menu {
  border-right: none;
  background: #001529;
}
.app-menu :deep(.el-menu-item) {
  color: rgba(255, 255, 255, 0.72);
}
.app-menu :deep(.el-menu-item.is-active) {
  color: #fff;
  background: #1677ff;
}
.app-menu :deep(.el-menu-item:hover) {
  background: rgba(255, 255, 255, 0.08);
}
.app-header {
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.app-header-title {
  color: #606266;
  font-size: 14px;
}
.app-model-tag {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: #409eff;
  background: #ecf5ff;
  border: 1px solid #d9ecff;
  border-radius: 12px;
  padding: 2px 10px;
}
.app-main {
  padding: 16px;
}
</style>
