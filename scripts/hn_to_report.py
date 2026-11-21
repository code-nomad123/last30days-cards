"""把 HN 指定时间窗内的热门故事转成 cardimg 能吃的 report 结构，并抓 og:image。

  python hn_to_report.py --days 7 --min-points 700 --top 12
  python hn_to_report.py --days 30 --min-points 300 --top 20 --out hn.json

窗口、分数门槛、条数、代理全部可配，不再写死。
HN Algolia 直连可用，默认不套代理；代理只影响抓 og:image 那一步。
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request

from common import build_opener, default_out, proxy_url

HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get_json(opener, url, timeout=25):
    with opener(urllib.request.Request(url, headers=HDRS), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def get_og_image(opener, url, timeout=10):
    """抓页面头部的 og:image / twitter:image。失败返回空串。"""
    if not url:
        return ""
    try:
        req = urllib.request.Request(url, headers=HDRS)
        with opener(req, timeout=timeout) as r:
            head = r.read(300_000).decode("utf-8", "ignore")
    except Exception:
        return ""
    m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        head, re.I)
    if not m:
        m = re.search(
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            head, re.I)
    if not m:
        m = re.search(
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            head, re.I)
    if not m:
        return ""
    img = m.group(1).strip()
    if img.startswith("//"):
        img = "https:" + img
    elif img.startswith("/"):
        img = urllib.parse.urljoin(url, img)
    return img if img.startswith("http") else ""


def main():
    ap = argparse.ArgumentParser(description="HN 热门 → cardimg 报告 JSON")
    ap.add_argument("--days", type=int, default=7, help="回看天数，默认 7")
    ap.add_argument("--min-points", type=int, default=700, help="分数下限，默认 700")
    ap.add_argument("--top", type=int, default=12, help="取前几条，默认 12")
    ap.add_argument("--topic", default="", help="报告标题，默认自动生成")
    ap.add_argument("--out", default="", help="输出路径，默认临时目录 hn_report.json")
    ap.add_argument("--no-images", action="store_true", help="跳过 og:image 抓取（快很多）")
    ap.add_argument("--proxy", default="", help="代理地址，默认读环境变量，空则直连")
    args = ap.parse_args()

    out = args.out or default_out("hn_report.json")
    proxy = args.proxy or proxy_url()
    opener = build_opener(proxy)

    now = int(time.time())
    since = now - args.days * 86400

    u = ("https://hn.algolia.com/api/v1/search?"
         + urllib.parse.urlencode({
             "tags": "story",
             "numericFilters": f"created_at_i>{since},points>{args.min_points}",
             "hitsPerPage": max(args.top * 3, 30),
         }))
    hits = [h for h in get_json(opener, u)["hits"] if h.get("title")]
    hits.sort(key=lambda h: h.get("points") or 0, reverse=True)
    hits = hits[:args.top]

    if not hits:
        print(f"没有满足 points>{args.min_points} 的故事，调低 --min-points 试试",
              file=sys.stderr)
        return 2

    items, cands, clusters = [], [], []
    for i, h in enumerate(hits):
        oid = h["objectID"]
        target = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"
        img = "" if args.no_images else get_og_image(opener, h.get("url") or "")
        pts = h.get("points") or 0
        ncmt = h.get("num_comments") or 0

        items.append({
            "item_id": f"HN{i:02d}",
            "source": "hacker_news_custom",
            "title": h["title"],
            "url": target,
            "author": h.get("author") or "",
            "published_at": time.strftime("%Y-%m-%d", time.localtime(h["created_at_i"])),
            "engagement": {"points": pts, "comments": ncmt},
            "image": img,
        })
        cands.append({
            "candidate_id": f"C{i:02d}",
            "item_id": f"HN{i:02d}",
            "source": "hacker_news_custom",
            "title": h["title"],
            "final_score": float(pts),
        })
        clusters.append({
            "cluster_id": f"cl-{i}",
            "title": h["title"],
            "candidate_ids": [f"C{i:02d}"],
            "sources": ["hacker_news_custom"],
            "score": float(pts),
        })
        print(f"  {pts:5}分 {ncmt:5}评  {'IMG' if img else '   '}  {h['title'][:60]}")

    report = {
        "topic": args.topic or f"Hacker News · 近 {args.days} 天热门",
        "range_from": time.strftime("%Y-%m-%d", time.localtime(since)),
        "range_to": time.strftime("%Y-%m-%d", time.localtime(now)),
        "clusters": clusters,
        "ranked_candidates": cands,
        "items_by_source": {"hacker_news_custom": items},
    }

    with open(out, "w", encoding="utf-8") as f:
        json.dump({"reports": [{"report": report}]}, f, ensure_ascii=False, indent=1)
    print(f"\n写出 {out}")
    print(f"抓到 og:image 的条数: {sum(1 for it in items if it['image'])}/{len(items)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
