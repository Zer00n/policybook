<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Edit2,
  FileCheck,
  FileText,
  HelpCircle,
  Shield,
  Users,
  Eye,
  ArrowLeft,
} from 'lucide-vue-next'
import DocViewer, { HighlightTarget, PageMeta } from '@/components/doc-viewer/DocViewer.vue'

const route = useRoute()
const router = useRouter()
const jobId = computed(() => (route.params.jobId as string) || '')

const loading = ref(true)
const errorMsg = ref('')
const reviewData = ref<any>(null)
const activeTab = ref<'basic' | 'parties' | 'coverages' | 'exclusions'>('basic')
const activeHighlight = ref<HighlightTarget | null>(null)
const isMaskedMode = ref(true)

// 编辑模态框
const editModal = ref<{
  visible: boolean
  fieldKey: string
  label: string
  originalValue: string | null
  currentValue: string
  status: string
}>({
  visible: false,
  fieldKey: '',
  label: '',
  originalValue: null,
  currentValue: '',
  status: 'verified',
})

const submitting = ref(false)
const confirmSuccessMsg = ref('')

async function fetchReview() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`http://localhost:8000/api/imports/${jobId.value}/review`)
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.error?.message || '获取核对数据失败')
    }
    const body = await res.json()
    reviewData.value = body.review_data
  } catch (err: any) {
    errorMsg.value = err.message || '网络连接异常'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  if (jobId.value) {
    fetchReview()
  }
})

// 字段点击高亮定位 (FLIP)
function focusFieldEvidence(fieldItem: any, event?: MouseEvent) {
  if (!fieldItem || !fieldItem.quote) return
  activeHighlight.value = {
    page_no: fieldItem.page_no || 1,
    rects: fieldItem.rects || [],
    status: fieldItem.status,
    sourceEl: (event?.currentTarget as HTMLElement) || null,
  }
}

function openEditModal(fieldKey: string, fieldItem: any) {
  editModal.value = {
    visible: true,
    fieldKey,
    label: fieldItem.label || fieldKey,
    originalValue: fieldItem.original_model_value ?? fieldItem.value,
    currentValue: fieldItem.value || '',
    status: 'verified',
  }
}

async function saveFieldEdit() {
  if (!editModal.value.fieldKey) return
  try {
    const res = await fetch(
      `http://localhost:8000/api/imports/${jobId.value}/review/fields/${editModal.value.fieldKey}`,
      {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          value: editModal.value.currentValue,
          status: editModal.value.status,
        }),
      }
    )
    if (res.ok) {
      const data = await res.json()
      // 更新本地状态
      if (reviewData.value.fields && reviewData.value.fields[editModal.value.fieldKey]) {
        reviewData.value.fields[editModal.value.fieldKey] = data.field
      }
      if (data.summary) {
        reviewData.value.summary = data.summary
      }
      editModal.value.visible = false
    } else {
      const err = await res.json().catch(() => ({}))
      alert(err.error?.message || '保存修改失败')
    }
  } catch (err: any) {
    alert(err.message || '网络异常')
  }
}

// 确认入库
async function confirmReview() {
  if (summary.value.conflict_count > 0) {
    alert('请先核对并修改所有冲突字段后再确认入库！')
    return
  }
  submitting.value = true
  try {
    const res = await fetch(`http://localhost:8000/api/imports/${jobId.value}/confirm`, {
      method: 'POST',
    })
    if (res.ok) {
      const data = await res.json()
      confirmSuccessMsg.value = `保单《${data.product_name}》已成功确认入库！`
      setTimeout(() => {
        router.push(`/policies/${data.policy_id}`)
      }, 1000)
    } else {
      const err = await res.json().catch(() => ({}))
      alert(err.error?.message || '入库失败')
    }
  } catch (err: any) {
    alert(err.message || '网络异常')
  } finally {
    submitting.value = false
  }
}

const summary = computed(() => {
  return (
    reviewData.value?.summary || {
      verified_count: 0,
      conflict_count: 0,
      unverified_count: 0,
      not_found_count: 0,
    }
  )
})

const pagesList = computed<PageMeta[]>(() => {
  return reviewData.value?.pages || []
})

