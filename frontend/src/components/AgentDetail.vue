<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { enZh, EVENT_ZH, NODE_ZH } from '../utils/i18n'

const props = defineProps<{
  runId: string
  nodeId: string
}>()

const events = ref<any[]>([])
const loading = ref(false)
const openPanels = ref<string[]>([])

watch(
  () => [props.runId, props.nodeId] as const,
  async ([runId, nodeId]) => {
    if (!nodeId || !runId) {
      events.value = []
      return
    }
    loading.value = true
    try {
      const resp = await fetch(`/api/trace/${runId}?node=${nodeId}`)
      const body = await resp.json()
      events.value = body.events ?? []
    } finally {
      loading.value = false
    }
  },
  { immediate: true },
)

const totalLatency = computed(() => events.value.reduce((s, e) => s + (e.latency || 0), 0))
const totalTokens = computed(() => events.value.reduce((s, e) => s + (e.tokens || 0), 0))
const decisions = computed(() => events.value.filter((e) => e.event_type === 'AGENT_DECISION'))
const toolCalls = computed(() => events.value.filter((e) => e.event_type === 'TOOL_CALL' || e.event_type === 'TOOL_RESULT'))
const validations = computed(() => events.value.filter((e) => e.event_type === 'VALIDATION'))

function pretty(v: any): string {
  if (v === undefined || v === null) return '—'
  try {
    return JSON.stringify(v, null, 2)
  } catch {
    return String(v)
  }
}
</script>

<template>
  <div class="agent-detail">
    <div v-if="!nodeId" class="detail-empty">
      <el-empty description="点击工作流图中的节点查看 Agent 详情" :image-size="60" />
    </div>

    <template v-else>
      <div class="detail-header">
        <el-tag type="primary" effect="dark">{{ enZh(nodeId, NODE_ZH) }}</el-tag>
        <span class="meta">{{ events.length }} 个事件</span>
        <span class="meta">{{ totalLatency.toFixed(0) }}ms</span>
        <span class="meta">{{ totalTokens }} tokens</span>
      </div>

      <el-collapse v-model="openPanels" v-loading="loading">
        <el-collapse-item v-for="ev in events" :key="ev.id" :name="ev.id">
          <template #title>
            <div class="ev-title">
              <el-tag size="small" :type="ev.event_type.includes('ERROR') ? 'danger' : 'info'" effect="plain">
                {{ enZh(ev.event_type, EVENT_ZH) }}
              </el-tag>
              <span class="ev-meta" v-if="ev.latency">{{ ev.latency.toFixed(0) }}ms</span>
              <span class="ev-meta" v-if="ev.tokens">{{ ev.tokens }} tokens</span>
              <span class="ev-status" :class="ev.status" v-if="ev.status && ev.status !== 'success'">{{ ev.status }}</span>
            </div>
          </template>
          <div class="ev-body">
            <div class="ev-block">
              <div class="ev-label">Input</div>
              <pre class="ev-json">{{ pretty(ev.input) }}</pre>
            </div>
            <div class="ev-block">
              <div class="ev-label">Output</div>
              <pre class="ev-json">{{ pretty(ev.output) }}</pre>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </template>
  </div>
</template>

<style scoped>
.detail-empty {
  padding: 20px 0;
}
.detail-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.meta {
  color: #909399;
  font-size: 12px;
}
.ev-title {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.ev-meta {
  color: #c0c4cc;
  font-size: 12px;
}
.ev-status {
  font-size: 12px;
}
.ev-status.error {
  color: #f56c6c;
}
.ev-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ev-block {
  background: #f7f8fa;
  border-radius: 4px;
  padding: 8px;
}
.ev-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.ev-json {
  margin: 0;
  font-size: 12px;
  font-family: monospace;
  white-space: pre-wrap;
  word-break: break-all;
  color: #303133;
  max-height: 200px;
  overflow-y: auto;
}
</style>

