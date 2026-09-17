<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  ShieldCheck,
  ShieldAlert,
  Clock,
  Coins,
  AlertTriangle,
  FileCheck,
  Calendar,
  HelpCircle,
  Calculator,
  PlusCircle,
  ChevronRight,
  ArrowUpRight,
  CheckCircle2
} from 'lucide-vue-next'
import SvgTimeline from '@/components/timeline/SvgTimeline.vue'

interface OverviewMetrics {
  total_annual_premium_cents: number
  total_annual_premium_yuan: number
  active_policy_count: number
  expiring_30d_count: number
  gap_member_count: number
}

interface TodoItem {
  id: string
  kind: string
  title: string
  description: string
  link: string
  severity: 'info' | 'warning' | 'urgent'
  date?: string
}

interface MemberTimeline {
  member_id: string
  member_name: string
  member_color: string
  relation: string
  has_gap: boolean
  bands: any[]
  gap_segments?: any[]
}

const router = useRouter()

const loading = ref(true)
const metrics = ref<OverviewMetrics>({
  total_annual_premium_cents: 0,
  total_annual_premium_yuan: 0,
  active_policy_count: 0,
  expiring_30d_count: 0,
  gap_member_count: 0
})
const timelines = ref<MemberTimeline[]>([])
const todos = ref<TodoItem[]>([])
const todayStr = ref('')

async function fetchOverviewData() {
  loading.value = true
  try {
    const res = await fetch('/api/overview')
    if (res.ok) {
      const data = await res.json()
      metrics.value = data.metrics
      timelines.value = data.timeline
      todos.value = data.todos
      todayStr.value = data.today
    }
  } catch (err) {
    console.error('Failed to load overview data:', err)
  } finally {
    loading.value = false
  }
}

function handleTodoClick(todo: TodoItem) {
  if (todo.link) {
    router.push(todo.link)
  }
}

onMounted(() => {
  fetchOverviewData()
})
</script>

