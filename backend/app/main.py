"""统一数据后端：
  POST /ingest        接收任意来源数据（插件微博/X、we-mp-rss 公众号 webhook），去重入库
  GET  /api/posts     查询（source/sentiment/keyword/time + 分页）
  GET  /api/stats     聚合统计（今日总量、来源分布、情感分布、近7天趋势）
  GET  /health        健康检查
"""
from fastapi import FastAPI, Request, Depends, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from .config import CORS_ORIGINS, INGEST_TOKEN, WEMP_TOKEN, WX_FULL_MIN
from .db import get_db, init_db
from . import adapters, crud, wemp_sync

app = FastAPI(title="大V动态统一后端", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# 建表：导入即执行（uvicorn / 测试均生效），幂等
init_db()


@app.on_event("startup")
async def _startup():
    # 启动 we-mp-rss 定时拉取（TestClient 不触发 startup，不影响测试）
    wemp_sync.start_scheduler()


def _check_token(x_ingest_token: str = Header(default="")):
    """/ingest（插件，公网）校验。INGEST_TOKEN 为空则放行。"""
    if INGEST_TOKEN and x_ingest_token != INGEST_TOKEN:
        raise HTTPException(status_code=401, detail="invalid ingest token")


def _check_wemp_token(x_ingest_token: str = Header(default="")):
    """/ingest/wemp（公众号 webhook，内网）独立校验。
    WEMP_TOKEN 为空则放行——即使设了 INGEST_TOKEN，公众号链路也不受影响。"""
    if WEMP_TOKEN and x_ingest_token != WEMP_TOKEN:
        raise HTTPException(status_code=401, detail="invalid wemp token")


def _extract_list(body):
    """把请求体规整成 list[dict]：支持单对象、数组、{items|data|articles:[...]}。"""
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        for k in ("items", "data", "articles", "list"):
            if isinstance(body.get(k), list):
                return body[k]
        return [body]
    return []


@app.post("/ingest")
async def ingest(request: Request, source: str = Query(default=None),
                 db: Session = Depends(get_db), _=Depends(_check_token)):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    raw_items = _extract_list(body)
    unified = []
    for it in raw_items:
        u = adapters.normalize(it, source_hint=source)
        if u:
            unified.append(u)
    result = crud.ingest(db, unified)
    result["received"] = len(raw_items)
    return {"ok": 1, **result}


@app.post("/ingest/wemp")
async def ingest_wemp(request: Request, db: Session = Depends(get_db), _=Depends(_check_wemp_token)):
    """we-mp-rss 公众号 Webhook 专用入口。

    与 /ingest 分开，专门适配 we-mp-rss。兼容三种形态（见 adapters.normalize_wemp）：
    自定义扁平模板 / 消息任务默认嵌套模板(feed+articles) / env CUSTOM_WEBHOOK 的 {title,content}。
    source 固定 wechat；优先按文章 URL 去重；3 个实例推同一文章只入库一次。
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    unified = adapters.normalize_wemp(body)
    result = crud.ingest(db, unified)
    result["received"] = len(unified)
    return {"ok": 1, **result}


@app.post("/sync/wemp")
async def sync_wemp(_=Depends(_check_token)):
    """手动触发一次 we-mp-rss 全量拉取+入库（存量+增量）。
    用 INGEST_TOKEN 保护（设了就要带 X-Ingest-Token）。返回拉取统计。"""
    return {"ok": 1, **(await wemp_sync.run_sync_async())}


@app.get("/api/wechat/pending")
def api_wechat_pending(limit: int = 50, min_len: int = None,
                       db: Session = Depends(get_db), _=Depends(_check_token)):
    """列出缺全文的公众号文章，交插件打开 mp.weixin 读 #js_content 补正文。
    min_len 可覆盖判定阈值（传很大的值=把已采过的也重新列出，用于一次性重抓覆盖）。
    用 INGEST_TOKEN 保护（与 /ingest 一致）。"""
    ml = WX_FULL_MIN if min_len is None else max(1, int(min_len))
    return {"ok": 1, "items": crud.wechat_pending(db, limit=limit, min_len=ml)}


@app.post("/api/wechat/content")
async def api_wechat_content(request: Request, db: Session = Depends(get_db), _=Depends(_check_token)):
    """接收插件回传的公众号全文，覆盖 content_html（权威全文）。
    body: {id?, url?, content_html, content?, pics?}"""
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON body")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="expect object")
    return crud.set_wechat_content(
        db,
        post_id=body.get("id"),
        url=body.get("url") or body.get("original_url"),
        content_html=body.get("content_html") or body.get("contentHtml") or "",
        content=body.get("content"),
        pics=body.get("pics") or body.get("media_urls"),
    )


@app.get("/api/posts")
def api_posts(source: str = None, sentiment: str = None, keyword: str = None,
              start: str = None, end: str = None, page: int = 1, page_size: int = 20,
              db: Session = Depends(get_db)):
    start_dt = adapters.parse_dt(start) if start else None
    end_dt = adapters.parse_dt(end) if end else None
    return crud.query_posts(db, source=source, sentiment=sentiment, keyword=keyword,
                            start=start_dt, end=end_dt, page=page, page_size=page_size)


@app.get("/api/stats")
def api_stats(db: Session = Depends(get_db)):
    return crud.get_stats(db)


@app.get("/health")
def health():
    return {"ok": 1}
