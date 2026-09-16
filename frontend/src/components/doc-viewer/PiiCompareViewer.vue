<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import {
  ShieldCheck,
  ChevronLeft,
  ChevronRight,
  Eye,
  FileText,
  Lock,
  CheckCircle2,
} from 'lucide-vue-next'

const props = defineProps<{
  documentId: string
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const docDetails = ref<any>(null)
const currentPage = ref(1)
const compareData = ref<any>(null)
const loading = ref(false)
const viewMode = ref<'image' | 'text'>('image')

// 同步滚动 refs
const leftPane = ref<HTMLElement | null>(null)
const rightPane = ref<HTMLElement | null>(null)
let isSyncingLeft = false
let isSyncingRight = false

function onLeftScroll() {
  if (isSyncingLeft || !leftPane.value || !rightPane.value) return
  isSyncingRight = true
  rightPane.value.scrollTop = leftPane.value.scrollTop
  rightPane.value.scrollLeft = leftPane.value.scrollLeft
  requestAnimationFrame(() => {
    isSyncingRight = false
  })
}

function onRightScroll() {
  if (isSyncingRight || !leftPane.value || !rightPane.value) return
  isSyncingLeft = true
  leftPane.value.scrollTop = rightPane.value.scrollTop
  leftPane.value.scrollLeft = rightPane.value.scrollLeft
  requestAnimationFrame(() => {
    isSyncingLeft = false
  })
}

async function loadDocument() {
  try {
    const res = await fetch(`/api/documents/${props.documentId}`)
    if (res.ok) {
      docDetails.value = await res.json()
      if (docDetails.value.pages?.length) {
        currentPage.value = 1
        loadPageCompare(1)
      }
    }
  } catch (err) {
    console.error('加载文档详情失败:', err)
  }
}

async function loadPageCompare(pageNo: number) {
  loading.value = true
  try {
    const res = await fetch(`/api/documents/${props.documentId}/pages/${pageNo}/pii-compare`)
    if (res.ok) {
      compareData.value = await res.json()
    }
  } catch (err) {
    console.error('加载脱敏对比数据失败:', err)
  } finally {
    loading.value = false
  }
}

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--
    loadPageCompare(currentPage.value)
  }
}

function nextPage() {
  if (docDetails.value && currentPage.value < docDetails.value.page_count) {
    currentPage.value++
    loadPageCompare(currentPage.value)
  }
}

watch(() => props.documentId, () => {
  loadDocument()
})

onMounted(() => {
  loadDocument()
})
</script>

