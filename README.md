# 美洲新闻自动抓取工具｜Daily Americas News Collection

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![RSS](https://img.shields.io/badge/RSS-Available-orange.svg)](https://slana4615-cel.github.io/Americas-news/rss.xml)

美洲新闻自动抓取工具。根据公开 RSS 新闻源自动抓取与美洲相关的新闻和机构动态，并输出 Markdown、HTML、RSS 和历史归档。



## 查看结果

**[Markdown 结果](daily_news.md)** | **[HTML 卡片视图](https://slana4615-cel.github.io/Americas-news/)** | **[RSS 订阅](https://slana4615-cel.github.io/Americas-news/rss.xml)**

## 默认分类

| 分类 | 公开 RSS 来源 | 条数 |
|------|---------------|------|
| 美国 | PBS NewsHour Politics | 5 |
| 拉丁美洲 | MercoPress Latin America | 5 |
| 加勒比地区 | Caribbean News Global | 5 |
| 智库 | Inter-American Dialogue | 5 |
| 国际组织 | UN News Americas | 5 |

只使用公开 RSS。

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

## RSS 源配置

在 `fetch_news.py` 中修改 `FEEDS`：

```python
FEEDS = {
    "美国": "https://www.pbs.org/newshour/feeds/rss/politics",
    "拉丁美洲": "https://en.mercopress.com/rss/latin-america",
    "加勒比地区": "https://caribbeannewsglobal.com/feed/",
    "智库": "https://www.thedialogue.org/feed/",
    "国际组织": "https://news.un.org/feed/subscribe/en/news/region/americas/feed/rss.xml",
}
```

## 项目来源与致谢

本项目基于 [unsolublesugar/daily-tech-news](https://github.com/unsolublesugar/daily-tech-news) 修改而来，原项目采用 MIT License。感谢原作者提供的自动抓取、归档和页面生成基础。

## License

This project is licensed under the [MIT License](LICENSE).
