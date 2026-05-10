"""
归档生成辅助模块。
"""
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

from config import SiteConfig, PathConfig, DEFAULT_SITE_CONFIG, DEFAULT_PATH_CONFIG
from templates import TemplateManager, ContentStructure


@dataclass
class ArchiveEntry:
    """保存归档条目信息的数据类。"""
    title: str
    link: str
    feed_name: str
    thumbnail_url: Optional[str] = None


class ArchiveGenerator:
    """统一管理归档生成。"""
    
    def __init__(self, site_config: SiteConfig = None, path_config: PathConfig = None):
        self.site_config = site_config or DEFAULT_SITE_CONFIG
        self.path_config = path_config or DEFAULT_PATH_CONFIG
        self.template_manager = TemplateManager(self.site_config, self.path_config)
        self.content_structure = ContentStructure(self.template_manager)
    
    def _ensure_directory(self, dir_path: str) -> None:
        """确保目录存在。"""
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def _save_content(self, content: str, file_path: str) -> None:
        """将内容保存到文件。"""
        self._ensure_directory(os.path.dirname(file_path))
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _process_entries(self, all_entries: Dict[str, List[Any]], 
                        thumbnails: Dict[str, str] = None) -> str:
        """将条目渲染为 HTML 字符串。"""
        html_content = ""
        
        for feed_name, entries in all_entries.items():
            html_content += f"    <h2>{feed_name}</h2>\n"
            
            if not entries:
                html_content += "    <p>未能获取新闻条目。</p>\n"
            else:
                for entry in entries:
                    thumbnail_url = thumbnails.get(entry.link) if thumbnails else None
                    card_html = self.template_manager.render_card(entry, feed_name, thumbnail_url)
                    html_content += card_html + "\n"
        
        return html_content
    
    def _process_entries_markdown(self, all_entries: Dict[str, List[Any]]) -> str:
        """将条目渲染为 Markdown 字符串。"""
        markdown_content = ""
        
        for feed_name, entries in all_entries.items():
            markdown_content += f"## {feed_name}\n\n"
            
            if not entries:
                markdown_content += "未能获取新闻条目。\n"
            else:
                for entry in entries:
                    entry_markdown = self.template_manager.render_markdown_entry(entry)
                    markdown_content += entry_markdown + "\n"
            
            markdown_content += "\n\n---\n"
        
        return markdown_content
    
    def generate_daily_archive(self, all_entries: Dict[str, List[Any]], 
                              date_obj: datetime,
                              thumbnails: Dict[str, str] = None) -> Tuple[str, str]:
        """生成每日归档（HTML 和 Markdown）。"""
        date_str = date_obj.strftime('%Y-%m-%d')
        title = self.site_config.get_site_title(date_str)
        
        # 生成 HTML
        entries_html = self._process_entries(all_entries, thumbnails)
        html_content = self.content_structure.build_html_page(
            title, date_str, entries_html, is_archive=True
        )
        
        # 生成 Markdown
        entries_markdown = self._process_entries_markdown(all_entries)
        markdown_content = self.content_structure.build_markdown_page(
            title, date_str, entries_markdown, is_archive=True
        )
        
        return html_content, markdown_content
    
    def save_daily_archive(self, all_entries: Dict[str, List[Any]], 
                          feed_info: Dict[str, Dict], date_obj: datetime,
                          thumbnails: Dict[str, str] = None) -> Tuple[str, str]:
        """生成每日归档并保存到文件。"""
        year = date_obj.year
        month = date_obj.month
        day = date_obj.day
        
        # 生成内容
        html_content, markdown_content = self.generate_daily_archive(
            all_entries, feed_info, date_obj, thumbnails
        )
        
        # 生成文件路径
        html_path = self.path_config.get_archive_file_path(year, month, day, "html")
        md_path = self.path_config.get_archive_file_path(year, month, day, "md")
        
        # 保存文件
        self._save_content(html_content, html_path)
        self._save_content(markdown_content, md_path)
        
        print(f"Archive saved: {html_path}, {md_path}")
        return html_path, md_path
    
    def generate_main_page(self, all_entries: Dict[str, List[Any]], 
                          feed_info: Dict[str, Dict], date_str: str,
                          thumbnails: Dict[str, str] = None) -> Tuple[str, str]:
        """生成主页面（HTML 和 Markdown）。"""
        title = self.site_config.get_site_title(date_str)
        
        # 生成 HTML
        entries_html = self._process_entries(all_entries, feed_info, thumbnails)
        
        # 添加主页面 RSS 信息
        rss_info = '''
    <div class="rss-info">
        <strong>📡 RSS 订阅</strong><br>
        可使用 RSS 阅读器订阅每日自动抓取结果。<br>
        <a href="rss.xml" target="_blank" rel="noopener">RSS 订阅</a>
    </div>
'''
        entries_html += rss_info
        
        html_content = self.content_structure.build_html_page(
            title, date_str, entries_html, is_archive=False
        )
        
        # 生成 Markdown
        entries_markdown = self._process_entries_markdown(all_entries, feed_info)
        markdown_content = self.content_structure.build_markdown_page(
            title, date_str, entries_markdown, is_archive=False
        )
        
        return html_content, markdown_content
    
    def convert_markdown_to_html(self, markdown_path: str, target_html_path: str = None) -> str:
        """将已有 Markdown 文件转换为 HTML。"""
        if not os.path.exists(markdown_path):
            raise FileNotFoundError(f"Markdown file not found: {markdown_path}")
        
        with open(markdown_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 根据路径深度决定 favicon 和 CSS 路径
        path_parts = markdown_path.replace(self.site_config.ARCHIVE_BASE_DIR, '').strip('/').split('/')
        depth = len([p for p in path_parts if p])
        
        # 计算相对路径
        if depth == 1:  # archives/index.html
            favicon_path = "../assets/favicons/"
            css_path = "../assets/css/main.css"
        elif depth == 2:  # archives/YYYY/index.html
            favicon_path = "../../assets/favicons/"
            css_path = "../../assets/css/main.css"
        elif depth == 3:  # archives/YYYY/MM/index.html
            favicon_path = "../../../assets/favicons/"
            css_path = "../../../assets/css/main.css"
        else:
            favicon_path = "assets/favicons/"
            css_path = "assets/css/main.css"
        
        # 提取标题
        title = "美洲新闻自动抓取结果归档"
        lines = content.split('\n')
        for line in lines:
            if line.startswith('# '):
                title = line[2:].strip()
                break
        
        # 生成 HTML head
        og_image_url = self.site_config.og_image_url
        site_description = self.site_config.SITE_DESCRIPTION
        site_url = self.site_config.site_url
        twitter_user = self.site_config.twitter_user
        
        html_head = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    
    <!-- OGP Tags -->
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{site_description}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{site_url}">
    <meta property="og:image" content="{og_image_url}">
    <meta property="og:site_name" content="美洲新闻自动抓取结果">
    
    <!-- Twitter Card Tags -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:creator" content="{twitter_user}">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{site_description}">
    <meta name="twitter:image" content="{og_image_url}">
    
    <!-- Favicon Links -->
    <link rel="apple-touch-icon" sizes="180x180" href="{favicon_path}apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="{favicon_path}favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="{favicon_path}favicon-16x16.png">
    <link rel="manifest" href="{favicon_path}site.webmanifest">
    <link rel="shortcut icon" href="{favicon_path}favicon.ico">
    
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        h1 {{
            color: #1f2328;
        }}
        ul {{
            list-style-type: disc;
            padding-left: 2em;
        }}
        li {{
            margin: 8px 0;
        }}
        a {{
            color: #0969da;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .back-link {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e1e5e9;
        }}
    </style>
</head>"""
        
        # 简单转换 Markdown 为 HTML
        lines = content.split('\n')
        html_body_lines = ['<body>', '<div class="content">']
        
        for line in lines:
            line = line.strip()
            if line.startswith('# '):
                # h1 标签
                title_text = line[2:]
                html_body_lines.append(f'<h1>{title_text}</h1>')
            elif line.startswith('## '):
                # h2 标签
                heading = line[3:]
                html_body_lines.append(f'<h2>{heading}</h2>')
            elif line.startswith('- ['):
                # 链接列表，格式为 - [标题](URL)
                import re
                match = re.match(r'- \[([^\]]+)\]\(([^)]+)\)', line)
                if match:
                    title_text, url = match.groups()
                    html_body_lines.append(f'<p><a href="{url}">{title_text}</a></p>')
                else:
                    html_body_lines.append(f'<p>{line}</p>')
            elif line == '---':
                html_body_lines.append('<hr>')
            elif line:
                html_body_lines.append(f'<p>{line}</p>')
        
        html_body_lines.extend(['</div>', '</body>', '</html>'])
        
        # 组合 head 和 body
        html_content = html_head + '\n' + '\n'.join(html_body_lines)
        
        # 保存文件
        if target_html_path:
            self._save_content(html_content, target_html_path)
            print(f"Converted HTML saved: {target_html_path}")
        
        return html_content


class ArchiveIndexGenerator:
    """管理归档索引页生成。"""
    
    def __init__(self, site_config: SiteConfig = None, path_config: PathConfig = None):
        self.site_config = site_config or DEFAULT_SITE_CONFIG
        self.path_config = path_config or DEFAULT_PATH_CONFIG
        self.template_manager = TemplateManager(self.site_config, self.path_config)
    
    def _ensure_directory(self, dir_path: str) -> None:
        """确保目录存在。"""
        Path(dir_path).mkdir(parents=True, exist_ok=True)
    
    def _save_content(self, content: str, file_path: str) -> None:
        """将内容保存到文件。"""
        self._ensure_directory(os.path.dirname(file_path))
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def _scan_archive_directories(self) -> Dict[int, List[int]]:
        """扫描归档目录并返回年月列表。"""
        archives_base = Path(self.site_config.ARCHIVE_BASE_DIR)
        year_month_map = {}
        
        if not archives_base.exists():
            return year_month_map
        
        for year_dir in archives_base.iterdir():
            if year_dir.is_dir() and year_dir.name.isdigit():
                year = int(year_dir.name)
                months = []
                
                for month_dir in year_dir.iterdir():
                    if month_dir.is_dir() and month_dir.name.isdigit():
                        months.append(int(month_dir.name))
                
                if months:
                    year_month_map[year] = sorted(months)
        
        return year_month_map
    
    def _scan_monthly_files(self, year: int, month: int) -> List[str]:
        """获取指定年月下的归档文件列表。"""
        month_dir = Path(self.path_config.get_archive_dir_path(year, month))
        files = []
        
        if month_dir.exists():
            for file_path in month_dir.glob("*.md"):
                if file_path.stem != "index":
                    files.append(file_path.stem)
        
        return sorted(files)
    
    def generate_archive_index(self) -> str:
        """生成总归档索引页。"""
        year_month_map = self._scan_archive_directories()
        
        # 生成 Markdown 内容
        md_content = "# 📚 历史抓取结果归档\n\n"
        md_content += f"{self.site_config.SITE_DESCRIPTION}\n\n"
        md_content += "## 按年归档\n\n"
        
        if not year_month_map:
            md_content += "未找到归档文件。\n"
        else:
            for year in sorted(year_month_map.keys(), reverse=True):
                md_content += f"- [{year} 年]({year}/index.md)\n"
        
        md_content += f"\n[← 返回最新结果](../daily_news.md)\n"
        
        return md_content
    
    def generate_yearly_index(self, year: int) -> str:
        """生成按年索引页。"""
        year_month_map = self._scan_archive_directories()
        months = year_month_map.get(year, [])
        
        md_content = f"# 📅 {year} 年抓取结果归档\n\n"
        md_content += f"{self.site_config.SITE_DESCRIPTION}\n\n"
        md_content += "## 按月归档\n\n"
        
        if not months:
            md_content += f"未找到 {year} 年的归档文件。\n"
        else:
            for month in sorted(months, reverse=True):
                md_content += f"- [{month:02d} 月]({month:02d}/index.md)\n"
        
        md_content += "\n[← 返回归档首页](../index.md)\n"
        
        return md_content
    
    def generate_monthly_index(self, year: int, month: int) -> str:
        """生成按月索引页。"""
        files = self._scan_monthly_files(year, month)
        
        md_content = f"# 📅 {year} 年 {month:02d} 月抓取结果归档\n\n"
        md_content += f"{self.site_config.SITE_DESCRIPTION}\n\n"
        md_content += "## 按日归档\n\n"
        
        if not files:
            md_content += f"未找到 {year} 年 {month:02d} 月的归档文件。\n"
        else:
            for file_date in sorted(files, reverse=True):
                # 从文件名提取日期（YYYY-MM-DD）
                try:
                    date_parts = file_date.split('-')
                    if len(date_parts) == 3:
                        day = int(date_parts[2])
                        md_content += f"- [{month:02d} 月 {day:02d} 日]({file_date}.md) | [HTML 卡片视图]({file_date}.html)\n"
                    else:
                        md_content += f"- [{file_date}]({file_date}.md)\n"
                except (ValueError, IndexError):
                    md_content += f"- [{file_date}]({file_date}.md)\n"
        
        md_content += f"\n[← 返回 {year} 年归档](../index.md)\n"
        
        return md_content
    
    def update_all_indexes(self) -> None:
        """更新所有索引页。"""
        year_month_map = self._scan_archive_directories()
        
        # 更新总索引
        archive_index_content = self.generate_archive_index()
        self._save_content(archive_index_content, f"{self.site_config.ARCHIVE_BASE_DIR}/index.md")
        print(f"Updated: {self.site_config.ARCHIVE_BASE_DIR}/index.md")
        
        # 更新按年和按月索引
        for year, months in year_month_map.items():
            # 按年索引
            yearly_content = self.generate_yearly_index(year)
            yearly_path = self.path_config.get_archive_dir_path(year) + "/index.md"
            self._save_content(yearly_content, yearly_path)
            print(f"Updated: {yearly_path}")
            
            # 按月索引
            for month in months:
                monthly_content = self.generate_monthly_index(year, month)
                monthly_path = self.path_config.get_archive_dir_path(year, month) + "/index.md"
                self._save_content(monthly_content, monthly_path)
                print(f"Updated: {monthly_path}")
