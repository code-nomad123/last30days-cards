#!/usr/bin/env python3
"""把 last30days 报告渲染成 PNG 信息图。

纯 Pillow，无其他依赖。中文用系统微软雅黑。

用法：
    python cardimg.py <report.json> -o cards.png
    python cardimg.py <report.json> -o cards.png --top 8
    python cardimg.py <report.json> -o cards.png --top 8 --images
"""

from __future__ import annotations

import argparse
import hashlib
import html
import io
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from common import SOURCE_NAME as SRC_NAME
from common import build_opener, load_report, proxy_url

# ---------- 配色 ----------
BG = (255, 255, 255)
INK = (15, 23, 42)
INK_SOFT = (71, 85, 105)
MUTED = (148, 163, 184)
ACCENT = (37, 99, 235)
CARD_BG = (248, 250, 252)
CARD_LINE = (226, 232, 240)
BAND = (15, 23, 42)
BAND_DIM = (148, 163, 184)
BAND_TEXT = (248, 250, 252)

SRC_COLOR = {
    "YouTube": (220, 38, 38),
    "HN": (234, 88, 12),
    "GitHub": (22, 163, 74),
    "Reddit": (217, 70, 239),
    "r/wallstreetbets": (217, 70, 239),
    "r/investing": (147, 51, 234),
    "Poly": (14, 165, 233),
    "X": (15, 23, 42),
    "TikTok": (2, 6, 23),
}

W = 1400
PAD = 64
DATE_W = 128          # 左栏日期宽度
CJK = set("、。，．：；？！（）《》【】「」—…·　")

# 微软雅黑缺字形时渲染成方块，统一换成 ASCII 等价物
CHAR_FIX = {
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u00a0": " ", "\u2007": " ", "\u202f": " ",
    "\u200b": "", "\u200c": "", "\u200d": "", "\ufeff": "",
    "\u00ad": "-",
}


def clean_text(s: str) -> str:
    if not s:
        return ""
    # YouTube 字幕里常有 &gt;&gt;、&amp; 之类原始实体，先解码再处理字形
    s = html.unescape(s)
    out = []
    for ch in s:
        if ch in CHAR_FIX:
            out.append(CHAR_FIX[ch])
            continue
        cp = ord(ch)
        # 表情符号 / 变体选择符 / 零宽连接符：微软雅黑无字形，剔掉
        if (0x1F000 <= cp <= 0x1FAFF or 0x2600 <= cp <= 0x27BF
                or 0xFE00 <= cp <= 0xFE0F or 0x1F1E6 <= cp <= 0x1F1FF
                or cp in (0x20E3,)):
            continue
        out.append(ch)
    return "".join(out).strip()


def _font_dirs() -> list[Path]:
    """字体目录候选，按平台排。也可用 LAST30DAYS_CARDS_FONT_DIR 指自己的目录。"""
    dirs = []
    env = os.environ.get("LAST30DAYS_CARDS_FONT_DIR")
    if env:
        dirs.append(Path(env))
    dirs += [
        Path(r"C:\Windows\Fonts"),          # Windows
        Path("/System/Library/Fonts"),      # macOS
        Path("/Library/Fonts"),
        Path.home() / "Library/Fonts",
        Path("/usr/share/fonts"),           # Linux
        Path("/usr/local/share/fonts"),
    ]
    return [d for d in dirs if d.exists()]


# 各平台常见的中文字体名，按优先级排
FONT_CANDS = (
    "msyh.ttc", "msyhbd.ttc",                       # 微软雅黑（Windows）
    "PingFang.ttc", "Hiragino Sans GB.ttc",         # macOS
    "NotoSansCJK-Regular.ttc", "NotoSansCJKsc-Regular.otf",
    "wqy-microhei.ttc", "SourceHanSansSC-Regular.otf",  # Linux
    "simhei.ttf", "simsun.ttc", "Deng.ttf",         # Windows 备选
)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    """先试指定字体，再按 FONT_CANDS 逐个回退，全找不到用 Pillow 内置位图字体。"""
    for cand in (name, *FONT_CANDS):
        for d in _font_dirs():
            p = d / cand
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    continue
    return ImageFont.load_default()


