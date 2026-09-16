<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Calculator,
  Calendar,
  AlertCircle,
  FileCheck,
  ShieldCheck,
  Sparkles,
  ChevronRight,
  Info,
  Building,
  User,
  ExternalLink,
  Receipt,
  HeartPulse,
} from 'lucide-vue-next'
import WaterfallChart, { WaterfallStep } from '@/components/charts/WaterfallChart.vue'
import DocViewer, { PageMeta, HighlightTarget } from '@/components/doc-viewer/DocViewer.vue'

interface Member {
  id: string
  display_name: string
  placeholder: string
  color: string
}

interface Policy {
  id: string
  product_name: string
  insurer: string
  category: string
  document_id?: string
}

interface ClaimResponse {
  member_id: string
  member_name: string
  event_kind: string
  event_date: string
  extracted_facts: string[]
  waterfall_steps: WaterfallStep[]
  lump_sums: Array<{
    coverage_id: string
    coverage_name: string
    policy_name: string
    amount: number
    note?: string
    evidence_quote?: string
    evidence_page_no?: number
    evidence_rects?: Array<{ x0: number; y0: number; x1: number; y1: number }>
  }>
  excluded: Array<{
    coverage_id: string
    coverage_name: string
    policy_name: string
    reason: string
  }>
  out_of_pocket_low: number
  out_of_pocket_high: number
  confirm_with_insurer: string[]
  materials_needed: string[]
}

const members = ref<Member[]>([])
const policies = ref<Policy[]>([])

// 表单状态
const selectedMemberId = ref('')
const eventKind = ref<'illness' | 'accident' | 'death' | 'other'>('illness')
const eventDate = ref('2025-05-15')
const description = ref('因急性化脓性阑尾炎在公立三级甲等医院普外科住院治疗，行腹腔镜阑尾切除术，住院 4 天。')
const totalCost = ref(18500)
const hasSi = ref(true)
const siReimbursed = ref<number | null>(8200)
const siCoveredCost = ref<number | null>(12000)
const city = ref('北京')

const isSimulating = ref(false)
const claimResult = ref<ClaimResponse | null>(null)

// 抽屉状态
const drawerOpen = ref(false)
const drawerPages = ref<PageMeta[]>([])
const activeHighlight = ref<HighlightTarget | null>(null)
const drawerPolicyTitle = ref('')

onMounted(async () => {
  try {
    const [mRes, pRes] = await Promise.all([
      fetch('/api/members'),
      fetch('/api/policies'),
    ])
    if (mRes.ok) {
      members.value = await mRes.json()
      if (members.value.length > 0) {
        selectedMemberId.value = members.value[0].id
      }
    }
    if (pRes.ok) {
      policies.value = await pRes.json()
    }
  } catch (err) {
    console.error('Failed to init data', err)
  }
})

// 快捷示例
function loadExample(type: 'appendix' | 'fracture' | 'cancer') {
  if (type === 'appendix') {
    eventKind.value = 'illness'
    description.value = '因急性化脓性阑尾炎在公立三级甲等医院普外科住院治疗，行腹腔镜阑尾切除术，住院 4 天。'
    totalCost.value = 18500
    hasSi.value = true
    siReimbursed.value = 8200
    siCoveredCost.value = 12000
  } else if (type === 'fracture') {
    eventKind.value = 'accident'
    description.value = '骑自行车不慎滑倒造成右侧锁骨骨折，急诊拍片并住院行内固定手术治疗。'
    totalCost.value = 24000
    hasSi.value = true
    siReimbursed.value = 9500
    siCoveredCost.value = 15000
  } else if (type === 'cancer') {
    eventKind.value = 'illness'
    description.value = '体检发现肺部结节，经穿刺病理活检确诊为原发性浸润性肺腺癌（早期）。'
    totalCost.value = 65000
    hasSi.value = true
    siReimbursed.value = 28000
    siCoveredCost.value = 42000
  }
}

