import feedparser
import datetime
import os
import sys
from pathlib import Path
from xml.dom import minidom
import xml.etree.ElementTree as ET
import requests
from bs4 import BeautifulSoup
import time
import re
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import json
import hashlib
import socket
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

# srcディレクトリをPythonパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# 設定のインポート
from config.archive_config import DEFAULT_SITE_CONFIG

socket.setdefaulttimeout(20)

# Public RSS feeds for Americas-focused research monitoring.
BRIEF_TITLE = "美洲新闻自动抓取结果｜Daily Americas News Collection"
BRIEF_DESCRIPTION = (
    "本文件由程序根据公开 RSS 新闻源自动抓取生成，仅用于研究团队初步筛选。"
    "新闻价值、事实核验和最终采用由人工判断。"
)
BRIEF_LANGUAGE = "zh-CN"
BRIEF_UPDATE_NOTE = "自动更新时间：每日 22:00 UTC。"

CATEGORY_LABELS = {
    "United States": "美国",
    "Latin America": "拉丁美洲",
    "Caribbean": "加勒比地区",
    "Think Tanks": "智库",
    "International Organizations": "国际组织",
}

SOURCE_LABELS = {
    "美国": "PBS NewsHour Politics",
    "拉丁美洲": "MercoPress Latin America",
    "加勒比地区": "Caribbean News Global",
    "智库": "Inter-American Dialogue",
    "国际组织": "UN News Americas",
}

FEEDS = {
    "美国": "https://www.pbs.org/newshour/feeds/rss/politics",
    "拉丁美洲": "https://en.mercopress.com/rss/latin-america",
    "加勒比地区": "https://caribbeannewsglobal.com/feed/",
    "智库": "https://www.thedialogue.org/feed/",
    "国际组织": "https://news.un.org/feed/subscribe/en/news/region/americas/feed/rss.xml",
}

# Domains to exclude from entry collection and thumbnail page requests.
EXCLUDED_DOMAINS = {
    'nytimes.com': 'paywalled source',
    'washingtonpost.com': 'paywalled source',
    'wsj.com': 'paywalled source',
    'ft.com': 'paywalled source',
    'economist.com': 'paywalled source',
    'bloomberg.com': 'paywalled source',
    'foreignaffairs.com': 'registration/paywall restricted source',
}

# 各フィードから取得する記事の件数
MAX_ENTRIES = 5

class ThumbnailCache:
    """サムネイルキャッシュを管理するクラス"""
    
    def __init__(self, cache_file_path="thumbnail_cache.json"):
        """
        キャッシュクラスの初期化
        
        Args:
            cache_file_path (str): キャッシュファイルのパス
        """
        self.cache_file_path = cache_file_path
        self.cache = self._load_cache()
    
    def _load_cache(self):
        """キャッシュファイルから既存のデータを読み込む"""
        try:
            if os.path.exists(self.cache_file_path):
                with open(self.cache_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load thumbnail cache: {e}")
        
        return {}
    
    def _save_cache(self):
        """キャッシュデータをファイルに保存する"""
        try:
            with open(self.cache_file_path, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save thumbnail cache: {e}")
    
    def _get_url_hash(self, url):
        """URLのハッシュ値を生成してキャッシュキーとする"""
        return hashlib.md5(url.encode('utf-8')).hexdigest()
    
    def get(self, url):
        """
        キャッシュからサムネイルURLを取得
        
        Args:
            url (str): 記事URL
            
        Returns:
            str or None: キャッシュされたサムネイルURL、またはNone
        """
        url_hash = self._get_url_hash(url)
        cache_entry = self.cache.get(url_hash)
        
        if cache_entry:
            # キャッシュエントリが7日以内なら有効とする
            import datetime
            cache_time = datetime.datetime.fromisoformat(cache_entry['timestamp'])
            now = datetime.datetime.now()
            
            if (now - cache_time).days < 7:
                return cache_entry.get('thumbnail_url')
        
        return None
    
    def set(self, url, thumbnail_url):
        """
        サムネイルURLをキャッシュに保存
        
        Args:
            url (str): 記事URL
            thumbnail_url (str or None): サムネイルURL
        """
        url_hash = self._get_url_hash(url)
        import datetime
        
        self.cache[url_hash] = {
            'url': url,
            'thumbnail_url': thumbnail_url,
            'timestamp': datetime.datetime.now().isoformat()
        }
    
    def save(self):
        """キャッシュをファイルに保存"""
        self._save_cache()
    
    def cleanup_old_entries(self, days_threshold=30):
        """
        古いキャッシュエントリを削除
        
        Args:
            days_threshold (int): 削除対象となる日数の閾値
        """
        import datetime
        now = datetime.datetime.now()
        
        keys_to_remove = []
        for key, entry in self.cache.items():
            try:
                cache_time = datetime.datetime.fromisoformat(entry['timestamp'])
                if (now - cache_time).days > days_threshold:
                    keys_to_remove.append(key)
            except Exception:
                # 不正なエントリは削除対象に
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self.cache[key]
        
        if keys_to_remove:
            print(f"Cleaned up {len(keys_to_remove)} old cache entries")

_TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "ref", "fbclid", "gclid",
})

def normalize_url(url):
    """URLを正規化して重複検出の精度を向上させる。

    - トラッキングパラメータ（utm_*、ref、fbclid、gclid）を除去
    - スキームを https に統一（http -> https）
    - パス末尾のスラッシュを除去
    - 元のURLは変更しない（比較用のみ）
    """
    if not url:
        return url
    try:
        parsed = urlparse(url)
        scheme = "https" if parsed.scheme == "http" else parsed.scheme
        path = parsed.path.rstrip("/") or "/"
        filtered_query = urlencode(
            [(k, v) for k, v in parse_qsl(parsed.query)
             if k.lower() not in _TRACKING_PARAMS]
        )
        return urlunparse((scheme, parsed.netloc, path, parsed.params, filtered_query, ""))
    except Exception:
        return url

def filter_entries_by_domain(entries, domain, label):
    filtered_entries = []
    excluded_count = 0
    
    for entry in entries:
        if hasattr(entry, 'link') and domain in entry.link:
            excluded_count += 1
            continue
        filtered_entries.append(entry)
    
    if excluded_count > 0:
        print(f"Excluded {excluded_count} {label} entries")
    
    return filtered_entries

CANADA_KEYWORDS = (
    "canada", "canadian", "ottawa", "toronto", "vancouver", "montreal",
    "bank of canada", "government of canada",
)

NOISE_KEYWORDS = (
    "sports", "nba", "nfl", "mlb", "soccer", "football", "baseball",
    "celebrity", "actor", "actress", "movie", "film", "music",
    "entertainment", "lifestyle", "fashion", "recipe", "travel tips",
    "weather forecast",
)

