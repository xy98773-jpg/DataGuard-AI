// e2e_trend_dialog.mjs — 实测：工作台「质量趋势」按钮打开弹窗 + 首页无趋势卡片
import { chromium } from 'playwright-core'

const FE = 'http://localhost:5173'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()

// 1) 首页不应再有趋势卡片
await page.goto(`${FE}/dashboard`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3000)
const dashBody = await page.locator('body').innerText()
console.log('首页无质量趋势卡片:', !dashBody.includes('质量趋势'))
if (dashBody.includes('质量趋势')) throw new Error('首页仍显示趋势')

// 2) 工作台有「质量趋势」按钮 → 点击打开弹窗
await page.goto(`${FE}/workflow`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3000)
const btn = page.locator('button', { hasText: '质量趋势' }).first()
console.log('工作台趋势按钮数:', await btn.count())
if (!(await btn.count())) throw new Error('工作台无趋势按钮')
await btn.click()
await page.waitForTimeout(2000)

// 3) 弹窗内容：SVG 折线 + 明细表 + 图例
const dlg = page.locator('.quality-trend-dialog')
console.log('弹窗打开:', await dlg.count() === 1)
const dlgBody = await dlg.innerText()
console.log('弹窗标题:', dlgBody.includes('质量趋势'))
console.log('ECharts canvas:', (await dlg.locator('.trend-chart canvas').count()) >= 1)
console.log('明细表含治理前/后:', dlgBody.includes('治理前') && dlgBody.includes('治理后'))
if ((await dlg.locator('.trend-chart canvas').count()) < 1) throw new Error('ECharts 未渲染')

// 4) 关闭弹窗
await page.keyboard.press('Escape')
await page.waitForTimeout(800)
console.log('ESC 可关闭:', (await page.locator('.quality-trend-dialog').count()) === 0 || (await page.locator('.quality-trend-dialog:visible').count()) === 0)

await browser.close()
console.log('E2E TREND DIALOG PASS')