def f_regular(size: int) -> ImageFont.FreeTypeFont:
    return font("msyh.ttc", size)


def f_bold(size: int) -> ImageFont.FreeTypeFont:
    return font("msyhbd.ttc", size)


def wrap_words(text: str, fnt: ImageFont.FreeTypeFont, max_w: int,
               max_lines: int = 0) -> list[str]:
    """折行：英文按词断，中文逐字断——不会把单词劈成两半。"""
    if not text:
        return []
    # 切成「词」：连续非空白非 CJK 的算一个词，CJK 单字算一个词
    tokens: list[str] = []
    buf = ""
    for ch in text:
        if ch.isspace():
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(" ")
        elif ch in CJK or ord(ch) > 0x2E80:
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        else:
            buf += ch
    if buf:
        tokens.append(buf)

    lines: list[str] = []
    cur = ""
    for tk in tokens:
        if tk == " " and not cur:
            continue
        trial = cur + tk
        if fnt.getlength(trial) <= max_w:
            cur = trial
        else:
            if cur.strip():
                lines.append(cur.rstrip())
                if max_lines and len(lines) >= max_lines:
                    break
            cur = "" if tk == " " else tk
    if cur.strip() and (not max_lines or len(lines) < max_lines):
        lines.append(cur.rstrip())

    if max_lines and len(lines) >= max_lines:
        joined = "".join(lines)
        if fnt.getlength(joined) < fnt.getlength(text) - fnt.getlength(lines[-1]) * 0.2:
            lines = lines[:max_lines]
            lines[-1] = lines[-1].rstrip()[:-1] + "…"
    return lines


def load_cards(path: Path, top: int, exclude: list[str] | None = None,
               min_score: float = 0.0) -> tuple[dict, list[dict]]:
    """读报告转卡片。

    exclude: 标题包含任一关键词就丢弃。上游 planner 偶尔会把搜索词里的
    "model" 这类泛词带偏，35 张卡里 22 张跑题时靠它挡一下。
    min_score: 分数下限，低于它的卡不画。
    """
    report = load_report(path)
    bad = [w.lower() for w in (exclude or []) if w.strip()]

    items = {}
    for lst in (report.get("items_by_source") or {}).values():
        for it in lst or []:
            items[it.get("item_id")] = it

    cards = []
    for cl in report.get("clusters") or []:
        ids = set(cl.get("candidate_ids") or [])
        members = [c for c in (report.get("ranked_candidates") or [])
                   if c.get("candidate_id") in ids]
        if not members:
            continue
        members.sort(key=lambda c: c.get("final_score") or 0, reverse=True)
        lead = members[0]
        it = items.get(lead.get("item_id")) or {}
        eng = it.get("engagement") or {}

        title = cl.get("title") or lead.get("title") or ""
        if bad and any(w in title.lower() for w in bad):
            continue
        score = cl.get("score") or 0
        if min_score and score < min_score:
            continue

        bits = []
        src_names = [SRC_NAME.get(s, s) for s in (cl.get("sources") or [])]
        is_reddit = any(n.startswith("r/") or n == "Reddit" for n in src_names)
        if eng.get("views"):
            bits.append(f"{eng['views']:,} 播放")
        if eng.get("likes"):
            bits.append(f"{eng['likes']:,} 赞")
        if eng.get("comments"):
            bits.append(f"{eng['comments']:,} 评")
        if eng.get("points"):
            # Reddit 的 points 是赞数，HN 是分数，叫法不能混
            bits.append(f"{eng['points']:,} {'赞' if is_reddit else '分'}")

        cards.append({
            "title": clean_text(title or "（无标题）"),
            "sources": cl.get("sources") or [],
            "score": round(cl.get("score") or 0, 1),
            "date": (it.get("published_at") or "")[:10],
            "meta": " · ".join(bits),
            "views": eng.get("views") or 0,
            "likes": eng.get("likes") or 0,
            "comments": eng.get("comments") or 0,
            "points": eng.get("points") or 0,
            "img_url": pick_image_url(it),
            "author": it.get("author") or "",
            "snippet": clean_text(it.get("snippet") or ""),
        })

    cards.sort(key=lambda c: c["score"], reverse=True)
    if top:
        cards = cards[:top]
    return report, cards