TARGET_REGION_KEYWORDS = (
    "united states", "u.s.", "us", "usa", "america", "american",
    "white house", "congress", "senate", "house of representatives",
    "federal reserve", "fed", "treasury department", "state department",
    "department of homeland security", "dhs", "trump administration",
    "biden administration", "latin america", "latin american",
    "south america", "central america", "caribbean", "mexico", "brazil",
    "argentina", "chile", "colombia", "venezuela", "peru", "ecuador",
    "bolivia", "uruguay", "paraguay", "cuba", "haiti",
    "dominican republic", "panama", "costa rica", "guatemala", "honduras",
    "el salvador", "nicaragua", "guyana", "suriname", "belize",
    "jamaica", "barbados", "trinidad", "tobago",
)

LATIN_AMERICA_ENTITY_KEYWORDS = (
    "latin america", "latin american", "south america", "central america",
    "caribbean", "mexico", "brazil", "argentina", "chile", "colombia",
    "venezuela", "peru", "ecuador", "bolivia", "uruguay", "paraguay",
    "cuba", "haiti", "dominican republic", "panama", "costa rica",
    "guatemala", "honduras", "el salvador", "nicaragua", "guyana",
    "suriname", "belize", "jamaica", "barbados", "trinidad", "tobago",
    "mercosur",
)

NON_AMERICAS_KEYWORDS = (
    "taiwan", "china", "beijing", "xi jinping", "trump-xi",
    "taiwan strait", "asia", "asian", "europe", "european", "ukraine",
    "russia", "middle east", "israel", "iran", "gaza", "africa",
    "african",
)

POLITICS_ECONOMY_KEYWORDS = (
    "politics", "political", "election", "vote", "voter", "campaign",
    "president", "government", "congress", "senate", "minister",
    "cabinet", "policy", "reform", "law", "court", "supreme court",
    "diplomacy", "foreign policy", "sanctions", "border", "migration",
    "immigration", "security", "defense", "military", "economy",
    "economic", "inflation", "interest rate", "central bank",
    "federal reserve", "fed", "treasury", "debt", "budget", "fiscal",
    "tax", "tariff", "trade", "investment", "market", "currency",
    "dollar", "growth", "recession", "jobs", "labor", "supply chain",
    "energy", "oil", "gas", "mining", "lithium", "copper", "imf",
    "world bank", "idb", "oas",
)

US_DOMESTIC_ENTITY_KEYWORDS = (
    "united states", "u.s.", "us", "usa", "american", "white house",
    "congress", "senate", "house of representatives", "supreme court",
    "federal reserve", "fed", "treasury", "treasury department",
    "department of homeland security", "dhs", "trump administration",
    "biden administration",
)

US_DOMESTIC_POLITICS_ECONOMY_KEYWORDS = (
    "u.s. congress", "us congress", "white house", "congress", "senate",
    "house of representatives", "federal reserve", "fed", "rate cut",
    "treasury", "dhs", "department of homeland security", "supreme court",
    "election", "midterm", "vote", "voter", "border", "immigration",
    "budget", "inflation", "jobs", "tax", "tariff", "interest rate",
    "trump administration", "biden administration",
)

CONTENT_SEARCH_LIMIT = 1200
_SHORT_KEYWORD_PATTERN = re.compile(r"^[a-z0-9]{1,3}$")
_BOUNDARY_KEYWORDS = frozenset({
    "sports", "soccer", "football", "baseball", "celebrity", "actor",
    "actress", "movie", "film", "music", "entertainment", "lifestyle",
    "fashion", "recipe",
})