async function runSimulation() {
  if (!selectedMemberId.value) {
    alert('请选择出险的家庭成员')
    return
  }
  if (!totalCost.value || totalCost.value <= 0) {
    alert('请输入有效的总医疗费用')
    return
  }

  isSimulating.value = true
  try {
    const res = await fetch('/api/claim/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        member_id: selectedMemberId.value,
        event_kind: eventKind.value,
        event_date: eventDate.value,
        description: description.value,
        total_cost: totalCost.value,
        has_si: hasSi.value,
        si_reimbursed: hasSi.value ? siReimbursed.value : 0,
        si_covered_cost: hasSi.value ? siCoveredCost.value : null,
        city: city.value,
      }),
    })

    if (res.ok) {
      claimResult.value = await res.json()
    } else {
      const err = await res.json()
      alert(`测算失败：${err?.error?.message || res.statusText}`)
    }
  } catch (err: any) {
    alert(`请求异常：${err.message}`)
  } finally {
    isSimulating.value = false
  }
}

// 点击瀑布图步骤或责任卡片查看原文
async function openEvidence(item: {
  coverage_id?: string | null
  evidence_quote?: string | null
  evidence_page_no?: number | null
  evidence_rects?: Array<{ x0: number; y0: number; x1: number; y1: number }>
}) {
  if (!item.evidence_quote) return

  try {
    // 若已知 coverage_id，找对应保单的 pages
    let docId = ''
    if (item.coverage_id) {
      // 遍历已存保单寻找
      for (const p of policies.value) {
        if (p.id) {
          const pRes = await fetch(`/api/policies/${p.id}`)
          if (pRes.ok) {
            const pData = await pRes.json()
            if (pData.coverages?.some((c: any) => c.id === item.coverage_id)) {
              drawerPages.value = pData.pages || []
              drawerPolicyTitle.value = pData.product_name
              docId = pData.document_id
              break
            }
          }
        }
      }
    }

    if (drawerPages.value.length === 0 && policies.value.length > 0) {
      const pRes = await fetch(`/api/policies/${policies.value[0].id}`)
      if (pRes.ok) {
        const pData = await pRes.json()
        drawerPages.value = pData.pages || []
        drawerPolicyTitle.value = pData.product_name
      }
    }

    activeHighlight.value = {
      page_no: item.evidence_page_no || 1,
      rects: item.evidence_rects || [],
      status: 'verified',
    }
    drawerOpen.value = true
  } catch (err) {
    console.error('Failed to open evidence drawer', err)
  }
}
</script>

