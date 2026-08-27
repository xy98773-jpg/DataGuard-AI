import { chromium } from 'playwright-core'

// 完整流程：localStorage 残留旧 run → 从注册页跳转（query.dataset）→ 治理 → 查看报告
const OLD_DS = 'ds_c9d46a3dff'
const OLD_RUN = 'run_e63c8ed9d6'
const NEW_DS = 'ds_2c515a583d' // worldometers 数据集（234 行，未治理）

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
page.on('pageerror', (err) => console.log('[pageerror]', err.message))

await page.addInitScript(({ oldDs, oldRun }) => {
  localStorage.setItem('dg-active-run', JSON.stringify({ datasetId: oldDs, runId: oldRun }))
}, { oldDs: OLD_DS, oldRun: OLD_RUN })

// 1. 跳转（模拟注册后点「治理 →」）
await page.goto(`http://localhost:5173/workflow?dataset=${NEW_DS}`, { waitUntil: 'networkidle', timeout: 30000 }).catch((e) => console.log('[goto]', e.message))
await page.waitForTimeout(1500)
console.log('跳转后旧按钮数量（应 0）:', await page.locator('text=查看完整报告').count())

// 2. 点击开始治理
await page.locator('text=开始治理').first().click()
console.log('已点击开始治理')

// 3. 轮询状态直到 SUCCESS（审批用 API 通过）
let runId = ''
for (let i = 0; i < 8; i++) {
  await page.waitForTimeout(1000)
  runId = (await page.locator('.run-id').first().textContent().catch(() => '')) || ''
  if (runId) break
}
console.log('run_id:', runId || '(页面未显示)')

let status = 'RUNNING'
for (let i = 0; i < 25; i++) {
  await page.waitForTimeout(3000)
  if (!runId) continue
  const resp = await page.request.get(`http://127.0.0.1:8000/api/workflow/${runId}`).catch(() => null)
  if (!resp) continue
  const body = await resp.json().catch(() => ({}))
  status = body.status || 'RUNNING'
  console.log(`t=${(i + 1) * 3}s status=${status}`)
  if (status === 'WAITING_APPROVAL') {
    await page.request.post('http://127.0.0.1:8000/api/approval/approve', { data: { run_id: runId } })
    console.log('已审批通过')
  }
  if (status === 'SUCCESS' || status === 'FAILED') break
}
console.log('最终状态:', status)

// 4. 等页面 loadResults 拉取 outputs，检查按钮 + 报告内容
for (let i = 0; i < 10; i++) {
  const btn = await page.locator('text=查看完整报告').count()
  if (btn > 0) break
  await page.waitForTimeout(1000)
}
const btnCount = await page.locator('text=查看完整报告').count()
console.log('治理后查看完整报告按钮（应 1）:', btnCount)

if (btnCount > 0) {
  await page.locator('text=查看完整报告').first().click()
  await page.waitForTimeout(1500)
  const dialog = await page.locator('.el-dialog').count()
  console.log('dialog 数量（应 1）:', dialog)
  const dialogText = (await page.locator('.el-dialog').first().textContent().catch(() => '')) || ''
  // 新数据特征：worldometers 列名（Population / Yearly Change / Density）
  const hasNew = dialogText.includes('Population') || dialogText.includes('Yearly Change') || dialogText.includes('Density')
  console.log('报告包含新数据特征(Population):', hasNew)
  console.log('报告包含旧数据特征(customer_id):', dialogText.includes('customer_id'))
}

function NEW_RUN() {
  return ''
}
await browser.close()
