import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { router } from './router'
import { useAuthStore } from '@/stores/auth'

import './styles/tokens.css'
import './styles/glass.css'
import './styles/motion.css'
import './styles/base.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

// 全局 401 拦截：会话过期或未登录时，把 Pinia 的 authenticated 置为 false，
// App.vue 会据此自动切回登录页（无需硬跳转刷新页面）。
// 已知缺口：ImportPage.vue 的上传进度用原生 EventSource 接 SSE，不经过 fetch，
// 因此这里捕获不到它的 401（影响面很小：需要 session 恰好在上传任务进行中过期）。
const nativeFetch = window.fetch.bind(window)
window.fetch = async (...args: Parameters<typeof fetch>) => {
  const response = await nativeFetch(...args)
  const input = args[0]
  const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
  if (response.status === 401 && url.startsWith('/api/') && !url.startsWith('/api/auth/')) {
    useAuthStore(pinia).authenticated = false
  }
  return response
}

app.mount('#app')
