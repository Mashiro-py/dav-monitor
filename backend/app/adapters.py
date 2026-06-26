"""把各来源的原始负载归一化为统一 dict（对应 posts 表字段）。

- 插件微博/X item：含 platform / postId / publishDate 等
- we-mp-rss 公众号 webhook：含 title / url / content 等（字段名做容错）

时间统一转 UTC（无时区的中文时间按北京时间 +08:00 处理）。
"""
import hashlib
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

CN_TZ = timezone(timedelta(hours=8))

# 插件 platform → 统一 source
SRC_MAP = {"weibo": "weibo", "x": "x", "weixin": "wechat", "wechat": "wechat"}


def strip_html(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p\s*>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = (s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
         .replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'"))
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def parse_dt(s):
    """各种时间字符串 → UTC naive datetime（存库用）。无法解析返回 None。"""
    if not s:
        return None
    if isinstance(s, (int, float)):  # unix 秒/毫秒
        ts = float(s)
        if ts > 1e12:
            ts /= 1000.0
        return datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None)
    s = str(s).strip().replace("T", " ").replace("Z", "")
    s = re.sub(r"([+-]\d{2}:?\d{2})$", "", s).strip()  # 去掉时区后缀，统一按北京时间
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s[:19], fmt).replace(tzinfo=CN_TZ)
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue
    # RFC822 (pubDate): Tue, 16 Jun 2026 10:00:00 +0800
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(str(s))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=CN_TZ)
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    except Exception:
        return None


def make_dedup_key(source: str, pid: str, url: str) -> str:
    if pid:
        return f"{source}:{pid}"
    return f"{source}:" + hashlib.sha1((url or "").encode("utf-8")).hexdigest()


def normalize(obj: dict, source_hint: str = None):
    """统一入口。返回 unified dict 或 None（无法识别）。"""
    if not isinstance(obj, dict):
        return None
    src = (source_hint or obj.get("source") or obj.get("platform") or "").lower()
    src = SRC_MAP.get(src, src)
    if src in ("weibo", "x"):
        return _from_plugin(obj, src)
    if src == "wechat":
        return _from_wechat(obj)
    # 无来源标记：若像公众号文章（有 title+url）按 wechat，否则放弃
    if obj.get("title") and (obj.get("url") or obj.get("link")):
        return _from_wechat(obj)
    return None


def _from_plugin(obj: dict, src: str) -> dict:
    pid = str(obj.get("postId") or obj.get("platform_post_id") or "")
    url = obj.get("url") or obj.get("original_url") or ""
    media = obj.get("pics") or obj.get("media_urls") or []
    author = obj.get("authorName") or obj.get("author_name") or ""
    if src == "x" and author:
        author_url = f"https://x.com/{author}"
    else:
        author_url = obj.get("author_url") or ""
    stats = {
        "likes": obj.get("likesCount", 0),
        "comments": obj.get("commentsCount", 0),
        "reposts": obj.get("repostsCount", 0),
    }
    return {
        "source": src,
        "account_name": obj.get("account") or obj.get("account_name") or "",
        "author_name": author,
        "author_url": author_url,
        "title": obj.get("title") or "",
        "content": obj.get("content") or "",
        "publish_time": parse_dt(obj.get("publishDate") or obj.get("publish_time")),
        "original_url": url,
        "platform_post_id": pid or None,
        "media_urls": media if isinstance(media, list) else [],
        "stats": stats,
        "raw_json": obj,
        "dedup_key": make_dedup_key(src, pid, url),
    }


# 微信文章 URL 规范化：只保留稳定身份参数（去掉 chksm/scene/key 等跟踪参数），
# 让同一篇文章在 3 个实例/多次推送中产生一致的去重键。
_WX_KEEP_PARAMS = {"__biz", "mid", "idx", "sn"}


def _wx_sn(url: str) -> str:
    """从微信文章链接里抽取文章唯一标识 sn（/s/{sn} 或 ?sn=...）。"""
    if not url:
        return ""
    m = re.search(r"/s/([\w\-]+)", url) or re.search(r"[?&]sn=([\w\-]+)", url)
    return m.group(1) if m else ""


