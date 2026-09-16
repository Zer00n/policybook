import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const outDir = path.join(rootDir, 'docs', 'screenshots', 'm0')

fs.mkdirSync(outDir, { recursive: true })

async function run() {
  console.log('启动 Edge 浏览器...')
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
  })

  const viewports = [
    { name: '390', width: 390, height: 844 },
    { name: '820', width: 820, height: 1180 },
    { name: '1440', width: 1440, height: 900 },
  ]

  try {
    for (const vp of viewports) {
      console.log(`正在捕获视口: ${vp.name} (${vp.width}x${vp.height})...`)
      const page = await browser.newPage({
        viewport: { width: vp.width, height: vp.height },
      })

      // 1. 浅色主题
      await page.goto('http://localhost:5173/dev/styleguide', { waitUntil: 'networkidle' })
      await page.evaluate(() => {
        document.documentElement.removeAttribute('data-theme')
      })
      // 点击模型探针测试按钮
      const testBtn = page.locator('button:has-text("发起连通测试")')
      if (await testBtn.count() > 0) {
        await testBtn.click()
        await page.waitForTimeout(600)
      }
      await page.waitForTimeout(400)
      const lightPath = path.join(outDir, `styleguide_${vp.name}_light.png`)
      await page.screenshot({ path: lightPath, fullPage: true })
      console.log(`已捕获浅色: ${lightPath}`)

      // 2. 深色主题
      await page.evaluate(() => {
        document.documentElement.setAttribute('data-theme', 'dark')
      })
      await page.waitForTimeout(400)
      const darkPath = path.join(outDir, `styleguide_${vp.name}_dark.png`)
      await page.screenshot({ path: darkPath, fullPage: true })
      console.log(`已捕获深色: ${darkPath}`)

      await page.close()
    }
  } catch (err) {
    console.error('截图执行错误:', err)
  } finally {
    await browser.close()
    process.exit(0)
  }
}

run().catch((err) => {
  console.error(err)
  process.exit(1)
})
