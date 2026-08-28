// debug_running_tasks.mjs — 实测运行中任务面板的真实 DOM
import { chromium } from 'playwright-core'

const FE = 'http://localhost:5173'
const BE = 'http://127.0.0.1:8000'

// 登录拿 token
const loginResp = await (await fetch(`${BE}/api/auth/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'admin123' }),
})).json()
const token = loginResp.token

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
await page.addInitScript((t) => localStorage.setItem('dg_token', t), token)
await page.goto(`${FE}/datasource`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2500)

// 打开运行中任务面板
await page.locator('button', { hasText: '运行中任务' }).click()
await page.waitForTimeout(1500)

// 打印弹窗完整 HTML 结构
const html = await page.locator('.el-dialog').first().evaluate((el) => el.outerHTML.slice(0, 3000))
console.log('--- 弹窗 HTML ---')
console.log(html)

// 统计按钮
const btns = await page.locator('.el-dialog button').allInnerTexts()
console.log('--- 弹窗内按钮 ---')
console.log(JSON.stringify(btns))

await browser.close()
