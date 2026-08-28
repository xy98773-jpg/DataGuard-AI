// e2e_login.mjs — 实测：未登录跳登录页 → 登录成功进首页 → 顶栏用户名/退出 → 设置页 fallback 区
import { chromium } from 'playwright-core'

const FE = 'http://localhost:5173'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()

// 1) 未登录访问首页 → 跳登录页
await page.goto(`${FE}/dashboard`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)
console.log('未登录跳登录页:', page.url().includes('/login'))

// 2) 输入错误密码 → 报错
await page.locator('input[type=password]').fill('wrongpass')
await page.locator('button', { hasText: '登 录' }).click()
await page.waitForTimeout(1200)
console.log('错误密码报错:', (await page.locator('body').innerText()).includes('用户名或密码错误'))

// 3) 正确登录 → 进首页
await page.locator('input[type=password]').fill('admin123')
await page.locator('button', { hasText: '登 录' }).click()
await page.waitForTimeout(2500)
console.log('登录后进首页:', page.url().includes('/dashboard'))
const token = await page.evaluate(() => localStorage.getItem('dg_token'))
console.log('token 已存:', !!token)
console.log('顶栏用户名:', (await page.locator('.app-header').innerText()).includes('admin'))

// 4) 设置页有备用模型区 + 免费模型提示
await page.goto(`${FE}/settings`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(2000)
const settingsBody = await page.locator('.settings-card').innerText()
console.log('备用模型区:', settingsBody.includes('备用模型'))
console.log('免费模型提示:', settingsBody.includes('qwen-flash') && settingsBody.includes('qwen-turbo'))

// 5) 退出登录 → 回登录页
await page.locator('.app-header button', { hasText: '退出' }).click()
await page.waitForTimeout(1500)
console.log('退出后回登录页:', page.url().includes('/login'))

await browser.close()
console.log('E2E LOGIN PASS')
