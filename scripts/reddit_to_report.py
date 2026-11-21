"""把 Reddit 存档（Arctic Shift）的帖子转成 cardimg 能吃的 report 结构。

Reddit 官方 JSON 在本网络不可达（直连超时 / 代理 403），
改用 arctic-shift.photon-reddit.com 存档 API，直连可用。

用法示例：
  python reddit_to_report.py --sub technology --sub programming ^
      --after 2026-11-13 --before 2026-11-21 --keyword release --min-score 100
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

from common import default_out

# Windows 控制台默认 GBK，标题里的 emoji 会直接报错
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

API = "https://arctic-shift.photon-reddit.com/api/posts/search"
COMMENTS_API = "https://arctic-shift.photon-reddit.com/api/comments/search"
UA = "last30days-cards/1.0"

# 子板 → 在卡片图上显示的来源名与配色（见 cardimg.SRC_NAME / SRC_COLOR）
SUB_TAG = {
    "wallstreetbets": "reddit_wsb",
    "investing": "reddit_inv",
}


def get(url, timeout=40, retries=4):
    """Arctic Shift 会限流（422 / 429），退避重试。"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            last = e
            if i < retries - 1:
                time.sleep(3 * (i + 1))
    raise last


def fetch_sub(sub, after, before, pages=4, limit=100, pause=2.0):
    """按时间倒序翻页，直到越过 after 或取满 pages。"""
    out, cursor = [], before
    for i in range(pages):
        q = urllib.parse.urlencode({
            "subreddit": sub, "after": after, "before": cursor,
            "limit": limit, "sort": "desc",
        })
        try:
            data = get(API + "?" + q).get("data", [])
        except Exception as e:
            print(f"  ! {sub} 第 {i + 1} 页失败: {type(e).__name__} {e}", file=sys.stderr)
            break
        if not data:
            break
        out.extend(data)
        oldest = min(p.get("created_utc") or 0 for p in data)
        cursor = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(oldest))
        if len(data) < limit:
            break
        time.sleep(pause)
    return out


def thumb_of(p):
    """Reddit 帖子的缩略图。self 贴无图，链接贴常有。"""
    t = p.get("thumbnail") or ""
    if t.startswith("http"):
        return t
    preview = p.get("preview") or {}
    imgs = preview.get("images") or []
    if imgs:
        src = (imgs[0].get("source") or {}).get("url") or ""
        if src.startswith("http"):
            return src.replace("&amp;", "&")
    return ""


def junk(s, min_len=24):
    """摘要可用性判断：纯图链、纯表情、过短、无实义，一律算废。"""
    if not s or len(s.strip()) < min_len:
        return True
    if re.fullmatch(r"(https?://\S+\s*)+", s.strip()):
        return True
    if not re.search(r"[A-Za-z\u4e00-\u9fff]", s):
        return True
    return False


def body_of(p, limit=160):
    """帖子正文摘要。selftext 常被删成 [removed]，那就留空。"""
    st = (p.get("selftext") or "").strip()
    if not st or st in ("[removed]", "[deleted]"):
        return ""
    st = " ".join(st.split())
    st = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", st)   # 去 markdown 图片
    st = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", st)  # 链接留文字
    st = re.sub(r"[*_`#>|\\]", "", st)
    st = re.sub(r"https?://\S+", "", st)            # 去掉裸链接，只留文字
    st = " ".join(st.split())
    if len(st) <= limit:
        return "" if junk(st) else st
    cut = st[:limit]
    sp = cut.rfind(" ")
    st = (cut[:sp] if sp > limit * 0.6 else cut).rstrip() + "…"
    return "" if junk(st) else st


