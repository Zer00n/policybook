<template>
  <div class="reports-page">
    <!-- Header -->
    <header class="page-header">
      <div>
        <h1 class="page-title">全家保单 PPT 报告导出</h1>
        <p class="page-subtitle">
          纯代码写入版式、颜色与核对数值，严格 16:9 比例生成，内置回读反向核验引擎保障 100% 准确性。
        </p>
      </div>
    </header>

    <!-- Main Generator Card -->
    <div class="generator-card glass">
      <div class="card-header">
        <div class="header-icon">
          <Presentation class="icon-lg" />
        </div>
        <div>
          <h2 class="section-title">生成新版家庭保单检视 PPT</h2>
          <p class="section-desc">
            汇总家庭全部有效保单、责任分布、各成员专页与未来缴费排期，自动执行数字回读核验。
          </p>
        </div>
      </div>

      <div class="form-group">
        <label for="custom-summary" class="form-label">
          首页总览简评（可选，留空将由系统自动计算统计）：
        </label>
        <textarea
          id="custom-summary"
          v-model="customSummary"
          class="text-input"
          rows="3"
          placeholder="例如：家庭基础医疗与意外保障齐全，当前年度总保费支出适中，重点关注后续重疾与定期寿险缴费期衔接..."
        ></textarea>
      </div>

      <div class="actions-row">
        <button
          class="btn-primary"
          :disabled="isGenerating"
          @click="generateReport"
        >
          <Loader2 v-if="isGenerating" class="spin icon-sm" />
          <FileDown v-else class="icon-sm" />
          <span>{{ isGenerating ? '正在生成并执行回读核验...' : '一键生成并核验 PPT 报告' }}</span>
        </button>
      </div>

      <!-- Live Verification Result Alert -->
      <div v-if="latestReport" class="verification-alert" :class="{ success: latestReport.verified, warning: !latestReport.verified }">
        <div class="alert-icon-col">
          <CheckCircle2 v-if="latestReport.verified" class="icon-md status-success" />
          <AlertTriangle v-else class="icon-md status-warning" />
        </div>
        <div class="alert-content">
          <div class="alert-title-row">
            <h3 class="alert-title">
              {{ latestReport.verified ? '反向回读核验通过：0 处数值偏差' : '回读核验发现异常' }}
            </h3>
            <span class="badge" :class="latestReport.verified ? 'badge-success' : 'badge-warning'">
              {{ latestReport.verified ? '核验通过 (100%)' : '存在偏差' }}
            </span>
          </div>
          <p class="alert-desc">
            从 PPT 文本框与表格中回读核验了 {{ latestReport.total_checked }} 项关键数值，与保单数据库快照严格一致。
          </p>
          
          <div class="stats-snapshot-grid">
            <div class="snap-item">
              <span class="snap-label">有效保单总数</span>
              <span class="snap-val">{{ latestReport.snapshot?.total_policies ?? '-' }} 份</span>
            </div>
            <div class="snap-item">
              <span class="snap-label">年度保费支出</span>
              <span class="snap-val">¥{{ (latestReport.snapshot?.total_premium_yuan ?? 0).toLocaleString() }}</span>
            </div>
            <div class="snap-item">
              <span class="snap-label">家庭身故保额</span>
              <span class="snap-val">{{ ((latestReport.snapshot?.total_death_yuan ?? 0) / 10000).toFixed(0) }} 万元</span>
            </div>
            <div class="snap-item">
              <span class="snap-label">家庭重疾保额</span>
              <span class="snap-val">{{ ((latestReport.snapshot?.total_ci_yuan ?? 0) / 10000).toFixed(0) }} 万元</span>
            </div>
          </div>

          <div class="alert-actions">
            <a
              :href="`/api/reports/ppt/${latestReport.id}/download`"
              download
              class="btn-download"
            >
              <Download class="icon-sm" />
              <span>下载 PPT 报告 (.pptx)</span>
            </a>
          </div>
        </div>
      </div>
    </div>

    <!-- PPT Preview Layout Structure -->
    <div class="preview-section glass">
      <h2 class="section-title">报告包含的标准 16:9 版式结构</h2>
      <div class="slide-deck-preview">
        <div class="slide-card">
          <div class="slide-screen">
            <div class="slide-decor"></div>
            <div class="slide-title-mock">家庭保单检视报告</div>
            <div class="slide-sub-mock">年度保障全景概览与责任分析</div>
          </div>
          <span class="slide-caption">第 1 页：专属封面</span>
        </div>

        <div class="slide-card">
          <div class="slide-screen">
            <div class="mock-grid">
              <div class="mock-cell">总保单</div>
              <div class="mock-cell">年保费</div>
              <div class="mock-cell">身故保额</div>
              <div class="mock-cell">重疾保额</div>
            </div>
            <div class="slide-sub-mock">保障结构与健康度评价</div>
          </div>
          <span class="slide-caption">第 2 页：全家总览</span>
        </div>

        <div class="slide-card">
          <div class="slide-screen">
            <div class="slide-table-mock">
              <div class="table-row header"></div>
              <div class="table-row"></div>
              <div class="table-row"></div>
            </div>
          </div>
          <span class="slide-caption">第 3..N 页：家庭成员专页</span>
        </div>

        <div class="slide-card">
          <div class="slide-screen">
            <div class="mock-timeline"></div>
            <div class="slide-sub-mock">未来 10 年缴费到期排期表</div>
          </div>
          <span class="slide-caption">第 N+1 页：缴费排期</span>
        </div>

        <div class="slide-card">
          <div class="slide-screen">
            <div class="slide-disclaimer-mock">法律声明与数据溯源依据</div>
          </div>
          <span class="slide-caption">第 N+2 页：法律免责声明</span>
        </div>
      </div>
    </div>

    <!-- History Reports List -->
    <div class="history-section glass">
      <div class="history-header">
        <h2 class="section-title">已生成的报告历史</h2>
        <button class="btn-text" @click="fetchReports">刷新列表</button>
      </div>

      <div v-if="loadingHistory" class="loading-state">
        <Loader2 class="spin icon-md" />
        <span>正在加载报告历史...</span>
      </div>

      <div v-else-if="reportsList.length === 0" class="empty-state">
        暂无已生成的 PPT 报告，点击上方按钮即可一键导出。
      </div>

      <div v-else class="reports-table-wrap">
        <table class="reports-table">
          <thead>
            <tr>
              <th>报告编号</th>
              <th>生成时间</th>
              <th>总保费支出</th>
              <th>核验状态</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in reportsList" :key="r.id">
              <td class="font-mono">{{ r.id }}</td>
              <td>{{ formatDate(r.created_at) }}</td>
              <td>¥{{ (r.snapshot?.total_premium_yuan ?? 0).toLocaleString() }}</td>
              <td>
                <span class="badge" :class="r.verified ? 'badge-success' : 'badge-warning'">
                  {{ r.verified ? '核验通过 (100%)' : '偏差警告' }}
                </span>
              </td>
              <td>
                <a :href="`/api/reports/ppt/${r.id}/download`" download class="table-link">
                  <Download class="icon-xs" />
                  <span>下载</span>
                </a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  Presentation,
  FileDown,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Download,
} from 'lucide-vue-next'

