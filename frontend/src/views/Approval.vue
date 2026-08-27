<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { enZh, RISK_ZH, TOOL_ZH } from '../utils/i18n'

const approvals = ref<any[]>([])
const loading = ref(false)
const submittingRun = ref('')
// 本地逐条选择：key = operation.id -> 'approve' | 'reject'
const choices = ref<Record<string, string>>({})
let timer: number | null = null

async function load() {
  try {
    const resp = await fetch('/api/approval/pending')
    approvals.value = (await resp.json()).approvals ?? []
  } catch {
    /* 暂时失败 */
  }
}

function opKey(a: any): string {
  return a.operation?.id || `${a.operation?.tool}__${a.operation?.column}`
}

/** 按运行任务分组（每个 run 一组，独立逐条审批与提交） */
const groups = computed(() => {
  const map = new Map<string, any[]>()
  for (const a of approvals.value) {
    if (!map.has(a.run_id)) map.set(a.run_id, [])
    map.get(a.run_id)!.push(a)
  }
  return [...map.entries()].map(([runId, list]) => ({ runId, list }))
})

function choose(a: any, decision: 'approve' | 'reject') {
  choices.value[opKey(a)] = decision
}

function groupHandled(g: { list: any[] }): number {
  return g.list.filter((a) => choices.value[opKey(a)]).length
}

async function submitGroup(g: { runId: string; list: any[] }) {
  const decisions: Record<string, string> = {}
  for (const a of g.list) {
    const k = opKey(a)
    if (!choices.value[k]) {
      ElMessage.warning(`还有 ${g.list.length - groupHandled(g)} 项未处理，请逐条批准或拒绝`)
      return
    }
    decisions[k] = choices.value[k]
  }
  submittingRun.value = g.runId
  try {
    const resp = await fetch('/api/approval/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: g.runId, operator: 'demo-user', decisions }),
    })
    if (resp.ok) {
      ElMessage.success(`运行任务 ${g.runId} 审批已提交，仅执行批准的操作`)
      // 清掉该 run 的选择状态
      for (const k of Object.keys(decisions)) delete choices.value[k]
      await load()
    } else {
      const body = await resp.json()
      ElMessage.error(body.detail || '提交失败')
    }
  } finally {
    submittingRun.value = ''
  }
}

/** 放弃一组：全部拒绝，运行任务结束（清理历史中断残留） */
async function rejectGroup(g: { runId: string }) {
  submittingRun.value = g.runId
  try {
    const resp = await fetch('/api/approval/reject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: g.runId, operator: 'demo-user' }),
    })
    if (resp.ok) {
      ElMessage.success(`已放弃运行任务 ${g.runId}（审批全部拒绝，任务结束）`)
      // 清掉该 run 的选择状态
      for (const k of Object.keys(choices.value)) if (k.includes('__')) delete choices.value[k]
      await load()
    } else {
      const body = await resp.json()
      ElMessage.error(body.detail || '操作失败')
    }
  } finally {
    submittingRun.value = ''
  }
}

/** 清理全部残留：所有待审批组全部放弃 */
async function rejectAllGroups() {
  const runs = groups.value.map((g) => g.runId)
  for (const runId of runs) {
    await fetch('/api/approval/reject', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ run_id: runId, operator: 'demo-user' }),
    })
  }
  choices.value = {}
  ElMessage.success(`已清理 ${runs.length} 个中断的运行任务`)
  await load()
}

