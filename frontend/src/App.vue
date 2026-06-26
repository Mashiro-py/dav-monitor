<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { getStats, getPosts, usingMock } from './api.js'
import StatCards from './components/StatCards.vue'
import SummaryCard from './components/SummaryCard.vue'
import TrendChart from './components/TrendChart.vue'
import SentimentChart from './components/SentimentChart.vue'
import FiltersBar from './components/FiltersBar.vue'
import PostList from './components/PostList.vue'

const stats = ref({})
const result = ref({ items: [], total: 0, page: 1, page_size: 20 })
const filters = ref({ source: '', sentiment: '', keyword: '', start: '', end: '' })
let timer = null

async function loadStats() { stats.value = await getStats() }
async function loadPosts(page = 1) {
  result.value = await getPosts({ ...filters.value, page, page_size: 20 })
}
function onFilter(f) { filters.value = f; loadPosts(1) }
function onPage(p) { loadPosts(p) }

onMounted(async () => {
  await Promise.all([loadStats(), loadPosts(1)])
  // 增量刷新：每 60s 拉一次（前端轮询展示，不涉及采集；与防封无关）
  timer = setInterval(() => { loadStats(); loadPosts(result.value.page || 1) }, 60000)
})
onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<template>
  <div class="topbar">
    <h1>🛰 大V动态舆情监测</h1>
    <span class="sub">微博 · X · 公众号 · 统一展示</span>
    <span v-if="usingMock" class="mock-badge">⚠ 演示数据（后端未连接）</span>
  </div>

  <StatCards :stats="stats" />

  <div class="grid cols-2" style="margin-top:14px">
    <TrendChart :trend="stats.trend || {}" />
    <SentimentChart :stats="stats" />
  </div>

  <div style="margin-top:14px"><SummaryCard :stats="stats" /></div>

  <div style="margin-top:14px"><FiltersBar @change="onFilter" /></div>

  <div style="margin-top:14px">
    <PostList :result="result" :stats="stats" @page="onPage" />
  </div>
</template>
