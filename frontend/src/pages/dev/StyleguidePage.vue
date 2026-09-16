<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Sparkles,
  RefreshCw,
  Send,
} from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

// 后端连通性测试状态
const healthStatus = ref<any>(null)
const modelTestStatus = ref<any>(null)
const testingModel = ref(false)

async function checkHealth() {
  try {
    const res = await fetch('/api/health')
    healthStatus.value = await res.json()
  } catch (err: any) {
    healthStatus.value = { status: 'error', error: err.message }
  }
}

async function testModelConnectivity() {
  testingModel.value = true
  modelTestStatus.value = null
  try {
    const res = await fetch('/api/settings/models/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    })
    modelTestStatus.value = await res.json()
  } catch (err: any) {
    modelTestStatus.value = { ok: false, error: err.message }
  } finally {
    testingModel.value = false
  }
}

onMounted(() => {
  checkHealth()
})
</script>

<template>
  <div class="styleguide-page">
    <header class="section-header">
      <h1 class="page-title">设计系统与规范验证</h1>
      <p class="page-subtitle">
        基于《保单簿 PolicyBook 开发指导手册》第 7 章：纸本与护面玻璃、定常语义色与克制动效。
      </p>
    </header>

    <!-- 后端联通探针 -->
    <section class="glass section-panel">
      <div class="panel-header">
        <h2 class="panel-title">后端服务与模型连通测试</h2>
        <button class="btn-secondary" @click="checkHealth">
          <RefreshCw :size="14" />
          刷新健康状态
        </button>
      </div>

      <div class="probe-grid">
        <div class="probe-item">
          <div class="probe-label">/api/health</div>
          <div class="probe-content">
            <span v-if="healthStatus?.status === 'ok'" class="badge badge--ok">
              <span class="badge-dot"></span> 健康运行 (v{{ healthStatus.version }})
            </span>
            <span v-else class="badge badge--risk">
              <span class="badge-dot"></span> 异常: {{ healthStatus?.error || '连接中...' }}
            </span>
          </div>
        </div>

        <div class="probe-item">
          <div class="probe-label">模型探针 /api/settings/models/test</div>
          <div class="probe-content">
            <button
              class="btn-primary"
              :disabled="testingModel"
              @click="testModelConnectivity"
            >
              <Send :size="14" />
              {{ testingModel ? '测试中...' : '发起连通测试' }}
            </button>
            <div v-if="modelTestStatus" class="model-result">
              <span v-if="modelTestStatus.ok" class="badge badge--ok">
                <span class="badge-dot"></span> {{ modelTestStatus.display_name }} ({{ modelTestStatus.latency_ms }}ms)
              </span>
              <span v-else class="badge badge--pending">
                <span class="badge-dot"></span> {{ modelTestStatus.display_name }}: {{ modelTestStatus.error }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 色板展示 -->
    <section class="glass section-panel">
      <h2 class="panel-title">1. 色板体系 (Palette)</h2>
      <p class="panel-desc">语义色固定不得挪用：青瓷代表已核验、杏黄代表待确认、朱砂代表缺口/冲突、暮紫代表模型生成。</p>

      <div class="palette-grid">
        <div class="color-chip" style="background: var(--c-mist); color: var(--c-pool)">
          <span class="chip-name">雾白 Mist</span>
          <span class="chip-val">#EEF2F6</span>
          <span class="chip-desc">浅色背景</span>
        </div>
        <div class="color-chip" style="background: var(--c-pool); color: #fff">
          <span class="chip-name">深潭 Pool</span>
          <span class="chip-val">#14233A</span>
          <span class="chip-desc">主文字 / 深色背景</span>
        </div>
        <div class="color-chip" style="background: var(--c-celadon); color: #fff">
          <span class="chip-name">青瓷 Celadon</span>
          <span class="chip-val">#2A8F82</span>
          <span class="chip-desc">已核验 / 主操作</span>
        </div>
        <div class="color-chip" style="background: var(--c-apricot); color: #fff">
          <span class="chip-name">杏黄 Apricot</span>
          <span class="chip-val">#C98217</span>
          <span class="chip-desc">待确认 / 等待期</span>
        </div>
        <div class="color-chip" style="background: var(--c-cinnabar); color: #fff">
          <span class="chip-name">朱砂 Cinnabar</span>
          <span class="chip-val">#C8443B</span>
          <span class="chip-desc">缺口 / 冲突 / 免责</span>
        </div>
        <div class="color-chip" style="background: var(--c-dusk); color: #fff">
          <span class="chip-name">暮紫 Dusk</span>
          <span class="chip-val">#5E54C9</span>
          <span class="chip-desc">模型生成内容标记</span>
        </div>
        <div class="color-chip" style="background: var(--c-paper); color: #14233A; border: 1px solid #e0dcd0">
          <span class="chip-name">纸 Paper</span>
          <span class="chip-val">#FFFDF8</span>
          <span class="chip-desc">合同原文阅读底色</span>
        </div>
      </div>
    </section>

    <!-- 字号阶梯 -->
    <section class="glass section-panel">
      <h2 class="panel-title">2. 字体与字号阶梯</h2>
      <p class="panel-desc">UI 使用 HarmonyOS Sans SC，原文引用使用思源宋体 Source Han Serif SC。</p>

      <div class="type-scale-list">
        <div class="type-row">
          <span class="type-meta">--fs-34 (2.125rem)</span>
          <span style="font-size: var(--fs-34); font-weight: 700">家庭保障总览 500,000 元</span>
        </div>
        <div class="type-row">
          <span class="type-meta">--fs-28 (1.75rem)</span>
          <span style="font-size: var(--fs-28); font-weight: 700">重大疾病与医疗保障</span>
        </div>
        <div class="type-row">
          <span class="type-meta">--fs-23 (1.4375rem)</span>
          <span style="font-size: var(--fs-23); font-weight: 600">平安守护意外伤害保险</span>
        </div>
        <div class="type-row">
          <span class="type-meta">--fs-19 (1.1875rem)</span>
          <span style="font-size: var(--fs-19); font-weight: 500">基本责任：意外身故伤残保障</span>
        </div>
        <div class="type-row">
          <span class="type-meta">--fs-16 (1rem)</span>
          <span style="font-size: var(--fs-16)">正文基准字号：被保险人在等待期后经专科医生确诊初次发生本合同约定的重大疾病。</span>
        </div>
        <div class="type-row">
          <span class="type-meta">--fs-14 (0.875rem)</span>
          <span style="font-size: var(--fs-14); color: var(--text-muted)">辅助正文与元数据说明（行高 1.6）</span>
        </div>
        <div class="type-row">
          <span class="type-meta">--fs-12 (0.75rem)</span>
          <span style="font-size: var(--fs-12); color: var(--text-muted)">状态标签与脚注字号</span>
        </div>
      </div>
    </section>

    <!-- 状态徽标与标记 -->
    <section class="glass section-panel">
      <h2 class="panel-title">3. 状态徽标与模型标记</h2>
      <p class="panel-desc">状态严禁仅靠颜色区分，圆点与文字必须并存。模型内容带暮紫色图标标注。</p>

      <div class="badge-group">
        <span class="badge badge--ok">
          <span class="badge-dot"></span> 已核验 (Verified)
        </span>
        <span class="badge badge--pending">
          <span class="badge-dot"></span> 待确认 (Pending)
        </span>
        <span class="badge badge--risk">
          <span class="badge-dot"></span> 冲突 / 缺口 (Conflict)
        </span>
        <span class="badge badge--ai">
          <span class="badge-dot"></span> 模型生成 (Generated)
        </span>
      </div>

      <div class="ai-block" style="margin-top: var(--sp-4);">
        <div class="ai-tag">
          <Sparkles :size="14" />
          <span>由模型根据条款整理</span>
        </div>
        <p style="font-size: var(--fs-14); margin-top: var(--sp-2)">
          本保单包含 30 万元意外伤害医疗保障，社保范围内费用 100 元免赔额后按 100% 赔付。未经社保按 80% 赔付。
        </p>
      </div>
    </section>

    <!-- 按钮体系 -->
    <section class="glass section-panel">
      <h2 class="panel-title">4. 按钮系统 (Buttons)</h2>
      <p class="panel-desc">主按钮青瓷实底，次按钮玻璃底，危险操作朱砂描边，文字说明动作结果。</p>

      <div class="btn-group">
        <button class="btn-primary">
          <CheckCircle2 :size="16" />
          确认入库
        </button>
        <button class="btn-secondary">
          <RefreshCw :size="16" />
          重新抽取
        </button>
        <button class="btn-danger">
          <AlertCircle :size="16" />
          删除保单
        </button>
        <button class="btn-primary" disabled>
          禁用状态
        </button>
      </div>
    </section>

    <!-- 原文引用卡片 -->
    <section class="glass section-panel">
      <h2 class="panel-title">5. 原文引用卡片 (Quote Cards)</h2>
      <p class="panel-desc">使用思源宋体，左侧细竖线指明校验状态，底部标注出处页码。</p>

      <div class="quote-card">
        <p>「被保险人因遭受意外伤害事故，并自事故发生之日起一百八十日内因该事故身故的，本公司按保险金额给付身故保险金。」</p>
        <span style="font-size: var(--fs-12); color: var(--text-muted); display: block; margin-top: var(--sp-1)">第 4 页 · 条款第 2.1 条</span>
      </div>

      <div class="quote-card quote-card--pending">
        <p>「等待期为合同生效之日起九十日。等待期内确诊重大疾病的，退还已交保费，合同终止。」</p>
        <span style="font-size: var(--fs-12); color: var(--text-muted); display: block; margin-top: var(--sp-1)">第 7 页 · 条款第 3.2 条 (待确认)</span>
      </div>

      <div class="quote-card quote-card--risk">
        <p>「被保险人从事潜水、跳伞、攀岩、蹦极等高风险运动期间遭受的意外伤害，本公司不承担给付保险金责任。」</p>
        <span style="font-size: var(--fs-12); color: var(--text-muted); display: block; margin-top: var(--sp-1)">第 12 页 · 责任免除 (免责)</span>
      </div>
    </section>

    <!-- 表单控件 -->
    <section class="glass section-panel">
      <h2 class="panel-title">6. 表单规范 (Forms)</h2>
      <p class="panel-desc">标签在上方，错误提示明确说明原因与修改指引。</p>

      <div class="form-demo-grid">
        <div class="form-group">
          <label class="form-label">基本保额</label>
          <input type="text" class="form-input" value="500,000 元" />
        </div>

        <div class="form-group">
          <label class="form-label">年保费</label>
          <input type="text" class="form-input" value="abc" />
          <span class="form-error">保费需要是有效数字，例如 1280</span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.styleguide-page {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}

.section-header {
  margin-bottom: var(--sp-2);
}

.page-title {
  font-size: var(--fs-28);
  font-weight: 700;
  letter-spacing: -0.02em;
}

.page-subtitle {
  font-size: var(--fs-14);
  color: var(--text-muted);
  margin-top: var(--sp-1);
}

.section-panel {
  padding: var(--sp-5);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-4);
}

.panel-title {
  font-size: var(--fs-19);
  font-weight: 600;
  margin-bottom: var(--sp-1);
}

.panel-desc {
  font-size: var(--fs-14);
  color: var(--text-muted);
  margin-bottom: var(--sp-4);
}

/* 探针 */
.probe-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--sp-4);
}

.probe-item {
  padding: var(--sp-3);
  border-radius: var(--r-control);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
}

.probe-label {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-bottom: var(--sp-2);
}

.probe-content {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.model-result {
  margin-top: var(--sp-2);
}

/* 色板 */
.palette-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: var(--sp-3);
}

.color-chip {
  padding: var(--sp-3);
  border-radius: var(--r-control);
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-height: 90px;
}

.chip-name {
  font-weight: 600;
  font-size: var(--fs-14);
}

.chip-val {
  font-size: var(--fs-12);
  opacity: 0.85;
  font-variant-numeric: tabular-nums;
}

.chip-desc {
  font-size: 11px;
  opacity: 0.75;
  margin-top: auto;
}

/* 字号 */
.type-scale-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.type-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid color-mix(in oklch, var(--text) 8%, transparent);
}

.type-meta {
  font-size: var(--fs-12);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

/* 徽标 */
.badge-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
}

/* 按钮 */
.btn-group {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3);
}

/* 表单 */
.form-demo-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: var(--sp-4);
}

.ai-block {
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--r-control);
  background: color-mix(in oklch, var(--ai) 8%, transparent);
  border: 1px solid color-mix(in oklch, var(--ai) 25%, transparent);
}
</style>