function getStatusBadge(status: string) {
  switch (status) {
    case 'verified':
      return { text: '已核验', class: 'badge-ok' }
    case 'conflict':
      return { text: '冲突', class: 'badge-risk' }
    case 'unverified':
      return { text: '待确认', class: 'badge-pending' }
    default:
      return { text: '未找到依据', class: 'badge-muted' }
  }
}
</script>

<template>
  <div class="review-page-wrapper">
    <!-- 顶部状态栏 -->
    <header class="review-header glass">
      <div class="header-left">
        <button class="back-link" @click="router.push('/import')">
          <ArrowLeft :size="16" /> 返回上传
        </button>
        <div class="doc-title-box">
          <h2 class="doc-title">{{ reviewData?.document_name || '保单抽取核对' }}</h2>
          <span class="category-tag">{{ reviewData?.category || '意外险' }}</span>
        </div>
      </div>

      <!-- 校验状态统计 Chips -->
      <div class="header-center">
        <div class="summary-chip chip-ok">
          <CheckCircle2 :size="14" /> 已核验 {{ summary.verified_count }}
        </div>
        <div v-if="summary.conflict_count > 0" class="summary-chip chip-risk animate-pulse">
          <AlertTriangle :size="14" /> 冲突待决 {{ summary.conflict_count }}
        </div>
        <div v-if="summary.unverified_count > 0" class="summary-chip chip-pending">
          <HelpCircle :size="14" /> 待确认 {{ summary.unverified_count }}
        </div>
      </div>

      <div class="header-right">
        <button
          class="btn-toggle-mask"
          @click="isMaskedMode = !isMaskedMode"
          :title="isMaskedMode ? '切换查看原始文件' : '切换查看脱敏打码图'"
        >
          <Eye :size="14" /> {{ isMaskedMode ? '脱敏打码' : '原件图片' }}
        </button>
        <button
          class="btn-confirm"
          :disabled="submitting || summary.conflict_count > 0"
          @click="confirmReview"
        >
          <FileCheck :size="16" /> {{ submitting ? '入库中...' : '确认入库' }}
        </button>
      </div>
    </header>

    <!-- 主体双栏区域 -->
    <div class="review-main-content">
      <!-- 左栏：抽取字段表单与证据 -->
      <div class="left-pane">
        <!-- 分类 Tab 切换 -->
        <div class="tab-bar">
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'basic' }"
            @click="activeTab = 'basic'"
          >
            <FileText :size="15" /> 基本信息
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'parties' }"
            @click="activeTab = 'parties'"
          >
            <Users :size="15" /> 关系人
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'coverages' }"
            @click="activeTab = 'coverages'"
          >
            <Shield :size="15" /> 责任项 ({{ reviewData?.coverages?.length || 0 }})
          </button>
          <button
            class="tab-btn"
            :class="{ active: activeTab === 'exclusions' }"
            @click="activeTab = 'exclusions'"
          >
            <AlertTriangle :size="15" /> 责任免除 ({{ reviewData?.exclusions?.length || 0 }})
          </button>
        </div>

        <div v-if="loading" class="pane-state">正在加载解析数据...</div>
        <div v-else-if="errorMsg" class="pane-state error">{{ errorMsg }}</div>
        <div v-else class="pane-body">
          <!-- 1. 基本信息面板 -->
          <div v-if="activeTab === 'basic'" class="fields-list">
            <div
              v-for="(fItem, fKey) in reviewData?.fields"
              :key="fKey"
              class="field-card glass-subtle"
              :class="{ 'has-conflict': fItem.status === 'conflict' }"
              @click="focusFieldEvidence(fItem, $event)"
            >
              <div class="field-top">
                <span class="field-label">{{ fItem.label || fKey }}</span>
                <div class="field-meta">
                  <span class="status-badge" :class="getStatusBadge(fItem.status).class">
                    {{ getStatusBadge(fItem.status).text }}
                  </span>
                  <button
                    class="edit-icon-btn"
                    @click.stop="openEditModal(String(fKey), fItem)"
                    title="人工核对修改"
                  >
                    <Edit2 :size="13" />
                  </button>
                </div>
              </div>

              <div class="field-value-line">
                <span class="field-val">{{ fItem.value || '未提取' }}</span>
                <span v-if="fItem.is_human_modified" class="human-tag">人工修改</span>
              </div>

              <div v-if="fItem.conflict_reason" class="conflict-alert">
                <AlertTriangle :size="13" /> {{ fItem.conflict_reason }}
              </div>

              <!-- 条款原文引用卡片 (思源宋体，左侧细竖线) -->
              <div v-if="fItem.quote" class="quote-card">
                <div class="quote-text font-serif">{{ fItem.quote }}</div>
                <div class="quote-footer">第 {{ fItem.page_no || 1 }} 页 原文依据</div>
              </div>
            </div>
          </div>

          <!-- 2. 关系人面板 -->
          <div v-if="activeTab === 'parties'" class="fields-list">
            <div
              v-if="reviewData?.parties?.applicant"
              class="field-card glass-subtle"
              @click="focusFieldEvidence(reviewData.parties.applicant, $event)"
            >
              <div class="field-top">
                <span class="field-label">投保人</span>
                <span
                  class="status-badge"
                  :class="getStatusBadge(reviewData.parties.applicant.status).class"
                >
                  {{ getStatusBadge(reviewData.parties.applicant.status).text }}
                </span>
              </div>
              <div class="field-value-line">
                <span class="field-val">{{ reviewData.parties.applicant.value }}</span>
              </div>
              <div v-if="reviewData.parties.applicant.quote" class="quote-card">
                <div class="quote-text font-serif">{{ reviewData.parties.applicant.quote }}</div>
                <div class="quote-footer">第 {{ reviewData.parties.applicant.page_no || 1 }} 页</div>
              </div>
            </div>

            <div
              v-for="(ins, idx) in reviewData?.parties?.insureds || []"
              :key="idx"
              class="field-card glass-subtle"
              @click="focusFieldEvidence(ins, $event)"
            >
              <div class="field-top">
                <span class="field-label">被保险人 {{ idx + 1 }}</span>
                <span class="status-badge" :class="getStatusBadge(ins.status).class">
                  {{ getStatusBadge(ins.status).text }}
                </span>
              </div>
              <div class="field-value-line">
                <span class="field-val">{{ ins.value }}</span>
              </div>
              <div v-if="ins.quote" class="quote-card">
                <div class="quote-text font-serif">{{ ins.quote }}</div>
                <div class="quote-footer">第 {{ ins.page_no || 1 }} 页</div>
              </div>
            </div>
          </div>

          <!-- 3. 责任项面板 -->
          <div v-if="activeTab === 'coverages'" class="coverages-list">
            <div
              v-for="cov in reviewData?.coverages || []"
              :key="cov.id"
              class="coverage-card glass-subtle"
            >
              <div class="cov-header">
                <span class="cov-name">{{ cov.name }}</span>
                <span class="cov-kind">{{ cov.kind }}</span>
              </div>

              <div class="cov-grid">
                <div
                  class="cov-prop"
                  @click="focusFieldEvidence(cov.limit, $event)"
                >
                  <span class="prop-k">保额/限额:</span>
                  <span class="prop-v">{{ cov.limit?.value || '详见条款' }}</span>
                </div>
                <div
                  class="cov-prop"
                  @click="focusFieldEvidence(cov.deductible, $event)"
                >
                  <span class="prop-k">免赔额:</span>
                  <span class="prop-v">{{ cov.deductible?.value || '0元' }}</span>
                </div>
              </div>

              <div
                v-if="cov.limit?.quote"
                class="quote-card"
                @click="focusFieldEvidence(cov.limit, $event)"
              >
                <div class="quote-text font-serif">{{ cov.limit.quote }}</div>
                <div class="quote-footer">第 {{ cov.limit.page_no || 1 }} 页 原文依据</div>
              </div>
            </div>
          </div>

          <!-- 4. 责任免除面板 -->
          <div v-if="activeTab === 'exclusions'" class="exclusions-list">
            <div
              v-for="ex in reviewData?.exclusions || []"
              :key="ex.id"
              class="exclusion-card glass-subtle"
              @click="focusFieldEvidence(ex, $event)"
            >
              <div class="ex-explanation">
                <span class="ex-tag">免责释义</span>
                {{ ex.plain_explanation }}
              </div>
              <div v-if="ex.quote" class="quote-card">
                <div class="quote-text font-serif">{{ ex.quote }}</div>
                <div class="quote-footer">第 {{ ex.page_no || 1 }} 页 条款原文</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右栏：原文阅读器与 FLIP 高亮层 (桌面常驻，移动端抽屉) -->
      <div class="right-pane">
        <DocViewer
          :pages="pagesList"
          :active-highlight="activeHighlight"
          :masked-mode="isMaskedMode"
        />
      </div>
    </div>

    <!-- 人工核对修改弹窗 -->
    <div v-if="editModal.visible" class="modal-overlay" @click.self="editModal.visible = false">
      <div class="modal-dialog glass">
        <h3 class="modal-title">修改字段值: {{ editModal.label }}</h3>
        <p class="modal-sub">模型原始抽取值: {{ editModal.originalValue || '无' }}</p>

        <div class="form-group">
          <label class="input-label">确认数值 / 修正文本</label>
          <input
            v-model="editModal.currentValue"
            class="text-input"
            type="text"
            placeholder="请输入核对后的真实信息"
          />
        </div>

        <div class="modal-actions">
          <button class="btn-cancel" @click="editModal.visible = false">取消</button>
          <button class="btn-save" @click="saveFieldEdit">确认修正并标记为已核验</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.review-page-wrapper {
  display: flex;
  flex-direction: column;
  height: 100vh;
  overflow: hidden;
  background: var(--bg);
}

