<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Home,
  ShieldCheck,
  UploadCloud,
  MessageSquareQuote,
  Calculator,
  Compass,
  Users,
  Presentation,
  BarChart3,
  Settings,
  Palette,
  Sun,
  Moon,
  Zap,
  ZapOff,
} from 'lucide-vue-next'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const router = useRouter()
const themeStore = useThemeStore()

const navItems = [
  { path: '/', name: '家庭总览', icon: Home },
  { path: '/policies', name: '保单库', icon: ShieldCheck },
  { path: '/import', name: '上传建档', icon: UploadCloud },
  { path: '/ask', name: '条款问答', icon: MessageSquareQuote },
  { path: '/claim', name: '理赔模拟', icon: Calculator },
  { path: '/renewal', name: '续保顾问', icon: Compass },
  { path: '/members', name: '家庭成员', icon: Users },
  { path: '/reports', name: '报告导出', icon: Presentation },
  { path: '/eval', name: '测评看板', icon: BarChart3 },
  { path: '/settings', name: '系统设置', icon: Settings },
  { path: '/dev/styleguide', name: '设计系统', icon: Palette },
]

const currentYear = new Date().getFullYear()
</script>

<template>
  <div class="app-layout">
    <!-- 环境光漂移背景 -->
    <div class="aura" aria-hidden="true">
      <i></i>
    </div>

    <!-- 桌面侧栏导航 (>= 1440px) -->
    <aside class="sidebar glass desktop-only">
      <div class="brand">
        <div class="brand-icon">
          <ShieldCheck :size="28" class="brand-svg" />
        </div>
        <span class="brand-title">保单簿</span>
      </div>

      <nav class="nav-list">
        <router-link
          v-for="item in navItems"
          :key="item.path"
          :to="item.path"
          class="nav-link"
          :class="{ active: route.path === item.path || (item.path !== '/' && route.path.startsWith(item.path)) }"
          :title="item.name"
        >
          <component :is="item.icon" :size="20" class="nav-icon" />
          <span class="nav-label">{{ item.name }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <button
          class="icon-btn"
          @click="themeStore.toggleTheme"
          :title="themeStore.isDark ? '切换至浅色模式' : '切换至深色模式'"
          aria-label="切换明暗主题"
        >
          <Sun v-if="themeStore.isDark" :size="18" />
          <Moon v-else :size="18" />
        </button>

        <button
          class="icon-btn"
          :class="{ 'lite-active': themeStore.isLite }"
          @click="themeStore.toggleLite"
          :title="themeStore.isLite ? '简洁模式开启中 (点击切换为平滑模式)' : '简洁模式关闭 (点击开启降功耗模式)'"
          aria-label="切换简洁模式"
        >
          <Zap v-if="!themeStore.isLite" :size="18" />
          <ZapOff v-else :size="18" />
        </button>
      </div>
    </aside>

    <!-- 平板顶栏导航 (600px - 1439px) -->
    <header class="tablet-header glass tablet-only">
      <div class="brand-compact">
        <ShieldCheck :size="22" class="brand-svg" />
        <span class="brand-title-compact">保单簿</span>
      </div>
      <nav class="tablet-nav">
        <router-link
          v-for="item in navItems.slice(0, 7)"
          :key="item.path"
          :to="item.path"
          class="tablet-link"
          :class="{ active: route.path === item.path }"
        >
          {{ item.name }}
        </router-link>
      </nav>
      <div class="header-actions">
        <button class="icon-btn" @click="themeStore.toggleTheme" title="主题切换">
          <Sun v-if="themeStore.isDark" :size="16" />
          <Moon v-else :size="16" />
        </button>
        <button class="icon-btn" @click="themeStore.toggleLite" title="简洁模式">
          <Zap v-if="!themeStore.isLite" :size="16" />
          <ZapOff v-else :size="16" />
        </button>
      </div>
    </header>

    <!-- 手机顶栏 (< 600px) -->
    <header class="mobile-header mobile-only">
      <div class="brand-compact">
        <ShieldCheck :size="20" class="brand-svg" />
        <span class="brand-title-compact">保单簿 PolicyBook</span>
      </div>
      <div class="header-actions">
        <button class="icon-btn" @click="themeStore.toggleTheme">
          <Sun v-if="themeStore.isDark" :size="16" />
          <Moon v-else :size="16" />
        </button>
      </div>
    </header>

    <!-- 主视口内容 -->
    <main class="main-content">
      <div class="content-body">
        <router-view />
      </div>

      <!-- 全站固定免责声明 -->
      <footer class="app-disclaimer">
        <p class="disclaimer-text">
          保单簿根据你上传的合同文本整理信息，帮助你理解条款和估算大致范围。所有结论以保险公司的核定和合同原文为准，本工具不构成投保建议、核保意见或理赔承诺。
        </p>
      </footer>
    </main>

    <!-- 手机底栏导航 (< 600px) -->
    <nav class="mobile-bottom-nav glass mobile-only">
      <router-link to="/" class="mobile-nav-link" :class="{ active: route.path === '/' }">
        <Home :size="20" />
        <span>总览</span>
      </router-link>
      <router-link to="/policies" class="mobile-nav-link" :class="{ active: route.path.startsWith('/policies') }">
        <ShieldCheck :size="20" />
        <span>保单</span>
      </router-link>
      <router-link to="/ask" class="mobile-nav-link" :class="{ active: route.path.startsWith('/ask') }">
        <MessageSquareQuote :size="20" />
        <span>问答</span>
      </router-link>
      <router-link to="/claim" class="mobile-nav-link" :class="{ active: route.path.startsWith('/claim') }">
        <Calculator :size="20" />
        <span>模拟</span>
      </router-link>
      <router-link to="/settings" class="mobile-nav-link" :class="{ active: route.path === '/settings' || route.path.startsWith('/dev') }">
        <Settings :size="20" />
        <span>设置</span>
      </router-link>
    </nav>
  </div>
</template>

<style scoped>
.app-layout {
  min-height: 100vh;
  display: flex;
  position: relative;
}

/* 桌面侧栏 (>= 1440px) */
.sidebar {
  width: 220px;
  min-width: 220px;
  height: 100vh;
  position: sticky;
  top: 0;
  display: flex;
  flex-direction: column;
  padding: var(--sp-4) var(--sp-3);
  margin: var(--sp-4) 0 var(--sp-4) var(--sp-4);
  height: calc(100vh - var(--sp-8));
  z-index: 20;
}

.brand {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  margin-bottom: var(--sp-4);
}

.brand-icon {
  width: 38px;
  height: 38px;
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
  font-size: var(--fs-19);
  font-weight: 700;
  letter-spacing: -0.02em;
}

.nav-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  overflow-y: auto;
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border-radius: var(--r-control);
  font-size: var(--fs-14);
  font-weight: 500;
  color: var(--text-muted);
  transition: var(--trans-fast);
}

