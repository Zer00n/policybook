<script setup lang="ts">
import { ref, onMounted } from 'vue'
import {
  Settings as SettingsIcon,
  Send,
  RefreshCw,
  Calendar,
  Copy,
  Check,
  Shield,
  RotateCcw,
  Save,
} from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
const settingsData = ref<any>(null)
const loading = ref(false)
const testResult = ref<any>(null)
const testingModel = ref(false)

// Calendar ICS state
const calendarSettings = ref<{ token: string; ics_url: string; enabled: boolean } | null>(null)
const copied = ref(false)
const resettingToken = ref(false)

// Coverage references state
const references = ref<Record<string, number>>({
  death: 100, // 万元
  critical_illness: 50,
  medical: 300,
  accident: 100,
  income_loss: 20,
  pension: 50,
})
const savingRefs = ref(false)
const saveSuccess = ref(false)

async function fetchSettings() {
  loading.value = true
  try {
    const [res, calRes, refRes] = await Promise.all([
      fetch('/api/settings'),
      fetch('/api/settings/calendar'),
      fetch('/api/settings/coverage-reference'),
    ])
    if (res.ok) {
      settingsData.value = await res.json()
    }
    if (calRes.ok) {
      calendarSettings.value = await calRes.json()
    }
    if (refRes.ok) {
      const refData = await refRes.json()
      const defRefs = refData.references?.default || {}
      references.value = {
        death: Math.round((defRefs.death || 1000000) / 10000),
        critical_illness: Math.round((defRefs.critical_illness || 500000) / 10000),
        medical: Math.round((defRefs.medical || 3000000) / 10000),
        accident: Math.round((defRefs.accident || 1000000) / 10000),
        income_loss: Math.round((defRefs.income_loss || 200000) / 10000),
        pension: Math.round((defRefs.pension || 500000) / 10000),
      }
    }
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

function getFullIcsUrl(): string {
  if (!calendarSettings.value?.ics_url) return ''
  const origin = window.location.origin
  return `${origin}${calendarSettings.value.ics_url}`
}

async function copyIcsUrl() {
  const url = getFullIcsUrl()
  if (!url) return
  try {
    await navigator.clipboard.writeText(url)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 2000)
  } catch (err) {
    console.error('Failed to copy ICS url:', err)
  }
}

async function resetCalendarToken() {
  if (!confirm('重置日历 Token 后，已有手机日历订阅将失效，需重新配置订阅链接。确定重置吗？')) {
    return
  }
  resettingToken.value = true
  try {
    const res = await fetch('/api/settings/calendar/reset-token', { method: 'POST' })
    if (res.ok) {
      const data = await res.json()
      calendarSettings.value = {
        token: data.token,
        ics_url: data.ics_url,
        enabled: true,
      }
    }
  } catch (err) {
    console.error('Failed to reset token:', err)
  } finally {
    resettingToken.value = false
  }
}

async function saveReferences() {
  savingRefs.value = true
  saveSuccess.value = false
  try {
    const payload = {
      member_id: 'default',
      references: {
        death: references.value.death * 10000,
        critical_illness: references.value.critical_illness * 10000,
        medical: references.value.medical * 10000,
        accident: references.value.accident * 10000,
        income_loss: references.value.income_loss * 10000,
        pension: references.value.pension * 10000,
      },
    }
    const res = await fetch('/api/settings/coverage-reference', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    if (res.ok) {
      saveSuccess.value = true
      setTimeout(() => {
        saveSuccess.value = false
      }, 2500)
    }
  } catch (err) {
    console.error('Failed to save references:', err)
  } finally {
    savingRefs.value = false
  }
}

async function testModel(modelKey?: string) {
  testingModel.value = true
  testResult.value = null
  const modelLabel = settingsData.value?.models?.find((m: any) => m.key === modelKey)?.display_name
    || modelKey || '默认模型'
  try {
    const res = await fetch('/api/settings/models/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_key: modelKey }),
    })
    const data = await res.json()
    if (res.ok) {
      testResult.value = { ok: true, display_name: data.display_name || modelLabel, latency_ms: data.latency_ms }
    } else {
      testResult.value = { ok: false, display_name: modelLabel, error: data?.error?.message || '连通测试失败' }
    }
  } catch (err: any) {
    testResult.value = { ok: false, display_name: modelLabel, error: err.message || '网络请求异常' }
  } finally {
    testingModel.value = false
  }
}

onMounted(() => {
  fetchSettings()
})
</script>

<template>
  <div class="settings-page">
    <header class="page-header">
      <h1 class="page-title">系统与模型设置</h1>
      <p class="page-subtitle">配置日历订阅、六维保障参考保额、火山方舟模型端点与显示外观</p>
    </header>

    <!-- 界面偏好 -->
    <div class="glass panel">
      <h2 class="panel-title">界面偏好</h2>
      <div class="setting-row">
        <div>
          <div class="setting-name">主题模式</div>
          <div class="setting-desc">当前：{{ themeStore.themeMode }} ({{ themeStore.isDark ? '深色' : '浅色' }})</div>
        </div>
        <div class="btn-group">
          <button
            class="btn-secondary"
            :class="{ active: themeStore.themeMode === 'light' }"
            @click="themeStore.setThemeMode('light')"
          >
            浅色
          </button>
          <button
            class="btn-secondary"
            :class="{ active: themeStore.themeMode === 'dark' }"
            @click="themeStore.setThemeMode('dark')"
          >
            深色
          </button>
          <button
            class="btn-secondary"
            :class="{ active: themeStore.themeMode === 'system' }"
            @click="themeStore.setThemeMode('system')"
          >
            跟随系统
          </button>
        </div>
      </div>

      <div class="setting-row">
        <div>
          <div class="setting-name">简洁模式 (低功耗)</div>
          <div class="setting-desc">关闭毛玻璃滤镜与环境光动画，适合 NAS 弱性能芯片</div>
        </div>
        <button
          class="btn-secondary"
          :class="{ 'btn-primary': themeStore.isLite }"
          @click="themeStore.toggleLite"
        >
          {{ themeStore.isLite ? '已启用简洁模式' : '已开启平滑效果' }}
        </button>
      </div>
    </div>

    <!-- 日历订阅 (ICS) (DEV-GUIDE 10.7 & PRD 3.13) -->
    <div class="glass panel">
      <div class="panel-header">
        <div class="header-left">
          <Calendar :size="18" class="text-ok" />
          <h2 class="panel-title">保单日历订阅 (RFC 5545 iCalendar)</h2>
        </div>
        <button
          class="btn-secondary"
          :disabled="resettingToken"
          @click="resetCalendarToken"
          title="重置安全订阅 Token"
        >
          <RotateCcw :size="14" />
          重置 Token
        </button>
      </div>

      <p class="panel-desc">
        在手机日历（iPhone、华为、小米等）或电脑（Mac Calendar、Outlook）中添加此网络日历订阅，即可自动同步保单到期提醒、等待期届满日程与续期年缴提醒。该地址采用独立随机 Token 鉴权（红线 11 守护）。
      </p>

      <div v-if="calendarSettings" class="ics-box">
        <div class="ics-url-display">
          <input
            readonly
            :value="getFullIcsUrl()"
            class="form-input ics-input"
          />
          <button class="btn-primary copy-btn" @click="copyIcsUrl">
            <Check v-if="copied" :size="14" />
            <Copy v-else :size="14" />
            {{ copied ? '已复制到剪贴板' : '复制订阅链接' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 六维保障参考保额配置 (DEV-GUIDE 8.8 & PRD 3.11) -->
    <div class="glass panel">
      <div class="panel-header">
        <div class="header-left">
          <Shield :size="18" class="text-ok" />
          <h2 class="panel-title">六维保障基准参考保额</h2>
        </div>
        <button
          class="btn-primary"
          :disabled="savingRefs"
          @click="saveReferences"
        >
          <Check v-if="saveSuccess" :size="14" />
          <Save v-else :size="14" />
          {{ saveSuccess ? '保存成功' : (savingRefs ? '保存中...' : '保存配置') }}
        </button>
      </div>

      <p class="panel-desc">
        设置家庭保单覆盖雷达图的 100% 充分覆盖基准值（单位：万元）。界面雷达将以此基准衡量实际有效保额并封顶 120% 渲染。
      </p>

      <div class="ref-grid">
        <div class="ref-item">
          <label class="ref-label">身故保障 (寿险)</label>
          <div class="ref-input-group">
            <input v-model.number="references.death" type="number" min="0" class="form-input" />
            <span class="ref-unit">万元</span>
          </div>
        </div>

        <div class="ref-item">
          <label class="ref-label">重疾保障 (确诊给付)</label>
          <div class="ref-input-group">
            <input v-model.number="references.critical_illness" type="number" min="0" class="form-input" />
            <span class="ref-unit">万元</span>
          </div>
        </div>

        <div class="ref-item">
          <label class="ref-label">医疗费用 (百万/意外医疗)</label>
          <div class="ref-input-group">
            <input v-model.number="references.medical" type="number" min="0" class="form-input" />
            <span class="ref-unit">万元</span>
          </div>
        </div>

        <div class="ref-item">
          <label class="ref-label">意外保障 (伤残/意外身故)</label>
          <div class="ref-input-group">
            <input v-model.number="references.accident" type="number" min="0" class="form-input" />
            <span class="ref-unit">万元</span>
          </div>
        </div>

        <div class="ref-item">
          <label class="ref-label">收入中断 (津贴/收入替代)</label>
          <div class="ref-input-group">
            <input v-model.number="references.income_loss" type="number" min="0" class="form-input" />
            <span class="ref-unit">万元</span>
          </div>
        </div>

        <div class="ref-item">
          <label class="ref-label">养老储备 (年金/增额终身寿)</label>
          <div class="ref-input-group">
            <input v-model.number="references.pension" type="number" min="0" class="form-input" />
            <span class="ref-unit">万元</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 模型端点配置 -->
    <div class="glass panel">
      <div class="panel-header">
        <h2 class="panel-title">模型端点配置 (config/models.yaml)</h2>
        <button class="btn-secondary" @click="fetchSettings">
          <RefreshCw :size="14" />
          刷新
        </button>
      </div>

      <div v-if="settingsData?.models" class="models-list">
        <div v-for="m in settingsData.models" :key="m.key" class="model-card">
          <div class="model-info">
            <div class="model-name">
              {{ m.display_name }}
              <span v-if="m.is_default" class="badge badge--ok">默认</span>
            </div>
            <div class="model-id">{{ m.model_id }} · 提供商: {{ m.provider }}</div>
          </div>
          <button
            class="btn-primary"
            :disabled="testingModel"
            @click="testModel(m.key)"
          >
            <Send :size="14" />
            连通测试
          </button>
        </div>
      </div>

      <div v-if="testResult" class="test-feedback">
        <div v-if="testResult.ok" class="badge badge--ok">
          <span class="badge-dot"></span> {{ testResult.display_name }} 测试通过 (耗时 {{ testResult.latency_ms }}ms)
        </div>
        <div v-else class="badge badge--pending">
          <span class="badge-dot"></span> {{ testResult.display_name }}: {{ testResult.error }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.page-title {
  font-size: var(--fs-28);
  font-weight: 700;
}

.page-subtitle {
  font-size: var(--fs-14);
  color: var(--text-muted);
}

.panel {
  padding: var(--sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.panel-title {
  font-size: var(--fs-19);
  font-weight: 600;
  margin: 0;
}

.panel-desc {
  font-size: var(--fs-12);
  color: var(--text-muted);
  line-height: 1.6;
  margin: 0;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--glass-stroke);
}

.setting-row:last-child {
  border-bottom: none;
}

.setting-name {
  font-weight: 600;
  font-size: var(--fs-14);
}

.setting-desc {
  font-size: var(--fs-12);
  color: var(--text-muted);
  margin-top: 2px;
}

.btn-group {
  display: flex;
  gap: var(--sp-2);
}

.btn-secondary.active {
  background: var(--ok);
  color: #fff;
  border-color: var(--ok);
}

/* ICS Box */
.ics-box {
  margin-top: var(--sp-1);
}

.ics-url-display {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
}

.ics-input {
  font-family: monospace;
  font-size: var(--fs-12);
  background: var(--glass-fill-strong);
  color: var(--text-muted);
  flex: 1;
}

.copy-btn {
  white-space: nowrap;
}

/* Reference Grid */
.ref-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--sp-3);
  margin-top: var(--sp-2);
}

.ref-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.ref-label {
  font-size: var(--fs-12);
  color: var(--text-muted);
  font-weight: 600;
}

.ref-input-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ref-unit {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

/* Models */
.models-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.model-card {
  padding: var(--sp-3) var(--sp-4);
  background: var(--glass-fill-strong);
  border-radius: var(--r-control);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1px solid var(--glass-stroke);
}

.model-name {
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}

.model-id {
  font-size: var(--fs-12);
  color: var(--text-muted);
  font-family: monospace;
  margin-top: 2px;
}

.test-feedback {
  margin-top: var(--sp-2);
}

@media (max-width: 768px) {
  .ref-grid {
    grid-template-columns: 1fr;
  }
  .ics-url-display {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
