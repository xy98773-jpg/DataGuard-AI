<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

// ---- 平台统计（GET /api/dashboard/stats）----
const stats = ref<any>(null)

// ---- 数据集管理列表（GET /api/dataset/list，支持搜索/筛选/分页）----
const datasets = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const search = ref('')
const srcFilter = ref('')
const page = ref(1)
const pageSize = 10

const SRC_MAP: Record<string, string> = { file: '文件', web: '网页', database: '数据库' }
const STATUS_MAP: Record<string, { zh: string; type: 'success' | 'danger' | 'warning' | 'primary' | 'info' }> = {
  SUCCESS: { zh: '成功', type: 'success' },
  FAILED: { zh: '失败', type: 'danger' },
  WAITING_APPROVAL: { zh: '待审批', type: 'warning' },
  RUNNING: { zh: '运行中', type: 'primary' },
  PENDING: { zh: '排队中', type: 'info' },
}

async function loadStats() {
  try {
    const resp = await fetch('/api/dashboard/stats')
    stats.value = await resp.json()
  } catch {
    stats.value = null
  }
}

// 数据集列表：搜索/筛选变化回到第 1 页，再加载
async function loadDatasets() {
  loading.value = true
  try {
    const params = new URLSearchParams({
      limit: String(pageSize),
      offset: String((page.value - 1) * pageSize),
    })
    if (search.value.trim()) params.set('search', search.value.trim())
    if (srcFilter.value) params.set('source_type', srcFilter.value)
    const resp = await fetch(`/api/dataset/list?${params.toString()}`)
    const body = await resp.json()
    datasets.value = body.datasets ?? []
    total.value = body.total ?? 0
  } catch {
    datasets.value = []
  } finally {
    loading.value = false
  }
}

watch([search, srcFilter], () => {
  page.value = 1
  loadDatasets()
})
watch(page, loadDatasets)

function goGovernance(row: any) {
  // 携带数据集 id 跳工作台：Workflow 页自动选中该数据集并清空旧状态
  router.push({ path: '/workflow', query: { dataset: row.id } })
}

function goIssues(row: any) {
  router.push({ path: '/issues', query: { dataset: row.id } })
}

const statCards = [
  { label: '运行总数', value: () => stats.value?.total_runs ?? 0, suffix: '次' },
  { label: '治理成功率', value: () => stats.value?.success_rate ?? 0, suffix: '%' },
  { label: '发现问题', value: () => stats.value?.issues_found ?? 0, suffix: '个' },
  { label: '数据集', value: () => stats.value?.datasets ?? 0, suffix: '个' },
]

const quickStart = [
  { step: '1', title: '准备数据', desc: '上传 CSV / Excel / JSON 文件，或接入 MySQL / PostgreSQL / 网页数据源' },
  { step: '2', title: '启动治理', desc: '在「治理工作台」点击「开始治理」，Agent 自动完成画像、质检、规划' },
  { step: '3', title: '查看图谱与问题', desc: '工作流图谱实时展示执行进度，点击节点查看每个 Agent 的真实推理与工具调用' },
  { step: '4', title: '审批与验证', desc: '高风险操作在「审批中心」人工确认后执行，最终输出前后质量评分与治理报告' },
]

onMounted(() => {
  loadStats()
  loadDatasets()
})
</script>

<template>
  <div class="dashboard-page">
    <!-- 顶部窄标题条（不再占半屏） -->
    <div class="topbar">
      <div class="topbar-title">
        <span class="logo">DataGuard AI</span>
        <span class="subtitle">企业数据治理 Agent 平台</span>
      </div>
      <div class="topbar-actions">
        <el-button type="primary" @click="router.push('/workflow')">前往治理工作台</el-button>
        <el-button @click="router.push('/datasource')">接入数据源</el-button>
      </div>
    </div>

    <!-- 平台统计卡片 -->
    <el-row :gutter="12" class="stats-row">
      <el-col :span="6" v-for="c in statCards" :key="c.label">
        <el-card shadow="hover" class="stat-card">
          <div class="stat-value">{{ c.value() }}<span class="stat-suffix">{{ c.suffix }}</span></div>
          <div class="stat-label">{{ c.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 数据集管理列表（核心：搜索/筛选/分页应对数据集变多） -->
    <el-card shadow="never" class="ds-card">
      <template #header>
        <div class="card-head">
          <span>数据集管理（共 {{ total }} 个）</span>
          <div class="list-tools">
            <el-input v-model="search" placeholder="搜索数据集名称 / 文件名" clearable style="width: 230px" />
            <el-select v-model="srcFilter" placeholder="来源类型" clearable style="width: 130px">
              <el-option label="文件" value="file" />
              <el-option label="网页" value="web" />
              <el-option label="数据库" value="database" />
            </el-select>
          </div>
        </div>
      </template>

      <el-table v-loading="loading" :data="datasets" stripe style="width: 100%">
        <el-table-column label="数据集" min-width="240">
          <template #default="{ row }">
            <div class="ds-name">{{ row.name }}</div>
            <div class="ds-file">{{ row.filename }}</div>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ SRC_MAP[row.source_type] ?? row.source_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="行数" width="100">
          <template #default="{ row }">{{ row.row_count ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="治理状态" width="120">
          <template #default="{ row }">
            <template v-if="row.last_status">
              <el-tag :type="(STATUS_MAP[row.last_status]?.type ?? 'info') as any" size="small" effect="dark">
                {{ STATUS_MAP[row.last_status]?.zh ?? row.last_status }}
              </el-tag>
            </template>
            <span v-else class="never">未治理</span>
          </template>
        </el-table-column>
        <el-table-column label="问题数" width="90">
          <template #default="{ row }">
            <el-badge :value="row.issue_count ?? 0" :hidden="!row.issue_count" type="danger" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="goGovernance(row)">治理 →</el-button>
            <el-button link @click="goIssues(row)">问题</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pager">
        <el-pagination
          layout="prev, pager, next, total"
          :total="total"
          :page-size="pageSize"
          :current-page="page"
          @current-change="(p: number) => (page = p)"
        />
      </div>
    </el-card>

    <!-- 使用引导（折叠，默认收起） -->
    <el-collapse class="guide">
      <el-collapse-item title="如何使用（4 步快速上手）">
        <div class="quick-list">
          <div v-for="q in quickStart" :key="q.step" class="quick-item">
            <el-tag type="primary" effect="dark" size="large" class="quick-step">{{ q.step }}</el-tag>
            <div>
              <div class="quick-title">{{ q.title }}</div>
              <div class="quick-desc">{{ q.desc }}</div>
            </div>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<style scoped>
.dashboard-page {
  max-width: 1300px;
}
/* ---- 顶部窄标题条 ---- */
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
/* ---- 数据集管理列表 ---- */
.ds-card {
  margin-bottom: 12px;
}
.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.list-tools {
  display: flex;
  gap: 8px;
}
.ds-name {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
}
.ds-file {
  font-size: 12px;
  color: #909399;
  margin-top: 2px;
}
.never {
  color: #c0c4cc;
  font-size: 12px;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
/* ---- 使用引导（折叠） ---- */
.guide {
  border-radius: 6px;
}
.quick-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 4px 8px;
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
  font-size: 14px;
  color: #303133;
}
.quick-desc {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.7;
}
</style>
