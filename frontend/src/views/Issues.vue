<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { enZh, ISSUE_TYPE_ZH, SEVERITY_ZH } from '../utils/i18n'

const route = useRoute()
const issues = ref<any[]>([])
const severityFilter = ref('')
const typeFilter = ref('')
const datasetFilter = ref('') // 按数据集筛选（支持 /issues?dataset=xxx 跳转）
const datasets = ref<any[]>([]) // 数据集下拉选项
const loading = ref(false)

/** 按数据集分组（第一层级：数据集名称，文件名作副标题） */
const groups = computed(() => {
  const map = new Map<string, any[]>()
  for (const i of issues.value) {
    const key = i.dataset_name || i.dataset_file || i.dataset_id || '未知数据集'
    if (!map.has(key)) map.set(key, [])
    map.get(key)!.push(i)
  }
  return [...map.entries()].map(([name, list]) => ({
    name,
    file: list[0]?.dataset_file && list[0]?.dataset_file !== name ? list[0].dataset_file : '',
    datasetId: list[0]?.dataset_id ?? '',
    count: list.length,
    high: list.filter((i) => i.severity === 'HIGH').length,
    medium: list.filter((i) => i.severity === 'MEDIUM').length,
    low: list.filter((i) => i.severity === 'LOW').length,
    list,
  }))
})

const stats = computed(() => ({
  total: issues.value.length,
  datasets: groups.value.length,
  high: issues.value.filter((i) => i.severity === 'HIGH').length,
  medium: issues.value.filter((i) => i.severity === 'MEDIUM').length,
  low: issues.value.filter((i) => i.severity === 'LOW').length,
}))

const types = computed(() => [...new Set(issues.value.map((i) => i.type))].sort())

async function loadDatasets() {
  try {
    const resp = await fetch('/api/dataset/list?limit=50')
    datasets.value = (await resp.json()).datasets ?? []
  } catch {
    datasets.value = []
  }
}

// 删除数据集（连带其问题与运行历史，二次确认）
async function deleteDataset(g: any) {
  if (!g.datasetId) return
  try {
    await ElMessageBox.confirm(
      `确定删除数据集「${g.name}」吗？\n将同时删除它的 ${g.count} 条问题记录与全部运行历史，且不可恢复。`,
      '删除数据集',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消', confirmButtonClass: 'el-button--danger' },
    )
  } catch {
    return  // 用户取消
  }
  const resp = await fetch(`/api/dataset/${g.datasetId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${localStorage.getItem('dg_token') ?? ''}` },
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    if (resp.status === 401) {
      ElMessage.error('登录已过期，请重新登录')
      setTimeout(() => (window.location.href = '/login'), 800)
      return
    }
    ElMessage.error(err?.detail || '删除失败')
    return
  }
  ElMessage.success(`已删除数据集「${g.name}」`)
  await load()  // 刷新问题列表（该分组消失）
  await loadDatasets()  // 刷新数据集下拉
}

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (severityFilter.value) params.set('severity', severityFilter.value)
    if (typeFilter.value) params.set('issue_type', typeFilter.value)
    if (datasetFilter.value) params.set('dataset_id', datasetFilter.value)
    const resp = await fetch(`/api/issues?${params.toString()}`)
    issues.value = (await resp.json()).issues ?? []
  } finally {
    loading.value = false
  }
}

watch([severityFilter, typeFilter, datasetFilter], load)
onMounted(async () => {
  await loadDatasets()
  // 从 Dashboard「问题」按钮跳转：/issues?dataset=ds_xxx 预选数据集
  const q = route.query.dataset
  if (typeof q === 'string' && q) datasetFilter.value = q
  load()
})
</script>

