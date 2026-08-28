// e2e_reflection.mjs — 验证图谱渲染 reflection 节点（反思重规划）
import { chromium } from 'playwright-core'

const BE = 'http://127.0.0.1:8000'
const FE = 'http://localhost:5173'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
await page.goto(`${FE}/workflow`, { waitUntil: 'domcontentloaded' })
// 注入持久化 run，使图谱区域渲染 VueFlow
await page.evaluate(() => {
  localStorage.setItem('dg-active-run', JSON.stringify({ datasetId: 'ds_e60ff05b07', runId: 'run_588b5d3dbd' }))
})
await page.reload({ waitUntil: 'domcontentloaded' })
await page.waitForTimeout(6000)
const nodeLabels = await page.locator('.vue-flow__node').allTextContents()
console.log('图谱节点:', nodeLabels.join(' | '))
if (!nodeLabels.some((t) => t.includes('反思重规划'))) throw new Error('reflection 节点未渲染')
const edgeCount = await page.locator('.vue-flow__edge').count()
console.log('边数:', edgeCount)
await browser.close()
console.log('E2E REFLECTION PASS')
