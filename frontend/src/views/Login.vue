<script setup lang="ts">
// 登录页：默认管理员 admin / admin123（README 注明）
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()

const username = ref('admin')
const password = ref('')
const loading = ref(false)

async function login() {
  if (!username.value.trim() || !password.value) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: username.value.trim(), password: password.value }),
    })
    const data = await resp.json()
    if (!resp.ok) {
      ElMessage.error(data.detail || '登录失败')
      return
    }
    localStorage.setItem('dg_token', data.token)
    localStorage.setItem('dg_username', data.username)
    ElMessage.success(`欢迎回来，${data.username}`)
    router.push(String(route.query.redirect || '/dashboard'))
  } catch {
    ElMessage.error('登录失败（后端不可用）')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="hover">
      <div class="login-logo">
        <el-icon :size="30" color="#409eff"><DataAnalysis /></el-icon>
        <h2>DataGuard AI</h2>
        <p class="login-sub">企业数据治理 Agent 平台</p>
      </div>
      <el-form label-position="top" @submit.prevent="login">
        <el-form-item label="用户名">
          <el-input v-model="username" placeholder="请输入用户名" size="large" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="password" type="password" show-password placeholder="请输入密码" size="large" @keyup.enter="login" />
        </el-form-item>
        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="login">登 录</el-button>
      </el-form>
      <div class="login-tip">默认账号：admin / admin123（请部署后尽快修改）</div>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #f0f5ff 0%, #e8f0fe 100%);
}
.login-card {
  width: 380px;
  padding: 12px 8px;
}
.login-logo {
  text-align: center;
  margin-bottom: 20px;
}
.login-logo h2 {
  margin: 8px 0 2px;
  color: #1f2d3d;
}
.login-sub {
  color: #909399;
  font-size: 13px;
  margin: 0;
}
.login-tip {
  margin-top: 14px;
  text-align: center;
  font-size: 12px;
  color: #909399;
}
</style>
