<script setup lang="ts">
import { computed, ref } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'

use([
  CanvasRenderer,
  BarChart,
  GridComponent,
  TooltipComponent,
  LegendComponent,
])

export interface WaterfallStep {
  label: string
  amount_low: number
  amount_high: number
  remaining_low: number
  remaining_high: number
  coverage_id?: string | null
  policy_name?: string | null
  note?: string | null
  evidence_quote?: string | null
  evidence_page_no?: number | null
  evidence_rects?: Array<{ x0: number; y0: number; x1: number; y1: number }>
}

const props = defineProps<{
  steps: WaterfallStep[]
  outOfPocketLow: number
  outOfPocketHigh: number
}>()

const emit = defineEmits<{
  (e: 'selectStep', step: WaterfallStep): void
}>()

const chartOption = computed(() => {
  if (!props.steps || props.steps.length === 0) {
    return {}
  }

  // 构造瀑布图数据序列
  // 步骤标签
  const categories: string[] = []
  const baseData: number[] = []
  const valueData: any[] = []

  let prevRemaining = 0

  props.steps.forEach((step, idx) => {
    categories.push(step.label)
    const amt = step.amount_low

    if (idx === 0) {
      // 起始总费用：基底 0，柱高为总金额
      baseData.push(0)
      valueData.push({
        value: amt,
        itemStyle: { color: '#C25B4E', borderRadius: [4, 4, 0, 0] },
      })
      prevRemaining = step.remaining_low
    } else {
      // 扣减项（社保或保单赔付）：柱顶在 prevRemaining，柱底在 step.remaining_low
      const rem = step.remaining_low
      baseData.push(rem)
      const isSi = step.label.includes('社保')
      const barColor = isSi ? '#D08C36' : '#2A8F82'
      valueData.push({
        value: amt,
        itemStyle: { color: barColor, borderRadius: [4, 4, 4, 4] },
      })
      prevRemaining = rem
    }
  })

  // 终点项：个人自付
  categories.push('个人自付差额')
  baseData.push(0)
  valueData.push({
    value: props.outOfPocketLow,
    itemStyle: { color: '#889895', borderRadius: [4, 4, 0, 0] },
  })

  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params: any[]) => {
        const item = params[1] || params[0]
        const idx = item.dataIndex
        const step = props.steps[idx]
        if (idx === props.steps.length) {
          return `<div style="font-size:12px;padding:4px;">
            <div style="font-weight:600;margin-bottom:4px;">个人自付差额</div>
            <div>金额：<b>¥${props.outOfPocketLow.toLocaleString()}</b>${
            props.outOfPocketLow !== props.outOfPocketHigh
              ? ` ~ ¥${props.outOfPocketHigh.toLocaleString()}`
              : ''
          }</div>
          </div>`
        }
        if (!step) return ''

        let html = `<div style="font-size:12px;padding:4px;">
          <div style="font-weight:600;margin-bottom:4px;">${step.label}</div>
          <div>抵扣金额：<b>¥${step.amount_low.toLocaleString()}</b></div>`
        if (step.note) {
          html += `<div style="color:#888;margin-top:2px;">${step.note}</div>`
        }
        if (step.evidence_quote) {
          html += `<div style="color:#2A8F82;margin-top:4px;">[点击柱状可查看条款依据]</div>`
        }
        html += `</div>`
        return html
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      top: '12%',
      containLabel: true,
    },
    xAxis: {
      type: 'category',
      data: categories,
      axisLabel: {
        interval: 0,
        rotate: categories.length > 4 ? 20 : 0,
        color: 'var(--text-2, #5D6B68)',
        fontSize: 12,
      },
      axisLine: { lineStyle: { color: 'var(--border-subtle, rgba(0,0,0,0.1))' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: {
        formatter: (val: number) => (val >= 10000 ? `${(val / 10000).toFixed(1)}万` : `¥${val}`),
        color: 'var(--text-3, #889895)',
      },
      splitLine: {
        lineStyle: {
          color: 'var(--border-subtle, rgba(0,0,0,0.06))',
          type: 'dashed',
        },
      },
    },
    series: [
      {
        name: 'Placeholder',
        type: 'bar',
        stack: 'Total',
        itemStyle: {
          borderColor: 'transparent',
          color: 'transparent',
        },
        emphasis: {
          itemStyle: {
            borderColor: 'transparent',
            color: 'transparent',
          },
        },
        data: baseData,
      },
      {
        name: 'Amount',
        type: 'bar',
        stack: 'Total',
        label: {
          show: true,
          position: 'top',
          formatter: (params: any) => {
            const v = params.value
            return v > 0 ? (v >= 10000 ? `${(v / 10000).toFixed(1)}万` : `¥${v}`) : ''
          },
          fontSize: 11,
          color: 'var(--text-1, #1B2524)',
        },
        data: valueData,
      },
    ],
  }
})

function onChartClick(params: any) {
  const idx = params.dataIndex
  if (idx < props.steps.length) {
    emit('selectStep', props.steps[idx])
  }
}
</script>

<template>
  <div class="waterfall-chart-container">
    <VChart
      v-if="steps && steps.length > 0"
      class="echarts-instance"
      :option="chartOption"
      autoresize
      @click="onChartClick"
    />
    <div v-else class="empty-placeholder">
      暂无理赔测算数据
    </div>
  </div>
</template>

<style scoped>
.waterfall-chart-container {
  width: 100%;
  height: 340px;
  position: relative;
}

.echarts-instance {
  width: 100%;
  height: 100%;
}

.empty-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-3);
  font-size: var(--fs-body-sm);
}
</style>
