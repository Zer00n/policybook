<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeft,
  FileText,
  Trash2,
  ShieldCheck,
  ShieldAlert,
  Eye,
  EyeOff,
  Copy,
  Check,
  Calendar,
  DollarSign,
  Clock,
  AlertTriangle,
  ExternalLink,
  ChevronRight,
  User,
  X,
  FileCheck,
} from 'lucide-vue-next'
import DocViewer, { HighlightTarget, PageMeta } from '@/components/doc-viewer/DocViewer.vue'

const route = useRoute()
const router = useRouter()
const policyId = computed(() => route.params.id as string)

const policy = ref<any>(null)
const loading = ref(true)
const errorMsg = ref('')

const showPlainPolicyNo = ref(false)
const copied = ref(false)
const drawerOpen = ref(false)
const isMaskedMode = ref(true)
const activeHighlight = ref<HighlightTarget | null>(null)

const deleteModalOpen = ref(false)
const deleting = ref(false)

const categoriesMap: Record<string, string> = {
  accident: '意外险',
  medical: '医疗险',
  critical_illness: '重疾险',
  term_life: '定期寿险',
  whole_life: '终身寿险',
  annuity: '年金险',
  property: '财产险',
  auto: '车险',
  other: '其他险种',
}

const coverageKindsMap: Record<string, string> = {
  death: '身故保障',
  disability: '伤残保障',
  critical_illness: '重疾给付',
  medical: '医疗费用',
  accident_medical: '意外医疗',
  hospital_allowance: '住院津贴',
  transport_extra: '交通额外',
  sudden_death: '猝死保障',
  other: '其他责任',
}

async function fetchPolicyDetail() {
  loading.value = true
  errorMsg.value = ''
  try {
    const res = await fetch(`/api/policies/${policyId.value}`)
    if (!res.ok) {
      if (res.status === 404) {
        errorMsg.value = '未找到该保单或已被删除'
      } else {
        errorMsg.value = '加载保单详情失败'
      }
      return
    }
    policy.value = await res.json()
  } catch (err: any) {
    errorMsg.value = err.message || '网络请求错误'
  } finally {
    loading.value = false
  }
}

const members = ref<any[]>([])
const editPartiesModalOpen = ref(false)
const editingApplicantId = ref<string | null>(null)
const editingInsuredId = ref<string | null>(null)
const updatingParties = ref(false)

async function fetchMembers() {
  try {
    const res = await fetch('/api/members')
    if (res.ok) {
      members.value = await res.json()
    }
  } catch {}
}

function openEditPartiesModal() {
  editingApplicantId.value = applicantParty.value?.member_id || null
  editingInsuredId.value = insuredMembers.value[0]?.member_id || null
  editPartiesModalOpen.value = true
}

async function savePolicyParties() {
  updatingParties.value = true
  try {
    const partiesPayload = []
    if (editingApplicantId.value) {
      partiesPayload.push({ role: 'applicant', member_id: editingApplicantId.value, share: 100 })
    }
    if (editingInsuredId.value) {
      partiesPayload.push({ role: 'insured', member_id: editingInsuredId.value, share: 100 })
    }
    for (const ben of beneficiaryParties.value) {
      partiesPayload.push({ role: 'beneficiary', member_id: ben.member_id, share: ben.share || 100 })
    }

    const res = await fetch(`/api/policies/${policyId.value}/parties`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parties: partiesPayload }),
    })
    if (res.ok) {
      editPartiesModalOpen.value = false
      await fetchPolicyDetail()
    } else {
      alert('保存成员关联失败')
    }
  } catch {
    alert('网络请求异常')
  } finally {
    updatingParties.value = false
  }
}

// Vue Router 在两个都命中 /policies/:id 的路由间跳转时会复用同一组件实例，
// onMounted 不会再次触发，必须显式监听参数变化才能刷新为新保单的数据
watch(policyId, () => {
  // 重置与上一份保单相关的阅读器/高亮状态，避免短暂显示旧保单的原文与高亮
  drawerOpen.value = false
  activeHighlight.value = null
  showPlainPolicyNo.value = false
  fetchPolicyDetail()
}, { immediate: true })

onMounted(() => {
  fetchMembers()
})

function formatMoney(cents?: number) {
  if (cents === null || cents === undefined) return '详见条款'
  const yuan = cents / 100
  if (yuan >= 10000 && yuan % 10000 === 0) {
    return `${yuan / 10000} 万元`
  }
  return `¥${yuan.toLocaleString('zh-CN')}`
}

