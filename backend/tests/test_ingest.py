"""Step 3 自检：伪造 微博/X/公众号 三种负载，验证入库、去重、查询、统计。
运行：  cd backend && python -m tests.test_ingest      （或 pytest tests/）
"""
import os
import sys

# 用独立测试库，先清空
os.environ["DB_URL"] = "sqlite:///./test_data.db"
if os.path.exists("test_data.db"):
    os.remove("test_data.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)

# --- 伪造样本 ---
WEIBO = {
    "platform": "weibo", "account": "机器之心", "authorName": "机器之心",
    "postId": "WB1001", "url": "https://weibo.com/u/123/WB1001",
    "content": "今天发布了新模型，非常强大。", "publishDate": "2026-06-23 09:00:00",
    "likesCount": 100, "commentsCount": 20, "repostsCount": 5, "pics": ["http://img/1.jpg"],
}
X = {
    "platform": "x", "account": "TheRundownAI", "authorName": "TheRundownAI",
    "postId": "1888000111", "url": "https://x.com/TheRundownAI/status/1888000111",
    "content": "Breaking: new AI model released.", "publishDate": "2026-06-23 08:30:00",
    "likesCount": 500, "commentsCount": 40, "repostsCount": 90,
}
WECHAT = {  # 模拟 we-mp-rss webhook
    "title": "深度解析：大模型最新进展", "url": "https://mp.weixin.qq.com/s/AbCdEf123",
    "content": "<p>正文段落一。</p><p>正文段落二。</p>", "mp_name": "量子位",
    "author": "量子位", "publish_time": "2026-06-23 07:15:00",
}


def expect(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        raise AssertionError(msg)


def run():
    print("[1] 三类来源分别入库")
    r1 = client.post("/ingest", json=WEIBO).json()
    r2 = client.post("/ingest", json=X).json()
    r3 = client.post("/ingest?source=wechat", json=WECHAT).json()
    expect(r1["inserted"] == 1, f"微博入库 1 条 (got {r1})")
    expect(r2["inserted"] == 1, f"X 入库 1 条 (got {r2})")
    expect(r3["inserted"] == 1, f"公众号入库 1 条 (got {r3})")

    print("[2] 重复提交不产生重复记录")
    dup = client.post("/ingest", json=[WEIBO, X, WECHAT]).json()
    expect(dup["inserted"] == 0 and dup["duplicated"] == 3, f"重复全部被去重 (got {dup})")

    print("[3] /api/posts 筛选")
    allp = client.get("/api/posts").json()
    expect(allp["total"] == 3, f"总数 3 (got {allp['total']})")
    wb = client.get("/api/posts?source=weibo").json()
    expect(wb["total"] == 1 and wb["items"][0]["source"] == "weibo", "按 source=weibo 过滤=1")
    kw = client.get("/api/posts?keyword=模型").json()
    expect(kw["total"] == 2, f"关键词'模型'命中 2 (got {kw['total']})")
    expect(wb["items"][0]["media_urls"] == ["http://img/1.jpg"], "media_urls 正确反序列化")
    wc = client.get("/api/posts?source=wechat").json()
    expect("正文段落一" in (wc["items"][0]["content"] or ""), "公众号 HTML 已转纯文本")

    print("[4] 时间筛选")
    late = client.get("/api/posts?start=2026-06-23 08:45:00").json()  # 北京时间
    expect(late["total"] == 1, f"start 之后只剩微博1条 (got {late['total']})")

    print("[5] /api/stats")
    s = client.get("/api/stats").json()
    expect(s["total"] == 3, f"stats.total=3 (got {s['total']})")
    expect(s["today_total"] == 3, f"今日采集=3 (got {s['today_total']})")
    expect(s["by_source"].get("weibo") == 1 and s["by_source"].get("x") == 1
           and s["by_source"].get("wechat") == 1, f"来源分布正确 (got {s['by_source']})")

    print("\n🎉 全部通过")


if __name__ == "__main__":
    try:
        run()
    except AssertionError:
        sys.exit(1)
