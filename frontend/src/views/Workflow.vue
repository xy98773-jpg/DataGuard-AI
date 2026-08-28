<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { ElMessage, ElMessageBox } from 'element-plus'
import AgentDetail from '../components/AgentDetail.vue'
import QualityTrend from '../components/QualityTrend.vue'
import ReportDrawer from '../components/ReportDrawer.vue'
import RunningTasks from '../components/RunningTasks.vue'
import TracePanel from '../components/TracePanel.vue'
import WorkflowGraph from '../components/WorkflowGraph.vue'
import { useAppStore } from '../stores/app'
import { enZh, ISSUE_TYPE_ZH, NODE_ZH, RISK_ZH, SEVERITY_ZH, STATUS_ZH, TOOL_ZH } from '../utils/i18n'

const store = useAppStore()
const route = useRoute()
const router = useRouter()
const { dataset, runStatus, issues, plan, validation, traceEvents, selectedNode, outputs, activeDatasetId, activeRunId, reportDrawerOpen } = storeToRefs(store)

const uploading = ref(false)
const uploadName = ref('')
const datasets = ref<any[]>([])
const usageStats = ref<any>(null) // Token 消耗统计：{ usage: {node: n}, total }
let timer: number | null = null

const statusZh = computed(() => enZh(runStatus.value?.status, STATUS_ZH))
const currentNodeZh = computed(() => {
  const st = runStatus.value?.node_states ?? {}
  const running = Object.keys(st).find((k) => st[k] === 'running')
  return running ? enZh(running, NODE_ZH) : ''
})

// ---- 数据集 ----

async function loadDatasets() {
  try {
    const resp = await fetch('/api/dataset/list?limit=50')
    const body = await resp.json()
    datasets.value = (body.datasets ?? []).map((d: any) => ({
      dataset_id: d.id,
      filename: d.filename,
      name: d.name || d.filename,  // 自定义名（上传时命名或事后改名）
      rows: d.row_count,
      source_type: d.source_type,
    }))
  } catch {
    /* ignore */
  }
}

function selectDataset(d: any) {
  store.dataset = d
  store.setActiveDataset(d.dataset_id)
  store.activeRunId = ''
  store.resetRun()
  outputs.value = null  // 清除上一数据集的治理成果，避免残留
  stopPoll()
  ElMessage.success(`已选择数据集：${d.filename}`)
}