function formatRatio(ratioThousandth?: number) {
  if (ratioThousandth === null || ratioThousandth === undefined) return '-'
  return `${(ratioThousandth / 10).toFixed(0)}%`
}

function getStatusBadge(status?: string) {
  switch (status) {
    case 'active':
      return { text: '生效中', class: 'status-active' }
    case 'waiting':
      return { text: '等待期', class: 'status-waiting' }
    case 'expiring_soon':
      return { text: '即将到期', class: 'status-warning' }
    case 'lapsed':
      return { text: '已失效', class: 'status-lapsed' }
    default:
      return { text: '生效中', class: 'status-active' }
  }
}

function getCategoryLabel(cat?: string) {
  if (!cat) return '保险产品'
  return categoriesMap[cat] || cat
}

function getCoverageKindLabel(kind?: string) {
  if (!kind) return '通用责任'
  return coverageKindsMap[kind] || kind
}

function copyPolicyNo() {
  const text = policy.value?.policy_no || '暂无保单号'
  navigator.clipboard.writeText(text).then(() => {
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  })
}

// 聚焦原文证据并展开阅读器 (FLIP)
function focusEvidence(ev: any, event?: MouseEvent) {
  if (!ev) return
  drawerOpen.value = true
  activeHighlight.value = {
    page_no: ev.page_no || 1,
    rects: ev.rects || [],
    status: ev.status || 'verified',
    sourceEl: (event?.currentTarget as HTMLElement) || null,
  }
}

// 删除保单
async function confirmDeletePolicy() {
  deleting.value = true
  try {
    const res = await fetch(`/api/policies/${policyId.value}`, {
      method: 'DELETE',
    })
    if (res.ok) {
      deleteModalOpen.value = false
      router.push('/policies')
    } else {
      alert('删除失败，请稍后重试')
    }
  } catch {
    alert('网络请求异常')
  } finally {
    deleting.value = false
  }
}

const pagesList = computed<PageMeta[]>(() => {
  return policy.value?.pages || []
})

const insuredMembers = computed(() => {
  if (!policy.value?.parties) return []
  return policy.value.parties.filter((p: any) => p.role === 'insured')
})

const applicantParty = computed(() => {
  if (!policy.value?.parties) return null
  return policy.value.parties.find((p: any) => p.role === 'applicant')
})

const beneficiaryParties = computed(() => {
  if (!policy.value?.parties) return []
  return policy.value.parties.filter((p: any) => p.role === 'beneficiary')
})
</script>

