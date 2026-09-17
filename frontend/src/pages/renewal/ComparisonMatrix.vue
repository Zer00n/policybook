<script setup lang="ts">
import { ExternalLink, Check, AlertTriangle, X, HelpCircle, Shield } from 'lucide-vue-next'

export interface ComparisonCell {
  value: string
  status: 'covered' | 'missing' | 'partial' | 'not_found'
  quote?: string
  source_url?: string
}

export interface ComparisonRow {
  dimension_key: string
  dimension_label: string
  baseline_cell: ComparisonCell
  candidate_cells: Record<string, ComparisonCell>
}

export interface ProductColumn {
  id: string
  name: string
  is_baseline: boolean
  premium_text?: string
  url?: string
}

export interface ComparisonMatrixData {
  products: ProductColumn[]
  rows: ComparisonRow[]
}

defineProps<{
  matrix: ComparisonMatrixData
}>()
</script>

<template>
  <div class="matrix-container glass">
    <div class="matrix-header-info">
      <div class="info-title">
        <Shield :size="16" class="title-icon" />
        <span>条款责任横向对比矩阵（纯代码确定性对齐）</span>
      </div>
      <span class="info-tag">白名单官方条款溯源</span>
    </div>

    <div class="table-scroll-wrapper">
      <table class="comparison-table">
        <thead>
          <tr>
            <th class="th-dim">保障维度</th>
            <th
              v-for="prod in matrix.products"
              :key="prod.id"
              class="th-prod"
              :class="{ 'th-baseline': prod.is_baseline }"
            >
              <div class="prod-badge-wrap">
                <span v-if="prod.is_baseline" class="badge-baseline">现有基线</span>
                <span v-else class="badge-candidate">官方候选</span>
              </div>
              <div class="prod-name">{{ prod.name }}</div>
              <div v-if="prod.premium_text" class="prod-premium">
                {{ prod.premium_text }}
              </div>
              <div v-if="prod.url" class="prod-url">
                <a :href="prod.url" target="_blank" rel="noopener noreferrer" class="url-link">
                  <span>官方条款</span>
                  <ExternalLink :size="11" />
                </a>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in matrix.rows"
            :key="row.dimension_key"
            class="matrix-row"
          >
            <td class="td-dim">
              <span class="dim-name">{{ row.dimension_label }}</span>
            </td>

            <!-- Baseline Cell -->
            <td class="td-cell td-baseline-cell">
              <div class="cell-content">
                <div class="status-indicator" :class="row.baseline_cell.status">
                  <Check v-if="row.baseline_cell.status === 'covered'" :size="13" />
                  <AlertTriangle v-else-if="row.baseline_cell.status === 'partial'" :size="13" />
                  <X v-else-if="row.baseline_cell.status === 'missing'" :size="13" />
                  <HelpCircle v-else :size="13" />
                  <span class="cell-val">{{ row.baseline_cell.value }}</span>
                </div>
                <div v-if="row.baseline_cell.quote" class="cell-quote">
                  "{{ row.baseline_cell.quote }}"
                </div>
              </div>
            </td>

            <!-- Candidate Cells -->
            <td
              v-for="prod in matrix.products.filter(p => !p.is_baseline)"
              :key="prod.id"
              class="td-cell"
            >
              <div
                v-if="row.candidate_cells[prod.id]"
                class="cell-content"
              >
                <div class="status-indicator" :class="row.candidate_cells[prod.id].status">
                  <Check v-if="row.candidate_cells[prod.id].status === 'covered'" :size="13" />
                  <AlertTriangle v-else-if="row.candidate_cells[prod.id].status === 'partial'" :size="13" />
                  <X v-else-if="row.candidate_cells[prod.id].status === 'missing'" :size="13" />
                  <HelpCircle v-else :size="13" />
                  <span class="cell-val">{{ row.candidate_cells[prod.id].value }}</span>
                </div>
                <div v-if="row.candidate_cells[prod.id].quote" class="cell-quote">
                  "{{ row.candidate_cells[prod.id].quote }}"
                </div>
              </div>
              <div v-else class="cell-empty">
                条款中未找到
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.matrix-container {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  border-radius: var(--r-panel);
  padding: var(--sp-4);
  backdrop-filter: blur(var(--glass-blur));
  margin: var(--sp-4) 0;
  box-shadow: var(--glass-shadow);
}

.matrix-header-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--sp-3);
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--glass-stroke);
}

.info-title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-weight: 600;
  font-size: var(--fs-14);
  color: var(--text);
}

.title-icon {
  color: var(--c-celadon);
}

.info-tag {
  font-size: var(--fs-12);
  color: var(--c-celadon);
  background: color-mix(in oklch, var(--c-celadon) 12%, transparent);
  padding: 2px 8px;
  border-radius: var(--r-control);
}

.table-scroll-wrapper {
  overflow-x: auto;
}

.comparison-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--fs-12);
  text-align: left;
}

th, td {
  padding: 10px 14px;
  border: 1px solid var(--glass-stroke);
  vertical-align: top;
}

.th-dim {
  width: 130px;
  background: color-mix(in oklch, var(--text) 4%, transparent);
  font-weight: 600;
  color: var(--text);
}

.th-prod {
  min-width: 180px;
  background: color-mix(in oklch, var(--text) 2%, transparent);
}

.th-baseline {
  background: color-mix(in oklch, var(--c-apricot) 8%, transparent);
}

.prod-badge-wrap {
  margin-bottom: 4px;
}

.badge-baseline {
  font-size: 11px;
  background: var(--c-apricot);
  color: white;
  padding: 1px 6px;
  border-radius: var(--r-control);
  font-weight: 500;
}

.badge-candidate {
  font-size: 11px;
  background: var(--c-celadon);
  color: white;
  padding: 1px 6px;
  border-radius: var(--r-control);
  font-weight: 500;
}

.prod-name {
  font-weight: 600;
  color: var(--text);
  margin-bottom: 2px;
}

.prod-premium {
  font-size: 11px;
  color: var(--text-muted);
  font-variant-numeric: tabular-nums;
}

.prod-url {
  margin-top: 4px;
}

.url-link {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 11px;
  color: var(--c-celadon);
  text-decoration: none;
}

.url-link:hover {
  text-decoration: underline;
}

.td-dim {
  font-weight: 500;
  color: var(--text);
  background: color-mix(in oklch, var(--text) 2%, transparent);
}

.td-baseline-cell {
  background: color-mix(in oklch, var(--c-apricot) 3%, transparent);
}

.cell-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: var(--fs-12);
  font-weight: 500;
}

.status-indicator.covered {
  color: var(--c-celadon);
}

.status-indicator.partial {
  color: var(--c-apricot);
}

.status-indicator.missing {
  color: var(--c-cinnabar);
}

.status-indicator.not_found {
  color: var(--text-muted);
}

.cell-val {
  color: var(--text);
}

.cell-quote {
  font-family: var(--font-quote);
  font-size: 11px;
  color: var(--text-muted);
  border-left: 2px solid var(--c-celadon);
  padding-left: 6px;
  margin-top: 2px;
  line-height: 1.4;
}

.cell-empty {
  color: var(--text-muted);
  font-size: 12px;
}
</style>
