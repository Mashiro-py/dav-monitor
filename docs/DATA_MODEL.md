# DATA_MODEL — 统一数据模型（Step 2 产出）

> 目标：一张 `posts` 表同时无损容纳 **微博 / X / 公众号** 三类内容，去重键明确，便于 `/ingest` 入库与 `/api/*` 查询。
> 建表脚本：[`../backend/sql/schema.sql`](../backend/sql/schema.sql)（SQLite 方言，MySQL 差异见文末）。
> ORM 模型（Step 3）：`backend/app/models.py` 与本表一一对应。

## 1. `posts` 表字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | INTEGER PK AUTOINCREMENT | ✓ | 内部自增主键 |
| `source` | TEXT | ✓ | 来源：`weibo` / `x` / `wechat`（**统一三值**，插件的 `weixin` 映射为 `wechat`） |
| `account_name` | TEXT | ✓ | 目标大V名（插件 `account` / 公众号名） |
| `author_name` | TEXT |  | 实际作者昵称 |
| `author_url` | TEXT |  | 作者主页链接 |
| `title` | TEXT |  | 标题（微博/X 为空，公众号有） |
| `content` | TEXT |  | 正文纯文本 |
| `publish_time` | DATETIME |  | 发布时间（统一存 **UTC**，见 §4） |
| `collect_time` | DATETIME | ✓ | 入库时间（服务端写入，UTC） |
| `original_url` | TEXT | ✓ | 原文链接（去重备用键） |
| `platform_post_id` | TEXT |  | 平台内唯一 id（微博 mblog id / 推文 id / 公众号 sn） |
| `media_urls` | TEXT(JSON) |  | 图片/视频链接数组，JSON 字符串，默认 `[]` |
| `stats` | TEXT(JSON) |  | 互动数 `{"likes":n,"comments":n,"reposts":n}`，默认 `{}` |
| `raw_json` | TEXT(JSON) |  | 原始负载留档（回溯/重解析用） |
| `sentiment` | TEXT |  | 情感：`positive`/`negative`/`neutral`/`NULL`（未分析） |
| `keywords` | TEXT(JSON) |  | 关键词数组 JSON，默认 `NULL` |
| `dedup_key` | TEXT UNIQUE | ✓ | **去重唯一键**，见 §2 |
| `created_at` | DATETIME | ✓ | 记录创建时间（服务端，UTC） |

索引：`dedup_key`(UNIQUE)、`source`、`publish_time`、`sentiment`、`account_name`。

## 2. 去重键 `dedup_key`

规则（服务端在 `/ingest` 计算，调用方无需关心）：
```
dedup_key = source + ':' + (platform_post_id || sha1(original_url))
```
- 有平台内 id → 用 `source:platform_post_id`（最稳，等价插件现有 `platform:postId`）。
- 无 id（部分公众号 webhook 只给 url）→ 用 `source:sha1(original_url)`。
- 入库用 `INSERT ... ON CONFLICT(dedup_key) DO NOTHING`（或 ORM 先查后插），**重复提交不产生重复记录**。

## 3. 三类来源 → 统一表映射（无损性验证）

### 3.1 微博（插件 item，`platform=weibo`）
| 统一字段 | 插件字段 |
|---|---|
| source | `'weibo'`（由 `weibo` 映射） |
| account_name | `account` |
| author_name | `authorName` |
| author_url | 由 uid 拼 `https://weibo.com/u/{uid}`（适配器补） |
| title | `''` |
| content | `content` |
| publish_time | `publishDate`（北京时间→转 UTC） |
| original_url | `url` |
| platform_post_id | `postId` |
| media_urls | `pics` |
| stats | `{likes:likesCount, comments:commentsCount, reposts:repostsCount}` |
| raw_json | 整个插件 item |

### 3.2 X（插件 item，`platform=x`）
| 统一字段 | 插件字段 |
|---|---|
| source | `'x'` |
| account_name | `account` |
| author_name | `authorName` |
| author_url | `https://x.com/{authorName}`（适配器补） |
| content | `content`（已含末尾外链） |
| publish_time | `publishDate`（北京时间→UTC） |
| original_url | `url` |
| platform_post_id | `postId` |
| media_urls | `pics` |
| stats | 同微博 |

### 3.3 公众号（we-mp-rss Webhook，`source=wechat`）
we-mp-rss 推送的文章负载（字段名以其实际为准，适配器做容错映射，详见 Step 4）：
| 统一字段 | webhook 字段（候选） |
|---|---|
| source | `'wechat'` |
| account_name | `mp_name` / `account` / `feed.title` |
| author_name | `author` / `mp_name` |
| title | `title` |
| content | `content`/`description`（HTML→纯文本，由后端清洗） |
| publish_time | `publish_time`/`pubDate`（→UTC） |
| original_url | `url`/`link` |
| platform_post_id | `id`/从 url 抽 `sn` |
| media_urls | `pic_url`/`cover`/正文内图（可空） |
| raw_json | 整个 webhook 负载 |

> 三类来源字段全部能落入上表，未识别的原始信息保留在 `raw_json`，满足"无损映射"。

## 4. 约定

- **时间统一 UTC 存储**：入库时把北京时间(`publish_time`无时区视为+08:00)转 UTC；API 返回 ISO8601（带 `Z`），前端按需本地化。
- **JSON 字段存字符串**：`media_urls`/`stats`/`keywords`/`raw_json` 以 TEXT 存 JSON，ORM 层做 `json.loads/dumps`。
- **sentiment/keywords 可空**：未跑 AI 分析时为空，前端对应区块显示占位（Step 7）。

## 5. MySQL 差异（预留）
- `INTEGER PK AUTOINCREMENT` → `BIGINT AUTO_INCREMENT`。
- `TEXT(JSON)` 可用原生 `JSON` 类型；`DATETIME` 一致。
- `ON CONFLICT(dedup_key) DO NOTHING` → `INSERT IGNORE` 或 `ON DUPLICATE KEY UPDATE`。
- 由 `backend` 的 `DB_URL` 环境变量切换，建表脚本提供两套或由 SQLAlchemy `create_all` 自动适配。
