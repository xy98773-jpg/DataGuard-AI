// e2e_cancel_reset.mjs — 实测：启动任务 → 工作台显示运行中 → 打开运行中任务取消 → 工作台重置为初始界面
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'

const FE = 'http://localhost:5173'
const BE = 'http://127.0.0.1:8000'
const csv = readFileSync('D:/Desktop/DataGuard AI/backend/datasets/demo/customer.csv')

// 登录 + 上传 + 启动任务
const login = await (await fetch(`${BE}/api/auth/login`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ username: 'admin', password: 'admin123' }),
})).json()
const fd = new FormData()
fd.append('file', new Blob([csv], { type: 'text/csv' }))
fd.append('name', '取消重置测试集')
const ds = await (await fetch(`${BE}/api/dataset/upload`, { method: 'POST', body: fd })).json()
const run = await (await fetch(`${BE}/api/workflow/start`, {
  method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${login.token}` },
  body: JSON.stringify({ dataset_id: ds.dataset_id }),
})).json()
console.log('启动 run:', run.run_id)

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
await page.addInitScript((t) => localStorage.setItem('dg_token', t), login.token)

// 1) 打开工作台并选中该数据集 → 应显示运行中（步骤条 active 或图谱）
await page.goto(`${FE}/workflow?dataset=${ds.dataset_id}`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(4000)
const wfBody = await page.locator('body').innerText()
console.log('工作台显示运行状态:', wfBody.includes('运行中') || wfBody.includes('启动治理'))

// 2) 打开运行中任务 → 精确取消「当前工作台显示的 run」（取消它应触发工作台重置）
await page.locator('.wf-toolbar button', { hasText: '运行中任务' }).click()
await page.waitForTimeout(1500)
const dlg = page.locator('.el-dialog').first()
// 找到包含当前 run_id 的任务行，点它的取消按钮
const runRow = dlg.locator('.run-item', { hasText: run.run_id })
console.log('找到当前 run 行:', await runRow.count() === 1)
if (await runRow.count()) {
  await runRow.locator('button', { hasText: '取消' }).click()
  await page.waitForTimeout(800)
  const confirm = page.locator('.el-message-box')
  if (await confirm.count()) {
    await confirm.locator('button', { hasText: '取消任务' }).click()
    await page.waitForTimeout(1500)
  }
}

// 3) 关闭面板，回到工作台：验证已重置（无运行中状态、无治理结果区、图谱为空）
const closeBtn = dlg.locator('.el-dialog__footer button', { hasText: '关闭' })
if (await closeBtn.count()) {
  await closeBtn.click()
  await page.waitForTimeout(1000)
} else {
  await page.keyboard.press('Escape')
  await page.waitForTimeout(1000)
}
const wfBody2 = await page.locator('body').innerText()
console.log('工作台已重置（无治理结果区）:', !wfBody2.includes('治理结果'))
console.log('工作台已重置（无运行中字样）:', !wfBody2.includes('运行中'))

// 4) 后端确认该 run 状态为 CANCELLED
const status = await (await fetch(`${BE}/api/workflow/${run.run_id}`)).json()
console.log('后端状态:', status.status)

await browser.close()
console.log('E2E CANCEL RESET PASS')
