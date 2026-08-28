// e2e_twostep_upload.mjs — 实测两段式上传：先选文件（不立即上传）→ 后填名字 → 点「开始上传」→ name 带上
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'

const BE = 'http://127.0.0.1:8000'
const FE = 'http://localhost:5173'
const csv = readFileSync('D:/Desktop/DataGuard AI/backend/datasets/demo/customer.csv')

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
await page.goto(`${FE}/workflow`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3000)

// 1) 先选文件（此刻不应上传，按钮应为「请先选择文件」→ 选后变「开始上传」）
const before = await page.locator('button.upload-btn').innerText()
console.log('选文件前按钮:', before)
if (!before.includes('请先选择文件')) throw new Error('未选文件时按钮状态错误')

await page.locator('input[type="file"]').setInputFiles({ name: 'customer.csv', mimeType: 'text/csv', buffer: csv })
await page.waitForTimeout(1000)
const after = await page.locator('button.upload-btn').innerText()
const pendingText = await page.locator('.pending-file').innerText()
console.log('选文件后按钮:', after, '| 已选提示:', pendingText)
if (!after.includes('开始上传')) throw new Error('选文件后按钮未变「开始上传」')
if (!pendingText.includes('customer.csv')) throw new Error('已选文件提示缺失')

// 2) 后填名字（模拟用户先选文件再填名）
await page.locator('input[placeholder*="数据集名称"]').fill('两段式实测名')

// 3) 点开始上传
await page.locator('button.upload-btn').click()
await page.waitForTimeout(5000)

// 4) 后端最新数据集 name 必须=两段式实测名
const list = await (await fetch(`${BE}/api/dataset/list?limit=1`)).json()
const top = list.datasets[0]
console.log('后端最新:', `${top.name}(${top.filename})`)
if (top.name !== '两段式实测名') throw new Error(`name 未带上: ${top.name}`)

// 5) 上传成功后按钮复位
const finalBtn = await page.locator('button.upload-btn').innerText()
console.log('上传后按钮:', finalBtn)

await browser.close()
console.log('E2E TWOSTEP UPLOAD PASS')