<template>
  <div class="policy-detail-container">
    <!-- 顶部操作栏 -->
    <div class="top-nav-bar">
      <button class="btn-back" @click="router.push('/policies')">
        <ArrowLeft :size="16" /> 返回保单库
      </button>

      <div v-if="policy" class="top-actions">
        <button
          class="btn-action btn-reader"
          :class="{ active: drawerOpen }"
          @click="drawerOpen = !drawerOpen"
        >
          <FileText :size="16" />
          <span>{{ drawerOpen ? '收起原文' : '查看合同原文' }}</span>
          <span v-if="pagesList.length" class="page-count-tag">
            {{ pagesList.length }} 页
          </span>
        </button>

        <button
          class="btn-action btn-danger"
          @click="deleteModalOpen = true"
          title="删除保单"
        >
          <Trash2 :size="16" />
          <span>删除</span>
        </button>
      </div>
    </div>

    <!-- 加载与错误状态 -->
    <div v-if="loading" class="state-panel glass">
      正在加载保单信息...
    </div>
    <div v-else-if="errorMsg" class="state-panel glass error">
      <AlertTriangle :size="32" class="error-icon" />
      <p>{{ errorMsg }}</p>
      <button class="btn-primary" @click="router.push('/policies')">返回保单库</button>
    </div>

    <!-- 保单主体内容 -->
    <div v-else-if="policy" class="detail-main-layout">
      <!-- 左/主内容区 -->
      <div class="content-column">
        <!-- 1. 保单核心摘要卡 (Panel 1) -->
        <div class="summary-card glass">
          <div class="card-top-row">
            <div class="company-badge">{{ policy.insurer }}</div>
            <div class="badges-group">
              <span class="category-pill">
                {{ getCategoryLabel(policy.category) }}
                {{ policy.subcategory ? `· ${policy.subcategory}` : '' }}
              </span>
              <span class="status-badge" :class="getStatusBadge(policy.status).class">
                {{ getStatusBadge(policy.status).text }}
              </span>
            </div>
          </div>

          <h1 class="policy-title">{{ policy.product_name }}</h1>

          <!-- 保单号行 (支持解密查看与复制) -->
          <div class="meta-row">
            <div class="policy-no-wrap">
              <span class="meta-label">保单号：</span>
              <span class="meta-val font-mono">
                {{
                  showPlainPolicyNo && policy.policy_no
                    ? policy.policy_no
                    : policy.policy_no
                    ? policy.policy_no.replace(/.(?=.{4})/g, '*')
                    : '未记录保单号'
                }}
              </span>
              <button
                v-if="policy.policy_no"
                class="icon-btn"
                :title="showPlainPolicyNo ? '隐藏保单号' : '查看完整保单号'"
                @click="showPlainPolicyNo = !showPlainPolicyNo"
              >
                <EyeOff v-if="showPlainPolicyNo" :size="14" />
                <Eye v-else :size="14" />
              </button>
              <button
                v-if="policy.policy_no"
                class="icon-btn"
                title="复制保单号"
                @click="copyPolicyNo"
              >
                <Check v-if="copied" :size="14" class="copied-icon" />
                <Copy v-else :size="14" />
              </button>
            </div>

            <!-- 关联合同证据 -->
            <div
              v-if="policy.evidences?.product_name"
              class="cite-link"
              @click="focusEvidence(policy.evidences.product_name, $event)"
            >
              <FileCheck :size="13" /> 条款依据 (第 {{ policy.evidences.product_name.page_no }} 页)
            </div>
          </div>

          <!-- 关系人标签行 -->
          <div class="parties-section">
            <div class="party-group">
              <span class="party-role-title">被保险人：</span>
              <div class="party-chips-line">
                <span
                  v-for="im in insuredMembers"
                  :key="im.id"
                  class="party-chip"
                  :style="{ borderColor: im.color, color: im.color }"
                >
                  <User :size="12" />
                  <strong>{{ im.display_name }}</strong>
                  <span v-if="im.placeholder" class="chip-placeholder">
                    ({{ im.placeholder }})
                  </span>
                </span>
                <span v-if="!insuredMembers.length" class="party-chip-empty">
                  未指定被保险人
                </span>
              </div>
            </div>

            <div v-if="applicantParty" class="party-group sub-party">
              <span class="party-role-title">投保人：</span>
              <span class="party-text">{{ applicantParty.display_name }}</span>
            </div>

            <div v-if="beneficiaryParties.length" class="party-group sub-party">
              <span class="party-role-title">受益人：</span>
              <span
                v-for="ben in beneficiaryParties"
                :key="ben.id"
                class="party-text"
              >
                {{ ben.display_name }} ({{ ben.share || 100 }}%)
              </span>
            </div>

            <button class="btn-secondary btn-small bind-member-btn" @click="openEditPartiesModal" style="margin-top: 6px;">
              <User :size="13" /> 变更归属成员
            </button>
          </div>

          <!-- 关键数值指标网格 (4格) -->
          <div class="metrics-grid">
            <div class="metric-item">
              <span class="metric-label">基本保额</span>
              <span class="metric-value metric-highlight">
                {{ formatMoney(policy.sum_insured_cents) }}
              </span>
            </div>

            <div class="metric-item">
              <span class="metric-label">年交 / 首期保费</span>
              <span class="metric-value">
                {{ formatMoney(policy.premium_cents) }}
              </span>
            </div>

            <div class="metric-item">
              <span class="metric-label">缴费方式 / 期间</span>
              <span class="metric-value">
                {{ policy.pay_mode || '年交' }}
                {{ policy.pay_years ? `· ${policy.pay_years}` : '' }}
              </span>
            </div>

            <div class="metric-item">
              <span class="metric-label">保障期间</span>
              <span class="metric-value">
                {{ policy.effective_date || '即期' }} ~ {{ policy.expiry_date || '终身' }}
              </span>
            </div>
          </div>

          <!-- 附加关键条款细则 -->
          <div class="clause-meta-row">
            <div class="meta-tag-item">
              <Clock :size="13" />
              <span>等待期: {{ policy.waiting_days !== null && policy.waiting_days !== undefined ? `${policy.waiting_days}天` : '详见条款' }}</span>
            </div>
            <div class="meta-tag-item">
              <ShieldCheck :size="13" />
              <span>犹豫期: {{ policy.cooling_days !== null && policy.cooling_days !== undefined ? `${policy.cooling_days}天` : '15天' }}</span>
            </div>
            <div class="meta-tag-item">
              <Calendar :size="13" />
              <span>
                续保: {{ policy.guaranteed_renewal ? `保证续保 (${policy.renewal_years || '长期'})` : '非保证续保' }}
              </span>
            </div>
          </div>
        </div>

        <!-- 2. 保障责任清单表格 (Panel 2) -->
        <div class="section-panel glass">
          <div class="panel-header">
            <div>
              <h2 class="panel-title">保障责任清单</h2>
              <p class="panel-subtitle">
                共 {{ policy.coverages?.length || 0 }} 项保障，点击条款依据可随时回溯合同原文
              </p>
            </div>
          </div>

          <div v-if="!policy.coverages?.length" class="empty-hint">
            暂无解析出具体责任项
          </div>

          <div v-else class="coverages-table-wrap">
            <table class="coverages-table">
              <thead>
                <tr>
                  <th>保障责任</th>
                  <th>类型</th>
                  <th class="num-col">保额 / 限额</th>
                  <th class="num-col">免赔额</th>
                  <th>赔付比例</th>
                  <th>等待期</th>
                  <th>条款依据</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="cov in policy.coverages"
                  :key="cov.id"
                  class="cov-row"
                >
                  <td>
                    <div class="cov-title-line">
                      <span class="cov-name">{{ cov.name }}</span>
                      <span v-if="cov.is_rider" class="rider-pill">附加险</span>
                    </div>
                  </td>
                  <td>
                    <span class="kind-tag">{{ getCoverageKindLabel(cov.kind) }}</span>
                  </td>
                  <td class="num-col">
                    <span class="money-text font-bold">
                      {{ formatMoney(cov.limit_cents) }}
                    </span>
                  </td>
                  <td class="num-col">
                    {{ cov.deductible_cents ? formatMoney(cov.deductible_cents) : '0元' }}
                  </td>
                  <td>
                    <div v-if="cov.ratio_with_si" class="ratio-line">
                      <span class="ratio-lbl">经社保:</span>
                      <span class="ratio-val">{{ formatRatio(cov.ratio_with_si) }}</span>
                    </div>
                    <div v-if="cov.ratio_without_si" class="ratio-line sub">
                      <span class="ratio-lbl">未经社保:</span>
                      <span class="ratio-val">{{ formatRatio(cov.ratio_without_si) }}</span>
                    </div>
                    <span v-if="!cov.ratio_with_si && !cov.ratio_without_si" class="text-muted">
                      100%
                    </span>
                  </td>
                  <td>
                    {{ cov.waiting_days ? `${cov.waiting_days}天` : '-' }}
                  </td>
                  <td>
                    <div v-if="cov.evidences?.length" class="evidence-actions">
                      <button
                        v-for="ev in cov.evidences"
                        :key="ev.id"
                        class="btn-evidence"
                        @click="focusEvidence(ev, $event)"
                      >
                        <FileText :size="12" /> 第 {{ ev.page_no }} 页
                      </button>
                    </div>
                    <span v-else class="text-muted">-</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <!-- 3. 责任免除与限制条款清单 (Panel 3) -->
        <div class="section-panel glass">
          <div class="panel-header">
            <div class="header-icon-title">
              <ShieldAlert :size="20" class="exclusion-icon" />
              <div>
                <h2 class="panel-title">责任免除与限制条款</h2>
                <p class="panel-subtitle">
                  合同中明确不承担赔偿责任的情形，共 {{ policy.exclusions?.length || 0 }} 项
                </p>
              </div>
            </div>
          </div>

          <div v-if="!policy.exclusions?.length" class="empty-hint">
            合同中暂未单独收录免责条款或正在解析中
          </div>

          <div v-else class="exclusions-grid">
            <div
              v-for="(excl, idx) in policy.exclusions"
              :key="excl.id || idx"
              class="exclusion-item glass-subtle"
            >
              <!-- 通俗释义 -->
              <div class="excl-plain-box">
                <span class="excl-tag">释义</span>
                <span class="excl-explanation">
                  {{ excl.plain_explanation || excl.title }}
                </span>
              </div>

              <!-- 原文引用 -->
              <div v-if="excl.quote" class="quote-container">
                <p class="quote-text">{{ excl.quote }}</p>
              </div>

              <!-- 底部依据按钮 -->
              <div class="excl-footer">
                <span class="excl-no">{{ excl.clause_no || `EXCL-${idx + 1}` }}</span>
                <button
                  class="btn-evidence"
                  @click="focusEvidence(excl, $event)"
                >
                  <FileText :size="12" />
                  <span>第 {{ excl.page_no || 1 }} 页 原文依据</span>
                  <ChevronRight :size="12" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 右侧抽屉 / 嵌入式阅读器 (DocViewer) -->
      <transition name="drawer-fade">
        <div
          v-if="drawerOpen"
          class="reader-drawer-overlay"
          @click.self="drawerOpen = false"
        >
          <div class="reader-drawer glass">
            <!-- 抽屉顶部控制条 -->
            <div class="drawer-header">
              <div class="drawer-title-box">
                <FileText :size="16" class="doc-icon" />
                <span class="doc-name">{{ policy.product_name }} - 条款原文</span>
              </div>

              <div class="drawer-controls">
                <!-- 脱敏/原图切换开关 -->
                <button
                  class="btn-toggle-mask"
                  :class="{ active: isMaskedMode }"
                  @click="isMaskedMode = !isMaskedMode"
                  title="切换脱敏视图"
                >
                  {{ isMaskedMode ? '已脱敏视图' : '原始扫描图' }}
                </button>

                <button class="btn-close" @click="drawerOpen = false" title="关闭">
                  <X :size="18" />
                </button>
              </div>
            </div>

            <!-- DocViewer 组件主体 -->
            <div class="drawer-body">
              <DocViewer
                :pages="pagesList"
                :active-highlight="activeHighlight"
                :masked-mode="isMaskedMode"
                is-drawer
                @close="drawerOpen = false"
              />
            </div>
          </div>
        </div>
      </transition>
    </div>

    <!-- 删除确认弹窗 -->
    <div
      v-if="deleteModalOpen"
      class="modal-overlay"
      @click.self="deleteModalOpen = false"
    >
      <div class="modal-dialog glass">
        <div class="modal-alert-icon">
          <AlertTriangle :size="28" />
        </div>
        <h3 class="modal-title">确定要删除该保单吗？</h3>
        <p class="modal-desc">
          删除后，保单《{{ policy?.product_name }}》的所有责任项、免责条款及对应原文索引将永久移除。
        </p>

        <div class="modal-actions">
          <button class="btn-cancel" @click="deleteModalOpen = false">取消</button>
          <button
            class="btn-confirm-delete"
            :disabled="deleting"
            @click="confirmDeletePolicy"
          >
            {{ deleting ? '正在删除...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 关联家庭成员模态框 -->
    <div
      v-if="editPartiesModalOpen"
      class="modal-overlay"
      @click.self="editPartiesModalOpen = false"
    >
      <div class="modal-dialog glass" style="max-width: 440px;">
        <h3 class="modal-title">关联保单归属家庭成员</h3>
        <p class="modal-desc">
          选择该保单归属的被保险人与投保人，保单将自动归集到对应成员名下汇总保额与保费。
        </p>

        <div class="form-group" style="margin-bottom: 16px; text-align: left;">
          <label style="display: block; font-size: 13px; margin-bottom: 6px; color: var(--text-muted); font-weight: 500;">
            被保险人
          </label>
          <select
            v-model="editingInsuredId"
            style="width: 100%; padding: 8px 12px; border-radius: var(--r-control); border: 1px solid var(--glass-stroke); background: var(--c-paper); color: var(--text); font-size: 14px;"
          >
            <option :value="null">未指定 (不关联具体成员)</option>
            <option v-for="m in members" :key="m.id" :value="m.id">
              {{ m.display_name }} ({{ m.placeholder }})
            </option>
          </select>
        </div>

        <div class="form-group" style="margin-bottom: 24px; text-align: left;">
          <label style="display: block; font-size: 13px; margin-bottom: 6px; color: var(--text-muted); font-weight: 500;">
            投保人
          </label>
          <select
            v-model="editingApplicantId"
            style="width: 100%; padding: 8px 12px; border-radius: var(--r-control); border: 1px solid var(--glass-stroke); background: var(--c-paper); color: var(--text); font-size: 14px;"
          >
            <option :value="null">未指定 (不关联具体成员)</option>
            <option v-for="m in members" :key="m.id" :value="m.id">
              {{ m.display_name }} ({{ m.placeholder }})
            </option>
          </select>
        </div>

        <div class="modal-actions">
          <button class="btn-cancel" @click="editPartiesModalOpen = false">取消</button>
          <button
            class="btn-primary"
            :disabled="updatingParties"
            @click="savePolicyParties"
          >
            {{ updatingParties ? '保存中...' : '保存关联' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.policy-detail-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 20px 48px;
}

/* 顶部操作条 */
.top-nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.btn-back {
  background: transparent;
  border: 1px solid var(--glass-stroke);
  color: var(--text);
  padding: 6px 12px;
  border-radius: var(--r-control);
  font-size: var(--fs-12);
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  transition: background var(--dur-fast) ease, border-color var(--dur-fast) ease;
}

.btn-back:hover {
  background: var(--glass-fill-strong);
  border-color: var(--ok);
}

.top-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.btn-action {
  padding: 6px 14px;
  border-radius: var(--r-control);
  font-size: var(--fs-12);
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: background var(--dur-fast) ease, border-color var(--dur-fast) ease;
}

.btn-reader {
  background: var(--glass-fill-strong);
  border: 1px solid var(--glass-stroke);
  color: var(--text);
}

.btn-reader:hover,
.btn-reader.active {
  border-color: var(--ok);
  color: var(--ok);
}

.page-count-tag {
  background: var(--c-paper);
  border: 1px solid var(--glass-stroke);
  font-size: var(--fs-12);
  padding: 1px 6px;
  border-radius: var(--r-pill);
}

.btn-danger {
  background: transparent;
  border: 1px solid color-mix(in oklch, var(--risk) 30%, transparent);
  color: var(--risk);
}

.btn-danger:hover {
  background: color-mix(in oklch, var(--risk) 12%, transparent);
}

/* 状态面板 */
.state-panel {
  padding: 60px 24px;
  border-radius: var(--r-panel);
  text-align: center;
  color: var(--text-muted);
}

.state-panel.error {
  color: var(--risk);
}

.error-icon {
  margin: 0 auto 12px;
}

/* 主内容布局 */
.detail-main-layout {
  display: flex;
  gap: 24px;
  position: relative;
}

.content-column {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* 1. 保单核心摘要卡 */
.summary-card {
  padding: 24px;
  border-radius: var(--r-panel);
  border: 1px solid var(--glass-stroke);
}

.card-top-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.company-badge {
  font-size: var(--fs-12);
  font-weight: 600;
  color: var(--text-muted);
}

.badges-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.category-pill {
  font-size: var(--fs-12);
  padding: 2px 8px;
  border-radius: var(--r-pill);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  color: var(--text-muted);
}

.status-badge {
  font-size: var(--fs-12);
  padding: 2px 8px;
  border-radius: var(--r-pill);
  font-weight: 500;
}

.status-active {
  background: color-mix(in oklch, var(--ok) 16%, transparent);
  color: var(--ok);
}

.status-waiting {
  background: color-mix(in oklch, var(--pending) 16%, transparent);
  color: var(--pending);
}

.status-warning {
  background: color-mix(in oklch, var(--pending) 20%, transparent);
  color: var(--pending);
}

.status-lapsed {
  background: var(--glass-fill);
  color: var(--text-muted);
}

.policy-title {
  margin: 0 0 12px;
  font-size: var(--fs-23);
  font-weight: 700;
  color: var(--text);
  line-height: 1.3;
}

.meta-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
  font-size: var(--fs-12);
}

.policy-no-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.meta-label {
  color: var(--text-muted);
}

.meta-val {
  color: var(--text);
  font-weight: 600;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 2px 4px;
  display: inline-flex;
  align-items: center;
  border-radius: 4px;
}

.icon-btn:hover {
  color: var(--text);
}

.copied-icon {
  color: var(--ok);
}

.cite-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--ok);
  cursor: pointer;
  font-size: var(--fs-12);
  padding: 2px 8px;
  border-radius: var(--r-pill);
  background: color-mix(in oklch, var(--ok) 8%, transparent);
  border: 1px solid color-mix(in oklch, var(--ok) 25%, transparent);
}

.cite-link:hover {
  background: color-mix(in oklch, var(--ok) 16%, transparent);
}

/* 关系人 */
.parties-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 16px;
  background: var(--glass-fill-strong);
  border-radius: var(--r-control);
  margin-bottom: 20px;
}

