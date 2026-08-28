// e2e_dashboard.mjs — 验证 Dashboard 统计卡片 + 最近运行表渲染
import { chromium } from 'playwright-core'

const FE = 'http://localhost:5173'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
await page.goto(`${FE}/dashboard`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(5000)
const statCards = await page.locator('.stat-card').count()
const statTexts = await page.locator('.stat-value').allTextContents()
const rows = await page.locator('.recent-card .el-table__row').count()
console.log('统计卡片数:', statCards, '值:', statTexts.join(' / '))
console.log('最近运行行数:', rows)
if (statCards < 4) throw new Error('统计卡片不足 4 个')
if (rows < 1) throw new Error('最近运行表为空')
await browser.close()
console.log('E2E DASHBOARD PASS')
