import { chromium } from '../frontend/node_modules/playwright/index.mjs'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')
const outDir = path.join(rootDir, 'docs', 'screenshots', 'm6')
const brainDir = 'C:\\Users\\lishi\\.gemini\\antigravity\\brain\\ed0913bc-da14-4c1e-96ba-0cedaf3a0c90'

fs.mkdirSync(outDir, { recursive: true })

async function run() {
  console.log('启动 Edge 浏览器捕获 M6 阶段（PPT 导出与评测看板）截图...')
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
  })

  // 1. 桌面端 (1440x900)
  const page = await browser.newPage({
    viewport: { width: 1440, height: 900 },
  })

  try {
    // -----------------------------------------------------------------
    // 1. 全家保单 PPT 导出页 (Reports Page)
    // -----------------------------------------------------------------
    console.log('访问 Reports 页面 http://127.0.0.1:5173/reports ...')
    await page.goto('http://127.0.0.1:5173/reports', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)

    // 点击一键生成并等待核验完成
    const generateBtn = page.locator('.btn-primary')
    if (await generateBtn.count() > 0) {
      console.log('点击生成 PPT 报告...')
      await generateBtn.first().click()
      // 等待生成与核验卡片出现
      await page.waitForSelector('.verification-alert', { timeout: 15000 })
      await page.waitForTimeout(1000)
    }

    // 截图 1: 桌面端 Reports 完整页面
    const reports1440 = path.join(outDir, 'reports_page_1440.png')
    await page.screenshot({ path: reports1440, fullPage: true })
    console.log(`已捕获桌面端 Reports 页面: ${reports1440}`)

    // 截图 2: 反向回读核验卡片特写
    const alertEl = page.locator('.verification-alert')
    if (await alertEl.count() > 0) {
      const alertPath = path.join(outDir, 'reports_verification_closeup.png')
      await alertEl.first().screenshot({ path: alertPath })
      console.log(`已捕获核验通过特写: ${alertPath}`)
    }

    // 截图 3: 16:9 标准版式预览区特写
    const previewEl = page.locator('.preview-section')
    if (await previewEl.count() > 0) {
      const previewPath = path.join(outDir, 'reports_slides_preview_closeup.png')
      await previewEl.first().screenshot({ path: previewPath })
      console.log(`已捕获版式预览区特写: ${previewPath}`)
    }

    // -----------------------------------------------------------------
    // 2. 评测看板页 (Eval Dashboard Page)
    // -----------------------------------------------------------------
    console.log('访问 Eval 看板页面 http://127.0.0.1:5173/eval ...')
    await page.goto('http://127.0.0.1:5173/eval', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1500)

    // 截图 4: 桌面端 Eval 看板完整页面
    const eval1440 = path.join(outDir, 'eval_dashboard_1440.png')
    await page.screenshot({ path: eval1440, fullPage: true })
    console.log(`已捕获桌面端 Eval 看板页面: ${eval1440}`)

    // 截图 5: 模型对比指标卡片特写
    const metricsEl = page.locator('.metrics-grid')
    if (await metricsEl.count() > 0) {
      const metricsPath = path.join(outDir, 'eval_metrics_closeup.png')
      await metricsEl.first().screenshot({ path: metricsPath })
      console.log(`已捕获模型对比指标特写: ${metricsPath}`)
    }

    // 截图 6: 点击单次运行查看调用明细抽屉/弹窗
    const detailBtn = page.locator('.btn-detail')
    if (await detailBtn.count() > 0) {
      console.log('打开评测批次调用明细弹窗...')
      await detailBtn.first().click()
      await page.waitForSelector('.modal-card', { timeout: 5000 })
      await page.waitForTimeout(800)

      const modalEl = page.locator('.modal-card')
      const modalPath = path.join(outDir, 'eval_trace_modal_closeup.png')
      await modalEl.screenshot({ path: modalPath })
      console.log(`已捕获调用明细弹窗特写: ${modalPath}`)

      // 关闭弹窗
      await page.locator('.btn-close').click()
      await page.waitForTimeout(500)
    }

    // -----------------------------------------------------------------
    // 3. 响应式断点截屏 (768 平板 & 390 手机端)
    // -----------------------------------------------------------------
    // 768 平板端 Reports
    await page.setViewportSize({ width: 768, height: 1024 })
    await page.goto('http://127.0.0.1:5173/reports', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)
    const reports768 = path.join(outDir, 'reports_page_768.png')
    await page.screenshot({ path: reports768, fullPage: true })
    console.log(`已捕获平板端 Reports 页面: ${reports768}`)

    // 768 平板端 Eval
    await page.goto('http://127.0.0.1:5173/eval', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)
    const eval768 = path.join(outDir, 'eval_dashboard_768.png')
    await page.screenshot({ path: eval768, fullPage: true })
    console.log(`已捕获平板端 Eval 页面: ${eval768}`)

    // 390 手机端 Reports
    await page.setViewportSize({ width: 390, height: 844 })
    await page.goto('http://127.0.0.1:5173/reports', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)
    const reports390 = path.join(outDir, 'reports_page_390.png')
    await page.screenshot({ path: reports390, fullPage: true })
    console.log(`已捕获手机端 Reports 页面: ${reports390}`)

    // 390 手机端 Eval
    await page.goto('http://127.0.0.1:5173/eval', { waitUntil: 'networkidle' })
    await page.waitForTimeout(1000)
    const eval390 = path.join(outDir, 'eval_dashboard_390.png')
    await page.screenshot({ path: eval390, fullPage: true })
    console.log(`已捕获手机端 Eval 页面: ${eval390}`)

    // 复制关键截图到 brainDir 供上下文直接内嵌预览
    const copyPairs = [
      ['reports_page_1440.png', 'reports_page_1440.png'],
      ['reports_verification_closeup.png', 'reports_verification_closeup.png'],
      ['reports_slides_preview_closeup.png', 'reports_slides_preview_closeup.png'],
      ['eval_dashboard_1440.png', 'eval_dashboard_1440.png'],
      ['eval_metrics_closeup.png', 'eval_metrics_closeup.png'],
      ['eval_trace_modal_closeup.png', 'eval_trace_modal_closeup.png'],
      ['reports_page_390.png', 'reports_page_390.png'],
      ['eval_dashboard_390.png', 'eval_dashboard_390.png'],
    ]

    for (const [src, dst] of copyPairs) {
      const srcPath = path.join(outDir, src)
      if (fs.existsSync(srcPath)) {
        fs.copyFileSync(srcPath, path.join(brainDir, dst))
      }
    }
    console.log('所有 M6 截图已捕获并完成多端同步！')

  } finally {
    await browser.close()
  }
}

run().catch(err => {
  console.error('截图执行发生异常:', err)
  process.exit(1)
})
