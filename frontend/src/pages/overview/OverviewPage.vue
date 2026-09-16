<script setup lang="ts">
import { ShieldCheck, PlusCircle, HelpCircle, Calculator } from 'lucide-vue-next'
</script>

<template>
  <div class="overview-page">
    <header class="page-header">
      <h1 class="page-title">家庭保障状况</h1>
      <p class="page-subtitle">保单簿全景概览与保障时间轴</p>
    </header>

    <div class="glass placeholder-card">
      <div class="placeholder-icon">
        <ShieldCheck :size="40" class="text-ok" />
      </div>
      <h2>家庭保障总览（待 M4 阶段实现完整保障时间轴与雷达）</h2>
      <p>在此阶段，你可以前往导航栏中的「设计系统」或「系统设置」查看工程与模型连通状态。</p>
      <div class="quick-actions">
        <router-link to="/import" class="btn-primary">
          <PlusCircle :size="16" />
          上传保单
        </router-link>
        <router-link to="/ask" class="btn-secondary">
          <HelpCircle :size="16" />
          问条款
        </router-link>
        <router-link to="/claim" class="btn-secondary">
          <Calculator :size="16" />
          模拟理赔
        </router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.overview-page {
  max-width: 1080px;
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

.placeholder-card {
  padding: var(--sp-7);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--sp-3);
  margin-top: var(--sp-4);
}

.placeholder-icon {
  width: 64px;
  height: 64px;
  border-radius: var(--r-control);
  background: color-mix(in oklch, var(--ok) 15%, transparent);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ok);
}

.quick-actions {
  display: flex;
  gap: var(--sp-3);
  margin-top: var(--sp-4);
}
</style>
