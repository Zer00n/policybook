/**
 * ECharts 使用 Canvas 渲染坐标轴、线条与柱状图等图形元素，Canvas 2D 的
 * fillStyle/strokeStyle 不支持解析 CSS 自定义属性（var(--xxx)），必须传入
 * 真实的颜色值。此函数在调用时读取当前生效的 CSS 自定义属性值，
 * 配合组件内对主题状态的依赖即可让图表颜色跟随主题切换更新。
 */
export function getCssVar(name: string, fallback = '#000000'): string {
  if (typeof window === 'undefined') return fallback
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return value || fallback
}
