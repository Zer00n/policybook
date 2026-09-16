import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const outDir = path.join(rootDir, 'docs', 'screenshots', 'm2')
const brainDir = 'C:\\Users\\lishi\\.gemini\\antigravity\\brain\\ed0913bc-da14-4c1e-96ba-0cedaf3a0c90'

fs.mkdirSync(outDir, { recursive: true })

async function run() {
  console.log('启动 Edge 浏览器捕获 M2 阶段截图...')
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
  })

  // 1. 桌面端 (1440x900)
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
  })

  try {
    const reviewJobId = '01M2REVIEWJOB0000000000001'
    const policyId = '01M2POLICY000000000000001'

    // 1. 核对页 (桌面双栏 1440)
    console.log('正在捕获核对页 (1440px 双栏)...')
    await page.goto(`http://localhost:5173/import/${reviewJobId}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)
    const reviewDesktopPath = path.join(outDir, 'review_page_1440.png')
    await page.screenshot({ path: reviewDesktopPath, fullPage: true })
    console.log(`已捕获: ${reviewDesktopPath}`)

    // 2. 核对页高亮定位与 FLIP 动效
    console.log('正在触发核对页字段依据点击高亮定位...')
    const fieldItem = page.locator('.field-item:has-text("基本保额")')
    if (await fieldItem.count() > 0) {
      await fieldItem.first().click()
      await page.waitForTimeout(500)
      const highlightPath = path.join(outDir, 'review_page_highlight_1440.png')
      await page.screenshot({ path: highlightPath, fullPage: true })
      console.log(`已捕获: ${highlightPath}`)
    }

    // 3. 保单库 (卡片网格视图 1440)
    console.log('正在捕获保单库 (卡片视图)...')
    await page.goto('http://localhost:5173/policies', { waitUntil: 'networkidle' })
    await page.waitForTimeout(800)
    const polGridPath = path.join(outDir, 'policy_list_grid_1440.png')
    await page.screenshot({ path: polGridPath, fullPage: true })
    console.log(`已捕获: ${polGridPath}`)

    // 4. 保单库 (表格列表视图 1440)
    console.log('正在切换到列表视图...')
    const tableBtn = page.locator('button[title="列表视图"]')
    if (await tableBtn.count() > 0) {
      await tableBtn.click()
      await page.waitForTimeout(400)
      const polTablePath = path.join(outDir, 'policy_list_table_1440.png')
      await page.screenshot({ path: polTablePath, fullPage: true })
      console.log(`已捕获: ${polTablePath}`)
    }

    // 5. 保单详情页 (1440)
    console.log('正在捕获保单详情页 (摘要卡 + 责任项 + 免责条款)...')
    await page.goto(`http://localhost:5173/policies/${policyId}`, { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)
    const polDetailPath = path.join(outDir, 'policy_detail_1440.png')
    await page.screenshot({ path: polDetailPath, fullPage: true })
    console.log(`已捕获: ${polDetailPath}`)

    // 6. 保单详情页 - 打开原文阅读器抽屉并高亮依据
    console.log('正在打开原文阅读器抽屉并定位条款依据...')
    const evidenceBtn = page.locator('button.btn-evidence:has-text("第 1 页")')
    if (await evidenceBtn.count() > 0) {
      await evidenceBtn.first().click()
      await page.waitForTimeout(600)
      const detailDrawerPath = path.join(outDir, 'policy_detail_drawer_1440.png')
      await page.screenshot({ path: detailDrawerPath, fullPage: true })
      console.log(`已捕获: ${detailDrawerPath}`)
    }

    await page.close()

    // 7. 移动端 (390x844 - iPhone 14/15 尺寸)
    const mobilePage = await browser.newPage({
      viewport: { width: 390, height: 844 },
    })

    console.log('正在捕获移动端核对页 (390px)...')
    await mobilePage.goto(`http://localhost:5173/import/${reviewJobId}`, { waitUntil: 'networkidle' })
    await mobilePage.waitForTimeout(1000)
    const mobileReviewPath = path.join(outDir, 'review_page_390.png')
    await mobilePage.screenshot({ path: mobileReviewPath, fullPage: true })
    console.log(`已捕获: ${mobileReviewPath}`)

    // 移动端打开阅读器抽屉
    const viewDocBtn = mobilePage.locator('button:has-text("查看合同原文")')
    if (await viewDocBtn.count() > 0) {
      await viewDocBtn.click()
      await mobilePage.waitForTimeout(600)
      const mobileDrawerPath = path.join(outDir, 'review_page_390_drawer.png')
      await mobilePage.screenshot({ path: mobileDrawerPath, fullPage: true })
      console.log(`已捕获: ${mobileDrawerPath}`)
    }

    await mobilePage.close()

    // 同步截图到 brain artifacts 目录
    try {
      const files = fs.readdirSync(outDir)
      for (const f of files) {
        if (f.endsWith('.png')) {
          fs.copyFileSync(path.join(outDir, f), path.join(brainDir, f))
        }
      }
      console.log('已同步截图到 conversation artifacts 目录。')
    } catch (e) {
      console.log('同步截图目录忽略:', e.message)
    }

    console.log('M2 截图全部完成！')
  } catch (err) {
    console.error('截图过程出错:', err)
  } finally {
    await browser.close()
  }
}

run()
