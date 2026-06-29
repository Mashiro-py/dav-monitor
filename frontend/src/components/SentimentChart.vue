<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({ stats: { type: Object, default: () => ({}) } })
const ringEl = ref(null)
const barEl = ref(null)
let ring = null, bar = null

const SENT = {
  positive: { label: '正面', color: '#16a34a' },
  negative: { label: '负面', color: '#e11d48' },
  neutral: { label: '中性', color: '#f59e0b' },
  unknown: { label: '未分析', color: '#94a3b8' },
}
const srcLabel = { weibo: '微博', x: 'X', wechat: '公众号' }

function render() {
  const bsent = props.stats.by_sentiment || {}
  const ringData = Object.keys(SENT)
    .map(k => ({ name: SENT[k].label, value: bsent[k] || 0, itemStyle: { color: SENT[k].color } }))
    .filter(d => d.value > 0)
  if (ring) {
    ring.setOption({
      tooltip: { trigger: 'item' },
      legend: { bottom: 0, textStyle: { color: '#6b7790' } },
      series: [{
        type: 'pie', radius: ['45%', '70%'], center: ['50%', '44%'],
        label: { color: '#1e2a44' },
        data: ringData.length ? ringData : [{ name: '暂无', value: 1, itemStyle: { color: '#e2e8f0' } }],
      }],
    }, true)
  }
  const bsrc = props.stats.by_source || {}
  const keys = Object.keys(srcLabel)
  if (bar) {
    bar.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 60, right: 16, top: 10, bottom: 24 },
      xAxis: { type: 'value', axisLabel: { color: '#6b7790' }, splitLine: { lineStyle: { color: '#eef0f5' } } },
      yAxis: { type: 'category', data: keys.map(k => srcLabel[k]), axisLabel: { color: '#6b7790' } },
      series: [{
        type: 'bar', barWidth: 16,
        itemStyle: { color: '#2563eb', borderRadius: [0, 6, 6, 0] },
        data: keys.map(k => bsrc[k] || 0),
      }],
    }, true)
  }
}

function resize() { ring && ring.resize(); bar && bar.resize() }
onMounted(() => {
  ring = echarts.init(ringEl.value)
  bar = echarts.init(barEl.value)
  render(); window.addEventListener('resize', resize)
})
onBeforeUnmount(() => { window.removeEventListener('resize', resize); ring && ring.dispose(); bar && bar.dispose() })
watch(() => props.stats, render, { deep: true })
</script>

<template>
  <div class="card">
    <h3>💬 情感分析</h3>
    <div ref="ringEl" class="chart" style="height: 200px"></div>
    <div ref="barEl" class="chart" style="height: 120px"></div>
  </div>
</template>
