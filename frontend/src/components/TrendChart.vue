<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ trend: { type: Object, default: () => ({}) } })
const el = ref(null)
let chart = null

const SRC = [
  { key: 'weibo', label: '微博', color: '#ff8a9b' },
  { key: 'x', label: 'X', color: '#6fb3ff' },
  { key: 'wechat', label: '公众号', color: '#5fd08a' },
]

function render() {
  if (!chart) return
  const days = Object.keys(props.trend || {}).sort()
  const series = SRC.map(s => ({
    name: s.label, type: 'line', smooth: true, showSymbol: false,
    itemStyle: { color: s.color }, areaStyle: { opacity: 0.06 },
    data: days.map(d => (props.trend[d] && props.trend[d][s.key]) || 0),
  }))
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#8b93a7' }, top: 0 },
    grid: { left: 40, right: 16, top: 36, bottom: 28 },
    xAxis: { type: 'category', data: days, axisLabel: { color: '#8b93a7' }, axisLine: { lineStyle: { color: '#2a3146' } } },
    yAxis: { type: 'value', axisLabel: { color: '#8b93a7' }, splitLine: { lineStyle: { color: '#1e2438' } } },
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