<template>
  <div class="overview-page">
    <header class="page-header">
      <div class="header-content">
        <h1 class="page-title">全家保障大盘</h1>
        <p class="page-subtitle">动态跟踪家庭保单生效状态、到期预警与断保空档</p>
      </div>
    </header>

    <!-- 4 核心指标：合并为单个玻璃面板，内部以分隔线区分 (同屏最多 3 个玻璃大面板) -->
    <section class="glass metrics-grid">
      <!-- 1. 年保费合计 -->
      <div class="metric-card">
        <div class="metric-icon metric-icon--teal">
          <Coins :size="22" />
        </div>
        <div class="metric-info">
          <span class="metric-label">全家年保费合计</span>
          <div class="metric-value-row">
            <span class="metric-value num">¥{{ metrics.total_annual_premium_yuan.toLocaleString() }}</span>
            <span class="metric-unit">元/年</span>
          </div>
        </div>
      </div>

      <!-- 2. 生效保单 -->
      <div class="metric-card">
        <div class="metric-icon metric-icon--teal">
          <ShieldCheck :size="22" />
        </div>
        <div class="metric-info">
          <span class="metric-label">当前生效保单</span>
          <div class="metric-value-row">
            <span class="metric-value num">{{ metrics.active_policy_count }}</span>
            <span class="metric-unit">份</span>
          </div>
        </div>
      </div>

      <!-- 3. 30天内到期 -->
      <div class="metric-card">
        <div
          class="metric-icon"
          :class="metrics.expiring_30d_count > 0 ? 'metric-icon--amber' : 'metric-icon--subtle'"
        >
          <Clock :size="22" />
        </div>
        <div class="metric-info">
          <span class="metric-label">30 天内到期</span>
          <div class="metric-value-row">
            <span
              class="metric-value num"
              :class="{ 'text-warning': metrics.expiring_30d_count > 0 }"
            >
              {{ metrics.expiring_30d_count }}
            </span>
            <span class="metric-unit">份</span>
          </div>
        </div>
      </div>

      <!-- 4. 有空档成员 -->
      <div class="metric-card">
        <div
          class="metric-icon"
          :class="metrics.gap_member_count > 0 ? 'metric-icon--danger' : 'metric-icon--subtle'"
        >
          <ShieldAlert :size="22" />
        </div>
        <div class="metric-info">
          <span class="metric-label">断保空档预警</span>
          <div class="metric-value-row">
            <span
              class="metric-value num"
              :class="{ 'text-danger': metrics.gap_member_count > 0 }"
            >
              {{ metrics.gap_member_count }}
            </span>
            <span class="metric-unit">人存在空档</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 自研 SVG 保障时间轴 (DEV-GUIDE 7.7) -->
    <section class="timeline-section">
      <SvgTimeline
        v-if="!loading && timelines.length > 0"
        :timelines="timelines"
        :today-str="todayStr"
      />
      <div v-else-if="loading" class="glass loading-placeholder">
        <div class="spinner"></div>
        <span>正在加载家庭保障时间轴...</span>
      </div>
      <div v-else class="glass empty-placeholder">
        <ShieldCheck :size="40" class="text-muted" />
        <p>暂无保单记录，请先在下方快捷入口上传保单建档。</p>
      </div>
    </section>

    <!-- 待办清单与快捷操作栏：合并为单个玻璃面板，内部以分隔线区分两个区块 -->
    <div class="glass content-split">
      <!-- 待办列表 -->
      <div class="todos-card">
        <div class="card-header">
          <div class="header-left">
            <AlertTriangle :size="18" class="text-warning" />
            <h3 class="card-title">待处理事项</h3>
          </div>
          <span class="todo-count">{{ todos.length }} 项待办</span>
        </div>

        <div v-if="todos.length > 0" class="todos-list">
          <div
            v-for="todo in todos"
            :key="todo.id"
            class="todo-item"
            :class="`todo-item--${todo.severity}`"
            role="button"
            tabindex="0"
            @click="handleTodoClick(todo)"
            @keydown.enter="handleTodoClick(todo)"
            @keydown.space.prevent="handleTodoClick(todo)"
          >
            <div class="todo-main">
              <div class="todo-title-row">
                <span class="todo-title">{{ todo.title }}</span>
                <span v-if="todo.date" class="todo-date">{{ todo.date }}</span>
              </div>
              <p class="todo-desc">{{ todo.description }}</p>
            </div>
            <ChevronRight :size="16" class="todo-arrow" />
          </div>
        </div>

        <div v-else class="todos-empty">
          <CheckCircle2 :size="28" class="text-ok" />
          <p>家庭保单状态良好，暂无待核对或紧急到期待办。</p>
        </div>
      </div>

      <!-- 快捷入口 (DEV-GUIDE 7.7) -->
      <div class="quick-actions-card">
        <div class="card-header">
          <h3 class="card-title">快捷入口</h3>
        </div>

        <div class="quick-actions-list">
          <router-link to="/import" class="quick-action-btn action-import">
            <div class="action-icon">
              <PlusCircle :size="20" />
            </div>
            <div class="action-text">
              <span class="action-name">上传保单建档</span>
              <span class="action-hint">扫描件/电子保单 OCR 脱敏入库</span>
            </div>
            <ArrowUpRight :size="16" class="action-arrow" />
          </router-link>

          <router-link to="/ask" class="quick-action-btn action-ask">
            <div class="action-icon">
              <HelpCircle :size="20" />
            </div>
            <div class="action-text">
              <span class="action-name">问一个条款问题</span>
              <span class="action-hint">基于精准原文比对的智能条款解答</span>
            </div>
            <ArrowUpRight :size="16" class="action-arrow" />
          </router-link>

          <router-link to="/claim" class="quick-action-btn action-claim">
            <div class="action-icon">
              <Calculator :size="20" />
            </div>
            <div class="action-text">
              <span class="action-name">估算一次理赔</span>
              <span class="action-hint">确定性纯代码计算费用瀑布与报销额</span>
            </div>
            <ArrowUpRight :size="16" class="action-arrow" />
          </router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overview-page {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.page-header {
  margin-bottom: var(--sp-1);
}

.page-title {
  font-size: var(--fs-28);
  font-weight: 700;
  margin: 0;
}

.page-subtitle {
  font-size: var(--fs-14);
  color: var(--text-muted);
  margin-top: 4px;
}

/* 4 Metrics Grid：单个玻璃面板，内部用分隔线区分 4 个指标 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
}

.metric-card {
  padding: var(--sp-4);
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  border-right: 1px solid var(--glass-stroke);
}

.metric-card:last-child {
  border-right: none;
}

.metric-icon {
  width: 46px;
  height: 46px;
  border-radius: var(--r-control);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.metric-icon--teal {
  background: color-mix(in oklch, var(--ok) 15%, transparent);
  color: var(--ok);
}

.metric-icon--amber {
  background: color-mix(in oklch, var(--accent) 15%, transparent);
  color: var(--accent);
}

.metric-icon--danger {
  background: color-mix(in oklch, var(--danger) 15%, transparent);
  color: var(--danger);
}

.metric-icon--subtle {
  background: var(--glass-fill-strong);
  color: var(--text-muted);
}

.metric-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.metric-label {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.metric-value-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
}

.metric-value {
  font-size: var(--fs-23);
  font-weight: 700;
  color: var(--text);
}

.metric-unit {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.text-warning {
  color: var(--accent);
}

.text-danger {
  color: var(--danger);
}

/* Timeline Section */
.timeline-section {
  width: 100%;
}

.loading-placeholder,
.empty-placeholder {
  padding: var(--sp-7);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-3);
  text-align: center;
  color: var(--text-muted);
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--glass-stroke);
  border-top-color: var(--ok);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Split Section: Todos & Quick Actions：单个玻璃面板，内部用分隔线区分两栏 */
