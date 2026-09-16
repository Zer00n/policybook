<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  ShieldAlert,
  Sparkles,
  Send,
  FastForward,
  ChevronLeft,
  Calendar,
  User,
  Building,
  RotateCcw,
  CheckCircle,
  FileCheck,
  Search,
} from 'lucide-vue-next'
import QuestionCard, { RenewalQuestion } from './QuestionCard.vue'
import RenewalProfileCard from './RenewalProfileCard.vue'
import RenewalReportView, { RenewalReportData } from './RenewalReportView.vue'

interface PolicyItem {
  id: string
  product_name: string
  insurer: string
  category: string
  expiry_date?: string
  premium_cents?: number
  insured_name?: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  structured_json?: string
  created_at: string
}

interface RenewalSession {
  id: string
  policy_id: string
  policy_name?: string
  insured_name?: string
  state: string
  profile: Record<string, any>
  current_questions: RenewalQuestion[]
  report?: RenewalReportData
  messages: ChatMessage[]
  created_at: string
  updated_at: string
}

const activeSession = ref<RenewalSession | null>(null)
const sessionsList = ref<RenewalSession[]>([])
const accidentPolicies = ref<PolicyItem[]>([])
const loading = ref(false)
const sending = ref(false)
const inputText = ref('')

async function fetchInitialData() {
  loading.value = true
  try {
    // 1. Fetch accident policies
    const polRes = await fetch('/api/policies')
    if (polRes.ok) {
      const data = await polRes.json()
      const list = Array.isArray(data) ? data : (data.items || data.policies || [])
      accidentPolicies.value = list.filter((p: any) => p.category === 'accident')
    }

    // 2. Fetch past renewal sessions
    const sessRes = await fetch('/api/renewal/sessions')
    if (sessRes.ok) {
      sessionsList.value = await sessRes.json()
      // If there are existing sessions, auto-load the most recent one
      if (sessionsList.value.length > 0 && !activeSession.value) {
        activeSession.value = sessionsList.value[0]
      }
    }
  } catch (err) {
    console.error('Failed to load initial data:', err)
  } finally {
    loading.value = false
  }
}

async function startNewSession(policyId: string) {
  loading.value = true
  try {
    const res = await fetch('/api/renewal/sessions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ policy_id: policyId }),
    })
    if (res.ok) {
      const newSession = await res.json()
      activeSession.value = newSession
      sessionsList.value.unshift(newSession)
    }
  } catch (err) {
    console.error('Failed to create renewal session:', err)
  } finally {
    loading.value = false
  }
}

async function selectSession(session: RenewalSession) {
  try {
    const res = await fetch(`/api/renewal/sessions/${session.id}`)
    if (res.ok) {
      activeSession.value = await res.json()
    } else {
      activeSession.value = session
    }
  } catch {
    activeSession.value = session
  }
}

