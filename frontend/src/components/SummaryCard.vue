<script setup>
// AI 热点态势分析（DeepSeek）：热点事件 / 主要观点 / 整体总结，中英双语。
// 数据自取自 /api/analysis/*；“立即分析”经 nginx 注入 token 调 /api/analysis/run（前端无密钥）。
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { getAnalysisLatest, getAnalysisQuota, getAnalysisHistory, runAnalysis } from '../api.js'

const lang = ref('zh')
const analysis = ref(null)        // 当前展示的一期（默认最新）
const quota = ref(null)           // {used, limit, remaining, last_run_at, running}
const historyItems = ref([])
const selectedId = ref('')        // 往期下拉选中 id（'' = 最新）
const running = ref(false)
const error = ref('')
let timer = null

const L = computed(() => lang.value === 'zh' ? {
  title: '📈 AI 热点态势分析', run: '⚡ 立即分析', runBusy: '⏳ 分析中…约需 30~60 秒',
  runOut: '今日次数已用完', left: (r, l) => `今日剩余 ${r}/${l} 次`,
  events: '🔥 热点事件', opinions: '💬 主要观点', overall: '📝 整体态势',
  posts: (n) => `相关 ${n} 条`, vs: '⚡ 对立观点：', history: '往期记录',
  latestOpt: '（最新）', auto: '自动', manual: '手动',
  empty: '还没有分析记录——点右上「立即分析」生成第一份，或等待每日自动分析（约 08:30）。',
  metaOf: (a) => `基于 ${fmt(a.range_start)} ~ ${fmt(a.range_end)} · 覆盖 ${a.covered_count}${a.total_count > a.covered_count ? `/${a.total_count} 条（超上下文已截断）` : ' 条'}`,
  noQuotaNote: '（本次失败未消耗配额）',
} : {
  title: '📈 AI Trend Analysis', run: '⚡ Analyze Now', runBusy: '⏳ Analyzing… ~30-60s',
  runOut: 'Daily limit reached', left: (r, l) => `${r}/${l} left today`,
  events: '🔥 Hot Events', opinions: '💬 Key Opinions', overall: '📝 Overall',
  posts: (n) => `${n} posts`, vs: '⚡ Opposing view: ', history: 'History',
  latestOpt: ' (latest)', auto: 'auto', manual: 'manual',
  empty: 'No analysis yet — click "Analyze Now", or wait for the daily auto run (~08:30 CST).',
  metaOf: (a) => `Window ${fmt(a.range_start)} ~ ${fmt(a.range_end)} · ${a.covered_count}${a.total_count > a.covered_count ? `/${a.total_count} items (truncated)` : ' items'}`,
  noQuotaNote: ' (quota not consumed)',
})

// 双语字段取值：优先当前语言，缺失回退另一语言
const t = (o) => (o && (o[lang.value] || o.zh || o.en)) || ''

// UTC(带Z) → 北京时间 "MM-DD HH:mm"
function fmt(s) {
  if (!s) return ''
  const d = new Date(s)
  if (isNaN(d)) return String(s).slice(5, 16)
  const bj = new Date(d.getTime() + 8 * 3600 * 1000)
  const p = (n) => String(n).padStart(2, '0')
  return `${p(bj.getUTCMonth() + 1)}-${p(bj.getUTCDate())} ${p(bj.getUTCHours())}:${p(bj.getUTCMinutes())}`
}

const srcLabel = { weibo: '微博', wechat: '公众号', x: 'X' }
const srcLine = computed(() => {
  const st = analysis.value?.source_stats || {}
  return Object.entries(st).map(([k, v]) => `${srcLabel[k] || k}${v}`).join(' / ')
})
const result = computed(() => analysis.value?.result || {})
const canRun = computed(() => !running.value && (quota.value ? quota.value.remaining > 0 : true))

async function refresh() {
  const [latest, q] = await Promise.all([getAnalysisLatest(), getAnalysisQuota()])
  quota.value = q
  if (!selectedId.value) analysis.value = latest   // 正在看往期时不打断
}