.content-split {
  display: grid;
  grid-template-columns: 1.2fr 0.8fr;
}

.todos-card {
  border-right: 1px solid var(--glass-stroke);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: var(--sp-3);
  border-bottom: 1px solid var(--glass-stroke);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  font-size: var(--fs-16);
  font-weight: 700;
  margin: 0;
}

.todo-count {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.todos-card,
.quick-actions-card {
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.todos-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.todo-item {
  padding: 10px 14px;
  border-radius: var(--r-control);
  background: var(--glass-fill-strong);
  border: 1px solid var(--glass-stroke);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  cursor: pointer;
  transition: all 0.15s ease;
}

.todo-item:hover {
  border-color: var(--ok);
  background: color-mix(in oklch, var(--ok) 5%, var(--glass-fill-strong));
}

.todo-item--urgent {
  border-left: 3px solid var(--danger);
}

.todo-item--warning {
  border-left: 3px solid var(--accent);
}

.todo-item--info {
  border-left: 3px solid var(--ok);
}

.todo-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
}

.todo-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.todo-title {
  font-size: var(--fs-12);
  font-weight: 600;
  color: var(--text);
}

.todo-date {
  font-size: 11px;
  color: var(--text-muted);
}

.todo-desc {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin: 0;
  line-height: 1.4;
}

.todo-arrow {
  color: var(--text-muted);
}

.todos-empty {
  padding: var(--sp-5);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  color: var(--text-muted);
  font-size: var(--fs-12);
}

/* Quick Actions List */
.quick-actions-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.quick-action-btn {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: 12px 14px;
  border-radius: var(--r-control);
  background: var(--glass-fill-strong);
  border: 1px solid var(--glass-stroke);
  text-decoration: none;
  color: inherit;
  transition: all 0.15s ease;
}

.quick-action-btn:hover {
  border-color: var(--ok);
  background: color-mix(in oklch, var(--ok) 5%, var(--glass-fill-strong));
}

.action-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.action-import .action-icon {
  background: color-mix(in oklch, var(--ok) 15%, transparent);
  color: var(--ok);
}

.action-ask .action-icon {
  background: color-mix(in oklch, var(--ai) 15%, transparent);
  color: var(--ai);
}

.action-claim .action-icon {
  background: color-mix(in oklch, var(--accent) 15%, transparent);
  color: var(--accent);
}

.action-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  flex: 1;
}

.action-name {
  font-size: var(--fs-14);
  font-weight: 600;
  color: var(--text);
}

.action-hint {
  font-size: 11px;
  color: var(--text-muted);
}

.action-arrow {
  color: var(--text-muted);
}

/* Responsive Breakpoints */
@media (max-width: 1024px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .metric-card {
    border-right: 1px solid var(--glass-stroke);
    border-bottom: 1px solid var(--glass-stroke);
  }
  .metric-card:nth-child(2n) {
    border-right: none;
  }
  .metric-card:nth-last-child(-n+2) {
    border-bottom: none;
  }
  .content-split {
    grid-template-columns: 1fr;
  }
  .todos-card {
    border-right: none;
    border-bottom: 1px solid var(--glass-stroke);
  }
}

@media (max-width: 600px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
  .metric-card {
    border-right: none;
    border-bottom: 1px solid var(--glass-stroke);
  }
  .metric-card:last-child {
    border-bottom: none;
  }
}
</style>
