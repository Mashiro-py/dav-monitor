"""AI 热点态势分析（DeepSeek）。

链路：取最近 N 小时三源内容（微博/X/公众号）→ 截断到上下文预算 →
DeepSeek 提炼热点事件/核心观点/整体态势（中英双语 JSON）→ 入库 analyses 表。

DeepSeek 调用规范（官方 OpenAI 兼容接口）：
  POST {DEEPSEEK_BASE}/chat/completions
  Header: Authorization: Bearer {DEEPSEEK_API_KEY}
  Body:   model / messages / stream=false / temperature / max_tokens
          / response_format={"type":"json_object"}（JSON 模式要求 prompt 中出现
          "json" 字样与结构说明——system 提示词已满足）
  ⚠️ key 的唯一存放位置：deploy/.env 的 DEEPSEEK_API_KEY（见 config.py 注释）。
"""
import asyncio
import json
import logging
import random
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select, func, and_, or_

from .config import (DEEPSEEK_API_KEY, DEEPSEEK_BASE, DEEPSEEK_MODEL,
                     ANALYSIS_HOURS, ANALYSIS_AUTO_HOUR, ANALYSIS_AUTO_ENABLED,
                     ANALYSIS_MANUAL_LIMIT)
from .db import SessionLocal
from .models import Post, Analysis

log = logging.getLogger("analysis")

# 配额与自动任务按【北京时间】的自然日计算（容器默认 UTC，不依赖容器时区设置）
BJ_TZ = timezone(timedelta(hours=8))

# ---- 语料截断预算 ----
PER_ITEM_CAP = {"wechat": 800}   # 公众号文章长，取标题+前800字（首段承载主要信息）
PER_ITEM_CAP_DEFAULT = 500       # 微博/X 本就短
CORPUS_BUDGET = 40000            # 全部条目拼装后的字符预算（≈3万 token，64K 上下文安全区）
FETCH_LIMIT = 1000               # 窗口内最多取多少条（防极端情况撑爆内存）


