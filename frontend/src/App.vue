<script setup lang="ts">
import AppShell from '@/components/shell/AppShell.vue'
import LoginPage from '@/pages/auth/LoginPage.vue'
import { onMounted } from 'vue'
import { useThemeStore } from '@/stores/theme'
import { useAuthStore } from '@/stores/auth'

const themeStore = useThemeStore()
const authStore = useAuthStore()

onMounted(() => {
  themeStore.updateTheme()
  authStore.checkStatus()
})
</script>

<template>
  <LoginPage v-if="!authStore.authenticated" />
  <AppShell v-else />
</template>
