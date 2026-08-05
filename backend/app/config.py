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

# ===== AI 热点态势分析（DeepSeek） =====
# ⚠️ API key 的唯一存放位置：服务器上 dav-monitor/deploy/.env 文件里加一行
#       DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
#    （backend-compose.yml 会把它注入后端容器；严禁写进前端代码/前端容器/任何响应体）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
# DeepSeek OpenAI 兼容接口基址与模型（官方：POST {BASE}/chat/completions，Bearer 鉴权）
DEEPSEEK_BASE = os.getenv("DEEPSEEK_BASE", "https://api.deepseek.com").strip().rstrip("/")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
ANALYSIS_HOURS = int(os.getenv("ANALYSIS_HOURS", "24"))            # 每次分析覆盖最近多少小时
ANALYSIS_AUTO_HOUR = int(os.getenv("ANALYSIS_AUTO_HOUR", "8"))     # 每天自动分析的小时（北京时间，分钟取 20~40 随机）
ANALYSIS_AUTO_ENABLED = os.getenv("ANALYSIS_AUTO_ENABLED", "true").lower() in ("1", "true", "yes", "on")
ANALYSIS_MANUAL_LIMIT = int(os.getenv("ANALYSIS_MANUAL_LIMIT", "10"))  # 手动分析每自然日上限（自动的1次不占用）

# ===== we-mp-rss 主动拉取同步 =====
# 要遍历的 we-mp-rss 实例基址（逗号分隔）。容器内经宿主 IP 可达。
WEMP_INSTANCES = [u.strip().rstrip("/") for u in os.getenv(
    "WEMP_INSTANCES",
    "http://172.22.7.189:8001,http://172.22.7.189:8002,http://172.22.7.189:8003",
).split(",") if u.strip()]
WEMP_RSS_LIMIT = int(os.getenv("WEMP_RSS_LIMIT", "100"))          # 每个 feed 取多少篇
WEMP_SYNC_ENABLED = os.getenv("WEMP_SYNC_ENABLED", "true").lower() in ("1", "true", "yes", "on")
WEMP_SYNC_INTERVAL_MIN = int(os.getenv("WEMP_SYNC_INTERVAL_MIN", "20"))  # 定时间隔(分钟)
