"""把多份 report JSON 合并成一份，让 cardimg 一次性出图。

典型用法：把 last30days 的调研结果和 Reddit 存档抓取结果拼在一张图上，
这样 YouTube / HN / r/wallstreetbets / r/investing 四个来源同框。

  python merge_reports.py --report a.json --report b.json --out merged.json ^
      --topic "Anthropic IPO · 全网视角"

注意：各家分数口径不同（YouTube/HN 是引擎综合分，Reddit 是点赞数），
合并后只保证时间轴一致，徽章数字不可跨源比较。
"""
import argparse
import json

from common import default_out, load_report


def load(path, prefix):
    rep = load_report(path)

    items, cands, clusters = [], [], []

    for lst in (rep.get("items_by_source") or {}).values():
        for it in lst or []:
            it = dict(it)
            it["item_id"] = f"{prefix}{it.get('item_id')}"
            items.append(it)

    for c in rep.get("ranked_candidates") or []:
        c = dict(c)
        c["candidate_id"] = f"{prefix}{c.get('candidate_id')}"
        c["item_id"] = f"{prefix}{c.get('item_id')}"
        cands.append(c)

    for cl in rep.get("clusters") or []:
        cl = dict(cl)
        cl["cluster_id"] = f"{prefix}{cl.get('cluster_id')}"
        cl["candidate_ids"] = [f"{prefix}{x}" for x in cl.get("candidate_ids") or []]
        cl["representative_ids"] = [f"{prefix}{x}"
                                    for x in cl.get("representative_ids") or []]
        clusters.append(cl)

    return rep, items, cands, clusters


def normalize(clusters, cands, items):
    """各源分数口径不同（引擎综合分 / 点赞数 / 热度分），不能并排比较。

    在每个来源内部把分数折算成 0-100 的百分位热度，原始数值仍留在条目的
    engagement 里由卡片下方那行照常显示。返回改写后的 clusters/cands。
    """
    by_src = {}
    for c in cands:
        by_src.setdefault(c.get("source"), []).append(c)

    new_cand = {}
    for src, group in by_src.items():
        group.sort(key=lambda c: c.get("final_score") or 0, reverse=True)
        n = len(group)
        for i, c in enumerate(group):
            pct = 100.0 if n == 1 else 100.0 * (n - 1 - i) / (n - 1)
            new_cand[c["candidate_id"]] = round(pct, 1)

    for cl in clusters:
        vals = [new_cand[x] for x in cl.get("candidate_ids") or [] if x in new_cand]
        if vals:
            cl["score"] = max(vals)
    for c in cands:
        if c["candidate_id"] in new_cand:
            c["final_score"] = new_cand[c["candidate_id"]]
    return clusters, cands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="append", required=True)
    ap.add_argument("--out", default="", help="默认写到临时目录 merged.json")
    ap.add_argument("--topic", default="")
    ap.add_argument("--raw-scores", action="store_true",
                    help="保留各源原始分数（默认做百分位归一化，避免跨源误读）")
    args = ap.parse_args()
    if not args.out:
        args.out = default_out("merged.json")

    all_items, all_cands, all_clusters = [], [], []
    froms, tos = [], []

    for i, path in enumerate(args.report):
        rep, items, cands, clusters = load(path, f"m{i}_")
        all_items += items
        all_cands += cands
        all_clusters += clusters
        if rep.get("range_from"):
            froms.append(rep["range_from"])
        if rep.get("range_to"):
            tos.append(rep["range_to"])
        print(f"{path}: {len(items)} 条 / {len(clusters)} 簇")

    note = ""
    if not args.raw_scores:
        all_clusters, all_cands = normalize(all_clusters, all_cands, all_items)
        note = "徽章为各源内部百分位热度，跨源不可比；原始数值见每条下方"
        print("分数已按来源内部百分位归一化")

    by_src = {}
    for it in all_items:
        by_src.setdefault(it.get("source") or "unknown", []).append(it)

    report = {
        "topic": args.topic or "合并报告",
        "range_from": min(froms) if froms else "",
        "range_to": max(tos) if tos else "",
        "clusters": all_clusters,
        "ranked_candidates": all_cands,
        "items_by_source": by_src,
        "note": note,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump({"reports": [{"report": report}]}, f, ensure_ascii=False, indent=1)

    print(f"\n合并 {len(all_items)} 条 / {len(all_clusters)} 簇 → {args.out}")
    for k, v in sorted(by_src.items(), key=lambda kv: -len(kv[1])):
        print(f"  {k}: {len(v)}")


if __name__ == "__main__":
    main()
