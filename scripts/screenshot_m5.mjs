import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const outDir = path.join(rootDir, 'docs', 'screenshots', 'm5')
const brainDir = 'C:\\Users\\lishi\\.gemini\\antigravity\\brain\\ed0913bc-da14-4c1e-96ba-0cedaf3a0c90'

fs.mkdirSync(outDir, { recursive: true })

async function run() {
  console.log('启动 Edge 浏览器捕获 M5 阶段（续保顾问）截图...')
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
    // 1. 访问续保顾问页 http://localhost:5173/renewal
    console.log('正在访问续保顾问页 http://localhost:5173/renewal ...')
    await page.goto('http://localhost:5173/renewal', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1500)

    // 截取完整会话与对比报告 (桌面端 1440)
    const renewalDesktopPath = path.join(outDir, 'renewal_page_1440.png')
    await page.screenshot({ path: renewalDesktopPath, fullPage: true })
    console.log(`已捕获桌面端对比报告大盘: ${renewalDesktopPath}`)

    // 2. 对比矩阵特写 (Comparison Matrix Closeup)
    const matrixEl = page.locator('.matrix-container')
    if (await matrixEl.count() > 0) {
      const matrixPath = path.join(outDir, 'renewal_matrix_closeup_1440.png')
      await matrixEl.first().screenshot({ path: matrixPath })
      console.log(`已捕获对比矩阵特写: ${matrixPath}`)
    }

    // 3. 需求画像与客服核对清单特写
    const checklistEl = page.locator('.checklist-card')
    if (await checklistEl.count() > 0) {
      const checklistPath = path.join(outDir, 'renewal_checklist_closeup_1440.png')
      await checklistEl.first().screenshot({ path: checklistPath })
      console.log(`已捕获客服核对清单特写: ${checklistPath}`)
    }

    // 3.5 访问 search_failed 会话并截取「检索未完成」防编造披露特写
    try {
      const statsRaw = fs.readFileSync(path.join(rootDir, 'docs', 'm5_stats.json'), 'utf8')
      const statsJson = JSON.parse(statsRaw)
      const failedSessionId = statsJson.search_timeout_disclosure?.session_id
      if (failedSessionId) {
        console.log(`正在访问检索失败会话 ${failedSessionId} ...`)
        // Select this session from history or API
        await page.evaluate(async (sessId) => {
          const res = await fetch(`/api/renewal/sessions/${sessId}`)
          if (res.ok) {
            const data = await res.json()
            // Dispatch or directly trigger selection if accessible
          }
        }, failedSessionId)

        // Or navigate to session switcher and find failed session
        const backBtn = page.locator('.btn-back')
        if (await backBtn.count() > 0) {
          await backBtn.click()
          await page.waitForTimeout(500)
          const sessItems = page.locator('.session-history-item')
          for (let i = 0; i < await sessItems.count(); i++) {
            const itemText = await sessItems.nth(i).innerText()
            if (itemText.includes('END')) {
              await sessItems.nth(i).click()
              await page.waitForTimeout(800)
              const failBanner = page.locator('.failure-banner')
              if (await failBanner.count() > 0) {
                const failPath = path.join(outDir, 'renewal_failure_disclosure_closeup.png')
                await failBanner.first().screenshot({ path: failPath })
                console.log(`已捕获检索未完成声明特写: ${failPath}`)
                break
              }
            }
          }
        }
      }
    } catch (e) {
      console.warn('捕获失败披露特写跳过:', e)
    }

    // 4. 创建新会话并截取追问卡片 (QuestionCard Closeup)
    console.log('触发新会话以捕获追问卡特写...')
    const switchBtn = page.locator('.btn-back')
    if (await switchBtn.count() > 0) {
      await switchBtn.click()
      await page.waitForTimeout(600)
    }

    // Click "发起续保规划" on first accident policy
    const startBtn = page.locator('.btn-start')
    if (await startBtn.count() > 0) {
      await startBtn.first().click()
      await page.waitForTimeout(1000)

      // Send initial statement to enter ASK_USER state
      const textInput = page.locator('.text-input')
      if (await textInput.count() > 0) {
        await textInput.fill('今年出差经常坐飞机和高铁，加班较多希望有猝死保障')
        const sendBtn = page.locator('.btn-send')
        await sendBtn.click()
        await page.waitForTimeout(1500)

        // Capture QuestionCard closeup
        const questionCard = page.locator('.questions-card')
        if (await questionCard.count() > 0) {
          const qCardPath = path.join(outDir, 'renewal_question_card_closeup.png')
          await questionCard.first().screenshot({ path: qCardPath })
          console.log(`已捕获追问卡特写: ${qCardPath}`)
        }
      }
    }

    // 5. 平板断点 (768x1024)
    console.log('捕获平板端 (768x1024) 续保顾问页...')
    const tabletPage = await browser.newPage({
      viewport: { width: 768, height: 1024 },
    })
    await tabletPage.goto('http://localhost:5173/renewal', { waitUntil: 'networkidle' })
    await tabletPage.waitForTimeout(1200)
    const tabletPath = path.join(outDir, 'renewal_page_768.png')
    await tabletPage.screenshot({ path: tabletPath, fullPage: true })
    console.log(`已捕获: ${tabletPath}`)
    await tabletPage.close()

    // 6. 移动端断点 (390x844 iPhone 12/13/14)
    console.log('捕获移动端 (390x844) 续保顾问页...')
    const mobilePage = await browser.newPage({
      viewport: { width: 390, height: 844 },
    })
    await mobilePage.goto('http://localhost:5173/renewal', { waitUntil: 'networkidle' })
    await mobilePage.waitForTimeout(1200)
    const mobilePath = path.join(outDir, 'renewal_page_390.png')
    await mobilePage.screenshot({ path: mobilePath, fullPage: true })
    console.log(`已捕获: ${mobilePath}`)
    await mobilePage.close()

    // 同步截图至 Artifacts 目录
    try {
      const files = fs.readdirSync(outDir)
      for (const file of files) {
        if (file.endsWith('.png')) {
          fs.copyFileSync(path.join(outDir, file), path.join(brainDir, file))
        }
      }
      console.log('已同步 M5 截图至 Brain Artifacts 目录')
    } catch (e) {
      console.warn('同步截图失败:', e)
    }

  } catch (err) {
    console.error('截屏发生错误:', err)
  } finally {
    await browser.close()
    console.log('M5 截屏全部完成。')
  }
}

run()
