// e2e_delete.mjs — 实测：首页删除数据集（二次确认）→ 列表/后端/问题列表同步消失
import { chromium } from 'playwright-core'
import { readFileSync } from 'node:fs'

const BE = 'http://127.0.0.1:8000'
const FE = 'http://localhost:5173'
const csv = readFileSync('D:/Desktop/DataGuard AI/backend/datasets/demo/customer.csv')

// 1) 上传两个数据集（一个待删、一个保留）
async function upload(name) {
  const fd = new FormData()
  fd.append('file', new Blob([csv], { type: 'text/csv' }))
  fd.append('name', name)
  return (await (await fetch(`${BE}/api/dataset/upload`, { method: 'POST', body: fd })).json()).dataset_id
}
const toDelete = await upload('E2E待删除数据集')
const keep = await upload('E2E保留数据集')
console.log('待删:', toDelete, '保留:', keep)

// 跑一次治理让待删数据集有 issues
await (await fetch(`${BE}/api/workflow/start`, {
  method: 'POST', headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ dataset_id: toDelete }),
})).json()

const browser = await chromium.launch({ channel: 'msedge', headless: true })
const page = await browser.newPage()

// 2) 首页找到待删行 → 点删除 → confirm 弹窗确认
await page.goto(`${FE}/dashboard`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(4000)
const row = page.locator('.ds-card .el-table__row', { hasText: 'E2E待删除数据集' })
console.log('目标行数:', await row.count())
if (!(await row.count())) throw new Error('待删数据集未出现在首页')
await row.locator('button', { hasText: '删除' }).click()
await page.waitForTimeout(1000)
const dlg = page.locator('.el-message-box')
console.log('确认弹窗:', await dlg.innerText().then((t) => t.includes('删除数据集') && t.includes('不可恢复')))
await dlg.locator('button', { hasText: '删除' }).click()
await page.waitForTimeout(3000)

// 3) 断言：首页列表无待删、保留仍在；后端确认；问题列表无该分组
const body = await page.locator('.ds-card').innerText()
console.log('首页无待删:', !body.includes('E2E待删除数据集'), '| 保留仍在:', body.includes('E2E保留数据集'))
if (body.includes('E2E待删除数据集')) throw new Error('删除后列表仍显示')

const list = await (await fetch(`${BE}/api/dataset/list?limit=50`)).json()
const still = list.datasets.some((d) => d.id === toDelete)
console.log('后端已删:', !still)
if (still) throw new Error('后端仍存在')

const issues = await (await fetch(`${BE}/api/issues?dataset_id=${toDelete}`)).json()
console.log('问题列表已清空:', (issues.issues ?? []).length === 0)
if ((issues.issues ?? []).length) throw new Error('问题未级联删除')

// 4) 问题中心页无该分组
await page.goto(`${FE}/issues`, { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(3000)
const body2 = await page.locator('body').innerText()
console.log('问题中心无待删分组:', !body2.includes('E2E待删除数据集'))

await browser.close()
console.log('E2E DELETE PASS')
