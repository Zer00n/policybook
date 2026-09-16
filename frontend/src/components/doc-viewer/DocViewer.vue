<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ZoomIn, ZoomOut, Maximize2, ChevronLeft, ChevronRight, X } from 'lucide-vue-next'

export interface PageMeta {
  page_no: number
  width: number
  height: number
  image_url: string
  masked_image_url: string
}

export interface HighlightTarget {
  page_no: number
  rects: Array<{ x0: number; y0: number; x1: number; y1: number }>
  status?: string
  sourceEl?: HTMLElement | null
}

const props = withDefaults(
  defineProps<{
    pages: PageMeta[]
    activeHighlight?: HighlightTarget | null
    isDrawer?: boolean
    maskedMode?: boolean
  }>(),
  {
    isDrawer: false,
    maskedMode: true,
  }
)

const emit = defineEmits<{
  (e: 'close'): void
}>()

const currentPage = ref(1)
const zoomLevel = ref(1.0) // 1.0 = 100%, 1.5 = 150%, 0 = fit-width
const pageRefs = ref<Record<number, HTMLElement>>({})
const pageImgRefs = ref<Record<number, HTMLImageElement>>({})
const viewerContainer = ref<HTMLElement | null>(null)
const flyBox = ref<{
  visible: boolean
  left: number
  top: number
  width: number
  height: number
  glowing: boolean
  color: string
}>({
  visible: false,
  left: 0,
  top: 0,
  width: 0,
  height: 0,
  glowing: false,
  color: 'var(--ok)',
})

const totalPages = computed(() => props.pages.length)

function setPageRef(el: any, pageNo: number) {
  if (el) pageRefs.value[pageNo] = el
}

function setImgRef(el: any, pageNo: number) {
  if (el) pageImgRefs.value[pageNo] = el
}

function getStatusColor(status?: string) {
  if (status === 'conflict') return 'var(--risk)'
  if (status === 'unverified') return 'var(--pending)'
  if (status === 'not_found') return 'var(--text-muted)'
  return 'var(--ok)'
}

// FLIP 引用定位动效 (DEV-GUIDE 7.8)
async function triggerFlipAnimation(target: HighlightTarget) {
  const pageEl = pageRefs.value[target.page_no]
  const imgEl = pageImgRefs.value[target.page_no]
  if (!pageEl || !imgEl || !target.rects || target.rects.length === 0) return

  currentPage.value = target.page_no

  // 1. 平滑滚动到目标页 (scrollIntoView)
  pageEl.scrollIntoView({ behavior: 'smooth', block: 'center' })

  const isReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  const isLite = document.documentElement.getAttribute('data-lite') === 'true'

  if (isReducedMotion || isLite || !target.sourceEl) {
    // 降级模式：无动画，直接显示
    return
  }

  // 延迟 180ms 等滚动启动
  await new Promise((r) => setTimeout(r, 180))

  // 计算目标在屏幕上的实际像素坐标
  const imgRect = imgEl.getBoundingClientRect()
  const pageMeta = props.pages.find((p) => p.page_no === target.page_no)
  const pagePtWidth = pageMeta?.width ? pageMeta.width / 2 : 595 // 144 DPI -> pt 约为 px / 2
  const scale = imgRect.width / pagePtWidth

  // 计算首个或合并高亮框在屏幕上的坐标
  const r0 = target.rects[0]
  const targetX = imgRect.left + r0.x0 * scale
  const targetY = imgRect.top + r0.y0 * scale
  const targetW = (r0.x1 - r0.x0) * scale
  const targetH = (r0.y1 - r0.y0) * scale

  // 获取起点（点击的卡片屏幕坐标）
  const sourceRect = target.sourceEl.getBoundingClientRect()
  const color = getStatusColor(target.status)

  // 2. 初始化飞入光晕框 (FLIP: First)
  flyBox.value = {
    visible: true,
    left: sourceRect.left,
    top: sourceRect.top,
    width: sourceRect.width,
    height: sourceRect.height,
    glowing: false,
    color,
  }

  await nextTick()

  // 3. 执行过渡飞行动画 (FLIP: Last & Invert & Play)
  requestAnimationFrame(() => {
    flyBox.value.left = targetX
    flyBox.value.top = targetY
    flyBox.value.width = targetW
    flyBox.value.height = targetH
  })

  // 480ms 后到位，触发光晕外发光扩散 (600ms)
  setTimeout(() => {
    flyBox.value.glowing = true
    setTimeout(() => {
      flyBox.value.visible = false
      flyBox.value.glowing = false
    }, 600)
  }, 480)
}

