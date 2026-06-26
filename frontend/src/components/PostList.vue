<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  result: { type: Object, default: () => ({ items: [], total: 0, page: 1, page_size: 20 }) },
  stats: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['page'])

const tab = ref('raw')   // raw | ai | report
const srcLabel = { weibo: '微博', x: 'X', wechat: '公众号' }
const sentLabel = { positive: '正面', negative: '负面', neutral: '中性', unknown: '未分析' }

const items = computed(() => props.result.items || [])
const totalPages = computed(() => Math.max(1, Math.ceil((props.result.total || 0) / (props.result.page_size || 20))))
const page = computed(() => props.result.page || 1)

function go(p) { if (p >= 1 && p <= totalPages.value) emit('page', p) }
function fmt(t) { return t ? String(t).replace('T', ' ').replace('Z', '').slice(0, 16) : '' }
function sclass(s) { return 's-' + (s || 'unknown') }
const aiSummary = computed(() => (props.stats.ai_summary || '').trim())
</script>

<template>
  <div class="card">
    <div class="tabs">
      <button :class="{ active: tab === 'raw' }" @click="tab = 'raw'">原始内容</button>
      <button :class="{ active: tab === 'ai' }" @click="tab = 'ai'">AI 分析</button>
      <button :class="{ active: tab === 'report' }" @click="tab = 'report'">报告</button>
    </div>

    <!-- 原始内容 -->
    <div v-if="tab === 'raw'">
      <div v-if="!items.length" class="empty">暂无数据</div>
      <div v-for="p in items" :key="p.id" class="post">
        <div class="meta">
          <span class="tag" :class="p.source">{{ srcLabel[p.source] || p.source }}</span>
          <strong style="color:#cdd3e2">{{ p.account_name }}</strong>
          <span>{{ fmt(p.publish_time) }}</span>
          <span v-if="p.stats">👍{{ p.stats.likes || 0 }} 💬{{ p.stats.comments || 0 }} 🔁{{ p.stats.reposts || 0 }}</span>
          <span :class="sclass(p.sentiment)">● {{ sentLabel[p.sentiment || 'unknown'] }}</span>
        </div>
        <div v-if="p.title" class="title">{{ p.title }}</div>
        <div class="body">{{ (p.content || '').slice(0, 180) }}</div>
        <div style="margin-top:6px"><a v-if="p.original_url && p.original_url !== '#'" :href="p.original_url" target="_blank">🔗 原文</a></div>
      </div>
    </div>

    <!-- AI 分析 -->
    <div v-else-if="tab === 'ai'">
      <div v-if="!items.length" class="empty">暂无数据</div>
      <div v-for="p in items" :key="p.id" class="post">
        <div class="meta">
          <span class="tag" :class="p.source">{{ srcLabel[p.source] || p.source }}</span>
          <strong style="color:#cdd3e2">{{ p.account_name }}</strong>
          <span :class="sclass(p.sentiment)">● {{ sentLabel[p.sentiment || 'unknown'] }}</span>
        </div>
        <div class="body">{{ (p.content || '').slice(0, 120) }}</div>
        <div style="margin-top:6px">
          <template v-if="p.keywords && p.keywords.length">
            <span v-for="(k, i) in p.keywords" :key="i" class="tag kw" style="margin-right:4px">#{{ k }}</span>
          </template>
          <span v-else class="s-unknown" style="font-size:12px">关键词/情感未分析（接入 Step 7 后自动填充）</span>
        </div>
      </div>
    </div>

    <!-- 报告 -->
    <div v-else class="summary">
      <template v-if="aiSummary">{{ aiSummary }}</template>
      <div v-else class="empty">报告生成中 / 开发中：接入 AI 分析层后展示每日舆情报告。</div>
    </div>

    <div v-if="tab !== 'report'" class="pager">
      <button :disabled="page <= 1" @click="go(page - 1)">上一页</button>
      <span>{{ page }} / {{ totalPages }}（共 {{ result.total || 0 }} 条）</span>
      <button :disabled="page >= totalPages" @click="go(page + 1)">下一页</button>
    </div>
  </div>
</template>
