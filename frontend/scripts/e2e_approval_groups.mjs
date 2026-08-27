import { chromium } from 'playwright-core'

// 验证：审批页按 run 分组渲染（当前有 run_81a0a91f8f 9 条 + run_beca592d1a 2 条）
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } })
page.on('pageerror', (err) => console.log('[pageerror]', err.message))

await page.goto('http://localhost:5173/approval', { waitUntil: 'networkidle', timeout: 30000 }).catch((e) => console.log('[goto]', e.message))
await page.waitForTimeout(2000)

const groups = await page.locator('.run-group').count()
const groupTitles = await page.locator('.group-title').allTextContents()
console.log('运行任务分组数（应 2）:', groups)
console.log('分组标题:', groupTitles)

const submitBtns = await page.locator('text=提交该组审批结果').count()
console.log('组提交按钮数（应 2）:', submitBtns)

// 每组操作条目数
for (let i = 0; i < groups; i++) {
  const items = await page.locator('.run-group').nth(i).locator('.approval-card').count()
  console.log(`组${i + 1} 操作条目数:`, items)
}

await browser.close()
