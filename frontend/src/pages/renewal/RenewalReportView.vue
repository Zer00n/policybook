<script setup lang="ts">
import { ref } from 'vue'
import {
  AlertTriangle,
  FileText,
  HelpCircle,
  Link,
  ShieldCheck,
  CheckSquare,
  Square,
  AlertCircle,
  ExternalLink,
} from 'lucide-vue-next'
import ComparisonMatrix, { ComparisonMatrixData } from './ComparisonMatrix.vue'

export interface SourceRecordDto {
  url: string
  domain: string
  title?: string
  via: string
  retrieved_at?: string
}

export interface RenewalReportData {
  session_id: string
  status: 'complete' | 'partial' | 'search_failed'
  search_failure_reason?: string
  comparison_matrix?: ComparisonMatrixData
  difference_narrative: string
  removed_unverified_count?: number
  customer_service_questions: string[]
  missing_info: string[]
  source_records: SourceRecordDto[]
  disclaimer: string
}

const props = defineProps<{
  report: RenewalReportData
}>()

const checkedQuestions = ref<Record<number, boolean>>({})

function toggleQuestion(idx: number) {
  checkedQuestions.value[idx] = !checkedQuestions.value[idx]
}
</script>

<template>
  <div class="report-view-container">
    <!-- Failure Disclosure Banner if search failed -->
    <div v-if="report.status === 'search_failed'" class="failure-banner glass">
      <div class="banner-header">
        <AlertTriangle :size="20" class="banner-icon" />
        <span class="banner-title">检索未完成声明（合规防编造保护触发）</span>
      </div>
      <div class="banner-body">
        <p class="fail-reason"><strong>未完成原因：</strong>{{ report.search_failure_reason }}</p>
        <p class="fail-notice">
          <strong>系统安全约定：</strong>根据项目红线原则，候选产品的每一个事实字段只能来自已下载并通过校验的官方文档。当联网搜索超时或数据源不可达时，系统坚决不使用大模型记忆补全产品事实，保护家庭决策真实可信。
        </p>
      </div>
    </div>

    <!-- Comparison Matrix -->
    <ComparisonMatrix
      v-if="report.comparison_matrix"
      :matrix="report.comparison_matrix"
    />

    <!-- Difference Narrative -->
    <div class="narrative-card glass">
      <div class="section-title-wrap">
        <FileText :size="16" class="title-icon" />
        <span class="section-title">各维度差异化分析与溯源</span>
        <span
          v-if="report.removed_unverified_count && report.removed_unverified_count > 0"
          class="removed-badge"
        >
          已依据红线剔除未验证语句 {{ report.removed_unverified_count }} 处
        </span>
      </div>
      <div class="narrative-content quote-text">
        {{ report.difference_narrative }}
      </div>
    </div>

    <!-- Customer Service Questions Checklist -->
    <div v-if="report.customer_service_questions.length > 0" class="checklist-card glass">
      <div class="section-title-wrap">
        <HelpCircle :size="16" class="title-icon" />
        <span class="section-title">续保前向保险公司客服核对清单</span>
      </div>
      <p class="checklist-desc">
        以下问题涉及条款细节或理赔限制，投保或续保前建议致电保险公司官方客服（或在线人工客服）逐一核实：
      </p>
      <div class="checklist-items">
        <div
          v-for="(q, idx) in report.customer_service_questions"
          :key="idx"
          class="checklist-item"
          :class="{ checked: checkedQuestions[idx] }"
          @click="toggleQuestion(idx)"
        >
          <component
            :is="checkedQuestions[idx] ? CheckSquare : Square"
            :size="16"
            class="check-icon"
          />
          <span class="question-text">{{ q }}</span>
        </div>
      </div>
    </div>

    <!-- Missing Info Disclosure -->
    <div v-if="report.missing_info.length > 0" class="missing-card glass">
      <div class="section-title-wrap">
        <AlertCircle :size="16" class="title-icon-amber" />
        <span class="section-title">未取得信息清单（透明披露）</span>
      </div>
      <ul class="missing-list">
        <li v-for="(item, idx) in report.missing_info" :key="idx">
          {{ item }}
        </li>
      </ul>
    </div>

    <!-- Source Records Provenance -->
    <div v-if="report.source_records.length > 0" class="sources-card glass">
      <div class="section-title-wrap">
        <Link :size="16" class="title-icon" />
        <span class="section-title">检索来源白名单凭证 (source_record)</span>
      </div>
      <div class="sources-list">
        <div
          v-for="(src, idx) in report.source_records"
          :key="idx"
          class="source-row"
        >
          <span class="source-domain-badge">{{ src.domain }}</span>
          <a
            :href="src.url"
            target="_blank"
            rel="noopener noreferrer"
            class="source-url"
          >
            <span>{{ src.title || src.url }}</span>
            <ExternalLink :size="11" />
          </a>
          <span class="source-via">途径: {{ src.via }}</span>
        </div>
      </div>
    </div>

    <!-- Global Mandatory Disclaimer -->
    <div class="disclaimer-footer">
      <ShieldCheck :size="14" class="disclaimer-icon" />
      <span>{{ report.disclaimer }}</span>
    </div>
  </div>
