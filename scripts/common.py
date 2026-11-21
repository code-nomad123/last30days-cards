"""last30days-cards 的共享工具：报告读取、来源名映射、代理与输出路径。

cards.py / cardimg.py / merge_reports.py 原先各自实现了一份读报告的代码，
改一处忘两处。现在统一从这里取。
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# 来源 key → 显示名。出文字和出图必须共用这张表，
# 否则同一份报告在终端叫 "Hacker News"、在图上叫 "HN"，用户会以为数据不同。
SOURCE_NAME = {
    "youtube": "YouTube",
    "hackernews": "HN",
    "hacker_news_custom": "HN",
    "reddit": "Reddit",
    "reddit_wsb": "r/wallstreetbets",
    "reddit_inv": "r/investing",
    "github": "GitHub",
    "polymarket": "Poly",
    "x": "X",
    "tiktok": "TikTok",
}


def source_name(key: str) -> str:
    """未登记的来源原样返回——宁可显示丑名字，也不要丢来源信息。"""
    return SOURCE_NAME.get(key, key)


def load_report(path: str | Path) -> dict:
    """接受两种形态：last-report.json（含 reports[]）或 --emit=json 的裸 report。

    用 utf-8-sig 读取：Windows 下带 BOM 的 JSON 会让 json.loads 直接抛
    "Unexpected UTF-8 BOM"。
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if raw.get("reports"):
        return raw["reports"][0]["report"]
    return raw


def default_out(filename: str) -> str:
    """默认输出路径放临时目录，不写死用户名——换台机器照样能跑。"""
    return str(Path(tempfile.gettempdir()) / filename)


def proxy_url() -> str:
    """代理地址，依次读 LAST30DAYS_CARDS_PROXY / HTTPS_PROXY / HTTP_PROXY。

    都没设就返回空串走直连：HN Algolia 与 GitHub 直连可用，
    但 YouTube 封面和 Reddit 缩略图必须走代理。
    """
    for key in ("LAST30DAYS_CARDS_PROXY", "HTTPS_PROXY", "HTTP_PROXY"):
        val = os.environ.get(key)
        if val:
            return val
    return ""


def build_opener(proxy: str = ""):
    """返回一个可调用对象，签名同 urllib.request.urlopen(req, timeout=...)。

    有代理就套 ProxyHandler，没代理走系统默认。返回可调用对象而不是
    OpenerDirector：调用方写 `build_opener(p)(req, timeout=10)` 两种路径一致。
    """
    import urllib.request

    if proxy:
        op = urllib.request.build_opener(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
        return op.open
    return urllib.request.urlopen