def entry_search_text(entry):
    """Build a lightweight search string from RSS-provided entry fields only."""
    parts = []

    for field in ("title", "summary", "description"):
        cleaned = clean_text(getattr(entry, field, None))
        if cleaned:
            parts.append(cleaned)

    content = getattr(entry, "content", None)
    if content:
        content_items = content if isinstance(content, list) else [content]
        for item in content_items:
            if isinstance(item, dict):
                value = item.get("value")
            else:
                value = getattr(item, "value", None) or str(item)
            cleaned = clean_text(value)
            if cleaned:
                parts.append(cleaned[:CONTENT_SEARCH_LIMIT])

    link = getattr(entry, "link", None)
    if link:
        parsed_link = urlparse(str(link))
        link_text = " ".join(
            part for part in (
                parsed_link.path,
                parsed_link.params,
                parsed_link.query,
                parsed_link.fragment,
            ) if part
        )
        if contains_any(parsed_link.netloc.lower(), CANADA_KEYWORDS):
            link_text = f"{parsed_link.netloc} {link_text}".strip()
        if link_text:
            parts.append(link_text)

    search_text = " ".join(parts)
    search_text = re.sub(
        r"\bthe post .*? appeared first on [^.]+\.?",
        " ",
        search_text,
        flags=re.IGNORECASE,
    )
    search_text = re.sub(r"\bby caribbean news global\b", " ", search_text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", search_text).strip()

def contains_any(text, keywords):
    if not text:
        return False

    raw_text = str(text)
    normalized_text = re.sub(r"\s+", " ", raw_text.lower())
    for keyword in keywords:
        normalized_keyword = keyword.lower()
        if normalized_keyword == "us":
            if re.search(r"(?<![A-Za-z0-9$])US(?![A-Za-z0-9$])", raw_text):
                return True
            continue
        if normalized_keyword in _BOUNDARY_KEYWORDS or _SHORT_KEYWORD_PATTERN.match(normalized_keyword):
            pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
            if re.search(pattern, normalized_text):
                return True
            continue
        if normalized_keyword in normalized_text:
            return True

    return False

def is_us_domestic_politics_or_economy(text):
    return (
        contains_any(text, US_DOMESTIC_ENTITY_KEYWORDS)
        and contains_any(text, US_DOMESTIC_POLITICS_ECONOMY_KEYWORDS)
    )

def should_keep_entry(entry):
    text = entry_search_text(entry)

    if not text:
        return False

    if contains_any(text, CANADA_KEYWORDS):
        return False

    if contains_any(text, NOISE_KEYWORDS):
        return False

    has_latin_america_entity = contains_any(text, LATIN_AMERICA_ENTITY_KEYWORDS)
    is_us_domestic_entry = is_us_domestic_politics_or_economy(text)

    if (
        contains_any(text, NON_AMERICAS_KEYWORDS)
        and not has_latin_america_entity
        and not is_us_domestic_entry
    ):
        return False

    has_target_region = contains_any(text, TARGET_REGION_KEYWORDS) or has_latin_america_entity
    has_politics_or_economy = contains_any(text, POLITICS_ECONOMY_KEYWORDS)

    return has_target_region and has_politics_or_economy

def filter_entries_by_scope(entries, feed_name):
    filtered_entries = []
    excluded_titles = []

    for entry in entries:
        if should_keep_entry(entry):
            filtered_entries.append(entry)
            continue

        title = clean_text(getattr(entry, "title", None)) or getattr(entry, "link", None) or "未提供标题"
        excluded_titles.append(title)

    if excluded_titles:
        print(f"Scope filter excluded {len(excluded_titles)} entries from {feed_name}")
        for title in excluded_titles:
            print(f"范围过滤: [{feed_name}] {title}")

    return filtered_entries

def extract_author_info(entry):
    """RSSエントリーから著者情報を抽出する"""
    author = None
    
    # 複数のフィールドから著者情報を取得を試行
    if hasattr(entry, 'author') and entry.author:
        author = entry.author.strip()
    elif hasattr(entry, 'author_detail') and entry.author_detail and entry.author_detail.get('name'):
        author = entry.author_detail['name'].strip()
    elif hasattr(entry, 'authors') and entry.authors and len(entry.authors) > 0:
        first_author = entry.authors[0]
        if isinstance(first_author, dict) and first_author.get('name'):
            author = first_author['name'].strip()
        elif hasattr(first_author, 'name'):
            author = first_author.name.strip()
    
    # 著者情報があれば、長すぎる場合は短縮処理
    if author:
        # O'Reilly Japan等の長い著者情報の短縮処理
        if len(author) > 50:  # 50文字を超える場合
            # "著者名　著 訳者名　訳" パターンの処理
            if "　著" in author:
                author = author.split("　著")[0]
            # カンマ区切りの複数著者の場合、最初の2名まで
            elif "、" in author:
                authors = author.split("、")
                if len(authors) > 2:
                    author = "、".join(authors[:2]) + "他"
                else:
                    author = "、".join(authors[:2])
            # それでも長い場合は前半50文字+...
            if len(author) > 50:
                author = author[:47] + "..."
    
    return author

def get_category_label(feed_name):
    """Return the Chinese category label for a feed name."""
    return CATEGORY_LABELS.get(feed_name, feed_name)

def clean_text(text):
    """Convert RSS HTML/text fragments to compact plain text."""
    if not text:
        return None
    soup = BeautifulSoup(str(text), 'html.parser')
    cleaned = soup.get_text(" ", strip=True)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned or None

def get_entry_summary(entry):
    """Extract the original RSS summary/description without translation."""
    for field in ('summary', 'description'):
        value = getattr(entry, field, None)
        cleaned = clean_text(value)
        if cleaned:
            return cleaned
    if hasattr(entry, 'content') and entry.content:
        content = entry.content[0].get('value', '') if isinstance(entry.content, list) else str(entry.content)
        return clean_text(content)
    return None

def get_entry_published(entry):
    """Extract the RSS-provided publication timestamp without rewriting it."""
    for field in ('published', 'updated', 'created'):
        value = getattr(entry, field, None)
        if value:
            return clean_text(value)
    parsed_date = (
        getattr(entry, 'published_parsed', None)
        or getattr(entry, 'updated_parsed', None)
        or getattr(entry, 'created_parsed', None)
    )
    if parsed_date:
        return datetime.datetime(*parsed_date[:6]).strftime('%Y-%m-%d %H:%M:%S UTC')
    return "未提供"

def get_entry_source(entry, feed_name):
    """Extract a source name while keeping category separate from source."""
    if hasattr(entry, 'source') and entry.source:
        source = entry.source
        if isinstance(source, dict) and source.get('title'):
            return clean_text(source.get('title'))
        if hasattr(source, 'title') and source.title:
            return clean_text(source.title)
    if hasattr(entry, 'source_detail') and entry.source_detail and entry.source_detail.get('title'):
        return clean_text(entry.source_detail.get('title'))
    if hasattr(entry, 'source_info') and entry.source_info:
        return entry.source_info
    if feed_name in SOURCE_LABELS:
        return SOURCE_LABELS[feed_name]
    if hasattr(entry, 'link') and entry.link:
        netloc = urlparse(entry.link).netloc.replace('www.', '')
        return netloc or feed_name
    return feed_name

def format_markdown_entry(entry, feed_name):
    """Render one RSS entry in the fixed Chinese research-screening format."""
    title = clean_text(getattr(entry, 'title', '')) or "未提供"
    link = getattr(entry, 'link', '') or "未提供"
    source = get_entry_source(entry, feed_name) or "未提供"
    published = get_entry_published(entry)
    category = get_category_label(feed_name)
    summary = get_entry_summary(entry)

    item = (
        f"- **原标题**：{title}\n"
        f"  - **来源**：{source}\n"
        f"  - **发布时间**：{published}\n"
        f"  - **地区分类**：{category}\n"
        f"  - **原文链接**：{link}\n"
    )
    if summary:
        item += f"  - **原文摘要**：{summary}\n"
    return item

def fetch_feed_entries(feed_url, feed_name=None):
    """指定されたURLからRSSフィードのエントリーを取得する"""
    try:
        feed = feedparser.parse(feed_url)
        feed_title = clean_text(feed.feed.get('title')) if feed.feed else None
        fallback_source = SOURCE_LABELS.get(feed_name) or feed_title or urlparse(feed_url).netloc
        
        # 各エントリに著者情報を追加
        for entry in feed.entries:
            entry.author_info = extract_author_info(entry)
            entry.source_info = fallback_source
        
        return feed.entries
    except Exception as e:
        print(f"Error fetching feed from {feed_url}: {e}")
        return []

def get_article_thumbnail(url, max_retries=2):
    """記事URLからサムネイル画像URLを取得する"""
    parsed_url = urlparse(url)
    if any(domain in parsed_url.netloc for domain in EXCLUDED_DOMAINS):
        print(f"Skipping thumbnail lookup for restricted or paywalled domain: {url}")
        return None

    headers = {
        'User-Agent': 'DailyAmericasNewsBrief/1.0 (+https://github.com/slana4615-cel/Americas-news)'
    }
    
    def validate_image_url(img_url):
        """画像URLが有効かどうかチェック"""
        if not img_url or len(img_url) > 2000:  # URLが長すぎる場合は除外
            return False
        if not img_url.startswith(('http://', 'https://')):
            return False
        # 画像形式のチェック
        if any(ext in img_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
            return True
        # Dynamic image services commonly used for article thumbnails.
        if any(domain in img_url for domain in ['res.cloudinary.com', 'images.ctfassets.net', 'cdn.sanity.io']):
            return True
        return False
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Open Graph画像を優先的に取得
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                img_url = og_image['content']
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    from urllib.parse import urljoin
                    img_url = urljoin(url, img_url)
                if validate_image_url(img_url):
                    return img_url
            
            # Twitter Card画像
            twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                img_url = twitter_image['content']
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    from urllib.parse import urljoin
                    img_url = urljoin(url, img_url)
                if validate_image_url(img_url):
                    return img_url
            
            # 記事内最初の画像
            article_img = soup.find('img')
            if article_img and article_img.get('src'):
                img_url = article_img['src']
                if img_url.startswith('//'):
                    img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    from urllib.parse import urljoin
                    img_url = urljoin(url, img_url)
                if validate_image_url(img_url):
                    return img_url
                
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)  # リトライ前に少し待機
            continue
    
    return None  # 画像が見つからない場合

def deduplicate_events(entries, target_count=10):
    """イベント系エントリーの重複を除去（シリーズ番号違いを統合）し、目標件数を確保"""
    if not entries:
        return entries
    
    # イベント名の基底部分を抽出するパターン
    patterns = [
        r'^(.+?)\s*#\d+.*$',  # "朝活もくもく会 #19" -> "朝活もくもく会"
        r'^(.+?)\s*第\d+回.*$',  # "第5回勉強会" -> "勉強会" 
        r'^(.+?)\s*Vol\.\d+.*$',  # "勉強会 Vol.3" -> "勉強会"
        r'^(.+?)\s*\(\d+\).*$',  # "勉強会(3)" -> "勉強会"
        r'^(.+?)\s*-\s*\d+.*$',  # "勉強会 - 5" -> "勉強会"
    ]
    
    # エントリーを基底名でグループ化
    event_groups = {}
    
    for entry in entries:
        title = entry.title.strip()
        base_name = title
        
        # パターンマッチングで基底名を抽出
        for pattern in patterns:
            match = re.match(pattern, title)
            if match:
                base_name = match.group(1).strip()
                break
        
        # 基底名でグループ化（最新のエントリーを優先）
        if base_name not in event_groups:
            event_groups[base_name] = entry
        else:
            # 既存エントリーより新しい場合は置き換え
            existing_date = getattr(event_groups[base_name], 'published_parsed', None)
            current_date = getattr(entry, 'published_parsed', None)
            
            if current_date and existing_date:
                if current_date > existing_date:
                    event_groups[base_name] = entry
            elif current_date and not existing_date:
                event_groups[base_name] = entry
    
    # グループ化されたエントリーを返す（元の順序を保持）
    deduplicated = []
    seen_bases = set()
    
    for entry in entries:
        title = entry.title.strip()
        base_name = title
        
        for pattern in patterns:
            match = re.match(pattern, title)
            if match:
                base_name = match.group(1).strip()
                break
        
        if base_name not in seen_bases:
            deduplicated.append(event_groups[base_name])
            seen_bases.add(base_name)
            
            # 目標件数に達したら終了
            if len(deduplicated) >= target_count:
                break
    
    return deduplicated

def deduplicate_urls_across_feeds(all_entries):
    """フィード間でのURL重複を除去し、補填を行う（PRIORITY_FEEDS順で処理）"""
    seen_urls = set()
    deduplicated_feeds = {}
    dedup_stats = {"total_removed": 0, "norm_caught": 0, "by_feed": {}}
    
    # PRIORITY_FEEDSの順序でフィードを処理
    from src.config.archive_config import DEFAULT_SITE_CONFIG
    priority_feeds = DEFAULT_SITE_CONFIG.PRIORITY_FEEDS
    
    # PRIORITY_FEEDSに含まれるフィードから処理
    processed_feeds = set()
    for feed_name in priority_feeds:
        if feed_name in all_entries:
            processed_feeds.add(feed_name)
            entries = all_entries[feed_name]
            
            if not entries:
                deduplicated_feeds[feed_name] = entries
                continue
                
            target_count = DEFAULT_SITE_CONFIG.get_max_entries(feed_name)
            
            # URL重複除去（正規化URLで比較）
            unique_entries = []
            removed_count = 0
            norm_caught_feed = 0
            for entry in entries:
                if not hasattr(entry, 'link'):
                    unique_entries.append(entry)
                    continue
                norm = normalize_url(entry.link)
                if norm not in seen_urls:
                    seen_urls.add(norm)
                    unique_entries.append(entry)
                    if len(unique_entries) >= target_count:
                        break
                else:
                    removed_count += 1
                    if hasattr(entry, 'title'):
                        print(f"重複除去: [{feed_name}] {entry.title}")
                        print(f"  URL: {entry.link}")
                        if norm != entry.link:
                            print(f"  正規化URL: {norm}  ← 正規化による検出")
                            norm_caught_feed += 1

            # Event-style feeds can still opt into title-based event deduplication.
            if "Event" in feed_name or "イベント" in feed_name:
                unique_entries = deduplicate_events(unique_entries, target_count)

            deduplicated_feeds[feed_name] = unique_entries
            dedup_stats["by_feed"][feed_name] = removed_count
            dedup_stats["total_removed"] += removed_count
            dedup_stats["norm_caught"] += norm_caught_feed

    # PRIORITY_FEEDSに含まれていないフィードを処理
    for feed_name, entries in all_entries.items():
        if feed_name not in processed_feeds:
            if not entries:
                deduplicated_feeds[feed_name] = entries
                continue

            target_count = DEFAULT_SITE_CONFIG.get_max_entries(feed_name)

            # URL重複除去（正規化URLで比較）
            unique_entries = []
            removed_count = 0
            norm_caught_feed = 0
            for entry in entries:
                if not hasattr(entry, 'link'):
                    unique_entries.append(entry)
                    continue
                norm = normalize_url(entry.link)
                if norm not in seen_urls:
                    seen_urls.add(norm)
                    unique_entries.append(entry)
                    if len(unique_entries) >= target_count:
                        break
                else:
                    removed_count += 1
                    if hasattr(entry, 'title'):
                        print(f"重複除去: [{feed_name}] {entry.title}")
                        print(f"  URL: {entry.link}")
                        if norm != entry.link:
                            print(f"  正規化URL: {norm}  ← 正規化による検出")
                            norm_caught_feed += 1

            # Event-style feeds can still opt into title-based event deduplication.
            if "Event" in feed_name or "イベント" in feed_name:
                unique_entries = deduplicate_events(unique_entries, target_count)

            deduplicated_feeds[feed_name] = unique_entries
            dedup_stats["by_feed"][feed_name] = removed_count
            dedup_stats["total_removed"] += removed_count
            dedup_stats["norm_caught"] += norm_caught_feed

    # 重複除去統計を出力
    if dedup_stats["total_removed"] > 0:
        norm_caught = dedup_stats["norm_caught"]
        exact_caught = dedup_stats["total_removed"] - norm_caught
        print(f"URL重複除去統計: 合計{dedup_stats['total_removed']}件を除去")
        print(f"  うち正規化による検出: {norm_caught}件 / 完全一致による検出: {exact_caught}件")
        for feed_name, removed_count in dedup_stats["by_feed"].items():
            if removed_count > 0:
                print(f"  {feed_name}: {removed_count}件")
    
    return deduplicated_feeds

def fetch_all_thumbnails(all_entries, max_workers=10, use_cache=True):
    """全フィードの全記事のサムネイルを並列取得（キャッシュ対応）"""
    # 全記事のURLリストを作成
    all_urls = []
    for entries in all_entries.values():
        all_urls.extend([entry.link for entry in entries])
    
    print(f"Fetching thumbnails for {len(all_urls)} articles...")
    
    # キャッシュの初期化
    cache = ThumbnailCache() if use_cache else None
    thumbnails = {}
    urls_to_fetch = []
    
    # キャッシュから取得できるものは先に処理
    if cache:
        cache_hits = 0
        for url in all_urls:
            cached_thumbnail = cache.get(url)
            if cached_thumbnail is not None:
                thumbnails[url] = cached_thumbnail
                cache_hits += 1
            else:
                urls_to_fetch.append(url)
        
        if cache_hits > 0:
            print(f"Cache hits: {cache_hits}/{len(all_urls)} thumbnails")
    else:
        urls_to_fetch = all_urls
    
    # キャッシュにないURLのみ並列取得
    if urls_to_fetch:
        print(f"Fetching {len(urls_to_fetch)} new thumbnails in parallel...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 未キャッシュのURLに対して並列でサムネイル取得を実行
            future_to_url = {
                executor.submit(get_article_thumbnail, url): url 
                for url in urls_to_fetch
            }
            
            completed = 0
            total = len(urls_to_fetch)
            
            # 完了した処理から順次結果を取得
            for future in concurrent.futures.as_completed(future_to_url):
                url = future_to_url[future]
                completed += 1
                
                try:
                    thumbnail_url = future.result(timeout=15)
                    thumbnails[url] = thumbnail_url
                    
                    # キャッシュに保存
                    if cache:
                        cache.set(url, thumbnail_url)
                    
                    print(f"Progress: {completed}/{total} new thumbnails fetched")
                except Exception as e:
                    print(f"Error fetching thumbnail for {url}: {e}")
                    thumbnails[url] = None
                    
                    # エラーの場合もキャッシュに保存（Noneとして）
                    if cache:
                        cache.set(url, None)
    
    # キャッシュを保存
    if cache:
        cache.cleanup_old_entries()  # 古いエントリを削除
        cache.save()
        print("Thumbnail cache updated")
                
    return thumbnails

def generate_html(all_entries, date_str, thumbnails=None):
    """新しいテンプレートシステムを使用してHTMLコンテンツを生成する"""
    from src.templates.template_manager import TemplateManager, ContentStructure
    
    # テンプレートマネージャーの初期化
    template_manager = TemplateManager()
    content_structure = ContentStructure(template_manager)
    
    # 記事カードのHTML生成
    entries_html = ""
    
    for feed_name, entries in all_entries.items():
        category = get_category_label(feed_name)
        entries_html += f"    <h2>{category}</h2>\n"
        
        if not entries:
            entries_html += "    <p>未能获取新闻条目。</p>\n"
        else:
            for entry in entries:
                thumbnail_url = thumbnails.get(entry.link) if thumbnails else None
                card_html = template_manager.render_card(entry, category, thumbnail_url)
                entries_html += card_html
    
    # 記事総数を計算
    total_entries = sum(len(entries) for entries in all_entries.values())
    
    # 完全なHTMLページを構築
    title = f"{BRIEF_TITLE} ({date_str})"
    html_content = content_structure.build_html_page(
        title=title,
        date_str=date_str,
        entries_html=entries_html,
        total_entries=total_entries,
        is_archive=False
    )
    
    return html_content

def generate_markdown(all_entries, date_str):
    """取得したエントリーからMarkdownコンテンツを生成する"""
    markdown = f"# {BRIEF_TITLE}\n\n"
    markdown += f"""- **生成日期**：{date_str}
- **自动更新**：每日 22:00 UTC
- **输出说明**：{BRIEF_DESCRIPTION}

📚 [历史归档](archives/index.md) | 🎨 [HTML 卡片视图]({DEFAULT_SITE_CONFIG.site_url}) | 📡 [RSS 订阅]({DEFAULT_SITE_CONFIG.rss_url})
---

## 抓取结果

"""

    for feed_name, entries in all_entries.items():
        category = get_category_label(feed_name)
        markdown += f"## {category}\n\n"
        if not entries:
            markdown += "未能获取新闻条目。\n"
        else:
            # エントリーはすでにURL重複除去済み
            for entry in entries:
                markdown += format_markdown_entry(entry, feed_name) + "\n"
        
        markdown += "\n\n---\n"
    
    return markdown

def generate_archive_markdown(all_entries, date_str):
    """アーカイブ用のMarkdownコンテンツを生成する（相対パス修正版）"""
    markdown = f"# {BRIEF_TITLE}\n\n"
    markdown += f"""- **生成日期**：{date_str}
- **自动更新**：每日 22:00 UTC
- **输出说明**：{BRIEF_DESCRIPTION}

📚 [最新结果](../../daily_news.md) | 🎨 [HTML 卡片视图]({DEFAULT_SITE_CONFIG.site_url}) | 📡 [RSS 订阅]({DEFAULT_SITE_CONFIG.rss_url})

---

## 抓取结果

"""

    for feed_name, entries in all_entries.items():
        category = get_category_label(feed_name)
        markdown += f"## {category}\n\n"
        if not entries:
            markdown += "未能获取新闻条目。\n"
        else:
            # エントリーはすでにURL重複除去済み
            for entry in entries:
                markdown += format_markdown_entry(entry, feed_name) + "\n"
        
        markdown += "\n\n---\n"
    
    return markdown

def generate_archive_html(all_entries, date_str, thumbnails=None):
    """新しいテンプレートシステムを使用してアーカイブHTMLを生成する"""
    from src.templates.template_manager import TemplateManager, ContentStructure
    
    # テンプレートマネージャーの初期化
    template_manager = TemplateManager()
    content_structure = ContentStructure(template_manager)
    
    # 記事カードのHTML生成
    entries_html = ""
    
    for feed_name, entries in all_entries.items():
        category = get_category_label(feed_name)
        entries_html += f"    <h2>{category}</h2>\n"
        
        if not entries:
            entries_html += "    <p>未能获取新闻条目。</p>\n"
        else:
            for entry in entries:
                thumbnail_url = thumbnails.get(entry.link) if thumbnails else None
                card_html = template_manager.render_card(entry, category, thumbnail_url)
                entries_html += card_html
    
    # アーカイブ用HTMLページを構築
    title = f"{BRIEF_TITLE} ({date_str})"
    html_content = content_structure.build_html_page(
        title=title,
        date_str=date_str,
        entries_html=entries_html,
        is_archive=True
    )
    
    return html_content

def save_to_archive(all_entries, date_obj, thumbnails=None):
    """日付別アーカイブファイルとして保存（MarkdownとHTML両方）"""
    year = date_obj.year
    month = f"{date_obj.month:02d}"
    date_str = date_obj.isoformat()
    
    # ディレクトリ作成
    archive_dir = Path(f"archives/{year}/{month}")
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Markdown版
    md_content = generate_archive_markdown(all_entries, date_str)
    archive_file = archive_dir / f"{date_str}.md"
    if archive_file.exists():
        print(f"Overwriting existing archive: {archive_file}")
    else:
        print(f"Creating new archive: {archive_file}")
    
    with open(archive_file, "w", encoding="utf-8") as f:
        f.write(md_content)
    
    # HTML版
    html_content = generate_archive_html(all_entries, date_str, thumbnails)
    html_file = archive_dir / f"{date_str}.html"
    
    with open(html_file, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"Generated archive files: {archive_file} and {html_file}")
    
    return archive_file

def update_monthly_index(year, month):
    """月別インデックスページを更新（MarkdownとHTML両方）"""
    archive_dir = Path(f"archives/{year}/{month:02d}")
    if not archive_dir.exists():
        return
    
    # その月のファイル一覧を取得
    md_files = sorted([f for f in archive_dir.iterdir() if f.suffix == '.md' and f.name != 'index.md'])
    
    # Markdown版
    month_label = f"{year}-{month:02d}"
    md_content = f"# {BRIEF_TITLE} 归档：{month_label}\n\n"
    md_content += f"{month_label} 自动抓取结果列表。\n\n"
    
    for md_file in reversed(md_files):  # 新しい順
        date_str = md_file.stem
        md_content += f"- [{date_str}]({md_file.name})\n"
    
    md_content += f"\n[← 返回 {year} 年归档](../index.md)\n"
    
    with open(archive_dir / "index.md", "w", encoding="utf-8") as f:
        f.write(md_content)
    
    # HTML版
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{BRIEF_TITLE} 归档：{month_label}</title>
    
    <!-- OGP Tags -->
    <meta property="og:title" content="{BRIEF_TITLE} 归档：{month_label}">
    <meta property="og:description" content="{BRIEF_DESCRIPTION}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{DEFAULT_SITE_CONFIG.site_url}">
    <meta property="og:image" content="{DEFAULT_SITE_CONFIG.og_image_url}">
    <meta property="og:site_name" content="{BRIEF_TITLE}">
    
    <!-- Twitter Card Tags -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:creator" content="@unsoluble_sugar">
    <meta name="twitter:title" content="{BRIEF_TITLE} 归档：{month_label}">
    <meta name="twitter:description" content="{BRIEF_DESCRIPTION}">
    <meta name="twitter:image" content="{DEFAULT_SITE_CONFIG.og_image_url}">
    
    <!-- Favicon Links -->
    <link rel="apple-touch-icon" sizes="180x180" href="../../../assets/favicons/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="../../../assets/favicons/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="../../../assets/favicons/favicon-16x16.png">
    <link rel="manifest" href="../../../assets/favicons/site.webmanifest">
    <link rel="shortcut icon" href="../../../assets/favicons/favicon.ico">
    
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
</head>
<body>
    <h1>{BRIEF_TITLE} 归档：{month_label}</h1>
    
    <p>{month_label} 自动抓取结果列表。</p>
    
    <ul>"""
    
    for md_file in reversed(md_files):  # 新しい順
        date_str = md_file.stem
        html_content += f'\n        <li><a href="{date_str}.html">{date_str}</a></li>'
    
    html_content += f"""
    </ul>
    
    <div class="back-link">
        <p><a href="../index.html">← 返回 {year} 年归档</a></p>
    </div>
</body>
</html>"""
    
    with open(archive_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def update_yearly_index(year):
    """年別インデックスページを更新（MarkdownとHTML両方）"""
    year_dir = Path(f"archives/{year}")
    if not year_dir.exists():
        return
    
    # その年の月ディレクトリ一覧を取得
    month_dirs = sorted([d for d in year_dir.iterdir() if d.is_dir() and d.name.isdigit()])
    
    # Markdown版
    md_content = f"# {BRIEF_TITLE} 归档：{year}\n\n"
    md_content += f"{year} 年自动抓取结果按月归档。\n\n"
    
    for month_dir in reversed(month_dirs):  # 新しい順
        month = int(month_dir.name)
        md_content += f"- [{year}-{month:02d}]({month_dir.name}/index.md)\n"
    
    md_content += f"\n[← 返回归档首页](../index.md)\n"
    
    with open(year_dir / "index.md", "w", encoding="utf-8") as f:
        f.write(md_content)
    
    # HTML版
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{BRIEF_TITLE} 归档：{year}</title>
    
    <!-- OGP Tags -->
    <meta property="og:title" content="{BRIEF_TITLE} 归档：{year}">
    <meta property="og:description" content="{BRIEF_DESCRIPTION}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{DEFAULT_SITE_CONFIG.site_url}">
    <meta property="og:image" content="{DEFAULT_SITE_CONFIG.og_image_url}">
    <meta property="og:site_name" content="{BRIEF_TITLE}">
    
    <!-- Twitter Card Tags -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:creator" content="@unsoluble_sugar">
    <meta name="twitter:title" content="{BRIEF_TITLE} 归档：{year}">
    <meta name="twitter:description" content="{BRIEF_DESCRIPTION}">
    <meta name="twitter:image" content="{DEFAULT_SITE_CONFIG.og_image_url}">
    
    <!-- Favicon Links -->
    <link rel="apple-touch-icon" sizes="180x180" href="../../assets/favicons/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="../../assets/favicons/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="../../assets/favicons/favicon-16x16.png">
    <link rel="manifest" href="../../assets/favicons/site.webmanifest">
    <link rel="shortcut icon" href="../../assets/favicons/favicon.ico">
    
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
</head>
<body>
    <h1>{BRIEF_TITLE} 归档：{year}</h1>
    
    <p>{year} 年自动抓取结果按月归档。</p>
    
    <ul>"""
    
    for month_dir in reversed(month_dirs):  # 新しい順
        month = int(month_dir.name)
        html_content += f'\n        <li><a href="{month_dir.name}/index.html">{year}-{month:02d}</a></li>'
    
    html_content += f"""
    </ul>
    
    <div class="back-link">
        <p><a href="../index.html">← 返回归档首页</a></p>
    </div>
</body>
</html>"""
    
    with open(year_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def generate_missing_html_archives():
    """既存のMarkdownアーカイブファイルに対応するHTMLファイルが存在しない場合に生成する"""
    archives_dir = Path("archives")
    if not archives_dir.exists():
        return
    
    # 全てのMarkdownアーカイブファイルを検索
    md_files = list(archives_dir.glob("**/????-??-??.md"))
    
    for md_file in md_files:
        html_file = md_file.with_suffix('.html')
        
        # HTMLファイルが存在しない場合のみ生成
        if not html_file.exists():
            print(f"Generating missing HTML archive: {html_file}")
            
            # Markdownファイルからコンテンツを読み取り、簡易的にHTMLに変換
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    md_content = f.read()
                
                # 日付を抽出
                date_match = re.search(r'^\s*-\s*\*\*生成日期\*\*：\s*(\d{4}-\d{2}-\d{2})', md_content, re.MULTILINE)
                if not date_match:
                    date_match = re.search(r'^Date:\s*(\d{4}-\d{2}-\d{2})', md_content, re.MULTILINE)
                if not date_match:
                    date_match = re.search(r'# .*\((\d{4}-\d{2}-\d{2})\)', md_content)
                if date_match:
                    date_str = date_match.group(1)
                    
                    # 簡易的なHTML生成（完全な記事リスト無しでも基本構造を生成）
                    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{BRIEF_TITLE} ({date_str})</title>
    
    <!-- OGP Tags -->
    <meta property="og:title" content="{BRIEF_TITLE} ({date_str})">
    <meta property="og:description" content="{BRIEF_DESCRIPTION}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{DEFAULT_SITE_CONFIG.site_url}">
    <meta property="og:image" content="{DEFAULT_SITE_CONFIG.og_image_url}">
    <meta property="og:site_name" content="{BRIEF_TITLE}">
    
    <!-- Twitter Card Tags -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:site" content="@unsoluble_sugar">
    
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }}
        h1, h2 {{
            color: #1f2328;
        }}
        a {{
            color: #0969da;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .rss-info {{
            background: #f6f8fa;
            padding: 16px;
            border-radius: 8px;
            margin: 20px 0;
        }}
        .footer {{
            margin-top: 40px;
            padding: 20px 0;
            border-top: 1px solid #e1e5e9;
            text-align: center;
            font-size: 14px;
            color: #656d76;
        }}
        .footer a {{
            color: #0969da;
            text-decoration: none;
        }}
        .footer a:hover {{
            text-decoration: underline;
        }}
        ul {{
            line-height: 1.8;
        }}
    </style>
</head>
<body>
    <h1>{BRIEF_TITLE} ({date_str})</h1>
    
    <p>📚 <a href="../../index.html">历史归档</a> | 📡 <a href="{DEFAULT_SITE_CONFIG.rss_url}">RSS 订阅</a></p>
    
    <p>{BRIEF_DESCRIPTION}</p>
    
    <div class="rss-info">
        <p>{BRIEF_UPDATE_NOTE}</p>
    </div>
    
    <hr>
"""
                    
                    # Markdownの内容を簡易的にHTMLに変換
                    lines = md_content.split('\n')
                    in_list = False
                    current_section = None
                    
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                            
                        # セクションヘッダー
                        if line.startswith('## ') and not line.startswith('## License'):
                            if in_list:
                                html_content += "    </ul>\n    <hr>\n"
                                in_list = False
                            
                            section_title = line[3:].strip()
                            html_content += f"    <h2>{section_title}</h2>\n"
                            current_section = section_title
                            
                        # リスト項目
                        elif line.startswith('- [') and current_section and 'License' not in current_section:
                            if not in_list:
                                html_content += "    <ul>\n"
                                in_list = True
                            
                            # リンクを抽出
                            link_match = re.match(r'- \[([^\]]+)\]\(([^)]+)\)', line)
                            if link_match:
                                title, url = link_match.groups()
                                html_content += f'        <li><a href="{url}">{title}</a></li>\n'
                    
                    if in_list:
                        html_content += "    </ul>\n    <hr>\n"
                    
                    html_content += f"""
    <div class="footer">
        <p>📡 <a href="{DEFAULT_SITE_CONFIG.rss_url}">订阅 RSS</a></p>
        <p>🚀 <a href="{DEFAULT_SITE_CONFIG.profile_url}" target="_blank" rel="noopener">{DEFAULT_SITE_CONFIG.profile_display_name}</a> |
        📁 <a href="{DEFAULT_SITE_CONFIG.github_repo_url}" target="_blank" rel="noopener">GitHub Repository</a></p>
    </div>
</body>
</html>"""
                    
                    with open(html_file, 'w', encoding='utf-8') as f:
                        f.write(html_content)
                        
            except Exception as e:
                print(f"Error generating HTML for {md_file}: {e}")

def update_archive_index():
    """アーカイブ全体のインデックスページを更新（MarkdownとHTML両方）"""
    archives_dir = Path("archives")
    if not archives_dir.exists():
        return
    
    # 既存のMarkdownファイルに対応するHTMLファイルを生成
    generate_missing_html_archives()
    
    # 年ディレクトリ一覧を取得
    year_dirs = sorted([d for d in archives_dir.iterdir() if d.is_dir() and d.name.isdigit()])
    
    # Markdown版（README.mdからの遷移用）
    md_content = f"# {BRIEF_TITLE} 归档\n\n"
    md_content += "历年自动抓取结果归档。\n\n"
    
    for year_dir in reversed(year_dirs):  # 新しい順
        year = year_dir.name
        md_content += f"- [{year}]({year}/index.md)\n"
    
    md_content += f"\n[← 返回最新结果](../daily_news.md)\n"
    with open(archives_dir / "index.md", "w", encoding="utf-8") as f:
        f.write(md_content)
    
    # HTML版（index.htmlからの遷移用）
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{BRIEF_TITLE} 归档</title>
    
    <!-- OGP Tags -->
    <meta property="og:title" content="{BRIEF_TITLE} 归档">
    <meta property="og:description" content="{BRIEF_DESCRIPTION}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="{DEFAULT_SITE_CONFIG.site_url}">
    <meta property="og:image" content="{DEFAULT_SITE_CONFIG.og_image_url}">
    <meta property="og:site_name" content="{BRIEF_TITLE}">
    
    <!-- Twitter Card Tags -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:creator" content="@unsoluble_sugar">
    <meta name="twitter:title" content="{BRIEF_TITLE} 归档">
    <meta name="twitter:description" content="{BRIEF_DESCRIPTION}">
    <meta name="twitter:image" content="{DEFAULT_SITE_CONFIG.og_image_url}">
    
    <!-- Favicon Links -->
    <link rel="apple-touch-icon" sizes="180x180" href="../assets/favicons/apple-touch-icon.png">
    <link rel="icon" type="image/png" sizes="32x32" href="../assets/favicons/favicon-32x32.png">
    <link rel="icon" type="image/png" sizes="16x16" href="../assets/favicons/favicon-16x16.png">
    <link rel="manifest" href="../assets/favicons/site.webmanifest">
    <link rel="shortcut icon" href="../assets/favicons/favicon.ico">
    
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
</head>
<body>
    <h1>{BRIEF_TITLE} 归档</h1>
    
    <p>历年自动抓取结果归档。</p>
    
    <ul>"""
    
    for year_dir in reversed(year_dirs):  # 新しい順
        year = year_dir.name
        html_content += f'\n        <li><a href="{year}/index.html">{year}</a></li>'
    
    html_content += """
    </ul>
    
    <div class="back-link">
        <p><a href="../index.html">← 返回最新结果</a></p>
    </div>
</body>
</html>"""
    
    with open(archives_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(html_content)

def update_readme_with_archive_link(content):
    """README.mdにアーカイブとRSSへのリンクを追加（既に含まれている場合はそのまま）"""
    # generate_markdown関数で既にアーカイブとRSSリンクが含まれているため、
    # 追加処理は不要。そのまま返す
    return content

def generate_rss_feed(all_entries, date_obj):
    """RSS XMLフィードを生成"""
    # RSS要素の作成
    rss = ET.Element('rss', version='2.0', attrib={'xmlns:atom': 'http://www.w3.org/2005/Atom'})
    channel = ET.SubElement(rss, 'channel')
    
    # チャンネル情報
    ET.SubElement(channel, 'title').text = BRIEF_TITLE
    ET.SubElement(channel, 'link').text = DEFAULT_SITE_CONFIG.site_url
    ET.SubElement(channel, 'description').text = BRIEF_DESCRIPTION
    ET.SubElement(channel, 'language').text = BRIEF_LANGUAGE
    ET.SubElement(channel, 'pubDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S +0000')
    ET.SubElement(channel, 'lastBuildDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    # Atom自己参照リンク
    atom_link = ET.SubElement(channel, 'atom:link')
    atom_link.set('href', DEFAULT_SITE_CONFIG.rss_url)
    atom_link.set('rel', 'self')
    atom_link.set('type', 'application/rss+xml')
    
    # 各フィードからアイテムを追加
    for feed_name, entries in all_entries.items():
        # エントリーはすでにURL重複除去済み
        for entry in entries:
            category = get_category_label(feed_name)
            source = get_entry_source(entry, feed_name)
            item = ET.SubElement(channel, 'item')
            # RSSタイトルはプレーンテキストのみ（HTMLタグや絵文字を除去）
            clean_title = re.sub(r'<[^>]+>', '', entry.title)  # HTMLタグを除去
            ET.SubElement(item, 'title').text = clean_title
            ET.SubElement(item, 'link').text = entry.link
            ET.SubElement(item, 'description').text = f'地区分类：{category}；来源：{source}；原标题：{clean_title}'
            ET.SubElement(item, 'guid').text = entry.link
            
            # 公開日（エントリーに日付があれば使用、なければ今日）
            pub_date = getattr(entry, 'published_parsed', None)
            if pub_date:
                pub_datetime = datetime.datetime(*pub_date[:6])
                ET.SubElement(item, 'pubDate').text = pub_datetime.strftime('%a, %d %b %Y %H:%M:%S +0000')
            else:
                ET.SubElement(item, 'pubDate').text = date_obj.strftime('%a, %d %b %Y %H:%M:%S +0000')
    
    return rss

def save_rss_feed(rss_element):
    """RSS XMLファイルを保存"""
    # XMLを整形して保存
    rough_string = ET.tostring(rss_element, encoding='unicode')
    reparsed = minidom.parseString(rough_string)
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
    
    with open("rss.xml", "wb") as f:
        f.write(pretty_xml)
    
    print("RSS feed generated: rss.xml")

def generate_slack_message(all_entries, date):
    """Slack通知用のメッセージを生成"""
    # 各フィードから先頭条目を抽出。ニュース価値の自動判断は行わない。
    sample_articles = []
    
    # 設定順で記事を選択
    priority_feeds = DEFAULT_SITE_CONFIG.PRIORITY_FEEDS
    
    for feed_name in priority_feeds:
        if feed_name in all_entries and all_entries[feed_name]:
            # 各フィードから最大2件取得
            for entry in all_entries[feed_name][:2]:
                if len(sample_articles) < 6:  # 最大6件まで
                    # タイトルからHTMLタグを除去
                    clean_title = re.sub(r'<[^>]+>', '', entry.title)
                    sample_articles.append({
                        "title": clean_title,
                        "link": entry.link
                    })
    
    # 総記事数を計算
    total_articles = sum(len(entries) for entries in all_entries.values())
    
    # Slackメッセージのペイロードを生成
    sample_text = "\n".join([
        f"• <{article['link']}|{article['title']}>"
        for article in sample_articles
    ]) or "暂无可展示条目。"
    
    slack_payload = {
        "text": f"📰 {BRIEF_TITLE} ({date.isoformat()})",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📰 {BRIEF_TITLE} ({date.isoformat()})"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*自动抓取条目示例（非新闻价值判断）*\n{sample_text}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*抓取统计*: 共抓取 {total_articles} 条\n\n🔗 <{DEFAULT_SITE_CONFIG.site_url}|打开 HTML 卡片视图>\n📰 <{DEFAULT_SITE_CONFIG.github_repo_url}|GitHub 仓库>"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                            "text": "⚡ GitHub Actions 自动更新 | 缩略图查询使用缓存"
                    }
                ]
            }
        ]
    }
    
    return slack_payload