</template>

<style scoped>
.report-view-container {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
  margin-top: var(--sp-4);
}

.failure-banner {
  background: color-mix(in oklch, var(--c-cinnabar) 10%, white);
  border: 1px solid var(--c-cinnabar);
  border-radius: var(--rad-panel);
  padding: var(--sp-4);
}

.banner-header {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  color: var(--c-cinnabar);
  font-weight: 600;
  font-size: var(--fs-14);
  margin-bottom: var(--sp-2);
}

.banner-body {
  font-size: var(--fs-13);
  color: var(--text);
  line-height: 1.6;
}

.fail-reason {
  margin: 0 0 var(--sp-2) 0;
  color: var(--c-cinnabar);
}

.fail-notice {
  margin: 0;
  color: var(--text-muted);
}

.narrative-card,
.checklist-card,
.missing-card,
.sources-card {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-panel);
  padding: var(--sp-4);
  backdrop-filter: blur(var(--glass-blur));
  box-shadow: var(--glass-shadow);
}

.section-title-wrap {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: var(--sp-3);
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--glass-stroke);
}

.title-icon {
  color: var(--c-celadon);
}

.title-icon-amber {
  color: var(--c-apricot);
}

.section-title {
  font-weight: 600;
  font-size: var(--fs-14);
  color: var(--text);
}

.removed-badge {
  font-size: 11px;
  background: color-mix(in oklch, var(--c-cinnabar) 12%, transparent);
  color: var(--c-cinnabar);
  padding: 2px 8px;
  border-radius: var(--rad-control);
  margin-left: auto;
}

.quote-text {
  font-family: var(--font-quote);
  font-size: var(--fs-13);
  line-height: 1.8;
  color: var(--text);
  border-left: 3px solid var(--c-celadon);
  padding-left: var(--sp-3);
  white-space: pre-wrap;
}

.checklist-desc {
  font-size: var(--fs-13);
  color: var(--text-muted);
  margin: 0 0 var(--sp-3) 0;
}

.checklist-items {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.checklist-item {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-2) var(--sp-3);
  background: color-mix(in oklch, var(--text) 2%, transparent);
  border-radius: var(--rad-control);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s ease;
}

.checklist-item:hover {
  background: color-mix(in oklch, var(--c-celadon) 8%, transparent);
}

.checklist-item.checked {
  opacity: 0.6;
  text-decoration: line-through;
}

.check-icon {
  color: var(--c-celadon);
  flex-shrink: 0;
  margin-top: 2px;
}

.question-text {
  font-size: var(--fs-13);
  color: var(--text);
  line-height: 1.5;
}

.missing-list {
  margin: 0;
  padding-left: var(--sp-4);
  font-size: var(--fs-13);
  color: var(--text-muted);
  line-height: 1.6;
}

.sources-list {
  display: flex;
  flex-direction: column;
  gap: var(--sp-2);
}

.source-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-12);
  padding: 4px 8px;
  background: color-mix(in oklch, var(--text) 2%, transparent);
  border-radius: var(--rad-control);
}

.source-domain-badge {
  font-weight: 600;
  color: var(--c-celadon);
  background: color-mix(in oklch, var(--c-celadon) 10%, transparent);
  padding: 1px 6px;
  border-radius: var(--rad-control);
}

.source-url {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--text);
  text-decoration: none;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.source-url:hover {
  text-decoration: underline;
  color: var(--c-celadon);
}

.source-via {
  color: var(--text-muted);
  font-size: 11px;
}

.disclaimer-footer {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  background: color-mix(in oklch, var(--text) 4%, transparent);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--rad-control);
  padding: var(--sp-3) var(--sp-4);
  font-size: var(--fs-12);
  color: var(--text-muted);
  line-height: 1.5;
  margin-top: var(--sp-2);
}

.disclaimer-icon {
  flex-shrink: 0;
  color: var(--text-muted);
}
</style>
