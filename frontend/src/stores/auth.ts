import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const configured = ref(false)
  const authenticated = ref(false)
  // 首次状态检查是否已完成：路由守卫需要等这个变 true 才放行，避免刷新瞬间误判为未登录
  const checked = ref(false)

  async function checkStatus() {
    try {
      const res = await fetch('/api/auth/status')
      if (res.ok) {
        const data = await res.json()
        configured.value = !!data.configured
        authenticated.value = !!data.authenticated
      }
    } catch {
      // 网络异常时保持现状，不强行判定为未登录，避免闪烁
    } finally {
      checked.value = true
    }
  }

  async function setup(password: string): Promise<{ ok: boolean; message?: string }> {
    const res = await fetch('/api/auth/setup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (res.ok) {
      configured.value = true
      authenticated.value = true
      return { ok: true }
    }
    const err = await res.json().catch(() => null)
    return { ok: false, message: err?.error?.message || '设置失败' }
  }

  async function login(password: string): Promise<{ ok: boolean; message?: string }> {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (res.ok) {
      authenticated.value = true
      return { ok: true }
    }
    const err = await res.json().catch(() => null)
    return { ok: false, message: err?.error?.message || '登录失败' }
  }

  async function logout() {
    try {
      await fetch('/api/auth/logout', { method: 'POST' })
    } finally {
      authenticated.value = false
    }
  }

  return {
    configured,
    authenticated,
    checked,
    checkStatus,
    setup,
    login,
    logout,
  }
})
