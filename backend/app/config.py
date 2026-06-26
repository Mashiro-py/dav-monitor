"""集中配置：全部来自环境变量 / .env，禁止硬编码密钥。"""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass  # 没装 python-dotenv 也能跑，直接读环境变量

DB_URL = os.getenv("DB_URL", "sqlite:///./data.db")

# /ingest 共享密钥；为空表示不校验（开发）。生产建议设置，插件/Webhook 带 X-Ingest-Token。
INGEST_TOKEN = os.getenv("INGEST_TOKEN", "").strip()

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# AI 分析（Step 7，可选）
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANALYZE_MODEL = os.getenv("ANALYZE_MODEL", "claude-haiku-4-5-20251001").strip()
