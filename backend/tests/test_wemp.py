"""验证 /ingest/wemp：公众号 webhook 适配、URL 去重、Unix 时间戳、三源混合统计，
且不破坏现有 /ingest。
运行：cd backend && python -m tests.test_wemp
"""
import os

os.environ["DB_URL"] = "sqlite:///./test_wemp.db"
if os.path.exists("test_wemp.db"):
    os.remove("test_wemp.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)


def expect(cond, msg):
    print(("  ✅ " if cond else "  ❌ ") + msg)
    if not cond:
        raise AssertionError(msg)


# 我定义的 we-mp-rss 推送格式
WEMP = {
    "title": "深度报道：国产大模型的算力之争",
    "url": "https://mp.weixin.qq.com/s/AbCd1234XyZ",
    "account_name": "量子位",
    "publish_time": 1718512200,                 # Unix 秒
    "summary": "<p>正文摘要第一段。</p><p>第二段。</p>",
}
# 同一篇文章，但带跟踪参数 + 用 /s?sn= 形式（模拟另一个实例推送）→ 应判为同一篇
WEMP_DUP = {
    "title": "深度报道：国产大模型的算力之争",
    "url": "https://mp.weixin.qq.com/s/AbCd1234XyZ?chksm=abc&scene=27",
    "account_name": "量子位",
    "publish_time": "2026-06-16 10:00:00",
    "summary": "重复推送",
}


def run():
    print("[1] 公众号 webhook 入库")
    r = client.post("/ingest/wemp", json=WEMP).json()
    expect(r["inserted"] == 1, f"入库 1 条 (got {r})")

    print("[2] 3 实例/多次推送同一文章 → URL 去重")
    r2 = client.post("/ingest/wemp", json=WEMP).json()
    r3 = client.post("/ingest/wemp", json=WEMP_DUP).json()   # 带跟踪参数的变体
    expect(r2["inserted"] == 0 and r2["duplicated"] == 1, f"完全相同被去重 (got {r2})")
    expect(r3["inserted"] == 0 and r3["duplicated"] == 1, f"带跟踪参数变体也被去重 (got {r3})")

    print("[3] 数组批量推送")
    batch = [WEMP, {"title": "另一篇", "url": "https://mp.weixin.qq.com/s/NEW999",
                    "account_name": "机器之心", "publish_time": 1718598600, "summary": "x"}]
    rb = client.post("/ingest/wemp", json=batch).json()
    expect(rb["inserted"] == 1 and rb["duplicated"] == 1, f"批量去重正确 (got {rb})")

    print("[4] /api/posts 能查到公众号且 source=wechat、时间戳已转换")
    q = client.get("/api/posts?source=wechat").json()
    expect(q["total"] == 2, f"公众号 2 条 (got {q['total']})")
    it = next(x for x in q["items"] if "算力之争" in x["title"])
    expect(it["source"] == "wechat", "source 标识为 wechat")
    expect("正文摘要第一段" in it["content"] and "<p>" not in it["content"], "HTML 已清洗为纯文本")
    expect((it["publish_time"] or "").startswith("2024-06-16"), f"Unix 秒已转时间 (got {it['publish_time']})")

    print("[5] 不破坏现有 /ingest（微博/X）")
    wb = client.post("/ingest", json={"platform": "weibo", "account": "新智元",
                                      "postId": "WB1", "url": "https://weibo.com/u/1/WB1",
                                      "content": "微博", "publishDate": "2026-06-23 09:00:00"}).json()
    x = client.post("/ingest", json={"platform": "x", "account": "StanfordHAI",
                                     "postId": "TW1", "url": "https://x.com/StanfordHAI/status/TW1",
                                     "content": "tweet", "publishDate": "2026-06-23 08:00:00"}).json()
    expect(wb["inserted"] == 1 and x["inserted"] == 1, "现有 /ingest 仍正常入库")

    print("[6] /api/stats 三源混合统计")
    s = client.get("/api/stats").json()
    expect(s["by_source"].get("wechat") == 2, f"stats 含公众号 2 (got {s['by_source']})")
    expect(s["by_source"].get("weibo") == 1 and s["by_source"].get("x") == 1, "三源都计入")
    expect(s["total"] == 4, f"总数 4 (got {s['total']})")

    print("\n🎉 全部通过")


if __name__ == "__main__":
    import sys
    try:
        run()
    except AssertionError:
        sys.exit(1)