<template>
  <div class="pii-compare-modal glass">
    <!-- 顶部工具栏 -->
    <header class="modal-header">
      <div class="header-left">
        <ShieldCheck :size="22" class="text-ok" />
        <div>
          <h2 class="modal-title">本地脱敏前后对比预览</h2>
          <span class="modal-subtitle">
            {{ docDetails?.original_name || '保单文件' }} · 状态：
            <span v-if="compareData?.pii_status === 'success'" class="badge badge--ok">
              <span class="badge-dot"></span> 二次安全校验通过 (零泄露)
            </span>
            <span v-else class="badge badge--pending">校验中</span>
          </span>
        </div>
      </div>

      <div class="header-right">
        <!-- 视图切换：图像 vs 文本 -->
        <div class="view-toggle">
          <button
            class="toggle-btn"
            :class="{ active: viewMode === 'image' }"
            @click="viewMode = 'image'"
          >
            <Eye :size="14" />
            原件与打码图
          </button>
          <button
            class="toggle-btn"
            :class="{ active: viewMode === 'text' }"
            @click="viewMode = 'text'"
          >
            <FileText :size="14" />
            文本层比对
          </button>
        </div>

        <!-- 翻页控制 -->
        <div class="pager">
          <button
            class="pager-btn"
            :disabled="currentPage <= 1"
            @click="prevPage"
            title="上一页"
          >
            <ChevronLeft :size="16" />
          </button>
          <span class="page-indicator">
            第 {{ currentPage }} 页 / 共 {{ docDetails?.page_count || 1 }} 页
          </span>
          <button
            class="pager-btn"
            :disabled="!docDetails || currentPage >= docDetails.page_count"
            @click="nextPage"
            title="下一页"
          >
            <ChevronRight :size="16" />
          </button>
        </div>

        <button class="btn-secondary close-btn" @click="emit('close')">
          关闭
        </button>
      </div>
    </header>

    <!-- 左右两栏同步滚动视口 -->
    <div class="compare-body">
      <!-- 左栏：脱敏前（仅保留本地） -->
      <section class="compare-col">
        <div class="col-header">
          <span class="col-tag tag-raw">
            <Lock :size="12" /> 本地原始层（家庭内网私有，绝不外发）
          </span>
        </div>

        <div
          ref="leftPane"
          class="col-content sync-scroll"
          @scroll="onLeftScroll"
        >
          <div v-if="viewMode === 'image'" class="page-paper image-container">
            <img
              v-if="compareData?.image_url"
              :src="compareData.image_url"
              alt="原始页面"
              class="page-img"
            />
            <div v-else class="loading-state">载入中...</div>
          </div>

          <div v-else class="page-paper text-container">
            <pre class="raw-text-view">{{ compareData?.raw_text }}</pre>
          </div>
        </div>
      </section>

      <!-- 分隔线 -->
      <div class="col-divider"></div>

      <!-- 右栏：脱敏后（发往模型的内容） -->
      <section class="compare-col">
        <div class="col-header">
          <span class="col-tag tag-masked">
            <CheckCircle2 :size="12" /> 发送给模型的内容（脱敏打码后）
          </span>
        </div>

        <div
          ref="rightPane"
          class="col-content sync-scroll"
          @scroll="onRightScroll"
        >
          <div v-if="viewMode === 'image'" class="page-paper image-container">
            <img
              v-if="compareData?.masked_image_url"
              :src="compareData.masked_image_url"
              alt="打码后页面"
              class="page-img"
            />
            <div v-else class="loading-state">载入中...</div>
          </div>

          <div v-else class="page-paper text-container">
            <pre class="masked-text-view">{{ compareData?.masked_text }}</pre>
          </div>
        </div>
      </section>
    </div>

    <!-- 底部：已识别占位符映射表 -->
    <footer class="modal-footer">
      <div class="footer-title">
        <span>当前文档脱敏占位符映射 (共 {{ docDetails?.pii_mappings?.length || 0 }} 项)</span>
        <span class="footer-hint">真实信息已用应用专属 Fernet 密钥加密，模型仅可获知带方括号的代号</span>
      </div>

      <div class="mappings-chip-list">
        <div
          v-for="(item, idx) in docDetails?.pii_mappings || []"
          :key="idx"
          class="mapping-chip"
        >
          <span class="chip-placeholder">{{ item.placeholder }}</span>
          <span class="chip-kind">
            {{
              item.kind === 'id_card' ? '身份证' :
              item.kind === 'phone' ? '手机号' :
              item.kind === 'bank_card' ? '银行卡' :
              item.kind === 'email' ? '邮箱' :
              item.kind === 'policy_no' ? '保单号' :
              item.kind === 'name' ? '家庭成员姓名' :
              item.kind === 'address' ? '住址' : '敏感信息'
            }}
          </span>
        </div>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.pii-compare-modal {
  display: flex;
  flex-direction: column;
  height: 88vh;
  max-width: 1380px;
  width: 95vw;
  margin: 0 auto;
  overflow: hidden;
  border-radius: var(--r-panel);
  border: 1px solid var(--glass-stroke);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-3) var(--sp-5);
  border-bottom: 1px solid var(--glass-stroke);
  background: var(--glass-fill-strong);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.modal-title {
  font-size: var(--fs-16);
  font-weight: 700;
}

.modal-subtitle {
  font-size: var(--fs-12);
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-top: 2px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.view-toggle {
  display: flex;
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  padding: 2px;
}

.toggle-btn {
  padding: 4px 10px;
  font-size: var(--fs-12);
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text-muted);
}

.toggle-btn.active {
  background: var(--ok);
  color: #fff;
  font-weight: 600;
}

.pager {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
}

.pager-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: var(--r-control);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
}

.page-indicator {
  font-size: var(--fs-12);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  padding: 0 var(--sp-2);
}

/* 两栏主体 */
.compare-body {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.compare-col {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.col-divider {
  width: 1px;
  background: var(--glass-stroke);
}

.col-header {
  padding: var(--sp-2) var(--sp-4);
  background: color-mix(in oklch, var(--text) 3%, transparent);
  border-bottom: 1px solid var(--glass-stroke);
}

.col-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-12);
  font-weight: 600;
}

.tag-raw {
  color: var(--text-muted);
}

.tag-masked {
  color: var(--ok);
}

.col-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: auto;
  padding: var(--sp-4);
  display: flex;
  justify-content: center;
}

.page-paper {
  background: var(--c-paper);
  color: var(--c-pool);
  border-radius: var(--r-page);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  max-width: 680px;
  width: 100%;
}

.image-container {
  padding: var(--sp-2);
}

.page-img {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 4px;
}

.text-container {
  padding: var(--sp-5);
  font-family: var(--font-quote);
  font-size: var(--fs-14);
  line-height: var(--lh-quote);
}

.raw-text-view,
.masked-text-view {
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
}

.masked-text-view {
  color: var(--c-pool);
}

/* 底部映射栏 */
.modal-footer {
  padding: var(--sp-3) var(--sp-5);
  border-top: 1px solid var(--glass-stroke);
  background: var(--glass-fill-strong);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.footer-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--fs-12);
  font-weight: 600;
}

.footer-hint {
  font-weight: 400;
  color: var(--text-muted);
}

.mappings-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  max-height: 80px;
  overflow-y: auto;
}

.mapping-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  padding: 2px 8px;
  border-radius: var(--r-pill);
  font-size: var(--fs-12);
}

.chip-placeholder {
  font-weight: 600;
  color: var(--ok);
}

.chip-kind {
  color: var(--text-muted);
}

@media (max-width: 820px) {
  .compare-body {
    flex-direction: column;
  }
  .col-divider {
    height: 1px;
    width: 100%;
  }
}
</style>
