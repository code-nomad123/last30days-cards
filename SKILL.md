---
name: last30days-cards
description: 把 last30days 的调研报告渲染成卡片式输出或 PNG 信息图——每个主题单独成卡，只留结论、互动量、关键引述和链接，也能出带时间轴的图。当用户说"用卡片给我""按主题整理 last30days 结果""整点图片""来张图"时使用；也可独立调用。
license: MIT
upstream:
  name: last30days
  repository: https://github.com/mvanhorn/last30days-skill
  author: mvanhorn
  license: MIT
---

# last30days-cards

把 `last30days` 已跑完的报告 JSON 重新排版成卡片。**不联网调研、不改 last30days 本身**——它只是个渲染器，last30days 是它的一个数据源。

> **上游**：[last30days](https://github.com/mvanhorn/last30days-skill) v4.3.2，作者 Matt Van Horn（[@mvanhorn](https://github.com/mvanhorn)），MIT 许可。
> 本项目基于其输出格式开发，不包含上游代码，与上游无隶属关系。完整归属声明见 `README.md` 的「上游归属」章节。

## 什么时候用

- 已经跑过 `last30days`，手上有报告 JSON，嫌原输出太杂。
- 用户要"每条信息单独成块""只留重点""按主题分组"。
- 想把 35 个 cluster / 38 个候选压成 5–8 张能扫完的卡。
- 手上是任意来源的 JSON（HN / Reddit 存档 / 自建数据），想拼成卡片图。

## 什么时候不用

- 还没跑过 last30days → 先跑 `last30days` 技能拿到报告。
- 需要全新调研 → 用 `last30days`，本技能不产数据。

## 安装与运行环境

需要 Python 3.10+ 与 Pillow（只有出图才需要 Pillow，纯文字模式不需要）。

```bash
python -m pip install pillow
```

脚本之间用 `common.py` 共享代码，**五个脚本必须放在同一目录**下运行，直接 `python cards.py ...` 即可，不需要装成包。

## 输入

优先读 last30days 的缓存报告（每次运行后自动覆盖）：

```
~/.config/last30days/last-report.json
```

结构：`reports[0].report` 内含 `clusters` 与 `ranked_candidates`。脚本同时接受 `last30days --emit=json` 直接输出的裸 report（无 `reports[]` 包裹）。

## 用法

```bash
# 四种文字风格
python cards.py <report.json> --style news    --top 10   # 新闻式综述：导语 + 时间轴
python cards.py <report.json> --style rundown --top 5    # 卡片式（最适合逐条阅读）
python cards.py <report.json> --style table   --top 10   # 表格，一屏扫完
python cards.py <report.json> --style plain              # 纯文本，最省 token

# 过滤
python cards.py <report.json> --source youtube --top 5    # 只看某个来源
python cards.py <report.json> --source reddit             # 别名，含全部 Reddit 子板

python cards.py <report.json> --json                      # 输出中间结构，供自己再加工
```

参数：
- `--style` — `rundown`（默认）/ `news` / `table` / `plain`
- `--top N` — 只显示前 N 张卡，`0` 或不传 = 全部
- `--source` — 来源过滤，支持别名（见下）
- `--json` — 不渲染，输出卡片字典数组

退出码：`0` 成功，`1` 文件不存在或 JSON 解析失败，`2` 过滤后无卡片。

### 来源别名

报告里的来源 key 各不相同（`hackernews` / `hacker_news_custom` / `reddit_wsb`），
`--source` 传人话就行，`SOURCE_ALIAS` 负责展开：

| 传这个 | 命中这些 |
|---|---|
| `hackernews` / `hn` | `hackernews`, `hacker_news_custom` |
| `reddit` | `reddit`, `reddit_wsb`, `reddit_inv` |
| `poly` / `polymarket` | `polymarket` |
| 其他 | 原样匹配 |

## 四种风格怎么选

| 风格 | 用途 | 形态 |
|---|---|---|
| `news` | 想知道"这一个月发生了什么" | 标题 + 时间范围 + 来源分布 + 导语 + 按日期铺开的时间轴 |
| `rundown` | 想知道"哪几条值得点开" | 每卡：标题、来源互动、摘要、关键引述、链接 |
| `table` | 想快速扫一眼全貌 | 五列表格，一屏十行 |
| `plain` | 塞给别的脚本 | 只有得分、标题、链接 |

`news` 的导语数字全部从报告里算出来（最高声量、最密集的一天），不臆造。

## 出图（PNG 信息图）

```bash
python cardimg.py <report.json> -o cards.png --top 8        # 精选 8 条
python cardimg.py <report.json> -o cards-all.png            # 全部
python cardimg.py <report.json> -o cards.png --top 8 --images   # 带原文配图
```

参数：`-o/--out` 输出路径（默认 `cards.png`）、`--top N` 只渲前 N 条、
`--images` 嵌原文配图、`--exclude 关键词` 排除跑题条目（可重复）、`--min-score N` 分数下限。

版式自上而下：深色头（话题 + 日期范围 + 来源徽章）→ 数据带（总播放、总点赞、总分、评论、活跃日）→ 时间轴（左栏 MM-DD，年份只在跨年时标一次；中间竖线带节点；右侧卡片带来源色条、两行标题、摘要、互动量、分数徽章）→ 页脚注明数据来源。

**字体**：脚本依次尝试 `msyh.ttc`（微软雅黑，Windows）、`PingFang.ttc`（macOS）、
`NotoSansCJK-Regular.ttc`（Linux）。都找不到时中文会变方块——在 `FONT_DIR` 里加自己的字体路径。

**折行不能用字符硬断**：英文单词会被劈成 "Tut orial"。`wrap_words()` 英文按词断、中文逐字断，改渲染逻辑时别绕过它。

退出码同 `cards.py`：`0` 成功，`1` 报告不存在或解析失败，`2` 无卡片。

实测尺寸参考：top 8 → 1400×1488（约 154KB）；全量 35 条 → 1400×4806（约 509KB）。

### 相关性过滤（`--exclude` / `--min-score`）

上游 planner 偶尔会把搜索词里的泛词带偏——2026-11-19 的 `mcp server` 报告里，搜索词含 "model"，
35 张卡有 22 张是模型新闻（Kimi、Qwen、Muse Ember）。渲染器不判断语义，但可以机械排除：

```bash
python cardimg.py report.json -o clean.png --exclude "Kimi" --exclude "Qwen" --exclude "模型"
python cardimg.py report.json -o clean.png --min-score 50
```

`--exclude` 对标题做不区分大小写的子串匹配。**这是止血不是治病**——干净结果还得从
last30days 的 `--plan` 收紧 subquery。

## 原文配图（`--images`）

卡片左侧嵌入原文配图（208×117，等比裁剪），文字自动右移。

**last30days 报告里没有图片字段**——扫过全部 539KB，不含 `thumbnail` / `image` / `cover` 任何键，
引擎只记文字和互动量。所以图是从 URL 反推的，`pick_image_url()` 负责这件事：

| 来源 | 能否拿到图 | 依据 |
|---|---|---|
| YouTube | ✅ 封面原图 | 视频 ID → `i.ytimg.com/vi/<id>/mqdefault.jpg` |
| GitHub | ✅ 作者头像 | `github.com/<author>.png?size=200` |
| 带 `image` 字段的条目 | ✅ 直接用 | 条目里有 `image` / `image_url` / `og_image` / `thumbnail` 任一字段就照用 |
| Hacker News | ⚠️ 看情况 | 原生报告无图；`hn_to_report.py` 抓了 `og:image` 写进条目就能用 |
| Reddit | ✅ 有据可查 | `reddit_to_report.py` 走存档 API 拿 `thumbnail`（图片贴才有，self 贴无图） |
| Polymarket | ❌ 无 | 条目没有配图概念，只能显示纯文字卡 |

**YouTube 封面与 Reddit 缩略图通常需要代理**，直连多半超时（取决于网络环境）。
GitHub 头像一般直连就行。没配代理时这些图会静默失败（`fetch_image` 返回 `None`，
卡片退回纯文字，不报错不中断）。

代理通过环境变量配置，`cardimg.py` 按这个顺序读：

```bash
export LAST30DAYS_CARDS_PROXY=http://127.0.0.1:8080   # 专用，替换成你的代理地址
export HTTPS_PROXY=http://127.0.0.1:8080
export HTTP_PROXY=http://127.0.0.1:8080
```

图片缓存在 `~/.cache/last30days-cards/img`（SHA256 前 20 位命名），
二次渲染 0.4 秒，全量 15 张图首次约 9 秒。

**这不是"重新画图"**。YouTube 那张就是视频上传者设置的封面，与网页上看到的一致；
文字、数据全部来自报告。只是换了排版，没有生成任何新内容。

带 `--images` 时，无图的卡片会把标题缩进到与有图卡片相同的位置（`INDENT = THUMB_W + 24`），
保证整列标题左边对齐；不带 `--images` 时 `INDENT = 0`，标题从卡片左侧正常起排。

数据带的指标列按内容实际宽度居中均分（`GAP = 96`），不是死板等分——只有 3 项时不会在右侧留一大片空白。

## 喂外部数据（任意 JSON）

`cardimg.py` 只认一种结构：`reports[0].report` 下有 `clusters` / `ranked_candidates` / `items_by_source`。
任何来源只要能拼成这个结构就能出图，不必是 last30days 跑出来的。

条目里塞这些字段即可：`item_id` / `source` / `title` / `url` / `author` / `published_at` /
`engagement{points,comments,views,likes}` / `image`。`image` 有值就直接当封面用，优先于 URL 反推。

`source` 不在 `common.SOURCE_NAME` 里也能跑，只是徽章显示原始名、配色退回灰色。
要固定的名字/颜色，加进 `SOURCE_NAME` 和 `SRC_COLOR` 即可。

两个现成的转换脚本：

### `hn_to_report.py` — HN 热门

```bash
python hn_to_report.py --days 7 --min-points 700 --top 12
python hn_to_report.py --days 30 --min-points 300 --top 20 --out hn.json
python hn_to_report.py --days 3 --top 5 --no-images      # 不抓 og:image，快很多
```

参数：`--days`（默认 7）、`--min-points`（默认 700）、`--top`（默认 12）、
`--topic`、`--out`（默认临时目录）、`--no-images`、`--proxy`（默认读环境变量）。
用 HN Algolia 公开 API，直连可用。

### `reddit_to_report.py` — Reddit 存档

```bash
python reddit_to_report.py --sub technology --sub programming \
  --after 2026-11-13 --before 2026-11-21 \
  --keyword release --keyword launch --top 22 --pages 8
```

参数：`--sub`（可重复）、`--after`/`--before`（必填）、`--keyword`（可重复，标题子串）、
`--min-score`、`--top`、`--pages`、`--no-comments`、`--topic`、`--out`（默认临时目录）。

**Reddit 官方 API 走不通**（JSON 直连超时、代理 403、RSS 403），
本脚本用 `arctic-shift.photon-reddit.com` 存档 API，实测直连可用。
两点注意：必须带时间范围；**422 是限流不是参数错**，脚本会退避重试。
分数与评论数来自存档，可能滞后于 Reddit 实时页面。

## 多源合并（`merge_reports.py`）

```bash
python merge_reports.py \
  --report ~/.config/last30days/last-report.json \
  --report /tmp/reddit_report.json \
  --out /tmp/merged.json --topic "示例话题 · 全网视角"
```

`--out` 不传则写临时目录。`load()` 会给各份报告的 ID 加前缀（`m0_` / `m1_`）避免撞车。

**为什么必须合并而不是分着出图**：引擎报告的分是综合分（几十到一百），
Reddit 报告的分是点赞数（几千），HN 是分数（几百）。直接把数字并排贴在同一张图里，
读者会以为 5079 分的那条比 100.0 分的那条重要 50 倍——两者根本不是同一个量纲。

所以 `merge_reports.py` 默认按 source 分组做百分位归一化：同一来源内部第 1 名是 100，
最后一名是 0，来源之间各排各的。原始数值不丢，仍在每条卡片下方那行
（`5,079 赞` / `1,715 分`）照常显示。想要原始分数就加 `--raw-scores`，但那种图只能看单一来源。

**跨源排名是假的**。归一化后 100.0 分会同时出现在 YouTube、HN、Reddit 榜首，
它们之间没有可比性——百分位只说明"在它自己那个来源里最热"。
合并图的正确读法是横向看分布（哪些来源在讨论这件事），不是纵向比高低。

## 卡片摘要行

卡片标题下面可以带一行两行的摘要（灰色小字，行距 27），内容取自条目的 `snippet` 字段。
`reddit_to_report.py` 会把 Reddit 帖子正文写进 `snippet`；**但多数热帖的 `selftext` 是
`[removed]`，正文拿不到，脚本会回落到抓最高赞评论**（形如
`热评 217 赞：I was allocated 3 ... THREE what am i supposed to do with that?`）。
`--no-comments` 可跳过那轮抓取，更快但被删正文的帖子会空白。

摘要行只影响版式：有摘要时卡片自动加高，有配图时垂直居中会一起算进去。

## 输出结构约定

每张卡固定这些字段，顺序即排版顺序：

| 字段 | 含义 | 处理方式 |
|---|---|---|
| `title` | 簇标题 | 按来源过滤时改用条目自身标题 |
| `sources` | 来源 | 已转成人话（`YouTube` 而非 `youtube`），走 `common.SOURCE_NAME` |
| `score` | 簇综合得分 | 已四舍五入到 1 位 |
| `engagement` | 互动量 | 各源字段归一：播放/赞/评/分/星/顶；Reddit 的 points 叫"赞"，HN 叫"分" |
| `published` | 发布日期 | 取 `YYYY-MM-DD` |
| `snippet` | 摘要 | 截断 180 字符；与标题重复时丢弃 |
| `why` | 推荐理由 | 过滤 `fallback-local-score` 等内部噪声 |
| `evidence` | 关键引述 | 字幕摘录 2 条 + 观众评论 2 条 |

## 代码结构

| 文件 | 职责 |
|---|---|
| `common.py` | 共享件：`SOURCE_NAME` 映射、`load_report()`、`default_out()`、`proxy_url()`、`build_opener()` |
| `cards.py` | 四种文字风格 + 来源别名过滤 |
| `cardimg.py` | PNG 渲染 + 配图抓取 + 相关性过滤 |
| `merge_reports.py` | 多报告合并 + 跨源百分位归一化 |
| `hn_to_report.py` | HN Algolia → 报告结构 |
| `reddit_to_report.py` | Reddit 存档 → 报告结构 |

读报告、来源名映射、代理、默认输出路径**只有 `common.py` 一份实现**，
改动时改那里，别在各脚本里各写一遍。

## 已内置的清洗规则（别改坏）

1. **UP 主自己的评论跳过**（`is_uploader: true`）——那是推广不是观众观点。
2. **`explanation` 里的内部信号不展示**——`fallback-local-score` / `no-explanation` 之类是调试字段，不是人话。
3. **snippet 以 title 开头时置空**——Hacker News、GitHub、YouTube 描述的常见情况，否则每卡浪费两行。
4. **文本压平空白再截断**——字幕常带换行，不处理会把卡片撑散。
5. **`--source` 过滤时分数改用条目自身分数**——簇分是聚合信号，簇里最高分的可能是被滤掉的那个源，照搬会张冠李戴（曾导致"只看 Hacker News"时 MCP Is Dead 显示 58.6 分）。
6. **字符兼容替换**——标题里的 U+2011（`GPT‑6.2`）、U+2019（`Anthropic’s`）与 emoji 会让微软雅黑渲染成方块，`clean_text()` 统一换成 ASCII 等价物或删除。

## 局限（重要，别对用户吹）

- 只做**重排**，不判断内容质量。last30days 给什么它排什么；上游漏掉的源（如 Reddit 403、X 未启用）它补不了。
- 卡片来自 `clusters`（语义聚类），簇为空时无卡片（退出码 2）。此时改用 `--style plain` 直读 `ranked_candidates` 也无解——应回退到 `last30days` 重跑。
- `--source` 过滤是在已聚类结果上筛，可能出现"某源 0 张卡"，不代表该源这次没数据。
- **默认不做相关性甄别**，只提供 `--exclude` / `--min-score` 这两个机械闸门。要干净结果得从 `last30days` 的 `--plan` 收紧 subquery。

## 试跑基准

2026-11-19 的 `mcp server` 报告（539KB，35 clusters / 38 candidates）：
- `--style rundown --top 5` 约 1.2KB 输出，覆盖 YouTube 13 条 + HN 22 条的精华。
- 同样内容用 `--emit=compact` 原始输出约 8KB。
