<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  Send,
  Sparkles,
  HelpCircle,
  FileText,
  User,
  ShieldCheck,
  AlertTriangle,
  ExternalLink,
  ChevronRight,
  Info,
} from 'lucide-vue-next'
import DocViewer, { PageMeta, HighlightTarget } from '@/components/doc-viewer/DocViewer.vue'

interface Member {
  id: string
  display_name: string
  placeholder: string
  color: string
}

interface Policy {
  id: string
  product_name: string
  insurer: string
  category: string
  document_id?: string
}

interface Citation {
  document_id?: string
  policy_id?: string
  policy_name?: string
  page: number
  quote: string
  status: string
  rects: Array<{ x0: number; y0: number; x1: number; y1: number }>
}

interface QAAnswer {
  verdict: 'likely_covered' | 'likely_not_covered' | 'depends' | 'no_basis'
  verdict_label: string
  reasoning: string[]
  citations: Citation[]
  confirm_with_insurer: string[]
  disclaimer: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content?: string
  answer?: QAAnswer
  loading?: boolean
}

// 作用域选择
const scope = ref<'all' | 'member' | 'policy'>('all')
const selectedMemberId = ref<string>('')
const selectedPolicyId = ref<string>('')

const members = ref<Member[]>([])
const policies = ref<Policy[]>([])
const queryInput = ref('')
const isSubmitting = ref(false)

// 对话消息列表
const messages = ref<ChatMessage[]>([
  {
    id: 'welcome',
    role: 'assistant',
    content: '你好！我是保单簿的条款问答助手。你可以针对全家保单、指定成员或指定某张保单提问（例如：“门诊输液可以报销吗？”、“骨折手术怎么赔付？”）。所有回答均基于已录入的合同条款原文并进行严格引用核验。',
  },
])

// 原文阅读器抽屉
const drawerOpen = ref(false)
const drawerPages = ref<PageMeta[]>([])
const activeHighlight = ref<HighlightTarget | null>(null)
const drawerPolicyTitle = ref('')

onMounted(async () => {
  try {
    const [mRes, pRes] = await Promise.all([
      fetch('/api/members'),
      fetch('/api/policies'),
    ])
    if (mRes.ok) members.value = await mRes.json()
    if (pRes.ok) policies.value = await pRes.json()
  } catch (e) {
    console.error('Failed to load members or policies', e)
  }
})

// 快捷提问预设
const presetQuestions = [
  '意外摔伤导致的门诊和住院费用如何报销？',
  '因病住院微创手术有免赔额吗？赔付比例是多少？',
  '种植牙齿或牙齿正畸美容能用这份保险赔吗？',
  '猝死或者突发急性病在不在保障范围内？',
]

function applyPreset(q: string) {
  queryInput.value = q
}

async function handleSend() {
  const q = queryInput.value.trim()
  if (!q || isSubmitting.value) return

  const userMsgId = 'u_' + Date.now()
  messages.value.push({
    id: userMsgId,
    role: 'user',
    content: q,
  })

  queryInput.value = ''
  isSubmitting.value = true

  const assistantMsgId = 'a_' + Date.now()
  const assistantMsg: ChatMessage = {
    id: assistantMsgId,
    role: 'assistant',
    loading: true,
  }
  messages.value.push(assistantMsg)

  try {
    const res = await fetch('/api/qa/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        question: q,
        scope: scope.value,
        member_id: scope.value === 'member' ? selectedMemberId.value : undefined,
        policy_id: scope.value === 'policy' ? selectedPolicyId.value : undefined,
        stream: false,
      }),
    })

    if (!res.ok) {
      throw new Error(`HTTP error ${res.status}`)
    }

    const data: QAAnswer = await res.json()
    messages.value = messages.value.map(m =>
      m.id === assistantMsgId ? { ...m, answer: data, loading: false } : m
    )
  } catch (err: any) {
    messages.value = messages.value.map(m =>
      m.id === assistantMsgId ? { ...m, content: `抱歉，请求处理失败：${err.message || '网络连接异常'}`, loading: false } : m
    )
  } finally {
    isSubmitting.value = false
  }
}