<template>
  <div class="claim-page-layout">
    <!-- 左侧：录入与控制面板 -->
    <div class="form-panel glass">
      <div class="panel-header">
        <h2 class="panel-title">
          <Calculator class="w-5 h-5 mr-2 text-[var(--primary)]" />
          理赔情景模拟
        </h2>
        <p class="panel-desc">
          输入就医费用与出险情况，模拟社保抵扣、小额与百万医疗梯次补偿及定额给付。
        </p>
      </div>

      <!-- 快速预设示例 -->
      <div class="preset-box">
        <span class="preset-title">快速载入情景：</span>
        <div class="preset-buttons">
          <button class="preset-btn" @click="loadExample('appendix')">急性阑尾炎住院</button>
          <button class="preset-btn" @click="loadExample('fracture')">意外摔倒锁骨骨折</button>
          <button class="preset-btn" @click="loadExample('cancer')">确诊早期肺腺癌</button>
        </div>
      </div>

      <!-- 表单字段 -->
      <div class="form-body">
        <!-- 成员选择 -->
        <div class="form-group">
          <label class="form-label">
            <User class="w-4 h-4 mr-1 text-[var(--text-3)]" />
            出险家庭成员
          </label>
          <select v-model="selectedMemberId" class="form-input select-input">
            <option v-for="m in members" :key="m.id" :value="m.id">
              {{ m.display_name }} ({{ m.placeholder }})
            </option>
          </select>
        </div>

        <!-- 事件类型与日期 -->
        <div class="form-row">
          <div class="form-group flex-1">
            <label class="form-label">事件类别</label>
            <div class="radio-tabs">
              <button
                type="button"
                class="radio-tab"
                :class="{ active: eventKind === 'illness' }"
                @click="eventKind = 'illness'"
              >
                疾病
              </button>
              <button
                type="button"
                class="radio-tab"
                :class="{ active: eventKind === 'accident' }"
                @click="eventKind = 'accident'"
              >
                意外
              </button>
              <button
                type="button"
                class="radio-tab"
                :class="{ active: eventKind === 'death' }"
                @click="eventKind = 'death'"
              >
                身故
              </button>
              <button
                type="button"
                class="radio-tab"
                :class="{ active: eventKind === 'other' }"
                @click="eventKind = 'other'"
              >
                其他
              </button>
            </div>
          </div>

          <div class="form-group w-36">
            <label class="form-label">
              <Calendar class="w-4 h-4 mr-1 text-[var(--text-3)]" />
              出险日期
            </label>
            <input v-model="eventDate" type="date" class="form-input" />
          </div>
        </div>

        <!-- 出险自述 -->
        <div class="form-group">
          <label class="form-label">病情或事故描述（用于匹配条款）</label>
          <textarea
            v-model="description"
            rows="3"
            class="form-input textarea-input"
            placeholder="例如：因急性肠胃炎在公立三级医院住院3天，自费药500元..."
          />
        </div>

        <!-- 医疗费用 -->
        <div class="form-row">
          <div class="form-group flex-1">
            <label class="form-label">
              <Receipt class="w-4 h-4 mr-1 text-[var(--text-3)]" />
              总医疗花费 (元)
            </label>
            <input
              v-model.number="totalCost"
              type="number"
              min="0"
              class="form-input"
              placeholder="0.00"
            />
          </div>
          <div class="form-group w-32">
            <label class="form-label">
              <Building class="w-4 h-4 mr-1 text-[var(--text-3)]" />
              就诊城市
            </label>
            <input v-model="city" type="text" class="form-input" placeholder="如：北京" />
          </div>
        </div>

        <!-- 医保设置 -->
        <div class="si-box">
          <div class="si-header">
            <label class="checkbox-label">
              <input v-model="hasSi" type="checkbox" class="accent-[var(--primary)]" />
              <span>已按社会医疗保险 (社保/医保) 结算</span>
            </label>
          </div>

          <div v-if="hasSi" class="si-fields">
            <div class="form-group flex-1">
              <label class="form-label">社保实际报销金额 (元)</label>
              <input
                v-model.number="siReimbursed"
                type="number"
                min="0"
                class="form-input"
                placeholder="实际医保报销"
              />
            </div>
            <div class="form-group flex-1">
              <label class="form-label">社保范围内费用 (元)</label>
              <input
                v-model.number="siCoveredCost"
                type="number"
                min="0"
                class="form-input"
                placeholder="社保内合规费用"
              />
            </div>
          </div>
        </div>

        <!-- 提交按钮 -->
        <button
          class="submit-btn"
          :disabled="isSimulating"
          @click="runSimulation"
        >
          <Sparkles class="w-4 h-4 mr-1" />
          <span>{{ isSimulating ? '正在提取事实并纯函数计算...' : '开始理赔模拟测算' }}</span>
        </button>
      </div>
    </div>

    <!-- 右侧：测算结果展示区 -->
    <div class="result-panel glass">
      <div v-if="!claimResult && !isSimulating" class="empty-state">
        <HeartPulse class="w-12 h-12 text-[var(--text-3)] mb-2 opacity-50" />
        <div class="text-[var(--text-2)] font-medium">请在左侧填写或选择出险情景并开始测算</div>
        <div class="text-[var(--text-3)] text-xs mt-1">系统将基于保单条款顺序抵扣并绘制费用瀑布图</div>
      </div>

      <div v-else-if="isSimulating" class="loading-state">
        <Sparkles class="w-8 h-8 text-[var(--primary)] animate-spin mb-3" />
        <div class="text-[var(--text-1)] font-medium">大模型正在提取出险事实与匹配保单责任...</div>
        <div class="text-[var(--text-3)] text-xs mt-1">纯代码引擎将根据等待期、免赔额与比例精确计算区间</div>
      </div>

      <!-- 结果详情区 -->
      <div v-else-if="claimResult" class="results-container">
        <!-- 概览卡片 -->
        <div class="summary-cards-grid">
          <div class="summary-card">
            <div class="card-label">总医疗费用</div>
            <div class="card-value font-mono">¥{{ totalCost.toLocaleString() }}</div>
          </div>
          <div class="summary-card">
            <div class="card-label">预估个人最终自付</div>
            <div class="card-value text-[var(--danger)] font-mono">
              ¥{{ claimResult.out_of_pocket_low.toLocaleString() }}
              <span v-if="claimResult.out_of_pocket_low !== claimResult.out_of_pocket_high">
                ~ ¥{{ claimResult.out_of_pocket_high.toLocaleString() }}
              </span>
            </div>
          </div>
          <div v-if="claimResult.lump_sums?.length" class="summary-card">
            <div class="card-label">定额给付赔偿金 (重疾/身故)</div>
            <div class="card-value text-[var(--ok)] font-mono">
              ¥{{ claimResult.lump_sums.reduce((acc, l) => acc + l.amount, 0).toLocaleString() }}
            </div>
          </div>
        </div>

        <!-- 费用瀑布图 -->
        <div class="chart-section glass">
          <div class="section-title">
            <Receipt class="w-4 h-4 mr-1 text-[var(--primary)]" />
            费用抵扣与赔付瀑布图 (点击柱段查看条款依据)
          </div>
          <WaterfallChart
            :steps="claimResult.waterfall_steps"
            :out-of-pocket-low="claimResult.out_of_pocket_low"
            :out-of-pocket-high="claimResult.out_of_pocket_high"
            @select-step="openEvidence"
          />
        </div>

        <!-- 参与赔付的责任项清单 -->
        <div class="breakdown-section">
          <div class="section-title">
            <ShieldCheck class="w-4 h-4 mr-1 text-[var(--primary)]" />
            分保单赔付明细与责任拆解
          </div>
          <div class="coverage-cards-list">
            <div
              v-for="(step, sIdx) in claimResult.waterfall_steps.slice(2)"
              :key="sIdx"
              class="coverage-card"
            >
              <div class="cov-card-header">
                <div>
                  <span class="cov-title">{{ step.label }}</span>
                  <span v-if="step.policy_name" class="cov-policy">({{ step.policy_name }})</span>
                </div>
                <div class="cov-amount font-mono">
                  抵扣 ¥{{ step.amount_low.toLocaleString() }}
                </div>
              </div>
              <div class="cov-note">{{ step.note || '补偿型医疗赔付' }}</div>
              <!-- 原文依据按钮 -->
              <div v-if="step.evidence_quote" class="cov-evidence-bar">
                <button class="evidence-link-btn" @click="openEvidence(step)">
                  <FileCheck class="w-3.5 h-3.5 mr-1 text-[var(--primary)]" />
                  <span>条款依据: “{{ step.evidence_quote.slice(0, 32) }}...”</span>
                  <ChevronRight class="w-3 h-3 ml-1" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 定额给付型责任 (独立计算) -->
        <div v-if="claimResult.lump_sums?.length" class="breakdown-section">
          <div class="section-title text-[var(--ok)]">
            <Sparkles class="w-4 h-4 mr-1" />
            定额给付责任 (不抵扣医疗费用)
          </div>
          <div class="coverage-cards-list">
            <div
              v-for="(l, lIdx) in claimResult.lump_sums"
              :key="lIdx"
              class="coverage-card lump-sum-card"
            >
              <div class="cov-card-header">
                <div>
                  <span class="cov-title">{{ l.coverage_name }}</span>
                  <span class="cov-policy">({{ l.policy_name }})</span>
                </div>
                <div class="cov-amount font-mono text-[var(--ok)]">
                  全额给付 ¥{{ l.amount.toLocaleString() }}
                </div>
              </div>
              <div class="cov-note">{{ l.note }}</div>
              <div v-if="l.evidence_quote" class="cov-evidence-bar">
                <button class="evidence-link-btn" @click="openEvidence(l)">
                  <FileCheck class="w-3.5 h-3.5 mr-1 text-[var(--primary)]" />
                  <span>条款依据: “{{ l.evidence_quote.slice(0, 32) }}...”</span>
                  <ChevronRight class="w-3 h-3 ml-1" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- 等待期排除项 -->
        <div v-if="claimResult.excluded?.length" class="breakdown-section">
          <div class="section-title text-[var(--warning)]">
            <AlertCircle class="w-4 h-4 mr-1" />
            排除责任项 (等待期内出险)
          </div>
          <div class="excluded-list">
            <div v-for="(ex, eIdx) in claimResult.excluded" :key="eIdx" class="excluded-item">
              <div class="excluded-header">
                <span class="font-medium">{{ ex.coverage_name }}</span>
                <span class="text-xs text-[var(--text-3)]">({{ ex.policy_name }})</span>
              </div>
              <div class="excluded-reason">{{ ex.reason }}</div>
            </div>
          </div>
        </div>

        <!-- 确认事项与材料清单 -->
        <div class="info-columns-grid">
          <div class="info-card glass">
            <div class="info-card-title text-[var(--amber)]">
              <AlertCircle class="w-4 h-4 mr-1" />
              向保险公司确认事项
            </div>
            <ul class="info-list">
              <li v-for="(c, cIdx) in claimResult.confirm_with_insurer" :key="cIdx">
                {{ c }}
              </li>
            </ul>
          </div>

          <div class="info-card glass">
            <div class="info-card-title text-[var(--primary)]">
              <FileCheck class="w-4 h-4 mr-1" />
              建议准备理赔材料
            </div>
            <ul class="info-list">
              <li v-for="(m, mIdx) in claimResult.materials_needed" :key="mIdx">
                {{ m }}
              </li>
            </ul>
          </div>
        </div>

        <!-- 固定免责声明 -->
        <div class="disclaimer-note">
          <Info class="w-4 h-4 mr-1.5 flex-shrink-0" />
          <span>
            保单簿根据你上传的合同文本整理信息，帮助你理解条款和估算大致范围。所有结论以保险公司的核定和合同原文为准，本工具不构成投保建议、核保意见或理赔承诺。
          </span>
        </div>
      </div>
    </div>

    <!-- 右侧阅读器抽屉 -->
    <div v-if="drawerOpen" class="drawer-overlay" @click.self="drawerOpen = false">
      <div class="drawer-container glass">
        <DocViewer
          :pages="drawerPages"
          :active-highlight="activeHighlight"
          :is-drawer="true"
          @close="drawerOpen = false"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.claim-page-layout {
  display: flex;
  height: calc(100vh - 64px);
  position: relative;
  overflow: hidden;
}

