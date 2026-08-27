import { chromium } from 'playwright-core'

// 模拟场景：localStorage 残留旧 run（run_e63c8ed9d6/ds_c9d46a3dff），
// 然后从 DataSource 注册页带新数据集 ds_2c515a583d 跳转到 /workflow?dataset=...
const OLD_DS = 'ds_c9d46a3dff'
const OLD_RUN = 'run_e63c8ed9d6'
const NEW_DS = 'ds_2c515a583d' // 刚注册的 web 数据集（无治理）

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
page.on('pageerror', (err) => console.log('[pageerror]', err.message))

await page.addInitScript(({ oldDs, oldRun }) => {
  localStorage.setItem('dg-active-run', JSON.stringify({ datasetId: oldDs, runId: oldRun }))
}, { oldDs: OLD_DS, oldRun: OLD_RUN })

await page.goto(`http://localhost:5173/workflow?dataset=${NEW_DS}`, { waitUntil: 'networkidle', timeout: 30000 }).catch((e) => console.log('[goto]', e.message))
await page.waitForTimeout(2000)

const reportBtn = await page.locator('text=查看完整报告').count()
const statusTag = await page.locator('.run-id').count()
const emptyText = await page.locator('text=① 上传或选择左侧数据集').count()
console.log('查看完整报告按钮（应为 0）:', reportBtn)
console.log('运行任务标签（应为 0）:', statusTag)
console.log('空状态提示（应 >0）:', emptyText)

// 左侧数据集信息应显示新数据集 web.web
const dsInfo = (await page.locator('.el-descriptions').first().textContent().catch(() => '')) || ''
console.log('数据集信息包含 web.web:', dsInfo.includes('web.web'))

await browser.close()