.review-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 24px;
  border-bottom: 1px solid var(--glass-stroke);
  z-index: 20;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-link {
  background: transparent;
  border: none;
  color: var(--text-muted);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  font-size: var(--fs-14);
}

.back-link:hover {
  color: var(--text);
}

.doc-title-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.doc-title {
  margin: 0;
  font-size: var(--fs-18);
  font-weight: 600;
  color: var(--text);
}

.category-tag {
  font-size: var(--fs-12);
  background: var(--glass-fill-strong);
  padding: 2px 8px;
  border-radius: var(--r-badge);
  color: var(--text-muted);
}

.header-center {
  display: flex;
  align-items: center;
  gap: 10px;
}

.summary-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-12);
  padding: 4px 12px;
  border-radius: var(--r-badge);
  font-weight: 500;
}

.chip-ok {
  background: color-mix(in oklch, var(--ok) 15%, transparent);
  color: var(--ok);
  border: 1px solid var(--ok);
}

.chip-risk {
  background: color-mix(in oklch, var(--risk) 15%, transparent);
  color: var(--risk);
  border: 1px solid var(--risk);
}

.chip-pending {
  background: color-mix(in oklch, var(--pending) 15%, transparent);
  color: var(--pending);
  border: 1px solid var(--pending);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-toggle-mask {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  padding: 6px 12px;
  border-radius: var(--r-control);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-12);
  color: var(--text);
}

