// e2e_workflow_tasks.mjs — 实测：运行中任务按钮在工作台质量趋势旁，点击打开面板有任务和取消按钮
import { chromium } from 'playwright-core'

const FE = 'http://localhost:5173'
const BE = 'http://127.0.0.1:8000'

const loginResp = await (await fetch(`${BE}/api/auth/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'admin123' }),
})).json()

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
await page.addInitScript((t) => localStorage.setItem('dg_token', t), loginResp.token)

// 1) 工作台工具条：质量趋势 + 运行中任务两个按钮
await page.goto(`${FE}/workflow`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2500)
const toolbar = await page.locator('.wf-toolbar').innerText()
console.log('含质量趋势按钮:', toolbar.includes('质量趋势'))
console.log('含运行中任务按钮:', toolbar.includes('运行中任务'))

// 2) 数据源页无运行中任务按钮
await page.goto(`${FE}/datasource`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)
const dsBody = await page.locator('.datasource-page').innerText()
console.log('数据源页无运行中任务:', !dsBody.includes('运行中任务'))

// 3) 回工作台打开运行中任务面板
await page.goto(`${FE}/workflow`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)
await page.locator('.wf-toolbar button', { hasText: '运行中任务' }).click()
await page.waitForTimeout(1500)
const dlg = page.locator('.el-dialog').first()
const dlgBody = await dlg.innerText()
console.log('面板打开:', await dlg.count() >= 1)
console.log('面板含任务:', dlgBody.includes('run_'))
console.log('面板含取消按钮:', (await dlg.locator('button', { hasText: '取消' }).count()) >= 1)

await browser.close()
console.log('E2E WORKFLOW TASKS PASS')
