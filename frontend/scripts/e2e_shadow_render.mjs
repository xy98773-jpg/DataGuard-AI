// e2e_shadow_render.mjs — 验证 database 源治理结果展示影子表（非 cleaned.csv）
import { chromium } from 'playwright-core'

const BE = 'http://127.0.0.1:8000'
const FE = 'http://localhost:5173'

// 取最近一个含 shadow_table 的 outputs
const ds = (await (await fetch(`${BE}/api/dataset/list`)).json()).datasets?.find((d) => d.source_type === 'database')
if (!ds) throw new Error('无 database 源数据集')
const outs = await (await fetch(`${BE}/api/dataset/${ds.id}/outputs`)).json()
console.log('dataset:', ds.id, 'shadow:', outs.shadow_table, 'rows:', outs.shadow_rows)
if (!outs.shadow_table) throw new Error('该数据集无影子表交付物')

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()
await page.goto(`${FE}/workflow`, { waitUntil: 'domcontentloaded' })
await page.evaluate(([datasetId, runId]) => {
  localStorage.setItem('dg-active-run', JSON.stringify({ datasetId, runId }))
}, [ds.id, outs.report?.run_id ?? ''])
await page.reload({ waitUntil: 'domcontentloaded' })
await page.waitForTimeout(7000)
const body = await page.locator('body').innerText()
console.log('页面含「影子表」:', body.includes('影子表'))
if (!body.includes('影子表')) throw new Error('页面未显示影子表交付物')
await browser.close()
console.log('E2E SHADOW RENDER PASS')