async function handleSendMessage(options?: { answers?: Record<string, string>; skip?: boolean; customText?: string }) {
  if (!activeSession.value || sending.value) return

  const text = options?.customText ?? inputText.value.trim()
  if (!text && !options?.answers && !options?.skip) return

  sending.value = true
  try {
    const res = await fetch(`/api/renewal/sessions/${activeSession.value.id}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: text,
        answers: options?.answers,
        skip: options?.skip || false,
      }),
    })

    if (res.ok) {
      const updatedSession: RenewalSession = await res.json()
      activeSession.value = updatedSession
      inputText.value = ''
      // Update session in list
      const idx = sessionsList.value.findIndex(s => s.id === updatedSession.id)
      if (idx >= 0) sessionsList.value[idx] = updatedSession
    }
  } catch (err) {
    console.error('Failed to send renewal message:', err)
  } finally {
    sending.value = false
  }
}

function handleQuestionSubmit(answers: Record<string, string>) {
  handleSendMessage({ answers, customText: '已确认本轮维度回答' })
}

function handleSkipQuestions() {
  handleSendMessage({ skip: true, customText: '跳过其余追问，直接检索对比' })
}

onMounted(() => {
  fetchInitialData()
})
</script>

<template>
  <div class="renewal-page-container">
    <!-- Header -->
    <header class="page-header glass">
      <div class="header-left">
        <button
          v-if="activeSession"
          type="button"
          class="btn-back"
          @click="activeSession = null"
        >
          <ChevronLeft :size="16" />
          <span>切换保单</span>
        </button>
        <div class="header-titles">
          <div class="title-with-badge">
            <h1 class="page-title">意外险续保顾问 Agent</h1>
            <span class="badge-agent">F09 续保顾问</span>
          </div>
          <p class="header-desc">
            基于家庭保单基线，在官方白名单与防编造约束下，受控追问需求并对齐条款对比。
          </p>
        </div>
      </div>

      <div v-if="activeSession" class="header-right">
        <span class="baseline-badge">
          基线：{{ activeSession.policy_name || '未命名保单' }}
        </span>
      </div>
    </header>

    <!-- State 1: Session Selector (when no active session) -->
    <div v-if="!activeSession" class="selector-view">
      <div class="selector-grid">
        <!-- Accident policies to start -->
        <div class="selector-panel glass">
          <div class="panel-header">
            <ShieldAlert :size="18" class="panel-icon" />
            <h2 class="panel-title">选择需续保规划的意外险保单</h2>
          </div>
          <div v-if="accidentPolicies.length === 0" class="empty-box">
            暂无已录入的意外险保单，请先在保单库录入保单。
          </div>
          <div v-else class="policies-list">
            <div
              v-for="pol in accidentPolicies"
              :key="pol.id"
              class="policy-card"
            >
              <div class="pol-main">
                <div class="pol-name">{{ pol.product_name }}</div>
                <div class="pol-meta">
                  <span>{{ pol.insurer }}</span>
                  <span v-if="pol.expiry_date">到期日: {{ pol.expiry_date }}</span>
                </div>
              </div>
              <button
                type="button"
                class="btn-start"
                :disabled="loading"
                @click="startNewSession(pol.id)"
              >
                <Sparkles :size="14" />
                <span>发起续保规划</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Historical renewal sessions -->
        <div class="selector-panel glass">
          <div class="panel-header">
            <FileCheck :size="18" class="panel-icon-celadon" />
            <h2 class="panel-title">历史续保规划记录 ({{ sessionsList.length }})</h2>
          </div>
          <div v-if="sessionsList.length === 0" class="empty-box">
            暂无历史规划记录，点击左侧保单即可开始。
          </div>
          <div v-else class="sessions-list">
            <div
              v-for="s in sessionsList"
              :key="s.id"
              class="session-history-item"
              @click="selectSession(s)"
            >
              <div class="sess-info">
                <div class="sess-name">{{ s.policy_name || '意外险规划' }}</div>
                <div class="sess-meta">
                  <span class="sess-state">{{ s.state }}</span>
                  <span>{{ s.created_at.slice(0, 10) }}</span>
                </div>
              </div>
              <span class="btn-enter">继续查看 &gt;</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- State 2: Active Session View -->
    <div v-else class="active-session-layout">
      <!-- Main Left Column: Conversation, Questions, and Report -->
      <main class="chat-main-column">
        <!-- Messages Stream -->
        <div class="messages-stream">
          <div
            v-for="msg in activeSession.messages"
            :key="msg.id"
            class="message-row"
            :class="msg.role"
          >
            <div class="msg-avatar">
              <span v-if="msg.role === 'assistant'">AI</span>
              <span v-else>我</span>
            </div>

            <div class="msg-bubble glass">
              <div class="msg-content">{{ msg.content }}</div>
            </div>
          </div>
        </div>

        <!-- Question Card (when in ASK_USER) -->
        <QuestionCard
          v-if="activeSession.state === 'ASK_USER' && activeSession.current_questions.length > 0"
          :questions="activeSession.current_questions"
          :submitting="sending"
          @submit="handleQuestionSubmit"
          @skip="handleSkipQuestions"
        />

        <!-- Renewal Report View (when report is ready) -->
        <RenewalReportView
          v-if="activeSession.report"
          :report="activeSession.report"
        />

        <!-- Input Bar (when session is in progress) -->
        <div
          v-if="activeSession.state !== 'END'"
          class="chat-input-bar glass"
        >
          <!-- Quick Chips -->
          <div class="quick-chips">
            <button
              type="button"
              class="chip-btn"
              @click="inputText = '今年出差比较频繁，主要坐高铁和飞机，希望加强交通额外赔'"
            >
              出差较多(高铁/飞机)
            </button>
            <button
              type="button"
              class="chip-btn"
              @click="inputText = '经常加班，特别关注猝死保障'"
            >
              经常加班需要猝死
            </button>
            <button
              type="button"
              class="chip-btn"
              @click="inputText = '今年工作生活无明显变化，想看看性价比更高的方案'"
            >
              无变化，看更高性价比
            </button>
            <button
              type="button"
              class="chip-btn chip-skip"
              @click="handleSkipQuestions"
            >
              <FastForward :size="12" />
              <span>跳过追问直接对比</span>
            </button>
          </div>

          <div class="input-row">
            <textarea
              v-model="inputText"
              class="text-input"
              rows="2"
              placeholder="请描述您今年的工作生活变化，或直接回答上述问题..."
              :disabled="sending"
              @keydown.enter.prevent="handleSendMessage()"
            ></textarea>
            <button
              type="button"
              class="btn-send"
              :disabled="sending || !inputText.trim()"
              @click="handleSendMessage()"
            >
              <Send :size="16" />
              <span>发送</span>
            </button>
          </div>
        </div>
      </main>

      <!-- Sidebar Right Column: Baseline Summary & Profile -->
      <aside class="sidebar-column">
        <!-- Baseline Summary Card -->
        <div class="baseline-card glass">
          <div class="sidebar-header">
            <ShieldAlert :size="16" class="sidebar-icon" />
            <span class="sidebar-title">基线保单信息</span>
          </div>
          <div class="baseline-details">
            <div class="detail-row">
              <span class="row-label">产品名称:</span>
              <span class="row-val">{{ activeSession.policy_name || '意外险' }}</span>
            </div>
            <div v-if="activeSession.insured_name" class="detail-row">
              <span class="row-label">被保险人:</span>
              <span class="row-val">{{ activeSession.insured_name }}</span>
            </div>
            <div class="detail-row">
              <span class="row-label">会话状态:</span>
              <span class="row-val status-tag">{{ activeSession.state }}</span>
            </div>
          </div>
        </div>

        <!-- Real-time Profile Card -->
        <RenewalProfileCard
          :profile="activeSession.profile"
          :current-state="activeSession.state"
        />

        <!-- Secondary Actions Card -->
        <div class="actions-card glass">
          <button
            type="button"
            class="action-item-btn"
            @click="activeSession = null"
          >
            <RotateCcw :size="14" />
            <span>规划其他保单</span>
          </button>
          <button
            v-if="activeSession.state !== 'END'"
            type="button"
            class="action-item-btn action-skip"
            @click="handleSkipQuestions"
          >
            <FastForward :size="14" />
            <span>跳过追问直接检索对比</span>
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.renewal-page-container {
  padding: var(--sp-5);
  max-width: 1400px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.page-header {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-panel);
  padding: var(--sp-4) var(--sp-5);
  backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--glass-shadow);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--sp-4);
}

.btn-back {
  display: flex;
  align-items: center;
  gap: 4px;
  background: color-mix(in oklch, var(--text) 5%, transparent);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-control);
  padding: 6px 12px;
  font-size: var(--fs-13);
  color: var(--text);
  cursor: pointer;
}

.btn-back:hover {
  background: color-mix(in oklch, var(--text) 10%, transparent);
}

.header-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.title-with-badge {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.page-title {
  margin: 0;
  font-size: var(--fs-18);
  font-weight: 700;
  color: var(--text);
}

.badge-agent {
  font-size: 11px;
  background: var(--c-celadon);
  color: white;
  padding: 2px 8px;
  border-radius: var(--rad-control);
  font-weight: 600;
}

.header-desc {
  margin: 0;
  font-size: var(--fs-13);
  color: var(--text-muted);
}

.baseline-badge {
  font-size: var(--fs-13);
  font-weight: 600;
  color: var(--c-apricot);
  background: color-mix(in oklch, var(--c-apricot) 12%, transparent);
  padding: 4px 12px;
  border-radius: var(--rad-control);
}

/* Selector Grid */
.selector-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-4);
}

.selector-panel {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-panel);
  padding: var(--sp-5);
  backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--glass-shadow);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.panel-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  border-bottom: 1px solid var(--glass-stroke);
  padding-bottom: var(--sp-3);
}

.panel-icon {
  color: var(--c-apricot);
}

.panel-icon-celadon {
  color: var(--c-celadon);
}

.panel-title {
  margin: 0;
  font-size: var(--fs-16);
  font-weight: 600;
  color: var(--text);
}

.empty-box {
  padding: var(--sp-6);
  text-align: center;
  color: var(--text-muted);
  font-size: var(--fs-14);
}

.policies-list,
.sessions-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.policy-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-3) var(--sp-4);
  background: color-mix(in oklch, var(--text) 3%, transparent);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-control);
}

.pol-name {
  font-weight: 600;
  font-size: var(--fs-14);
  color: var(--text);
  margin-bottom: 2px;
}

.pol-meta {
  display: flex;
  gap: var(--sp-3);
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.btn-start {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--c-celadon);
  color: white;
  border: none;
  border-radius: var(--rad-control);
  padding: 8px 14px;
  font-size: var(--fs-13);
  font-weight: 500;
  cursor: pointer;
}

.btn-start:hover:not(:disabled) {
  opacity: 0.9;
}

.session-history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--sp-3) var(--sp-4);
  background: color-mix(in oklch, var(--text) 3%, transparent);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-control);
  cursor: pointer;
  transition: background 0.15s ease;
}

.session-history-item:hover {
  background: color-mix(in oklch, var(--c-celadon) 8%, transparent);
}

.sess-name {
  font-weight: 600;
  font-size: var(--fs-14);
  color: var(--text);
  margin-bottom: 2px;
}

.sess-meta {
  display: flex;
  gap: var(--sp-2);
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.sess-state {
  color: var(--c-celadon);
  font-weight: 600;
}

.btn-enter {
  font-size: var(--fs-12);
  color: var(--c-celadon);
  font-weight: 600;
}

/* Active Session Layout */
.active-session-layout {
  display: grid;
  grid-template-columns: 1fr 340px;
  gap: var(--sp-4);
  align-items: start;
}

.chat-main-column {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.messages-stream {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.message-row {
  display: flex;
  gap: var(--sp-3);
  max-width: 88%;
}

.message-row.assistant {
  align-self: flex-start;
}

.message-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  flex-shrink: 0;
}

.message-row.assistant .msg-avatar {
  background: var(--c-dusk);
  color: white;
}

.message-row.user .msg-avatar {
  background: var(--c-celadon);
  color: white;
}

.msg-bubble {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-control);
  padding: var(--sp-3) var(--sp-4);
  backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--glass-shadow);
}

.message-row.assistant .msg-bubble {
  border-left: 3px solid var(--c-dusk);
}

.message-row.user .msg-bubble {
  background: color-mix(in oklch, var(--c-celadon) 10%, white);
  border-color: var(--c-celadon);
}

.msg-content {
  font-size: var(--fs-14);
  line-height: 1.6;
  color: var(--text);
  white-space: pre-wrap;
}

/* Input Bar */
.chat-input-bar {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-panel);
  padding: var(--sp-3) var(--sp-4);
  backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--glass-shadow);
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.quick-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.chip-btn {
  background: color-mix(in oklch, var(--text) 4%, transparent);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-control);
  padding: 4px 10px;
  font-size: 11px;
  color: var(--text-muted);
  cursor: pointer;
}

.chip-btn:hover {
  background: color-mix(in oklch, var(--c-celadon) 12%, transparent);
  color: var(--c-celadon);
  border-color: var(--c-celadon);
}

.chip-skip {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--c-apricot);
  border-color: color-mix(in oklch, var(--c-apricot) 30%, transparent);
}

.chip-skip:hover {
  background: color-mix(in oklch, var(--c-apricot) 12%, transparent);
  color: var(--c-apricot);
  border-color: var(--c-apricot);
}

.input-row {
  display: flex;
  gap: var(--sp-2);
  align-items: flex-end;
}

.text-input {
  flex: 1;
  background: color-mix(in oklch, white 80%, transparent);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-control);
  padding: 8px 12px;
  font-family: var(--font-ui);
  font-size: var(--fs-14);
  color: var(--text);
  resize: none;
  outline: none;
}

.text-input:focus {
  border-color: var(--c-celadon);
}

.btn-send {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--c-celadon);
  color: white;
  border: none;
  border-radius: var(--rad-control);
  padding: 10px 18px;
  font-size: var(--fs-13);
  font-weight: 500;
  cursor: pointer;
  height: fit-content;
}

.btn-send:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Sidebar Column */
.sidebar-column {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.baseline-card,
.actions-card {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-panel);
  padding: var(--sp-4);
  backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--glass-shadow);
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  border-bottom: 1px solid var(--glass-stroke);
  padding-bottom: var(--sp-2);
  margin-bottom: var(--sp-3);
}

.sidebar-icon {
  color: var(--c-apricot);
}

.sidebar-title {
  font-weight: 600;
  font-size: var(--fs-13);
  color: var(--text);
}

.baseline-details {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
  font-size: var(--fs-12);
}

.detail-row {
  display: flex;
  justify-content: space-between;
}

.row-label {
  color: var(--text-muted);
}

.row-val {
  font-weight: 600;
  color: var(--text);
}

.status-tag {
  color: var(--c-celadon);
}

.actions-card {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.action-item-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-control);
  padding: 8px 12px;
  font-size: var(--fs-12);
  color: var(--text);
  cursor: pointer;
}

.action-item-btn:hover {
  background: color-mix(in oklch, var(--text) 5%, transparent);
}

.action-skip {
  color: var(--c-apricot);
  border-color: color-mix(in oklch, var(--c-apricot) 30%, transparent);
}

/* Responsive adjustments */
@media (max-width: 960px) {
  .selector-grid {
    grid-template-columns: 1fr;
  }
  .active-session-layout {
    grid-template-columns: 1fr;
  }
  .sidebar-column {
    order: -1;
  }
}

@media (max-width: 600px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--sp-3);
  }
  .header-left {
    flex-direction: column;
    align-items: flex-start;
    gap: var(--sp-2);
  }
}
</style>
