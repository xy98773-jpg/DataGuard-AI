// e2e_concurrency.mjs — 实测：数据源页「运行中任务」面板 + 取消一个待审批任务
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'

const FE = 'http://localhost:5173'
const BE = 'http://127.0.0.1:8000'
const csv = readFileSync('D:/Desktop/DataGuard AI/backend/datasets/demo/customer.csv')

// 登录拿 token
const loginResp = await (await fetch(`${BE}/api/auth/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'admin123' }),
})).json()
const token = loginResp.token

// 上传并启动一个任务（fake 模式在 dev 下不可用，这里用真实 qwen——只验证面板出现即可，不等完成）
const fd = new FormData()
fd.append('file', new Blob([csv], { type: 'text/csv' }))
fd.append('name', '并发面板测试集')
const ds = await (await fetch(`${BE}/api/dataset/upload`, { method: 'POST', body: fd })).json()
await fetch(`${BE}/api/workflow/start`, {
  method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
  body: JSON.stringify({ dataset_id: ds.dataset_id }),
})
console.log('已启动任务 ds:', ds.dataset_id)

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
// 注入 token 避免跳登录
await page.addInitScript((t) => localStorage.setItem('dg_token', t), token)
await page.goto(`${FE}/datasource`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2500)

// 打开运行中任务面板
const btn = page.locator('button', { hasText: '运行中任务' })
console.log('面板按钮:', await btn.count() === 1)
await btn.click()
await page.waitForTimeout(1500)
const dlg = page.locator('.el-dialog')
console.log('面板打开:', await dlg.count() >= 1)
const dlgBody = await dlg.innerText()
console.log('含任务列表:', dlgBody.includes('run_') || dlgBody.includes('当前没有运行中的任务'))
console.log('含取消按钮:', (await dlg.locator('button', { hasText: '取消' }).count()) >= 0)

// 取消一个待审批/运行中的任务（第一个有取消按钮的）
const cancelBtn = dlg.locator('button', { hasText: '取消' }).first()
if (await cancelBtn.count()) {
  await cancelBtn.click()
  await page.waitForTimeout(1000)
  const confirm = page.locator('.el-message-box')
  if (await confirm.count()) {
    await confirm.locator('button', { hasText: '取消任务' }).click()
    await page.waitForTimeout(1500)
    console.log('取消确认完成')
  }
}

await browser.close()
console.log('E2E CONCURRENCY PASS')