def save_slack_message(slack_payload):
    """Slackメッセージをファイルに保存"""
    with open("slack_message.json", "w", encoding="utf-8") as f:
        json.dump(slack_payload, f, ensure_ascii=False, indent=2)
    print("Slack message generated: slack_message.json")

if __name__ == "__main__":
    script_start_time = time.time()
    # Use a UTC date so scheduled GitHub Actions runs are stable across regions.
    today = datetime.datetime.now(datetime.timezone.utc).date()
    
    all_entries = {}
    for name, feed_url in FEEDS.items():
        print(f"Fetching entries from {name}...")
        entries = fetch_feed_entries(feed_url, name)
        
        for domain, label in EXCLUDED_DOMAINS.items():
            entries = filter_entries_by_domain(entries, domain, label)
        
        entries = filter_entries_by_scope(entries, name)
        
        all_entries[name] = entries
    
    # フィード間URL重複除去と補填
    print("Removing duplicate URLs across feeds...")
    all_entries = deduplicate_urls_across_feeds(all_entries)
    
    # 🚀 全サムネイルを並列取得（大幅高速化）
    start_time = time.time()
    thumbnails = fetch_all_thumbnails(all_entries)
    thumbnail_time = time.time() - start_time
    print(f"Thumbnail fetching completed in {thumbnail_time:.2f} seconds")
    
    # Markdownコンテンツ生成
    markdown_content = generate_markdown(all_entries, today.isoformat())
    
    # HTMLコンテンツ生成（事前取得済みサムネイルを使用）
    html_content = generate_html(all_entries, today.isoformat(), thumbnails)
    
    # アーカイブに保存
    archive_file = save_to_archive(all_entries, today, thumbnails)
    print(f"Archived to: {archive_file}")
    
    # インデックスページ更新
    update_monthly_index(today.year, today.month)
    update_yearly_index(today.year)
    update_archive_index()
    
    # daily_news.md更新（アーカイブリンク付き）
    daily_news_content = update_readme_with_archive_link(markdown_content)
    with open("daily_news.md", "w", encoding="utf-8") as f:
        f.write(daily_news_content)
    
    # index.html生成（カード表示用）
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Generated index.html with card layout")
    
    # RSSフィード生成
    rss_feed = generate_rss_feed(all_entries, today)
    save_rss_feed(rss_feed)
    
    # Slackメッセージ生成
    slack_message = generate_slack_message(all_entries, today)
    save_slack_message(slack_message)
        
    total_time = time.time() - script_start_time
    print(f"Successfully updated daily_news.md, index.html, archive structure, and RSS feed.")
    print(f"Total execution time: {total_time:.2f} seconds (thumbnail fetching: {thumbnail_time:.2f}s)")