interface ReportSnapshot {
  total_policies: number
  total_members: number
  total_premium_yuan: number
  total_death_yuan: number
  total_ci_yuan: number
  max_medical_yuan: number
}

interface ReportItem {
  id: string
  created_at: string
  verified: boolean
  total_checked: number
  mismatches: any[]
  snapshot?: ReportSnapshot
}

const customSummary = ref('')
const isGenerating = ref(false)
const loadingHistory = ref(false)
const latestReport = ref<ReportItem | null>(null)
const reportsList = ref<ReportItem[]>([])

async function fetchReports() {
  loadingHistory.value = true
  try {
    const res = await fetch('/api/reports/ppt')
    if (res.ok) {
      reportsList.value = await res.json()
      if (!latestReport.value && reportsList.value.length > 0) {
        latestReport.value = reportsList.value[0]
      }
    }
  } catch (err) {
    console.error('Failed to fetch reports list', err)
  } finally {
    loadingHistory.value = false
  }
}

async function generateReport() {
  if (isGenerating.value) return
  isGenerating.value = true
  try {
    const res = await fetch('/api/reports/ppt', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ custom_summary: customSummary.value || undefined }),
    })
    if (res.ok) {
      const data = await res.json()
      latestReport.value = data
      await fetchReports()
    } else {
      alert('生成报告失败，请检查保单数据或服务端日志')
    }
  } catch (err) {
    console.error('Error generating report:', err)
    alert('网络请求异常，请稍后重试')
  } finally {
    isGenerating.value = false
  }
}

function formatDate(isoStr: string): string {
  if (!isoStr) return '-'
  try {
    const d = new Date(isoStr)
    if (!isNaN(d.getTime())) {
      return d.toLocaleString('zh-CN', { hour12: false })
    }
    return isoStr
  } catch {
    return isoStr
  }
}

onMounted(() => {
  fetchReports()
})
</script>

<style scoped>
.reports-page {
  max-width: 1100px;
  margin: 0 auto;
  padding: var(--sp-6) var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-6);
}

.page-header {
  margin-bottom: var(--sp-2);
}

.page-title {
  font-size: var(--fs-28);
  font-weight: 700;
  color: var(--text);
  margin-bottom: var(--sp-2);
}

.page-subtitle {
  font-size: var(--fs-14);
  color: var(--text-muted);
  line-height: 1.6;
}

.generator-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  padding: var(--sp-6);
}

.card-header {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-4);
}

.header-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--r-control);
  background: rgba(42, 143, 130, 0.1);
  color: var(--ok);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.section-title {
  font-size: var(--fs-19);
  font-weight: 600;
  color: var(--text);
}

