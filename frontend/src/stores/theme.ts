import { defineStore } from 'pinia'
import { ref, watch, onMounted } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

export const useThemeStore = defineStore('theme', () => {
  const themeMode = ref<ThemeMode>(
    (localStorage.getItem('policybook_theme') as ThemeMode) || 'system'
  )

  const isDark = ref(false)
  
  // 简洁模式：硬件较弱时默认启用
  const savedLite = localStorage.getItem('policybook_lite')
  const defaultLite = savedLite !== null 
    ? savedLite === 'true' 
    : (typeof navigator !== 'undefined' && (navigator.hardwareConcurrency || 8) <= 4)
  const isLite = ref(defaultLite)

  function updateTheme() {
    let dark = false
    if (themeMode.value === 'system') {
      dark = window.matchMedia('(prefers-color-scheme: dark)').matches
    } else {
      dark = themeMode.value === 'dark'
    }
    isDark.value = dark

    const root = document.documentElement
    if (dark) {
      root.setAttribute('data-theme', 'dark')
    } else {
      root.removeAttribute('data-theme')
    }

    if (isLite.value) {
      root.setAttribute('data-lite', 'true')
    } else {
      root.removeAttribute('data-lite')
    }
  }

  function setThemeMode(mode: ThemeMode) {
    themeMode.value = mode
    localStorage.setItem('policybook_theme', mode)
    updateTheme()
  }

  function toggleLite() {
    isLite.value = !isLite.value
    localStorage.setItem('policybook_lite', String(isLite.value))
    updateTheme()
  }

  function toggleTheme() {
    if (isDark.value) {
      setThemeMode('light')
    } else {
      setThemeMode('dark')
    }
  }

  // 监听系统主题变化
  if (typeof window !== 'undefined') {
    const media = window.matchMedia('(prefers-color-scheme: dark)')
    media.addEventListener('change', () => {
      if (themeMode.value === 'system') {
        updateTheme()
      }
    })
  }

  watch([themeMode, isLite], () => {
    updateTheme()
  })

  return {
    themeMode,
    isDark,
    isLite,
    setThemeMode,
    toggleTheme,
    toggleLite,
    updateTheme,
  }
})
