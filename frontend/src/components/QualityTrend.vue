<script setup lang="ts">
// 质量趋势弹窗：SVG 双折线（治理前灰虚线 → 治理后蓝实线）+ 明细表
// 数据自拉 GET /api/dashboard/stats 的 quality_trend（真实历史评分）
import { computed, onMounted, ref, watch } from 'vue'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ (e: 'update:open', v: boolean): void }>()

const trend = ref<any[]>([])
const loading = ref(false)

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
  }
}
watch(() => props.open, (v) => { if (v) loadTrend() })
onMounted(loadTrend)

// SVG points（viewBox 800x220，Y 轴 0-100 映射）
function trendPoints(field: 'before_score' | 'after_score'): string {
  const list = trend.value
  if (list.length < 2) return ''
  const n = list.length
  return list
    .map((r: any, i: number) => {
      const x = 40 + (i * 700) / (n - 1)
      const y = 190 - (r[field] ?? 0) * 1.5
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}
const trendXLabels = computed(() =>
  trend.value.map((r: any, i: number, arr: any[]) => {
    const label = (r.dataset_name || '').slice(0, 8)
    const x = 40 + (i * 700) / Math.max(arr.length - 1, 1)
    return { label, x: x.toFixed(1) }
  }),
)
const lastScore = computed(() => (trend.value.length ? trend.value[trend.value.length - 1].after_score : null))
</script>

<template>
  <el-dialog
    :model-value="props.open"
    @update:model-value="(v: boolean) => emit('update:open', v)"
    width="70%"
    align-center
    class="quality-trend-dialog"
  >
    <template #header>
      <span class="trend-title">📈 质量趋势（最近 {{ trend.length }} 次治理）</span>
    </template>
    <div v-loading="loading">
      <template v-if="trend.length >= 2">
        <svg viewBox="0 0 800 220" class="trend-svg" preserveAspectRatio="xMidYMid meet">
          <!-- Y 轴网格（50/75/100） -->
          <line x1="40" y1="115" x2="750" y2="115" stroke="#f0f2f5" stroke-width="1" />
          <line x1="40" y1="77.5" x2="750" y2="77.5" stroke="#f0f2f5" stroke-width="1" />
          <line x1="40" y1="40" x2="750" y2="40" stroke="#f0f2f5" stroke-width="1" />
          <text x="8" y="118" class="axis">50</text>
          <text x="8" y="80.5" class="axis">75</text>
          <text x="8" y="43" class="axis">100</text>
          <!-- before（灰虚线） / after（蓝实线） -->
          <polyline :points="trendPoints('before_score')" fill="none" stroke="#c0c4cc" stroke-width="2" stroke-dasharray="5,4" />
          <polyline :points="trendPoints('after_score')" fill="none" stroke="#409eff" stroke-width="2.5" />
          <!-- 末端 after 分数标注 -->
          <text v-if="lastScore != null" :x="750" :y="190 - lastScore * 1.5 - 6" text-anchor="end" class="score-end">{{ lastScore }}</text>
          <!-- 底部数据集短名 -->
          <text v-for="(l, i) in trendXLabels" :key="i" :x="l.x" y="210" text-anchor="middle" class="axis-label">{{ l.label }}</text>
        </svg>
        <div class="trend-legend">
          <span class="lg lg-before">治理前</span>
          <span class="lg lg-after">治理后</span>
        </div>
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
.trend-svg {
  width: 100%;
  height: 210px;
  display: block;
}
.trend-svg .axis {
  font-size: 13px;
  fill: #606266;
  font-weight: 600;
}
.trend-svg .axis-label {
  font-size: 12px;
  fill: #606266;
}
.trend-svg .score-end {
  font-size: 15px;
  font-weight: 700;
  fill: #409eff;
}
.trend-legend {
  display: flex;
  gap: 16px;
  margin: 8px 0 12px;
  font-size: 13px;
  color: #303133;
}
.trend-legend .lg::before {
  content: '';
  display: inline-block;
  width: 22px;
  height: 3px;
  vertical-align: middle;
  margin-right: 6px;
}
.lg-before::before {
  background: #c0c4cc;
  background-image: linear-gradient(90deg, #c0c4cc 50%, transparent 50%);
  background-size: 8px 3px;
}
.lg-after::before {
  background: #409eff;
}
.trend-table {
  margin-top: 4px;
}
.up-score {
  color: #67c23a;
  font-weight: 700;
}
</style>