.nav-link:hover {
  background: color-mix(in oklch, var(--text) 6%, transparent);
  color: var(--text);
}

.nav-link.active {
  background: color-mix(in oklch, var(--ok) 14%, transparent);
  color: var(--ok);
  font-weight: 600;
}

.sidebar-footer {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--glass-stroke);
}

.icon-btn {
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: var(--r-control);
  color: var(--text-muted);
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
}

.icon-btn:hover {
  color: var(--text);
  background: var(--glass-fill-strong);
}

.icon-btn.lite-active {
  color: var(--pending);
}

/* 主内容区 */
.main-content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: var(--sp-4) var(--sp-5);
}

.content-body {
  flex: 1;
}

/* 固定免责声明 */
.app-disclaimer {
  margin-top: var(--sp-7);
  padding: var(--sp-3) var(--sp-4);
  border-radius: var(--r-control);
  background: color-mix(in oklch, var(--text) 4%, transparent);
  border-left: 3px solid var(--text-muted);
}

.disclaimer-text {
  font-size: var(--fs-12);
  line-height: 1.6;
  color: var(--text-muted);
}

/* 响应式展示切换 */
.desktop-only { display: flex; }
.tablet-only { display: none; }
.mobile-only { display: none; }

/* 平板 (600px - 1439px) */
@media (max-width: 1439px) and (min-width: 600px) {
  .desktop-only { display: none; }
  .tablet-only { display: flex; }
  .mobile-only { display: none; }

  .app-layout {
    flex-direction: column;
  }

  .tablet-header {
    position: sticky;
    top: var(--sp-3);
    margin: var(--sp-3) var(--sp-4) 0;
    padding: var(--sp-2) var(--sp-4);
    display: flex;
    align-items: center;
    justify-content: space-between;
    z-index: 30;
  }

  .tablet-nav {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
    overflow-x: auto;
  }

  .tablet-link {
    font-size: var(--fs-14);
    padding: var(--sp-1) var(--sp-3);
    border-radius: var(--r-control);
    color: var(--text-muted);
    white-space: nowrap;
  }

  .tablet-link.active {
    color: var(--ok);
    background: color-mix(in oklch, var(--ok) 12%, transparent);
    font-weight: 600;
  }

  .main-content {
    padding: var(--sp-4);
  }
}

/* 手机 (< 600px) */
@media (max-width: 599px) {
  .desktop-only { display: none; }
  .tablet-only { display: none; }
  .mobile-only { display: flex; }

  .app-layout {
    flex-direction: column;
    padding-bottom: 70px;
  }

  .mobile-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--sp-3) var(--sp-4);
    background: var(--glass-fill);
    border-bottom: 1px solid var(--glass-stroke);
  }

  .brand-compact {
    display: flex;
    align-items: center;
    gap: var(--sp-2);
  }

  .brand-title-compact {
    font-size: var(--fs-16);
    font-weight: 700;
  }

  .main-content {
    padding: var(--sp-3);
  }

  .mobile-bottom-nav {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    height: 60px;
    display: flex;
    align-items: center;
    justify-content: space-around;
    z-index: 40;
    border-radius: 0;
    border-top: 1px solid var(--glass-stroke);
    border-left: none;
    border-right: none;
    border-bottom: none;
  }

  .mobile-nav-link {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    font-size: 11px;
    color: var(--text-muted);
  }

  .mobile-nav-link.active {
    color: var(--ok);
    font-weight: 600;
  }
}
</style>
