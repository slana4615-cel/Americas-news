# 美洲新闻自动抓取工具｜Daily Americas News Collection

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![RSS](https://img.shields.io/badge/RSS-Available-orange.svg)](https://slana4615-cel.github.io/Americas-news/rss.xml)

美洲新闻自动抓取工具。根据公开 RSS 新闻源和透明的 Google News RSS fallback 自动抓取与美洲相关的新闻和机构动态，并按来源权威性、时效、地区相关性、政治经济相关性和跨源覆盖情况排序后输出 Markdown、HTML、RSS 和历史归档。



## 查看结果

**[Markdown 结果](daily_news.md)** | **[HTML 卡片视图](https://slana4615-cel.github.io/Americas-news/)** | **[RSS 订阅](https://slana4615-cel.github.io/Americas-news/rss.xml)**

## 默认输出分类

| 分类 | 说明 |
|------|------|
| 美国 | 美国政治、经济和对美洲政策相关条目 |
| 拉丁美洲 | 拉美国家、区域政治经济和安全条目 |
| 加勒比地区 | 加勒比国家和区域机构相关条目 |
| 智库 | 美洲研究机构、区域政策研究和专题分析 |
| 国际组织 | 联合国、IMF、世界银行、IDB、OAS、ECLAC 等机构动态 |

系统先汇总多个公开 RSS 候选源，保留基础关键词过滤，再通过评分和来源上限选择最终条目，避免固定来源或小众来源主导输出。

## 输出文件

- `daily_news.md`：每日 Markdown 自动抓取结果
- `index.html`：HTML 卡片视图
- `rss.xml`：生成后的 RSS
- `archives/`：按日期归档的 Markdown 和 HTML
- `slack_message.json`：可选 Slack 通知载荷

## 本地运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 fetch_news.py
```

也可以激活虚拟环境后运行：

```bash
source .venv/bin/activate
python3 fetch_news.py
```

## 自动更新

GitHub Actions 每日 北京时间9：00 自动运行，也支持手动触发。工作流会在结果变化时提交 `daily_news.md`、`index.html`、`rss.xml` 和 `archives/`。

## RSS 源和来源级别配置

在 `fetch_news.py` 中修改 `SOURCE_TIERS`、`FEEDS` 和 `FALLBACK_FEEDS`。输出会保留英文原标题，并在 Markdown、HTML 和 RSS 中标注来源级别。

```python
SOURCE_TIERS = {
    "Tier 1": {"score": 100, "domains": (...)},
    "Tier 2": {"score": 75, "domains": (...)},
    "Tier 3": {"score": 45, "domains": (...)},
}
```

## 项目来源与致谢

本项目基于 [unsolublesugar/daily-tech-news](https://github.com/unsolublesugar/daily-tech-news) 修改而来，原项目采用 MIT License。感谢原作者提供的自动抓取、归档和页面生成基础。

## License

This project is licensed under the [MIT License](LICENSE).
