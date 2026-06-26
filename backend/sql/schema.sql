-- ================================================================
-- schema.sql — 统一 posts 表（SQLite 方言）
-- 对应 docs/DATA_MODEL.md。后端用 SQLAlchemy create_all 自动建表，
-- 此脚本作为权威 DDL 备查 / 手动初始化用：  sqlite3 data.db < schema.sql
-- ================================================================

CREATE TABLE IF NOT EXISTS posts (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  source            TEXT    NOT NULL,                 -- weibo / x / wechat
  account_name      TEXT    NOT NULL,
  author_name       TEXT,
  author_url        TEXT,
  title             TEXT,
  content           TEXT,
  publish_time      DATETIME,                          -- UTC
  collect_time      DATETIME NOT NULL,                 -- UTC，服务端写入
  original_url      TEXT    NOT NULL,
  platform_post_id  TEXT,
  media_urls        TEXT    DEFAULT '[]',              -- JSON array
  stats             TEXT    DEFAULT '{}',              -- JSON object
  raw_json          TEXT,                              -- JSON，原始负载留档
  sentiment         TEXT,                              -- positive/negative/neutral/NULL
  keywords          TEXT,                              -- JSON array / NULL
  dedup_key         TEXT    NOT NULL UNIQUE,           -- 去重唯一键
  created_at        DATETIME NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_posts_dedup     ON posts (dedup_key);
CREATE INDEX        IF NOT EXISTS idx_posts_source    ON posts (source);
CREATE INDEX        IF NOT EXISTS idx_posts_publish   ON posts (publish_time);
CREATE INDEX        IF NOT EXISTS idx_posts_sentiment ON posts (sentiment);
CREATE INDEX        IF NOT EXISTS idx_posts_account   ON posts (account_name);
