<script setup lang="ts">
import { onMounted, ref } from 'vue'

const stats = ref<any>(null)

async function load() {
  try {
    const resp = await fetch('/api/system/stats')
    stats.value = await resp.json()
  } catch {
    stats.value = null
  }
}

const statCards = [
  { label: '运行总数', value: () => stats.value?.total_runs ?? 0, suffix: '次' },
  { label: '治理成功率', value: () => stats.value?.success_rate ?? 0, suffix: '%' },
  { label: '发现问题数', value: () => stats.value?.issues_found ?? 0, suffix: '个' },
  { label: '平均运行耗时', value: () => stats.value?.avg_run_seconds ?? 0, suffix: '秒' },
]

onMounted(load)
</script>

<template>
  <div class="system-page">
    <div class="topbar">
      <div class="topbar-title">
        <span class="logo">系统状态</span>
        <span class="subtitle">平台可观测性指标（运行统计 + LLM 缓存命中）</span>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-row :gutter="12" class="stats-row">
      <el-col :span="6" v-for="c in statCards" :key="c.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ c.value() }}<span class="stat-suffix">{{ c.suffix }}</span></div>
          <div class="stat-label">{{ c.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="cache-card">
      <template #header>
        <span>LLM 结果缓存命中统计</span>
      </template>

      <el-row :gutter="12" v-if="stats?.cache">
        <el-col :span="6">
          <div class="cache-num">{{ stats.cache.hits }}</div>
          <div class="cache-label">命中次数</div>
        </el-col>
        <el-col :span="6">
          <div class="cache-num">{{ stats.cache.misses }}</div>
          <div class="cache-label">未命中次数</div>
        </el-col>
        <el-col :span="6">
          <div class="cache-num">{{ stats.cache.hit_rate }}%</div>
          <div class="cache-label">命中率</div>
        </el-col>
        <el-col :span="6">
          <div class="cache-num">{{ stats.cache.size }}/{{ stats.cache.max_size }}</div>
          <div class="cache-label">当前缓存条数（size / max）</div>
        </el-col>
      </el-row>

      <el-progress
        v-if="stats?.cache"
        :percentage="stats.cache.hit_rate"
        :stroke-width="14"
        class="cache-progress"
      />

      <div class="cache-desc">
        缓存 key = prompt 哈希，TTL 1 小时；同一数据重复治理直接命中，节省 token。重启后端后计数清零（进程内缓存）。
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.system-page {
  max-width: 1300px;
}
.topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: linear-gradient(135deg, #0b2447 0%, #1677ff 100%);
  color: #fff;
  border-radius: 8px;
  padding: 14px 20px;
  margin-bottom: 12px;
}
.topbar-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.logo {
  font-size: 20px;
  font-weight: 700;
}
.subtitle {
  font-size: 13px;
  color: rgba(255, 255, 255, 0.85);
}
.stats-row {
  margin-bottom: 12px;
}
.stat-card {
  text-align: center;
  padding: 6px 0;
}
.stat-value {
  font-size: 30px;
  font-weight: 700;
  color: #1677ff;
}
.stat-suffix {
  font-size: 14px;
  color: #909399;
  margin-left: 4px;
  font-weight: 400;
}
.stat-label {
  margin-top: 6px;
  font-size: 13px;
  color: #606266;
}
.cache-card {
  margin-bottom: 12px;
}
.cache-num {
  font-size: 26px;
  font-weight: 700;
  color: #303133;
  text-align: center;
}
.cache-label {
  margin-top: 6px;
  font-size: 13px;
  color: #606266;
  text-align: center;
}
.cache-progress {
  margin: 16px 0;
}
.cache-desc {
  font-size: 12px;
  color: #909399;
  line-height: 1.7;
}
</style>
