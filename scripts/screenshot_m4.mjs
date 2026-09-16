import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const outDir = path.join(rootDir, 'docs', 'screenshots', 'm4')
const brainDir = 'C:\\Users\\lishi\\.gemini\\antigravity\\brain\\ed0913bc-da14-4c1e-96ba-0cedaf3a0c90'

fs.mkdirSync(outDir, { recursive: true })

async function run() {
  console.log('启动 Edge 浏览器捕获 M4 阶段截图...')
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
    // 1. 家庭总览页面 (桌面端 1440)
    console.log('正在访问家庭总览页 http://localhost:5173/ ...')
    await page.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1200)

    const overviewDesktopPath = path.join(outDir, 'overview_page_1440.png')
    await page.screenshot({ path: overviewDesktopPath, fullPage: true })
    console.log(`已捕获: ${overviewDesktopPath}`)

    // 2. 时间轴断保空档特写 (Timeline Gap Closeup)
    const timelineWidget = page.locator('.timeline-widget')
    if (await timelineWidget.count() > 0) {
      const gapCloseupPath = path.join(outDir, 'timeline_gap_closeup_1440.png')
      await timelineWidget.screenshot({ path: gapCloseupPath })
      console.log(`已捕获时间轴特写: ${gapCloseupPath}`)
    }

    // 3. 家庭成员页面（覆盖雷达与缺口热力图）
    console.log('正在访问家庭成员页 http://localhost:5173/members ...')
    await page.goto('http://localhost:5173/members', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1500)

    const membersPath = path.join(outDir, 'members_radar_heatmap_1440.png')
    await page.screenshot({ path: membersPath, fullPage: true })
    console.log(`已捕获成员雷达热力图: ${membersPath}`)

    // 4. 系统设置页面（日历订阅与参考保额）
    console.log('正在访问设置页 http://localhost:5173/settings ...')
    await page.goto('http://localhost:5173/settings', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)

    const settingsPath = path.join(outDir, 'settings_calendar_ics_1440.png')
    await page.screenshot({ path: settingsPath, fullPage: true })
    console.log(`已捕获设置页与ICS订阅: ${settingsPath}`)

    // 5. 平板断点 (768x1024)
    console.log('捕获平板端 (768x1024) 家庭总览页...')
    const tabletPage = await browser.newPage({
      viewport: { width: 768, height: 1024 },
    })
    await tabletPage.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
    await tabletPage.waitForTimeout(1000)
    const overviewTabletPath = path.join(outDir, 'overview_page_768.png')
    await tabletPage.screenshot({ path: overviewTabletPath, fullPage: true })
    console.log(`已捕获: ${overviewTabletPath}`)
    await tabletPage.close()

    // 6. 移动端断点 (390x844 iPhone 12/13/14)
    console.log('捕获移动端 (390x844) 家庭总览页...')
    const mobilePage = await browser.newPage({
      viewport: { width: 390, height: 844 },
    })
    await mobilePage.goto('http://localhost:5173/', { waitUntil: 'networkidle' })
    await mobilePage.waitForTimeout(1000)
    const overviewMobilePath = path.join(outDir, 'overview_page_390.png')
    await mobilePage.screenshot({ path: overviewMobilePath, fullPage: true })
    console.log(`已捕获: ${overviewMobilePath}`)
    await mobilePage.close()

    // 同步截图至 Artifacts 目录
    try {
      const files = fs.readdirSync(outDir)
      for (const file of files) {
        if (file.endsWith('.png')) {
          fs.copyFileSync(path.join(outDir, file), path.join(brainDir, file))
        }
      }
      console.log('已同步截图至 Brain Artifacts 目录')
    } catch (e) {
      console.warn('同步截图失败:', e)
    }

  } catch (err) {
    console.error('截屏发生错误:', err)
  } finally {
    await browser.close()
    console.log('M4 截屏完成。')
  }
}

run()
