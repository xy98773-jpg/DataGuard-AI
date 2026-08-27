<script setup lang="ts">
import { computed, ref } from 'vue'
import { enZh, EVENT_ZH, NODE_ZH } from '../utils/i18n'

const props = defineProps<{
  events: any[]
}>()

const expanded = ref<Record<number, boolean>>({})

const sorted = computed(() => [...props.events].sort((a, b) => a.id - b.id))

function timeOf(ev: any): string {
  if (!ev.created_at) return ''
  const d = new Date(ev.created_at)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}:${String(d.getSeconds()).padStart(2, '0')}`
}

function tagType(ev: any): string {
  if (ev.event_type.includes('ERROR')) return 'danger'
  if (ev.event_type.includes('START')) return 'primary'
  if (ev.event_type.includes('DECISION')) return 'success'
  if (ev.event_type.includes('TOOL')) return 'warning'
  if (ev.event_type.includes('VALIDATION')) return 'info'
  if (ev.event_type.includes('APPROVAL')) return 'warning'
  return ''
}

function toggle(id: number) {
  expanded.value[id] = !expanded.value[id]
}

function pretty(obj: any): string {
  if (obj == null) return ''
  try {
    const s = JSON.stringify(obj, null, 2)
    return s.length > 8000 ? s.slice(0, 8000) + '\n…(已截断)' : s
  } catch {
    return String(obj)
  }
}

/** 事件内容的可读标题：Agent 决策/工具调用/验证结果 */
function contentTitle(ev: any): string {
  if (ev.event_type.includes('DECISION')) return 'Agent 决策输出'
  if (ev.event_type.includes('TOOL_CALL')) return '工具调用（参数）'
  if (ev.event_type.includes('TOOL_RESULT')) return '工具执行结果'
  if (ev.event_type.includes('VALIDATION')) return '验证结果'
  if (ev.event_type.includes('APPROVAL')) return '审批'
  return '事件内容'
}
</script>

<template>
  <div class="trace-panel">
    <el-empty v-if="!sorted.length" description="暂无追踪事件" :image-size="60" />
    <div v-for="ev in sorted" :key="ev.id" class="trace-item" @click="toggle(ev.id)">
      <div class="trace-head">
        <span class="trace-time">{{ timeOf(ev) }}</span>
        <el-tag size="small" :type="tagType(ev) as any" effect="plain">{{ enZh(ev.node, NODE_ZH) }}</el-tag>
        <el-tag size="small" type="info" effect="plain">{{ enZh(ev.event_type, EVENT_ZH) }}</el-tag>
        <span v-if="ev.latency" class="trace-meta">{{ ev.latency.toFixed(0) }}ms</span>
        <span v-if="ev.tokens" class="trace-meta">{{ ev.tokens }} tokens</span>
        <span class="trace-arrow">{{ expanded[ev.id] ? '▾' : '▸' }}</span>
      </div>
      <div v-if="ev.status && ev.status !== 'success'" class="trace-status error">
        {{ ev.status }}
      </div>
      <div v-if="expanded[ev.id] && (ev.input || ev.output)" class="trace-body">
        <div v-if="ev.input" class="trace-block">
          <div class="trace-block-title">输入（Input）</div>
          <pre>{{ pretty(ev.input) }}</pre>
        </div>
        <div v-if="ev.output" class="trace-block">
          <div class="trace-block-title">{{ contentTitle(ev) }}（Output）</div>
          <pre>{{ pretty(ev.output) }}</pre>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.trace-panel {
  max-height: 420px;
  overflow-y: auto;
}
.trace-item {
  padding: 6px 8px;
  border-left: 3px solid #e4e7ed;
  margin-bottom: 6px;
  background: #fafafa;
  border-radius: 0 4px 4px 0;
  cursor: pointer;
}
.trace-item:hover {
  background: #f5f7fa;
}
.trace-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.trace-time {
  color: #909399;
  font-size: 12px;
  font-family: monospace;
}
.trace-meta {
  color: #c0c4cc;
  font-size: 12px;
}
.trace-arrow {
  margin-left: auto;
  color: #c0c4cc;
}
.trace-status.error {
  color: #f56c6c;
  font-size: 12px;
  margin-top: 2px;
}
.trace-body {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed #e4e7ed;
}
.trace-block {
  margin-bottom: 6px;
}
.trace-block-title {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}
.trace-block pre {
  background: #303133;
  color: #e5eaf3;
  font-size: 12px;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  max-height: 260px;
  overflow-y: auto;
  margin: 0;
  font-family: 'JetBrains Mono', Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