<template>
  <div class="issues-page">
    <el-row :gutter="12" class="stat-row">
      <el-col :span="6"><el-card shadow="never"><div class="stat"><div class="stat-num">{{ stats.total }}</div><div class="stat-label">问题总数</div></div></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><div class="stat"><div class="stat-num">{{ stats.datasets }}</div><div class="stat-label">涉及数据集</div></div></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><div class="stat high"><div class="stat-num">{{ stats.high }}</div><div class="stat-label">高严重度</div></div></el-card></el-col>
      <el-col :span="6"><el-card shadow="never"><div class="stat"><div class="stat-num">{{ stats.medium }} / {{ stats.low }}</div><div class="stat-label">中 / 低严重度</div></div></el-card></el-col>
    </el-row>

    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>数据质量问题（按数据集分级）</span>
          <div class="filters">
            <el-select v-model="datasetFilter" placeholder="全部数据集" clearable filterable style="width: 200px">
              <el-option v-for="d in datasets" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
            <el-select v-model="severityFilter" placeholder="全部严重度" clearable style="width: 140px">
              <el-option label="HIGH（高）" value="HIGH" />
              <el-option label="MEDIUM（中）" value="MEDIUM" />
              <el-option label="LOW（低）" value="LOW" />
            </el-select>
            <el-select v-model="typeFilter" placeholder="全部类型" clearable style="width: 180px">
              <el-option v-for="t in types" :key="t" :label="enZh(t, ISSUE_TYPE_ZH)" :value="t" />
            </el-select>
          </div>
        </div>
      </template>

      <el-empty v-if="!issues.length" description="暂无问题（可到治理工作台运行一次治理流程）" />
      <el-collapse v-else v-loading="loading" class="groups">
        <el-collapse-item v-for="g in groups" :key="g.name">
          <template #title>
            <div class="group-head">
              <span class="group-name">📄 {{ g.name }}<span v-if="g.file" class="group-file">{{ g.file }}</span></span>
              <span class="group-badges">
                <el-tag size="small" type="danger" effect="plain">高 {{ g.high }}</el-tag>
                <el-tag size="small" type="warning" effect="plain">中 {{ g.medium }}</el-tag>
                <el-tag size="small" type="info" effect="plain">低 {{ g.low }}</el-tag>
                <span class="group-count">共 {{ g.count }} 个问题</span>
                <el-button link type="danger" size="small" @click.stop="deleteDataset(g)">删除数据集</el-button>
              </span>
            </div>
          </template>
          <el-table :data="g.list" size="small" max-height="420">
            <el-table-column label="编号" width="90">
              <template #default="{ row }">{{ row.id }}</template>
            </el-table-column>
            <el-table-column label="类型" width="150">
              <template #default="{ row }">{{ enZh(row.type, ISSUE_TYPE_ZH) }}</template>
            </el-table-column>
            <el-table-column prop="column" label="列" width="100" />
            <el-table-column label="严重度" width="110">
              <template #default="{ row }">
                <el-tag :type="row.severity === 'HIGH' ? 'danger' : row.severity === 'MEDIUM' ? 'warning' : 'info'" size="small">
                  {{ enZh(row.severity, SEVERITY_ZH) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="置信度" width="80">
              <template #default="{ row }">{{ (row.confidence * 100).toFixed(0) }}%</template>
            </el-table-column>
            <el-table-column prop="affected_rows" label="影响行数" width="80" />
            <el-table-column prop="run_id" label="运行任务" min-width="150" show-overflow-tooltip />
            <el-table-column label="证据样例" min-width="180">
              <template #default="{ row }">{{ (row.evidence || []).slice(0, 3).join(', ') }}</template>
            </el-table-column>
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<style scoped>
.issues-page {
  max-width: 1400px;
}
.stat-row {
  margin-bottom: 12px;
}
.stat {
  text-align: center;
  padding: 6px 0;
}
.stat-num {
  font-size: 26px;
  font-weight: 700;
  color: #303133;
}
.stat.high .stat-num { color: #f56c6c; }
.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 2px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.filters {
  display: flex;
  gap: 8px;
}
.groups {
  border-top: none;
}
.group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding-right: 12px;
}
.group-name {
  font-weight: 600;
  font-size: 14px;
}
.group-file {
  font-weight: 400;
  font-size: 12px;
  color: #909399;
  margin-left: 8px;
  font-family: monospace;
}
.group-badges {
  display: flex;
  align-items: center;
  gap: 6px;
}
.group-count {
  color: #909399;
  font-size: 12px;
  margin-left: 6px;
}
</style>
