# 项目结构说明

## 目录结构

```
americas-news/
├── src/                          # Python 源代码
│   ├── __init__.py              # 主包初始化
│   ├── main.py                  # 兼容辅助入口
│   ├── config/                  # 配置管理
│   │   ├── __init__.py
│   │   └── archive_config.py    # 站点与路径配置
│   ├── generators/              # 生成器
│   │   ├── __init__.py
│   │   └── archive_generator.py # 归档与索引生成
│   ├── templates/               # 模板管理
│   │   ├── __init__.py
│   │   └── template_manager.py  # HTML/CSS 模板
│   └── utils/                   # 工具函数
│       └── __init__.py
├── assets/                      # 静态资源
│   ├── css/                    # 样式表
│   ├── images/                 # 图片文件
│   │   └── x-logo/            # X 标识资源
│   └── js/                    # JavaScript
├── docs/                       # 文档
│   └── DIRECTORY_STRUCTURE.md
├── archives/                   # 自动生成的历史归档
├── daily_tech_news.py         # 兼容入口，转发执行 fetch_news.py
├── fetch_news.py              # 主要抓取与生成脚本
├── requirements.txt           # Python 依赖
└── README.md                  # 项目概览
```

## 运行方式

### 主要入口
```bash
python3 fetch_news.py
```

### 兼容入口
```bash
python3 daily_tech_news.py
```

## 模块说明

### src/config/
- **SiteConfig**：站点整体配置
- **PathConfig**：路径与 URL 配置

### src/generators/
- **ArchiveGenerator**：每日归档生成
- **ArchiveIndexGenerator**：索引页生成

### src/templates/
- **TemplateManager**：HTML/CSS 模板统一管理
- **ContentStructure**：内容结构化

### src/utils/
- 预留通用工具函数位置

## 变更记录

### v2.0.0 - 项目结构调整
- 整理目录结构
- 拆分配置、模板和归档辅助模块
- 保留主要抓取脚本兼容性
- 面向后续维护预留模块边界

### v1.1.0 - 重构
- 整合归档生成功能
- 减少重复代码
- 统一配置管理

### v1.0.0 - 初始版本
- 基础新闻抓取和发布能力
- RSS feed parsing
- HTML/Markdown 生成
