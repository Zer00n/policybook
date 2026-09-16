<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Settings as SettingsIcon, Send, RefreshCw } from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
const settingsData = ref<any>(null)
const loading = ref(false)
const testResult = ref<any>(null)
const testingModel = ref(false)

async function fetchSettings() {
  loading.value = true
  try {
    const res = await fetch('/api/settings')
    settingsData.value = await res.json()
  } catch (err) {
    console.error(err)
  } finally {
    loading.value = false
  }
}

async function testModel(modelKey?: string) {
  testingModel.value = true
  testResult.value = null
  try {
    const res = await fetch('/api/settings/models/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model_key: modelKey }),
    })
    testResult.value = await res.json()
  } catch (err: any) {
    testResult.value = { ok: false, error: err.message }
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
      <p class="page-subtitle">配置火山方舟模型端点、脱敏规则、家庭密码与显示外观</p>
    </header>

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

.panel-title {
  font-size: var(--fs-19);
  font-weight: 600;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-3) 0;
  border-bottom: 1px solid color-mix(in oklch, var(--text) 8%, transparent);
}

.setting-name {
  font-weight: 500;
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

.btn-group .btn-secondary.active {
  background: var(--ok);
  color: #fff;
  border-color: var(--ok);
}

.models-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.model-card {
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--r-control);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  display: flex;
  align-items: center;
  justify-content: space-between;
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
  font-variant-numeric: tabular-nums;
  margin-top: 2px;
}

.test-feedback {
  padding-top: var(--sp-2);
}
</style>