def canonical_wechat_url(url: str) -> str:
    if not url:
        return ""
    try:
        sp = urlsplit(url.strip())
        q = sorted((k, v) for k, v in parse_qsl(sp.query) if k in _WX_KEEP_PARAMS)
        return urlunsplit((sp.scheme.lower() or "https", sp.netloc.lower(), sp.path, urlencode(q), ""))
    except Exception:
        return url.strip()


def from_wemp(p: dict) -> dict:
    """we-mp-rss Webhook 专用适配器（对应 /ingest/wemp 端点）。

    期望的推送 JSON（你在 we-mp-rss 消息模板里对齐这些字段名即可）：
      {
        "title":        "文章标题",
        "url":          "https://mp.weixin.qq.com/s/xxxx",   原文链接
        "account_name": "公众号名称",
        "publish_time": 1718512200,   或 "2026-06-16 10:00:00"  （Unix秒/毫秒/字符串均可）
        "summary":      "摘要或描述"
      }
    去重：按文章原文链接（规范化后取 sn，等价于 URL 去重），source 固定 wechat。
    兼容若干别名字段，少填也不会报错。
    """
    if not isinstance(p, dict):
        return None
    title = (p.get("title") or "").strip()
    url = (p.get("url") or p.get("link") or p.get("original_url") or "").strip()
    account = (p.get("account_name") or p.get("account") or p.get("mp_name")
               or p.get("nickname") or "").strip()
    raw_summary = (p.get("summary") or p.get("description")
                   or p.get("content") or p.get("digest") or "")
    sn = _wx_sn(url)
    canon = canonical_wechat_url(url)
    media = [p[k] for k in ("cover", "pic_url", "thumb", "thumb_url", "image") if p.get(k)]
    return {
        "source": "wechat",
        "account_name": account,
        "author_name": (p.get("author") or account or "").strip(),
        "author_url": p.get("mp_url") or "",
        "title": title,
        "content": strip_html(raw_summary),
        "publish_time": parse_dt(p.get("publish_time") or p.get("pubDate")
                                 or p.get("time") or p.get("created_at")),
        "original_url": url,
        "platform_post_id": sn or None,
        "media_urls": media,
        "stats": {},
        "raw_json": p,
        # sn 存在 → "wechat:{sn}"（与 _from_wechat 一致，跨端点也不会重复）；
        # 无 sn → 退化为规范化 URL 的哈希，仍是按 URL 去重。
        "dedup_key": make_dedup_key("wechat", sn, canon),
    }


def _from_wechat(obj: dict) -> dict:
    title = obj.get("title") or ""
    url = obj.get("url") or obj.get("link") or obj.get("original_url") or ""
    content = strip_html(obj.get("content") or obj.get("content_html")
                         or obj.get("description") or obj.get("summary") or "")
    feed = obj.get("feed") if isinstance(obj.get("feed"), dict) else {}
    account = (obj.get("mp_name") or obj.get("account") or obj.get("account_name")
               or obj.get("nickname") or feed.get("title") or "")
    pid = str(obj.get("id") or obj.get("article_id") or "")
    if not pid and url:
        m = re.search(r"/s/([\w-]+)", url) or re.search(r"[?&]sn=([^&]+)", url)
        if m:
            pid = m.group(1)
    media = []
    for k in ("pic_url", "cover", "thumb", "image", "thumb_url"):
        v = obj.get(k)
        if v:
            media.append(v)
    return {
        "source": "wechat",
        "account_name": account,
        "author_name": obj.get("author") or account,
        "author_url": obj.get("mp_url") or feed.get("url") or "",
        "title": title,
        "content": content,
        "publish_time": parse_dt(obj.get("publish_time") or obj.get("pubDate")
                                 or obj.get("published") or obj.get("created_at")),
        "original_url": url,
        "platform_post_id": pid or None,
        "media_urls": media,
        "stats": {},
        "raw_json": obj,
        "dedup_key": make_dedup_key("wechat", pid, url),
    }
