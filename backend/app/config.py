"""集中配置：全部来自环境变量 / .env，禁止硬编码密钥。"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # 没装 python-dotenv 也能跑，直接读环境变量

DB_URL = os.getenv("DB_URL", "sqlite:///./data.db")

# /ingest 共享密钥；为空表示不校验（开发）。生产建议设置，插件/Webhook 带 X-Ingest-Token。
# /ingest（插件微博/X，走公网）的校验 token；为空=不校验
INGEST_TOKEN = os.getenv("INGEST_TOKEN", "").strip()
# /ingest/wemp（公众号 webhook，同机内网）的独立 token；为空=不校验。
# 与 INGEST_TOKEN 解耦：给插件设了 token 也不会影响免 token 的公众号链路。
WEMP_TOKEN = os.getenv("WEMP_TOKEN", "").strip()

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# AI 分析（Step 7，可选）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANALYZE_MODEL = os.getenv("ANALYZE_MODEL", "claude-haiku-4-5-20251001").strip()

# ===== we-mp-rss 主动拉取同步 =====
# 要遍历的 we-mp-rss 实例基址（逗号分隔）。容器内经宿主 IP 可达。
WEMP_INSTANCES = [u.strip().rstrip("/") for u in os.getenv(
    "WEMP_INSTANCES",
    "http://172.22.7.189:8001,http://172.22.7.189:8002,http://172.22.7.189:8003",
).split(",") if u.strip()]
WEMP_RSS_LIMIT = int(os.getenv("WEMP_RSS_LIMIT", "100"))          # 每个 feed 取多少篇
WEMP_SYNC_ENABLED = os.getenv("WEMP_SYNC_ENABLED", "true").lower() in ("1", "true", "yes", "on")
WEMP_SYNC_INTERVAL_MIN = int(os.getenv("WEMP_SYNC_INTERVAL_MIN", "20"))  # 定时间隔(分钟)
