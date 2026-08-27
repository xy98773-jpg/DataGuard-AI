<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const activeMenu = computed(() => route.path)
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
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <span class="app-header-title">企业数据治理 Agent 平台</span>
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
}
.app-header-title {
  color: #606266;
  font-size: 14px;
}
.app-main {
  padding: 16px;
}
</style>
