// e2e_token_render.mjs — 验证 Token 统计卡片真实渲染（用已有 SUCCESS run 注入 localStorage）
import { chromium } from 'playwright-core'

const BE = 'http://127.0.0.1:8000'
const FE = 'http://localhost:5173'

const usage = await (await fetch(`${BE}/api/trace/run_588b5d3dbd/usage`)).json()
console.log('usage:', JSON.stringify(usage.usage), 'total:', usage.total)
if (!usage.total) throw new Error('该 run 无 token 数据')

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
await page.goto(`${FE}/workflow`, { waitUntil: 'domcontentloaded' })
await page.evaluate(([runId]) => {
  localStorage.setItem('dg-active-run', JSON.stringify({ datasetId: 'ds_e60ff05b07', runId }))
}, ['run_588b5d3dbd'])
await page.reload({ waitUntil: 'domcontentloaded' })
await page.waitForTimeout(7000)
const text = await page.evaluate(() => document.querySelector('.token-stats')?.textContent ?? '')
console.log('渲染文本:', text.slice(0, 220))
if (!text.includes('Token 消耗') || !text.includes('合计')) throw new Error('Token 卡片未渲染')
await browser.close()
console.log('E2E TOKEN RENDER PASS')