class AnalysisError(Exception):
    """可读的分析失败原因（文案会原样返回给前端展示）。"""


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _bj_day_start_utc():
    """今天（北京时间自然日）零点对应的 UTC naive 时间，用于配额统计。"""
    start_bj = datetime.now(BJ_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    return start_bj.astimezone(timezone.utc).replace(tzinfo=None)


def _iso(dt):
    return dt.isoformat() + "Z" if dt else None


# ===================== 语料准备 =====================

def _fetch_posts(db, hours):
    """取最近 hours 小时的三源内容，publish_time 缺失的按 collect_time 兜底，新→旧。"""
    since = _utcnow() - timedelta(hours=hours)
    return db.execute(
        select(Post)
        .where(or_(Post.publish_time >= since,
                   and_(Post.publish_time.is_(None), Post.collect_time >= since)))
        .order_by(Post.publish_time.desc().nullslast(), Post.id.desc())
        .limit(FETCH_LIMIT)
    ).scalars().all()


def _render_lines(rows, cap_scale=1.0):
    """把每条内容渲染成一行紧凑文本：[序号] 来源|账号|时间|标题|正文摘录。"""
    lines = []
    for i, p in enumerate(rows, 1):
        cap = int(PER_ITEM_CAP.get(p.source, PER_ITEM_CAP_DEFAULT) * cap_scale)
        text = " ".join((p.content or "").split())[:cap]
        t = (p.publish_time or p.collect_time)
        t_bj = (t.replace(tzinfo=timezone.utc).astimezone(BJ_TZ).strftime("%m-%d %H:%M")) if t else "?"
        title = " ".join((p.title or "").split())[:80]
        lines.append(f"[{i}] {p.source}|{p.account_name or '?'}|{t_bj}|{title}|{text}")
    return lines


def _take_within_budget(lines):
    """按时间序（新→旧）累加，超预算即停：保最新、丢最旧。"""
    out, used = [], 0
    for ln in lines:
        if out and used + len(ln) > CORPUS_BUDGET:
            break
        out.append(ln)
        used += len(ln)
    return out


def build_corpus(rows):
    """三级截断：单条上限 → 超预算单条减半 → 仍超则丢最旧。返回 (lines, covered)。"""
    lines = _render_lines(rows)
    if sum(map(len, lines)) > CORPUS_BUDGET:
        lines = _render_lines(rows, 0.5)
    lines = _take_within_budget(lines)
    return lines, len(lines)


# ===================== Prompt =====================

SYSTEM_PROMPT = """你是一名资深的中英双语舆情分析师。用户会提供一批中国大V账号（来自微博、X/推特、微信公众号）在指定时间窗口内发布的内容。

你的任务：
1. 识别这些大V正在发布/讨论的热点事件；
2. 识别他们正在评论的热点事件；
3. 提炼各账号的核心观点、立场，以及账号之间的观点分歧。

铁律：
- 只依据提供的内容归纳，禁止编造、禁止引入材料之外的背景知识、禁止外推；
- 无法判断的字段留空数组或空字符串，不要臆测；
- 所有面向读者的文本字段必须同时给出 zh（简体中文）和 en（English，地道翻译）两个版本。

严格输出以下 JSON 结构（json_object），不要输出任何 JSON 之外的文字：
{
  "summary": {"zh": "当日整体态势总结，150-300字", "en": "Overall situation summary in English"},
  "hot_events": [
    {
      "title": {"zh": "事件标题", "en": "Event title"},
      "accounts": ["涉及的账号名"],
      "sources": ["weibo", "wechat", "x"],
      "post_count": 相关内容条数（整数）,
      "brief": {"zh": "事件简述及大V们如何参与讨论，50-120字", "en": "Brief in English"}
    }
  ],
  "key_opinions": [
    {
      "topic": {"zh": "观点主题", "en": "Topic"},
      "accounts": ["持此观点的账号名"],
      "opinion": {"zh": "观点摘要", "en": "Opinion summary"},
      "has_disagreement": true或false,
      "disagreement": {"zh": "对立观点及持有账号；无对立则为空字符串", "en": "..."}
    }
  ]
}

hot_events 按热度（相关条数×涉及账号数）降序排列，最多 8 个；key_opinions 最多 8 条。"""


def build_user_prompt(lines, total, covered, start_utc, end_utc):
    s = start_utc.replace(tzinfo=timezone.utc).astimezone(BJ_TZ).strftime("%Y-%m-%d %H:%M")
    e = end_utc.replace(tzinfo=timezone.utc).astimezone(BJ_TZ).strftime("%Y-%m-%d %H:%M")
    head = (f"时间窗口：{s} ~ {e}（北京时间）。窗口内共 {total} 条内容，"
            f"以下提供 {covered} 条（每行格式：[序号] 来源|账号|发布时间|标题|正文摘录）：\n\n")
    return head + "\n".join(lines)


# ===================== DeepSeek 调用 =====================

async def _call_deepseek(messages):
    if not DEEPSEEK_API_KEY:
        raise AnalysisError("未配置 DEEPSEEK_API_KEY（应写在 deploy/.env，随 backend 容器注入）")
    url = f"{DEEPSEEK_BASE}/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}",
               "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": messages,
        "stream": False,
        "temperature": 0.3,
        "max_tokens": 6000,
        "response_format": {"type": "json_object"},
    }
    last = None
    for attempt in range(1, 4):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10)) as client:
                r = await client.post(url, headers=headers, json=payload)
            # 4xx 里可判定的错误直接给可读文案，不再重试
            if r.status_code == 401:
                raise AnalysisError("DeepSeek API key 无效（401），请检查 deploy/.env 的 DEEPSEEK_API_KEY")
            if r.status_code == 402:
                raise AnalysisError("DeepSeek 账户余额不足（402），请充值后重试")
            if r.status_code >= 400:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            data = r.json()
            return data["choices"][0]["message"]["content"]
        except AnalysisError:
            raise
        except Exception as e:  # 网络/超时/429/5xx → 重试
            last = e
            log.warning("deepseek attempt %s/3 failed: %s", attempt, e)
            if attempt < 3:
                await asyncio.sleep(2 if attempt == 1 else 8)
    raise AnalysisError(f"DeepSeek 调用失败（已重试 3 次）：{last}")


def _parse_result(text):
    """解析并校验模型输出；json_object 模式下极少失败，失败时尝试截取大括号修复。"""
    try:
        obj = json.loads(text)
    except Exception:
        s, e = text.find("{"), text.rfind("}")
        if s < 0 or e <= s:
            raise AnalysisError("模型输出不是合法 JSON，请重试")
        try:
            obj = json.loads(text[s:e + 1])
        except Exception:
            raise AnalysisError("模型输出不是合法 JSON，请重试")
    if not isinstance(obj, dict):
        raise AnalysisError("模型输出结构异常，请重试")
    obj.setdefault("summary", {"zh": "", "en": ""})
    obj["hot_events"] = obj.get("hot_events") or []
    obj["key_opinions"] = obj.get("key_opinions") or []
    return obj


# ===================== 配额 / 序列化 =====================

def manual_used_today(db) -> int:
    """今日（北京时间自然日）已消耗的手动配额 = 当日成功的 manual 分析行数。"""
    return db.execute(
        select(func.count()).select_from(Analysis)
        .where(and_(Analysis.trigger_type == "manual",
                    Analysis.created_at >= _bj_day_start_utc()))
    ).scalar() or 0


def auto_ran_today(db) -> bool:
    return bool(db.execute(
        select(func.count()).select_from(Analysis)
        .where(and_(Analysis.trigger_type == "auto",
                    Analysis.created_at >= _bj_day_start_utc()))
    ).scalar())


