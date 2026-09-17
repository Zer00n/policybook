<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Eye,
  ShieldCheck,
  RefreshCw,
  FileCheck,
  ChevronDown,
  ChevronUp,
  Terminal,
  Loader2,
} from 'lucide-vue-next'
import PiiCompareViewer from '@/components/doc-viewer/PiiCompareViewer.vue'

interface LogEntry {
  timestamp: string
  level: string
  message: string
}

interface ActiveJob {
  job_id: string
  document_id: string
  filename: string
  step: string
  progress: number
  status: string
  error?: string
  logs: LogEntry[]
  showLogs: boolean
}

interface DocumentItem {
  id: string
  original_name: string
  page_count: number
  mime: string
  created_at: string
}

const router = useRouter()
const isDragging = ref(false)
const uploading = ref(false)
const activeJobs = ref<ActiveJob[]>([])
const documents = ref<DocumentItem[]>([])
const selectedDocId = ref<string | null>(null)
const showCompareModal = ref(false)

const eventSources: EventSource[] = []

// 5 大主阶段定义
const PIPELINE_STAGES = [
  { id: 1, name: '解析渲染', key: 'render', desc: 'PDF 解析与 144 DPI 渲染' },
  { id: 2, name: 'OCR与脱敏', key: 'pii', desc: 'RapidOCR 与隐私数据打码' },
  { id: 3, name: '页面分类', key: 'classify', desc: '方舟大模型智能页面识别' },
  { id: 4, name: '深度抽取', key: 'extract', desc: '保单基本信息与保障责任抽取' },
  { id: 5, name: '校验就绪', key: 'review', desc: '原文精确子串定位与冲突核验' },
]

function getStageStatus(job: ActiveJob, stageIndex: number): 'completed' | 'current' | 'pending' | 'failed' {
  if (job.status === 'failed') {
    const currentIdx = getStageIndexForStep(job.step)
    if (stageIndex === currentIdx) return 'failed'
    if (stageIndex < currentIdx) return 'completed'
    return 'pending'
  }

  if (job.status === 'succeeded' || job.step === 'review') {
    return 'completed'
  }

  const currentIdx = getStageIndexForStep(job.step)
  if (stageIndex < currentIdx) return 'completed'
  if (stageIndex === currentIdx) return 'current'
  return 'pending'
}

function getStageIndexForStep(step: string): number {
  switch (step) {
    case 'init':
    case 'hash_check':
    case 'render':
      return 0
    case 'ocr':
    case 'pii':
      return 1
    case 'classify':
      return 2
    case 'extract_policy':
    case 'extract_coverages':
      return 3
    case 'verify':
    case 'review':
      return 4
    default:
      return 0
  }
}

function getStepLabel(step: string): string {
  const stepMap: Record<string, string> = {
    init: '初始化建档任务...',
    hash_check: '校验文件哈希 (SHA-256)...',
    render: '144 DPI 高清渲染与文字坐标提取...',
    ocr: '本地 RapidOCR 引擎识别扫描件...',
    pii: '本地脱敏遮盖与打码隔离...',
    classify: '方舟大模型执行合同页面智能分类...',
    extract_policy: '方舟大模型深度抽取保单核心信息...',
    extract_coverages: '方舟大模型结构化抽取责任与免责...',
    verify: '精确子串定位与数值一致性核验...',
    review: '核对草稿已准备就绪',
  }
  return stepMap[step] || step
}

async function fetchDocuments() {
  try {
    const res = await fetch('/api/documents')
    if (res.ok) {
      documents.value = await res.json()
    }
  } catch (err) {
    console.error('加载文档列表失败:', err)
  }
}

async function fetchActiveJobs() {
  try {
    const res = await fetch('/api/jobs/active')
    if (res.ok) {
      const data = await res.json()
      for (const item of data.jobs) {
        const existing = activeJobs.value.find((j) => j.job_id === item.job_id)
        if (!existing) {
          const jobRecord: ActiveJob = {
            job_id: item.job_id,
            document_id: item.document_id || '',
            filename: item.filename,
            step: item.step,
            progress: item.progress,
            status: item.status,
            error: item.error,
            logs: item.logs || [],
            showLogs: item.status === 'running' || item.status === 'queued',
          }
          activeJobs.value.push(jobRecord)
          if (item.status === 'queued' || item.status === 'running') {
            listenToJob(jobRecord)
          }
        }
      }
    }
  } catch (err) {
    console.error('获取活跃任务失败:', err)
  }
}

function handleDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function handleDragLeave(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
}

function handleDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  if (e.dataTransfer?.files?.length) {
    uploadFiles(e.dataTransfer.files)
  }
}

function onFileInput(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files?.length) {
    uploadFiles(target.files)
  }
}

async function uploadFiles(fileList: FileList) {
  if (!fileList.length) return
  uploading.value = true

  const formData = new FormData()
  for (let i = 0; i < fileList.length; i++) {
    formData.append('files', fileList[i])
  }

  try {
    const res = await fetch('/api/imports', {
      method: 'POST',
      body: formData,
    })

    if (res.ok) {
      const data = await res.json()
      for (const item of data.jobs) {
        const jobRecord: ActiveJob = {
          job_id: item.job_id,
          document_id: item.document_id,
          filename: item.filename,
          step: 'init',
          progress: 0.05,
          status: 'running',
          logs: [],
          showLogs: true,
        }
        activeJobs.value.unshift(jobRecord)
        listenToJob(jobRecord)
      }
    }
  } catch (err) {
    console.error('上传失败:', err)
  } finally {
    uploading.value = false
  }
}

function listenToJob(job: ActiveJob) {
  const es = new EventSource(`/api/jobs/${job.job_id}/events`)
  eventSources.push(es)

  es.addEventListener('snapshot', (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data)
      job.step = data.step || job.step
      job.progress = data.progress ?? job.progress
      job.status = data.status || job.status
      if (data.error) job.error = data.error
      if (data.document_id) job.document_id = data.document_id
      if (data.filename) job.filename = data.filename
      if (Array.isArray(data.logs) && data.logs.length > 0) {
        job.logs = data.logs
      }
      if (data.status === 'succeeded' || data.status === 'failed') {
        es.close()
        fetchDocuments()
      }
    } catch (err) {
      console.error('解析 snapshot 失败:', err)
    }
  })

  es.addEventListener('step', (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data)
      job.step = data.step
      job.progress = data.progress
    } catch (err) {
      console.error('解析 step 失败:', err)
    }
  })

  es.addEventListener('log', (event: MessageEvent) => {
    try {
      const entry = JSON.parse(event.data)
      if (!job.logs) job.logs = []
      job.logs.push(entry)
      scrollLogsToBottom(job.job_id)
    } catch (err) {
      console.error('解析 log 失败:', err)
    }
  })

  es.addEventListener('done', () => {
    job.status = 'succeeded'
    job.progress = 1.0
    job.step = 'review'
    es.close()
    fetchDocuments()
  })

  es.addEventListener('error', (event: any) => {
    try {
      const data = JSON.parse(event.data)
      // 后端主动推送的结构化 error 事件是终止事件，关闭连接，不依赖浏览器默认重连
      job.status = 'failed'
      job.error = data.message || '处理异常中断'
      es.close()
    } catch {
      // event.data 无法解析：属于连接层面的网络错误（而非后端下发的终止事件），
      // 交由浏览器 EventSource 的默认重连机制处理
    }
  })
}

function scrollLogsToBottom(jobId: string) {
  nextTick(() => {
    const el = document.getElementById(`logs-console-${jobId}`)
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  })
}

function toggleLogs(job: ActiveJob) {
  job.showLogs = !job.showLogs
  if (job.showLogs) {
    scrollLogsToBottom(job.job_id)
  }
}

function openCompare(docId: string) {
  selectedDocId.value = docId
  showCompareModal.value = true
}

function goToReview(jobId: string) {
  router.push(`/import/${jobId}`)
}

onMounted(() => {
  fetchActiveJobs()
  fetchDocuments()
})

onUnmounted(() => {
  for (const es of eventSources) {
    es.close()
  }
})
</script>

