<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  Users,
  Plus,
  Edit2,
  Trash2,
  ShieldCheck,
  Lock,
  UserCheck,
} from 'lucide-vue-next'

interface Member {
  id: string
  display_name: string
  relation: string
  birth_year: number | null
  gender: string | null
  occupation: string | null
  city: string | null
  social_insurance: string | null
  color: string
  placeholder: string
  real_name: string | null
  created_at: string
}

const members = ref<Member[]>([])
const loading = ref(false)
const showModal = ref(false)
const isEditing = ref(false)
const editingId = ref<string | null>(null)

const relations = ['本人', '配偶', '子女', '父母', '其他']
const genders = ['男', '女', '其他']
const siTypes = ['职工', '居民', '无', '未知']
const presetColors = ['#2A8F82', '#14233A', '#C98217', '#5E54C9', '#3B82F6', '#EC4899']

const form = ref({
  display_name: '',
  relation: '本人',
  real_name: '',
  birth_year: 1990,
  gender: '男',
  occupation: '',
  city: '北京',
  social_insurance: '职工',
  color: '#2A8F82',
})

async function fetchMembers() {
  loading.value = true
  try {
    const res = await fetch('/api/members')
    if (res.ok) {
      members.value = await res.json()
    }
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

function openAddModal() {
  isEditing.value = false
  editingId.value = null
  form.value = {
    display_name: '',
    relation: '本人',
    real_name: '',
    birth_year: 1990,
    gender: '男',
    occupation: '',
    city: '北京',
    social_insurance: '职工',
    color: '#2A8F82',
  }
  showModal.value = true
}

function openEditModal(m: Member) {
  isEditing.value = true
  editingId.value = m.id
  form.value = {
    display_name: m.display_name,
    relation: m.relation,
    real_name: m.real_name || '',
    birth_year: m.birth_year || 1990,
    gender: m.gender || '男',
    occupation: m.occupation || '',
    city: m.city || '北京',
    social_insurance: m.social_insurance || '职工',
    color: m.color || '#2A8F82',
  }
  showModal.value = true
}

async function submitForm() {
  if (!form.value.display_name.trim()) return

  if (isEditing.value && editingId.value) {
    // 更新
    await fetch(`/api/members/${editingId.value}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
    })
  } else {
    // 新增
    await fetch('/api/members', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
    })
  }

  showModal.value = false
  fetchMembers()
}

async function deleteMember(id: string) {
  if (confirm('确定删除该家庭成员记录吗？')) {
    await fetch(`/api/members/${id}`, { method: 'DELETE' })
    fetchMembers()
  }
}

onMounted(() => {
  fetchMembers()
})
</script>

<template>
  <div class="members-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">家庭成员档案</h1>
        <p class="page-subtitle">
          维护家庭成员真实姓名（仅本地加密存储，用于精准脱敏）与专属占位符代号
        </p>
      </div>

      <button class="btn-primary" @click="openAddModal">
        <Plus :size="16" />
        添加家庭成员
      </button>
    </header>

    <!-- 成员卡片网格 -->
    <div v-if="members.length > 0" class="members-grid">
      <div
        v-for="m in members"
        :key="m.id"
        class="glass member-card"
      >
        <div class="card-top">
          <div class="avatar" :style="{ backgroundColor: m.color }">
            {{ m.display_name.slice(0, 1) }}
          </div>
          <div class="member-primary">
            <div class="name-row">
              <span class="display-name">{{ m.display_name }}</span>
              <span class="badge badge--ok">{{ m.placeholder }}</span>
              <span class="relation-tag">{{ m.relation }}</span>
            </div>
            <div class="meta-row">
              <span>{{ m.birth_year ? `${m.birth_year} 年` : '未知年份' }}</span>
              <span>·</span>
              <span>{{ m.gender || '未知性别' }}</span>
              <span>·</span>
              <span>{{ m.city || '未知城市' }}</span>
            </div>
          </div>

          <div class="card-actions">
            <button class="icon-btn-small" @click="openEditModal(m)" title="编辑">
              <Edit2 :size="14" />
            </button>
            <button class="icon-btn-small btn-del" @click="deleteMember(m.id)" title="删除">
              <Trash2 :size="14" />
            </button>
          </div>
        </div>

        <div class="card-details">
          <div class="detail-item">
            <span class="detail-label">社保类型：</span>
            <span class="detail-val">{{ m.social_insurance || '未知' }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">职业描述：</span>
            <span class="detail-val">{{ m.occupation || '未填写' }}</span>
          </div>
          <div class="detail-item encrypted-box">
            <span class="detail-label">
              <Lock :size="12" /> 脱敏匹配真实姓名：
            </span>
            <span class="detail-val text-realname">
              {{ m.real_name || '未登记真实姓名' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="glass empty-panel">
      <Users :size="48" class="empty-icon" />
      <h3>暂无家庭成员档案</h3>
      <p>添加家庭成员并登记真实姓名，上传保单时系统会自动将真实姓名精确替换为占位符。</p>
      <button class="btn-primary" @click="openAddModal" style="margin-top: var(--sp-3)">
        <Plus :size="16" />
        添加第一位家庭成员
      </button>
    </div>

    <!-- 添加/编辑弹窗 -->
    <div v-if="showModal" class="modal-overlay" @click.self="showModal = false">
      <div class="glass modal-dialog">
        <h2 class="dialog-title">{{ isEditing ? '编辑家庭成员' : '添加家庭成员' }}</h2>

        <form @submit.prevent="submitForm" class="dialog-form">
          <div class="form-row">
            <div class="form-group">
              <label class="form-label">显示名 *</label>
              <input v-model="form.display_name" required class="form-input" placeholder="如：爸爸、大宝" />
            </div>
            <div class="form-group">
              <label class="form-label">关系 *</label>
              <select v-model="form.relation" class="form-input">
                <option v-for="r in relations" :key="r" :value="r">{{ r }}</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              真实姓名
              <span class="form-hint">（仅保存在 NAS 本地，用于解析时精确替换，严禁发给模型）</span>
            </label>
            <input v-model="form.real_name" class="form-input" placeholder="如：张伟明" />
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">出生年份</label>
              <input v-model.number="form.birth_year" type="number" class="form-input" placeholder="1990" />
            </div>
            <div class="form-group">
              <label class="form-label">性别</label>
              <select v-model="form.gender" class="form-input">
                <option v-for="g in genders" :key="g" :value="g">{{ g }}</option>
              </select>
            </div>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label class="form-label">所在城市</label>
              <input v-model="form.city" class="form-input" placeholder="北京" />
            </div>
            <div class="form-group">
              <label class="form-label">社保类型</label>
              <select v-model="form.social_insurance" class="form-input">
                <option v-for="si in siTypes" :key="si" :value="si">{{ si }}</option>
              </select>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">职业描述</label>
            <input v-model="form.occupation" class="form-input" placeholder="如：软件工程师（办公室工作）" />
          </div>

          <div class="form-group">
            <label class="form-label">头像标识色</label>
            <div class="color-picker-row">
              <button
                type="button"
                v-for="c in presetColors"
                :key="c"
                class="color-dot"
                :style="{ backgroundColor: c }"
                :class="{ selected: form.color === c }"
                @click="form.color = c"
              ></button>
            </div>
          </div>

          <div class="dialog-actions">
            <button type="button" class="btn-secondary" @click="showModal = false">取消</button>
            <button type="submit" class="btn-primary">保存成员</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<style scoped>
.members-page {
  max-width: 1080px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
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

.members-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--sp-4);
}

.member-card {
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.card-top {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
}

.avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  color: #fff;
  font-size: var(--fs-19);
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.member-primary {
  flex: 1;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.display-name {
  font-size: var(--fs-16);
  font-weight: 700;
}

.relation-tag {
  font-size: var(--fs-12);
  color: var(--text-muted);
  background: color-mix(in oklch, var(--text) 8%, transparent);
  padding: 1px 6px;
  border-radius: var(--r-control);
}

.meta-row {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-top: 2px;
  display: flex;
  gap: 4px;
}

.card-actions {
  display: flex;
  gap: var(--sp-1);
}

.icon-btn-small {
  width: 28px;
  height: 28px;
  padding: 0;
  border-radius: var(--r-control);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  color: var(--text-muted);
}

.icon-btn-small:hover {
  color: var(--text);
  background: var(--glass-fill-strong);
}

.icon-btn-small.btn-del:hover {
  color: var(--risk);
  border-color: var(--risk);
}

.card-details {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  font-size: var(--fs-14);
  border-top: 1px solid var(--glass-stroke);
  padding-top: var(--sp-2);
}

.detail-item {
  display: flex;
  align-items: center;
}

.detail-label {
  color: var(--text-muted);
  font-size: var(--fs-12);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  width: 140px;
}

.detail-val {
  font-size: var(--fs-14);
  font-weight: 500;
}

.encrypted-box {
  background: color-mix(in oklch, var(--ok) 8%, transparent);
  padding: 4px 8px;
  border-radius: var(--r-control);
  margin-top: 4px;
}

.text-realname {
  color: var(--ok);
  font-weight: 600;
}

/* 空状态 */
.empty-panel {
  padding: var(--sp-8);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--sp-2);
}

.empty-icon {
  color: var(--text-muted);
  margin-bottom: var(--sp-2);
}

/* 弹窗 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
}

.modal-dialog {
  max-width: 520px;
  width: 90%;
  padding: var(--sp-5);
  background: var(--glass-fill-strong);
  box-shadow: var(--glass-shadow);
}

.dialog-title {
  font-size: var(--fs-19);
  font-weight: 700;
  margin-bottom: var(--sp-4);
}

.dialog-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
}

.form-hint {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 400;
}

.color-picker-row {
  display: flex;
  gap: var(--sp-2);
}

.color-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 2px solid transparent;
  cursor: pointer;
  padding: 0;
}

.color-dot.selected {
  border-color: #fff;
  box-shadow: 0 0 0 2px var(--ok);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-3);
  margin-top: var(--sp-3);
}
</style>
