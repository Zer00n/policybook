<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search,
  LayoutGrid,
  List,
  Filter,
  Plus,
  ShieldCheck,
  Calendar,
  DollarSign,
  User,
  ChevronRight,
  Sparkles,
} from 'lucide-vue-next'

const router = useRouter()

const viewMode = ref<'grid' | 'table'>('grid')
const searchQuery = ref('')
const selectedMember = ref('')
const selectedCategory = ref('')
const selectedStatus = ref('all')

const policies = ref<any[]>([])
const members = ref<any[]>([])
const loading = ref(true)

const categories = [
  { key: '', label: '全部险种' },
  { key: 'accident', label: '意外险' },
  { key: 'medical', label: '医疗险' },
  { key: 'critical_illness', label: '重疾险' },
  { key: 'term_life', label: '定期寿险' },
  { key: 'whole_life', label: '终身寿险' },
  { key: 'annuity', label: '年金险' },
  { key: 'property', label: '财产险' },
  { key: 'auto', label: '车险' },
]

const statusTabs = [
  { key: 'all', label: '全部' },
  { key: 'active', label: '生效中' },
  { key: 'waiting', label: '等待期' },
  { key: 'expiring_soon', label: '即将到期' },
  { key: 'lapsed', label: '已失效' },
]

async function fetchMembers() {
  try {
    const res = await fetch('http://localhost:8000/api/members')
    if (res.ok) {
      members.value = await res.json()
    }
  } catch {}
}

async function fetchPolicies() {
  loading.value = true
  try {
    const params = new URLSearchParams()
    if (searchQuery.value.trim()) params.set('q', searchQuery.value.trim())
    if (selectedMember.value) params.set('member_id', selectedMember.value)
    if (selectedCategory.value) params.set('category', selectedCategory.value)
    if (selectedStatus.value && selectedStatus.value !== 'all') {
      params.set('status', selectedStatus.value)
    }

    const res = await fetch(`http://localhost:8000/api/policies?${params.toString()}`)
    if (res.ok) {
      const data = await res.json()
      policies.value = data.items || []
    }
  } catch {
    policies.value = []
  } finally {
    loading.value = false
  }
}

watch([selectedMember, selectedCategory, selectedStatus], () => {
  fetchPolicies()
})

function onSearch() {
  fetchPolicies()
}

onMounted(() => {
  fetchMembers()
  fetchPolicies()
})

function formatMoney(cents?: number) {
  if (!cents && cents !== 0) return '未录入'
  const yuan = cents / 100
  if (yuan >= 10000 && yuan % 10000 === 0) {
    return `${yuan / 10000} 万元`
  }
  return `¥${yuan.toLocaleString('zh-CN')}`
}

function getCategoryLabel(cat: string) {
  const item = categories.find((c) => c.key === cat)
  return item ? item.label : cat
}

