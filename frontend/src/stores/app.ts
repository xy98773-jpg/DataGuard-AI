import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

// 页面切换 / 刷新后仍能恢复最近的数据集与运行任务
// 运行时状态（dataset/runStatus/issues/...）保存在 store 内存中，
// 切换页面组件卸载不丢失；刷新时按 localStorage 的 run_id 重新拉取（后端已持久化）。
const LS_KEY = 'dg-active-run'

function loadPersisted(): { datasetId: string; runId: string } {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (raw) return JSON.parse(raw)
  } catch {
    /* ignore */
  }
  return { datasetId: '', runId: '' }
}

export const useAppStore = defineStore('app', () => {
  const backendOnline = ref(false)
  const persisted = loadPersisted()
  const activeDatasetId = ref(persisted.datasetId)
  const activeRunId = ref(persisted.runId)

  // ---- 运行时状态（Workflow 工作台共享，切页不丢）----
  const dataset = ref<any>(null)
  const runStatus = ref<any>(null)
  const issues = ref<any[]>([])
  const plan = ref<any[]>([])
  const validation = ref<any>(null)
  const traceEvents = ref<any[]>([])
  const selectedNode = ref('')
  const outputs = ref<any>(null)  // 治理成果（outputs API 响应），与 dataset/run 同生命周期
  const reportDrawerOpen = ref(false)  // 治理报告弹窗（内存态，切页不丢）

  watch([activeDatasetId, activeRunId], ([d, r]) => {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify({ datasetId: d, runId: r }))
    } catch {
      /* ignore */
    }
  })

  function setBackendOnline(online: boolean) {
    backendOnline.value = online
  }

  function setActiveDataset(datasetId: string) {
    activeDatasetId.value = datasetId
  }

  function setActiveRun(runId: string) {
    activeRunId.value = runId
  }

  function resetRun() {
    runStatus.value = null
    issues.value = []
    plan.value = []
    validation.value = null
    traceEvents.value = []
    selectedNode.value = ''
    outputs.value = null  // 关键：治理成果必须随运行状态一起清空，避免残留旧报告
  }

  return {
    backendOnline,
    activeDatasetId,
    activeRunId,
    dataset,
    runStatus,
    issues,
    plan,
    validation,
    traceEvents,
    selectedNode,
    outputs,
    reportDrawerOpen,
    setBackendOnline,
    setActiveDataset,
    setActiveRun,
    resetRun,
  }
})
