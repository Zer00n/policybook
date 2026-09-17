<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ZoomIn, ZoomOut, RotateCcw, Calendar } from 'lucide-vue-next'

export interface TimelineSegment {
  segment_type: 'waiting' | 'effective' | 'gap'
  start_date: string
  end_date: string
  label: string
  policy_id?: string
  policy_name?: string
  color?: string
}

export interface PolicyTimelineBand {
  policy_id: string
  product_name: string
  category: string
  insurer: string
  start_date: string
  end_date: string
  segments: TimelineSegment[]
}

export interface MemberTimeline {
  member_id: string
  member_name: string
  member_color: string
  relation: string
  has_gap: boolean
  bands: PolicyTimelineBand[]
  gap_segments?: TimelineSegment[]
}

const props = defineProps<{
  timelines: MemberTimeline[]
  todayStr: string
}>()

const router = useRouter()

// Viewport & Zoom state
// zoomMonths: 12, 24, 36
const zoomMonths = ref<number>(36)
const panOffsetDays = ref<number>(0)

// Drag to pan state
const isDragging = ref(false)
const dragStartX = ref(0)
const dragStartOffset = ref(0)
const svgContainerRef = ref<HTMLDivElement | null>(null)

// Animation flag (only run once per session, DEV-GUIDE 7.7)
const hasAnimated = ref(false)
const isAnimating = ref(false)

// Tooltip state
const hoverInfo = ref<{
  visible: boolean
  x: number
  y: number
  title: string
  insurer?: string
  dates: string
  type: string
  policyId?: string
} | null>(null)

const todayDate = computed(() => {
  return props.todayStr ? new Date(props.todayStr) : new Date()
})

// Calculate date range based on zoom and pan
const dateRange = computed(() => {
  const center = new Date(todayDate.value)
  center.setDate(center.getDate() + panOffsetDays.value)

  const halfDays = Math.round((zoomMonths.value * 30.4) / 2)
  const startDate = new Date(center)
  startDate.setDate(startDate.getDate() - halfDays)

  const endDate = new Date(center)
  endDate.setDate(endDate.getDate() + halfDays)

  const totalDays = Math.max(1, Math.round((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)))

  return { startDate, endDate, totalDays }
})

// SVG Coordinates
const SVG_WIDTH = 1000
const PADDING_LEFT = 120
const PADDING_RIGHT = 30
const CHART_WIDTH = SVG_WIDTH - PADDING_LEFT - PADDING_RIGHT
const HEADER_HEIGHT = 45
const ROW_HEIGHT = 58
const BAND_HEIGHT = 16
const GAP_HEIGHT = 14

const svgHeight = computed(() => {
  return HEADER_HEIGHT + Math.max(props.timelines.length, 1) * ROW_HEIGHT + 30
})

function dateToX(dStr: string): number {
  const d = new Date(dStr)
  const { startDate, totalDays } = dateRange.value
  const diffDays = (d.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)
  const ratio = diffDays / totalDays
  return PADDING_LEFT + ratio * CHART_WIDTH
}

// 计算一段色带/空档在可视窗口内实际应绘制的矩形：
// 两端都裁剪到可视范围，且当整段完全落在可视窗口之外时 visible=false（不渲染），
// 避免出现贴在图表边缘、暗示并不存在的覆盖/空档的“幻影”色带
function segRect(startDate: string, endDate: string, minWidth = 4) {
  const rawStart = dateToX(startDate)
  const rawEnd = dateToX(endDate)
  const chartRight = PADDING_LEFT + CHART_WIDTH
  if (rawEnd < PADDING_LEFT || rawStart > chartRight) {
    return { x: 0, width: 0, visible: false }
  }
  const x = Math.max(PADDING_LEFT, rawStart)
  const clampedEnd = Math.min(chartRight, rawEnd)
  return { x, width: Math.max(minWidth, clampedEnd - x), visible: true }
}

// Time ticks (Months/Years)
const timeTicks = computed(() => {
  const { startDate, endDate, totalDays } = dateRange.value
  const ticks: { x: number; label: string; isYear: boolean }[] = []

  const stepMonths = zoomMonths.value <= 12 ? 1 : (zoomMonths.value <= 24 ? 2 : 3)
  const cur = new Date(startDate.getFullYear(), startDate.getMonth(), 1)

  while (cur <= endDate) {
    if (cur >= startDate) {
      const diffDays = (cur.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24)
      const x = PADDING_LEFT + (diffDays / totalDays) * CHART_WIDTH
      const isJan = cur.getMonth() === 0
      const label = isJan
        ? `${cur.getFullYear()}年`
        : `${cur.getMonth() + 1}月`
      ticks.push({ x, label, isYear: isJan })
    }
    cur.setMonth(cur.getMonth() + stepMonths)
  }
  return ticks
})

