<script setup>
import { computed } from 'vue'
const props = defineProps({ stats: { type: Object, default: () => ({}) } })

const srcLabel = { weibo: '微博', x: 'X', wechat: '公众号' }
const sources = computed(() => {
  const bs = props.stats.by_source || {}
  return Object.keys(srcLabel).map(k => ({ key: k, label: srcLabel[k], count: bs[k] || 0 }))
})
</script>

<template>
  <div class="grid cols-4">
    <div class="card stat">
      <div class="num">{{ stats.today_total ?? 0 }}</div>
      <div class="lbl">今日采集总量</div>
      <div class="sub">累计 {{ stats.total ?? 0 }} 条</div>
    </div>
    <div class="card stat" v-for="s in sources" :key="s.key">
      <div class="num">{{ s.count }}</div>
      <div class="lbl">{{ s.label }}来源</div>
      <div class="sub">
        <span class="tag" :class="s.key">{{ s.label }}</span>
      </div>
    </div>
  </div>
</template>
