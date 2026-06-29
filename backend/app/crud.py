"""入库（带去重）与查询/统计。"""
import json
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, func, and_
from sqlalchemy.exc import IntegrityError

from .models import Post


def _now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _loads(s, default):
    try:
        return json.loads(s) if s else default
    except Exception:
        return default


def post_to_dict(p: Post) -> dict:
    return {
        "id": p.id,
        "source": p.source,
        "account_name": p.account_name,
        "author_name": p.author_name,
        "author_url": p.author_url,
        "title": p.title,
        "content": p.content,
        "content_html": p.content_html,
        "publish_time": p.publish_time.isoformat() + "Z" if p.publish_time else None,
        "collect_time": p.collect_time.isoformat() + "Z" if p.collect_time else None,
        "original_url": p.original_url,
        "platform_post_id": p.platform_post_id,
        "media_urls": _loads(p.media_urls, []),
        "stats": _loads(p.stats, {}),
        "sentiment": p.sentiment,
        "keywords": _loads(p.keywords, None),
    }


def ingest(db, unified_list) -> dict:
    """批量入库，dedup_key 去重。返回 {inserted, duplicated, invalid}。"""
    inserted = duplicated = invalid = 0
    seen_in_batch = set()
    for u in unified_list:
        if not u or not u.get("dedup_key") or not u.get("original_url"):
            invalid += 1
            continue
        key = u["dedup_key"]
        if key in seen_in_batch:
            duplicated += 1
            continue
        seen_in_batch.add(key)
        if db.execute(select(Post.id).where(Post.dedup_key == key)).first():
            duplicated += 1
            continue
        now = _now_utc()
        p = Post(
            source=u["source"],
            account_name=u.get("account_name") or "",
            author_name=u.get("author_name"),
            author_url=u.get("author_url"),
            title=u.get("title"),
            content=u.get("content"),
            content_html=u.get("content_html"),
            publish_time=u.get("publish_time"),
            collect_time=now,
            original_url=u["original_url"],
            platform_post_id=u.get("platform_post_id"),
            media_urls=json.dumps(u.get("media_urls") or [], ensure_ascii=False),
            stats=json.dumps(u.get("stats") or {}, ensure_ascii=False),
            raw_json=json.dumps(u.get("raw_json") or {}, ensure_ascii=False),
            sentiment=u.get("sentiment"),
            keywords=json.dumps(u["keywords"], ensure_ascii=False) if u.get("keywords") else None,
            dedup_key=key,
            created_at=now,
        )
        db.add(p)
        try:
            db.commit()
            inserted += 1
        except IntegrityError:
            db.rollback()  # 并发下唯一键冲突 → 当重复
            duplicated += 1
    return {"inserted": inserted, "duplicated": duplicated, "invalid": invalid}


def query_posts(db, source=None, sentiment=None, keyword=None,
                start=None, end=None, page=1, page_size=20):
    conds = []
    if source:
        conds.append(Post.source == source)
    if sentiment:
        conds.append(Post.sentiment == sentiment)
    if keyword:
        like = f"%{keyword}%"
        conds.append((Post.content.like(like)) | (Post.title.like(like)) | (Post.account_name.like(like)))
    if start:
        conds.append(Post.publish_time >= start)
    if end:
        conds.append(Post.publish_time <= end)
    where = and_(*conds) if conds else True

    total = db.execute(select(func.count()).select_from(Post).where(where)).scalar() or 0
    page = max(1, int(page))
    page_size = max(1, min(200, int(page_size)))
    rows = db.execute(
        select(Post).where(where)
        .order_by(Post.publish_time.desc().nullslast(), Post.id.desc())
        .limit(page_size).offset((page - 1) * page_size)
    ).scalars().all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [post_to_dict(p) for p in rows]}


def get_stats(db) -> dict:
    today = _now_utc().date()
    today_start = datetime(today.year, today.month, today.day)
    total = db.execute(select(func.count()).select_from(Post)).scalar() or 0
    today_total = db.execute(
        select(func.count()).select_from(Post).where(Post.collect_time >= today_start)
    ).scalar() or 0

    by_source = {s: c for s, c in db.execute(
        select(Post.source, func.count()).group_by(Post.source)).all()}
    by_sentiment = {(s or "unknown"): c for s, c in db.execute(
        select(Post.sentiment, func.count()).group_by(Post.sentiment)).all()}

    # 近 7 天按天 × 来源 趋势（按 publish_time，缺失则忽略）
    trend = {}
    since = today_start - timedelta(days=6)
    rows = db.execute(
        select(Post.source, func.count(), func.strftime("%Y-%m-%d", Post.publish_time))
        .where(Post.publish_time >= since)
        .group_by(Post.source, func.strftime("%Y-%m-%d", Post.publish_time))
    ).all() if DB_IS_SQLITE() else []
    for src, cnt, day in rows:
        if not day:
            continue
        trend.setdefault(day, {}).setdefault(src, 0)
        trend[day][src] += cnt

    return {
        "total": total,
        "today_total": today_total,
        "by_source": by_source,
        "by_sentiment": by_sentiment,
        "trend": trend,
    }


def DB_IS_SQLITE():
    from .config import DB_URL
    return DB_URL.startswith("sqlite")
