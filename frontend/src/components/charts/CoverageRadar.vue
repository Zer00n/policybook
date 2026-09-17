<script setup lang="ts">
import { ref, computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { RadarChart } from 'echarts/charts'
import { TooltipComponent, LegendComponent } from 'echarts/components'
import { getCssVar } from '@/utils/theme-color'
import { useThemeStore } from '@/stores/theme'

use([CanvasRenderer, RadarChart, TooltipComponent, LegendComponent])

export interface RadarDimension {
  key: string
  name: string
  effective_cents: number
  effective_yuan: number
  effective_display: string
  reference_cents?: number
  reference_yuan?: number
  reference_display?: string
  ratio: number
  score_pct: number
  has_reference: boolean
}

export interface MemberRadar {
  member_id: string
  member_name: string
  member_color: string
  dimensions: RadarDimension[]
}

const props = defineProps<{
  members: MemberRadar[]
  dimensionNames: string[]
}>()

const selectedIds = ref<string[]>([])

// Auto-select first 3 members if not initialized
const activeMembers = computed(() => {
  if (selectedIds.value.length === 0) {
    return props.members.slice(0, 3)
  }
  return props.members.filter(m => selectedIds.value.includes(m.member_id))
})

function toggleMember(id: string) {
  if (selectedIds.value.includes(id)) {
    if (selectedIds.value.length > 1) {
      selectedIds.value = selectedIds.value.filter(i => i !== id)
    }
  } else {
    if (selectedIds.value.length >= 3) {
      selectedIds.value.shift()
    }
    selectedIds.value.push(id)
  }
}

const isMemberActive = (id: string) => {
  if (selectedIds.value.length === 0) {
    return props.members.slice(0, 3).some(m => m.member_id === id)
  }
  return selectedIds.value.includes(id)
}

const themeStore = useThemeStore()

const chartOption = computed(() => {
  // 依赖 isDark 使该 computed 在主题切换时重新求值，从而重新读取 CSS 变量
  void themeStore.isDark

  const colorTextMuted = getCssVar('--text-muted', '#5D6B68')
  const colorStroke = getCssVar('--glass-stroke', 'rgba(0,0,0,0.1)')
  const colorOk = getCssVar('--ok', '#2A8F82')

  const indicators = props.dimensionNames.map(name => ({
    name,
    max: 120 // 120% cap
  }))

  const seriesData: any[] = []

  // DEV-GUIDE 7.9: 参考保额为虚线外圈 (100% 满额基准线)
  seriesData.push({
    name: '参考保额基准 (100%)',
    value: indicators.map(() => 100),
    symbol: 'none',
    lineStyle: {
      type: 'dashed',
      color: colorTextMuted,
      width: 1.5
    },
    itemStyle: {
      color: colorTextMuted
    },
    areaStyle: {
      color: 'transparent'
    }
  })

  // DEV-GUIDE 7.9: 成员多边形使用成员头像色 20% 填充
  activeMembers.value.forEach(m => {
    const values = m.dimensions.map(d => d.score_pct)
    const color = m.member_color || colorOk

    seriesData.push({
      name: m.member_name,
      value: values,
      symbol: 'circle',
      symbolSize: 5,
      lineStyle: {
        color: color,
        width: 2
      },
      itemStyle: {
        color: color
      },
      areaStyle: {
        color: color,
        opacity: 0.2 // 20% alpha
      }
    })
  })

  return {
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(15, 23, 42, 0.85)',
      borderColor: 'rgba(255, 255, 255, 0.1)',
      textStyle: { color: '#fff', fontSize: 12 },
      formatter: (params: any) => {
        if (params.name.includes('基准')) {
          return `<div style="font-weight:bold">${params.name}</div><div>100% 充分覆盖基准</div>`
        }
        const member = activeMembers.value.find(m => m.member_name === params.name)
        if (!member) return params.name

        let html = `<div style="font-weight:bold;margin-bottom:4px">${member.member_name} 保障覆盖雷达</div>`
        member.dimensions.forEach(d => {
          const refText = d.has_reference ? `参考: ${d.reference_display}` : '未设参考'
          html += `<div style="display:flex;justify-content:space-between;gap:12px">
            <span>${d.name}:</span>
            <b>${d.effective_display}</b>
            <span style="color:var(--text-muted);font-size:11px">(${refText} · ${d.score_pct}%)</span>
          </div>`
        })
        return html
      }
    },
    radar: {
      indicator: indicators,
      shape: 'polygon',
      splitNumber: 4,
      axisName: {
        color: colorTextMuted,
        fontSize: 12,
        fontWeight: 'bold'
      },
      splitLine: {
        lineStyle: {
          color: colorStroke
        }
      },
      splitArea: {
        show: true,
        areaStyle: {
          color: ['rgba(255, 255, 255, 0.01)', 'rgba(255, 255, 255, 0.03)']
        }
      },
      axisLine: {
        lineStyle: {
          color: colorStroke
        }
      }
    },
    series: [
      {
        type: 'radar',
        data: seriesData
      }
    ]
  }
})
</script>

<template>
  <div class="radar-card glass">
    <div class="radar-header">
      <div class="header-left">
        <h3 class="radar-title">六维保障覆盖雷达</h3>
        <span class="radar-subtitle">有效保额对比参考保额（虚线为 100% 充足基准）</span>
      </div>

      <!-- Member Select Pills (Up to 3) -->
      <div v-if="members.length > 1" class="member-pills">
        <button
          v-for="m in members"
          :key="m.member_id"
          class="member-pill"
          :class="{ active: isMemberActive(m.member_id) }"
          :style="{
            borderColor: isMemberActive(m.member_id) ? m.member_color : 'transparent',
            backgroundColor: isMemberActive(m.member_id)
              ? `color-mix(in oklch, ${m.member_color} 20%, transparent)`
              : 'var(--glass-fill-strong)'
          }"
          @click="toggleMember(m.member_id)"
        >
          <span class="pill-dot" :style="{ backgroundColor: m.member_color }"></span>
          <span>{{ m.member_name }}</span>
        </button>
      </div>
    </div>

    <!-- Chart -->
    <div class="chart-box">
      <VChart :option="chartOption" autoresize class="echarts-radar" />
    </div>
  </div>
</template>

<style scoped>
.radar-card {
  padding: var(--sp-4);
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
  position: relative;
}

.radar-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: var(--sp-2);
}

.radar-title {
  font-size: var(--fs-16);
  font-weight: 700;
  margin: 0;
}

.radar-subtitle {
  font-size: var(--fs-12);
  color: var(--text-muted);
}

.member-pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.member-pill {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 16px;
  font-size: var(--fs-12);
  cursor: pointer;
  border: 1px solid var(--glass-stroke);
  transition: all 0.15s ease;
  color: var(--text-muted);
}

.member-pill.active {
  color: var(--text);
  font-weight: 600;
}

.pill-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.chart-box {
  width: 100%;
  height: 320px;
}

.echarts-radar {
  width: 100%;
  height: 100%;
}
</style>
