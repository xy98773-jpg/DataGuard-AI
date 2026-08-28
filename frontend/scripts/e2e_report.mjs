// e2e_report.mjs — 实测：工作台导出 PDF/HTML 下载 + Dashboard 质量趋势渲染
import { chromium } from 'playwright-core'

const FE = 'http://localhost:5173'
const BE = 'http://127.0.0.1:8000'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ acceptDownloads: true })

// 1) Dashboard 质量趋势渲染
await page.goto(`${FE}/dashboard`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3500)
const body = await page.locator('body').innerText()
console.log('趋势卡片:', body.includes('质量趋势'))
console.log('SVG 折线:', (await page.locator('.trend-svg polyline').count()) >= 1)
if (!body.includes('质量趋势')) throw new Error('趋势卡片未渲染')

// 2) 找一个 SUCCESS run 直接打开工作台（query 定位数据集 → 自动恢复 run）
const stats = await (await fetch(`${BE}/api/dashboard/stats`)).json()
const done = stats.quality_trend[0]  // 最近一次有评分的治理
const runInfo = await (await fetch(`${BE}/api/workflow/${done.run_id}`)).json()
console.log('目标 run:', done.run_id, 'ds:', runInfo.dataset_id)
await page.goto(`${FE}/workflow?dataset=${runInfo.dataset_id}`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(4000)

// 3) 导出 PDF（结果区「导出 PDF」按钮 → 触发下载）
const pdfBtn = page.locator('button', { hasText: '导出 PDF' }).first()
console.log('导出PDF按钮数:', await pdfBtn.count())
const [pdfDl] = await Promise.all([
  page.waitForEvent('download', { timeout: 60000 }),
  pdfBtn.click(),
])
const pdfPath = await pdfDl.path()
console.log('PDF 下载成功:', !!pdfPath)

// 4) 打开报告弹窗 → 弹窗内导出 HTML + PDF
await page.locator('button', { hasText: '查看完整报告' }).first().click()
await page.waitForTimeout(1500)
const dlgHtml = page.locator('.report-dialog button', { hasText: '导出 HTML' }).first()
const dlgPdf = page.locator('.report-dialog button', { hasText: '导出 PDF' }).first()
console.log('弹窗导出HTML按钮:', await dlgHtml.count(), '| 弹窗导出PDF按钮:', await dlgPdf.count())
const [htmlDl] = await Promise.all([
  page.waitForEvent('download', { timeout: 30000 }),
  dlgHtml.click(),
])
const htmlPath = await htmlDl.path()
console.log('HTML 下载成功:', !!htmlPath)
const [dlgPdfDl] = await Promise.all([
  page.waitForEvent('download', { timeout: 60000 }),
  dlgPdf.click(),
])
const dlgPdfPath = await dlgPdfDl.path()
console.log('弹窗 PDF 下载成功:', !!dlgPdfPath)

await browser.close()
console.log('E2E REPORT PASS')
