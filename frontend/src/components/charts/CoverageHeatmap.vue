<script setup lang="ts">
import { useRouter } from 'vue-router'
import { AlertTriangle, CheckCircle2, MinusCircle, ShieldAlert } from 'lucide-vue-next'

export interface HeatmapCell {
  status: 'none' | 'partial' | 'full'
  effective_yuan: number
  effective_display: string
  ratio: number
  policy_ids: string[]
  policy_names: string[]
}

export interface HeatmapMemberRow {
  member_id: string
  member_name: string
  member_color: string
  relation: string
  cells: Record<string, HeatmapCell>
}

export interface HeatmapCategory {
  key: string
  name: string
}

const props = defineProps<{
  categories: HeatmapCategory[]
  rows: HeatmapMemberRow[]
}>()

const router = useRouter()

function onCellClick(cell: HeatmapCell) {
  if (cell.policy_ids && cell.policy_ids.length > 0) {
    if (cell.policy_ids.length === 1) {
      router.push(`/policies/${cell.policy_ids[0]}`)
    } else {
      router.push('/policies')
    }
  } else {
    // Navigate to ask or policies to add
    router.push('/policies')
  }
}
</script>

<template>
  <div class="heatmap-card glass">
    <div class="heatmap-header">
      <div>
        <h3 class="heatmap-title">家庭保障缺口热力图</h3>
        <span class="heatmap-subtitle">横轴为风险类型，纵轴为家庭成员。点击单元格可直达对应保单</span>
      </div>

      <!-- Legend -->
      <div class="heatmap-legend">
        <div class="legend-item">
          <span class="status-badge status-badge--full">充分覆盖 (≥100%)</span>
        </div>
        <div class="legend-item">
          <span class="status-badge status-badge--partial">部分覆盖 (<100%)</span>
        </div>
        <div class="legend-item">
          <span class="status-badge status-badge--none">保障缺口 (0%)</span>
        </div>
      </div>
    </div>

    <!-- Table Grid -->
    <div class="heatmap-table-wrapper">
      <table class="heatmap-table">
        <thead>
          <tr>
            <th class="col-member">家庭成员</th>
            <th
              v-for="cat in categories"
              :key="cat.key"
              class="col-category"
            >
              {{ cat.name }}
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.member_id">
            <!-- Member Header -->
            <td class="cell-member">
              <div class="member-tag">
                <span
                  class="avatar-mini"
                  :style="{ backgroundColor: row.member_color || '#2A8F82' }"
                >
                  {{ row.member_name.slice(0, 1) }}
                </span>
                <span class="member-name">{{ row.member_name }}</span>
                <span class="relation-tag">{{ row.relation }}</span>
              </div>
            </td>

            <!-- Category Cells -->
            <td
              v-for="cat in categories"
              :key="cat.key"
              class="cell-category"
            >
              <div
                v-if="row.cells[cat.key]"
                :class="[
                  'heatmap-cell',
                  `heatmap-cell--${row.cells[cat.key].status}`,
                  row.cells[cat.key].policy_ids.length > 0 ? 'heatmap-cell--clickable' : ''
                ]"
                @click="onCellClick(row.cells[cat.key])"
                :title="row.cells[cat.key].policy_names.length > 0
                  ? `${cat.name}：${row.cells[cat.key].policy_names.join('、')} (${row.cells[cat.key].effective_display})`
                  : `${cat.name}：暂无有效保单覆盖`"
              >
                <div class="cell-content">
                  <div class="cell-status-icon">
                    <CheckCircle2
                      v-if="row.cells[cat.key].status === 'full'"
                      :size="13"
                      class="icon-full"
                    />
                    <MinusCircle
                      v-else-if="row.cells[cat.key].status === 'partial'"
                      :size="13"
                      class="icon-partial"
                    />
                    <ShieldAlert
                      v-else
                      :size="13"
                      class="icon-none"
                    />
                  </div>
                  <span class="cell-amount">{{ row.cells[cat.key].effective_display }}</span>
                </div>

                <div v-if="row.cells[cat.key].policy_names.length > 0" class="cell-policy-count">
                  {{ row.cells[cat.key].policy_names.length }} 份保单
                </div>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.heatmap-card {
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

.heatmap-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--sp-2);
}

.heatmap-title {
  font-size: var(--fs-16);
  font-weight: 700;
  margin: 0;
}

.heatmap-subtitle {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.heatmap-legend {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}

.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}

.status-badge--full {
  background: color-mix(in oklch, var(--ok) 15%, transparent);
  color: var(--ok);
  border: 1px solid color-mix(in oklch, var(--ok) 30%, transparent);
}

.status-badge--partial {
  background: color-mix(in oklch, var(--accent) 15%, transparent);
  color: var(--accent);
  border: 1px solid color-mix(in oklch, var(--accent) 30%, transparent);
}

.status-badge--none {
  background: color-mix(in oklch, var(--danger) 15%, transparent);
  color: var(--danger);
  border: 1px dashed var(--danger);
}

.heatmap-table-wrapper {
  overflow-x: auto;
}

.heatmap-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 6px;
  font-size: var(--fs-13);
}

.col-member {
  width: 150px;
  text-align: left;
  padding: 8px 12px;
  color: var(--text-muted);
  font-weight: normal;
}

.col-category {
  text-align: center;
  padding: 8px 12px;
  color: var(--text-secondary);
  font-weight: 600;
}

.cell-member {
  padding: 4px 8px;
  vertical-align: middle;
}

.member-tag {
  display: flex;
  align-items: center;
  gap: 8px;
}

.avatar-mini {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: bold;
}

.member-name {
  font-weight: 600;
  color: var(--text-primary);
}

.relation-tag {
  font-size: 10px;
  padding: 1px 5px;
  background: var(--bg-surface);
  border-radius: 4px;
  color: var(--text-muted);
}

.cell-category {
  padding: 2px;
  vertical-align: middle;
}

.heatmap-cell {
  padding: 8px 10px;
  border-radius: var(--r-control);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  transition: all 0.15s ease;
  min-height: 48px;
}

.heatmap-cell--clickable {
  cursor: pointer;
}

.heatmap-cell--clickable:hover {
  filter: brightness(1.05);
  transform: scale(1.02);
}

.heatmap-cell--full {
  background: color-mix(in oklch, var(--ok) 18%, transparent);
  border: 1px solid color-mix(in oklch, var(--ok) 35%, transparent);
  color: var(--text-primary);
}

.heatmap-cell--partial {
  background: color-mix(in oklch, var(--accent) 15%, transparent);
  border: 1px solid color-mix(in oklch, var(--accent) 30%, transparent);
  color: var(--text-primary);
}

.heatmap-cell--none {
  background: color-mix(in oklch, var(--danger) 8%, transparent);
  border: 1px dashed color-mix(in oklch, var(--danger) 40%, transparent);
  color: var(--text-muted);
}

.cell-content {
  display: flex;
  align-items: center;
  gap: 5px;
}

.icon-full {
  color: var(--ok);
}

.icon-partial {
  color: var(--accent);
}

.icon-none {
  color: var(--danger);
}

.cell-amount {
  font-size: var(--fs-13);
  font-weight: bold;
}

.cell-policy-count {
  font-size: 10px;
  color: var(--text-muted);
}
</style>
