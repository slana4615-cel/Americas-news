"""
アーカイブ生成のための設定管理モジュール
"""
import os
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class SiteConfig:
    """サイト全体の設定を管理するクラス"""
    
    # サイト基本情報
    SITE_TITLE_TEMPLATE: str = "美洲新闻自动抓取结果｜Daily Americas News Collection ({date})"
    SITE_DESCRIPTION: str = "本文件由程序根据公开 RSS 新闻源自动抓取生成，仅用于研究团队初步筛选。新闻价值、事实核验和最终采用由人工判断。"
    GITHUB_USERNAME: str = os.getenv("GITHUB_USERNAME") or os.getenv("USER_NAME") or os.getenv("GITHUB_REPOSITORY_OWNER", "slana4615-cel")
    REPOSITORY_NAME: str = os.getenv("REPOSITORY_NAME", "Americas-news")
    GITHUB_REPOSITORY_NAME: str = os.getenv("GITHUB_REPOSITORY_NAME", "Americas-news")
    X_USERNAME: str = os.getenv("X_USERNAME") or os.getenv("TWITTER_USERNAME") or os.getenv("GITHUB_REPOSITORY_OWNER") or "unsoluble_sugar"
    
    @property
    def site_url(self) -> str:
        """GitHub Pages URLを動的生成"""
        return f"https://{self.GITHUB_USERNAME}.github.io/{self.REPOSITORY_NAME}/"
    
    @property
    def github_repo_url(self) -> str:
        """GitHubリポジトリURLを動的生成"""
        return f"https://github.com/{self.GITHUB_USERNAME}/{self.GITHUB_REPOSITORY_NAME}"
    
    @property
    def rss_url(self) -> str:
        """RSS URLを動的生成"""
        return f"{self.site_url}rss.xml"
    
    @property
    def twitter_user(self) -> str:
        """X ユーザー名を@付きで取得"""
        return f"@{self.X_USERNAME}"
    
    @property
    def profile_url(self) -> str:
        """プロフィールURLを取得（X設定時はX、未設定時はGitHub）"""
        # X_USERNAMEが明示的に設定されている場合はXリンク
        if os.getenv("X_USERNAME") or os.getenv("TWITTER_USERNAME"):
            return f"https://x.com/{self.X_USERNAME}"
        # 未設定の場合はGitHubプロフィール
        else:
            return f"https://github.com/{self.GITHUB_USERNAME}"
    
    @property
    def profile_display_name(self) -> str:
        """プロフィール表示名を取得"""
        # X_USERNAMEが明示的に設定されている場合は@付き
        if os.getenv("X_USERNAME") or os.getenv("TWITTER_USERNAME"):
            return f"@{self.X_USERNAME}"
        # 未設定の場合はGitHubユーザー名
        else:
            return self.GITHUB_USERNAME
    
    # フィード設定
    MAX_ENTRIES_DEFAULT: int = 5
    MAX_ENTRIES_EVENTS: int = 10
    PRIORITY_FEEDS: List[str] = None
    
    # アーカイブ設定
    ARCHIVE_BASE_DIR: str = "archives"
    
    # OGP画像設定
    OG_IMAGE_FILENAME: str = "assets/images/OGP.png"
    
    # X(Twitter) 設定
    X_LOGO_PATH: str = "assets/images/x-logo/logo-white.png"
    X_HASHTAGS: str = "AmericasNews,AcademicResearch"
    
    def __post_init__(self):
        if self.PRIORITY_FEEDS is None:
            self.PRIORITY_FEEDS = [
                "美国",
                "拉丁美洲",
                "加勒比地区",
                "智库",
                "国际组织",
            ]
    
    @property
    def og_image_url(self) -> str:
        """OGP画像の完全URLを取得"""
        return f"{self.site_url}{self.OG_IMAGE_FILENAME}"
    
    def get_site_title(self, date_str: str) -> str:
        """日付を含むサイトタイトルを生成"""
        return self.SITE_TITLE_TEMPLATE.format(date=date_str)
    
    def get_max_entries(self, feed_name: str) -> int:
        """フィード名に応じた最大エントリー数を取得"""
        if "Event" in feed_name or "イベント" in feed_name:
            return self.MAX_ENTRIES_EVENTS
        return self.MAX_ENTRIES_DEFAULT


@dataclass
class PathConfig:
    """パス関連の設定を管理するクラス"""
    
    # 相対パス設定
    MAIN_TO_ARCHIVE: str = "archives"
    ARCHIVE_TO_MAIN: str = "../.."
    ARCHIVE_TO_MONTHLY: str = ".."
    
    @staticmethod
    def get_archive_dir_path(year: int, month: int = None) -> str:
        """アーカイブディレクトリのパスを生成"""
        if month is None:
            return f"archives/{year}"
        return f"archives/{year}/{month:02d}"
    
    @staticmethod
    def get_archive_file_path(year: int, month: int, day: int, file_type: str = "md") -> str:
        """アーカイブファイルのパスを生成"""
        date_str = f"{year}-{month:02d}-{day:02d}"
        return f"archives/{year}/{month:02d}/{date_str}.{file_type}"
    
    @staticmethod
    def get_relative_main_page_path(depth: int) -> str:
        """階層の深さに応じたメインページへの相対パスを生成"""
        if depth == 0:
            return "index.html"
        elif depth == 1:
            return "../index.html"
        elif depth == 2:
            return "../../index.html"
        else:
            return "../" * depth + "index.html"


# デフォルト設定インスタンス
DEFAULT_SITE_CONFIG = SiteConfig()
DEFAULT_PATH_CONFIG = PathConfig()