onMounted(() => {
  load()
  timer = window.setInterval(load, 2000)
})
onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<template>
  <div class="approval-page">
    <el-card shadow="never">
      <template #header>
        <div class="card-head">
          <span>待审批</span>
          <el-tag size="small" type="warning">{{ approvals.length }} 项待处理</el-tag>
          <div class="head-actions">
            <el-popconfirm
              v-if="groups.length > 1"
              title="确定清理全部中断的运行任务吗？它们的审批将全部拒绝并结束。"
              confirm-button-text="清理全部"
              cancel-button-text="取消"
              @confirm="rejectAllGroups"
            >
              <template #reference>
                <el-button type="danger" plain size="small">清理全部残留</el-button>
              </template>
            </el-popconfirm>
          </div>
        </div>
      </template>

      <el-empty v-if="!approvals.length" description="暂无待审批的高风险操作" />

      <div v-else class="approval-list">
        <el-alert
          type="info"
          :closable="false"
          show-icon
          class="tip-alert"
          title="按运行任务分组审批：每组内逐条选择「批准（执行）」或「拒绝（跳过）」，全部处理后提交该组。"
        />

        <!-- 每个运行任务一组 -->
        <el-card v-for="g in groups" :key="g.runId" shadow="never" class="run-group">
          <template #header>
            <div class="group-head">
              <span class="group-title">运行任务：{{ g.runId }}</span>
              <el-tag size="small" type="warning">{{ g.list.length }} 项待处理</el-tag>
            </div>
          </template>

          <el-card v-for="a in g.list" :key="a.id" shadow="hover" class="approval-card">
            <div class="op-head">
              <span class="op-name">{{ enZh(a.operation.tool, TOOL_ZH) }}（列：{{ a.operation.column }}）</span>
              <el-tag :type="a.operation.risk === 'HIGH' ? 'danger' : a.operation.risk === 'MEDIUM' ? 'warning' : 'info'" size="small">
                {{ enZh(a.operation.risk, RISK_ZH) }}
              </el-tag>
            </div>

            <el-descriptions :column="3" size="small" class="op-meta">
              <el-descriptions-item label="操作编号">{{ opKey(a) }}</el-descriptions-item>
              <el-descriptions-item label="预计影响行数">{{ a.operation.affected_rows }}</el-descriptions-item>
              <el-descriptions-item label="提交时间">{{ a.created_at }}</el-descriptions-item>
            </el-descriptions>

            <div v-if="a.operation.samples && a.operation.samples.length" class="preview">
              <div class="preview-title">变更预览（治理前 → 治理后）</div>
              <div v-for="(s, i) in a.operation.samples.slice(0, 3)" :key="i" class="preview-row">
                <code class="before">{{ JSON.stringify(s.before) }}</code>
                <el-icon><Right /></el-icon>
                <code class="after">{{ JSON.stringify(s.after) }}</code>
              </div>
            </div>

            <div class="op-actions">
              <el-button
                type="danger"
                plain
                :class="{ chosen: choices[opKey(a)] === 'reject' }"
                @click="choose(a, 'reject')"
              >拒绝（跳过）</el-button>
              <el-button
                type="success"
                plain
                :class="{ chosen: choices[opKey(a)] === 'approve' }"
                @click="choose(a, 'approve')"
              >批准（执行）</el-button>
              <el-tag v-if="choices[opKey(a)]" size="small" :type="choices[opKey(a)] === 'approve' ? 'success' : 'danger'" effect="dark">
                {{ choices[opKey(a)] === 'approve' ? '已选：批准' : '已选：拒绝' }}
              </el-tag>
            </div>
          </el-card>

          <div class="submit-bar">
            <el-popconfirm
              title="放弃该运行任务？所有待审批操作将全部拒绝，任务结束。"
              confirm-button-text="放弃"
              cancel-button-text="取消"
              @confirm="rejectGroup(g)"
            >
              <template #reference>
                <el-button type="danger" plain :loading="submittingRun === g.runId">放弃该组（清理）</el-button>
              </template>
            </el-popconfirm>
            <el-button
              type="primary"
              :disabled="groupHandled(g) !== g.list.length"
              :loading="submittingRun === g.runId"
              @click="submitGroup(g)"
            >
              提交该组审批结果（{{ groupHandled(g) }} / {{ g.list.length }}）
            </el-button>
          </div>
        </el-card>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.approval-page {
  max-width: 900px;
}
.card-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.head-actions {
  margin-left: auto;
}
.tip-alert {
  margin-bottom: 12px;
}
.approval-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.run-group {
  border: 1px solid #dcdfe6;
}
.group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.group-title {
  font-weight: 600;
  font-size: 14px;
  font-family: monospace;
}
.approval-card {
  margin-bottom: 10px;
}
.op-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.op-name {
  font-weight: 600;
  font-size: 15px;
}
.op-meta {
  margin-bottom: 8px;
}
.preview {
  background: #f7f8fa;
  border-radius: 6px;
  padding: 10px;
  margin-bottom: 10px;
}
.preview-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}
.preview-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  margin-bottom: 4px;
}
.preview-row .before {
  color: #f56c6c;
}
.preview-row .after {
  color: #67c23a;
}
.op-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 8px;
}
.op-actions .chosen {
  border-width: 2px;
}
.submit-bar {
  margin-top: 8px;
  display: flex;
  justify-content: flex-end;
}
</style>
