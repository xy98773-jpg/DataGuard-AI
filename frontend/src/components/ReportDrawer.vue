<script setup lang="ts">
import { computed } from 'vue'
import { enZh, ISSUE_TYPE_ZH, SEVERITY_ZH, TOOL_ZH, RISK_ZH } from '../utils/i18n'

const props = defineProps<{
  open: boolean
  outputs: any
  runId: string
  dataset: any
}>()
const emit = defineEmits<{ (e: 'close'): void }>()

const report = computed(() => props.outputs?.report ?? {})
const issues = computed(() => report.value.issues ?? [])
const plan = computed(() => report.value.plan?.actions ?? [])
const exec = computed(() => report.value.execution ?? [])
const validation = computed(() => report.value.validation ?? {})
const cleanedExists = computed(() => !!props.outputs?.cleaned_exists)
// database 源交付物是影子表（无 csv 文件），不显示 csv 下载
const shadowInfo = computed(() => props.outputs?.shadow_table ?? '')

const DIM_ZH: Record<string, string> = {
  completeness: '完整性',
  uniqueness: '唯一性',
  format_validity: '格式合规',
}

/** 质量维度明细（before → after 双进度条） */
const qualityDims = computed(() => {
  const before = validation.value?.quality_before?.dimensions ?? {}
  const after = validation.value?.quality_after?.dimensions ?? {}
  return Object.keys({ ...before, ...after }).map((k) => ({
    key: k,
    name: DIM_ZH[k] || k,
    before: Math.round((before[k] ?? 0) * 1000) / 10,
    after: Math.round((after[k] ?? 0) * 1000) / 10,
    improved: (after[k] ?? 0) >= (before[k] ?? 0),
  }))
})

const execSummary = computed(() => {
  const ok = exec.value.filter((r: any) => r.status === 'success')
  const rows = ok.reduce((s: number, r: any) => s + (r.affected_rows ?? 0), 0)
  return { total: exec.value.length, ok: ok.length, rows }
})

const beforeScore = computed(() => validation.value?.quality_before?.overall ?? validation.value?.before_score ?? 0)
const afterScore = computed(() => validation.value?.quality_after?.overall ?? validation.value?.after_score ?? 0)

function fmtBefore(s: any): string {
  if (s == null) return '（空值）'
  if (typeof s === 'object') return `${s.column_value ?? ''} ×${s.occurrences ?? 1}`
  return String(s)
}
function fmtAfter(s: any): string {
  if (s === 'deleted') return '已删除'
  if (s == null) return '（空值）'
  if (typeof s === 'object') return s.after ?? JSON.stringify(s)
  return String(s)
}

