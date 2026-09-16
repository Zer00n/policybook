<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Eye,
  ShieldCheck,
  RefreshCw,
} from 'lucide-vue-next'
import PiiCompareViewer from '@/components/doc-viewer/PiiCompareViewer.vue'

interface ActiveJob {
  job_id: string
  document_id: string
  filename: string
  step: string
  progress: number
  status: string
  error?: string
}

interface DocumentItem {
  id: string
  original_name: string
  page_count: number
  mime: string
  created_at: string
}

const isDragging = ref(false)
const uploading = ref(false)
const activeJobs = ref<ActiveJob[]>([])
const documents = ref<DocumentItem[]>([])
const selectedDocId = ref<string | null>(null)
const showCompareModal = ref(false)

const eventSources: EventSource[] = []

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
        }
        activeJobs.value.push(jobRecord)
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

  es.addEventListener('step', (event) => {
    const data = JSON.parse(event.data)
    job.step = data.step
    job.progress = data.progress
  })

  es.addEventListener('done', (event) => {
    job.status = 'succeeded'
    job.progress = 1.0
    es.close()
    fetchDocuments()
  })

  es.addEventListener('error', (event: any) => {
    try {
      const data = JSON.parse(event.data)
      job.status = 'failed'
      job.error = data.message
    } catch {
      // 连接关闭
    }
    es.close()
  })
}

function openCompare(docId: string) {
  selectedDocId.value = docId
  showCompareModal.value = true
}

function getStepLabel(step: string) {
  const stepMap: Record<string, string> = {
    init: '初始化任务...',
    hash_check: '校验文件哈希...',
    render: '144 DPI 页面渲染与字符提取...',
    ocr: '本地 OCR 扫描识别...',
    pii: '本地脱敏与图片打码...',
  }
  return stepMap[step] || step
}

onMounted(() => {
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
        支持 PDF（文本型或扫描型）、JPG/PNG/HEIC 照片，单文件 ≤ 50MB。在家庭 NAS 本地完成页面渲染、OCR 与严格脱敏。
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

    <!-- 正在处理的任务队列 -->
    <section v-if="activeJobs.length > 0" class="glass panel">
      <h2 class="panel-title">处理进度与流水线 (SSE 实时推送)</h2>
      <div class="job-list">
        <div
          v-for="job in activeJobs"
          :key="job.job_id"
          class="job-card"
        >
          <div class="job-info">
            <div class="job-header-row">
              <span class="job-name">{{ job.filename }}</span>
              <span v-if="job.status === 'succeeded'" class="badge badge--ok">
                <CheckCircle2 :size="12" /> 处理完毕
              </span>
              <span v-else-if="job.status === 'failed'" class="badge badge--risk">
                <AlertCircle :size="12" /> 失败: {{ job.error }}
              </span>
              <span v-else class="badge badge--pending">
                <span class="badge-dot"></span> {{ getStepLabel(job.step) }}
              </span>
            </div>

            <!-- 进度条 -->
            <div class="progress-bar-wrap">
              <div
                class="progress-bar-fill"
                :style="{ width: `${Math.round(job.progress * 100)}%` }"
              ></div>
            </div>
          </div>

          <button
            v-if="job.status === 'succeeded'"
            class="btn-primary"
            @click="openCompare(job.document_id)"
          >
            <Eye :size="14" />
            查看脱敏对比
          </button>
        </div>
      </div>
    </section>

    <!-- 已入库文档列表 -->
    <section class="glass panel">
      <div class="panel-header">
        <h2 class="panel-title">已上传文档 ({{ documents.length }})</h2>
        <button class="btn-secondary" @click="fetchDocuments">
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

/* 任务列表 */
.panel {
  padding: var(--sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
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

.job-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.job-card {
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--r-control);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  display: flex;
  align-items: center;
  gap: var(--sp-4);
}

.job-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.job-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.job-name {
  font-weight: 600;
  font-size: var(--fs-14);
}

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
  padding: 4px 10px;
  font-size: var(--fs-12);
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
