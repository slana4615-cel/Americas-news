<language>Chinese</language>
<character_code>UTF-8</character_code>

# AGENTS.md

请使用中文回答和说明。

## 项目定位

本项目是美洲新闻自动抓取工具，用于根据公开 RSS 新闻源定期抓取与美洲相关的新闻和机构动态，并生成结构化结果，供中文研究团队进行初步筛选。

本项目不负责判断新闻价值，不自动撰写评论，不生成“今日重点”“研究价值”“今日观察”等主观判断内容。程序只负责抓取、去重、归类和结构化展示。

新闻价值判断、事实核验、后续研判和最终采用决定均由人工研究团队完成。

## 输出要求

- `daily_news.md` 面向中文研究团队阅读。
- `daily_news.md` 使用中文栏目名和中文元信息。
- 每条新闻必须保留英文原标题，不翻译标题，避免误译。
- 每条新闻使用固定字段结构：
  - `原标题`
  - `来源`
  - `发布时间`
  - `地区分类`
  - `原文链接`
  - `原文摘要`（当 RSS 提供 summary / description 时）
- 地区分类使用中文：
  - 美国
  - 拉丁美洲
  - 加勒比地区
  - 加拿大
  - 智库
  - 国际组织

## 保留功能

以下输出和自动化能力必须保留：

- `daily_news.md`
- `index.html`
- `rss.xml`
- `archives/`
- GitHub Actions 自动更新
- RSS 去重逻辑
- 不抓取付费墙页面，不绕过网站限制

## 技术栈

- Python 3.9+
- `feedparser`
- `requests`
- `beautifulsoup4`
- `concurrent.futures`
- GitHub Actions

## 常用命令

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
source .venv/bin/activate
python3 fetch_news.py
```

兼容入口：

```bash
python3 daily_tech_news.py
```

## 项目结构

```text
americas-news/
├── fetch_news.py              # 主要抓取与生成脚本
├── daily_tech_news.py         # 兼容入口，转发执行 fetch_news.py
├── daily_news.md              # 自动生成的每日 Markdown 结果
├── index.html                 # 自动生成的 HTML 卡片视图
├── rss.xml                    # 自动生成的 RSS
├── archives/                  # 历史归档
├── assets/                    # CSS / JS / HTML 模板等静态资源
├── src/                       # 配置和模板辅助模块
├── requirements.txt           # Python 依赖
└── .github/workflows/         # GitHub Actions 配置
```

## 维护原则

- 优先维护抓取、结构化输出和自动更新稳定性。
- 不添加 AI 自动评分、自动评论、自动摘要再创作或主观筛选逻辑。
- 如果需要新增 RSS 源，应优先选择公开、稳定、非付费墙来源。
- 修改输出格式时，应确保 `daily_news.md`、`index.html`、`rss.xml` 和 `archives/` 能继续生成。
