// e2e_rename.mjs — 实测：首页数据集列表「改名」→ 弹窗 → PATCH → 列表/问题中心显示新名
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'

const BE = 'http://127.0.0.1:8000'
const FE = 'http://localhost:5173'
const csv = readFileSync('D:/Desktop/DataGuard AI/backend/datasets/demo/customer.csv')

// 1) API 上传一个未命名的数据集
const fd = new FormData()
fd.append('file', new Blob([csv], { type: 'text/csv' }))
fd.append('name', 'E2E改名前置')
const up = await (await fetch(`${BE}/api/dataset/upload`, { method: 'POST', body: fd })).json()
console.log('uploaded:', up.dataset_id, up.name)

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()

// 2) 打开首页，找到该数据集所在行，点「改名」
await page.goto(`${FE}/dashboard`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(4000)
const row = page.locator('.ds-card .el-table__row', { hasText: 'E2E改名前置' })
console.log('目标行数:', await row.count())
if (!(await row.count())) throw new Error('上传的数据集未出现在首页列表')
await row.locator('button', { hasText: '改名' }).click()
await page.waitForTimeout(1000)

// 3) 弹窗输入新名并保存
const dialog = page.locator('.el-message-box')
await dialog.locator('input').fill('E2E改名后数据集')
await dialog.locator('button', { hasText: '保存' }).click()
await page.waitForTimeout(3000)

// 4) 断言列表显示新名 + 后端确认
const body = await page.locator('.ds-card').innerText()
console.log('列表含新名:', body.includes('E2E改名后数据集'))
if (!body.includes('E2E改名后数据集')) throw new Error('改名后列表未显示新名')

const list = await (await fetch(`${BE}/api/dataset/list?limit=50`)).json()
const item = list.datasets.find((d) => d.id === up.dataset_id)
console.log('后端 name:', item?.name)
if (item?.name !== 'E2E改名后数据集') throw new Error('后端 name 未更新')

// 5) 问题中心跳转也显示新名
await page.goto(`${FE}/issues?dataset=${up.dataset_id}`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3000)
const body2 = await page.locator('body').innerText()
console.log('问题中心含新名:', body2.includes('E2E改名后数据集'))

await browser.close()
console.log('E2E RENAME PASS')