// 聚焦原文依据并打开抽屉
async function openCitationDrawer(citation: Citation) {
  if (!citation) return

  // 获取页面元数据
  try {
    if (citation.policy_id) {
      const pRes = await fetch(`/api/policies/${citation.policy_id}`)
      if (pRes.ok) {
        const pData = await pRes.json()
        drawerPages.value = pData.pages || []
        drawerPolicyTitle.value = pData.product_name || '保单原文'
      }
    } else if (citation.document_id) {
      const dRes = await fetch(`/api/documents/${citation.document_id}/pages`)
      if (dRes.ok) {
        const dData = await dRes.json()
        drawerPages.value = dData.pages || []
        drawerPolicyTitle.value = citation.policy_name || '保单条款原文'
      }
    }

    activeHighlight.value = {
      page_no: citation.page,
      rects: citation.rects || [],
      status: citation.status || 'verified',
    }
    drawerOpen.value = true
  } catch (err) {
    console.error('Failed to open citation in drawer', err)
  }
}

function getVerdictClass(v?: string) {
  switch (v) {
    case 'likely_covered':
      return 'verdict-covered'
    case 'likely_not_covered':
      return 'verdict-not-covered'
    case 'depends':
      return 'verdict-depends'
    case 'no_basis':
    default:
      return 'verdict-no-basis'
  }
}
</script>

<template>
  <div class="ask-page-layout">
    <!-- 主问答交流区 -->
    <div class="chat-main-container">
      <!-- 顶栏：提问范围配置 -->
      <div class="scope-bar glass">
        <div class="scope-label">提问范围：</div>
        <div class="scope-pills">
          <button
            class="pill-btn"
            :class="{ active: scope === 'all' }"
            @click="scope = 'all'"
          >
            <ShieldCheck class="w-3.5 h-3.5 mr-1" />
            全家有效保单
          </button>
          <button
            class="pill-btn"
            :class="{ active: scope === 'member' }"
            @click="scope = 'member'"
          >
            <User class="w-3.5 h-3.5 mr-1" />
            指定成员
          </button>
          <button
            class="pill-btn"
            :class="{ active: scope === 'policy' }"
            @click="scope = 'policy'"
          >
            <FileText class="w-3.5 h-3.5 mr-1" />
            指定保单
          </button>
        </div>

        <!-- 成员选择器 -->
        <div v-if="scope === 'member'" class="selector-wrap">
          <select v-model="selectedMemberId" class="scope-select">
            <option value="">全部家庭成员</option>
            <option v-for="m in members" :key="m.id" :value="m.id">
              {{ m.display_name }} ({{ m.placeholder }})
            </option>
          </select>
        </div>

        <!-- 保单选择器 -->
        <div v-if="scope === 'policy'" class="selector-wrap">
          <select v-model="selectedPolicyId" class="scope-select">
            <option value="">全部已生效保单</option>
            <option v-for="p in policies" :key="p.id" :value="p.id">
              {{ p.insurer }} - {{ p.product_name }}
            </option>
          </select>
        </div>
      </div>

      <!-- 对话记录区 -->
      <div class="chat-feed-area">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="message-row"
          :class="`role-${msg.role}`"
        >
          <!-- 用户提问气泡 -->
          <div v-if="msg.role === 'user'" class="user-bubble">
            {{ msg.content }}
          </div>

          <!-- 助手回答面板 -->
          <div v-else class="assistant-panel glass">
            <!-- 加载状态 -->
            <div v-if="msg.loading" class="loading-box">
              <Sparkles class="w-5 h-5 animate-spin text-[var(--primary)]" />
              <span>正在全文检索条款、比对依据并生成分析...</span>
            </div>

            <!-- 纯文字回答（如欢迎语） -->
            <div v-else-if="msg.content" class="text-content">
              {{ msg.content }}
            </div>

            <!-- 结构化回答输出 -->
            <div v-else-if="msg.answer" class="qa-structured-result">
              <!-- 结论徽章 -->
              <div class="verdict-banner" :class="getVerdictClass(msg.answer.verdict)">
                <div class="verdict-tag">{{ msg.answer.verdict_label }}</div>
                <div class="verdict-sub">根据已核验的条款文本得出初步结论</div>
              </div>

              <!-- 推理分析步骤 -->
              <div v-if="msg.answer.reasoning?.length" class="section-block">
                <div class="section-title">
                  <Sparkles class="w-4 h-4 mr-1 text-[var(--primary)]" />
                  条款分析过程
                </div>
                <ul class="reasoning-list">
                  <li v-for="(r, idx) in msg.answer.reasoning" :key="idx" class="reasoning-item">
                    {{ r }}
                  </li>
                </ul>
              </div>

              <!-- 条款依据引用卡片 (思源宋体，左侧竖线) -->
              <div v-if="msg.answer.citations?.length" class="section-block">
                <div class="section-title">
                  <FileText class="w-4 h-4 mr-1 text-[var(--primary)]" />
                  合同条款原文依据
                </div>
                <div class="citations-grid">
                  <div
                    v-for="(c, cIdx) in msg.answer.citations"
                    :key="cIdx"
                    class="citation-card"
                    @click="openCitationDrawer(c)"
                  >
                    <div class="citation-header">
                      <span class="policy-name">{{ c.policy_name || '保单合同' }}</span>
                      <span class="page-badge">第 {{ c.page }} 页</span>
                      <span class="action-tag">
                        定位原文 <ChevronRight class="w-3 h-3 ml-0.5 inline" />
                      </span>
                    </div>
                    <div class="citation-quote">
                      “{{ c.quote }}”
                    </div>
                  </div>
                </div>
              </div>

              <!-- 需要向保险公司确认事项 -->
              <div
                v-if="msg.answer.confirm_with_insurer?.length"
                class="section-block confirm-box"
              >
                <div class="section-title text-[var(--amber)]">
                  <AlertTriangle class="w-4 h-4 mr-1" />
                  需向保险公司进一步确认事项
                </div>
                <ul class="confirm-list">
                  <li v-for="(item, iIdx) in msg.answer.confirm_with_insurer" :key="iIdx">
                    {{ item }}
                  </li>
                </ul>
              </div>

              <!-- 固定免责声明 -->
              <div class="disclaimer-bar">
                <Info class="w-3.5 h-3.5 mr-1 flex-shrink-0" />
                <span>{{ msg.answer.disclaimer }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 快捷预设提问标签 -->
      <div class="preset-wrap">
        <span class="preset-label">猜你想问：</span>
        <button
          v-for="(p, idx) in presetQuestions"
          :key="idx"
          class="preset-chip"
          @click="applyPreset(p)"
        >
          {{ p }}
        </button>
      </div>

      <!-- 底部输入框 -->
      <div class="input-container glass">
        <textarea
          v-model="queryInput"
          placeholder="输入关于保障范围、理赔条件或免责条款的问题（Enter 发送，Shift+Enter 换行）..."
          rows="2"
          class="chat-textarea"
          @keydown.enter.exact.prevent="handleSend"
        />
        <button
          class="send-btn"
          :disabled="!queryInput.trim() || isSubmitting"
          @click="handleSend"
        >
          <Send class="w-4 h-4 mr-1" />
          <span>提问</span>
        </button>
      </div>
    </div>

    <!-- 右侧阅读器抽屉 -->
    <div v-if="drawerOpen" class="drawer-overlay" @click.self="drawerOpen = false">
      <div class="drawer-container glass">
        <DocViewer
          :pages="drawerPages"
          :active-highlight="activeHighlight"
          :is-drawer="true"
          @close="drawerOpen = false"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.ask-page-layout {
  display: flex;
  height: calc(100vh - 64px);
  position: relative;
  overflow: hidden;
}

.chat-main-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: var(--sp-4) var(--sp-6);
  max-width: 1080px;
  margin: 0 auto;
  width: 100%;
}

