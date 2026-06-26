# CURRENT_STATE — 现有采集插件现状（Step 1 产出）

> 对象：`../social-collector`（Chrome MV3 扩展）。本文件只描述**现状**，不含改造方案。
> 目的：为后续统一数据模型（Step 2）、后端 `/ingest`（Step 3/5）提供事实依据。

## 一段话总结

现有插件 `social-collector` 用一个 Service Worker（`background.js`）驱动：由 `chrome.alarms` 的 `scrapeAlarm` 周期性触发 `performScrape()`，对 `accounts.js` 注册的账号**逐个串行采集**——**微博**走 weibo.com PC `ajax/statuses/mymblog` JSON 接口（在后台 weibo.com 标签页上下文里 fetch，自动带登录 cookie + XSRF，失败回落 m.weibo.cn 容器接口），**X** 走"打开 `x.com/{handle}` 后台标签页 + 注入脚本滚动解析 `article[data-testid=tweet]` DOM"；两者都把结果归一化为同一套字段、按发布时间取最近 N 条，最后在 `processScrapedItems()` 里以 `platform:postId` 为键去重，增量写入 `chrome.storage.local` 的 `collectedData`（JSON 字符串），并可在侧边栏导出 Excel/CSV。

---

## 1. 微博采集流程

入口：`performScrape()` → 对 `platform ∈ {weibo, both}` 的账号：

1. **UID 解析（缺失才做，结果回填 config）** `weiboResolveUid(query)`，多策略 + 诊断日志：
   - 策略1：在后台 weibo.com 标签页上下文里请求 `/ajax/side/search?q=` → `data.users`（最干净）。
   - 策略2：`m.weibo.cn/api/container/getIndex?containerid=100103type%3D3%26q%3D...` 递归扫 `screen_name+id` 用户对象。
   - 策略3：`m.weibo.cn/n/{昵称}` 跟随重定向，从最终 URL 抽 `/u/{uid}`。
   - `pickBestUser()` 排序：完全同名 > 名字包含 > 认证 > 粉丝数。
2. **取帖子** `weiboFetchPosts(uid, …, cfg)`：
   - 主：`weiboFetchPostsPC(uid, maxPosts)` —— 经 `weiboPcApi()` 在 weibo.com 页面里 GET `/ajax/statuses/mymblog?uid={uid}&page={n}&feature=0`，读 `data.list`；`isLongText` 时再 GET `/ajax/statuses/longtext?id={mblogid}` 展开全文。
   - 回落：`weiboFetchPostsMobile()` —— `m.weibo.cn` 容器接口 `107603{uid}`（需 m.weibo.cn 登录态，未登录返回 `ok:-100`）。
   - 翻页到 `pageCap = min(6, ceil(maxPosts/10)+1)`；累计够 `maxPosts` 即停。
   - `sortRecentSlice()`：按 `publishDate` 从新到旧排序取前 `maxPosts`（自动剔除置顶旧帖）。

## 2. X(推特) 采集流程

入口：`performScrape()` → 对 `platform == x` 的账号 → `xFetchProfile(handle, …, cfg)`：

1. `chrome.tabs.create({url:'https://x.com/{handle}', active: cfg.xVisible})` 开标签页（默认隐藏）。
2. `waitForTabComplete()` + 固定 2.5s 等 SPA 水合。
3. `chrome.scripting.executeScript({func: xScrapeInPage, args:[handle, maxTweets+5, xScrollRounds]})`：
   - 自包含函数，注入页面运行；检测登录墙（`/i/flow/login` 等）→ 返回 `{blocked, blockReason}`。
   - 循环 `window.scrollTo` 到底 + 等待，`collect()` 解析 `article[data-testid="tweet"]`：从 `time` 的 `a[href*="/status/"]` 取 `author/id`，`div[data-testid="tweetText"]` 取正文，`[data-testid=reply/retweet/like]` 的 aria-label 解析互动数，`tweetPhoto img` 取图，`videoPlayer` 判断视频；连续 3 次页面高度不变即停。
4. 回到后台后映射为统一字段，再 `sortRecentSlice(items, xMaxTweets)` 取最近 N。
5. `finally` 关闭标签页。

> 注：公众号当前仅有"给定 `mp.weixin.qq.com/s/...` 链接抓正文"（`wxFetchArticle` + `wx_injector.js` 兜底）与"搜狗发现（不稳定，默认关）"，**无法自动发现历史文章** → 这正是后续 we-mp-rss 要补的部分。

