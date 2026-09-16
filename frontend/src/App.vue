<script setup lang="ts">
import AppShell from '@/components/shell/AppShell.vue'
import { onMounted } from 'vue'
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()

onMounted(() => {
  themeStore.updateTheme()
})
</script>

<template>
  <AppShell />
</template>