/* 提问范围栏 */
.scope-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-4);
  border-radius: var(--rad-control);
  margin-bottom: var(--sp-3);
}

.scope-label {
  font-size: var(--fs-body-sm);
  color: var(--text-2);
  font-weight: 500;
}

.scope-pills {
  display: flex;
  gap: var(--sp-1);
}

.pill-btn {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: var(--rad-full);
  font-size: var(--fs-body-xs);
  background: transparent;
  color: var(--text-2);
  border: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: all 0.15s ease;
}

.pill-btn.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

.scope-select {
  padding: 4px 10px;
  font-size: var(--fs-body-xs);
  border-radius: var(--rad-control);
  border: 1px solid var(--border-subtle);
  background: var(--surface-1);
  color: var(--text-1);
  outline: none;
}

/* 消息流 */
.chat-feed-area {
  flex: 1;
  overflow-y: auto;
  padding-right: var(--sp-2);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.message-row {
  display: flex;
  width: 100%;
}

.message-row.role-user {
  justify-content: flex-end;
}

.message-row.role-assistant {
  justify-content: flex-start;
}

.user-bubble {
  max-width: 75%;
  background: var(--primary);
  color: #fff;
  padding: var(--sp-3) var(--sp-4);
  border-radius: 16px 16px 4px 16px;
  font-size: var(--fs-body-md);
  line-height: 1.5;
  word-break: break-word;
}

.assistant-panel {
  max-width: 85%;
  width: 100%;
  border-radius: var(--rad-panel);
  padding: var(--sp-5);
  background: var(--surface-2);
  border: 1px solid var(--border-subtle);
}

.loading-box {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  color: var(--text-2);
  font-size: var(--fs-body-sm);
  padding: var(--sp-2) 0;
}

.text-content {
  font-size: var(--fs-body-md);
  color: var(--text-1);
  line-height: 1.6;
}

/* 结构化结论 */
.verdict-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--rad-control);
  margin-bottom: var(--sp-4);
}

