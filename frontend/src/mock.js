// 无真实后端时的 mock 数据，保证 Dashboard 能渲染不崩。
function daysAgo(n) {
  const d = new Date(Date.now() - n * 86400000)
  return d.toISOString().slice(0, 10)
}

export const MOCK_STATS = {
  total: 128,
  today_total: 17,
  by_source: { weibo: 70, x: 41, wechat: 17 },
  by_sentiment: { positive: 52, negative: 23, neutral: 48, unknown: 5 },
  trend: (() => {
    const t = {}
    for (let i = 6; i >= 0; i--) {
      t[daysAgo(i)] = {
        weibo: 6 + ((i * 7) % 9),
        x: 3 + ((i * 5) % 6),
        wechat: 1 + ((i * 3) % 4),
      }
    }
    return t
  })(),
  ai_summary: '',
}

const SAMPLE = [
  { source: 'weibo', account_name: '机器之心', content: '最新大模型发布，多项基准刷新纪录，社区反响热烈。', sentiment: 'positive' },
  { source: 'x', account_name: 'TheRundownAI', content: 'Breaking: a new open-source model challenges the frontier labs.', sentiment: 'neutral' },
  { source: 'wechat', account_name: '量子位', content: '深度报道：国产芯片在推理场景的实测表现与争议。', sentiment: 'negative' },
  { source: 'weibo', account_name: '量子位', content: '行业活动现场：多家厂商展示端侧 AI 新品。', sentiment: 'neutral' },
  { source: 'x', account_name: 'StanfordHAI', content: 'New report on AI policy and its societal impact released today.', sentiment: 'positive' },
]

export function mockPosts(params = {}) {
  let items = []
  for (let i = 0; i < 24; i++) {
    const s = SAMPLE[i % SAMPLE.length]
    items.push({
      id: i + 1,
      source: s.source,
      account_name: s.account_name,
      author_name: s.account_name,
      title: s.source === 'wechat' ? s.content.slice(0, 16) : '',
      content: s.content,
      original_url: '#',
      publish_time: new Date(Date.now() - i * 3600000).toISOString() + 'Z',
      sentiment: s.sentiment,
      keywords: ['AI', '大模型'],
      stats: { likes: 100 - i, comments: 20, reposts: 5 },
      media_urls: [],
    })
  }
  if (params.source) items = items.filter(i => i.source === params.source)
  if (params.sentiment) items = items.filter(i => i.sentiment === params.sentiment)
  if (params.keyword) items = items.filter(i => (i.content || '').includes(params.keyword) || (i.account_name || '').includes(params.keyword))
  const page = params.page || 1, ps = params.page_size || 20
  return { total: items.length, page, page_size: ps, items: items.slice((page - 1) * ps, page * ps) }
}