// Today line X position
const todayX = computed(() => {
  return dateToX(props.todayStr || new Date().toISOString().split('T')[0])
})

const isTodayVisible = computed(() => {
  return todayX.value >= PADDING_LEFT && todayX.value <= PADDING_LEFT + CHART_WIDTH
})

// Zoom controls
function setZoom(months: number) {
  zoomMonths.value = months
}

function resetView() {
  zoomMonths.value = 36
  panOffsetDays.value = 0
}

// Drag / Pan handlers
function onMouseDown(e: MouseEvent) {
  isDragging.value = true
  dragStartX.value = e.clientX
  dragStartOffset.value = panOffsetDays.value
}

function onMouseMove(e: MouseEvent) {
  if (!isDragging.value || !svgContainerRef.value) return
  const deltaX = e.clientX - dragStartX.value
  const containerW = svgContainerRef.value.clientWidth || 800
  const daysPerPixel = dateRange.value.totalDays / containerW
  panOffsetDays.value = Math.round(dragStartOffset.value - deltaX * daysPerPixel)
}

function onMouseUp() {
  isDragging.value = false
}

// Tooltip handlers
function showSegmentTooltip(
  e: MouseEvent,
  seg: TimelineSegment,
  band?: PolicyTimelineBand
) {
  const rect = svgContainerRef.value?.getBoundingClientRect()
  const x = e.clientX - (rect?.left || 0)
  const y = e.clientY - (rect?.top || 0)

  let title = seg.policy_name || band?.product_name || '保单'
  let typeStr = '保障生效'
  if (seg.segment_type === 'waiting') typeStr = '等待期'
  if (seg.segment_type === 'gap') typeStr = '断保空档'

  hoverInfo.value = {
    visible: true,
    x,
    y: Math.max(10, y - 60),
    title,
    insurer: band?.insurer,
    dates: `${seg.start_date} 至 ${seg.end_date}`,
    type: typeStr,
    policyId: seg.policy_id || band?.policy_id
  }
}

function hideTooltip() {
  if (hoverInfo.value) {
    hoverInfo.value.visible = false
  }
}

function onSegmentClick(policyId?: string) {
  if (policyId) {
    router.push(`/policies/${policyId}`)
  }
}

onMounted(() => {
  window.addEventListener('mouseup', onMouseUp)
  window.addEventListener('mousemove', onMouseMove)

  const animatedBefore = sessionStorage.getItem('pb_timeline_animated')
  if (!animatedBefore) {
    isAnimating.value = true
    setTimeout(() => {
      isAnimating.value = false
      hasAnimated.value = true
      sessionStorage.setItem('pb_timeline_animated', '1')
    }, 800)
  } else {
    hasAnimated.value = true
  }
})

onUnmounted(() => {
  window.removeEventListener('mouseup', onMouseUp)
  window.removeEventListener('mousemove', onMouseMove)
})
</script>

