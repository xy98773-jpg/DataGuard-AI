// e2e_dashboard_mgmt.mjs — 验证首页数据集管理：自定义名显示 + 搜索筛选 + 状态/问题数 + Issues 跳转筛选
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'

const BE = 'http://127.0.0.1:8000'
const FE = 'http://localhost:5173'
const csv = readFileSync('D:/Desktop/DataGuard AI/backend/datasets/demo/customer.csv')

// 1) 上传带自定义名的数据集
const fd = new FormData()
fd.append('file', new Blob([csv], { type: 'text/csv' }))
fd.append('name', '首页验证数据ABC')
const up = await (await fetch(`${BE}/api/dataset/upload`, { method: 'POST', body: fd })).json()
console.log('uploaded:', up.dataset_id, up.name)

// 2) 跑一次治理产生问题数
await (await fetch(`${BE}/api/workflow/start`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ dataset_id: up.dataset_id }),
})).json()

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()

// 3) Dashboard：自定义名显示 + 状态/问题数
await page.goto(`${FE}/dashboard`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(4000)
const body1 = await page.locator('body').innerText()
console.log('Dashboard 含自定义名:', body1.includes('首页验证数据ABC'))
if (!body1.includes('首页验证数据ABC')) throw new Error('自定义名未显示')

// 4) 搜索框过滤
await page.fill('input[placeholder="搜索数据集名称 / 文件名"]', '首页验证数据ABC')
await page.waitForTimeout(2500)
const rows = await page.locator('.ds-card .el-table__row').count()
console.log('搜索后行数:', rows)
if (rows !== 1) throw new Error('搜索过滤失败')

// 5) Issues 跳转筛选（?dataset=xxx）
await page.goto(`${FE}/issues?dataset=${up.dataset_id}`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3500)
const body2 = await page.locator('body').innerText()
console.log('Issues 含自定义名分组:', body2.includes('首页验证数据ABC'))
if (!body2.includes('首页验证数据ABC')) throw new Error('Issues 分组未显示自定义名')

await browser.close()
console.log('E2E DASHBOARD MGMT PASS')