<template>
  <div class="import-page">
    <header class="page-header">
      <h1 class="page-title">保单上传与脱敏建档</h1>
      <p class="page-subtitle">
        支持 PDF（原生或扫描件）、JPG/PNG/HEIC 照片，单文件 ≤ 50MB。在家庭 NAS 本地完成页面渲染、OCR 与严格脱敏后调用方舟模型深度抽取。
      </p>
    </header>

    <!-- 拖拽上传区 -->
    <div
      class="glass dropzone"
      :class="{ dragging: isDragging }"
      @dragover="handleDragOver"
      @dragleave="handleDragLeave"
      @drop="handleDrop"
    >
      <div class="dropzone-inner">
        <UploadCloud :size="48" class="dropzone-icon" />
        <h3 class="dropzone-title">拖拽保单文件到此处，或点击选择</h3>
        <p class="dropzone-hint">
          支持 PDF、JPG、PNG、HEIC 格式 · 原始保单及身份证信息绝对不出家门
        </p>
        <label class="btn-primary file-label">
          <input
            type="file"
            multiple
            accept=".pdf,.png,.jpg,.jpeg,.heic"
            class="hidden-file-input"
            @change="onFileInput"
          />
          选择本地文件
        </label>
      </div>
    </div>

    <!-- 处理中的流水线任务卡片 -->
    <section v-if="activeJobs.length > 0" class="glass panel">
      <div class="panel-header">
        <h2 class="panel-title">处理流水线与实时日志</h2>
        <span class="badge badge--pending">{{ activeJobs.length }} 个任务</span>
      </div>

      <div class="job-list">
        <div
          v-for="job in activeJobs"
          :key="job.job_id"
          class="job-card"
        >
          <!-- 任务头部信息 -->
          <div class="job-header">
            <div class="job-title-group">
              <FileText :size="20" class="text-ok" />
              <div>
                <span class="job-name">{{ job.filename }}</span>
                <span class="job-id-hint">ID: {{ job.job_id.slice(0, 10) }}...</span>
              </div>
            </div>

            <div class="job-status-badges">
              <span v-if="job.status === 'succeeded'" class="badge badge--ok">
                <CheckCircle2 :size="13" /> 处理完毕
              </span>
              <span v-else-if="job.status === 'failed'" class="badge badge--risk">
                <AlertCircle :size="13" /> 失败: {{ job.error || '执行异常' }}
              </span>
              <span v-else class="badge badge--pending">
                <Loader2 :size="13" class="animate-spin" /> {{ getStepLabel(job.step) }}
              </span>
            </div>
          </div>

          <!-- 5 大阶段可视流水线 Stepper -->
          <div class="pipeline-stepper">
            <div
              v-for="(stage, idx) in PIPELINE_STAGES"
              :key="stage.id"
              class="stepper-item"
              :class="`step-${getStageStatus(job, idx)}`"
            >
              <div class="step-indicator">
                <CheckCircle2 v-if="getStageStatus(job, idx) === 'completed'" :size="16" />
                <Loader2 v-else-if="getStageStatus(job, idx) === 'current'" :size="16" class="animate-spin" />
                <AlertCircle v-else-if="getStageStatus(job, idx) === 'failed'" :size="16" />
                <span v-else class="step-num">{{ stage.id }}</span>
              </div>
              <div class="step-content">
                <div class="step-name">{{ stage.name }}</div>
                <div class="step-desc">{{ stage.desc }}</div>
              </div>
              <div v-if="idx < PIPELINE_STAGES.length - 1" class="step-divider"></div>
            </div>
          </div>

          <!-- 进度条 -->
          <div class="progress-bar-wrap">
            <div
              class="progress-bar-fill"
              :style="{ width: `${Math.round(job.progress * 100)}%` }"
            ></div>
          </div>

          <!-- 操作按钮栏 -->
          <div class="job-actions-row">
            <div class="action-left">
              <button
                class="btn-text-toggle"
                @click="toggleLogs(job)"
              >
                <Terminal :size="14" />
                <span>实时日志 ({{ job.logs?.length || 0 }} 条)</span>
                <ChevronUp v-if="job.showLogs" :size="14" />
                <ChevronDown v-else :size="14" />
              </button>
            </div>

            <div class="action-right">
              <button
                v-if="job.document_id"
                class="btn-secondary btn-small"
                @click="openCompare(job.document_id)"
              >
                <Eye :size="14" />
                查看脱敏对比
              </button>
              <button
                v-if="job.status === 'succeeded'"
                class="btn-primary btn-small btn-highlight"
                @click="goToReview(job.job_id)"
              >
                <FileCheck :size="15" />
                前往核对结果
              </button>
            </div>
          </div>

          <!-- 展开式实时日志抽屉/控制台 -->
          <div
            v-if="job.showLogs"
            :id="`logs-console-${job.job_id}`"
            class="logs-console"
          >
            <div v-if="job.logs && job.logs.length > 0" class="logs-stream">
              <div
                v-for="(log, lIdx) in job.logs"
                :key="lIdx"
                class="log-line"
                :class="`log-${log.level}`"
              >
                <span class="log-time">[{{ log.timestamp }}]</span>
                <span class="log-badge" :class="`badge-${log.level}`">{{ log.level.toUpperCase() }}</span>
                <span class="log-msg">{{ log.message }}</span>
              </div>
            </div>
            <div v-else class="log-empty">
              <Loader2 :size="14" class="animate-spin text-muted" />
              <span>正在建立 SSE 实时推送通道...</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- 已入库文档列表 -->
    <section class="glass panel">
      <div class="panel-header">
        <h2 class="panel-title">已上传文档 ({{ documents.length }})</h2>
        <button class="btn-secondary btn-small" @click="fetchDocuments">
          <RefreshCw :size="14" />
          刷新列表
        </button>
      </div>

      <div v-if="documents.length > 0" class="docs-table-wrap">
        <table class="docs-table">
          <thead>
            <tr>
              <th>文件名称</th>
              <th>页数</th>
              <th>格式</th>
              <th>上传时间</th>
              <th style="text-align: right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="d in documents" :key="d.id">
              <td class="doc-name-cell">
                <FileText :size="16" class="text-ok" />
                <span>{{ d.original_name }}</span>
              </td>
              <td>{{ d.page_count }} 页</td>
              <td>{{ d.mime.split('/')[1]?.toUpperCase() || 'PDF' }}</td>
              <td class="tabular-nums">{{ new Date(d.created_at).toLocaleString() }}</td>
              <td style="text-align: right">
                <button
                  class="btn-secondary btn-small"
                  @click="openCompare(d.id)"
                >
                  <Eye :size="14" />
                  脱敏对比
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else class="empty-docs">
        <ShieldCheck :size="36" class="text-muted" />
        <p>暂无已上传的保单文件，拖拽文件即可开始建档。</p>
      </div>
    </section>

    <!-- 脱敏前后对比弹窗 -->
    <div
      v-if="showCompareModal && selectedDocId"
      class="modal-backdrop"
      @click.self="showCompareModal = false"
    >
      <PiiCompareViewer
        :document-id="selectedDocId"
        @close="showCompareModal = false"
      />
    </div>
  </div>
