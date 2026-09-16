<script setup lang="ts">
import { ref, watch } from 'vue'
import { HelpCircle, Check, ArrowRight, FastForward } from 'lucide-vue-next'

export interface RenewalQuestion {
  dimension: string
  label: string
  question: string
  why: string
  options: string[]
  affects: string[]
}

const props = defineProps<{
  questions: RenewalQuestion[]
  submitting?: boolean
}>()

const emit = defineEmits<{
  (e: 'submit', answers: Record<string, string>): void
  (e: 'skip'): void
}>()

const selectedAnswers = ref<Record<string, string>>({})

watch(
  () => props.questions,
  (newQs) => {
    selectedAnswers.value = {}
  },
  { immediate: true }
)

function selectOption(dimension: string, option: string) {
  selectedAnswers.value[dimension] = option
}

function handleSubmit() {
  emit('submit', { ...selectedAnswers.value })
}

function handleSkip() {
  emit('skip')
}
</script>

<template>
  <div class="questions-card glass">
    <div class="questions-header">
      <div class="header-tag">
        <span class="pulse-dot"></span>
        <span class="tag-title">顾问受控追问 (本轮 {{ questions.length }} 项)</span>
      </div>
      <p class="header-hint">
        根据《意外险缺口核验清单》，以下维度对责任范围与费率有决定性影响，请确认：
      </p>
    </div>

    <div class="questions-list">
      <div
        v-for="(q, idx) in questions"
        :key="q.dimension"
        class="question-item"
      >
        <div class="q-title-row">
          <span class="q-num">0{{ idx + 1 }}</span>
          <span class="q-dim-label">{{ q.label }}</span>
          <span class="q-text">{{ q.question }}</span>
        </div>

        <div class="why-badge">
          <HelpCircle :size="13" class="why-icon" />
          <span class="why-label">为什么问：</span>
          <span class="why-text">{{ q.why }}</span>
        </div>

        <div class="options-grid">
          <button
            v-for="opt in q.options"
            :key="opt"
            type="button"
            class="opt-btn"
            :class="{ active: selectedAnswers[q.dimension] === opt }"
            @click="selectOption(q.dimension, opt)"
          >
            <span class="opt-text">{{ opt }}</span>
            <Check v-if="selectedAnswers[q.dimension] === opt" :size="14" class="opt-check" />
          </button>
        </div>
      </div>
    </div>

    <div class="questions-actions">
      <button
        type="button"
        class="btn-secondary"
        :disabled="submitting"
        @click="handleSkip"
      >
        <FastForward :size="14" />
        <span>跳过其余追问，直接对比</span>
      </button>

      <button
        type="button"
        class="btn-primary"
        :disabled="submitting || Object.keys(selectedAnswers).length === 0"
        @click="handleSubmit"
      >
        <span>确认并继续</span>
        <ArrowRight :size="14" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.questions-card {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-panel);
  padding: var(--sp-5);
  backdrop-filter: blur(var(--glass-blur));
  margin: var(--sp-4) 0;
  box-shadow: var(--glass-shadow);
}

.questions-header {
  margin-bottom: var(--sp-4);
  border-bottom: 1px solid var(--glass-stroke);
  padding-bottom: var(--sp-3);
}

.header-tag {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-1);
}

.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--c-apricot);
}

.tag-title {
  font-size: var(--fs-13);
  font-weight: 600;
  color: var(--c-apricot);
  letter-spacing: 0.02em;
}

.header-hint {
  font-size: var(--fs-13);
  color: var(--text-muted);
  margin: 0;
  line-height: 1.5;
}

.questions-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-5);
}

.question-item {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.q-title-row {
  display: flex;
  align-items: baseline;
  gap: var(--sp-2);
}

.q-num {
  font-family: var(--font-ui);
  font-weight: 700;
  font-size: var(--fs-12);
  color: var(--c-apricot);
  background: color-mix(in oklch, var(--c-apricot) 14%, transparent);
  padding: 2px 6px;
  border-radius: var(--rad-control);
}

.q-dim-label {
  font-weight: 600;
  font-size: var(--fs-14);
  color: var(--text);
}

.q-text {
  font-size: var(--fs-14);
  color: var(--text);
}

.why-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: var(--fs-12);
  background: color-mix(in oklch, var(--c-apricot) 10%, transparent);
  color: var(--c-apricot);
  padding: 4px 10px;
  border-radius: var(--rad-control);
  width: fit-content;
}

.why-icon {
  flex-shrink: 0;
}

.why-label {
  font-weight: 600;
}

.why-text {
  color: var(--text);
  opacity: 0.88;
}

.options-grid {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin-top: var(--sp-1);
}

.opt-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-control);
  padding: 6px 14px;
  font-size: var(--fs-13);
  color: var(--text);
  cursor: pointer;
  transition: background 0.15s ease, border-color 0.15s ease;
}

.opt-btn:hover {
  background: color-mix(in oklch, var(--c-celadon) 10%, white);
  border-color: var(--c-celadon);
}

.opt-btn.active {
  background: color-mix(in oklch, var(--c-celadon) 16%, transparent);
  border-color: var(--c-celadon);
  color: var(--c-celadon);
  font-weight: 600;
}

.opt-check {
  color: var(--c-celadon);
}

.questions-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--sp-5);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--glass-stroke);
}

.btn-secondary {
  display: flex;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px dashed var(--glass-stroke);
  border-radius: var(--rad-control);
  padding: 8px 14px;
  font-size: var(--fs-12);
  color: var(--text-muted);
  cursor: pointer;
}

.btn-secondary:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.03);
  color: var(--text);
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: 6px;
  background: var(--c-celadon);
  color: white;
  border: none;
  border-radius: var(--rad-control);
  padding: 8px 18px;
  font-size: var(--fs-13);
  font-weight: 500;
  cursor: pointer;
}

.btn-primary:hover:not(:disabled) {
  opacity: 0.92;
}

.btn-primary:disabled,
.btn-secondary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
