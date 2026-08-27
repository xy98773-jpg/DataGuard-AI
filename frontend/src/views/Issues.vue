<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { enZh, ISSUE_TYPE_ZH, SEVERITY_ZH } from '../utils/i18n'

const issues = ref<any[]>([])
const severityFilter = ref('')
const typeFilter = ref('')
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

async function load() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (severityFilter.value) params.set('severity', severityFilter.value)
    if (typeFilter.value) params.set('issue_type', typeFilter.value)
    const resp = await fetch(`/api/issues?${params.toString()}`)
    issues.value = (await resp.json()).issues ?? []
  } finally {
    loading.value = false
  }
}

watch([severityFilter, typeFilter], load)
onMounted(load)
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
