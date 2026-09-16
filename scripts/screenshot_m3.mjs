import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const outDir = path.join(rootDir, 'docs', 'screenshots', 'm3')
const brainDir = 'C:\\Users\\lishi\\.gemini\\antigravity\\brain\\ed0913bc-da14-4c1e-96ba-0cedaf3a0c90'

fs.mkdirSync(outDir, { recursive: true })

async function run() {
  console.log('启动 Edge 浏览器捕获 M3 阶段截图...')
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
  })

  // 1. 桌面端 (1440x900)
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
  })
  page.on('console', msg => console.log('BROWSER:', msg.text()))

  try {
    // 1. 条款问答页面 (桌面端 1440)
    console.log('正在访问问答页 http://localhost:5173/ask ...')
    await page.goto('http://localhost:5173/ask', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)

    // 输入问题并提问
    const textarea = page.locator('.chat-textarea')
    await textarea.fill('平安守护百分百的身故保险金怎么赔？基本保额是多少？')
    await page.waitForTimeout(500)
    const sendBtn = page.locator('.send-btn')
    await sendBtn.click()
    console.log('等待问答完成并显示结构化结论 (预计 20-40s)...')
    await page.waitForSelector('.qa-structured-result', { timeout: 120000 })
    await page.waitForTimeout(1500)

    const askDesktopPath = path.join(outDir, 'ask_page_1440.png')
    await page.screenshot({ path: askDesktopPath, fullPage: true })
    console.log(`已捕获: ${askDesktopPath}`)

    // 2. 问答页展开阅读器抽屉
    const citationCard = page.locator('.citation-card').first()
    if (await citationCard.count() > 0) {
      console.log('点击条款引用卡片展开阅读器抽屉...')
      await citationCard.click()
      await page.waitForTimeout(2000)
      const askDrawerPath = path.join(outDir, 'ask_page_drawer_1440.png')
      await page.screenshot({ path: askDrawerPath, fullPage: true })
      console.log(`已捕获: ${askDrawerPath}`)
      // 关闭抽屉
      const closeBtn = page.locator('.drawer-container button[title="关闭"]')
      if (await closeBtn.count() > 0) await closeBtn.click()
    } else {
      // 若当前回答为 no_basis，截图降级问答页
      const askDrawerPath = path.join(outDir, 'ask_page_drawer_1440.png')
      await page.screenshot({ path: askDrawerPath, fullPage: true })
      console.log(`已捕获 (降级模式): ${askDrawerPath}`)
    }

    // 3. 理赔情景模拟页 (桌面端 1440)
    console.log('正在访问理赔模拟页 http://localhost:5173/claim ...')
    await page.goto('http://localhost:5173/claim', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)

    // 点击测算按钮
    const submitBtn = page.locator('.submit-btn')
    if (await submitBtn.count() > 0) {
      console.log('点击理赔模拟测算按钮 (预计 15-30s)...')
      await submitBtn.click()
      await page.waitForSelector('.results-container', { timeout: 120000 })
      await page.waitForTimeout(2000)
    }

    const claimWaterfallPath = path.join(outDir, 'claim_page_waterfall_1440.png')
    await page.screenshot({ path: claimWaterfallPath, fullPage: true })
    console.log(`已捕获: ${claimWaterfallPath}`)

    // 4. 理赔页点击条款依据展开抽屉
    const evidenceBtn = page.locator('.evidence-link-btn').first()
    if (await evidenceBtn.count() > 0) {
      console.log('点击责任项条款依据展开抽屉...')
      await evidenceBtn.click()
      await page.waitForTimeout(2000)
      const claimDrawerPath = path.join(outDir, 'claim_page_drawer_1440.png')
      await page.screenshot({ path: claimDrawerPath, fullPage: true })
      console.log(`已捕获: ${claimDrawerPath}`)
    } else {
      const claimDrawerPath = path.join(outDir, 'claim_page_drawer_1440.png')
      await page.screenshot({ path: claimDrawerPath, fullPage: true })
      console.log(`已捕获: ${claimDrawerPath}`)
    }

    // 5. 移动端 (390x844) 问答页
    console.log('正在切换至移动端视口 (390px)...')
    const mobilePage = await browser.newPage({
      viewport: { width: 390, height: 844 },
    })
    await mobilePage.goto('http://localhost:5173/ask', { waitUntil: 'networkidle' })
    await mobilePage.waitForTimeout(1000)
    const mTextarea = mobilePage.locator('.chat-textarea')
    await mTextarea.fill('意外门诊微创手术能报销吗？')
    const mSend = mobilePage.locator('.send-btn')
    await mSend.click()
    await mobilePage.waitForSelector('.qa-structured-result', { timeout: 120000 })
    await mobilePage.waitForTimeout(1000)

    const askMobilePath = path.join(outDir, 'ask_page_390.png')
    await mobilePage.screenshot({ path: askMobilePath, fullPage: true })
    console.log(`已捕获: ${askMobilePath}`)

    // 复制到 brain 目录作为 artifacts
    const files = fs.readdirSync(outDir).filter(f => f.endsWith('.png'))
    for (const f of files) {
      fs.copyFileSync(path.join(outDir, f), path.join(brainDir, f))
    }
    console.log(`已将 ${files.length} 张截图同步至 Artifact 目录`)
  } catch (err) {
    console.error('截图捕获异常:', err)
  } finally {
    await browser.close()
    console.log('截图捕获任务结束。')
  }
}

run()
