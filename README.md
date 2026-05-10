# 美洲新闻自动抓取结果｜Daily Americas News Collection

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![RSS](https://img.shields.io/badge/RSS-Available-orange.svg)](https://unsolublesugar.github.io/americas-news/rss.xml)

本项目用于根据公开 RSS 新闻源自动抓取美洲相关新闻，并输出 Markdown、HTML、RSS 和历史归档，方便研究团队人工筛选。

本项目不自动判断新闻价值，不自动撰写评论。新闻价值、事实核验和最终采用由人工完成。

## 查看结果

**[Markdown 结果](daily_news.md)** | **[HTML 卡片视图](https://unsolublesugar.github.io/americas-news/)** | **[RSS 订阅](https://unsolublesugar.github.io/americas-news/rss.xml)**

## 默认分类

| 分类 | 公开 RSS 来源 | 条数 |
|------|---------------|------|
| 美国 | PBS NewsHour Politics | 5 |
| 拉丁美洲 | MercoPress Latin America | 5 |
| 加勒比地区 | Caribbean News Global | 5 |
| 加拿大 | Government of Canada News Atom feed | 5 |
| 智库 | Inter-American Dialogue | 5 |
| 国际组织 | UN News Americas | 5 |

本项目只使用公开 RSS，不抓取付费墙页面，也不绕过网站限制。缩略图查询会跳过已知付费或受限域名。

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

GitHub Actions 每日 22:00 UTC 自动运行，也支持手动触发。工作流会在结果变化时提交 `daily_news.md`、`index.html`、`rss.xml` 和 `archives/`。

## RSS 源配置

在 `fetch_news.py` 中修改 `FEEDS`：

```python
FEEDS = {
    "美国": "https://www.pbs.org/newshour/feeds/rss/politics",
    "拉丁美洲": "https://en.mercopress.com/rss/latin-america",
    "加拿大": "https://api.io.canada.ca/io-server/gc/news/en/v2?format=atom&orderBy=desc&pick=50&sort=publishedDate",
    "智库": "https://www.thedialogue.org/feed/",
}
```

请保持来源为公开 RSS，并避免付费墙或受限页面。

## License

This project is licensed under the [MIT License](LICENSE).
