#!/usr/bin/env python3
"""把 last30days 的 JSON 报告渲染成卡片式输出。

读 last30days 已经跑完的报告 JSON（或 --emit=json 的输出），
按主题聚成卡片，每卡只留重点。不联网、不改 last30days 本身。

用法：
    python cards.py <report.json>
    python cards.py <report.json> --style rundown|table|plain
    python cards.py <report.json> --top 5 --source youtube
    python cards.py <report.json> --json          # 输出中间结构，便于再加工
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from common import load_report as _load_report
from common import source_name


# ---------- 文本清洗 ----------

def clip(text: str | None, limit: int = 110) -> str:
    """压平空白并截断——卡片里不做整段搬运。"""
    t = re.sub(r"\s+", " ", (text or "")).strip()
    return t if len(t) <= limit else t[:limit].rstrip() + "…"


# explanation 常是内部信号而非人话，别让它们占版面
_NOISE = ("fallback", "local-score", "no-explanation", "none", "n/a")


def clean_reason(value: str | None) -> str:
    t = (value or "").strip()
    if not t or any(n in t.lower() for n in _NOISE):
        return ""
    return clip(t, 120)


# ---------- 数据提取 ----------

def load_report(path: Path) -> dict:
    """兼容旧调用点：真正的实现和 cardimg / merge_reports 共用 common.py。"""
    return _load_report(path)


def normalize_engagement(eng: dict | None, src: str = "") -> str:
    """把各源不同的互动字段统一成一行可读文本。

    Reddit 的 points 是赞数，HN 的 points 是分数，叫法不能混。
    """
    if not eng:
        return ""
    is_reddit = src.startswith("reddit") or source_name(src).startswith("r/")
    parts = []
    if eng.get("views"):
        parts.append(f"{eng['views']:,} 播放")
    if eng.get("likes"):
        parts.append(f"{eng['likes']:,} 赞")
    if eng.get("comments"):
        parts.append(f"{eng['comments']:,} 评")
    if eng.get("points"):
        parts.append(f"{eng['points']:,} {'赞' if is_reddit else '分'}")
    if eng.get("stars"):
        parts.append(f"{eng['stars']:,} 星")
    if eng.get("upvotes"):
        parts.append(f"{eng['upvotes']:,} 顶")
    return " · ".join(parts)


# 来源别名：用户嘴上说 "hackernews"，报告里可能写 "hacker_news_custom"。
# 出图和出文字用同一套别名，否则同一份合并报告图上有卡、文字说没数据。
SOURCE_ALIAS = {
    "hackernews": {"hackernews", "hacker_news_custom"},
    "hn": {"hackernews", "hacker_news_custom"},
    "reddit": {"reddit", "reddit_wsb", "reddit_inv"},
    "poly": {"polymarket"},
    "polymarket": {"polymarket"},
}


def matches_source(wanted: str, actual: str) -> bool:
    """wanted 是用户传的 --source，actual 是报告里的来源 key。"""
    if not wanted:
        return True
    if wanted == actual:
        return True
    return actual in SOURCE_ALIAS.get(wanted.lower(), {wanted})


def build_cards(report: dict, top: int, source_filter: str | None) -> list[dict]:
    """把 ranked_candidates 按 cluster 分组成卡片，只保留重点字段。"""
    items_by_id = {}
    for src, items in (report.get("items_by_source") or {}).items():
        for it in items or []:
            items_by_id[it.get("item_id")] = it

    clusters = report.get("clusters") or []
    cards = []

    for cl in clusters:
        srcs = cl.get("sources") or []
        if source_filter and not any(matches_source(source_filter, s) for s in srcs):
            continue

        # 取该簇的代表条目，按最终得分排序
        cand_ids = set(cl.get("candidate_ids") or [])
        members = [
            c for c in (report.get("ranked_candidates") or [])
            if c.get("candidate_id") in cand_ids
        ]
        if source_filter:
            members = [m for m in members
                       if matches_source(source_filter, m.get("source") or "")
                       or any(matches_source(source_filter, s)
                              for s in (m.get("sources") or []))]
        if not members:
            continue
        members.sort(key=lambda c: c.get("final_score") or 0, reverse=True)

        lead = members[0]
        item = items_by_id.get(lead.get("item_id")) or {}
        meta = item.get("metadata") or {}

        # 按来源过滤后，簇标题可能仍来自被过滤掉的那个源，此时改用条目自身标题
        title = cl.get("title") or ""
        if source_filter or not title:
            title = lead.get("title") or item.get("title") or title or "（无标题）"

        # snippet 与 title 重复时丢弃（HN/GitHub/YouTube 常见：描述以标题开头）
        snippet = clip(lead.get("snippet") or item.get("snippet"), 180)
        if snippet:
            t_head = clip(title, 60).rstrip("…")
            if snippet.rstrip("…").startswith(t_head):
                snippet = ""

        # 重点三件套：一句话结论 > 时间线 > 互动量
        evidence = []
        for hl in (meta.get("transcript_highlights") or [])[:2]:
            evidence.append(clip(hl))
        for cm in (meta.get("top_comments") or []):
            if cm.get("is_uploader"):
                continue  # UP 主自夸/推广，不是观众观点
            txt = (cm.get("excerpt") or "").strip()
            if txt:
                evidence.append(f"{cm.get('author','匿名')}: {clip(txt, 90)}")
            if len(evidence) >= 4:
                break

        # 分数：不过滤时用簇分（聚合信号）；过滤后照搬簇分会张冠李戴
        # （簇里最高分的可能是被滤掉的那个源），改用该成员自己的分数。
        if source_filter:
            score = lead.get("final_score") or 0
        else:
            score = cl.get("score") or lead.get("final_score") or 0

        # 过滤时只显示真正命中的那些来源，别把 "reddit" 这种别名当来源名印出去
        shown = [s for s in srcs if matches_source(source_filter, s)] if source_filter else srcs
        shown = [s for s in ([lead.get("source")] if source_filter and lead.get("source")
                             else shown) if s]

        cards.append({
            "title": title,
            "sources": [source_name(s) for s in shown],
            "score": round(score, 1),
            "url": lead.get("url") or item.get("url") or "",
            "author": item.get("author") or "",
            "published": (item.get("published_at") or "")[:10],
            "engagement": normalize_engagement(item.get("engagement"),
                                              item.get("source") or ""),
            "snippet": snippet,
            "why": clean_reason(lead.get("explanation") or item.get("why_relevant")),
            "evidence": evidence,
            "member_count": len(members),
        })

    cards.sort(key=lambda c: c["score"], reverse=True)
    return cards[:top] if top else cards


# ---------- 三种输出风格 ----------

def render_rundown(cards: list[dict], report: dict) -> str:
    """卡片式：每卡独立成块，先结论后证据。"""
    out = []
    topic = report.get("topic", "")
    rng = f"{report.get('range_from','')} ~ {report.get('range_to','')}"
    out.append(f"**TL;DR:** {topic} · {len(cards)} 张卡 · {rng}")
    out.append("")

    for i, c in enumerate(cards, 1):
        head = f"**{i}. {c['title']}**"
        out.append(head)
        meta_bits = []
        if c["sources"]:
            meta_bits.append(" / ".join(c["sources"]))
        if c["engagement"]:
            meta_bits.append(c["engagement"])
        if c["published"]:
            meta_bits.append(c["published"])
        if meta_bits:
            out.append(" · ".join(meta_bits))
        if c["snippet"]:
            out.append(c["snippet"])
        if c["why"]:
            out.append(f"→ {c['why']}")
        for ev in c["evidence"]:
            out.append(f"  「{ev}」")
        if c["url"]:
            out.append(c["url"])
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_table(cards: list[dict], report: dict) -> str:
    """表格：一屏扫完所有条目。"""
    out = [f"| # | 标题 | 来源 | 互动 | 得分 |", "|---|---|---|---|---|"]
    for i, c in enumerate(cards, 1):
        title = c["title"].replace("|", "\\|")[:60]
        out.append(
            f"| {i} | {title} | {'/'.join(c['sources'])} | "
            f"{c['engagement'] or '-'} | {c['score']} |"
        )
    return "\n".join(out) + "\n"


def render_plain(cards: list[dict], report: dict) -> str:
    """纯文本：给下游脚本或最小 token 场景。"""
    out = []
    for c in cards:
        out.append(f"[{c['score']}] {c['title']} ({'/'.join(c['sources'])})")
        if c["engagement"]:
            out.append(f"  {c['engagement']}")
        if c["url"]:
            out.append(f"  {c['url']}")
    return "\n".join(out) + "\n"


def _span_days(rng_from: str, rng_to: str) -> str:
    """把报告窗口算成 "N 天" 前缀，算不出来就返回空串。"""
    from datetime import date

    try:
        a = date.fromisoformat(rng_from[:10])
        b = date.fromisoformat(rng_to[:10])
    except (ValueError, TypeError):
        return ""
    days = (b - a).days
    return f"{days} 天" if days > 0 else ""


def render_news(cards: list[dict], report: dict) -> str:
    """新闻式综述：导语讲清这一个月发生了什么，再按时间轴铺开。

    所有数字都从报告里算，不臆造。
    """
    topic = report.get("topic", "")
    rng_from, rng_to = report.get("range_from", ""), report.get("range_to", "")

    # 源分布
    src_count = {}
    for c in cards:
        for s in c["sources"]:
            src_count[s] = src_count.get(s, 0) + 1
    src_line = " · ".join(f"{s} {n}" for s, n in
                          sorted(src_count.items(), key=lambda x: -x[1]))

    # 按日期聚合
    by_date: dict[str, list[dict]] = {}
    for c in cards:
        d = c["published"] or "未知日期"
        by_date.setdefault(d, []).append(c)

    # 找最集中的一天
    peak_date, peak_items = max(by_date.items(), key=lambda kv: len(kv[1])) \
        if by_date else ("", [])
    top_card = max(cards, key=lambda c: c["score"]) if cards else None

    out = []
    # 时长从报告的真实窗口算，不写死"30 天"——上游可能只跑了 7 天
    span = _span_days(rng_from, rng_to)
    out.append(f"# {topic} · {span}事件综述")
    out.append("")
    out.append(f"**时间范围：** {rng_from} ~ {rng_to}　**共 {len(cards)} 条线索**")
    out.append(f"**来源分布：** {src_line}")
    out.append("")

    # 导语：三句话概括
    out.append("## 概况")
    if top_card:
        out.append(
            f"这段时间里声量最高的是「{top_card['title']}」"
            f"（{top_card['engagement'] or '无互动数据'}，得分 {top_card['score']}）。"
        )
    if peak_date and len(peak_items) >= 2:
        out.append(
            f"最密集的一天是 {peak_date}，一天内冒出 {len(peak_items)} 条线索："
            f"{'、'.join('「' + clip(i['title'], 30) + '」' for i in peak_items[:3])}。"
        )
    out.append("")

    # 时间轴
    out.append("## 时间轴")
    out.append("")
    for d in sorted(by_date):
        items = sorted(by_date[d], key=lambda c: c["score"], reverse=True)
        out.append(f"**{d}**　{len(items)} 条")
        for c in items:
            meta = " · ".join(x for x in [c["engagement"]] if x)
            out.append(f"- **{c['title']}**" + (f"　{meta}" if meta else ""))
            if c["snippet"]:
                out.append(f"  {clip(c['snippet'], 100)}")
        out.append("")
    return "\n".join(out).rstrip() + "\n"


STYLES = {"rundown": render_rundown, "table": render_table,
          "plain": render_plain, "news": render_news}


def main() -> int:
    ap = argparse.ArgumentParser(description="把 last30days JSON 渲染成卡片")
    ap.add_argument("report", type=Path, help="last-report.json 或 --emit=json 的输出")
    ap.add_argument("--style", choices=list(STYLES), default="rundown")
    ap.add_argument("--top", type=int, default=0, help="只显示前 N 张卡，0=全部")
    ap.add_argument("--source", default=None, help="只保留某来源，如 youtube")
    ap.add_argument("--json", action="store_true", help="输出中间结构而非渲染文本")
    args = ap.parse_args()

    if not args.report.exists():
        print(f"报告不存在: {args.report}", file=sys.stderr)
        return 1

    try:
        report = load_report(args.report)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"报告解析失败: {e}", file=sys.stderr)
        return 1

    cards = build_cards(report, args.top, args.source)
    if not cards:
        print("没有可渲染的卡片（clusters 为空或来源过滤后无剩）", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(cards, ensure_ascii=False, indent=2))
    else:
        print(STYLES[args.style](cards, report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