watch(
  () => props.activeHighlight,
  (newVal) => {
    if (newVal) {
      triggerFlipAnimation(newVal)
    }
  },
  { deep: true }
)

function prevPage() {
  if (currentPage.value > 1) {
    currentPage.value--
    pageRefs.value[currentPage.value]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function nextPage() {
  if (currentPage.value < totalPages.value) {
    currentPage.value++
    pageRefs.value[currentPage.value]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === '[') prevPage()
  if (e.key === ']') nextPage()
  if (e.key === 'Escape' && props.isDrawer) emit('close')
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

// 计算某个页面上属于当前 activeHighlight 的矩形高亮框
function getPageRects(pageNo: number) {
  if (!props.activeHighlight || props.activeHighlight.page_no !== pageNo) return []
  const imgEl = pageImgRefs.value[pageNo]
  if (!imgEl) return []

  const pageMeta = props.pages.find((p) => p.page_no === pageNo)
  const pagePtWidth = pageMeta?.width ? pageMeta.width / 2 : 595
  const imgWidth = imgEl.clientWidth || 595
  const scale = imgWidth / pagePtWidth

  return props.activeHighlight.rects.map((r) => ({
    left: `${r.x0 * scale}px`,
    top: `${r.y0 * scale}px`,
    width: `${(r.x1 - r0_val(r.x0, r.x1)) * scale}px`,
    height: `${(r.y1 - r0_val(r.y0, r.y1)) * scale}px`,
    color: getStatusColor(props.activeHighlight?.status),
  }))
}

function r0_val(a: number, b: number) {
  return a
}
</script>

<template>
  <div class="doc-viewer" :class="{ 'as-drawer': isDrawer }" ref="viewerContainer">
    <!-- 顶部工具栏 -->
    <div class="viewer-toolbar glass">
      <div class="page-nav">
        <button class="icon-btn" :disabled="currentPage <= 1" @click="prevPage" title="上一页 ([)">
          <ChevronLeft :size="16" />
        </button>
        <span class="page-num">{{ currentPage }} / {{ totalPages || 1 }}</span>
        <button class="icon-btn" :disabled="currentPage >= totalPages" @click="nextPage" title="下一页 (])">
          <ChevronRight :size="16" />
        </button>
      </div>

      <div class="zoom-controls">
        <button class="icon-btn" @click="zoomLevel = Math.max(0.7, zoomLevel - 0.15)" title="缩小">
          <ZoomOut :size="16" />
        </button>
        <span class="zoom-text">{{ Math.round(zoomLevel * 100) }}%</span>
        <button class="icon-btn" @click="zoomLevel = Math.min(2.0, zoomLevel + 0.15)" title="放大">
          <ZoomIn :size="16" />
        </button>
        <button class="icon-btn" @click="zoomLevel = 1.0" title="适应大小">
          <Maximize2 :size="16" />
        </button>
      </div>

      <div v-if="isDrawer" class="drawer-actions">
        <button class="icon-btn close-btn" @click="emit('close')" title="关闭 (Esc)">
          <X :size="18" />
        </button>
      </div>
    </div>

    <!-- 原文页面流（纸面质感，清晰无模糊） -->
    <div class="pages-scroll-container">
      <div
        v-for="page in pages"
        :key="page.page_no"
        :ref="(el) => setPageRef(el, page.page_no)"
        class="paper-page-wrap"
        :style="{ transform: `scale(${zoomLevel})`, transformOrigin: 'top center' }"
      >
        <div class="page-header-tag">第 {{ page.page_no }} 页</div>
        <div class="paper-page">
          <img
            :ref="(el) => setImgRef(el, page.page_no)"
            :src="maskedMode ? page.masked_image_url : page.image_url"
            :alt="`第 ${page.page_no} 页`"
            class="page-image"
            loading="lazy"
          />

          <!-- 静态高亮矩形框 (已定位在原文上) -->
          <div
            v-for="(box, bIdx) in getPageRects(page.page_no)"
            :key="bIdx"
            class="static-highlight-box"
            :style="{
              left: box.left,
              top: box.top,
              width: box.width,
              height: box.height,
              borderColor: box.color,
              backgroundColor: box.color,
            }"
          />
        </div>
      </div>

      <div v-if="pages.length === 0" class="empty-viewer">
        <p>暂无文档页面</p>
      </div>
    </div>

    <!-- FLIP 飞行高亮框动效图层 -->
    <div
      v-if="flyBox.visible"
      class="flip-fly-box"
      :class="{ 'glow-pulse': flyBox.glowing }"
      :style="{
        left: `${flyBox.left}px`,
        top: `${flyBox.top}px`,
        width: `${flyBox.width}px`,
        height: `${flyBox.height}px`,
        borderColor: flyBox.color,
        boxShadow: `0 0 20px ${flyBox.color}`,
      }"
    />
  </div>
</template>

<style scoped>
.doc-viewer {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg);
  position: relative;
  overflow: hidden;
}

