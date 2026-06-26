# WEMP_RSS_SETUP — 公众号采集（we-mp-rss）部署与对接（Step 4 产出）

公众号没有公开的"列出某号全部历史文章"接口，插件做不到自动发现。本系统改用开源后端
**we-mp-rss**（扫码授权 + 定时抓取 → RSS/API/Webhook），把新文章通过 Webhook 推到统一后端
`POST /ingest?source=wechat`。**实时感靠 Webhook 推送，不是缩短抓取间隔**（间隔 ≥30min）。

参考：<https://github.com/rachelos/we-mp-rss>（镜像 `ghcr.io/rachelos/we-mp-rss`，端口 8001）

---

## 1. 启动

先确保统一后端在宿主机 8000 端口跑着（`cd backend && uvicorn app.main:app --port 8000`）。

```bash
cd deploy
docker compose up -d
docker compose logs -f we-mp-rss      # 看启动日志
```
打开管理界面：<http://localhost:8001/>

> Linux 若 `host.docker.internal` 不通：把 `CUSTOM_WEBHOOK` 改成宿主局域网 IP（如 `http://192.168.1.10:8000/ingest?source=wechat`），或在 Step 8 把 backend 一起纳入同一 compose 网络后用服务名 `http://backend:8000/...`。

## 2. 扫码授权

1. 进入管理界面 → 找到「扫码授权 / 登录」。
2. 用**目标采集账号**的微信扫码授权（he 抓取依赖该登录态，请用一个专用微信号）。
3. 授权成功后界面显示已登录。

## 3. 添加 20 个目标公众号

在「添加订阅 / Add Subscription」里逐个搜索并添加（公众号名见下）：

```
硅谷101  互联网的那点事  硅星人  爱范儿  阑夕  数字生命卡兹克  夕小瑶科技说
十字路口Crossing  赛博禅心  向小田  吴说区块链  互联网分析师于斌  机器之心
量子位  新智元  智东西  极客公园  甲子光年  AI前线  AI科技评论
```
> 名称以微信内实际公众号名为准；同名较多时按认证主体确认。

## 4. 抓取间隔（防封硬约束 ≥30min）

`docker-compose.yml` 已设：
- `SPAN_INTERVAL=1800`（任务执行间隔 30 分钟）
- `GATHER_CONTENT_AUTO_INTERVAL=30`（未采内容自动检查 30 分钟）
- `MAX_PAGE=3`（每次最多翻 3 页，保守）

若界面里另有「抓取频率」设置项，也设为 ≥30 分钟。**理由**：公众号风控对高频抓取敏感，且新文及时性已由 Webhook 主动推送保证，无需高频轮询。

## 5. 配置 Webhook → 后端 /ingest

**推荐用公众号专用端点 `/ingest/wemp`**（与微博/X 的 `/ingest` 分开，按 we-mp-rss 模板格式适配、按文章 URL 去重）：

把 `CUSTOM_WEBHOOK` 指向：`http://host.docker.internal:8000/ingest/wemp`

并在 we-mp-rss「消息任务（WebHook）」的**消息模板**里，把推送体配置成下面这个 JSON 结构（字段名照抄，值用 we-mp-rss 的占位符替换）：

```json
{
  "title":        "{{标题占位}}",
  "url":          "{{原文链接占位}}",
  "account_name": "{{公众号名称占位}}",
  "publish_time": "{{发布时间占位}}",
  "summary":      "{{摘要或正文占位}}"
}
```
- `publish_time` 支持 Unix 秒/毫秒，或 `YYYY-MM-DD HH:MM:SS` 字符串，后端统一转换。
- 后端 `app/adapters.py::from_wemp` 负责映射到统一表（`source=wechat`），按 URL（规范化后取文章 `sn`）去重，3 个实例推同一篇只入库一次。

> 兼容：旧的 `/ingest?source=wechat`（走 `_from_wechat` 容错适配）仍可用，但新部署建议用 `/ingest/wemp` + 上面的固定模板，最稳。

## 6. 验证链路（公众号发新文 → Webhook → 库里出现）

### 6a. 真链路（有真实新文时）
目标公众号发新文 → 等到下一个抓取周期（≤30min）→ we-mp-rss 命中 Webhook →
查询后端确认入库：
```bash
curl "http://127.0.0.1:8000/api/posts?source=wechat&page=1"
```

### 6b. 手动可复现验证（不依赖真实发文，随时可跑）
模拟一次 we-mp-rss 的 Webhook 投递：
```bash
curl -X POST "http://127.0.0.1:8000/ingest?source=wechat" \
  -H "Content-Type: application/json" \
  -d '{"title":"验证文章","url":"https://mp.weixin.qq.com/s/VERIFY001",
       "content":"<p>第一段</p><p>第二段</p>","mp_name":"量子位",
       "author":"量子位","publish_time":"2026-06-23 10:00:00"}'
# 期望返回 {"ok":1,"inserted":1,...}
curl "http://127.0.0.1:8000/api/posts?source=wechat&keyword=验证"
# 期望能查到该文章，且 content 已是纯文本"第一段\n第二段"
# 再 POST 一次相同负载 → inserted:0, duplicated:1（去重生效）
```

## 7. 按实际负载校准适配器（重要）

we-mp-rss 未公开 Webhook 负载字段名。**首次真实推送后**，到后端看一眼原始负载：
```bash
# raw_json 里保存了 webhook 原始字段
curl "http://127.0.0.1:8000/api/posts?source=wechat&page=1"
```
（后端入库时把整个负载存进了 `raw_json`。）若发现字段名与适配器假设不符（如正文在 `body` 而非 `content`），
在 `backend/app/adapters.py::_from_wechat` 里补一个候选字段名即可，无需改 we-mp-rss。

---

## 验收对照（Step 4）
- [x] `docker-compose.yml` 能拉起 we-mp-rss（镜像/端口/卷/间隔/Webhook 均按官方参数）
- [x] 抓取间隔 ≥30min（`SPAN_INTERVAL=1800`），README 写明理由
- [x] Webhook 指向 `/ingest?source=wechat`，适配器把负载映射进统一表
- [x] 给出可复现的手动验证步骤（6b），含去重验证
- [ ] 真链路（6a）需在你本机扫码 + 有真实新文后跑通（环境相关，留你执行）
