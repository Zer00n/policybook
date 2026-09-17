<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ShieldCheck, Lock, Loader2 } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

const password = ref('')
const confirmPassword = ref('')
const submitting = ref(false)
const errorMsg = ref('')

onMounted(() => {
  if (!authStore.checked) {
    authStore.checkStatus()
  }
})

async function handleSubmit() {
  errorMsg.value = ''

  if (!authStore.configured) {
    if (password.value.length < 4) {
      errorMsg.value = '密码长度至少 4 位'
      return
    }
    if (password.value !== confirmPassword.value) {
      errorMsg.value = '两次输入的密码不一致'
      return
    }
    submitting.value = true
    const res = await authStore.setup(password.value)
    submitting.value = false
    if (!res.ok) {
      errorMsg.value = res.message || '设置失败'
    }
    return
  }

  submitting.value = true
  const res = await authStore.login(password.value)
  submitting.value = false
  if (!res.ok) {
    errorMsg.value = res.message || '登录失败'
    password.value = ''
  }
}
</script>

<template>
  <div class="login-page">
    <div class="aura" aria-hidden="true">
      <i></i>
    </div>

    <div class="login-card glass">
      <div class="brand">
        <div class="brand-icon">
          <ShieldCheck :size="32" class="brand-svg" />
        </div>
        <h1 class="brand-title">保单簿</h1>
        <p class="brand-subtitle">家庭保单管理与条款解读</p>
      </div>

      <form class="login-form" @submit.prevent="handleSubmit">
        <template v-if="!authStore.checked">
          <div class="checking-state">
            <Loader2 :size="18" class="spin" />
            <span>正在检查登录状态...</span>
          </div>
        </template>

        <template v-else>
          <h2 class="form-title">
            {{ authStore.configured ? '输入家庭密码登录' : '首次使用，设置家庭密码' }}
          </h2>

          <div class="form-group">
            <label class="form-label">
              <Lock :size="14" class="label-icon" />
              {{ authStore.configured ? '密码' : '设置密码' }}
            </label>
            <input
              v-model="password"
              type="password"
              class="form-input"
              :placeholder="authStore.configured ? '请输入家庭密码' : '至少 4 位，全家共用'"
              autofocus
              required
            />
          </div>

          <div v-if="!authStore.configured" class="form-group">
            <label class="form-label">
              <Lock :size="14" class="label-icon" />
              确认密码
            </label>
            <input
              v-model="confirmPassword"
              type="password"
              class="form-input"
              placeholder="再次输入密码"
              required
            />
          </div>

          <p v-if="errorMsg" class="form-error">{{ errorMsg }}</p>

          <button type="submit" class="btn-primary submit-btn" :disabled="submitting">
            <Loader2 v-if="submitting" :size="16" class="spin" />
            <span>{{ authStore.configured ? '登录' : '设置并登录' }}</span>
          </button>
        </template>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  background: var(--bg);
}

.login-card {
  width: min(380px, 90vw);
  padding: var(--sp-6) var(--sp-5);
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
  position: relative;
  z-index: 1;
}

.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--sp-2);
  text-align: center;
}

.brand-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--r-control);
  background: color-mix(in oklch, var(--ok) 18%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
}

.brand-svg {
  color: var(--ok);
}

.brand-title {
  font-size: var(--fs-23);
  font-weight: 700;
}

.brand-subtitle {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.checking-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  color: var(--text-muted);
  font-size: var(--fs-14);
  padding: var(--sp-5) 0;
}

.form-title {
  font-size: var(--fs-16);
  font-weight: 600;
  text-align: center;
  margin-bottom: var(--sp-1);
}

.label-icon {
  color: var(--text-muted);
}

.form-error {
  font-size: var(--fs-12);
  color: var(--risk);
}

.submit-btn {
  width: 100%;
  padding: var(--sp-3);
  font-size: var(--fs-14);
  margin-top: var(--sp-2);
}

.spin {
  animation: login-spin 1s linear infinite;
}

@keyframes login-spin {
  to { transform: rotate(360deg); }
}
</style>
