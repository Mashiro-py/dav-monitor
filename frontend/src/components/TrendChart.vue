<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ trend: { type: Object, default: () => ({}) } })
const el = ref(null)
let chart = null

const SRC = [
  { key: 'weibo', label: '微博', color: '#e0608f' },
  { key: 'x', label: 'X', color: '#2563eb' },
  { key: 'wechat', label: '公众号', color: '#0ea5a4' },
]

function render() {
  if (!chart) return
  const days = Object.keys(props.trend || {}).sort()
  const series = SRC.map(s => ({
    name: s.label, type: 'line', smooth: true, showSymbol: false,
    itemStyle: { color: s.color }, areaStyle: { opacity: 0.10 },
    data: days.map(d => (props.trend[d] && props.trend[d][s.key]) || 0),
  }))
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#6b7790' }, top: 0 },
    grid: { left: 40, right: 16, top: 36, bottom: 28 },
    xAxis: { type: 'category', data: days, axisLabel: { color: '#6b7790' }, axisLine: { lineStyle: { color: '#d9e2ef' } } },
    yAxis: { type: 'value', axisLabel: { color: '#6b7790' }, splitLine: { lineStyle: { color: '#eef0f5' } } },
    series,
  }, true)
}

function resize() { chart && chart.resize() }
onMounted(() => { chart = echarts.init(el.value); render(); window.addEventListener('resize', resize) })
onBeforeUnmount(() => { window.removeEventListener('resize', resize); chart && chart.dispose() })
watch(() => props.trend, render, { deep: true })
</script>

<template>
  <div class="card">
    <h3>🗞 媒体报道趋势（近 7 天 · 按来源）</h3>
    <div ref="el" class="chart"></div>
  </div>
</template>
