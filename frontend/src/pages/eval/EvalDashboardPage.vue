<template>
  <div class="eval-page">
    <!-- Header -->
    <header class="page-header">
      <div>
        <h1 class="page-title">评测看板 (Eval Dashboard)</h1>
        <p class="page-subtitle">
          标准化多模型任务集评测体系：严格复现、判定脚本全自动执行、支持模型对比与调用时间线分析。
        </p>
      </div>
      <div class="header-actions">
        <button class="btn-refresh" :disabled="loading" @click="fetchData">
          <RotateCcw class="icon-sm" :class="{ spin: loading }" />
          <span>刷新数据</span>
        </button>
      </div>
    </header>

    <!-- Top Comparison Metrics Cards -->
    <div v-if="comparisonRows.length > 0" class="metrics-grid">
      <div v-for="row in comparisonRows" :key="row.run_id" class="metric-card glass-subtle">
        <div class="card-tag-row">
          <span class="model-badge" :class="row.model_alias === 'evolving' ? 'badge-primary' : 'badge-secondary'">
            {{ row.model_alias === 'evolving' ? '主测模型 (Evolving)' : '基线模型 (' + (row.model_alias || 'Baseline') + ')' }}
          </span>
          <span class="commit-tag font-mono">commit: {{ row.git_commit }}</span>
        </div>

        <h3 class="model-name font-mono">{{ row.model_id }}</h3>

        <div class="kpi-row">
          <div class="kpi-item">
            <span class="kpi-val highlight">{{ row.pass_rate }}</span>
            <span class="kpi-lbl">综合通过率</span>
          </div>
          <div class="kpi-item">
            <span class="kpi-val">{{ row.quote_accuracy }}</span>
            <span class="kpi-lbl">引用准确率</span>
          </div>
          <div class="kpi-item">
            <span class="kpi-val">{{ row.avg_tokens }}</span>
            <span class="kpi-lbl">平均 Tokens</span>
          </div>
          <div class="kpi-item">
            <span class="kpi-val">{{ (Number(row.avg_latency_ms) / 1000).toFixed(2) }}s</span>
            <span class="kpi-lbl">平均耗时</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Summary Records Table -->
    <div class="glass main-panel">
      <div class="panel-header">
        <div class="title-wrap">
          <Layers class="icon-md text-primary" />
          <h2 class="panel-title">评测批次汇总 (summary.csv)</h2>
        </div>
        <span class="summary-count">共 {{ summaryRows.length }} 次标准化评测记录</span>
      </div>

      <div v-if="loading && summaryRows.length === 0" class="loading-state">
        <Loader2 class="spin icon-md" />
        <span>正在加载测评数据...</span>
      </div>

      <div v-else-if="summaryRows.length === 0" class="empty-state">
        暂无评测记录。运行 <code>python -m app.eval run</code> 即可生成标准化测试数据。
      </div>

      <div v-else class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>批次 ID</th>
              <th>任务集</th>
              <th>模型</th>
              <th>种子 (Seed)</th>
              <th>Git 提交</th>
              <th>通过率</th>
              <th>引用准确率</th>
              <th>平均耗时</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in summaryRows" :key="r.run_id">
              <td class="font-mono run-id-cell">{{ r.run_id }}</td>
              <td><span class="suite-tag">{{ r.suite }}</span></td>
              <td>{{ r.model_alias }}</td>
              <td class="font-mono">{{ r.seed }}</td>
              <td class="font-mono">{{ r.git_commit }}</td>
              <td>
                <span class="badge" :class="Number(r.passed_tasks) === Number(r.total_tasks) ? 'badge-success' : 'badge-warning'">
                  {{ r.pass_rate }} ({{ r.passed_tasks }}/{{ r.total_tasks }})
                </span>
              </td>
              <td>{{ r.quote_accuracy }}</td>
              <td>{{ r.avg_latency_ms }} ms</td>
              <td>
                <button class="btn-detail" @click="openRunDetail(r.run_id)">
                  <span>查看明细</span>
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Task Breakdown Drawer / Modal -->
    <div v-if="selectedRun" class="modal-backdrop" @click.self="selectedRun = null">
      <div class="modal-card glass">
        <div class="modal-header">
          <div>
            <h3 class="modal-title">评测批次调用明细：{{ selectedRun.run_id }}</h3>
            <p class="modal-sub">模型：{{ selectedRun.meta?.model_id }} | 种子：{{ selectedRun.meta?.seed }}</p>
          </div>
          <button class="btn-close" @click="selectedRun = null">✕</button>
        </div>

        <div class="task-list">
          <div
            v-for="(t, idx) in selectedRun.results"
            :key="t.task_id"
            class="task-card"
            :class="getTaskJudgment(t.task_id)?.passed ? 'passed' : 'failed'"
          >
            <div class="task-head">
              <div class="task-tag-row">
                <span class="task-num font-mono">#{{ idx + 1 }} {{ t.task_id }}</span>
                <span
                  class="badge"
                  :class="getTaskJudgment(t.task_id)?.passed ? 'badge-success' : 'badge-danger'"
                >
                  {{ getTaskJudgment(t.task_id)?.passed ? '通过' : '未通过' }}
                </span>
              </div>
              <span class="task-latency font-mono">{{ t.latency_ms }}ms | {{ t.total_tokens }} tokens</span>
            </div>

            <div class="task-q">
              <strong>问题：</strong>{{ t.question }}
            </div>

            <div class="verdict-compare-row">
              <div>
                <span class="lbl">模型结论：</span>
                <span class="val font-mono">{{ t.verdict }}</span>
              </div>
              <div>
                <span class="lbl">标准答案 (Gold)：</span>
                <span class="val font-mono">{{ t.gold?.verdict }}</span>
              </div>
            </div>

            <div v-if="t.explanation" class="task-exp">
              <strong>解释：</strong>{{ t.explanation }}
            </div>

            <div v-if="t.verified_quotes && t.verified_quotes.length > 0" class="task-quotes">
              <span class="lbl">引用原文与校验状态：</span>
              <div class="quote-tags">
                <span
                  v-for="(q, qIdx) in t.verified_quotes"
                  :key="qIdx"
                  class="quote-tag"
                  :class="q.status === 'verified' ? 'verified' : 'not-found'"
                >
                  第 {{ q.page }} 页: "{{ q.quote }}" ({{ q.status === 'verified' ? '精准匹配' : '未找到' }})
                </span>
              </div>
            </div>

            <div v-if="getTaskJudgment(t.task_id)?.failure_reasons?.length" class="failure-reasons">
              <AlertCircle class="icon-xs text-danger" />
              <span>判定不通过原因：{{ getTaskJudgment(t.task_id)?.failure_reasons?.join('；') }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { RotateCcw, Layers, Loader2, AlertCircle } from 'lucide-vue-next'

interface SummaryRow {
  run_id: string
  suite: string
  model_alias: string
  model_id: string
  seed: string
  git_commit: string
  prompt_version: string
  total_tasks: string
  passed_tasks: string
  pass_rate: string
  verdict_accuracy: string
  quote_accuracy: string
  avg_tokens: string
  avg_latency_ms: string
  created_at: string
}

const loading = ref(false)
const summaryRows = ref<SummaryRow[]>([])
const selectedRun = ref<any | null>(null)

const comparisonRows = computed(() => {
  // Show latest run for each distinct model_alias
  const map = new Map<string, SummaryRow>()
  for (const r of summaryRows.value) {
    if (!map.has(r.model_alias)) {
      map.set(r.model_alias, r)
    }
  }
  return Array.from(map.values())
})

async function fetchData() {
  loading.value = true
  try {
    const res = await fetch('/api/eval/summary')
    if (res.ok) {
      const data = await res.json()
      summaryRows.value = data.summary || []
    }
  } catch (err) {
    console.error('Failed to fetch eval summary', err)
  } finally {
    loading.value = false
  }
}

async function openRunDetail(runId: string) {
  try {
    const res = await fetch(`/api/eval/runs/${runId}`)
    if (res.ok) {
      selectedRun.value = await res.json()
    }
  } catch (err) {
    console.error('Failed to fetch run detail', err)
  }
}

function getTaskJudgment(taskId: string) {
  if (!selectedRun.value || !selectedRun.value.judgments) return null
  const jList = selectedRun.value.judgments.judgments || []
  return jList.find((j: any) => j.task_id === taskId)
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.eval-page {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--sp-6) var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-6);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.btn-refresh {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-4);
  border: 1px solid var(--glass-stroke);
  background: var(--glass-fill-strong);
  color: var(--text);
  border-radius: var(--r-control);
  font-size: var(--fs-14);
  cursor: pointer;
}