<template>
  <div class="timeline-widget glass">
    <!-- Toolbar -->
    <div class="timeline-toolbar">
      <div class="toolbar-title-group">
        <span class="toolbar-title">保障时间轴</span>
        <span class="timeline-hint">（可左右拖动平移）</span>
      </div>

      <div class="toolbar-controls">
        <!-- Zoom Buttons -->
        <div class="zoom-btn-group">
          <button
            class="zoom-btn"
            :class="{ active: zoomMonths === 12 }"
            @click="setZoom(12)"
          >
            1 年
          </button>
          <button
            class="zoom-btn"
            :class="{ active: zoomMonths === 24 }"
            @click="setZoom(24)"
          >
            2 年
          </button>
          <button
            class="zoom-btn"
            :class="{ active: zoomMonths === 36 }"
            @click="setZoom(36)"
          >
            3 年
          </button>
        </div>

        <button class="icon-tool-btn" @click="resetView" title="重置视野至今天">
          <RotateCcw :size="14" />
        </button>

        <!-- Legend -->
        <div class="legend-group">
          <div class="legend-item">
            <span class="legend-box legend-box--effective"></span>
            <span>生效中</span>
          </div>
          <div class="legend-item">
            <span class="legend-box legend-box--waiting"></span>
            <span>等待期</span>
          </div>
          <div class="legend-item">
            <span class="legend-box legend-box--gap"></span>
            <span>断保空档</span>
          </div>
        </div>
      </div>
    </div>

    <!-- SVG Container -->
    <div
      ref="svgContainerRef"
      class="svg-scroll-container"
      :class="{ grabbing: isDragging }"
      @mousedown="onMouseDown"
    >
      <svg
        :viewBox="`0 0 ${SVG_WIDTH} ${svgHeight}`"
        class="timeline-svg"
        preserveAspectRatio="xMidYMid meet"
      >
        <defs>
          <!-- Waiting period hatch pattern -->
          <pattern
            id="hatch-waiting"
            width="8"
            height="8"
            patternTransform="rotate(45 0 0)"
            patternUnits="userSpaceOnUse"
          >
            <line x1="0" y1="0" x2="0" y2="8" stroke="currentColor" stroke-width="2.5" opacity="0.45" />
          </pattern>
        </defs>

        <!-- Time Ticks & Grid Background -->
        <g class="grid-group">
          <!-- Time line axis -->
          <line
            :x1="PADDING_LEFT"
            :y1="HEADER_HEIGHT - 6"
            :x2="PADDING_LEFT + CHART_WIDTH"
            :y2="HEADER_HEIGHT - 6"
            stroke="var(--glass-stroke)"
            stroke-width="1"
          />

          <!-- Tick lines and labels -->
          <g v-for="(tick, idx) in timeTicks" :key="idx">
            <line
              :x1="tick.x"
              :y1="HEADER_HEIGHT - 10"
              :x2="tick.x"
              :y2="svgHeight - 15"
              stroke="var(--glass-stroke)"
              :stroke-dasharray="tick.isYear ? 'none' : '3 3'"
              :stroke-width="tick.isYear ? 1.2 : 0.8"
              :opacity="tick.isYear ? 0.8 : 0.4"
            />
            <text
              :x="tick.x"
              :y="HEADER_HEIGHT - 16"
              text-anchor="middle"
              :class="['axis-text', tick.isYear ? 'axis-text--year' : '']"
            >
              {{ tick.label }}
            </text>
          </g>
        </g>

        <!-- Member Rows -->
        <g
          v-for="(member, mIdx) in timelines"
          :key="member.member_id"
          class="member-row"
          :transform="`translate(0, ${HEADER_HEIGHT + mIdx * ROW_HEIGHT})`"
        >
          <!-- Row background light strip -->
          <rect
            :x="10"
            :y="4"
            :width="SVG_WIDTH - 20"
            :height="ROW_HEIGHT - 8"
            rx="6"
            fill="var(--glass-fill-strong)"
            opacity="0.3"
          />

          <!-- Member Label Column -->
          <g class="member-label" :transform="`translate(20, ${ROW_HEIGHT / 2})`">
            <!-- Avatar circle -->
            <circle
              cx="14"
              cy="0"
              r="12"
              :fill="member.member_color || '#2A8F82'"
            />
            <text
              x="14"
              y="4"
              text-anchor="middle"
              fill="#fff"
              font-size="11"
              font-weight="bold"
            >
              {{ member.member_name.slice(0, 1) }}
            </text>
            <text
              x="36"
              y="1"
              dominant-baseline="central"
              class="member-name-text"
            >
              {{ member.member_name }}
            </text>
            <text
              x="36"
              y="16"
              dominant-baseline="central"
              class="member-relation-text"
            >
              {{ member.relation }}
            </text>
          </g>

          <!-- Policy Bands -->
          <g
            v-for="(band, bIdx) in member.bands"
            :key="band.policy_id"
            :class="['band-group', { 'anim-grow': isAnimating }]"
            :style="{
              animationDelay: `${mIdx * 60}ms`,
              transformOrigin: `${PADDING_LEFT}px 0px`
            }"
          >
            <!-- Segments within policy -->
            <g v-for="(seg, sIdx) in band.segments" :key="sIdx">
              <!-- Effective or Waiting bar -->
              <template v-if="seg.segment_type === 'effective'">
                <rect
                  v-for="rect in [segRect(seg.start_date, seg.end_date)]"
                  v-show="rect.visible"
                  :key="'eff-' + sIdx"
                  :x="rect.x"
                  :y="(ROW_HEIGHT - BAND_HEIGHT) / 2"
                  :width="rect.width"
                  :height="BAND_HEIGHT"
                  rx="4"
                  :fill="member.member_color || '#2A8F82'"
                  class="segment-rect segment-rect--clickable"
                  @mouseenter="showSegmentTooltip($event, seg, band)"
                  @mouseleave="hideTooltip"
                  @click="onSegmentClick(seg.policy_id)"
                />
              </template>

              <!-- Waiting period (with hatch) -->
              <g v-else-if="seg.segment_type === 'waiting'">
                <template v-for="rect in [segRect(seg.start_date, seg.end_date)]" :key="'wait-' + sIdx">
                  <rect
                    v-show="rect.visible"
                    :x="rect.x"
                    :y="(ROW_HEIGHT - BAND_HEIGHT) / 2"
                    :width="rect.width"
                    :height="BAND_HEIGHT"
                    rx="4"
                    :fill="member.member_color || '#2A8F82'"
                    opacity="0.35"
                  />
                  <rect
                    v-show="rect.visible"
                    :x="rect.x"
                    :y="(ROW_HEIGHT - BAND_HEIGHT) / 2"
                    :width="rect.width"
                    :height="BAND_HEIGHT"
                    rx="4"
                    fill="url(#hatch-waiting)"
                    style="color: #fff;"
                    class="segment-rect segment-rect--clickable"
                    @mouseenter="showSegmentTooltip($event, seg, band)"
                    @mouseleave="hideTooltip"
                    @click="onSegmentClick(seg.policy_id)"
                  />
                </template>
              </g>
            </g>
          </g>

          <!-- Gap Segments (Red Dashed Box) -->
          <g v-if="member.gap_segments && member.gap_segments.length > 0">
            <g v-for="(gap, gIdx) in member.gap_segments" :key="gIdx">
              <template v-for="rect in [segRect(gap.start_date, gap.end_date, 14)]" :key="gIdx">
                <rect
                  v-show="rect.visible"
                  :x="rect.x"
                  :y="(ROW_HEIGHT - GAP_HEIGHT) / 2"
                  :width="rect.width"
                  :height="GAP_HEIGHT"
                  rx="3"
                  class="gap-rect"
                  @mouseenter="showSegmentTooltip($event, gap)"
                  @mouseleave="hideTooltip"
                />
                <text
                  v-show="rect.visible"
                  :x="rect.x + rect.width / 2"
                  :y="ROW_HEIGHT / 2"
                  dominant-baseline="central"
                  text-anchor="middle"
                  class="gap-label-text"
                >
                  空档
                </text>
              </template>
            </g>
          </g>
        </g>

        <!-- "Today" Line & Marker -->
        <g v-if="isTodayVisible" class="today-marker">
          <line
            :x1="todayX"
            :y1="HEADER_HEIGHT - 12"
            :x2="todayX"
            :y2="svgHeight - 10"
            stroke="var(--danger, #C8443B)"
            stroke-width="2"
            stroke-dasharray="4 2"
          />
          <!-- Badge -->
          <rect
            :x="todayX - 18"
            :y="HEADER_HEIGHT - 28"
            width="36"
            height="18"
            rx="9"
            fill="var(--danger, #C8443B)"
          />
          <text
            :x="todayX"
            :y="HEADER_HEIGHT - 16"
            text-anchor="middle"
            fill="#fff"
            font-size="10"
            font-weight="bold"
          >
            今天
          </text>
        </g>
      </svg>

      <!-- Floating Tooltip -->
      <div
        v-if="hoverInfo && hoverInfo.visible"
        class="timeline-tooltip glass"
        :style="{ left: `${hoverInfo.x}px`, top: `${hoverInfo.y}px` }"
      >
        <div class="tooltip-header">
          <span class="tooltip-title">{{ hoverInfo.title }}</span>
          <span
            :class="[
              'tooltip-tag',
              hoverInfo.type === '断保空档' ? 'tooltip-tag--danger' : 'tooltip-tag--ok'
            ]"
          >
            {{ hoverInfo.type }}
          </span>
        </div>
        <div v-if="hoverInfo.insurer" class="tooltip-row">
          <span class="tooltip-muted">保司：</span>{{ hoverInfo.insurer }}
        </div>
        <div class="tooltip-row">
          <span class="tooltip-muted">时间：</span>{{ hoverInfo.dates }}
        </div>
        <div v-if="hoverInfo.policyId" class="tooltip-hint">
          点击进入保单详情
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.timeline-widget {
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  position: relative;
  overflow: hidden;
}