/* 左侧表单面板 */
.form-panel {
  width: 440px;
  min-width: 360px;
  height: 100%;
  overflow-y: auto;
  padding: var(--sp-5);
  background: var(--surface-1);
  border-right: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
}

.panel-header {
  margin-bottom: var(--sp-4);
}

.panel-title {
  display: flex;
  align-items: center;
  font-size: var(--fs-title-md);
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: var(--sp-1);
}

.panel-desc {
  font-size: var(--fs-body-xs);
  color: var(--text-3);
  line-height: 1.4;
}

.preset-box {
  background: rgba(42, 143, 130, 0.05);
  border: 1px dashed var(--border-subtle);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--rad-control);
  margin-bottom: var(--sp-4);
}

.preset-title {
  font-size: 11px;
  color: var(--text-3);
  display: block;
  margin-bottom: var(--sp-1);
}

.preset-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
}

.preset-btn {
  padding: 3px 8px;
  border-radius: 4px;
  border: 1px solid var(--border-subtle);
  background: var(--surface-1);
  font-size: 11px;
  color: var(--primary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.preset-btn:hover {
  background: var(--primary);
  color: #fff;
}

.form-body {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}

.form-row {
  display: flex;
  gap: var(--sp-2);
}

.form-label {
  display: flex;
  align-items: center;
  font-size: var(--fs-body-xs);
  font-weight: 500;
  color: var(--text-2);
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border-radius: var(--rad-control);
  border: 1px solid var(--border-subtle);
  background: var(--surface-2);
  color: var(--text-1);
  font-size: var(--fs-body-sm);
  outline: none;
}

.form-input:focus {
  border-color: var(--primary);
}

.textarea-input {
  resize: vertical;
  font-family: inherit;
}

.radio-tabs {
  display: flex;
  border-radius: var(--rad-control);
  border: 1px solid var(--border-subtle);
  overflow: hidden;
}

.radio-tab {
  flex: 1;
  padding: 6px 0;
  text-align: center;
  border: none;
  background: var(--surface-2);
  font-size: var(--fs-body-xs);
  color: var(--text-2);
  cursor: pointer;
}

.radio-tab.active {
  background: var(--primary);
  color: #fff;
  font-weight: 500;
}

.si-box {
  border: 1px solid var(--border-subtle);
  border-radius: var(--rad-control);
  padding: var(--sp-3);
  background: rgba(0, 0, 0, 0.01);
}

.checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-body-xs);
  font-weight: 500;
  color: var(--text-1);
  cursor: pointer;
}