async function loadHistory() {
  historyItems.value = await getAnalysisHistory(30)
}

function pickHistory() {
  if (!selectedId.value) { refresh(); return }
  const it = historyItems.value.find(x => String(x.id) === String(selectedId.value))
  if (it) analysis.value = it
}

async function runNow() {
  if (!canRun.value) return
  running.value = true
  error.value = ''
  try {
    const r = await runAnalysis()
    analysis.value = r.analysis
    quota.value = r.quota
    selectedId.value = ''
    loadHistory()
  } catch (e) {
    error.value = (e.message || '分析失败') + L.value.noQuotaNote
    getAnalysisQuota().then(q => { if (q) quota.value = q })
  } finally {
    running.value = false
  }
}

onMounted(async () => {
  await refresh()
  loadHistory()
  timer = setInterval(refresh, 60000)
})
onBeforeUnmount(() => timer && clearInterval(timer))
</script>

<template>
  <div class="card">
    <!-- 头部：标题 | 语言切换 | 往期 | 配额 + 立即分析 -->
    <div class="hd">
      <h3 style="margin-bottom:0">{{ L.title }}</h3>
      <div class="lang-sw">
        <button :class="{ on: lang === 'zh' }" @click="lang = 'zh'">中文</button>
        <button :class="{ on: lang === 'en' }" @click="lang = 'en'">EN</button>
      </div>
      <select v-if="historyItems.length" v-model="selectedId" class="his" @change="pickHistory" :title="L.history">
        <option value="">{{ fmt(historyItems[0]?.created_at) }}{{ L.latestOpt }}</option>
        <option v-for="h in historyItems.slice(1)" :key="h.id" :value="h.id">
          {{ fmt(h.created_at) }} · {{ h.trigger_type === 'auto' ? L.auto : L.manual }}
        </option>
      </select>
      <span class="spacer"></span>
      <span v-if="quota" class="quota" :class="{ zero: quota.remaining === 0 }">{{ L.left(quota.remaining, quota.limit) }}</span>
      <button class="run" :disabled="!canRun" @click="runNow">
        {{ running ? L.runBusy : (quota && quota.remaining === 0 ? L.runOut : L.run) }}
      </button>
    </div>

    <!-- 错误条：可读文案，不白屏 -->
    <div v-if="error" class="err">⚠️ {{ error }}</div>

    <!-- 空状态 -->
    <div v-if="!analysis" class="summary"><span class="placeholder">{{ L.empty }}</span></div>

    <template v-else>
      <!-- 元信息：时间范围 / 覆盖条数 / 来源分布 / 触发方式 -->
      <div class="meta-line">
        {{ L.metaOf(analysis) }}
        <template v-if="srcLine">（{{ srcLine }}）</template>
        · {{ analysis.trigger_type === 'auto' ? L.auto : L.manual }} · {{ fmt(analysis.created_at) }}
      </div>

      <!-- 🔥 热点事件 -->
      <div class="sec">{{ L.events }}</div>
      <div v-if="!(result.hot_events || []).length" class="none">—</div>
      <div v-for="(ev, i) in result.hot_events" :key="'e' + i" class="event">
        <div class="ev-hd">
          <span class="ev-title">{{ t(ev.title) }}</span>
          <span v-if="ev.post_count" class="ev-cnt">{{ L.posts(ev.post_count) }}</span>
        </div>
        <div class="ev-meta">
          <span v-for="(a, j) in (ev.accounts || []).slice(0, 6)" :key="j" class="chip">{{ a }}</span>
          <span v-for="s in (ev.sources || [])" :key="s" class="tag" :class="s">{{ srcLabel[s] || s }}</span>
        </div>
        <div class="ev-brief">{{ t(ev.brief) }}</div>
      </div>

      <!-- 💬 主要观点 -->
      <div class="sec">{{ L.opinions }}</div>
      <div v-if="!(result.key_opinions || []).length" class="none">—</div>
      <div v-for="(op, i) in result.key_opinions" :key="'o' + i" class="opinion">
        <div><strong>{{ t(op.topic) }}</strong>
          <span class="op-acc"> — {{ (op.accounts || []).join('、') }}</span>
        </div>
        <div class="op-text">{{ t(op.opinion) }}</div>
        <div v-if="op.has_disagreement && t(op.disagreement)" class="op-vs">{{ L.vs }}{{ t(op.disagreement) }}</div>
      </div>

      <!-- 📝 整体态势 -->
      <div class="sec">{{ L.overall }}</div>
      <div class="overall">{{ t(result.summary) || '—' }}</div>
    </template>
  </div>
