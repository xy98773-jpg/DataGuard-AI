<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const datasets = ref<any[]>([])

async function load() {
  try {
    const resp = await fetch('/api/dataset/list')
    datasets.value = (await resp.json()).datasets ?? []
  } catch {
    /* ignore */
  }
}

onMounted(load)

const quickStart = [
  { step: '1', title: '准备数据', desc: '上传 CSV / Excel / JSON 文件，或接入 MySQL / PostgreSQL / 网页数据源' },
  { step: '2', title: '启动治理', desc: '在「治理工作台」点击「开始治理」，Agent 自动完成画像、质检、规划' },
  { step: '3', title: '查看图谱与问题', desc: '工作流图谱实时展示执行进度，点击节点查看每个 Agent 的真实推理与工具调用' },
  { step: '4', title: '审批与验证', desc: '高风险操作在「审批中心」人工确认后执行，最终输出前后质量评分与治理报告' },
]
</script>

<template>
  <div class="dashboard-page">
    <el-card shadow="never" class="hero">
      <h1 class="hero-title">DataGuard AI — 企业数据治理 Agent 平台</h1>
      <p class="hero-desc">
        由 <b>Agent 负责理解与决策</b>、<b>Workflow 负责流程控制</b>、<b>工具负责确定性执行</b>、
        <b>校验器负责结果验证</b>、<b>风险引擎负责安全控制</b>、<b>追踪系统负责全过程可观测</b>，
        实现从数据理解、质量检测、治理规划到安全执行的完整智能化数据治理流程。
      </p>
      <div class="hero-actions">
        <el-button type="primary" size="large" @click="router.push('/workflow')">前往治理工作台</el-button>
        <el-button size="large" @click="router.push('/datasource')">接入数据源</el-button>
      </div>
    </el-card>

    <el-row :gutter="12">
      <el-col :span="14">
        <el-card shadow="never">
          <template #header>快速开始（4 步）</template>
          <div class="quick-list">
            <div v-for="q in quickStart" :key="q.step" class="quick-item">
              <el-tag type="primary" effect="dark" size="large" class="quick-step">{{ q.step }}</el-tag>
              <div>
                <div class="quick-title">{{ q.title }}</div>
                <div class="quick-desc">{{ q.desc }}</div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="10">
        <el-card shadow="never">
          <template #header>最近数据集</template>
          <el-empty v-if="!datasets.length" description="还没有数据集，先去上传一个吧" :image-size="60" />
          <div v-else class="ds-list">
            <div v-for="d in datasets" :key="d.id" class="ds-item">
              <div class="ds-name">{{ d.filename }}</div>
              <div class="ds-meta">
                {{ d.row_count }} 行 · {{ d.source_type }}
                <el-button type="primary" link size="small" @click="router.push('/workflow')">治理 →</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard-page {
  max-width: 1300px;
}
.hero {
  margin-bottom: 12px;
  background: linear-gradient(135deg, #0b2447 0%, #1677ff 100%);
  color: #fff;
}
.hero-title {
  margin: 0 0 12px;
  font-size: 26px;
}
.hero-desc {
  font-size: 14px;
  line-height: 1.9;
  color: rgba(255, 255, 255, 0.92);
  max-width: 900px;
}
.hero-actions {
  margin-top: 18px;
}
.quick-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.quick-item {
  display: flex;
  gap: 14px;
  align-items: flex-start;
}
.quick-step {
  min-width: 34px;
  text-align: center;
}
.quick-title {
  font-weight: 600;
  font-size: 15px;
  color: #303133;
}
.quick-desc {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.7;
}
.ds-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ds-item {
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 10px 12px;
}
.ds-name {
  font-weight: 600;
  font-size: 14px;
}
.ds-meta {
  margin-top: 4px;
  font-size: 12px;
  color: #909399;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
