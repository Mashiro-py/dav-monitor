# backend — 统一数据后端（FastAPI）

接收三类来源（微博 / X / 公众号）数据，统一清洗去重存储，对外提供查询/统计 API。

## 运行

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env          # 按需修改 DB_URL / INGEST_TOKEN / CORS_ORIGINS
uvicorn app.main:app --reload --port 8000
```

启动后：
- 文档（Swagger）：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/health

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ingest` | 接收任意来源数据并去重入库。body 可为单对象 / 数组 / `{items:[...]}`。可选 `?source=weibo\|x\|wechat` 指定来源；插件 item 自带 `platform` 可不传。设置了 `INGEST_TOKEN` 时需带头 `X-Ingest-Token`。 |
| GET | `/api/posts` | 查询。参数：`source` `sentiment` `keyword` `start` `end`（北京时间）`page` `page_size`。 |
| GET | `/api/stats` | 聚合：`total` `today_total` `by_source` `by_sentiment` `trend`(近7天)。 |

### 示例

```bash
# 公众号 webhook 入库（we-mp-rss 指向这里，见 docs/WEMP_RSS_SETUP.md）
curl -X POST "http://127.0.0.1:8000/ingest?source=wechat" \
  -H "Content-Type: application/json" \
  -d '{"title":"测试","url":"https://mp.weixin.qq.com/s/abc","content":"<p>正文</p>","mp_name":"量子位","publish_time":"2026-06-23 10:00:00"}'

# 插件微博/X 入库（插件 Step 5 自动调用）
curl -X POST http://127.0.0.1:8000/ingest -H "Content-Type: application/json" \
  -d '[{"platform":"weibo","account":"机器之心","postId":"1","url":"https://weibo.com/x/1","content":"...","publishDate":"2026-06-23 09:00:00"}]'

# 查询
curl "http://127.0.0.1:8000/api/posts?source=weibo&keyword=模型&page=1"
curl "http://127.0.0.1:8000/api/stats"
```

## 自检

```bash
cd backend && python -m tests.test_ingest      # 伪造三类来源，验证入库/去重/筛选/统计
```

## 结构

```
app/config.py    环境变量配置（DB_URL/INGEST_TOKEN/CORS）
app/db.py        引擎/会话/建表
app/models.py    posts ORM 模型（= sql/schema.sql）
app/adapters.py  各来源 → 统一结构（时间转 UTC、HTML 清洗、dedup_key）
app/crud.py      去重入库 / 查询 / 统计
app/main.py      FastAPI 路由
sql/schema.sql   权威 DDL（备查）
tests/           自检
```
