# 大V动态采集 + 舆情展示系统

一个端到端系统，在**不被封号的前提下尽量及时**地采集微博 / X(推特) / 公众号大V动态，统一清洗去重存储，并在一个 Dashboard 上混合展示（采集总量、态势总结、报道趋势、情感分析、热点列表 + 筛选）。

> 配套采集插件位于同级目录 [`../social-collector`](../social-collector)（Chrome MV3 扩展，本系统在其上增量对接，未重写）。

---

## 整体数据流

```
                 微博(15–30min随机)        X(30–60min随机)
                 weibo.com PC接口          x.com 注入DOM解析
                        \                      /
                         \  插件 background.js  /   （差异化随机间隔 + 失败退避 + 超时重试）
                          \   pushToBackend    /
                           v                  v
   公众号                  POST /ingest  ◄──────────────  we-mp-rss (Docker)
   mp.weixin              （统一后端 FastAPI）            扫码授权 + 定时抓取(≥30min)
   ───────► CUSTOM_WEBHOOK ─► POST /ingest?source=wechat   新文章 Webhook 推送
                           |
                  adapters 归一化 + dedup_key 去重
                           v
                    ┌─────────────┐
                    │  posts 表    │  (SQLite，统一模型)
                    └─────────────┘
                           |
                GET /api/posts   GET /api/stats
                           v
                  前端 Dashboard (Vue3 + ECharts)
              采集总量 / 态势总结 / 趋势 / 情感 / 列表+筛选
                  （每 60s 增量刷新展示，非高频轮询采集）
```

三个来源的"实时感" = **随机化间隔 + Webhook 推送 + 前端增量刷新**，**不靠提高轮询频率**。

---

## 组成与目录

| 模块 | 路径 | 技术 | 职责 |
|------|------|------|------|
| 采集插件 | [`../social-collector`](../social-collector) | Chrome MV3 | 微博/X 采集，新数据推 `/ingest` |
| 公众号采集 | [`deploy/`](deploy/) | we-mp-rss (Docker) | 公众号→Webhook→`/ingest` |
| 统一后端 | [`backend/`](backend/) | FastAPI + SQLAlchemy | `/ingest` 去重入库、`/api/posts`、`/api/stats` |
| 展示前端 | [`frontend/`](frontend/) | Vue3 + Vite + ECharts | 纯展示 Dashboard |
| 设计文档 | [`docs/`](docs/) | — | 现状/数据模型/公众号部署 |

文档：[现状](docs/CURRENT_STATE.md) · [数据模型](docs/DATA_MODEL.md) · [we-mp-rss 部署](docs/WEMP_RSS_SETUP.md)

---

## 启动步骤（开发）

### 1. 后端
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # 按需改 DB_URL / INGEST_TOKEN / CORS_ORIGINS
uvicorn app.main:app --reload --port 8000
# 自检： python -m tests.test_ingest
```

### 2. 前端
```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173 （/api 自动代理到 8000）
```

### 3. 插件（微博 / X）
1. `chrome://extensions/` → 开发者模式 → 加载 `../social-collector`
2. 浏览器登录 **weibo.com** 与 **x.com**
3. 侧边栏「设置」→ 填后端地址 `http://127.0.0.1:8000`（如设了 token 一并填）→ 保存
4. 「账号」页批量解析微博 UID → 面板「定时采集」

### 4. 公众号（we-mp-rss）
见 [docs/WEMP_RSS_SETUP.md](docs/WEMP_RSS_SETUP.md)：`cd deploy && docker compose up -d` → 扫码授权 → 添加公众号 → Webhook 已指向 `/ingest?source=wechat`。

---

## 防封策略（硬约束）

**核心原则：防封优先级高于实时性。"实时" ≠ 高频轮询。**

| 来源 | 采集间隔 | 实现 | 理由 |
|------|----------|------|------|
| **微博** | **15–30 分钟随机** | 插件 `scrapeAlarmWeibo`，`scheduleCycle` 硬下限 **≥15min** | 绑真实 cookie，频控明确不可激进 |
| **X** | **30–60 分钟随机** | 插件 `scrapeAlarmX`，硬下限 **≥30min** | X 对自动化判定最严，封号风险最高，最保守 |
| **公众号** | **≥30 分钟** | we-mp-rss `SPAN_INTERVAL=1800` | 风控敏感；新文及时性靠 Webhook 推送，非高频拉取 |

强化措施（均在 `social-collector/background.js`）：
- **差异化随机间隔**：微博/X 两个独立闹钟，区间随机化，绝不固定为小值。
- **硬下限兜底**：`scheduleCycle` 内 `FLOOR = 微博15 / X30` 分钟，UI 再怎么填都不可能跌破——**全项目无任何 ≤10min 固定高频轮询绑定真实账号的代码路径**（无 `periodInMinutes` 周期轮询）。
- **失败退避（backoff）**：某轮异常或目标账号 0 结果（疑似限流/登录失效）→ 下次间隔 ×2（上限 ×4），成功后复位。
- **账号间随机延迟**：`delay(2,4)`/`delay(3,6)` 等，翻页 `delay(1.5,3)`。
- **后端推送**：`pushToBackend` 带 15s 超时 + 指数退避重试，失败不阻断本地存储。
- **登录态请求**保留并强化上述随机延迟/间隔/退避。

> 前端每 60s 的刷新是**展示层拉取已入库数据**，不触发任何采集，与封号风险无关。

---

## 验收对照（本轮交付）

- [x] **统一数据模型**：微博/X/公众号三源无损映射进 `posts`，去重键 `source:platform_post_id`（或 `source:sha1(url)`）。
- [x] **/ingest**：伪造三源负载入库正确，重复提交不产生重复记录（`backend/tests/test_ingest.py` 14 项通过）。
- [x] **/api/posts & /api/stats**：按情感/关键词/时间筛选正确；stats 当日总量与库一致。
- [x] **we-mp-rss Webhook**：适配器映射 + 手动可复现验证步骤（docs/WEMP_RSS_SETUP.md §6b）。
- [x] **插件对接**：采集后推 `/ingest`，本地导出与防封逻辑不受影响；微博/X 差异化随机区间且有注释。
- [x] **前端**：mock 兜底不崩；接真实 API 后总量/情感/列表/筛选联动；`npm run build` 通过。
- [x] **防封复核**：无固定 ≤10min 高频轮询绑定真实账号；实时性靠 Webhook + 随机间隔 + 前端增量刷新。
- [ ] **AI 分析层（Step 7）**：本轮按需求**未实现**；后端 `/api/stats` 暂无 `ai_summary`，`posts.sentiment/keywords` 可空，前端对应区块显示"分析中/开发中"占位（不报错）。预留 `ANTHROPIC_API_KEY`/`ANALYZE_MODEL` 配置位，后续可补。

---

## 后续可扩展（非本轮范围）
- Step 7 AI 分析层：对入库内容打情感/关键词标签 + 生成每日态势总结，写回 `sentiment`/`keywords`/`ai_summary`。
- MySQL 生产库（`DB_URL` 切换，`docs/DATA_MODEL.md` §5 已留差异说明）。
- 用户体系 / 多租户 / 可视化编辑（本轮非目标）。