// 事后改名：历史数据集列表可直接改显示名（首页/问题中心同步生效）
async function renameDataset(d: any) {
  try {
    const { value } = await ElMessageBox.prompt(
      `为数据集「${d.name}」设置新名称：`,
      '重命名数据集',
      { inputValue: d.name, confirmButtonText: '保存', cancelButtonText: '取消' },
    )
    const newName = (value ?? '').trim()
    if (!newName) {
      ElMessage.warning('名称不能为空')
      return
    }
    const resp = await fetch(`/api/dataset/${d.dataset_id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: newName }),
    })
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}))
      ElMessage.error(err?.detail || '重命名失败')
      return
    }
    ElMessage.success(`已重命名为「${newName}」`)
    await loadDatasets()  // 刷新历史列表
    if (store.dataset?.dataset_id === d.dataset_id) store.dataset = { ...store.dataset, name: newName }
  } catch {
    /* 用户取消 */
  }
}

// ---- 两段式上传：先选文件暂存 → 填名（可选）→ 点「开始上传」才提交（文件+name 一起走）----
const pendingFile = ref<File | null>(null)

function onFileChange(f: any) {
  // 只暂存，不立即上传——避免「先选文件后填名」导致 name 丢失
  pendingFile.value = f?.raw ?? null
}

async function onUpload() {
  if (!pendingFile.value) return
  uploading.value = true
  const fd = new FormData()
  fd.append('file', pendingFile.value)
  if (uploadName.value.trim()) fd.append('name', uploadName.value.trim())
  try {
    const resp = await fetch('/api/dataset/upload', { method: 'POST', body: fd })
    // 响应体可能为空/非 JSON（如后端异常退出），先做安全解析，再给友好提示
    let body: any = null
    try {
      body = await resp.json()
    } catch {
      throw new Error(resp.ok ? '服务响应异常，请重试' : `后端服务异常（HTTP ${resp.status}），请确认 backend 已启动`)
    }
    if (!resp.ok) {
      ElMessage.error(body?.detail || `上传失败（HTTP ${resp.status}）`)
      return
    }
    store.dataset = body
    store.setActiveDataset(body.dataset_id)
    store.activeRunId = ''
    store.resetRun()
    outputs.value = null  // 清除上一数据集的治理成果
    stopPoll()
    await loadDatasets()
    pendingFile.value = null  // 上传成功清空待上传文件
    ElMessage.success(`已上传 ${body.name || body.filename}（${body.rows} 行）`)
  } catch (e: any) {
    // 网络层失败（fetch 抛 TypeError）＝后端不可用；业务失败用后端返回的消息
    if (e instanceof TypeError || String(e?.message ?? '').toLowerCase().includes('fetch')) {
      ElMessage.error('无法连接后端服务，请确认 backend 已启动（http://127.0.0.1:8000）')
    } else {
      ElMessage.error(e?.message || '上传失败，请重试')
    }
  } finally {
    uploading.value = false
  }
}

// ---- 启动与轮询 ----

async function startGovernance() {
  if (!store.dataset) return
  let body: any
  try {
    const resp = await fetch('/api/workflow/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: store.dataset.dataset_id, goal: '数据质量治理' }),
    })
    try {
      body = await resp.json()
    } catch {
      throw new Error(resp.ok ? '服务响应异常，请重试' : `后端服务异常（HTTP ${resp.status}），请确认 backend 已启动`)
    }
    if (!resp.ok) {
      ElMessage.error(body?.detail || `启动失败（HTTP ${resp.status}）`)
      return
    }
  } catch (e: any) {
    if (e instanceof TypeError || String(e?.message ?? '').toLowerCase().includes('fetch')) {
      ElMessage.error('无法连接后端服务，请确认 backend 已启动（http://127.0.0.1:8000）')
    } else {
      ElMessage.error(e?.message || '启动失败，请重试')
    }
    return
  }
  store.activeRunId = body.run_id
  store.runStatus = { status: 'RUNNING', progress: 0, node_states: {} }
  store.resetRun()
  outputs.value = null  // 新运行开始前清除旧成果
  await poll()
  timer = window.setInterval(poll, 1500)
}

async function poll() {
  if (!store.activeRunId) return
  try {
    // 并行拉取状态 + trace，事件流实时累积（不再等流程结束）
    const [statusResp, traceResp, usageResp] = await Promise.all([
      fetch(`/api/workflow/${store.activeRunId}`),
      fetch(`/api/trace/${store.activeRunId}`),
      fetch(`/api/trace/${store.activeRunId}/usage`),
    ])
    const status = await statusResp.json()
    store.runStatus = status
    store.traceEvents = (await traceResp.json()).events ?? []
    usageStats.value = await usageResp.json()
    if (status.status === 'SUCCESS' || status.status === 'FAILED') {
      stopPoll()
      await loadResults()
      if (status.status === 'FAILED') ElMessage.error(`治理流程失败（${NODE_ZH[status.current_node] ?? status.current_node}）`)
    }
  } catch {
    /* 轮询暂时失败，继续 */
  }
}

async function loadResults() {
  const dsId = store.dataset?.dataset_id || store.activeDatasetId
  const [issuesResp, planResp, validationResp, traceResp, outputsResp, usageResp] = await Promise.all([
    fetch(`/api/issues/${store.activeRunId}`),
    fetch(`/api/plan/${store.activeRunId}`),
    fetch(`/api/validation/${store.activeRunId}`),
    fetch(`/api/trace/${store.activeRunId}`),
    dsId ? fetch(`/api/dataset/${dsId}/outputs`) : Promise.resolve({ json: () => ({}) }),
    fetch(`/api/trace/${store.activeRunId}/usage`),
  ])
  store.issues = (await issuesResp.json()).issues ?? []
  store.plan = (await planResp.json()).actions ?? []
  store.validation = await validationResp.json()
  store.traceEvents = (await traceResp.json()).events ?? []
  outputs.value = await outputsResp.json()
  usageStats.value = await usageResp.json()
}

function onNodeClick(nodeId: string) {
  store.selectedNode = nodeId
}

// 打开治理报告弹窗（函数式，避免模板内联赋值的歧义）
function openReport() {
  store.reportDrawerOpen = true
}
function closeReport() {
  store.reportDrawerOpen = false
}

// 质量趋势弹窗（历史治理评分走势）
const trendOpen = ref(false)
// 运行中任务弹窗（治理工作台发起任务，这里查看/取消最直观）
const activeTasksOpen = ref(false)

// 导出治理报告（HTML / PDF）——工作台结果区
async function exportReport(fmt: 'pdf' | 'html') {
  if (!activeRunId.value) return
  const resp = await fetch(`/api/report/${activeRunId.value}/${fmt}`)
  if (!resp.ok) {
    ElMessage.error(fmt === 'pdf' ? 'PDF 导出失败（请确认本机已安装 Edge 浏览器）' : 'HTML 导出失败')
    return
  }
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `治理报告.${fmt}`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${fmt.toUpperCase()} 报告`)
}

// 抽屉打开时若报告数据未就绪（如刷新后），自动重新拉取一次
watch(reportDrawerOpen, (open) => {
  if (open && store.activeRunId && !outputs.value?.report) {
    loadResults()
  }
})

function stopPoll() {
  if (timer !== null) {
    window.clearInterval(timer)
    timer = null
  }
}

// ---- 步骤引导（el-steps）----

function stepStatus(idx: number): 'waiting' | 'process' | 'success' | 'error' {
  const st = store.runStatus?.node_states ?? {}
  const s = store.runStatus?.status ?? ''
  const milestones: Array<() => boolean> = [
    () => !!store.dataset,
    () => !!store.activeRunId,
    () => st.profiler === 'success',
    () => st.inspector === 'success',
    () => st.planner === 'success' && st.plan_validator === 'success',
    () => st.risk === 'success' && (st.approval === 'success' || !st.approval),
    () => st.execution === 'success',
    () => st.validator === 'success' || s === 'SUCCESS',
  ]
  if (idx === milestones.length - 1 && s === 'FAILED') return 'error'
  for (let i = 0; i < milestones.length; i++) {
    if (!milestones[i]()) {
      return i === idx ? 'process' : 'waiting'
    }
  }
  return 'success'
}

const steps = [
  { title: '上传数据集', desc: 'CSV / Excel / JSON' },
  { title: '启动治理', desc: 'Supervisor 规划流程' },
  { title: '分析画像', desc: 'Profiler 数据画像' },
  { title: '发现问题', desc: 'Inspector 质量检测' },
  { title: '规划方案', desc: 'Planner 清洗计划' },
  { title: '风险审批', desc: 'Risk + 人工审批' },
  { title: '执行清洗', desc: 'Execution 执行工具' },
  { title: '结果验证', desc: 'Validator 质量评分' },
]

// ---- 恢复（页面切换/刷新后继续跟踪到终态）----

// 从数据源注册跳转而来（query.dataset 携带新数据集 id）：
// 响应式监听（immediate 覆盖首次挂载，watch 覆盖组件复用时的 query 变化）：
// 自动选中新数据集并清空旧运行状态（resetRun 统一清空含 outputs），避免旧检测信息残留。
// 注意：datasets 尚未加载时（immediate 于 mount 前触发）只记录目标 dataset_id，
// 实际切换交给 onMounted 统一恢复，避免清掉 query 后无法回填 run。
watch(
  () => route.query.dataset,
  (freshDsId) => {
    if (!freshDsId) return
    if (!datasets.value.length) {
      // 数据集列表未就绪：仅记录目标，等待 onMounted 统一恢复
      store.setActiveDataset(String(freshDsId))
      return
    }
    const d = datasets.value.find((x: any) => x.dataset_id === freshDsId)
    if (d) store.dataset = d
    store.setActiveDataset(String(freshDsId))
    store.activeRunId = ''
    store.resetRun()
    stopPoll()
    // 清除 query，避免刷新后重复触发
    router.replace({ path: '/workflow' })
  },
  { immediate: true },
)

onMounted(async () => {
  await loadDatasets()
  // 恢复数据集信息（loadResults 依赖 store.dataset 拉取 outputs）
  if (route.query.dataset) {
    // query 直达：watch 可能因列表未加载而未处理，这里补全切换
    const q = String(route.query.dataset)
    const d = datasets.value.find((x: any) => x.dataset_id === q)
    if (d) store.dataset = d
    store.setActiveDataset(q)
    store.activeRunId = ''
    store.resetRun()
    stopPoll()
    router.replace({ path: '/workflow' })
  } else if (!store.dataset && store.activeDatasetId) {
    const d = datasets.value.find((x: any) => x.dataset_id === store.activeDatasetId)
    if (d) store.dataset = d
  }
  // 恢复运行：无 activeRunId 时回填该数据集最近一次运行
  if (!store.activeRunId && store.activeDatasetId) {
    try {
      const resp = await fetch(`/api/dataset/${store.activeDatasetId}/latest-run`)
      const lr = await resp.json()
      if (lr.run_id) {
        store.activeRunId = lr.run_id
        if (lr.status) store.runStatus = { status: lr.status, node_states: store.runStatus?.node_states ?? {} }
      }
    } catch {
      /* 静默 */
    }
  }
  if (store.activeRunId) {
    // 恢复运行：立即拉一次，然后持续轮询直到终态；同时加载当前可见数据
    await poll()
    await loadResults()
    if (store.runStatus && !['SUCCESS', 'FAILED'].includes(store.runStatus.status)) {
      timer = window.setInterval(poll, 1500)
    }
  }
})

onUnmounted(stopPoll)
</script>

<template>
  <div class="workflow-page">
    <div class="wf-toolbar">
      <span class="wf-toolbar-title">治理工作台</span>
      <div class="wf-toolbar-actions">
        <el-button type="warning" @click="trendOpen = true" class="toolbar-btn">
          <el-icon style="font-size: 16px"><TrendCharts /></el-icon>&nbsp;质量趋势
        </el-button>
        <el-button type="danger" @click="activeTasksOpen = true" class="toolbar-btn toolbar-btn-danger">
          <el-icon style="font-size: 16px"><Loading /></el-icon>&nbsp;运行中任务
        </el-button>
      </div>
    </div>
    <el-card shadow="never" class="steps-card">
      <el-steps
        :active="steps.findIndex((_, i) => stepStatus(i) === 'process') === -1 ? steps.length : steps.findIndex((_, i) => stepStatus(i) === 'process')"
        align-center
        finish-status="success"
        process-status="process"
      >
        <el-step v-for="(s, i) in steps" :key="i" :title="s.title" :description="s.desc" />
      </el-steps>
    </el-card>

    <el-row :gutter="12">
      <!-- 左侧：数据集 -->
      <el-col :span="6">
        <el-card shadow="never" class="panel">
          <template #header>数据集</template>
          <el-input v-model="uploadName" placeholder="数据集名称（可选，默认用文件名）" clearable class="upload-name" />
          <el-upload
            drag
            :auto-upload="false"
            :show-file-list="false"
            accept=".csv,.xlsx,.xls,.json"
            :on-change="onFileChange"
            :disabled="uploading"
          >
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div class="el-upload__text">拖拽文件到此处，或 <em>点击选择</em></div>
            <template #tip>
              <div class="el-upload__tip">支持 CSV / Excel / JSON</div>
            </template>
          </el-upload>

          <!-- 两段式：已选文件提示 + 开始上传按钮（点上传时才把文件与名称一起提交） -->
          <div v-if="pendingFile" class="pending-file">
            📎 已选择：{{ pendingFile.name }}
            <el-button link type="danger" :disabled="uploading" @click="pendingFile = null">移除</el-button>
          </div>
          <el-button type="primary" size="large" class="upload-btn" :loading="uploading" :disabled="!pendingFile" @click="onUpload">
            {{ pendingFile ? '开始上传' : '请先选择文件' }}
          </el-button>

          <el-descriptions v-if="dataset" :column="1" border class="dataset-info" size="small">
            <el-descriptions-item label="数据集 ID">{{ dataset.dataset_id }}</el-descriptions-item>
            <el-descriptions-item label="显示名">{{ dataset.name || dataset.filename }}</el-descriptions-item>
            <el-descriptions-item label="文件名">{{ dataset.filename }}</el-descriptions-item>
            <el-descriptions-item label="行数">{{ dataset.rows }}</el-descriptions-item>
            <el-descriptions-item label="列数">{{ dataset.columns ?? '-' }}</el-descriptions-item>
          </el-descriptions>

          <el-button type="primary" size="large" class="start-btn" :disabled="!dataset || !!activeRunId" @click="startGovernance">
            开始治理
          </el-button>

          <template v-if="validation">
            <el-divider content-position="left">质量评分</el-divider>
            <div class="score-block">
              <div class="score-line">
                <span>治理前</span>
                <el-progress :percentage="Math.round(validation.before_score)" :stroke-width="12" color="#f56c6c" :format="() => validation.before_score.toFixed(1)" />
              </div>
              <div class="score-line">
                <span>治理后</span>
                <el-progress :percentage="Math.round(validation.after_score)" :stroke-width="12" color="#67c23a" :format="() => validation.after_score.toFixed(1)" />
              </div>
              <el-tag :type="validation.status === 'PASS' ? 'success' : 'danger'" size="small" effect="dark">
                {{ validation.status === 'PASS' ? 'PASS（验证通过）' : 'FAIL（验证失败）' }}
              </el-tag>
            </div>
          </template>

          <el-divider content-position="left">历史数据集</el-divider>
          <div class="history-list">
            <div v-if="!datasets.length" class="history-empty">暂无历史数据集</div>
            <div
              v-for="d in datasets"
              :key="d.dataset_id"
              class="history-item"
              :class="{ active: dataset?.dataset_id === d.dataset_id }"
              @click="selectDataset(d)"
            >
              <div class="history-main">
                <span class="history-name">{{ d.name }}</span>
                <span class="history-file">{{ d.filename }}</span>
              </div>
              <span class="history-meta">
                {{ d.rows }} 行
                <el-button link type="warning" size="small" title="重命名" @click.stop="renameDataset(d)">改名</el-button>
              </span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 中间：工作流图谱 -->
      <el-col :span="10">
        <el-card shadow="never" class="panel">
          <template #header>
            <div class="card-head">
              <span>工作流图谱</span>
              <template v-if="activeRunId">
                <el-tag
                  :type="runStatus?.status === 'SUCCESS' ? 'success' : runStatus?.status === 'FAILED' ? 'danger' : runStatus?.status === 'WAITING_APPROVAL' ? 'warning' : 'primary'"
                  size="small"
                  effect="dark"
                >
                  {{ statusZh }}
                </el-tag>
                <span class="run-id">{{ activeRunId }}</span>
                <span v-if="currentNodeZh" class="current-node">当前：{{ currentNodeZh }}</span>
              </template>
            </div>
          </template>

          <template v-if="!activeRunId">
            <el-empty description="① 上传或选择左侧数据集 ② 点击「开始治理」启动流程" />
          </template>
          <template v-else>
            <WorkflowGraph
              :node-states="runStatus?.node_states ?? {}"
              :status="runStatus?.status"
              @node-click="onNodeClick"
            />

            <!-- 待审批：醒目提示，而非停滞进度条 -->
            <div v-if="runStatus?.status === 'WAITING_APPROVAL'" class="approval-banner">
              <el-icon :size="20"><Hourglass /></el-icon>
              <div>
                <div class="banner-title">任务等待人工审批</div>
                <div class="banner-desc">高风险操作已暂停，请前往「审批中心」批准或拒绝后继续执行</div>
              </div>
              <el-button type="warning" size="small" @click="$router.push('/approval')">去审批</el-button>
            </div>

            <el-progress
              v-else-if="runStatus && runStatus.status === 'RUNNING'"
              :percentage="runStatus?.progress ?? 0"
              class="progress-bar"
            />

            <!-- 结果摘要 + 查看完整报告 -->
            <template v-if="outputs || issues.length || plan.length">
              <el-divider content-position="left">治理结果</el-divider>
              <div class="result-summary">
                <div class="rs-item">
                  <div class="rs-num">{{ issues.length }}</div>
                  <div class="rs-label">发现的问题</div>
                </div>
                <div class="rs-item">
                  <div class="rs-num">{{ plan.length }}</div>
                  <div class="rs-label">清洗动作</div>
                </div>
                <div class="rs-item" v-if="validation">
                  <div class="rs-num rs-score">{{ validation?.before_score?.toFixed?.(2) ?? validation?.before_score }} → {{ validation?.after_score?.toFixed?.(2) ?? validation?.after_score }}</div>
                  <div class="rs-label">质量评分</div>
                </div>
                <div class="rs-item" v-if="outputs?.shadow_table">
                  <el-tag type="success" size="small" effect="dark">影子表</el-tag>
                  <div class="rs-label">已写入 {{ outputs.shadow_table }}（{{ outputs.shadow_rows }} 行）</div>
                </div>
                <div class="rs-item" v-else-if="outputs?.cleaned_exists">
                  <a :href="`/api/dataset/${dataset.dataset_id}/cleaned.csv`" download>
                    <el-button type="success" size="small">⬇ cleaned.csv</el-button>
                  </a>
                  <div class="rs-label">清洗后的新数据</div>
                </div>
                <div class="rs-item">
                  <el-button v-if="outputs?.report" type="primary" size="small" @click="openReport">
                    查看完整报告
                  </el-button>
                  <div class="rs-label" v-if="outputs?.report">全屏详情</div>
                </div>
                <div class="rs-item" v-if="['SUCCESS', 'FAILED'].includes(runStatus?.status)">
                  <el-button type="warning" size="small" @click="exportReport('pdf')">导出 PDF</el-button>
                  <div class="rs-label">治理报告</div>
                </div>
              </div>
            </template>

            <template v-if="false"></template>
          </template>
        </el-card>
      </el-col>

      <!-- 右侧：追踪详情 -->
      <el-col :span="8">
        <el-card shadow="never" class="panel">
          <template #header>追踪详情</template>
          <el-empty v-if="!activeRunId" description="运行工作流后查看真实追踪" :image-size="60" />
          <template v-else>
            <!-- Token 消耗统计（按 Agent 汇总，来自真实 trace） -->
            <div v-if="usageStats?.total" class="token-stats">
              <div class="token-head">
                <span>Token 消耗</span>
                <span class="token-total">合计 {{ usageStats.total }} tokens</span>
              </div>
              <div v-for="(n, node) in usageStats.usage" :key="node" class="token-row">
                <span class="token-name">{{ enZh(String(node), NODE_ZH) }}</span>
                <el-progress
                  class="token-bar"
                  :percentage="Math.round((n / (usageStats.total || 1)) * 100)"
                  :stroke-width="8"
                  :show-text="false"
                  color="#409eff"
                />
                <span class="token-num">{{ n }}</span>
              </div>
            </div>
            <div class="trace-section">
              <div class="section-title">事件流</div>
              <TracePanel :events="traceEvents" />
            </div>
            <el-divider />
            <div class="section-title">Agent 详情</div>
            <AgentDetail :run-id="activeRunId" :node-id="selectedNode" />
          </template>
        </el-card>
      </el-col>
    </el-row>

    <!-- 治理报告弹窗 -->
    <ReportDrawer
      :open="reportDrawerOpen"
      :outputs="outputs"
      :run-id="activeRunId"
      :dataset="dataset"
      @close="closeReport"
    />
    <QualityTrend v-model:open="trendOpen" />
    <RunningTasks v-model:open="activeTasksOpen" />
  </div>
</template>

<style scoped>
.workflow-page {
  max-width: 1500px;
}
.wf-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.wf-toolbar-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}
.wf-toolbar-actions {
  display: flex;
  gap: 10px;
}
.toolbar-btn {
  font-weight: 700;
  padding: 10px 18px;
  font-size: 14px;
}
.toolbar-btn-danger {
  box-shadow: 0 2px 8px rgba(245, 108, 108, 0.35);
}
.steps-card {
  margin-bottom: 12px;
}
.panel {
  margin-bottom: 12px;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.run-id {
  color: #909399;
  font-size: 12px;
}
.current-node {
  color: #409eff;
  font-size: 12px;
  font-weight: 600;
}
.upload-name {
  margin-bottom: 10px;
}
.dataset-info {
  margin-top: 16px;
}
.pending-file {
  margin-top: 10px;
  font-size: 13px;
  color: #606266;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f5f7fa;
  border: 1px dashed #c0c4cc;
  border-radius: 6px;
  padding: 8px 10px;
}
.upload-btn {
  margin-top: 10px;
  width: 100%;
}
.start-btn {
  margin-top: 16px;
  width: 100%;
}
.progress-bar {
  margin-top: 10px;
}
.approval-banner {  margin-top: 10px;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  border-radius: 8px;
  color: #e6a23c;
}
.banner-title {
  font-weight: 600;
  font-size: 14px;
}
.banner-desc {
  font-size: 12px;
  color: #b88230;
  margin-top: 2px;
}
.score-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.score-line {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #606266;
}
.history-list {
  max-height: 220px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.history-empty {
  color: #c0c4cc;
  font-size: 12px;
  text-align: center;
  padding: 8px 0;
}
.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
}
.history-item:hover {
  background: #f5f7fa;
}
.history-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}
.history-name {
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.history-meta {
  color: #909399;
  font-size: 12px;
  flex-shrink: 0;
}
.result-summary {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 4px;
}
.rs-item {
  background: #fafafa;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  padding: 10px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.rs-num {
  font-size: 17px;
  font-weight: 700;
  color: #303133;
}
.rs-score {
  font-size: 14px;
}
.rs-label {
  font-size: 12px;
  color: #909399;
}
.trace-section {
  margin-bottom: 4px;
}
.token-stats {
  background: #f5f7fa;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 8px 10px;
  margin-bottom: 12px;
}
.token-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 8px;
}
.token-total {
  color: #409eff;
  font-weight: 700;
}
.token-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 5px;
}
.token-name {
  width: 72px;
  font-size: 12px;
  color: #606266;
  flex-shrink: 0;
}
.token-bar {
  flex: 1;
}
.token-num {
  width: 48px;
  text-align: right;
  font-size: 12px;
  font-family: monospace;
  color: #303133;
  flex-shrink: 0;
}
.section-title {
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
  font-weight: 600;
}
.deliver-block {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.deliver-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}
.deliver-label {
  color: #606266;
  min-width: 90px;
}
.deliver-val {
  color: #909399;
  font-family: monospace;
  font-size: 12px;
}
.deliver-desc {
  margin-top: 4px;
}
.dims {
  margin-top: 10px;
}
.dim-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
  font-weight: 600;
}
.dim-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.dim-name {
  min-width: 60px;
  font-size: 12px;
  color: #606266;
}
.dim-bar {
  flex: 1;
}
.dim-arrow {
  color: #c0c4cc;
}
.execs {
  margin-top: 10px;
}
.sample-line {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  line-height: 1.7;
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
</style>