.doc-viewer.as-drawer {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 520px;
  max-width: 100vw;
  z-index: 1000;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.15);
}

.viewer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  border-bottom: 1px solid var(--glass-stroke);
  z-index: 10;
  gap: 12px;
}

.page-nav,
.zoom-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-num,
.zoom-text {
  font-size: var(--fs-12);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
  min-width: 48px;
  text-align: center;
}

.icon-btn {
  background: transparent;
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  color: var(--text);
  padding: 4px 8px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
}

.icon-btn:hover:not(:disabled) {
  background: var(--glass-fill-strong);
}

.icon-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.close-btn:hover {
  color: var(--risk);
  border-color: var(--risk);
}

.pages-scroll-container {
  flex: 1;
  overflow-y: auto;
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 28px;
  background: color-mix(in oklch, var(--c-pool) 4%, var(--c-mist));
}

.paper-page-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  transition: transform 0.2s ease;
}

.page-header-tag {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-bottom: 6px;
  align-self: flex-start;
}

/* 纸质质感：保持浅色纸面底色，清晰无模糊 (DEV-GUIDE 7.8) */
.paper-page {
  position: relative;
  background-color: var(--c-paper);
  border-radius: var(--r-page);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.04);
  overflow: hidden;
  max-width: 100%;
}

.page-image {
  display: block;
  width: 100%;
  height: auto;
  user-select: none;
}

/* 静态高亮框 */
.static-highlight-box {
  position: absolute;
  pointer-events: none;
  border: 1.5px solid var(--ok);
  background-color: color-mix(in oklch, var(--ok) 14%, transparent);
  border-radius: 3px;
  transition: all 0.2s ease;
}

/* FLIP 飞行高亮框 */
.flip-fly-box {
  position: fixed;
  pointer-events: none;
  z-index: 9999;
  border: 2px solid var(--ok);
  border-radius: 4px;
  background-color: color-mix(in oklch, var(--ok) 18%, transparent);
  transition: all 480ms cubic-bezier(0.16, 1, 0.3, 1);
}

.flip-fly-box.glow-pulse {
  animation: glow-pulse-fade 600ms ease-out forwards;
}

@keyframes glow-pulse-fade {
  0% {
    transform: scale(1);
    opacity: 1;
    filter: drop-shadow(0 0 16px currentColor);
  }
  50% {
    transform: scale(1.06);
    opacity: 0.9;
    filter: drop-shadow(0 0 28px currentColor);
  }
  100% {
    transform: scale(1);
    opacity: 0.3;
    filter: drop-shadow(0 0 4px currentColor);
  }
}

.empty-viewer {
  padding: 60px 0;
  color: var(--text-muted);
  font-size: var(--fs-14);
}
</style>
