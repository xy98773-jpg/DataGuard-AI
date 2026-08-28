// e2e_upload_name.mjs — 复现：UI 填自定义名上传，查后端是否存 name
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'

const FE = 'http://localhost:5173'
const csv = readFileSync('D:/Desktop/DataGuard AI/backend/datasets/demo/customer.csv')

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
await page.goto(`${FE}/workflow`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3000)

// 1) 填自定义名输入框
const nameInput = page.locator('input[placeholder*="数据集名称"]')
console.log('名称输入框数量:', await nameInput.count())
if (await nameInput.count()) {
  await nameInput.fill('UI实测命名ABC')
  console.log('已填写:', await nameInput.inputValue())
}

// 2) 上传文件（el-upload 隐藏 input）
const fileInput = page.locator('input[type="file"]')
console.log('文件输入框数量:', await fileInput.count())
if (await fileInput.count()) {
  await fileInput.setInputFiles({ name: 'customer.csv', mimeType: 'text/csv', buffer: csv })
}

// 3) 等上传完成提示
await page.waitForTimeout(6000)
const body = await page.locator('body').innerText()
console.log('上传成功提示:', body.includes('已上传') ? body.split('\n').find((l) => l.includes('已上传')) : '无')

// 4) 查后端最新数据集的 name
const list = await (await fetch('http://127.0.0.1:8000/api/dataset/list?limit=3')).json()
console.log('后端最新数据集:', list.datasets.map((d) => `${d.name}(${d.filename})`).join(' | '))

await browser.close()
console.log('UI UPLOAD NAME TEST DONE')