.timeline-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-3);
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--glass-stroke);
}

.toolbar-title-group {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
}

.toolbar-title {
  font-size: var(--fs-19);
  font-weight: 700;
}

.timeline-hint {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.toolbar-controls {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
}

.zoom-btn-group {
  display: flex;
  background: var(--glass-fill-strong);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  padding: 2px;
}

.zoom-btn {
  padding: 4px 10px;
  font-size: var(--fs-12);
  background: transparent;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  color: var(--text-muted);
  transition: all 0.15s ease;
}

.zoom-btn.active {
  background: var(--ok);
  color: #fff;
  font-weight: 600;
}

.icon-tool-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 1px solid var(--glass-stroke);
  background: var(--glass-fill-strong);
  cursor: pointer;
  color: var(--text-muted);
}

.icon-tool-btn:hover {
  color: var(--ok);
  border-color: var(--ok);
}

.legend-group {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.legend-box {
  width: 14px;
  height: 8px;
  border-radius: 2px;
}

.legend-box--effective {
  background: var(--ok);
}

.legend-box--waiting {
  background: repeating-linear-gradient(
    45deg,
    color-mix(in oklch, var(--ok) 40%, transparent),
    color-mix(in oklch, var(--ok) 40%, transparent) 3px,
    var(--ok) 3px,
    var(--ok) 6px
  );
}

.legend-box--gap {
  border: 1.5px dashed var(--danger);
  background: color-mix(in oklch, var(--danger) 15%, transparent);
}

.svg-scroll-container {
  position: relative;
  width: 100%;
  overflow-x: auto;
  cursor: grab;
  user-select: none;
}

.svg-scroll-container.grabbing {
  cursor: grabbing;
}

.timeline-svg {
  width: 100%;
  min-width: 650px;
  display: block;
}

.axis-text {
  font-size: 10px;
  fill: var(--text-muted);
}

.axis-text--year {
  font-size: 11px;
  font-weight: bold;
  fill: var(--text);
}

.member-name-text {
  font-size: 13px;
  font-weight: 600;
  fill: var(--text);
}

.member-relation-text {
  font-size: 10px;
  fill: var(--text-muted);
}

.segment-rect {
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.segment-rect:hover {
  opacity: 0.85;
  filter: drop-shadow(0 0 4px rgba(42, 143, 130, 0.4));
}

.gap-rect {
  fill: rgba(200, 68, 59, 0.12);
  stroke: var(--danger, #C8443B);
  stroke-width: 1.5;
  stroke-dasharray: 4 2;
  cursor: pointer;
}

.gap-label-text {
  font-size: 10px;
  font-weight: 700;
  fill: var(--danger, #C8443B);
  pointer-events: none;
}

/* DEV-GUIDE 7.7: 首次加载时色带自左向右绘制一次，时长 480ms，按成员错开 60ms */
@keyframes timelineGrow {
  0% {
    transform: scaleX(0);
    opacity: 0.2;
  }
  100% {
    transform: scaleX(1);
    opacity: 1;
  }
}

.anim-grow {
  animation: timelineGrow 480ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
}

/* Tooltip */
.timeline-tooltip {
  position: absolute;
  pointer-events: none;
  z-index: 100;
  padding: 8px 12px;
  border-radius: var(--r-control);
  background: var(--glass-fill-strong);
  backdrop-filter: blur(12px);
  border: 1px solid var(--glass-stroke);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 160px;
  transform: translate(-50%, -100%);
  transition: opacity 0.1s ease;
}

.tooltip-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.tooltip-title {
  font-size: var(--fs-12);
  font-weight: bold;
  color: var(--text);
}

.tooltip-tag {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
}

.tooltip-tag--ok {
  background: color-mix(in oklch, var(--ok) 15%, transparent);
  color: var(--ok);
}

.tooltip-tag--danger {
  background: color-mix(in oklch, var(--danger) 15%, transparent);
  color: var(--danger);
}

.tooltip-row {
  font-size: var(--fs-12);
  color: var(--text);
}

.tooltip-muted {
  color: var(--text-muted);
}

.tooltip-hint {
  font-size: 10px;
  color: var(--ok);
  margin-top: 2px;
  font-style: italic;
}

/* Responsive */
@media (max-width: 768px) {
  .timeline-toolbar {
    flex-direction: column;
    align-items: flex-start;
  }
  .toolbar-controls {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
