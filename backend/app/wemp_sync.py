"""主动拉取 we-mp-rss 文章并入库（方案A：读各实例的 RSS）。

流程：遍历 WEMP_INSTANCES → GET /rss 发现 feed_id（MP_WXS_*）→
对每个 feed GET /rss/{feed_id}/api?limit=N 取文章(RSS XML) → feedparser 解析 →
映射成 from_wemp 认得的字段 → crud.ingest 去重入库（source=wechat，按 URL 去重）。

公众号名取 RSS 的 channel/title（item 里没有）。发布时间是 RFC822（pubDate），
由 adapters.parse_dt 解析。整条链路不改 we-mp-rss。
"""
import asyncio
import logging
import re

import httpx
import feedparser

from .config import (WEMP_INSTANCES, WEMP_RSS_LIMIT,
                     WEMP_SYNC_ENABLED, WEMP_SYNC_INTERVAL_MIN)
from .db import SessionLocal
from . import adapters, crud

log = logging.getLogger("wemp_sync")

FEED_ID_RE = re.compile(r"MP_WXS_[A-Za-z0-9_]+")
HTTP_TIMEOUT = 20.0


def parse_feed_ids(rss_text: str):
    """从 /rss 列表 XML 里提取所有 feed_id（MP_WXS_*），保序去重。"""
    seen, out = set(), []
    for fid in FEED_ID_RE.findall(rss_text or ""):
        if fid not in seen:
            seen.add(fid)
            out.append(fid)
    return out


def parse_articles(feed_xml: str):
    """解析单个 feed 的文章 RSS XML → (公众号名, [article_dict])。
    article_dict 的字段名与 adapters.from_wemp 对齐，零额外映射。"""
    d = feedparser.parse(feed_xml or "")
    account = (d.feed.get("title") or "").strip()
    arts = []
    for e in d.entries:
        link = (e.get("link") or e.get("id") or "").strip()
        pic = ""
        if e.get("enclosures"):
            enc = e.enclosures[0]
            pic = enc.get("href") or enc.get("url") or ""
        arts.append({
            "title": (e.get("title") or "").strip(),
            "url": link,                                   # → original_url（取 sn 去重）
            "mp_name": account,                            # → account_name
            "publish_time": e.get("published") or e.get("updated") or "",  # RFC822 → parse_dt
            "description": e.get("summary") or e.get("description") or "",  # → content
            "pic_url": pic,                                # → media_urls
        })
    return account, arts


async def _get(client: httpx.AsyncClient, url: str) -> str:
    r = await client.get(url, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    return r.text


async def _sync_instance(client, base, summary):
    inst = {"base": base, "feeds": 0, "articles": 0}
    unified = []
    try:
        rss_text = await _get(client, f"{base}/rss")
    except Exception as e:
        summary["errors"].append(f"{base} /rss: {e}")
        summary["instances"].append(inst)
        return unified
    feed_ids = parse_feed_ids(rss_text)
    inst["feeds"] = len(feed_ids)
    summary["feeds"] += len(feed_ids)
    for fid in feed_ids:
        try:
            xml = await _get(client, f"{base}/rss/{fid}/api?limit={WEMP_RSS_LIMIT}&offset=0")
            _account, arts = parse_articles(xml)
            inst["articles"] += len(arts)
            summary["articles"] += len(arts)
            for a in arts:
                u = adapters.from_wemp(a)
                if u:
                    unified.append(u)
        except Exception as e:
            summary["errors"].append(f"{base} {fid}: {e}")
    summary["instances"].append(inst)
    return unified


async def run_sync_async() -> dict:
    """执行一次全量拉取+入库，返回统计。"""
    summary = {"instances": [], "feeds": 0, "articles": 0,
               "inserted": 0, "duplicated": 0, "invalid": 0, "errors": []}
    unified_all = []
    async with httpx.AsyncClient(headers={"User-Agent": "dav-monitor-sync"},
                                 follow_redirects=True) as client:
        for base in WEMP_INSTANCES:
            unified_all.extend(await _sync_instance(client, base, summary))

    if unified_all:
        db = SessionLocal()
        try:
            r = crud.ingest(db, unified_all)
            summary["inserted"] = r["inserted"]
            summary["duplicated"] = r["duplicated"]
            summary["invalid"] = r["invalid"]
        finally:
            db.close()
    log.info("wemp sync: feeds=%s articles=%s inserted=%s duplicated=%s errors=%s",
             summary["feeds"], summary["articles"], summary["inserted"],
             summary["duplicated"], len(summary["errors"]))
    return summary


# ---------- 定时任务（asyncio 后台循环） ----------
_task = None


async def _loop():
    # 启动即跑一次（拉存量），之后按间隔增量
    while True:
        try:
            await run_sync_async()
        except Exception as e:
            log.warning("wemp sync loop error: %s", e)
        await asyncio.sleep(max(1, WEMP_SYNC_INTERVAL_MIN) * 60)


def start_scheduler():
    global _task
    if not WEMP_SYNC_ENABLED:
        log.info("wemp sync disabled")
        return
    if _task is None:
        _task = asyncio.create_task(_loop())
        log.info("wemp sync scheduler started: every %s min, instances=%s",
                 WEMP_SYNC_INTERVAL_MIN, WEMP_INSTANCES)