# ---------- 抓原始配图 ----------

YT_ID = re.compile(r"(?:v=|youtu\.be/|/shorts/|/embed/)([A-Za-z0-9_-]{11})")


def pick_image_url(item: dict) -> str:
    """从条目里找可用的原始配图地址。

    优先用条目自带的图片字段（若上游或外部脚本写入了 og:image），
    否则从 URL 反推：
    - YouTube：视频 ID → i.ytimg.com 缩略图（就是视频封面原图）
    - GitHub：作者 → 头像
    - 其余（HN / Reddit / Polymarket）没有可推导的图，返回空串
    """
    for key in ("image", "image_url", "og_image", "thumbnail"):
        val = item.get(key)
        if isinstance(val, str) and val.startswith("http"):
            return val

    src = (item.get("source") or "").lower()
    url = item.get("url") or ""

    if src == "youtube":
        m = YT_ID.search(url)
        if m:
            return f"https://i.ytimg.com/vi/{m.group(1)}/mqdefault.jpg"

    if src == "github":
        author = item.get("author") or ""
        if author and "/" not in author:
            return f"https://github.com/{author}.png?size=200"

    return ""


def _cache_dir() -> Path:
    d = Path.home() / ".cache" / "last30days-cards" / "img"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch_image(url: str, timeout: int = 15) -> Image.Image | None:
    """下载并缓存图片。失败返回 None，绝不抛异常。"""
    if not url:
        return None
    key = hashlib.sha256(url.encode()).hexdigest()[:20]
    cached = _cache_dir() / f"{key}.png"
    if cached.exists():
        try:
            return Image.open(cached).convert("RGB")
        except OSError:
            cached.unlink(missing_ok=True)

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with build_opener(proxy_url())(req, timeout=timeout) as r:
            blob = r.read()
        im = Image.open(io.BytesIO(blob)).convert("RGB")
        im.save(cached, "PNG")
        return im
    except Exception:
        return None


def fit_image(im: Image.Image, w: int, h: int) -> Image.Image:
    """等比缩放后居中裁剪到 w×h。"""
    scale = max(w / im.width, h / im.height)
    nw, nh = max(1, round(im.width * scale)), max(1, round(im.height * scale))
    im = im.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = (nh - h) // 2
    return im.crop((left, top, left + w, top + h))