</template>

<style scoped>
.text-muted { color: var(--text-muted); }
.animate-spin { animation: import-page-spin 1s linear infinite; }
@keyframes import-page-spin {
  to { transform: rotate(360deg); }
}

.import-page {
  max-width: 1080px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}

.page-title {
  font-size: var(--fs-28);
  font-weight: 700;
}

.page-subtitle {
  font-size: var(--fs-14);
  color: var(--text-muted);
  margin-top: 2px;
}

/* 拖拽上传区 */
.dropzone {
  border: 2px dashed var(--glass-stroke);
  padding: var(--sp-7);
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  transition: var(--trans-base);
  border-radius: var(--r-panel);
}

.dropzone.dragging {
  border-color: var(--ok);
  background: color-mix(in oklch, var(--ok) 10%, transparent);
}

.dropzone-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
}

.dropzone-icon {
  color: var(--ok);
  margin-bottom: var(--sp-1);
}

.dropzone-title {
  font-size: var(--fs-19);
  font-weight: 600;
}

.dropzone-hint {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-bottom: var(--sp-2);
}

.hidden-file-input {
  display: none;
}

.file-label {
  cursor: pointer;
}

/* 面板通配 */
.panel {
  padding: var(--sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  border-radius: var(--r-panel);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  font-size: var(--fs-19);
  font-weight: 600;
}

/* 任务列表与卡片 */
.job-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.job-card {
  padding: var(--sp-4);
  border-radius: var(--r-control);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  transition: all 0.2s ease;
}

.job-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.job-title-group {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.job-name {
  font-weight: 600;
  font-size: var(--fs-14);
  color: var(--text);
}

.job-id-hint {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-left: 8px;
  font-family: var(--font-mono, monospace);
}

.job-status-badges {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 5 阶段可视流水线 Stepper */
.pipeline-stepper {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--glass-fill-strong);
  border-radius: var(--r-control);
  padding: var(--sp-3) var(--sp-4);
  margin: var(--sp-1) 0;
  overflow-x: auto;
}

.stepper-item {
  display: flex;
  align-items: center;
  gap: 8px;
  position: relative;
  flex: 1;
}

.step-indicator {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--fs-12);
  font-weight: 600;
  flex-shrink: 0;
  transition: all 0.2s ease;
}

.step-completed .step-indicator {
  background: color-mix(in oklch, var(--ok) 20%, transparent);
  color: var(--ok);
  border: 1.5px solid var(--ok);
}

.step-current .step-indicator {
  background: color-mix(in oklch, var(--pending) 20%, transparent);
  color: var(--pending);
  border: 1.5px solid var(--pending);
}

.step-failed .step-indicator {
  background: color-mix(in oklch, var(--risk) 20%, transparent);
  color: var(--risk);
  border: 1.5px solid var(--risk);
}

.step-pending .step-indicator {
  background: color-mix(in oklch, var(--text-muted) 10%, transparent);
  color: var(--text-muted);
  border: 1px solid var(--glass-stroke);
}

.step-content {
  display: flex;
  flex-direction: column;
}

.step-name {
  font-size: var(--fs-12);
  font-weight: 600;
  color: var(--text);
}

.step-completed .step-name {
  color: var(--ok);
}

.step-current .step-name {
  color: var(--pending);
}

.step-desc {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.step-divider {
  flex: 1;
  height: 2px;
  background: var(--glass-stroke);
  margin: 0 12px;
}

.step-completed + .stepper-item .step-divider {
  background: var(--ok);
}

/* 进度条 */
.progress-bar-wrap {
  width: 100%;
  height: 6px;
  background: color-mix(in oklch, var(--text) 10%, transparent);
  border-radius: var(--r-pill);
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--ok);
  border-radius: var(--r-pill);
  transition: width 300ms ease;
}

/* 操作行 */
.job-actions-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.btn-text-toggle {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-12);
  padding: 4px 8px;
  border-radius: var(--r-control);
  transition: color 0.15s ease;
}

