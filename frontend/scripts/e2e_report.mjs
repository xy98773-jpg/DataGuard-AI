import { chromium } from 'playwright-core'

// 用已知有报告数据的 run 恢复前端状态（ds_c9d46a3dff / run_e63c8ed9d6 已 SUCCESS）
const DS = process.env.DS || 'ds_c9d46a3dff'
const RUN = process.env.RUN || 'run_e63c8ed9d6'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
page.on('console', (msg) => console.log('[console]', msg.type(), msg.text()))
page.on('pageerror', (err) => console.log('[pageerror]', err.message))

await page.addInitScript(({ ds, run }) => {
  localStorage.setItem('dg-active-run', JSON.stringify({ datasetId: ds, runId: run }))
}, { ds: DS, run: RUN })

await page.goto('http://localhost:5173/workflow', { waitUntil: 'networkidle', timeout: 30000 }).catch((e) => console.log('[goto]', e.message))

// 等待按钮出现（loadResults 拉取 outputs 后）
let btnCount = 0
for (let i = 0; i < 20; i++) {
  btnCount = await page.locator('text=查看完整报告').count()
  if (btnCount > 0) break
  await page.waitForTimeout(1000)
}
console.log('查看完整报告 按钮数量:', btnCount)
const dlCount = await page.locator('text=下载 cleaned.csv').count()
console.log('下载按钮数量:', dlCount)

if (btnCount > 0) {
  console.log('--- 点击查看完整报告 ---')
  await page.locator('text=查看完整报告').first().click()
  await page.waitForTimeout(1500)
  const dialogCount = await page.locator('.el-dialog').count()
  const overlayCount = await page.locator('.el-overlay').count()
  const reportTitle = await page.locator('.el-dialog__header').count()
  console.log('el-dialog 数量:', dialogCount, '| overlay 数量:', overlayCount, '| dialog header:', reportTitle)
  const headerText = (await page.locator('.el-dialog__header').first().textContent().catch(() => '')) || ''
  console.log('dialog header 文本:', headerText.slice(0, 80))
  // 展开检查：dialog 是否可见
  const visible = await page.locator('.el-dialog').first().isVisible().catch(() => false)
  console.log('dialog visible:', visible)
  // 检查 body 是否有报错痕迹（Vue 错误会挂载到 body）
  const errText = await page.locator('body').textContent().catch(() => '')
  console.log('body 包含 VUE ERROR:', errText.includes('Vue') && errText.includes('error'))
}

await browser.close()