.section-desc {
  font-size: var(--fs-14);
  color: var(--text-muted);
  margin-top: var(--sp-1);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.form-label {
  font-size: var(--fs-14);
  font-weight: 500;
  color: var(--text);
}

.text-input {
  width: 100%;
  padding: var(--sp-3);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  background: var(--bg);
  color: var(--text);
  font-family: inherit;
  font-size: var(--fs-14);
  resize: vertical;
}

.text-input:focus {
  border-color: var(--ok);
}

.text-input:focus-visible {
  outline: 2px solid var(--ok);
  outline-offset: 2px;
}

.actions-row {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  background: var(--ok);
  color: #ffffff;
  border: none;
  border-radius: var(--r-control);
  padding: var(--sp-3) var(--sp-6);
  font-size: var(--fs-14);
  font-weight: 600;
  cursor: pointer;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.verification-alert {
  display: flex;
  gap: var(--sp-4);
  padding: var(--sp-5);
  border-radius: var(--r-control);
  border: 1px solid;
}

.verification-alert.success {
  background: rgba(42, 143, 130, 0.06);
  border-color: rgba(42, 143, 130, 0.3);
}

.verification-alert.warning {
  background: rgba(234, 88, 12, 0.06);
  border-color: rgba(234, 88, 12, 0.3);
}

.alert-icon-col {
  flex-shrink: 0;
  padding-top: var(--sp-1);
}

.status-success {
  color: var(--ok);
}

.status-warning {
  color: var(--pending);
}

.alert-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.alert-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.alert-title {
  font-size: var(--fs-16);
  font-weight: 600;
  color: var(--text);
}

.badge {
  font-size: var(--fs-12);
  padding: var(--sp-1) var(--sp-2);
  border-radius: var(--r-control);
  font-weight: 600;
}

.badge-success {
  background: rgba(42, 143, 130, 0.15);
  color: var(--ok);
}

.badge-warning {
  background: color-mix(in oklch, var(--pending) 15%, transparent);
  color: var(--pending);
}

.alert-desc {
  font-size: var(--fs-14);
  color: var(--text-muted);
}

.stats-snapshot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: var(--sp-3);
  margin-top: var(--sp-2);
}

.snap-item {
  background: var(--glass-fill-strong);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  padding: var(--sp-2) var(--sp-3);
  display: flex;
  flex-direction: column;
}

.snap-label {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.snap-val {
  font-size: var(--fs-14);
  font-weight: 700;
  color: var(--text);
  margin-top: var(--sp-1);
  font-variant-numeric: tabular-nums;
}

.alert-actions {
  margin-top: var(--sp-2);
}

.btn-download {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  background: var(--ok);
  color: #ffffff;
  padding: var(--sp-2) var(--sp-4);
  border-radius: var(--r-control);
  text-decoration: none;
  font-size: var(--fs-14);
  font-weight: 500;
}

.preview-section {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-6);
}

.slide-deck-preview {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--sp-4);
}

.slide-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.slide-screen {
  aspect-ratio: 16 / 9;
  background: #f8faf9;
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  padding: var(--sp-2);
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  position: relative;
  overflow: hidden;
}

.slide-decor {
  position: absolute;
  left: 8px;
  top: 8px;
  bottom: 8px;
  width: 3px;
  background: var(--ok);
  border-radius: 2px;
}

.slide-title-mock {
  font-size: var(--fs-12);
  font-weight: 700;
  color: var(--text);
}

.slide-sub-mock {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 2px;
}

.mock-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 4px;
  width: 80%;
  margin-bottom: 4px;
}

.mock-cell {
  font-size: 9px;
  background: rgba(42, 143, 130, 0.1);
  color: var(--ok);
  padding: 2px 4px;
  border-radius: 2px;
  text-align: center;
}

.slide-table-mock {
  width: 85%;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.table-row {
  height: 6px;
  background: #e2e8f0;
  border-radius: 1px;
}

.table-row.header {
  background: var(--ok);
}

.slide-caption {
  font-size: var(--fs-12);
  color: var(--text-muted);
  text-align: center;
}

.history-section {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-6);
}

.history-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.btn-text {
  background: none;
  border: none;
  color: var(--ok);
  font-size: var(--fs-14);
  cursor: pointer;
}

.reports-table-wrap {
  overflow-x: auto;
}

.reports-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-14);
}

.reports-table th,
.reports-table td {
  padding: var(--sp-3);
  text-align: left;
  border-bottom: 1px solid var(--glass-stroke);
}

.reports-table th {
  color: var(--text-muted);
  font-weight: 500;
}

.table-link {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  color: var(--ok);
  text-decoration: none;
  font-weight: 500;
}

.empty-state, .loading-state {
  padding: var(--sp-8);
  text-align: center;
  color: var(--text-muted);
  font-size: var(--fs-14);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
}

.icon-xs { width: 14px; height: 14px; }
.icon-sm { width: 16px; height: 16px; }
.icon-md { width: 20px; height: 20px; }
.icon-lg { width: 24px; height: 24px; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }
</style>
