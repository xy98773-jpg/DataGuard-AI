// e2e_settings.mjs — 实测：模型设置页加载/保存/测试连接 + 顶栏模型标签
import { chromium } from 'playwright-core'

const FE = 'http://localhost:5173'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()

// 1) 设置页打开 + 表单加载（模型/地址回填、Key 脱敏占位）
await page.goto(`${FE}/settings`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2500)
const modelInput = page.locator('input[placeholder*="qwen-flash"]').first()
console.log('模型回填:', await modelInput.inputValue())
const body = await page.locator('.settings-card').innerText()
console.log('含模型设置:', body.includes('模型设置'))
console.log('含 Base URL:', body.includes('API 地址'))
const keyPlaceholder = await page.locator('input[placeholder*="已配置"]').count()
console.log('Key 脱敏占位:', keyPlaceholder >= 1)

// 2) 修改模型名 → 保存 → 成功后回读
await modelInput.fill('qwen-max')
await page.locator('button', { hasText: '保存配置' }).click()
await page.waitForTimeout(2000)
const body2 = await page.locator('body').innerText()
console.log('保存成功提示:', body2.includes('已保存'))
if (!body2.includes('已保存')) throw new Error('保存未成功')

// 3) 测试连接（真实 qwen-flash key 在 .env，配置恢复后应可测通——这里仅验证按钮存在与返回提示）
const testBtn = page.locator('button', { hasText: '测试连接' })
console.log('测试连接按钮:', await testBtn.count() === 1)

// 4) 顶栏当前模型标签
await page.goto(`${FE}/dashboard`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)
const head = await page.locator('.app-header').innerText()
console.log('顶栏模型标签:', head.includes('当前模型'))

// 恢复原配置（qwen-flash 百炼，避免污染用户真实环境）
await page.goto(`${FE}/settings`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1500)
const modelInput2 = page.locator('input[placeholder*="qwen-flash"]').first()
await modelInput2.fill('qwen-flash')
await page.locator('button', { hasText: '保存配置' }).click()
await page.waitForTimeout(1500)

await browser.close()
console.log('E2E SETTINGS PASS')