function getStatusBadge(st: string) {
  switch (st) {
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
</script>

<template>
  <div class="policy-page-container">
    <!-- 页面顶栏 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">家庭保单库</h1>
        <p class="page-desc">按家庭成员集中归档、责任清单穿透与全文检索</p>
      </div>

      <button class="btn-primary" @click="router.push('/import')">
        <Plus :size="16" /> 上传新保单
      </button>
    </div>

    <!-- 筛选过滤与搜索工具栏 -->
    <div class="filter-toolbar glass">
      <!-- 搜索框 -->
      <div class="search-box">
        <Search :size="16" class="search-icon" />
        <input
          v-model="searchQuery"
          class="search-input"
          type="text"
          placeholder="全文搜索条款内容、产品名、保险公司..."
          @keydown.enter="onSearch"
        />
      </div>

      <!-- 成员筛选下拉 -->
      <div class="filter-select-wrap">
        <select v-model="selectedMember" class="filter-select">
          <option value="">全家成员</option>
          <option v-for="m in members" :key="m.id" :value="m.id">
            {{ m.display_name }} ({{ m.placeholder }})
          </option>
        </select>
      </div>

      <!-- 险种大类下拉 -->
      <div class="filter-select-wrap">
        <select v-model="selectedCategory" class="filter-select">
          <option v-for="c in categories" :key="c.key" :value="c.key">
            {{ c.label }}
          </option>
        </select>
      </div>

      <!-- 视图切换 (卡片 vs 列表) -->
      <div class="view-switch">
        <button
          class="view-btn"
          :class="{ active: viewMode === 'grid' }"
          @click="viewMode = 'grid'"
          title="卡片视图"
        >
          <LayoutGrid :size="16" />
        </button>
        <button
          class="view-btn"
          :class="{ active: viewMode === 'table' }"
          @click="viewMode = 'table'"
          title="列表视图"
        >
          <List :size="16" />
        </button>
      </div>
    </div>

    <!-- 状态切换 Tab -->
    <div class="status-tab-bar">
      <button
        v-for="tab in statusTabs"
        :key="tab.key"
        class="status-tab"
        :class="{ active: selectedStatus === tab.key }"
        @click="selectedStatus = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- 保单网格卡片视图 -->
    <div v-if="loading" class="loading-state">
      正在加载保单库...
    </div>
    <div v-else-if="policies.length === 0" class="empty-state glass">
      <ShieldCheck :size="48" class="empty-icon" />
      <h3 class="empty-title">暂无匹配保单</h3>
      <p class="empty-desc">你可以拖拽上传保单 PDF 或扫描件建档</p>
      <button class="btn-primary" @click="router.push('/import')">
        <Plus :size="16" /> 立即上传
      </button>
    </div>

    <!-- 1. 卡片视图 -->
    <div v-else-if="viewMode === 'grid'" class="policy-grid">
      <div
        v-for="policy in policies"
        :key="policy.id"
        class="policy-card glass-subtle"
        @click="router.push(`/policies/${policy.id}`)"
      >
        <div class="card-header">
          <div class="insurer-tag">{{ policy.insurer }}</div>
          <span class="status-badge" :class="getStatusBadge(policy.status).class">
            {{ getStatusBadge(policy.status).text }}
          </span>
        </div>

        <h3 class="card-title">{{ policy.product_name }}</h3>
        <div class="card-category">{{ getCategoryLabel(policy.category) }}</div>

        <!-- 被保人标签 -->
        <div class="member-chips-line">
          <span
            v-for="m in policy.insured_members || []"
            :key="m.id"
            class="member-chip"
            :style="{ borderColor: m.color, color: m.color }"
          >
            <User :size="12" /> {{ m.display_name }}
          </span>
          <span v-if="!policy.insured_members?.length" class="member-chip-empty">
            未关联成员
          </span>
        </div>

        <!-- 关键数字 -->
        <div class="card-figures">
          <div class="fig-item">
            <span class="fig-label">基本保额</span>
            <span class="fig-val fig-ok">{{ formatMoney(policy.sum_insured_cents) }}</span>
          </div>
          <div class="fig-item">
            <span class="fig-label">首年/年交保费</span>
            <span class="fig-val">{{ formatMoney(policy.premium_cents) }}</span>
          </div>
        </div>

        <div class="card-footer">
          <span class="dates-range">
            <Calendar :size="13" /> {{ policy.effective_date || '未录入' }} 至 {{ policy.expiry_date || '终身' }}
          </span>
          <ChevronRight :size="16" class="arrow-icon" />
        </div>
      </div>
    </div>

    <!-- 2. 列表视图 -->
    <div v-else class="policy-table-wrap glass">
      <table class="policy-table">
        <thead>
          <tr>
            <th>保险公司 / 产品名称</th>
            <th>险种分类</th>
            <th>被保险人</th>
            <th class="num-col">基本保额</th>
            <th class="num-col">保费</th>
            <th>保障期间</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="policy in policies"
            :key="policy.id"
            class="table-row"
            @click="router.push(`/policies/${policy.id}`)"
          >
            <td>
              <div class="tbl-insurer">{{ policy.insurer }}</div>
              <div class="tbl-product">{{ policy.product_name }}</div>
            </td>
            <td>{{ getCategoryLabel(policy.category) }}</td>
            <td>
              <div class="tbl-members">
                <span
                  v-for="m in policy.insured_members || []"
                  :key="m.id"
                  class="member-chip small"
                  :style="{ borderColor: m.color, color: m.color }"
                >
                  {{ m.display_name }}
                </span>
              </div>
            </td>
            <td class="num-col tbl-money-ok">{{ formatMoney(policy.sum_insured_cents) }}</td>
            <td class="num-col">{{ formatMoney(policy.premium_cents) }}</td>
            <td class="tbl-date">{{ policy.effective_date || '-' }} ~ {{ policy.expiry_date || '终身' }}</td>
            <td>
              <span class="status-badge" :class="getStatusBadge(policy.status).class">
                {{ getStatusBadge(policy.status).text }}
              </span>
            </td>
            <td>
              <button class="tbl-action-btn" @click.stop="router.push(`/policies/${policy.id}`)">
                详情
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.policy-page-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.page-title {
  margin: 0 0 4px;
  font-size: var(--fs-24);
  font-weight: 700;
  color: var(--text);
}

.page-desc {
  margin: 0;
  font-size: var(--fs-14);
  color: var(--text-muted);
}

.btn-primary {
  background: var(--ok);
  color: white;
  border: none;
  padding: 8px 18px;
  border-radius: var(--r-control);
  font-weight: 600;
  font-size: var(--fs-14);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  transition: opacity 0.2s ease;
}

.btn-primary:hover {
  opacity: 0.9;
}

.filter-toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: var(--r-control);
  margin-bottom: 16px;
}

.search-box {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon {
  position: absolute;
  left: 12px;
  color: var(--text-muted);
}

.search-input {
  width: 100%;
  padding: 8px 12px 8px 36px;
  border-radius: var(--r-control);
  border: 1px solid var(--glass-stroke);
  background: var(--c-paper);
  color: var(--text);
  font-size: var(--fs-14);
  outline: none;
}

.search-input:focus {
  border-color: var(--ok);
  outline: 2px solid var(--ok);
}

.filter-select {
  padding: 8px 12px;
  border-radius: var(--r-control);
  border: 1px solid var(--glass-stroke);
  background: var(--c-paper);
  color: var(--text);
  font-size: var(--fs-13);
  outline: none;
  cursor: pointer;
}

.view-switch {
  display: flex;
  gap: 4px;
  background: var(--glass-fill-strong);
  padding: 3px;
  border-radius: var(--r-control);
}

.view-btn {
  background: transparent;
  border: none;
  color: var(--text-muted);
  padding: 5px 8px;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
}

.view-btn.active {
  background: var(--c-paper);
  color: var(--ok);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.status-tab-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.status-tab {
  background: transparent;
  border: 1px solid transparent;
  padding: 6px 14px;
  border-radius: var(--r-badge);
  font-size: var(--fs-13);
  color: var(--text-muted);
  cursor: pointer;
}

.status-tab.active {
  background: var(--glass-fill-strong);
  border-color: var(--glass-stroke);
  color: var(--ok);
  font-weight: 600;
}

/* 网格卡片 */
.policy-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 20px;
}

.policy-card {
  padding: 20px;
  border-radius: var(--r-panel);
  border: 1px solid var(--glass-stroke);
  cursor: pointer;
  display: flex;
  flex-direction: column;
  transition: border-color var(--dur-fast) ease, background var(--dur-fast) ease;
}

.policy-card:hover {
  border-color: var(--ok);
  background: var(--glass-fill-strong);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.insurer-tag {
  font-size: var(--fs-12);
  color: var(--text-muted);
  font-weight: 500;
}

.card-title {
  margin: 0 0 4px;
  font-size: var(--fs-18);
  font-weight: 600;
  color: var(--text);
}

.card-category {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-bottom: 12px;
}

.member-chips-line {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}

.member-chip {
  font-size: var(--fs-12);
  padding: 2px 8px;
  border-radius: var(--r-badge);
  border: 1px solid;
  background: var(--glass-fill);
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.member-chip-empty {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.card-figures {
  display: grid;
  grid-template-columns: 1fr 1fr;
  padding: 12px 0;
  border-top: 1px solid var(--glass-stroke);
  border-bottom: 1px solid var(--glass-stroke);
  margin-bottom: 12px;
}

.fig-item {
  display: flex;
  flex-direction: column;
}

.fig-label {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-bottom: 2px;
}

.fig-val {
  font-size: var(--fs-16);
  font-weight: 700;
  color: var(--text);
  font-variant-numeric: tabular-nums;
}

.fig-ok {
  color: var(--ok);
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.dates-range {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.arrow-icon {
  color: var(--text-muted);
}

/* 状态徽标 */
.status-badge {
  font-size: var(--fs-12);
  padding: 2px 8px;
  border-radius: var(--r-badge);
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

/* 列表表格 */
.policy-table-wrap {
  border-radius: var(--r-panel);
  overflow: hidden;
  border: 1px solid var(--glass-stroke);
}

.policy-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-14);
}

.policy-table th {
  padding: 12px 16px;
  text-align: left;
  background: var(--glass-fill-strong);
  color: var(--text-muted);
  font-weight: 500;
  font-size: var(--fs-13);
  border-bottom: 1px solid var(--glass-stroke);
}

.policy-table td {
  padding: 14px 16px;
  border-bottom: 1px solid var(--glass-stroke);
}

.table-row {
  cursor: pointer;
  transition: background 0.15s ease;
}

.table-row:hover {
  background: var(--glass-fill-strong);
}

.num-col {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.tbl-insurer {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.tbl-product {
  font-weight: 600;
  color: var(--text);
}

.tbl-money-ok {
  color: var(--ok);
  font-weight: 600;
}

.tbl-date {
  font-size: var(--fs-13);
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.tbl-action-btn {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  padding: 4px 10px;
  border-radius: var(--r-control);
  cursor: pointer;
  color: var(--text);
  font-size: var(--fs-12);
}

.empty-state {
  text-align: center;
  padding: 60px 24px;
  border-radius: var(--r-panel);
}

.empty-icon {
  color: var(--text-muted);
  margin-bottom: 16px;
}

.empty-title {
  margin: 0 0 8px;
  font-size: var(--fs-18);
  color: var(--text);
}

.empty-desc {
  margin: 0 0 20px;
  color: var(--text-muted);
  font-size: var(--fs-14);
}

.loading-state {
  text-align: center;
  padding: 40px;
  color: var(--text-muted);
}
</style>
