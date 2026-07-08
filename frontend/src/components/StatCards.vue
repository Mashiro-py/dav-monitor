<script setup>
import { computed } from 'vue'
const props = defineProps({ stats: { type: Object, default: () => ({}) } })

const srcLabel = { weibo: '微博', x: 'X', wechat: '公众号' }
const sources = computed(() => {
  const bs = props.stats.by_source || {}
  return Object.keys(srcLabel).map(k => ({ key: k, label: srcLabel[k], count: bs[k] || 0 }))
})
// 公众号全文补采进度 {done, total, pending}
const wx = computed(() => props.stats.wx_fulltext || null)
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
        <span v-if="s.key === 'wechat' && wx && wx.total" class="wx-progress"
              :title="`已补全文 ${wx.done} 篇，待补 ${wx.pending} 篇`">全文 {{ wx.done }}/{{ wx.total }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wx-progress { margin-left: 6px; font-size: 11px; color: #15803d; background: #dcfce7; padding: 1px 6px; border-radius: 8px; white-space: nowrap; }
</style>