## 3. 数据字段结构（统一 item，写入 collectedData）

每条记录字段（微博/X/公众号共用）：

| 字段 | 说明 | 微博来源 | X 来源 |
|------|------|----------|--------|
| `platform` | `weibo` / `x` / `weixin` | 固定 | 固定 |
| `account` | 目标账号名（accounts.js 的 name） | ✓ | ✓ |
| `authorName` | 实际作者昵称 | `mb.user.screen_name` | status 链接里的 author |
| `postId` | 平台内唯一 id（**去重键**） | `String(mb.id)` | 推文数字 id |
| `url` | 原文链接 | `weibo.com/{uid}/{mblogid}` | `x.com/{author}/status/{id}` |
| `title` | 标题（微博/X 恒空，公众号有） | `''` | `''` |
| `content` | 正文纯文本（X 末尾附外链） | `text_raw`/长文 | tweetText |
| `contentLength` | 正文长度 | ✓ | ✓ |
| `publishDate` | `YYYY-MM-DD HH:MM:SS`（北京时间） | `normWeiboTime` | `isoToLocal(datetime)` |
| `source` | 发布客户端/类型 | `mb.source` | `X`/`转推` |
| `pics` | 图片 url 数组 | `pic_infos.*.url` | `tweetPhoto img.src` |
| `picCount` | 图片数（X 含视频计 1） | ✓ | ✓ |
| `repostsCount`/`commentsCount`/`likesCount` | 互动数 | reposts/comments/attitudes | retweet/reply/like |
| `collected_at` | 采集时刻 ISO 串 | `new Date().toISOString()` | 同左 |

> ⚠️ 当前**没有保存 raw_json**（原始接口/ DOM 数据）。Step 2 统一模型建议补 `raw_json` 以便回溯。
> 公众号路径额外含 `fetchStatus`；微博/X 无该字段。

## 4. 去重逻辑

`processScrapedItems(items)`（`background.js`）：
```js
const exist = new Set(data.map(d => `${d.platform}:${d.postId || d.url}`));
const newItems = items.filter(it => !exist.has(`${it.platform}:${it.postId || it.url}`));
```
- **去重键 = `platform + ':' + (postId || url)`**，对已存量全表去重。
- 新增项 `push` 进 `collectedData`，超过 `maxHistory(8000)` 从头截断。
- 当日采集次数计数器 `scrapeCounter`（跨天重置）。

## 5. 间隔 / 延迟 / 防封参数（现状）

定时调度 `scheduleNextScrapeAlarm()`：
```js
mins = max(1, intervalMin + random()*(intervalMax - intervalMin));   // 默认 30~60 随机
chrome.alarms.create('scrapeAlarm', { delayInMinutes: mins });
```

| 参数 | 当前默认 | 位置 | 作用 |
|------|----------|------|------|
| `intervalMin` / `intervalMax` | **30 / 60** 分钟 | DEFAULT_CONFIG | 整轮采集间隔随机区间 |
| 账号间 / 阶段间 `delay()` | 微博后 `delay(2,4)`；X 后 `delay(3,6)`；UID 解析后 `delay(1,2)` | performScrape | 账号之间随机停顿 |
| 微博翻页 `delay(1.5,3)` | — | weiboFetchPosts* | 翻页随机停顿 |
| X 滚动等待 | `1500 + random()*900` ms | xScrapeInPage | 每次滚动等待 |
| `MAX_SCRAPE_DURATION_MS` | 20 分钟 | — | 僵尸采集强制重置阈值 |
| `weiboMaxPosts` / `xMaxTweets` | 5 / 5 | DEFAULT_CONFIG | 每账号取最近 N 条 |

### 与"防封硬约束"的差距（留待 Step 5 修正，本步仅记录）

1. **微博与 X 共用同一个 `intervalMin~intervalMax`（30~60）**，未按约束差异化（微博应 15–30、X 应 30–60）。当前所有账号在**一轮** `performScrape` 里串行跑完，无法对两类平台分别定间隔。
2. 无显式**失败退避（backoff）**：请求失败只记日志，不会拉长下次间隔。
3. 无对接后端 `/ingest` 的推送链路（仅本地存储 + 手动导出）。

> 以上差距均为已知项，Step 5 处理；Step 1 仅做现状记录，不改代码。