def render(report: dict, cards: list[dict], out: Path, with_images: bool = False) -> None:
    f_title = f_bold(42)
    f_sub = f_regular(22)
    f_stat = f_bold(30)
    f_statl = f_regular(19)
    f_date = f_bold(21)
    f_card = f_bold(26)
    f_meta = f_regular(20)
    f_snip = f_regular(19)
    f_badge = f_bold(23)
    f_chip = f_bold(20)

    card_l = PAD + DATE_W
    card_r = W - PAD
    card_w = card_r - card_l
    text_w = card_w - 190  # 右侧留分数徽章（含内边距，防长标题压到徽章上）

    # 抓图（仅在 --images 时）
    thumbs: dict[int, Image.Image | None] = {}
    if with_images:
        for i, c in enumerate(cards):
            thumbs[i] = fetch_image(c.get("img_url") or "")
        got = sum(1 for v in thumbs.values() if v is not None)
        print(f"配图: {got}/{len(cards)} 张成功", file=sys.stderr)

    # 有图无图共用同一文字左边界，避免标题参差；纯文字模式不缩进
    THUMB_W, THUMB_H = 208, 117
    INDENT = (THUMB_W + 24) if with_images else 0

    # 预排版
    laid = []
    for i, c in enumerate(cards):
        has_img = thumbs.get(i) is not None
        tw = text_w - INDENT
        lines = wrap_words(c["title"], f_card, tw, max_lines=2)
        snip = wrap_words(c.get("snippet") or "", f_snip, tw, max_lines=2)
        h = 34 + len(lines) * 34 + (26 if c["meta"] else 0)
        if snip:
            h += len(snip) * 27 + 8
        floor = max(h, THUMB_H + 32) if has_img else max(h, 92)
        laid.append((c, lines, floor, snip))

    groups: dict[str, list[int]] = {}
    for i, tup in enumerate(laid):
        groups.setdefault(tup[0]["date"] or "未知", []).append(i)

    header_h = 216
    stats_h = 96
    H = header_h + stats_h + 40
    for dk in sorted(groups):
        for i in groups[dk]:
            H += laid[i][2] + 14
        H += 18
    H += 78

    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    # ---- 顶栏 ----
    d.rectangle([0, 0, W, header_h], fill=BAND)
    d.text((PAD, 44), report.get("topic", "调研"), font=f_title, fill=BAND_TEXT)
    rng = f"{report.get('range_from','')} ~ {report.get('range_to','')}"
    d.text((PAD, 104), f"{rng}　·　{len(cards)} 条线索", font=f_sub, fill=BAND_DIM)

    # 来源徽章（转标准名 + 配色）
    cnt: dict[str, int] = {}
    for c in cards:
        for s in c["sources"]:
            nm = SRC_NAME.get(s, s)
            cnt[nm] = cnt.get(nm, 0) + 1
    x = PAD
    for nm, n in sorted(cnt.items(), key=lambda kv: -kv[1]):
        label = f"{nm} {n}"
        tw = f_chip.getlength(label)
        d.rounded_rectangle([x, 150, x + tw + 26, 150 + 36], 18,
                            fill=SRC_COLOR.get(nm, MUTED))
        d.text((x + 13, 157), label, font=f_chip, fill=(255, 255, 255))
        x += tw + 36

    # ---- 数据带：四个硬指标 ----
    total_views = sum(c["views"] for c in cards)
    total_likes = sum(c["likes"] for c in cards)
    total_cmt = sum(c["comments"] for c in cards)
    total_pts = sum(c["points"] for c in cards)

    stats = []
    if total_views:
        stats.append((f"{total_views:,}", "总播放"))
    if total_likes:
        stats.append((f"{total_likes:,}", "总点赞"))
    if total_pts:
        has_hn = any(SRC_NAME.get(s) == "HN" for c in cards for s in c["sources"])
        stats.append((f"{total_pts:,}", "HN 总分" if has_hn else "总分"))
    if total_cmt:
        stats.append((f"{total_cmt:,}", "评论"))
    stats.append((f"{len(groups)}", "活跃日"))

    sy = header_h + 8
    d.line([PAD, sy, W - PAD, sy], fill=CARD_LINE, width=2)

    # 按内容实际宽度均分并整体居中，避免剩几项时右侧留大片空白
    GAP = 96
    widths = [max(f_stat.getlength(num), f_statl.getlength(label))
              for num, label in stats]
    total = sum(widths) + GAP * (len(stats) - 1)
    cx = (W - total) // 2
    for i, (num, label) in enumerate(stats):
        d.text((cx, sy + 14), num, font=f_stat, fill=INK)
        d.text((cx, sy + 52), label, font=f_statl, fill=MUTED)
        cx += widths[i]
        if i < len(stats) - 1:
            d.line([cx + GAP // 2, sy + 16, cx + GAP // 2, sy + 76],
                   fill=CARD_LINE, width=2)
            cx += GAP
    d.line([PAD, sy + stats_h - 8, W - PAD, sy + stats_h - 8], fill=CARD_LINE, width=2)

    # ---- 时间轴主体 ----
    y = header_h + stats_h + 32
    year_shown = ""
    for dk in sorted(groups):
        idxs = groups[dk]
        yr, md = dk[:4], dk[5:]
        d.text((PAD, y + 6), md, font=f_date, fill=ACCENT)
        if yr and yr != year_shown:   # 只在跨年时标一次年份
            d.text((PAD, y + 32), yr, font=f_meta, fill=MUTED)
            year_shown = yr
        if len(idxs) > 1:
            d.text((PAD, y + (58 if yr == year_shown else 32)),
                   f"{len(idxs)} 条", font=f_meta, fill=MUTED)

        for i in idxs:
            c, lines, ch, snip = laid[i]

            # 时间轴竖线 + 节点
            d.line([PAD + DATE_W - 14, y - 4, PAD + DATE_W - 14, y + ch + 6],
                   fill=CARD_LINE, width=2)
            d.ellipse([PAD + DATE_W - 20, y + 20, PAD + DATE_W - 8, y + 32],
                      fill=ACCENT)

            d.rounded_rectangle([card_l, y, card_r, y + ch], 14,
                                fill=CARD_BG, outline=CARD_LINE)
            # 来源色条
            if c["sources"]:
                nc = SRC_COLOR.get(SRC_NAME.get(c["sources"][0], ""), MUTED)
                d.rounded_rectangle([card_l, y + 1, card_l + 5, y + ch - 1], 3, fill=nc)

            tx = card_l + 26 + INDENT
            ty = y + 17
            thumb = thumbs.get(i)
            if thumb is not None:
                # 封面贴左侧，文字右移
                img.paste(fit_image(thumb, THUMB_W, THUMB_H),
                          (card_l + 26, y + (ch - THUMB_H) // 2))
                body_h = (len(lines) * 34 + (26 if c["meta"] else 0)
                          + (len(snip) * 27 + 8 if snip else 0))
                ty = y + max(17, (ch - body_h) // 2)
            for ln in lines:
                d.text((tx, ty), ln, font=f_card, fill=INK)
                ty += 34
            if snip:
                ty += 2
                for ln in snip:
                    d.text((tx, ty), ln, font=f_snip, fill=INK_SOFT)
                    ty += 27
            if c["meta"]:
                d.text((tx, ty + 4), c["meta"], font=f_meta, fill=INK_SOFT)

            # 分数徽章
            badge = f"{c['score']}"
            bw = f_badge.getlength(badge) + 26
            d.rounded_rectangle([card_r - bw - 20, y + 18, card_r - 20, y + 60],
                                21, fill=ACCENT)
            d.text((card_r - bw - 20 + 13, y + 25), badge, font=f_badge,
                   fill=(255, 255, 255))

            y += ch + 14
        y += 18

    # ---- 页脚 ----
    if with_images:
        note = "文字数据来自 last30days 缓存报告；配图为原文封面，本次联网抓取"
    else:
        note = "数据来自 last30days 缓存报告，未重新联网"
    d.line([PAD, H - 56, W - PAD, H - 56], fill=CARD_LINE, width=2)
    d.text((PAD, H - 42), f"last30days-cards　·　{note}",
           font=f_meta, fill=MUTED)

    img.save(out, "PNG", optimize=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="把 last30days 报告渲染成 PNG")
    ap.add_argument("report", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("cards.png"))
    ap.add_argument("--top", type=int, default=0)
    ap.add_argument("--images", action="store_true",
                    help="抓取原文配图（YouTube 封面 / GitHub 头像）并嵌入卡片")
    ap.add_argument("--exclude", action="append", default=[],
                    help="标题含该关键词就丢弃，可重复传多个；挡上游 planner 跑题的卡")
    ap.add_argument("--min-score", type=float, default=0.0,
                    help="分数下限，低于它的卡不画")
    args = ap.parse_args()

    if not args.report.exists():
        print(f"报告不存在: {args.report}", file=sys.stderr)
        return 1
    try:
        report, cards = load_cards(args.report, args.top,
                                   exclude=args.exclude,
                                   min_score=args.min_score)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"解析失败: {e}", file=sys.stderr)
        return 1
    if not cards:
        print("没有可渲染的卡片", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    render(report, cards, args.out, with_images=args.images)
    print(f"已生成: {args.out} ({args.out.stat().st_size:,} 字节)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