def quota_info(db) -> dict:
    used = manual_used_today(db)
    last = db.execute(select(Analysis).order_by(Analysis.id.desc()).limit(1)).scalar_one_or_none()
    return {
        "used": used,
        "limit": ANALYSIS_MANUAL_LIMIT,
        "remaining": max(0, ANALYSIS_MANUAL_LIMIT - used),
        "last_run_at": _iso(last.created_at) if last else None,
        "running": is_running(),
    }


def analysis_to_dict(a: Analysis) -> dict:
    def _loads(s, default):
        try:
            return json.loads(s) if s else default
        except Exception:
            return default
    return {
        "id": a.id,
        "created_at": _iso(a.created_at),
        "trigger_type": a.trigger_type,
        "model": a.model,
        "range_start": _iso(a.range_start),
        "range_end": _iso(a.range_end),
        "covered_count": a.covered_count,
        "total_count": a.total_count,
        "source_stats": _loads(a.source_stats, {}),
        "result": _loads(a.result_json, {}),
    }


def latest_analysis(db):
    a = db.execute(select(Analysis).order_by(Analysis.id.desc()).limit(1)).scalar_one_or_none()
    return analysis_to_dict(a) if a else None


def history(db, limit=30):
    rows = db.execute(
        select(Analysis).order_by(Analysis.id.desc()).limit(max(1, min(100, limit)))
    ).scalars().all()
    return [analysis_to_dict(a) for a in rows]


# ===================== 执行一次分析 =====================

_lock = asyncio.Lock()


def is_running() -> bool:
    return _lock.locked()


async def run_analysis(db, trigger: str) -> dict:
    """跑一次完整分析并入库。失败抛 AnalysisError（不入库 = 不扣配额）。"""
    if _lock.locked():
        raise AnalysisError("已有一次分析正在进行中，请稍候再试")
    async with _lock:
        end = _utcnow()
        start = end - timedelta(hours=ANALYSIS_HOURS)
        rows = _fetch_posts(db, ANALYSIS_HOURS)
        if not rows:
            raise AnalysisError(f"最近 {ANALYSIS_HOURS} 小时没有可分析的内容，跳过")
        src_stats = {}
        for p in rows:
            src_stats[p.source] = src_stats.get(p.source, 0) + 1

        lines, covered = build_corpus(rows)
        user_prompt = build_user_prompt(lines, len(rows), covered, start, end)
        content = await _call_deepseek([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ])
        result = _parse_result(content)

        a = Analysis(
            created_at=_utcnow(), trigger_type=trigger, model=DEEPSEEK_MODEL,
            range_start=start, range_end=end,
            covered_count=covered, total_count=len(rows),
            source_stats=json.dumps(src_stats, ensure_ascii=False),
            result_json=json.dumps(result, ensure_ascii=False),
        )
        db.add(a)
        db.commit()
        log.info("analysis done: id=%s trigger=%s covered=%s/%s", a.id, trigger, covered, len(rows))
        return analysis_to_dict(a)


# ===================== 每日自动分析（asyncio 后台循环） =====================

_sched_task = None


async def _run_auto() -> bool:
    db = SessionLocal()
    try:
        r = await run_analysis(db, "auto")
        log.info("auto analysis ok: id=%s", r["id"])
        return True
    except AnalysisError as e:
        log.warning("auto analysis failed: %s", e)
        return False
    except Exception as e:
        log.warning("auto analysis error: %s", e)
        return False
    finally:
        db.close()


async def _auto_loop():
    await asyncio.sleep(20)   # 等应用完全就绪
    while True:
        try:
            db = SessionLocal()
            try:
                ran = auto_ran_today(db)
            finally:
                db.close()
            now_bj = datetime.now(BJ_TZ)
            target = now_bj.replace(hour=ANALYSIS_AUTO_HOUR,
                                    minute=random.randint(20, 40), second=0, microsecond=0)
            if not ran and now_bj >= target:
                # 到点未跑（含容器中午重启的补跑场景）：立即执行；失败 30 分钟后再试
                ok = await _run_auto()
                if not ok:
                    await asyncio.sleep(1800)
                continue
            if ran:
                target += timedelta(days=1)   # 今天已跑 → 睡到明天的时段
            wait = (target - datetime.now(BJ_TZ)).total_seconds()
            await asyncio.sleep(max(60, wait))
        except Exception as e:
            log.warning("analysis auto loop error: %s", e)
            await asyncio.sleep(600)


def start_scheduler():
    global _sched_task
    if not ANALYSIS_AUTO_ENABLED:
        log.info("analysis auto disabled (ANALYSIS_AUTO_ENABLED=false)")
        return
    if not DEEPSEEK_API_KEY:
        log.info("analysis auto disabled: DEEPSEEK_API_KEY not set (deploy/.env)")
        return
    if _sched_task is None:
        _sched_task = asyncio.create_task(_auto_loop())
        log.info("analysis scheduler started: daily ~%02d:20-%02d:40 BJT, window=%sh",
                 ANALYSIS_AUTO_HOUR, ANALYSIS_AUTO_HOUR, ANALYSIS_HOURS)
