# last30days-cards

把 [last30days](https://github.com/mvanhorn/last30days-skill) 的调研报告，重新排版成能扫完的卡片或 PNG 长图。

![样例输出](docs/sample.png)

*上图由 `cardimg.py --top 5 --images` 从一份真实的 last30days 报告渲染而成，配图为视频原文封面。*

---

## 1. 解决什么问题

跑完一次 last30days 调研，你会得到一个 `last-report.json`，里面是几十个语义簇、几十个候选、上万字的视频字幕和评论区摘录。`--emit=compact` 把它压到约 8KB，但那仍然是**给模型读的证据信封**——徽章、簇、互动量、引述全都在，信息密度极高，人要顺着扫一遍很累，也没法直接发给别人。

这个项目只做一件事：**换个排版**。

三条硬约束，决定了它能安全地插在 last30days 后面：

| 约束 | 含义 |
|---|---|
| 不联网调研 | 只读已有报告 JSON，0.1 秒出文字、0.5 秒出图 |
| 不改 last30days | 独立脚本，last30days 升级时不会冲突 |
| 不生成内容 | 数字全部从报告里算出来，配图是原文封面原图，没有一个字是编的 |

它是个**报告渲染器**，last30days 只是它的数据源之一——任何能拼成同样结构的 JSON 都能出图。

> **上游项目**：[last30days](https://github.com/mvanhorn/last30days-skill) — 作者 [Matt Van Horn (@mvanhorn)](https://github.com/mvanhorn)，MIT 许可。
> 本项目基于它的输出格式开发，与上游**无隶属关系，也未获其背书**。详细归属见文末「[上游归属](#上游归属)」。

## 2. 主要功能

### 四种文字风格

| 风格 | 回答的问题 | 形态 |
|---|---|---|
| `news` | 这段时间发生了什么？ | 标题 + 时间范围 + 来源分布 + 导语 + 按日期铺开的时间轴 |
| `rundown` | 哪几条值得点开？ | 每卡：标题、来源互动、摘要、关键引述、链接 |
| `table` | 全貌长什么样？ | 五列表格，一屏十行 |
| `plain` | 最省 token 的形态 | 只有得分、标题、链接 |

### PNG 信息图

1400px 宽的彩色长图，自上而下：深色头（话题 + 日期范围 + 来源徽章）→ 数据带（总播放 / 总点赞 / 总分 / 评论 / 活跃日）→ 时间轴（左栏日期、中间节点、右侧卡片）→ 页脚标注数据来源。

- `--images` 嵌入**原文配图**（YouTube 视频封面、GitHub 头像、Reddit 图片贴缩略图），不是重新画的插图
- `--exclude` / `--min-score` 两个机械闸门，挡掉上游 planner 跑题的卡
- 中文字体按平台自动回退（Windows 微软雅黑 / macOS 苹方 / Linux Noto），可用 `LAST30DAYS_CARDS_FONT_DIR` 指自己的

### 多源合并

`merge_reports.py` 把多份报告拼成一份。**关键设计：按来源分组做百分位归一化**——因为引擎综合分（几十到一百）、Reddit 点赞数（几千）、HN 分数（几百）根本不是同一个量纲，直接并排会让人以为 5079 点赞比 61.8 综合分重要 80 倍。归一化后各排各的，原始数值仍显示在每条卡片下方。

### 两个现成数据源适配器

| 脚本 | 数据源 | 说明 |
|---|---|---|
| `hn_to_report.py` | Hacker News Algolia API | 窗口、分数门槛、条数、代理全可配 |
| `reddit_to_report.py` | Arctic Shift 存档 API | Reddit 官方 JSON/API 常不可达，改走存档；带限流退避 |

## 3. 安装方法

需要 **Python 3.10+**。

```bash
git clone https://github.com/code-nomad123/last30days-cards.git
cd last30days-cards
```

出图需要 Pillow，纯文字模式不需要：

```bash
pip install -r requirements.txt
# 等价于 pip install pillow
```

装成 Agent 技能（可选，装完 Agent 会自动识别 `SKILL.md`）：

```bash
# DeepSeek Harness
cp -r last30days-cards ~/.dsh/skills/
# Claude Code
cp -r last30days-cards ~/.claude/skills/
```

> 六个 `.py` 必须放在同一个 `scripts/` 目录下——它们通过 `common.py` 共享代码，不需要装成包，也不能拆开。

## 4. 使用方法

### 前置：先有一份报告

```bash
# 用 last30days 跑一次调研，报告会落到：
#   Linux/macOS: ~/.config/last30days/last-report.json
#   Windows:     %USERPROFILE%\.config\last30days\last-report.json
```

或者用任意符合下方「输入格式」的 JSON。

### 文字输出

```bash
python scripts/cards.py <report.json> --style news    --top 10
python scripts/cards.py <report.json> --style rundown --top 8
python scripts/cards.py <report.json> --style table   --top 10
python scripts/cards.py <report.json> --style plain
python scripts/cards.py <report.json> --json
```

| 参数 | 取值 | 说明 |
|---|---|---|
| `--style` | `rundown`（默认）/ `news` / `table` / `plain` | 四种风格 |
| `--top N` | 整数，默认 `0` | 只显示前 N 张卡，0 = 全部 |
| `--source` | 见下方别名表 | 只保留某来源 |
| `--json` | 开关 | 输出卡片字典数组，供二次加工 |

### PNG 出图

```bash
python scripts/cardimg.py <report.json> -o cards.png --top 8
python scripts/cardimg.py <report.json> -o cards.png --top 8 --images
python scripts/cardimg.py <report.json> -o clean.png --exclude "Kimi" --exclude "Qwen"
python scripts/cardimg.py <report.json> -o clean.png --min-score 50
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `-o/--out` | `cards.png` | 输出路径 |
| `--top N` | `0`（全部） | 只渲前 N 条 |
| `--images` | 关 | 抓原文配图嵌入卡片 |
| `--exclude KW` | 无 | 标题含该关键词就丢弃，可重复传 |
| `--min-score N` | `0` | 分数下限，低于它的卡不画 |

### 来源过滤别名

报告里的来源 key 各不相同（`hackernews` / `hacker_news_custom` / `reddit_wsb`），`--source` 传人话即可：

| 传这个 | 命中这些 |
|---|---|
| `hackernews` / `hn` | `hackernews`, `hacker_news_custom` |
| `reddit` | `reddit`, `reddit_wsb`, `reddit_inv` |
| `poly` / `polymarket` | `polymarket` |
| 其他 | 原样匹配 |

### 代理配置（抓配图时）

YouTube 封面和 Reddit 缩略图在很多网络环境下需要代理。按以下顺序读取，都没设就走直连：

```bash
export LAST30DAYS_CARDS_PROXY=http://127.0.0.1:7897   # 优先级最高
export HTTPS_PROXY=http://127.0.0.1:7897
export HTTP_PROXY=http://127.0.0.1:7897
```

没配代理时图片静默失败——卡片退回纯文字，**不报错不中断**。图片缓存在 `~/.cache/last30days-cards/img`（SHA256 前 20 位命名），二次渲染直接命中缓存。

### 多源合并

```bash
python scripts/merge_reports.py \
  --report ~/.config/last30days/last-report.json \
  --report /tmp/reddit_report.json \
  --out /tmp/merged.json --topic "Anthropic IPO · 全网视角"
```

| 参数 | 说明 |
|---|---|
| `--report PATH` | 可重复，传几份就合几份 |
| `--out PATH` | 默认写临时目录 `merged.json` |
| `--topic` | 合并后的话题名 |
| `--raw-scores` | 跳过归一化，保留各源原始分数（此时只能看单一来源） |

### HN 数据源

```bash
python scripts/hn_to_report.py --days 7 --min-points 700 --top 12
python scripts/hn_to_report.py --days 30 --min-points 300 --top 20 --out hn.json
```

| 参数 | 默认 | 说明 |
|---|---|---|
| `--days` | `7` | 回看天数 |
| `--min-points` | `700` | 分数下限 |
| `--top` | `12` | 取前几条 |
| `--topic` | 自动 | 报告标题 |
| `--out` | 临时目录 `hn_report.json` | 输出路径 |
| `--no-images` | 关 | 跳过 og:image 抓取，快很多 |
| `--proxy` | 读环境变量 | 代理地址，空则直连 |

### Reddit 数据源

```bash
python scripts/reddit_to_report.py --sub wallstreetbets --sub investing \
  --after 2026-11-13 --before 2026-11-21 \
  --keyword anthropic --keyword ipo --top 22 --pages 8
```

| 参数 | 说明 |
|---|---|
| `--sub NAME` | 必填，可重复传多个子板 |
| `--after` / `--before` | 必填，`YYYY-MM-DD`。**必须带时间范围**，否则 API 报 422 |
| `--keyword KW` | 可重复，标题小写子串匹配；留空则不过滤 |
| `--min-score` / `--top` / `--pages` | 分数下限 / 最终条数 / 每板翻几页（每页 100 帖） |
| `--no-comments` | 不抓热评补摘要（更快，但正文被删的帖会空白） |
| `--topic` / `--out` | 话题名 / 输出路径（默认临时目录） |

> **422 是限流不是参数错**，脚本会自动退避重试。分数与评论数来自存档，可能滞后于 Reddit 实时页面。

### 退出码

所有脚本统一：`0` 成功，`1` 文件不存在或解析失败，`2` 过滤后无内容。

## 5. 输入输出示例

### 输入格式

`cardimg.py` 与 `cards.py` 只认一种结构。任何来源只要能拼出来就能出图：

```json
{
  "reports": [{
    "report": {
      "topic": "我的话题",
      "range_from": "2026-11-13",
      "range_to": "2026-11-21",
      "clusters": [
        {
          "cluster_id": "c1",
          "title": "Hello 卡片",
          "candidate_ids": ["C0"],
          "sources": ["custom"],
          "score": 88.0
        }
      ],
      "ranked_candidates": [
        {
          "candidate_id": "C0",
          "item_id": "I0",
          "source": "custom",
          "title": "Hello 卡片",
          "final_score": 88.0
        }
      ],
      "items_by_source": {
        "custom": [
          {
            "item_id": "I0",
            "source": "custom",
            "title": "Hello 卡片",
            "url": "https://example.com",
            "author": "me",
            "published_at": "2026-11-20",
            "engagement": {"points": 42, "comments": 7},
            "snippet": "一两句摘要",
            "image": "https://.../cover.jpg"
          }
        ]
      }
    }
  }]
}
```

必填字段只有 `clusters[].title` / `clusters[].candidate_ids` / `ranked_candidates[].candidate_id` / `ranked_candidates[].item_id` / `items_by_source`。`engagement` 可含 `views` / `likes` / `comments` / `points`，`image` 有值就直接当封面用（优先于 URL 反推）。也接受不带 `reports[]` 包裹的裸 report（`last30days --emit=json` 的输出）。

`source` 不在内置映射表里也能跑，只是徽章显示原始名、配色退回灰色。要固定名字和颜色，加进 `common.SOURCE_NAME` 与 `cardimg.SRC_COLOR`。

### 输出示例：`--style rundown`

真实输出（一份 7 天窗口的报告，`--top 2`）：

```
**TL;DR:** fed rate cut inflation outlook · 2 张卡 · 2026-11-14 ~ 2026-11-21

**1. Darius Dale: 2027 Should Be a "Great Year for Bitcoin" as Fed Rate Cuts Come**
YouTube · 14,828 播放 · 227 赞 · 20 评 · 2026-11-19
Well, with the December Fed rate hike priced in as signs of disinflation build, is the Fed making a policy mistake? And what does it mean for Bitcoin? Joining us now is Darius Dale…
  「You know, how how much do you see inflation and global liquidity throughout 2027 hinging on what happens there…」
  「The 10-year yield is back up above 5% and when you last joined us in October, we talked about a possi…」
https://www.youtube.com/watch?v=GVYglll7Wgs

**2. Fed Governor Waller: Need to get a little more aggressive in our rate hikes to tame inflation**
YouTube · 28,665 播放 · 154 赞 · 92 评 · 2026-11-18
Morning. I'm here in Washington, D.C. on on really a beautiful fall morning with Fed Governor Chris Waller. Governor Waller, thanks for joining us. Well, thanks for having…
  「Well, I gave a speech last week and I said we need to consider a 50 basis point hike if CPI inflation…」
  「@snoopcow: The only way to push inflation down to 2% target is to manufacture a recession.」
https://www.youtube.com/watch?v=SuzARBoNncQ
```

### 输出示例：`--style news`

标题里的天数**从报告的真实窗口算出来**，不是写死的：

```
# fed rate cut inflation outlook · 7 天事件综述

**时间范围：** 2026-11-14 ~ 2026-11-21　**共 4 条线索**
**来源分布：** YouTube 4

## 概况
这段时间里声量最高的是「Darius Dale: 2027 Should Be a "Great Year for Bitcoin" as Fed Rate Cuts Come」（14,828 播放 · 227 赞 · 20 评，得分 61.8）。
最密集的一天是 2026-11-18，一天内冒出 2 条线索：「Fed Governor Waller: Need to g…」、「Putin and Xi Close Ranks Ahead…」。

## 时间轴

**2026-11-18**　2 条
- **Fed Governor Waller: Need to get a little more aggressive in our rate hikes to tame inflation**　28,665 播放 · 154 赞 · 92 评
  Morning. I'm here in Washington, D.C. on on really a beautiful fall morning with Fed Governor Chris…
- **Putin and Xi Close Ranks Ahead of High-Stakes Trump Summit?**　13,729 播放 · 74 赞 · 7 评
  NVIDIA HAS DECIDED TO START A NATIONAL SECURITY EXPORT CONTROL OVERSIGHT COMMITTEE. HAVE YO…

**2026-11-19**　1 条
- **Darius Dale: 2027 Should Be a "Great Year for Bitcoin" as Fed Rate Cuts Come**　14,828 播放 · 227 赞 · 20 评
  Well, with the December Fed rate hike priced in as signs of disinflation build, is the Fed making a…
```

### 输出示例：`--style table`

```
| # | 标题 | 来源 | 互动 | 得分 |
|---|---|---|---|---|
| 1 | Darius Dale: 2027 Should Be a “Great Year for Bitcoin” as Fe | YouTube | 14,828 播放 · 227 赞 · 20 评 | 61.8 |
| 2 | Fed Governor Waller: Need to get a little more aggressive in | YouTube | 28,665 播放 · 154 赞 · 92 评 | 55.7 |
| 3 | Putin and Xi Close Ranks Ahead of High-Stakes Trump Summit? | YouTube | 13,729 播放 · 74 赞 · 7 评 | 53.8 |
```

### 输出示例：`--style plain`

```
[61.8] Darius Dale: 2027 Should Be a “Great Year for Bitcoin” as Fed Rate Cuts Come (YouTube)
  14,828 播放 · 227 赞 · 20 评
  https://www.youtube.com/watch?v=GVYglll7Wgs
[55.7] Fed Governor Waller: Need to get a little more aggressive in our rate hikes to tame inflation (YouTube)
  28,665 播放 · 154 赞 · 92 评
  https://www.youtube.com/watch?v=SuzARBoNncQ
```

### 输出示例：`--json`

```json
[
  {
    "title": "Darius Dale: 2027 Should Be a “Great Year for Bitcoin” as Fed Rate Cuts Come",
    "sources": ["YouTube"],
    "score": 61.8,
    "url": "https://www.youtube.com/watch?v=GVYglll7Wgs",
    "author": "Bitcoin Magazine",
    "published": "2026-11-19",
    "engagement": "14,828 播放 · 227 赞 · 20 评",
    "snippet": "Well, with the December Fed rate hike priced in as signs of disinflation build, is the Fed making a policy mistake? …",
    "why": "",
    "evidence": [
      "You know, how how much do you see inflation and global liquidity throughout 2027 hinging on what happens there…",
      "The 10-year yield is back up above 5% and when you last joined us in October, we talked about a possi…"
    ],
    "member_count": 1
  }
]
```

### 输出示例：PNG

| 命令 | 实测尺寸 | 文件大小 | 耗时 |
|---|---|---|---|
| `--top 8` | 1400 × 2014 | 269 KB | 0.45 s |
| 不传 `--top`（全量 11 条） | 1400 × 2576 | 382 KB | 0.6 s |
| `--top 8 --images` | 1400 × 2116 | 604 KB | 0.50 s（图片缓存已热） |

纯文字 `--style rundown` 约 0.11 秒。首次抓配图会慢一些（每张图一次网络请求）。

## 项目结构

```
last30days-cards/
├── SKILL.md                 # Agent 技能说明（自动识别用）
├── README.md
├── LICENSE                  # MIT
├── requirements.txt         # 只有 pillow
├── docs/sample.png          # README 里的样例图
└── scripts/
    ├── common.py            # 共享件：来源名映射、报告读取、代理、默认输出路径
    ├── cards.py             # 四种文字风格 + 来源别名过滤
    ├── cardimg.py           # PNG 渲染 + 原文配图 + 相关性过滤
    ├── merge_reports.py     # 多报告合并 + 跨源百分位归一化
    ├── hn_to_report.py      # HN Algolia → 报告结构
    └── reddit_to_report.py  # Reddit 存档 → 报告结构
```

读报告、来源名映射、代理、默认输出路径**只有 `common.py` 一份实现**，改那里，不在各脚本里重复写。

## 原文配图能力

| 来源 | 能否拿到图 | 依据 |
|---|---|---|
| YouTube | ✅ 封面原图 | 视频 ID → `i.ytimg.com/vi/<id>/mqdefault.jpg` |
| GitHub | ✅ 作者头像 | `github.com/<author>.png?size=200` |
| 条目带 `image` 字段 | ✅ 直接用 | 优先于 URL 反推 |
| Reddit | ✅ 图片贴 | 存档 API 的 `thumbnail`；self 贴无图 |
| Hacker News | ⚠️ 看情况 | 需先抓 `og:image` 写进条目 |
| Polymarket | ❌ 无 | 条目没有配图概念 |

**last30days 的报告里没有图片字段**——逐键扫过 539KB，不含 `thumbnail` / `image` / `cover` 任何键。所以图是从 URL 反推的。

## 局限

- 只做**重排**，不判断内容质量。上游漏掉的源（Reddit 403、X 未启用）它补不了。
- 卡片来自 `clusters`（语义聚类），簇为空时无卡片（退出码 2）。
- `--source` 在已聚类结果上筛，可能出现"某源 0 张卡"，不代表该源这次没数据。
- 默认不做相关性甄别，只有 `--exclude` / `--min-score` 两个机械闸门。**这是止血不是治病**——干净结果还得回到 last30days 收紧 `--plan` 的 subquery。
- 跨源百分位只说明"在它自己那个来源里最热"，来源之间没有可比性。

## 上游归属

本项目是 [last30days](https://github.com/mvanhorn/last30days-skill) 的**伴生工具**，基于它产出的报告格式开发。

| 项目 | 信息 |
|---|---|
| 上游名称 | last30days（AI agent skill） |
| 上游仓库 | https://github.com/mvanhorn/last30days-skill |
| 上游作者 | Matt Van Horn（[@mvanhorn](https://github.com/mvanhorn)） |
| 上游许可 | MIT License |
| 上游版权 | Copyright (c) 2026 Matt Van Horn |
| 上游版本 | 本项目开发与测试所依据的版本为 v4.3.2 |

### 代码独立性说明

**本项目不包含、不复制、不修改上游的任何源代码。** 已核验：

- 六个脚本的 `import` 只有 Python 标准库（`json`、`urllib`、`argparse`、`pathlib`、`tempfile` 等）与 `Pillow`，无一处 `import` 上游模块
- 全仓库无一处引用 `last30days.py`、`scripts/lib/`、`render.py` 等上游路径
- 上游的渲染能力位于 `scripts/lib/render.py`（约 5,600 行、130 个函数），属于纯文本/HTML 输出；本项目是位图渲染器，二者无代码交集

因此本项目**不是上游的衍生作品（derivative work）**，MIT 许可的传染性条款不适用。上游归属在此声明，是因为：

1. 数据格式约定来源于上游（读取 `last-report.json` 的 `reports[0].report` 结构）
2. 使用者需要知道数据从哪来
3. 尊重上游作者的劳动

### 关于 MIT 许可中的版权声明保留义务

上游 MIT 许可证要求「上述版权声明和本许可声明应包含在本软件的所有副本或主要部分中」。由于本项目未复制上游代码，该义务在**法律上不适用**。本 README 仍完整记录上游版权信息，属于自愿的学术性致谢，不为规避任何法律要求。

若你**确实复制了上游的代码片段**到自己修改的版本中，则必须同时保留上游的 MIT 版权声明——最简单的做法是保留本节，并在自己仓库的 `LICENSE` 文件后附上上游版权行。

### 相关但不属于本项目的组件

上游 last30days 内置了一个 vendored 的 X/Twitter 搜索客户端：

- 路径：`scripts/lib/vendor/bird-search/`
- 版权：Copyright (c) 2025 Peter Steinberger
- 许可：MIT

本项目不包含该组件，此处一并注明以保持信息完整。

## 许可

本项目采用 MIT License，见 [LICENSE](LICENSE)。

本项目版权：Copyright (c) 2026 last30days-cards contributors

使用本项目时，你的合规义务包括：

- 保留本项目的 MIT 许可声明
- 如使用了 [last30days](https://github.com/mvanhorn/last30days-skill)，须同时遵守其 MIT 许可
- 如使用了 `hn_to_report.py`，须遵守 [Hacker News API 使用条款](https://github.com/HackerNews/API)
- 如使用了 `reddit_to_report.py`，须遵守 [Reddit 数据使用条款](https://www.redditinc.com/policies/data-api-terms)（本项目通过 [Arctic Shift](https://arctic-shift.photon-reddit.com/) 第三方存档访问公开数据，请自行确认适用条款）