.si-fields {
  display: flex;
  gap: var(--sp-2);
  margin-top: var(--sp-2);
}

.submit-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 12px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--rad-control);
  font-size: var(--fs-body-md);
  font-weight: 600;
  cursor: pointer;
  margin-top: var(--sp-2);
  transition: opacity 0.15s ease;
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 右侧结果区 */
.result-panel {
  flex: 1;
  height: 100%;
  overflow-y: auto;
  padding: var(--sp-5);
  background: var(--surface-2);
}

.empty-state,
.loading-state {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.results-container {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  max-width: 900px;
  margin: 0 auto;
}

.summary-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--sp-3);
}

.summary-card {
  padding: var(--sp-4);
  border-radius: var(--rad-control);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
}

.card-label {
  font-size: var(--fs-body-xs);
  color: var(--text-3);
  margin-bottom: var(--sp-1);
}

.card-value {
  font-size: var(--fs-title-md);
  font-weight: 700;
  color: var(--text-1);
}

.chart-section {
  padding: var(--sp-4);
  border-radius: var(--rad-panel);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
}

.section-title {
  display: flex;
  align-items: center;
  font-size: var(--fs-body-sm);
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: var(--sp-3);
}

.coverage-cards-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.coverage-card {
  padding: var(--sp-3);
  border-radius: var(--rad-control);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
}

