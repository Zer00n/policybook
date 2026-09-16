import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const outDir = path.join(rootDir, 'docs', 'screenshots', 'm5')
const brainDir = 'C:\\Users\\lishi\\.gemini\\antigravity\\brain\\ed0913bc-da14-4c1e-96ba-0cedaf3a0c90'

async function run() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

  try {
    await page.goto('http://localhost:5173/renewal', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)

    // Click back if inside an active session
    const backBtn = page.locator('.btn-back')
    if (await backBtn.count() > 0) {
      await backBtn.click()
      await page.waitForTimeout(800)
    }

    // Find failed session item in history
    const sessItems = page.locator('.session-history-item')
    const count = await sessItems.count()
    console.log(`Found ${count} session items in history`)

    // Look for search_failed session
    const statsRaw = fs.readFileSync(path.join(rootDir, 'docs', 'm5_stats.json'), 'utf8')
    const statsJson = JSON.parse(statsRaw)
    const failedSessId = statsJson.search_timeout_disclosure?.session_id

    // Use evaluate to load this session directly into activeSession
    await page.evaluate(async (id) => {
      const res = await fetch(`/api/renewal/sessions/${id}`)
      const data = await res.json()
      // Directly trigger
      const comp = document.querySelector('.renewal-page-container')
      // Let's set it via Vue instance or click the session in history
    }, failedSessId)

    // Click through each history item until failure-banner is found
    for (let i = 0; i < await sessItems.count(); i++) {
      await sessItems.nth(i).click()
      await page.waitForTimeout(600)
      const banner = page.locator('.failure-banner')
      if (await banner.count() > 0) {
        console.log(`Found failure banner in session ${i}`)
        const bannerPath = path.join(outDir, 'renewal_failure_disclosure_closeup.png')
        await banner.screenshot({ path: bannerPath })
        fs.copyFileSync(bannerPath, path.join(brainDir, 'renewal_failure_disclosure_closeup.png'))
        console.log(`Saved failure disclosure closeup: ${bannerPath}`)
        break
      }
      // Go back
      const back = page.locator('.btn-back')
      if (await back.count() > 0) {
        await back.click()
        await page.waitForTimeout(400)
      }
    }
  } catch (e) {
    console.error(e)
  } finally {
    await browser.close()
  }
}

run()