// 导出治理报告（HTML / PDF）
async function exportReport(fmt: 'pdf' | 'html') {
  try {
    const resp = await fetch(`/api/report/${props.runId}/${fmt}`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `治理报告.${fmt}`
    a.click()
    URL.revokeObjectURL(url)
  } catch {
    // 静默：按钮下方提示由调用方负责（避免引入额外依赖）
  }
}
</script>

<template>
  <el-dialog
    :model-value="open"
    width="72%"
    align-center
    class="report-dialog"
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    @close="emit('close')"
  >
    <template #header>
      <div class="report-title">
        <span class="title-main">📋 治理报告</span>
        <span class="title-name">{{ dataset?.name || dataset?.filename || '' }}</span>
        <el-tag size="small" type="info" effect="plain">{{ runId }}</el-tag>
      </div>
    </template>

    <div class="report-body">
      <!-- 顶部操作条 -->
      <div class="report-actions">
        <el-tag v-if="shadowInfo" type="success" size="small" effect="dark">
          已写入影子表 {{ shadowInfo }}（{{ outputs?.shadow_rows ?? 0 }} 行，生产表未改动）
        </el-tag>
        <a v-else-if="cleanedExists" :href="`/api/dataset/${dataset?.dataset_id}/cleaned.csv`" download>
          <el-button type="success" size="small">⬇ 下载 cleaned.csv</el-button>
        </a>
        <el-button type="warning" size="small" @click="exportReport('pdf')">导出 PDF</el-button>
        <el-button size="small" @click="exportReport('html')">导出 HTML</el-button>
        <el-button type="primary" size="small" @click="emit('close')">收起报告</el-button>
      </div>

      <!-- 概要统计 -->
      <div class="report-summary">
        <div class="summary-card">
          <div class="summary-num">{{ issues.length }}</div>
          <div class="summary-label">发现的问题</div>
        </div>
        <div class="summary-card">
          <div class="summary-num">{{ execSummary.ok }} / {{ execSummary.total }}</div>
          <div class="summary-label">清洗动作成功</div>
        </div>
        <div class="summary-card">
          <div class="summary-num">{{ execSummary.rows }}</div>
          <div class="summary-label">影响行数</div>
        </div>
        <div class="summary-card">
          <div class="summary-num">{{ beforeScore.toFixed?.(2) ?? beforeScore }} → {{ afterScore.toFixed?.(2) ?? afterScore }}</div>
          <div class="summary-label">
            质量评分
            <el-tag :type="validation.status === 'PASS' ? 'success' : 'danger'" size="small" effect="dark" class="status-tag">
              {{ validation.status === 'PASS' ? 'PASS' : 'FAIL' }}
            </el-tag>
          </div>
        </div>
      </div>

      <!-- 1. 发现的问题 -->
      <section class="report-section">
        <div class="section-title">发现的问题（{{ issues.length }}）</div>
        <el-table :data="issues" size="default" max-height="360" border>
          <el-table-column label="编号" width="100" prop="id" />
          <el-table-column label="类型" width="200">
            <template #default="{ row }">{{ enZh(row.issue_type ?? row.type, ISSUE_TYPE_ZH) }}</template>
          </el-table-column>
          <el-table-column prop="column" label="列" width="120" />
          <el-table-column label="严重度" width="130">
            <template #default="{ row }">
              <el-tag :type="row.severity === 'HIGH' ? 'danger' : row.severity === 'MEDIUM' ? 'warning' : 'info'" size="small">
                {{ enZh(row.severity, SEVERITY_ZH) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="affected_rows" label="影响行数" width="100" />
          <el-table-column label="置信度" width="100">
            <template #default="{ row }">{{ (row.confidence * 100).toFixed(0) }}%</template>
          </el-table-column>
          <el-table-column label="证据样例" min-width="220">
            <template #default="{ row }">{{ (row.evidence || []).slice(0, 3).join(', ') || '—' }}</template>
          </el-table-column>
        </el-table>
      </section>

      <!-- 2. 清洗计划 -->
      <section class="report-section">
        <div class="section-title">清洗计划（{{ plan.length }}）</div>
        <el-table :data="plan" size="default" border>
          <el-table-column label="工具" min-width="200">
            <template #default="{ row }">{{ enZh(row.tool, TOOL_ZH) }}</template>
          </el-table-column>
          <el-table-column prop="column" label="列" width="140" />
          <el-table-column label="风险" width="140">
            <template #default="{ row }">
              <el-tag :type="row.risk === 'HIGH' ? 'danger' : row.risk === 'MEDIUM' ? 'warning' : 'success'" size="small">
                {{ enZh(row.risk, RISK_ZH) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="对应问题" min-width="120">
            <template #default="{ row }">{{ row.issue_id || '—' }}</template>
          </el-table-column>
        </el-table>
      </section>

      <!-- 3. 清洗动作明细（before → after） -->
      <section class="report-section">
        <div class="section-title">清洗动作明细（含样例对比）</div>
        <el-table :data="exec" size="default" border>
          <el-table-column label="工具" min-width="180">
            <template #default="{ row }">{{ enZh(row.tool, TOOL_ZH) }}</template>
          </el-table-column>
          <el-table-column prop="column" label="列" width="120" />
          <el-table-column label="风险" width="110">
            <template #default="{ row }">
              <el-tag :type="row.risk === 'HIGH' ? 'danger' : row.risk === 'MEDIUM' ? 'warning' : 'success'" size="small">
                {{ enZh(row.risk, RISK_ZH) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="affected_rows" label="影响行数" width="100" />
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">
                {{ row.status === 'success' ? '成功' : '失败' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="样例（before → after）" min-width="280">
            <template #default="{ row }">
              <div class="sample-line" v-for="(s, idx) in (row.samples || []).slice(0, 3)" :key="idx">
                <span class="sample-before">{{ fmtBefore(s.before) }}</span>
                <span class="sample-arrow">→</span>
                <span class="sample-after">{{ fmtAfter(s.after) }}</span>
              </div>
              <span v-if="!(row.samples || []).length" class="sample-none">—</span>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <!-- 4. 质量维度对比 -->
      <section class="report-section" v-if="qualityDims.length">
        <div class="section-title">质量维度对比（0-100%）</div>
        <div class="dims">
          <div v-for="d in qualityDims" :key="d.key" class="dim-row">
            <span class="dim-name">{{ d.name }}</span>
            <span class="dim-bar">
              <el-progress :percentage="Math.round(d.before)" :stroke-width="10" color="#f56c6c" :format="() => d.before.toFixed(1)" />
            </span>
            <span class="dim-arrow">→</span>
            <span class="dim-bar">
              <el-progress :percentage="Math.round(d.after)" :stroke-width="10" :color="d.improved ? '#67c23a' : '#e6a23c'" :format="() => d.after.toFixed(1)" />
            </span>
          </div>
        </div>
      </section>
    </div>
  </el-dialog>
</template>

<style scoped>
.report-dialog {
  background: #f5f7fa;
}
.report-dialog :deep(.el-dialog__body) {
  max-height: calc(100vh - 180px);
  overflow-y: auto;
}
.report-body {
  padding: 4px 8px 24px;
}
.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.report-title {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  font-size: 16px;
}
.title-main {
  font-size: 18px;
  font-weight: 700;
}
.title-name {
  font-size: 15px;
  color: #606266;
}
.report-actions {
  display: flex;
  gap: 8px;
}
.report-summary {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}
.summary-card {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 14px 16px;
  text-align: center;
}
.summary-num {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}
.summary-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.status-tag {
  margin-left: 6px;
}
.report-section {
  background: #fff;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.section-title {
  font-size: 15px;
  font-weight: 700;
  color: #303133;
  margin-bottom: 12px;
}
.sample-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  line-height: 1.8;
}
.sample-before {
  color: #f56c6c;
  font-family: monospace;
}
.sample-after {
  color: #67c23a;
  font-family: monospace;
}
.sample-arrow {
  color: #c0c4cc;
}
.sample-none {
  color: #c0c4cc;
}
.dims {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.dim-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.dim-name {
  min-width: 70px;
  font-size: 13px;
  color: #606266;
}
.dim-bar {
  flex: 1;
}
.dim-arrow {
  color: #c0c4cc;
}
@media (max-width: 900px) {
  .report-summary {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
