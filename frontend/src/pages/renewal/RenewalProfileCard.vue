<script setup lang="ts">
import { computed } from 'vue'
import { UserCheck, CheckCircle2, Circle } from 'lucide-vue-next'

export interface ProfileItem {
  value: string
  label?: string
  updated_at?: string
}

const props = defineProps<{
  profile: Record<string, ProfileItem>
  currentState: string
}>()

const items = computed(() => {
  return Object.entries(props.profile).map(([k, v]) => ({
    key: k,
    label: v.label || k,
    value: v.value,
  }))
})

const stateSteps = [
  { key: 'COLLECT_NEEDS', label: '1. 需求澄清' },
  { key: 'GAP_CHECK', label: '2. 缺口追问' },
  { key: 'ASK_USER', label: '2. 缺口追问' },
  { key: 'SEARCH', label: '3. 官网检索' },
  { key: 'FETCH_DOCS', label: '4. 条款抓取' },
  { key: 'COMPARE', label: '5. 矩阵对齐' },
  { key: 'REPORT', label: '6. 报告生成' },
  { key: 'END', label: '完成' },
]

const currentStepIndex = computed(() => {
  const idx = stateSteps.findIndex(s => s.key === props.currentState)
  return idx >= 0 ? idx : (props.currentState === 'END' ? 7 : 0)
})
</script>

<template>
  <div class="profile-card glass">
    <div class="card-header">
      <div class="header-title">
        <UserCheck :size="16" class="header-icon" />
        <span>需求画像与状态</span>
      </div>
      <span class="step-badge">{{ currentState }}</span>
    </div>

    <!-- Progress Timeline -->
    <div class="process-steps">
      <div
        v-for="(step, idx) in ['需求澄清', '缺口追问', '联网检索', '责任对齐', '报告生成']"
        :key="step"
        class="step-node"
        :class="{
          done: currentStepIndex > idx + 1,
          active: currentStepIndex === idx || (idx === 1 && currentStepIndex === 2)
        }"
      >
        <span class="step-dot"></span>
        <span class="step-text">{{ step }}</span>
      </div>
    </div>

    <!-- Profile Items -->
    <div class="profile-items-wrap">
      <div class="items-title">已确认需求维度 ({{ items.length }})</div>
      <div v-if="items.length === 0" class="empty-hint">
        顾问正在引导澄清，确认的维度将实时沉淀于此...
      </div>
      <div v-else class="items-list">
        <div
          v-for="item in items"
          :key="item.key"
          class="profile-item"
        >
          <div class="item-label-wrap">
            <CheckCircle2 :size="12" class="item-check" />
            <span class="item-label">{{ item.label }}</span>
          </div>
          <span class="item-val">{{ item.value }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.profile-card {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-panel);
  padding: var(--sp-4);
  backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--glass-shadow);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid var(--glass-stroke);
  padding-bottom: var(--sp-2);
}

.header-title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-weight: 600;
  font-size: var(--fs-14);
  color: var(--text);
}

.header-icon {
  color: var(--c-celadon);
}

.step-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--c-celadon);
  background: color-mix(in oklch, var(--c-celadon) 14%, transparent);
  padding: 2px 8px;
  border-radius: var(--r-control);
}

.process-steps {
  display: flex;
  justify-content: space-between;
  position: relative;
  margin: var(--sp-2) 0;
  padding: 0 4px;
}

.step-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  color: var(--text-muted);
}

.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: color-mix(in oklch, var(--text) 20%, transparent);
}

.step-node.active .step-dot {
  background: var(--c-apricot);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--c-apricot) 25%, transparent);
}

.step-node.active .step-text {
  color: var(--c-apricot);
  font-weight: 600;
}

.step-node.done .step-dot {
  background: var(--c-celadon);
}

.step-node.done .step-text {
  color: var(--c-celadon);
}

.profile-items-wrap {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.items-title {
  font-size: var(--fs-12);
  font-weight: 600;
  color: var(--text);
}

.empty-hint {
  font-size: var(--fs-12);
  color: var(--text-muted);
  line-height: 1.5;
  padding: var(--sp-2) 0;
}

.items-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.profile-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: color-mix(in oklch, var(--text) 3%, transparent);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-control);
  padding: 6px 10px;
  font-size: var(--fs-12);
}

.item-label-wrap {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--text-muted);
}

.item-check {
  color: var(--c-celadon);
}

.item-val {
  font-weight: 600;
  color: var(--text);
}
</style>