.btn-confirm {
  background: var(--ok);
  color: white;
  border: none;
  padding: 8px 18px;
  border-radius: var(--r-control);
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: opacity 0.2s ease;
}

.btn-confirm:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.review-main-content {
  display: grid;
  grid-template-columns: 480px 1fr;
  flex: 1;
  overflow: hidden;
}

@media (max-width: 1024px) {
  .review-main-content {
    grid-template-columns: 1fr;
  }
}

.left-pane {
  display: flex;
  flex-direction: column;
  border-right: 1px solid var(--glass-stroke);
  background: var(--glass-fill);
  overflow: hidden;
}

.tab-bar {
  display: flex;
  border-bottom: 1px solid var(--glass-stroke);
  background: var(--glass-fill-strong);
}

.tab-btn {
  flex: 1;
  padding: 10px 8px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  font-size: var(--fs-13);
  color: var(--text-muted);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.tab-btn.active {
  color: var(--ok);
  border-bottom-color: var(--ok);
  font-weight: 600;
}

.pane-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.field-card {
  padding: 12px 16px;
  border-radius: var(--r-control);
  border: 1px solid var(--glass-stroke);
  background: var(--glass-fill-strong);
  cursor: pointer;
  transition: all 0.15s ease;
}

.field-card:hover {
  border-color: var(--ok);
}

.field-card.has-conflict {
  border-color: var(--risk);
  background: color-mix(in oklch, var(--risk) 4%, transparent);
}

.field-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.field-label {
  font-size: var(--fs-13);
  color: var(--text-muted);
}

.field-meta {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-badge {
  font-size: var(--fs-12);
  padding: 2px 6px;
  border-radius: var(--r-badge);
}

.badge-ok {
  background: color-mix(in oklch, var(--ok) 16%, transparent);
  color: var(--ok);
}

.badge-risk {
  background: color-mix(in oklch, var(--risk) 16%, transparent);
  color: var(--risk);
}

.badge-pending {
  background: color-mix(in oklch, var(--pending) 16%, transparent);
  color: var(--pending);
}

.badge-muted {
  background: var(--glass-fill);
  color: var(--text-muted);
}

.edit-icon-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px;
}

.edit-icon-btn:hover {
  color: var(--ok);
}

.field-value-line {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.field-val {
  font-size: var(--fs-15);
  font-weight: 600;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.human-tag {
  font-size: var(--fs-12);
  background: var(--glass-fill);
  color: var(--ok);
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid var(--ok);
}

.conflict-alert {
  margin-top: 6px;
  font-size: var(--fs-12);
  color: var(--risk);
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 引用卡片：思源宋体，左侧细竖线 */
.quote-card {
  margin-top: 8px;
  padding: 6px 12px;
  border-left: 2.5px solid var(--ok);
  background: color-mix(in oklch, var(--c-paper) 40%, transparent);
  border-radius: 0 var(--r-control) var(--r-control) 0;
}

.font-serif {
  font-family: var(--font-quote);
}

.quote-text {
  font-size: var(--fs-13);
  color: var(--text);
  line-height: 1.5;
}

.quote-footer {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-top: 4px;
}

.coverages-list,
.exclusions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.coverage-card,
.exclusion-card {
  padding: 14px 16px;
  border-radius: var(--r-control);
  border: 1px solid var(--glass-stroke);
  background: var(--glass-fill-strong);
  cursor: pointer;
}

.cov-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.cov-name {
  font-size: var(--fs-15);
  font-weight: 600;
  color: var(--text);
}

.cov-kind {
  font-size: var(--fs-12);
  padding: 2px 8px;
  background: var(--glass-fill);
  border-radius: var(--r-badge);
  color: var(--text-muted);
}

.cov-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-top: 8px;
}

.cov-prop {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-13);
}

.prop-k {
  color: var(--text-muted);
}

.prop-v {
  color: var(--text);
  font-weight: 500;
}

.ex-explanation {
  font-size: var(--fs-14);
  color: var(--text);
  line-height: 1.5;
}

.ex-tag {
  font-size: var(--fs-12);
  background: color-mix(in oklch, var(--risk) 16%, transparent);
  color: var(--risk);
  padding: 1px 6px;
  border-radius: 4px;
  margin-right: 6px;
  font-weight: 600;
}

.right-pane {
  flex: 1;
  height: 100%;
  overflow: hidden;
}

/* 模态框 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9000;
}

.modal-dialog {
  width: 440px;
  max-width: 90vw;
  padding: 24px;
  border-radius: var(--r-page);
  border: 1px solid var(--glass-stroke);
  background: var(--glass-fill-strong);
  box-shadow: var(--glass-shadow);
}

.modal-title {
  margin: 0 0 4px;
  font-size: var(--fs-18);
  font-weight: 600;
  color: var(--text);
}

.modal-sub {
  font-size: var(--fs-13);
  color: var(--text-muted);
  margin-bottom: 18px;
}

.form-group {
  margin-bottom: 16px;
}

.input-label {
  display: block;
  font-size: var(--fs-13);
  color: var(--text-muted);
  margin-bottom: 6px;
}

.text-input {
  width: 100%;
  padding: 8px 12px;
  border-radius: var(--r-control);
  border: 1px solid var(--glass-stroke);
  background: var(--c-paper);
  color: var(--text);
  font-size: var(--fs-14);
  outline: none;
  box-sizing: border-box;
}

.text-input:focus {
  border-color: var(--ok);
  outline: 2px solid var(--ok);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
}

.btn-cancel {
  background: transparent;
  border: 1px solid var(--glass-stroke);
  padding: 6px 14px;
  border-radius: var(--r-control);
  color: var(--text-muted);
  cursor: pointer;
}

.btn-save {
  background: var(--ok);
  color: white;
  border: none;
  padding: 6px 16px;
  border-radius: var(--r-control);
  cursor: pointer;
  font-weight: 500;
}
</style>