.party-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.party-role-title {
  font-size: var(--fs-12);
  color: var(--text-muted);
  min-width: 72px;
}

.party-chips-line {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.party-chip {
  font-size: var(--fs-12);
  padding: 2px 10px;
  border-radius: var(--r-pill);
  border: 1px solid;
  background: var(--c-paper);
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.chip-placeholder {
  font-size: 11px;
  opacity: 0.8;
}

.party-chip-empty {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.sub-party {
  font-size: var(--fs-12);
}

.party-text {
  color: var(--text);
  font-weight: 500;
}

/* 4格指标 */
.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 16px 0;
  border-top: 1px solid var(--glass-stroke);
  border-bottom: 1px solid var(--glass-stroke);
  margin-bottom: 16px;
}

.metric-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.metric-label {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.metric-value {
  font-size: var(--fs-19);
  font-weight: 700;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.metric-highlight {
  color: var(--ok);
}

/* 底部细则小条 */
.clause-meta-row {
  display: flex;
  align-items: center;
  gap: 20px;
  font-size: var(--fs-12);
  color: var(--text-muted);
  flex-wrap: wrap;
}

.meta-tag-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

/* 2 & 3 通用面板容器 */
.section-panel {
  padding: 24px;
  border-radius: var(--r-panel);
  border: 1px solid var(--glass-stroke);
}

.panel-header {
  margin-bottom: 16px;
}

.header-icon-title {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.exclusion-icon {
  color: var(--risk);
  margin-top: 2px;
}

.panel-title {
  margin: 0 0 4px;
  font-size: var(--fs-19);
  font-weight: 700;
  color: var(--text);
}

.panel-subtitle {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.empty-hint {
  text-align: center;
  padding: 24px;
  color: var(--text-muted);
  font-size: var(--fs-14);
}

/* 责任表格 */
.coverages-table-wrap {
  border-radius: var(--r-control);
  overflow: hidden;
  border: 1px solid var(--glass-stroke);
}

.coverages-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-12);
}

.coverages-table th {
  padding: 12px 14px;
  text-align: left;
  background: var(--glass-fill-strong);
  color: var(--text-muted);
  font-weight: 500;
  font-size: var(--fs-12);
  border-bottom: 1px solid var(--glass-stroke);
}

.coverages-table td {
  padding: 14px;
  border-bottom: 1px solid var(--glass-stroke);
}

.cov-row {
  transition: background var(--dur-fast) ease;
}

.cov-row:hover {
  background: var(--glass-fill-strong);
}

.cov-title-line {
  display: flex;
  align-items: center;
  gap: 6px;
}

.cov-name {
  font-weight: 600;
  color: var(--text);
}

.rider-pill {
  font-size: 11px;
  padding: 1px 6px;
  border-radius: var(--r-pill);
  background: color-mix(in oklch, var(--pending) 16%, transparent);
  color: var(--pending);
  font-weight: 500;
}

.kind-tag {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.num-col {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.money-text {
  color: var(--ok);
}

.ratio-line {
  font-size: var(--fs-12);
  display: flex;
  gap: 4px;
}

.ratio-line.sub {
  color: var(--text-muted);
}

.ratio-lbl {
  color: var(--text-muted);
}

.ratio-val {
  font-weight: 600;
  color: var(--text);
}

.evidence-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.btn-evidence {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  color: var(--text);
  padding: 4px 8px;
  border-radius: var(--r-control);
  font-size: var(--fs-12);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease;
}

.btn-evidence:hover {
  border-color: var(--ok);
  background: var(--glass-fill-strong);
  color: var(--ok);
}

/* 3. 免责条款卡片网格 */
.exclusions-grid {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.exclusion-item {
  padding: 16px;
  border-radius: var(--r-control);
  border: 1px solid var(--glass-stroke);
  background: var(--glass-fill-strong);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.excl-plain-box {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.excl-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: var(--r-pill);
  background: color-mix(in oklch, var(--risk) 16%, transparent);
  color: var(--risk);
  flex-shrink: 0;
  margin-top: 2px;
}

.excl-explanation {
  font-size: var(--fs-14);
  font-weight: 600;
  color: var(--text);
  line-height: 1.5;
}

/* 原文引用块：思源宋体 + 2px 朱砂色竖线 */
.quote-container {
  font-family: var(--font-quote);
  font-size: var(--fs-14);
  color: var(--text);
  line-height: var(--lh-quote);
  padding: 8px 14px;
  background: var(--c-paper);
  border-left: 2px solid var(--risk);
  border-radius: 0 var(--r-control) var(--r-control) 0;
}

.quote-text {
  margin: 0;
  white-space: pre-wrap;
}

.excl-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.excl-no {
  font-size: var(--fs-12);
  color: var(--text-muted);
  font-family: monospace;
}

/* 右侧抽屉 / 原文阅读器 */
.reader-drawer-overlay {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
}

.reader-drawer {
  width: min(560px, 94vw);
  height: 100%;
  background: var(--bg);
  border-left: 1px solid var(--glass-stroke);
  display: flex;
  flex-direction: column;
  box-shadow: -4px 0 24px rgba(0, 0, 0, 0.25);
}

.drawer-header {
  padding: 14px 18px;
  border-bottom: 1px solid var(--glass-stroke);
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--glass-fill-strong);
}

.drawer-title-box {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--fs-14);
  font-weight: 600;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-icon {
  color: var(--ok);
  flex-shrink: 0;
}

.drawer-controls {
  display: flex;
  align-items: center;
  gap: 10px;
}

.btn-toggle-mask {
  font-size: var(--fs-12);
  padding: 4px 8px;
  border-radius: var(--r-control);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  color: var(--text-muted);
  cursor: pointer;
}

.btn-toggle-mask.active {
  color: var(--ok);
  border-color: var(--ok);
}

.btn-close {
  background: transparent;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 6px;
  display: inline-flex;
  align-items: center;
}

.btn-close:hover {
  color: var(--text);
  background: var(--glass-fill);
}

.drawer-body {
  flex: 1;
  overflow: hidden;
  position: relative;
}

/* 抽屉过渡动效 */
.drawer-fade-enter-active,
.drawer-fade-leave-active {
  transition: opacity 220ms ease;
}

.drawer-fade-enter-from,
.drawer-fade-leave-to {
  opacity: 0;
}

.drawer-fade-enter-active .reader-drawer,
.drawer-fade-leave-active .reader-drawer {
  transition: transform 220ms var(--ease-out);
}

.drawer-fade-enter-from .reader-drawer,
.drawer-fade-leave-to .reader-drawer {
  transform: translateX(100%);
}

/* 删除模态框 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 1200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-dialog {
  max-width: 440px;
  width: 100%;
  padding: 24px;
  border-radius: var(--r-panel);
  border: 1px solid var(--glass-stroke);
  text-align: center;
}

.modal-alert-icon {
  color: var(--risk);
  margin-bottom: 12px;
}

.modal-title {
  margin: 0 0 8px;
  font-size: var(--fs-19);
  font-weight: 700;
  color: var(--text);
}

.modal-desc {
  margin: 0 0 24px;
  font-size: var(--fs-14);
  color: var(--text-muted);
  line-height: 1.5;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-cancel {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  padding: 8px 16px;
  border-radius: var(--r-control);
  cursor: pointer;
  color: var(--text);
  font-size: var(--fs-14);
}

.btn-confirm-delete {
  background: var(--risk);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: var(--r-control);
  cursor: pointer;
  font-size: var(--fs-14);
  font-weight: 600;
}

.btn-confirm-delete:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 移动端响应式 (<768px) */
@media (max-width: 768px) {
  .metrics-grid {
    grid-template-columns: 1fr 1fr;
    row-gap: 16px;
  }

  .coverages-table {
    display: block;
    overflow-x: auto;
  }
}

/* 手机 (<600px)：原文阅读器改为从底部滑出的全屏抽屉，而非从右侧滑入 */
@media (max-width: 599px) {
  .reader-drawer-overlay {
    align-items: flex-end;
    justify-content: center;
  }

  .reader-drawer {
    width: 100%;
    height: 90vh;
    border-left: none;
    border-top: 1px solid var(--glass-stroke);
    border-radius: var(--r-panel) var(--r-panel) 0 0;
  }

  .drawer-fade-enter-from .reader-drawer,
  .drawer-fade-leave-to .reader-drawer {
    transform: translateY(100%);
  }
}
</style>
