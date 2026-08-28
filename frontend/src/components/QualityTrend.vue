<script setup lang="ts">
// 质量趋势弹窗：ECharts 折线（治理前灰虚线 → 治理后蓝实线渐变面积）+ 明细表
// 数据自拉 GET /api/dashboard/stats 的 quality_trend（真实历史评分）
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()

const trend = ref<any[]>([])
const loading = ref(false)
const chartEl = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null

async function loadTrend() {
  if (!props.open) return
  loading.value = true
  try {
    const resp = await fetch('/api/dashboard/stats')
    const body = await resp.json()
    trend.value = body.quality_trend ?? []
  } catch {
    trend.value = []
  } finally {
    loading.value = false
    await nextTick()  // 等 v-if 渲染出 chartEl 容器
    renderChart()
  }
}

function renderChart() {
  if (!chartEl.value) return
  if (!chart) chart = echarts.init(chartEl.value)
  const list = trend.value
  if (list.length < 2) {
    chart?.clear()
    return
  }
  const names = list.map((r) => (r.dataset_name || '').slice(0, 8))
  const before = list.map((r) => r.before_score)
  const after = list.map((r) => r.after_score)
  const minY = Math.floor(Math.min(...after, ...before) / 5) * 5 - 2
  chart.setOption(
    {
      tooltip: {
        trigger: 'axis',
        formatter(params: any[]) {
          const i = params[0]?.dataIndex ?? 0
          const r = list[i]
          const dt = (r.created_at || '').slice(0, 16).replace('T', ' ')
          return `<b>${r.dataset_name}</b><br/>${dt}<br/>治理前：<span style="color:#c0c4cc">${r.before_score}</span> → 治理后：<span style="color:#409eff;font-weight:700">${r.after_score}</span>（▲ ${(r.after_score - r.before_score).toFixed(2)}）`
        },
      },
      legend: { data: ['治理前', '治理后'], top: 0, textStyle: { fontSize: 13, color: '#606266' } },
      grid: { left: 52, right: 24, top: 40, bottom: 48 },
      xAxis: {
        type: 'category',
        data: names,
        axisLabel: {
          fontSize: 12,
          color: '#606266',
          interval: 0,
          margin: 12,
          // 超过 4 字自动换两行显示，避免旋转遮挡
          formatter: (v: string) => {
            const arr = v.split('')
            if (arr.length <= 4) return v
            const mid = Math.ceil(arr.length / 2)
            return arr.slice(0, mid).join('') + '\n' + arr.slice(mid).join('')
          },
        },
        axisLine: { lineStyle: { color: '#dcdfe6' } },
      },
      yAxis: {
        type: 'value',
        min: minY,
        max: 100,
        axisLabel: { fontSize: 13, color: '#606266', fontWeight: 600 },
        splitLine: { lineStyle: { color: '#f0f2f5' } },
      },
      series: [
        {
          name: '治理前',
          type: 'line',
          data: before,
          symbol: 'circle',
          symbolSize: 7,
          lineStyle: { width: 2, type: 'dashed', color: '#c0c4cc' },
          itemStyle: { color: '#c0c4cc' },
        },
        {
          name: '治理后',
          type: 'line',
          data: after,
          symbol: 'circle',
          symbolSize: 8,
          lineStyle: { width: 3, color: '#409eff' },
          itemStyle: { color: '#409eff' },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(64,158,255,0.35)' },
              { offset: 1, color: 'rgba(64,158,255,0.03)' },
            ]),
          },
          label: {
            show: true,
            position: 'top',
            formatter: (p: any) => `${p.data}`,
            fontSize: 12,
            fontWeight: 700,
            color: '#409eff',
            distance: 6,
          },
        },
      ],
    },
    true,
  )
  chart.resize()
}

watch(() => props.open, (v) => { if (v) { loadTrend(); setTimeout(() => chart?.resize(), 250) } })
watch(trend, async () => { await nextTick(); renderChart() })
onMounted(loadTrend)
onBeforeUnmount(() => { chart?.dispose(); chart = null })

function onResize() {
  chart?.resize()
}
window.addEventListener('resize', onResize)
onBeforeUnmount(() => window.removeEventListener('resize', onResize))
</script>

<template>
  <el-dialog
    :model-value="props.open"
    @update:model-value="(v: boolean) => emit('update:open', v)"
    width="72%"
    align-center
    class="quality-trend-dialog"
  >
    <template #header>
      <span class="trend-title">📈 质量趋势（最近 {{ trend.length }} 次治理）</span>
    </template>
    <div v-loading="loading">
      <template v-if="trend.length >= 2">
        <div ref="chartEl" class="trend-chart" />
        <el-table :data="trend" size="small" max-height="300" class="trend-table">
          <el-table-column label="数据集" prop="dataset_name" show-overflow-tooltip />
          <el-table-column label="治理时间" width="160">
            <template #default="{ row }">{{ row.created_at?.slice(0, 16)?.replace('T', ' ') }}</template>
          </el-table-column>
          <el-table-column label="治理前" width="90">
            <template #default="{ row }">{{ row.before_score }}</template>
          </el-table-column>
          <el-table-column label="治理后" width="90">
            <template #default="{ row }"><span class="up-score">{{ row.after_score }}</span></template>
          </el-table-column>
          <el-table-column label="提升" width="90">
            <template #default="{ row }"><span class="up-score">▲ {{ (row.after_score - row.before_score).toFixed(2) }}</span></template>
          </el-table-column>
        </el-table>
      </template>
      <el-empty v-else description="暂无足够的治理历史（完成 ≥2 次治理后展示趋势）" :image-size="60" />
    </div>
  </el-dialog>
</template>

<style scoped>
.trend-title {
  font-size: 16px;
  font-weight: 700;
  color: #303133;
}
.trend-chart {
  width: 100%;
  height: 320px;
}
.trend-table {
  margin-top: 6px;
}
.up-score {
  color: #67c23a;
  font-weight: 700;
}
</style>