def top_comment(pid, timeout=30):
    """抓该帖最像样的高赞评论，用作正文缺失时的摘要。失败返回空串。"""
    if not pid:
        return ""
    try:
        q = urllib.parse.urlencode({"link_id": pid, "limit": 100, "sort": "desc"})
        cs = get(COMMENTS_API + "?" + q, timeout=timeout).get("data", [])
    except Exception:
        return ""
    cs = [c for c in cs
          if (c.get("body") or "").strip() not in ("", "[removed]", "[deleted]")]
    cs.sort(key=lambda c: c.get("score") or 0, reverse=True)

    # 从高赞往下找第一条有实质内容的，纯图链/纯表情不算
    for best in cs[:12]:
        body = " ".join((best.get("body") or "").split())
        body = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", body)
        body = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", body)
        body = re.sub(r"https?://\S+", "", body)
        body = " ".join(body.split())
        if junk(body, min_len=30):
            continue
        if len(body) > 150:
            body = body[:150].rstrip() + "…"
        return f"热评 {best.get('score') or 0} 赞：{body}"
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sub", action="append", required=True,
                    help="子板名，可重复传多个")
    ap.add_argument("--after", required=True)
    ap.add_argument("--before", required=True)
    ap.add_argument("--keyword", action="append", default=[],
                    help="标题关键词（小写子串），可重复；留空则不过滤")
    ap.add_argument("--min-score", type=int, default=0)
    ap.add_argument("--top", type=int, default=12, help="最终保留几条")
    ap.add_argument("--pages", type=int, default=4,
                    help="每个子板最多翻几页（每页 100 帖），翻越多覆盖越全但越慢")
    ap.add_argument("--no-comments", action="store_true",
                    help="不抓热评补摘要（更快，但正文被删的帖子会显示空白）")
    ap.add_argument("--topic", default="Reddit · 热议")
    ap.add_argument("--out", default="",
                    help="输出路径，默认临时目录 reddit_report.json")
    args = ap.parse_args()

    kws = [k.lower() for k in args.keyword]
    out = args.out or default_out("reddit_report.json")
    items, cands, clusters = [], [], []
    n = 0

    for sub in args.sub:
        posts = fetch_sub(sub, args.after, args.before, pages=args.pages)
        print(f"{sub}: 抓到 {len(posts)} 帖")

        keep = []
        for p in posts:
            title = p.get("title") or ""
            if not title:
                continue
            if kws and not any(k in title.lower() for k in kws):
                continue
            if (p.get("score") or 0) < args.min_score:
                continue
            keep.append(p)

        keep.sort(key=lambda p: p.get("score") or 0, reverse=True)
        tag = SUB_TAG.get(sub, "reddit")
        print(f"{sub}: 过滤后 {len(keep)} 帖")

        for p in keep:
            iid = f"R{n:02d}"
            n += 1
            pts = p.get("score") or 0
            ncmt = p.get("num_comments") or 0
            items.append({
                "item_id": iid,
                "source": tag,
                "title": p["title"],
                "url": p.get("permalink") and
                       "https://www.reddit.com" + p["permalink"] or p.get("url"),
                "author": p.get("author") or "",
                "published_at": time.strftime(
                    "%Y-%m-%d", time.gmtime(p.get("created_utc") or 0)),
                "engagement": {"points": pts, "comments": ncmt},
                "image": thumb_of(p),
                "snippet": body_of(p),
                "pid": p.get("id") or "",
            })
            cands.append({
                "candidate_id": f"C{n:02d}",
                "item_id": iid,
                "source": tag,
                "title": p["title"],
                "final_score": float(pts),
            })
            clusters.append({
                "cluster_id": f"cl-{n}",
                "title": p["title"],
                "candidate_ids": [f"C{n:02d}"],
                "sources": [tag],
                "score": float(pts),
            })

    # 全局按分数截断，保证多个子板混合时也是高分优先
    if args.top and len(items) > args.top:
        ranked = sorted(range(len(items)), key=lambda i: items[i]["engagement"]["points"], reverse=True)
        keep_idx = set(ranked[:args.top])
        items = [items[i] for i in range(len(items)) if i in keep_idx]
        cands = [c for c in cands if c["item_id"] in {x["item_id"] for x in items}]
        clusters = [c for c in clusters
                    if set(c["candidate_ids"]) & {x["candidate_id"] for x in cands}]

    # 截断后补摘要：正文被删的帖子抓最高赞评论顶上
    if not args.no_comments:
        for it in items:
            if it.get("snippet"):
                continue
            txt = top_comment(it.pop("pid", ""))
            if txt:
                it["snippet"] = txt
                print(f"  + 评论摘要: {it['title'][:40]}")
            time.sleep(1.2)

    for it in items:
        it.pop("pid", None)

    report = {
        "topic": args.topic,
        "range_from": args.after,
        "range_to": args.before,
        "clusters": clusters,
        "ranked_candidates": cands,
        "items_by_source": {},
    }
    for it in items:
        report["items_by_source"].setdefault(it["source"], []).append(it)

    with open(out, "w", encoding="utf-8") as f:
        json.dump({"reports": [{"report": report}]}, f, ensure_ascii=False, indent=1)

    print(f"\n共 {len(items)} 条 → {out}")
    print(f"有缩略图: {sum(1 for i in items if i['image'])}/{len(items)}")


if __name__ == "__main__":
    main()
