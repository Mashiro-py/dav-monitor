"""验证 we-mp-rss 主动拉取同步：RSS XML 解析、字段映射、入库去重、/api/posts 字段完整。
不依赖网络：monkeypatch wemp_sync._get 返回固定 RSS XML。
运行：cd backend && python -m tests.test_wemp_sync
"""
import os

os.environ["DB_URL"] = "sqlite:///./test_sync.db"
if os.path.exists("test_sync.db"):
    os.remove("test_sync.db")

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402
from app import wemp_sync  # noqa: E402

# --- 固定的 we-mp-rss RSS 样例（仿你实测的格式）---
RSS_LIST = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>订阅列表</title>
<item><title>机器之心</title><link>http://x/rss/MP_WXS_3073282833</link>
<guid>MP_WXS_3073282833</guid></item>
<item><title>爱范儿</title><link>http://x/rss/MP_WXS_2831008240</link>
<guid>MP_WXS_2831008240</guid></item>
</channel></rss>"""

FEED_JIQI = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
<channel><title>机器之心</title><link>http://x</link>
<item>
  <title>大模型最新突破</title>
  <link>https://mp.weixin.qq.com/s/JIQI_AAA</link>
  <guid>https://mp.weixin.qq.com/s/JIQI_AAA</guid>
  <description>&lt;p&gt;摘要内容一&lt;/p&gt;</description>
  <pubDate>Sat, 27 Jun 2026 15:57:31 +0800</pubDate>
  <enclosure url="https://img/cover1.jpg" type="image/jpeg"/>
  <content:encoded></content:encoded>
</item>
<item>
  <title>第二篇文章</title>
  <link>https://mp.weixin.qq.com/s/JIQI_BBB?chksm=zz&amp;scene=27</link>
  <description>摘要二</description>
  <pubDate>Fri, 26 Jun 2026 09:00:00 +0800</pubDate>
</item>
</channel></rss>"""

FEED_IFANR = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>爱范儿</title>
<item><title>新品发布</title><link>https://mp.weixin.qq.com/s/IFANR_CCC</link>
<description>摘要三</description><pubDate>Sat, 27 Jun 2026 10:00:00 +0800</pubDate></item>
</channel></rss>"""


async def fake_get(client, url):
    if url.endswith("/rss"):
        return RSS_LIST
    if "MP_WXS_3073282833" in url:
        return FEED_JIQI
    if "MP_WXS_2831008240" in url:
        return FEED_IFANR
    raise AssertionError("unexpected url " + url)


wemp_sync._get = fake_get
wemp_sync.WEMP_INSTANCES = ["http://dummy:8001"]   # 单实例即可覆盖逻辑

client = TestClient(app)


def expect(c, m):
    print(("  ✅ " if c else "  ❌ ") + m)
    assert c


def run():
    print("[0] 纯解析单测")
    ids = wemp_sync.parse_feed_ids(RSS_LIST)
    expect(ids == ["MP_WXS_3073282833", "MP_WXS_2831008240"], f"feed_id 提取+保序去重 {ids}")
    acc, arts = wemp_sync.parse_articles(FEED_JIQI)
    expect(acc == "机器之心", "公众号名取自 channel/title")
    expect(len(arts) == 2 and arts[0]["url"] == "https://mp.weixin.qq.com/s/JIQI_AAA", "文章link解析")
    expect(arts[0]["pic_url"] == "https://img/cover1.jpg", "enclosure→封面图")

    print("[1] 手动触发 /sync/wemp 拉取入库")
    r = client.post("/sync/wemp").json()
    expect(r["feeds"] == 2 and r["articles"] == 3, f"发现2feed/3篇 (got {r})")
    expect(r["inserted"] == 3 and r["duplicated"] == 0, f"入库3篇 (got {r})")

    print("[2] 重复拉取 → 去重，不重复入库")
    r2 = client.post("/sync/wemp").json()
    expect(r2["inserted"] == 0 and r2["duplicated"] == 3, f"全部去重 (got {r2})")

    print("[3] /api/posts 字段完整性")
    q = client.get("/api/posts?source=wechat").json()
    expect(q["total"] == 3, f"公众号3条 (got {q['total']})")
    a = next(x for x in q["items"] if "大模型最新突破" in x["title"])
    expect(a["account_name"] == "机器之心", "account_name 填充")
    expect(a["original_url"] == "https://mp.weixin.qq.com/s/JIQI_AAA", "original_url 正确")
    expect((a["publish_time"] or "").startswith("2026-06-27T07:57"), f"RFC822→UTC 时间 (got {a['publish_time']})")
    expect("摘要内容一" in (a["content"] or "") and "<p>" not in a["content"], "description→content 去HTML")
    expect(a["media_urls"] == ["https://img/cover1.jpg"], "封面图入 media_urls")

    print("[4] 三源混合统计含公众号")
    s = client.get("/api/stats").json()
    expect(s["by_source"].get("wechat") == 3, f"stats 含公众号3 (got {s['by_source']})")

    print("\n🎉 全部通过")


if __name__ == "__main__":
    import sys
    try:
        run()
    except AssertionError:
        sys.exit(1)
