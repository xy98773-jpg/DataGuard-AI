<script setup lang="ts">
// 运行中任务面板：实时查看 PENDING/RUNNING/WAITING_APPROVAL 任务，可取消
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void; (e: 'cancelled', runId: string): void }>()

const runs = ref<any[]>([])
const loading = ref(false)
let timer: number | null = null

const STATUS_ZH: Record<string, { zh: string; type: string }> = {
  PENDING: { zh: '排队中', type: 'info' },
  RUNNING: { zh: '运行中', type: 'primary' },
  WAITING_APPROVAL: { zh: '待审批', type: 'warning' },
}

async function load() {
  if (!props.open) return
  loading.value = true
  try {
    const resp = await fetch('/api/workflow/active')
    const body = await resp.json()
    runs.value = body.runs ?? []
  } catch {
    runs.value = []
  } finally {
    loading.value = false
  }
}

// 取消任务（二次确认）
async function cancelRun(run: any) {
  try {
    await ElMessageBox.confirm(`确定取消任务 ${run.run_id} 吗？`, '取消任务', {
      type: 'warning',
      confirmButtonText: '取消任务',
      cancelButtonText: '再想想',
    })
  } catch {
    return
  }
  const resp = await fetch(`/api/workflow/${run.run_id}/cancel`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${localStorage.getItem('dg_token') ?? ''}` },
  })
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({}))
    ElMessage.error(err.detail || '取消失败')
    return
  }
  ElMessage.success('任务已取消')
  emit('cancelled', run.run_id)  // 通知父组件：若当前正显示该 run，应重置工作台
  await load()
}

// 打开时加载一次并启动轮询；关闭时停止（真实 watch 监听 open 变化）
watch(
  () => props.open,
  (v) => {
    if (v) {
      load()
      timer = window.setInterval(load, 3000)
    } else if (timer) {
      clearInterval(timer)
      timer = null
    }
  },
)

onMounted(() => {
  // 组件常驻挂载：如果初始就是打开状态也要加载
  if (props.open) {
    load()
    timer = window.setInterval(load, 3000)
  }
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <el-dialog
    :model-value="props.open"
    @update:model-value="(v: boolean) => emit('update:open', v)"
    title="运行中任务"
    width="640px"
    align-center
  >
    <div v-loading="loading">
      <el-empty v-if="!runs.length" description="当前没有运行中的任务" :image-size="70" />
      <div v-else class="run-list">
        <div v-for="r in runs" :key="r.run_id" class="run-item">
          <div class="run-info">
            <div class="run-id">{{ r.run_id }}</div>
            <div class="run-meta">
              <el-tag :type="(STATUS_ZH[r.status]?.type as any) ?? 'info'" size="small" effect="plain">
                {{ STATUS_ZH[r.status]?.zh ?? r.status }}
              </el-tag>
              <span v-if="r.current_node" class="run-node">节点：{{ r.current_node }}</span>
            </div>
          </div>
          <el-button
            v-if="['PENDING', 'RUNNING', 'WAITING_APPROVAL'].includes(r.status)"
            type="danger"
            size="small"
            @click="cancelRun(r)"
          >
            取消
          </el-button>
        </div>
      </div>
    </div>
    <template #footer>
      <el-button size="small" @click="load">刷新</el-button>
      <el-button type="primary" size="small" @click="emit('update:open', false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.run-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.run-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  padding: 10px 12px;
}
.run-id {
  font-family: monospace;
  font-size: 13px;
  color: #303133;
}
.run-meta {
  margin-top: 4px;
  display: flex;
  gap: 10px;
  align-items: center;
}
.run-node {
  font-size: 12px;
  color: #909399;
}
</style>