.btn-text-toggle:hover {
  color: var(--text);
}

.action-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.btn-highlight {
  font-weight: 600;
  padding: 6px 14px;
}

/* 实时日志控制台 */
.logs-console {
  background: color-mix(in oklch, var(--bg) 80%, black);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  padding: 10px 14px;
  max-height: 180px;
  overflow-y: auto;
  font-family: var(--font-mono, 'Consolas', monospace);
  font-size: 12px;
  line-height: 1.6;
}

.logs-stream {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.log-time {
  color: var(--text-muted);
  flex-shrink: 0;
}

.log-badge {
  font-size: 10px;
  padding: 1px 4px;
  border-radius: 3px;
  flex-shrink: 0;
  font-weight: 600;
}

.badge-info {
  background: color-mix(in oklch, var(--ok) 20%, transparent);
  color: var(--ok);
}

.badge-warn {
  background: color-mix(in oklch, var(--pending) 20%, transparent);
  color: var(--pending);
}

.badge-success {
  background: color-mix(in oklch, var(--ok) 30%, transparent);
  color: var(--ok);
}

.badge-error {
  background: color-mix(in oklch, var(--risk) 20%, transparent);
  color: var(--risk);
}

.log-msg {
  color: var(--text);
  word-break: break-all;
}

.log-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-muted);
  padding: 8px 0;
}

/* 文档列表表格 */
.docs-table-wrap {
  overflow-x: auto;
}

.docs-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-14);
}

.docs-table th,
.docs-table td {
  padding: var(--sp-3) var(--sp-3);
  text-align: left;
  border-bottom: 1px solid var(--glass-stroke);
}

.docs-table th {
  font-size: var(--fs-12);
  color: var(--text-muted);
  font-weight: 600;
}

.doc-name-cell {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-weight: 500;
}

.btn-small {
  padding: 5px 12px;
  font-size: var(--fs-12);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.empty-docs {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
  padding: var(--sp-6);
  color: var(--text-muted);
  font-size: var(--fs-14);
}

/* 弹窗遮罩 */
.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: var(--sp-4);
}
</style>
