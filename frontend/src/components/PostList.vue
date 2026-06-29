<script setup>
import { ref, computed } from 'vue'
import DOMPurify from 'dompurify'

const props = defineProps({
  result: { type: Object, default: () => ({ items: [], total: 0, page: 1, page_size: 20 }) },
  stats: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['page'])

const tab = ref('raw')   // raw | ai | report
const selected = ref(null)
const srcLabel = { weibo: '微博', x: 'X', wechat: '公众号' }
const sentLabel = { positive: '正面', negative: '负面', neutral: '中性', unknown: '未分析' }

const items = computed(() => props.result.items || [])
const totalPages = computed(() => Math.max(1, Math.ceil((props.result.total || 0) / (props.result.page_size || 20))))
const page = computed(() => props.result.page || 1)

function go(p) { if (p >= 1 && p <= totalPages.value) emit('page', p) }
function fmt(t) { return t ? String(t).replace('T', ' ').replace('Z', '').slice(0, 16) : '' }
function sclass(s) { return 's-' + (s || 'unknown') }
const aiSummary = computed(() => (props.stats.ai_summary || '').trim())

function openDetail(p) { selected.value = p }

// 链接新窗口打开 + 图片防盗链/懒加载（净化后处理）
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A') { node.setAttribute('target', '_blank'); node.setAttribute('rel', 'noopener noreferrer') }
  if (node.tagName === 'IMG') { node.setAttribute('referrerpolicy', 'no-referrer'); node.setAttribute('loading', 'lazy') }
})
function safeHtml(html) {
  return DOMPurify.sanitize(html || '', { ADD_ATTR: ['target'] })
}
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
      <div v-for="p in items" :key="p.id" class="post clickable" @click="openDetail(p)">
        <div class="meta">
          <span class="tag" :class="p.source">{{ srcLabel[p.source] || p.source }}</span>
          <strong style="color:#1e2a44">{{ p.account_name }}</strong>
          <span>{{ fmt(p.publish_time) }}</span>
          <span v-if="p.stats">👍{{ p.stats.likes || 0 }} 💬{{ p.stats.comments || 0 }} 🔁{{ p.stats.reposts || 0 }}</span>
          <span :class="sclass(p.sentiment)">● {{ sentLabel[p.sentiment || 'unknown'] }}</span>
        </div>
        <div v-if="p.title" class="title">{{ p.title }}</div>
        <div class="body">{{ (p.content || '').slice(0, 180) }}</div>
        <div class="row-ft">
          <span class="more">查看全文 ›</span>
          <a v-if="p.original_url && p.original_url !== '#'" :href="p.original_url" target="_blank" @click.stop>🔗 原文</a>
        </div>
      </div>
    </div>

    <!-- AI 分析 -->
    <div v-else-if="tab === 'ai'">
      <div v-if="!items.length" class="empty">暂无数据</div>
      <div v-for="p in items" :key="p.id" class="post clickable" @click="openDetail(p)">
        <div class="meta">
          <span class="tag" :class="p.source">{{ srcLabel[p.source] || p.source }}</span>
          <strong style="color:#1e2a44">{{ p.account_name }}</strong>
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

  <!-- 详情弹窗：图文完整展示 -->
  <div v-if="selected" class="detail-mask" @click.self="selected = null">
    <div class="detail-box">
      <div class="detail-hd">
        <div>
          <span class="tag" :class="selected.source">{{ srcLabel[selected.source] || selected.source }}</span>
          <strong>{{ selected.account_name }}</strong>
          <span class="dim">{{ fmt(selected.publish_time) }}</span>
        </div>
        <button @click="selected = null">✕</button>
      </div>
      <div v-if="selected.title" class="detail-title">{{ selected.title }}</div>
      <div v-if="selected.content_html" class="detail-body rich" v-html="safeHtml(selected.content_html)"></div>
      <div v-else class="detail-body plain">{{ selected.content || '（无正文）' }}</div>
      <div class="detail-ft">
        <a v-if="selected.original_url && selected.original_url !== '#'" :href="selected.original_url" target="_blank">🔗 打开原文</a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.post.clickable { cursor: pointer; }
.post.clickable:hover { background: #f5f8fd; }
.row-ft { display: flex; gap: 14px; align-items: center; margin-top: 6px; }
.row-ft .more { color: #2563eb; font-size: 12px; }

.detail-mask { position: fixed; inset: 0; background: rgba(30, 42, 68, .45); display: flex; align-items: center; justify-content: center; z-index: 50; padding: 20px; }
.detail-box { background: #ffffff; border: 1px solid #d9e2ef; border-radius: 12px; max-width: 760px; width: 100%; max-height: 86vh; overflow: auto; padding: 18px 20px; box-shadow: 0 10px 30px rgba(30,42,68,.15); }
.detail-hd { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px; }
.detail-hd strong { color: #1e2a44; }
.detail-hd button { background: none; border: none; color: #6b7790; font-size: 18px; cursor: pointer; }
.dim { color: #6b7790; font-size: 12px; margin-left: 8px; }
.detail-title { font-size: 18px; font-weight: 700; margin: 6px 0 12px; line-height: 1.4; color: #1e2a44; }
.detail-body { line-height: 1.85; color: #2b3650; font-size: 15px; }
.detail-body.plain { white-space: pre-wrap; }
.detail-ft { margin-top: 16px; }
.detail-ft a { color: #2563eb; }
/* v-html 注入内容需 :deep() 才能命中 */
.rich :deep(img) { max-width: 100%; height: auto; border-radius: 8px; margin: 8px 0; display: block; }
.rich :deep(a) { color: #2563eb; word-break: break-all; }
.rich :deep(p) { margin: 8px 0; }
.rich :deep(video) { max-width: 100%; }
</style>
