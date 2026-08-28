<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const datasets = ref<any[]>([])
const stats = ref<any>(null) // /api/dashboard/stats 平台统计

// 状态 → 中文标签 & 颜色（与全站 STATUS_ZH 一致）
const STATUS_MAP: Record<string, { zh: string; type: 'success' | 'danger' | 'warning' | 'primary' | 'info' }> = {
  SUCCESS: { zh: '成功', type: 'success' },
  FAILED: { zh: '失败', type: 'danger' },
  WAITING_APPROVAL: { zh: '待审批', type: 'warning' },
  RUNNING: { zh: '运行中', type: 'primary' },
  PENDING: { zh: '排队中', type: 'info' },
}
const SRC_MAP: Record<string, string> = { file: '文件', web: '网页', database: '数据库' }

async function load() {
  try {
    const resp = await fetch('/api/dataset/list')
    datasets.value = (await resp.json()).datasets ?? []
  } catch {
    /* ignore */
  }
}

// 平台统计：总运行 / 成功率 / 问题数 / 数据集数 + 最近运行列表
async function loadStats() {
  try {
    const resp = await fetch('/api/dashboard/stats')
    stats.value = await resp.json()
  } catch {
    stats.value = null
  }
}

onMounted(() => {
  load()
  loadStats()
})

// 统计卡片数据（4 项）
const statCards = [
  { label: '运行总数', value: () => stats.value?.total_runs ?? 0, suffix: '次' },
  { label: '治理成功率', value: () => stats.value?.success_rate ?? 0, suffix: '%' },
  { label: '发现问题', value: () => stats.value?.issues_found ?? 0, suffix: '个' },
  { label: '数据集', value: () => stats.value?.datasets ?? 0, suffix: '个' },
]

function goRun(row: any) {
  // 跳转治理工作台查看该运行（页面按 activeRunId 恢复并展示图谱/追踪/报告）
  router.push({ path: '/workflow' })
}

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

    <!-- 平台统计卡片（来自真实业务库） -->
    <el-row :gutter="12" class="stats-row">
      <el-col :span="6" v-for="c in statCards" :key="c.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ c.value() }}<span class="stat-suffix">{{ c.suffix }}</span></div>
          <div class="stat-label">{{ c.label }}</div>
        </el-card>
      </el-col>
    </el-row>

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
                {{ d.row_count }} 行 · {{ SRC_MAP[d.source_type] ?? d.source_type }}
                <el-button type="primary" link size="small" @click="router.push('/workflow')">治理 →</el-button>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近运行（含状态/质量分/重规划次数） -->
    <el-card shadow="never" class="recent-card">
      <template #header>最近运行</template>
      <el-empty v-if="!stats?.recent_runs?.length" description="还没有运行记录，去治理工作台启动一次吧" :image-size="60" />
      <el-table v-else :data="stats.recent_runs" stripe style="width: 100%" @row-click="goRun">
        <el-table-column label="运行 ID" prop="run_id" width="180" />
        <el-table-column label="数据集" prop="dataset_name" min-width="140" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">{{ SRC_MAP[row.source_type] ?? row.source_type }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="(STATUS_MAP[row.status]?.type ?? 'info') as any" size="small" effect="dark">
              {{ STATUS_MAP[row.status]?.zh ?? row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="质量评分" width="160">
          <template #default="{ row }">
            <span v-if="row.before_score != null" class="score-text">
              {{ Number(row.before_score).toFixed(2) }} → {{ Number(row.after_score).toFixed(2) }}
            </span>
            <span v-else class="score-none">—</span>
          </template>
        </el-table-column>
        <el-table-column label="重规划" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.iteration > 0" type="warning" size="small" effect="plain">{{ row.iteration }} 次</el-tag>
            <span v-else class="score-none">—</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="170">
          <template #default="{ row }">
            <span class="time-text">{{ row.created_at ? new Date(row.created_at).toLocaleString('zh-CN') : '' }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
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
/* ---- 统计卡片 ---- */
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
/* ---- 快速开始 / 最近数据集 ---- */
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
/* ---- 最近运行表 ---- */
.recent-card {
  margin-top: 12px;
}
.score-text {
  font-family: monospace;
  font-size: 13px;
  color: #303133;
}
.score-none {
  color: #c0c4cc;
}
.time-text {
  font-size: 12px;
  color: #909399;
}
</style>