.cov-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-1);
}

.cov-title {
  font-weight: 600;
  font-size: var(--fs-body-sm);
  color: var(--text-1);
}

.cov-policy {
  font-size: var(--fs-body-xs);
  color: var(--text-3);
  margin-left: var(--sp-1);
}

.cov-amount {
  font-weight: 600;
  color: var(--primary);
  font-size: var(--fs-body-sm);
}

.cov-note {
  font-size: var(--fs-body-xs);
  color: var(--text-2);
}

.cov-evidence-bar {
  margin-top: var(--sp-2);
  padding-top: var(--sp-1);
  border-top: 1px dashed var(--border-subtle);
}

.evidence-link-btn {
  display: inline-flex;
  align-items: center;
  background: transparent;
  border: none;
  font-size: var(--fs-body-xs);
  color: var(--primary);
  cursor: pointer;
  padding: 2px 0;
}

.evidence-link-btn:hover {
  text-decoration: underline;
}

.lump-sum-card {
  border-left: 3px solid var(--ok);
}

.excluded-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.excluded-item {
  padding: var(--sp-3);
  border-radius: var(--rad-control);
  background: rgba(208, 140, 54, 0.08);
  border: 1px solid var(--warning);
}

.excluded-header {
  display: flex;
  justify-content: space-between;
  font-size: var(--fs-body-sm);
  color: var(--warning);
  margin-bottom: var(--sp-1);
}

.excluded-reason {
  font-size: var(--fs-body-xs);
  color: var(--text-2);
}

.info-columns-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
}

.info-card {
  padding: var(--sp-4);
  border-radius: var(--rad-control);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
}

.info-card-title {
  display: flex;
  align-items: center;
  font-size: var(--fs-body-xs);
  font-weight: 600;
  margin-bottom: var(--sp-2);
}

.info-list {
  list-style-type: disc;
  padding-left: var(--sp-4);
  font-size: var(--fs-body-xs);
  color: var(--text-2);
  line-height: 1.6;
}

.disclaimer-note {
  display: flex;
  align-items: flex-start;
  padding: var(--sp-3);
  border-radius: var(--rad-control);
  background: rgba(0, 0, 0, 0.03);
  font-size: 11px;
  color: var(--text-3);
  line-height: 1.5;
}

/* 抽屉 */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 999;
  display: flex;
  justify-content: flex-end;
}

.drawer-container {
  width: 650px;
  max-width: 90vw;
  height: 100%;
  background: var(--surface-1);
  border-left: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
}

@media (max-width: 900px) {
  .claim-page-layout {
    flex-direction: column;
    overflow-y: auto;
    height: auto;
  }
  .form-panel {
    width: 100%;
    height: auto;
  }
  .result-panel {
    height: auto;
  }
  .info-columns-grid {
    grid-template-columns: 1fr;
  }
}
</style>
