import { chromium } from 'playwright-core'

// 验证：治理过程中 TracePanel 事件流实时累积（不等流程结束）
const NEW_DS = 'ds_2c515a583d' // worldometers 数据集

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
page.on('pageerror', (err) => console.log('[pageerror]', err.message))

await page.goto(`http://localhost:5173/workflow?dataset=${NEW_DS}`, { waitUntil: 'networkidle', timeout: 30000 }).catch(() => {})
await page.waitForTimeout(1500)
await page.locator('text=开始治理').first().click()
console.log('已开始治理')

// 每 4 秒记录一次 TracePanel 事件数量（.trace-item）
for (let i = 0; i < 7; i++) {
  await page.waitForTimeout(4000)
  const count = await page.locator('.trace-item').count()
  const status = (await page.locator('.run-id').first().textContent().catch(() => '')) || ''
  console.log(`t=${(i + 1) * 4}s trace_events=${count}`)
}
await browser.close()
