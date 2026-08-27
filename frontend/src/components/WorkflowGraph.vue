<script setup lang="ts">
import { computed } from 'vue'
import { MarkerType, VueFlow, type Edge, type Node } from '@vue-flow/core'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import { NODE_ZH } from '../utils/i18n'
import { enZh } from '../utils/i18n'

const props = defineProps<{
  nodeStates: Record<string, string>  // node id -> waiting|running|success|failed
  status: string  // RUNNING | SUCCESS | FAILED | WAITING_APPROVAL ...
}>()

const emit = defineEmits<{ (e: 'node-click', id: string): void }>()

interface NodeDef {
  id: string
  x: number
  y: number
}

const NODE_DEFS: NodeDef[] = [
  { id: 'supervisor', x: 300, y: 0 },
  { id: 'profiler', x: 300, y: 95 },
  { id: 'inspector', x: 300, y: 190 },
  { id: 'planner', x: 300, y: 285 },
  { id: 'plan_validator', x: 500, y: 285 },
  { id: 'risk', x: 700, y: 285 },
  { id: 'approval', x: 700, y: 400 },
  { id: 'execution', x: 500, y: 400 },
  { id: 'validator', x: 300, y: 500 },
  { id: 'reflection', x: 80, y: 380 },
]

function onNodeClick(ev: any) {
  emit('node-click', ev.node.id)
}

const nodes = computed<Node[]>(() =>
  NODE_DEFS.map((d) => {
    const st = props.nodeStates?.[d.id] ?? 'waiting'
    const cls =
      st === 'running' ? 'dg-node running' : st === 'success' ? 'dg-node success' : st === 'failed' ? 'dg-node failed' : 'dg-node'
    return {
      id: d.id,
      position: { x: d.x, y: d.y },
      class: cls,
      label: enZh(d.id, NODE_ZH),
      data: { label: enZh(d.id, NODE_ZH) },
    }
  }),
)

const edges = computed<Edge[]>(() => [
  { id: 'e1', source: 'supervisor', target: 'profiler', label: '路由' },
  { id: 'e2', source: 'profiler', target: 'inspector' },
  { id: 'e3', source: 'inspector', target: 'planner' },
  { id: 'e4', source: 'planner', target: 'plan_validator' },
  {
    id: 'e5',
    source: 'plan_validator',
    target: 'risk',
    label: '通过',
    markerEnd: MarkerType.ArrowClosed,
  },
  {
    id: 'e6',
    source: 'plan_validator',
    target: 'planner',
    label: '拒绝',
    style: { strokeDasharray: '5 5' },
    markerEnd: MarkerType.ArrowClosed,
  },
  {
    id: 'e7',
    source: 'risk',
    target: 'approval',
    label: '需审批',
    markerEnd: MarkerType.ArrowClosed,
  },
  {
    id: 'e8',
    source: 'risk',
    target: 'execution',
    label: '自动',
    markerEnd: MarkerType.ArrowClosed,
  },
  {
    id: 'e9',
    source: 'approval',
    target: 'execution',
    label: '批准',
    markerEnd: MarkerType.ArrowClosed,
  },
  { id: 'e10', source: 'execution', target: 'validator' },
  {
    id: 'e11',
    source: 'validator',
    target: 'reflection',
    label: '失败',
    style: { strokeDasharray: '5 5' },
    markerEnd: MarkerType.ArrowClosed,
  },
  { id: 'e12', source: 'reflection', target: 'planner', label: '重规划' },
])
</script>

<template>
  <div class="workflow-graph">
    <VueFlow :nodes="nodes" :edges="edges" :fit-view-on-init="true" :nodes-draggable="false" :nodes-connectable="false" @node-click="onNodeClick" />
    <div class="graph-legend">
      <span class="legend-item"><i class="dot running" />执行中</span>
      <span class="legend-item"><i class="dot success" />已完成</span>
      <span class="legend-item"><i class="dot failed" />失败</span>
      <span class="legend-item"><i class="dot waiting" />等待</span>
    </div>
  </div>
</template>

<style>
.workflow-graph {
  height: 580px;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  position: relative;
  background: #fafafa;
}
.workflow-graph .vue-flow__node {
  font-size: 13px;
  border-radius: 8px;
  padding: 8px 14px;
  border: 1px solid #dcdfe6;
  background: #fff;
  min-width: 100px;
  text-align: center;
}
.workflow-graph .dg-node.running {
  border-color: #409eff;
  background: #ecf5ff;
  box-shadow: 0 0 8px rgba(64, 158, 255, 0.4);
  color: #409eff;
  font-weight: 600;
}
.workflow-graph .dg-node.success {
  border-color: #67c23a;
  background: #f0f9eb;
  color: #67c23a;
}
.workflow-graph .dg-node.failed {
  border-color: #f56c6c;
  background: #fef0f0;
  color: #f56c6c;
}
.graph-legend {
  position: absolute;
  bottom: 8px;
  right: 12px;
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: #909399;
  background: rgba(255, 255, 255, 0.85);
  padding: 4px 10px;
  border-radius: 6px;
}
.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dot.running { background: #409eff; }
.dot.success { background: #67c23a; }
.dot.failed { background: #f56c6c; }
.dot.waiting { background: #dcdfe6; }
</style>
