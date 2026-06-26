# frontend — 舆情监测 Dashboard（Vue 3 + Vite + ECharts）

纯展示前端：采集总量、AI 态势总结、媒体报道趋势、情感分析、热点/最新列表 + 筛选器。
数据全部来自后端 `/api/stats` 与 `/api/posts`。**不含任何采集逻辑。**

## 运行

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173  （/api 自动代理到 127.0.0.1:8000）
```

生产构建：
```bash
# 后端不在同源时，先设置 .env：VITE_API_BASE=http://你的后端:8000
npm run build      # 产物在 dist/，可用任意静态服务器托管
npm run preview
```

## 行为

- **后端可达**：实时展示真实数据，每 60s 增量刷新（仅前端展示轮询，与采集防封无关）。
- **后端不可达**：自动回退 `src/mock.js` 的演示数据，页面照常渲染，右上角显示「演示数据」徽标，不报错、不崩。
- **AI 字段为空**（未跑 Step 7）：情感显示「未分析」，「AI 分析 / 报告」Tab 显示占位文案。

## 区块

| 区块 | 组件 | 数据 |
|------|------|------|
| 顶部统计卡 | `StatCards.vue` | `/api/stats` today_total/total/by_source |
| AI 态势总结 | `SummaryCard.vue` | `stats.ai_summary`（空则占位） |
| 报道趋势折线 | `TrendChart.vue` | `stats.trend`（近7天×来源） |
| 情感分析 环形+条形 | `SentimentChart.vue` | `stats.by_sentiment` + `by_source` |
| 筛选器 | `FiltersBar.vue` | source/sentiment/keyword/start/end |
| 列表（原始/AI/报告 Tab） | `PostList.vue` | `/api/posts` 分页 |
