import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const outDir = path.join(rootDir, 'docs', 'screenshots', 'm1')

fs.mkdirSync(outDir, { recursive: true })

async function run() {
  console.log('启动 Edge 浏览器捕获 M1 截图...')
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
  })

  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
  })

  try {
    // 1. 成员管理页
    console.log('正在捕获成员管理页...')
    await page.goto('http://localhost:5173/members', { waitUntil: 'networkidle' })
    await page.waitForTimeout(600)
    const membersPath = path.join(outDir, 'members_page_1440.png')
    await page.screenshot({ path: membersPath, fullPage: true })
    console.log(`已捕获: ${membersPath}`)

    // 2. 上传与文档列表页
    console.log('正在捕获保单上传与文档列表页...')
    await page.goto('http://localhost:5173/import', { waitUntil: 'networkidle' })
    await page.waitForTimeout(600)
    const importPath = path.join(outDir, 'import_page_1440.png')
    await page.screenshot({ path: importPath, fullPage: true })
    console.log(`已捕获: ${importPath}`)

    // 3. 点击第一个文档的“脱敏对比”按钮
    console.log('正在打开第一个文档的脱敏对比弹窗...')
    const compareBtns = page.locator('button:has-text("脱敏对比")')
    if (await compareBtns.count() > 0) {
      await compareBtns.first().click()
      await page.waitForTimeout(800)
      const comparePath = path.join(outDir, 'pii_compare_pdf_1440.png')
      await page.screenshot({ path: comparePath, fullPage: true })
      console.log(`已捕获: ${comparePath}`)

      // 切换到文本层比对
      const textToggle = page.locator('button:has-text("文本层比对")')
      if (await textToggle.count() > 0) {
        await textToggle.click()
        await page.waitForTimeout(500)
        const textComparePath = path.join(outDir, 'pii_compare_text_1440.png')
        await page.screenshot({ path: textComparePath, fullPage: true })
        console.log(`已捕获: ${textComparePath}`)
      }

      // 关闭弹窗
      const closeBtn = page.locator('button:has-text("关闭")')
      if (await closeBtn.count() > 0) {
        await closeBtn.click()
        await page.waitForTimeout(400)
      }
    }

    // 4. 打开扫描件的“脱敏对比”
    if (await compareBtns.count() > 1) {
      console.log('正在打开扫描件文档的脱敏对比弹窗...')
      await compareBtns.nth(1).click()
      await page.waitForTimeout(800)
      const scannedComparePath = path.join(outDir, 'scanned_ocr_pii_compare.png')
      await page.screenshot({ path: scannedComparePath, fullPage: true })
      console.log(`已捕获: ${scannedComparePath}`)
    }

    await page.close()
  } catch (err) {
    console.error('M1 截图执行异常:', err)
  } finally {
    await browser.close()
    process.exit(0)
  }
}

run().catch((err) => {
  console.error(err)
  process.exit(1)
})