.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: var(--sp-4);
}

.metric-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  padding: var(--sp-6);
}

.card-tag-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.model-badge {
  font-size: var(--fs-12);
  padding: 2px 8px;
  border-radius: var(--r-control);
  font-weight: 600;
}

.badge-primary {
  background: rgba(42, 143, 130, 0.15);
  color: var(--ok);
}

.badge-secondary {
  background: var(--glass-fill-strong);
  color: var(--text-muted);
}

.commit-tag {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.model-name {
  font-size: var(--fs-14);
  font-weight: 600;
  color: var(--text);
  word-break: break-all;
}

.kpi-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--sp-2);
  margin-top: var(--sp-2);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--glass-stroke);
}

.kpi-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.kpi-val {
  font-size: var(--fs-19);
  font-weight: 700;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.kpi-val.highlight {
  color: var(--ok);
}

.kpi-lbl {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 2px;
}

.main-panel {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  padding: var(--sp-6);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title-wrap {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.panel-title {
  font-size: var(--fs-19);
  font-weight: 600;
  color: var(--text);
}

.summary-count {
  font-size: var(--fs-14);
  color: var(--text-muted);
}

.table-wrap {
  overflow-x: auto;
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-14);
}

.data-table th,
.data-table td {
  padding: var(--sp-3);
  text-align: left;
  border-bottom: 1px solid var(--glass-stroke);
}

.data-table th {
  color: var(--text-muted);
  font-weight: 500;
}

.run-id-cell {
  font-size: var(--fs-12);
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.suite-tag {
  background: rgba(100, 116, 139, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: var(--fs-12);
}

.badge {
  font-size: var(--fs-12);
  padding: 2px 8px;
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

.badge-danger {
  background: color-mix(in oklch, var(--danger) 15%, transparent);
  color: var(--danger);
}

.btn-detail {
  padding: 4px 10px;
  background: none;
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  color: var(--ok);
  font-size: var(--fs-12);
  cursor: pointer;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  padding: var(--sp-4);
}

.modal-card {
  width: 100%;
  max-width: 800px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--glass-fill-strong);
  padding: var(--sp-6);
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: var(--sp-3);
  border-bottom: 1px solid var(--glass-stroke);
}

.modal-title {
  font-size: var(--fs-16);
  font-weight: 600;
  color: var(--text);
}

.modal-sub {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-top: 2px;
}

.btn-close {
  background: none;
  border: none;
  font-size: var(--fs-19);
  cursor: pointer;
  color: var(--text-muted);
}

.task-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  overflow-y: auto;
  padding-top: var(--sp-3);
}

.task-card {
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  padding: var(--sp-3);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  background: var(--bg);
}

.task-card.passed {
  border-left: 4px solid var(--ok);
}

.task-card.failed {
  border-left: 4px solid var(--danger);
}

.task-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.task-tag-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.task-num {
  font-weight: 600;
  font-size: var(--fs-12);
}

.task-latency {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.task-q {
  font-size: var(--fs-14);
  color: var(--text);
}

.verdict-compare-row {
  display: flex;
  gap: var(--sp-6);
  font-size: var(--fs-12);
  background: rgba(0, 0, 0, 0.02);
  padding: var(--sp-2);
  border-radius: var(--r-control);
}

.verdict-compare-row .lbl {
  color: var(--text-muted);
}

.verdict-compare-row .val {
  font-weight: 600;
  color: var(--text);
}

.task-exp {
  font-size: var(--fs-12);
  color: var(--text-muted);
  line-height: 1.5;
}

.task-quotes {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-quotes .lbl {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.quote-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.quote-tag {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
}

.quote-tag.verified {
  background: rgba(42, 143, 130, 0.15);
  color: var(--ok);
}

.quote-tag.not-found {
  background: color-mix(in oklch, var(--danger) 15%, transparent);
  color: var(--danger);
}

.failure-reasons {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  font-size: var(--fs-12);
  color: var(--danger);
}

.text-primary { color: var(--ok); }
.text-danger { color: var(--danger); }
.font-mono { font-family: monospace; }
.icon-xs { width: 14px; height: 14px; }
.icon-sm { width: 16px; height: 16px; }
.icon-md { width: 20px; height: 20px; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { 100% { transform: rotate(360deg); } }

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
</style>