</template>

<style scoped>
.hd { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.spacer { flex: 1; }

.lang-sw { display: flex; border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
.lang-sw button { background: #fff; border: none; padding: 4px 12px; font-size: 12px; color: var(--muted); cursor: pointer; }
.lang-sw button.on { background: var(--accent-soft); color: var(--accent); font-weight: 600; }

.his { background: #fff; border: 1px solid var(--border); color: var(--muted); border-radius: 8px; padding: 4px 8px; font-size: 12px; max-width: 190px; }

.quota { font-size: 12px; color: var(--accent); background: var(--accent-soft); padding: 3px 10px; border-radius: 10px; white-space: nowrap; }
.quota.zero { color: var(--muted); background: var(--panel2); }

.run { background: var(--accent); color: #fff; border: none; border-radius: 8px; padding: 7px 14px; font-size: 13px; cursor: pointer; white-space: nowrap; }
.run:hover:not(:disabled) { background: #1d4fd7; }
.run:disabled { opacity: .5; cursor: default; }

.err { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; border-radius: 8px; padding: 8px 12px; font-size: 13px; margin-bottom: 10px; }

.meta-line { font-size: 12px; color: var(--muted); padding: 6px 0 2px; }

/* 三个板块标题：加大字号，颜色随板块主色（蓝/琥珀/绿，与页面 tag 色系一致） */
.sec { font-size: 16px; font-weight: 700; color: var(--text); margin: 16px 0 10px; padding-top: 12px; border-top: 1px dashed var(--border); }
.none { color: var(--muted); font-size: 13px; }

/* 🔥 热点事件：浅蓝卡片 + 蓝色左边条 */
.event { background: var(--accent-soft); border: 1px solid #cfe0fb; border-left: 3px solid var(--accent); border-radius: 10px; padding: 12px 14px; margin-bottom: 10px; }
.ev-hd { display: flex; align-items: baseline; gap: 8px; }
.ev-title { font-weight: 600; color: var(--text); font-size: 14px; }
.ev-cnt { font-size: 11px; color: var(--accent); background: #fff; border: 1px solid #cfe0fb; padding: 1px 8px; border-radius: 8px; white-space: nowrap; }
.ev-meta { display: flex; flex-wrap: wrap; gap: 5px; margin: 6px 0; }
.chip { font-size: 11px; background: #fff; border: 1px solid var(--border); color: var(--muted); padding: 1px 8px; border-radius: 9px; }
.ev-brief { color: #475068; line-height: 1.7; font-size: 13px; }

/* 💬 主要观点：浅琥珀卡片 + 琥珀左边条 */
.opinion { background: #fff9ec; border: 1px solid #f1e2c1; border-left: 3px solid var(--neu); border-radius: 10px; padding: 11px 14px; margin-bottom: 10px; font-size: 13px; }
.opinion strong { font-size: 14px; }
.op-acc { color: var(--muted); font-size: 12px; }
.op-text { color: #475068; line-height: 1.7; margin-top: 4px; }
.op-vs { color: var(--neg); font-size: 12px; margin-top: 5px; }

/* 📝 整体态势：浅绿卡片 + 绿色左边条 */
.overall { background: #e9f7ef; border: 1px solid #cde8d8; border-left: 3px solid var(--pos); border-radius: 10px; padding: 12px 14px; line-height: 1.8; font-size: 13.5px; color: #2b3650; }

.summary { line-height: 1.75; }
.summary .placeholder { color: var(--muted); font-style: italic; }
</style>