.verdict-tag {
  font-size: var(--fs-body-lg);
  font-weight: 600;
}

.verdict-sub {
  font-size: var(--fs-body-xs);
  opacity: 0.85;
}

.verdict-covered {
  background: rgba(42, 143, 130, 0.15);
  color: var(--ok);
  border-left: 4px solid var(--ok);
}

.verdict-not-covered {
  background: rgba(194, 91, 78, 0.15);
  color: var(--danger);
  border-left: 4px solid var(--danger);
}

.verdict-depends {
  background: rgba(208, 140, 54, 0.15);
  color: var(--warning);
  border-left: 4px solid var(--warning);
}

.verdict-no-basis {
  background: rgba(136, 152, 149, 0.15);
  color: var(--text-2);
  border-left: 4px solid var(--text-3);
}

.section-block {
  margin-bottom: var(--sp-4);
}

.section-title {
  display: flex;
  align-items: center;
  font-size: var(--fs-body-sm);
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: var(--sp-2);
}

.reasoning-list {
  list-style-type: decimal;
  padding-left: var(--sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  font-size: var(--fs-body-sm);
  color: var(--text-2);
  line-height: 1.6;
}

/* 原文引用卡片 */
.citations-grid {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.citation-card {
  padding: var(--sp-3);
  border-radius: var(--rad-control);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
  cursor: pointer;
  transition: background 0.15s ease;
}

.citation-card:hover {
  background: rgba(42, 143, 130, 0.05);
  border-color: var(--primary);
}

.citation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--sp-2);
  font-size: var(--fs-body-xs);
}

.policy-name {
  font-weight: 600;
  color: var(--text-1);
}

.page-badge {
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-2);
}

.action-tag {
  color: var(--primary);
  display: inline-flex;
  align-items: center;
}

.citation-quote {
  font-family: var(--font-serif);
  font-size: var(--fs-body-sm);
  color: var(--text-1);
  line-height: 1.5;
  border-left: 2px solid var(--primary);
  padding-left: var(--sp-2);
}

.confirm-box {
  background: rgba(208, 140, 54, 0.08);
  padding: var(--sp-3);
  border-radius: var(--rad-control);
  border: 1px dashed var(--warning);
}

.confirm-list {
  list-style-type: disc;
  padding-left: var(--sp-5);
  font-size: var(--fs-body-xs);
  color: var(--text-2);
  line-height: 1.6;
}

.disclaimer-bar {
  display: flex;
  align-items: center;
  font-size: 11px;
  color: var(--text-3);
  padding-top: var(--sp-2);
  border-top: 1px solid var(--border-subtle);
}

/* 预设问题 */
.preset-wrap {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin: var(--sp-2) 0;
}

.preset-label {
  font-size: var(--fs-body-xs);
  color: var(--text-3);
}

.preset-chip {
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
  color: var(--text-2);
  padding: 4px 10px;
  border-radius: var(--rad-full);
  font-size: var(--fs-body-xs);
  cursor: pointer;
  transition: all 0.15s ease;
}

.preset-chip:hover {
  color: var(--primary);
  border-color: var(--primary);
}

/* 输入框 */
.input-container {
  display: flex;
  align-items: flex-end;
  gap: var(--sp-2);
  padding: var(--sp-3);
  border-radius: var(--rad-control);
  background: var(--surface-1);
  border: 1px solid var(--border-subtle);
}

.chat-textarea {
  flex: 1;
  border: none;
  background: transparent;
  resize: none;
  font-size: var(--fs-body-md);
  color: var(--text-1);
  outline: none;
  font-family: inherit;
}

.send-btn {
  display: inline-flex;
  align-items: center;
  padding: 8px 18px;
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: var(--rad-control);
  font-size: var(--fs-body-sm);
  font-weight: 500;
  cursor: pointer;
  transition: opacity 0.15s ease;
}

.send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 抽屉 */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  z-index: 999;
  display: flex;
  justify-content: flex-end;
}

.drawer-container {
  width: 650px;
  max-width: 90vw;
  height: 100%;
  background: var(--surface-1);
  border-left: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
}

@media (max-width: 768px) {
  .chat-main-container {
    padding: var(--sp-2);
  }
  .assistant-panel,
  .user-bubble {
    max-width: 95%;
  }
}
</style>
