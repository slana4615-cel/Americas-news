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
from collections import OrderedDict, defaultdict
from email.utils import parsedate_to_datetime
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
    "美国": "美国",
    "Latin America": "拉丁美洲",
    "拉丁美洲": "拉丁美洲",
    "Caribbean": "加勒比地区",
    "加勒比地区": "加勒比地区",
    "Canada": "加拿大",
    "加拿大": "加拿大",
    "Think Tanks": "智库",
    "Think Tanks / Research": "智库",
    "智库": "智库",
    "International Organizations": "国际组织",
    "Regional / International Organizations": "国际组织",
    "国际组织": "国际组织",
}

OUTPUT_CATEGORY_ORDER = (
    "美国",
    "拉丁美洲",
    "加勒比地区",
    "智库",
    "国际组织",
)

SOURCE_TIERS = {
    "Tier 1": {
        "score": 100,
        "domains": (
            "reuters.com",
            "apnews.com",
            "bbc.com",
            "bbc.co.uk",
            "aljazeera.com",
            "france24.com",
            "dw.com",
            "theguardian.com",
            "elpais.com",
            "ft.com",
            "bloomberg.com",
            "economist.com",
        ),
    },
    "Tier 2": {
        "score": 75,
        "domains": (
            "americasquarterly.org",
            "thedialogue.org",
            "insightcrime.org",
            "nacla.org",
            "cepal.org",
            "oas.org",
            "iadb.org",
            "worldbank.org",
            "imf.org",
            "news.un.org",
            "un.org",
        ),
    },
    "Tier 3": {
        "score": 45,
        "domains": (
            "mercopress.com",
            "caribbeannewsglobal.com",
            "latinamericanpost.com",
            "latinamericareports.com",
        ),
    },
}

SOURCE_AUTHORITY = {
    domain: tier
    for tier, tier_config in SOURCE_TIERS.items()
    for domain in tier_config["domains"]
}

SOURCE_NAME_ALIASES = {
    "reuters": "reuters.com",
    "associated press": "apnews.com",
    "ap news": "apnews.com",
    "bbc": "bbc.com",
    "bbc news": "bbc.com",
    "al jazeera": "aljazeera.com",
    "france 24": "france24.com",
    "france24": "france24.com",
    "dw": "dw.com",
    "deutsche welle": "dw.com",
    "the guardian": "theguardian.com",
    "el pais": "elpais.com",
    "financial times": "ft.com",
    "bloomberg": "bloomberg.com",
    "the economist": "economist.com",
    "americas quarterly": "americasquarterly.org",
    "inter-american dialogue": "thedialogue.org",
    "the dialogue": "thedialogue.org",
    "insight crime": "insightcrime.org",
    "in sight crime": "insightcrime.org",
    "nacla": "nacla.org",
    "eclac": "cepal.org",
    "cepal": "cepal.org",
    "organization of american states": "oas.org",
    "oas": "oas.org",
    "inter-american development bank": "iadb.org",
    "idb": "iadb.org",
    "world bank": "worldbank.org",
    "imf": "imf.org",
    "international monetary fund": "imf.org",
    "un news": "news.un.org",
    "united nations": "un.org",
    "mercopress": "mercopress.com",
    "caribbean news global": "caribbeannewsglobal.com",
    "latin america reports": "latinamericareports.com",
    "latin american post": "latinamericanpost.com",
}

THINK_TANK_DOMAINS = {
    "americasquarterly.org",
    "thedialogue.org",
    "insightcrime.org",
    "nacla.org",
}

INTERNATIONAL_ORG_DOMAINS = {
    "cepal.org",
    "oas.org",
    "iadb.org",
    "worldbank.org",
    "imf.org",
    "news.un.org",
    "un.org",
}

def google_news_rss_url(query):
    """Build a transparent Google News RSS fallback URL for public search results."""
    return "https://news.google.com/rss/search?" + urlencode({
        "q": query,
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en",
    })

SOURCE_LABELS = {
    "BBC Latin America": "BBC",
    "BBC US & Canada": "BBC",
    "The Guardian Americas": "The Guardian",
    "The Guardian US News": "The Guardian",
    "Al Jazeera": "Al Jazeera",
    "France 24 Americas": "France 24",
    "DW Americas": "DW",
    "Americas Quarterly": "Americas Quarterly",
    "Inter-American Dialogue": "Inter-American Dialogue",
    "InSight Crime": "InSight Crime",
    "NACLA": "NACLA",
    "UN News Americas": "UN News",
    "MercoPress Latin America": "MercoPress",
    "Caribbean News Global": "Caribbean News Global",
    "Google News - Major Americas": "Google News",
    "Google News - US Americas Policy": "Google News",
    "Google News - Caribbean": "Google News",
    "Google News - Institutions": "Google News",
}

FEEDS = [
    {
        "name": "BBC Latin America",
        "url": "https://feeds.bbci.co.uk/news/world/latin_america/rss.xml",
        "category": "拉丁美洲",
        "source_label": "BBC",
    },
    {
        "name": "BBC US & Canada",
        "url": "https://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
        "category": "美国",
        "source_label": "BBC",
    },
    {
        "name": "The Guardian Americas",
        "url": "https://www.theguardian.com/world/americas/rss",
        "category": "拉丁美洲",
        "source_label": "The Guardian",
    },
    {
        "name": "The Guardian US News",
        "url": "https://www.theguardian.com/us-news/rss",
        "category": "美国",
        "source_label": "The Guardian",
    },
    {
        "name": "Al Jazeera",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "category": "拉丁美洲",
        "source_label": "Al Jazeera",
    },
    {
        "name": "France 24 Americas",
        "url": "https://www.france24.com/en/americas/rss",
        "category": "拉丁美洲",
        "source_label": "France 24",
    },
    {
        "name": "DW Americas",
        "url": "https://rss.dw.com/rdf/rss-en-americas",
        "category": "拉丁美洲",
        "source_label": "DW",
    },
    {
        "name": "Americas Quarterly",
        "url": "https://www.americasquarterly.org/feed/",
        "category": "智库",
        "source_label": "Americas Quarterly",
    },
    {
        "name": "Inter-American Dialogue",
        "url": "https://www.thedialogue.org/feed/",
        "category": "智库",
        "source_label": "Inter-American Dialogue",
    },
    {
        "name": "InSight Crime",
        "url": "https://insightcrime.org/feed/",
        "category": "智库",
        "source_label": "InSight Crime",
    },
    {
        "name": "NACLA",
        "url": "https://nacla.org/feed",
        "category": "智库",
        "source_label": "NACLA",
    },
    {
        "name": "UN News Americas",
        "url": "https://news.un.org/feed/subscribe/en/news/region/americas/feed/rss.xml",
        "category": "国际组织",
        "source_label": "UN News",
    },
    {
        "name": "MercoPress Latin America",
        "url": "https://en.mercopress.com/rss/latin-america",
        "category": "拉丁美洲",
        "source_label": "MercoPress",
    },
    {
        "name": "Caribbean News Global",
        "url": "https://caribbeannewsglobal.com/feed/",
        "category": "加勒比地区",
        "source_label": "Caribbean News Global",
    },
]

FALLBACK_FEEDS = [
    {
        "name": "Google News - Major Americas",
        "url": google_news_rss_url(
            '(site:reuters.com OR site:apnews.com OR site:bbc.com OR site:france24.com) '
            '("Latin America" OR "South America" OR "Central America" OR Mexico OR Brazil OR Argentina OR Colombia OR Peru OR Chile OR Venezuela) '
            '(politics OR election OR economy OR debt OR inflation OR migration OR sanctions OR trade OR security) when:14d'
        ),
        "category": "拉丁美洲",
        "source_label": "Google News",
    },
    {
        "name": "Google News - US Americas Policy",
        "url": google_news_rss_url(
            '(site:reuters.com OR site:apnews.com OR site:bbc.com OR site:theguardian.com) '
            '("United States" OR U.S.) ("Latin America" OR Mexico OR Caribbean OR Venezuela OR Cuba OR Haiti) '
            '(policy OR sanctions OR migration OR trade OR diplomacy OR border) when:14d'
        ),
        "category": "美国",
        "source_label": "Google News",
    },
    {
        "name": "Google News - Caribbean",
        "url": google_news_rss_url(
            '(site:reuters.com OR site:apnews.com OR site:bbc.com OR site:news.un.org OR site:france24.com) '
            '(Caribbean OR Haiti OR Cuba OR Jamaica OR Guyana OR "Dominican Republic") '
            '(politics OR economy OR security OR migration OR debt OR election OR energy) when:14d'
        ),
        "category": "加勒比地区",
        "source_label": "Google News",
    },
    {
        "name": "Google News - Institutions",
        "url": google_news_rss_url(
            '("Latin America" OR Caribbean) (IMF OR "World Bank" OR IDB OR OAS OR ECLAC OR CEPAL) '
            '(economy OR debt OR migration OR report OR election OR climate OR trade) when:30d'
        ),
        "category": "国际组织",
        "source_label": "Google News",
    },
]

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

# Candidate pool and final output controls.
CANDIDATE_LIMIT_PER_FEED = 40
TOTAL_ARTICLE_LIMIT = 25
MIN_SELECTION_SCORE = 55
MAX_ARTICLES_PER_EVENT_CLUSTER = 3
TOP_LOG_COUNT = 10
CATEGORY_MAX_COUNTS = {
    "美国": 6,
    "拉丁美洲": 8,
    "加勒比地区": 8,
    "智库": 4,
    "国际组织": 4,
}
CATEGORY_MIN_COUNTS = {
    "智库": 2,
    "国际组织": 2,
}

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

def normalize_domain(domain):
    """Normalize a host name for source-authority matching."""
    if not domain:
        return ""

    domain = domain.lower().strip()
    domain = domain.split("@")[-1]
    domain = domain.split(":")[0]
    for prefix in ("www.", "m.", "amp.", "feeds.", "rss."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain

def domain_matches(domain, configured_domain):
    """Return True when an article host belongs to a configured source domain."""
    domain = normalize_domain(domain)
    configured_domain = normalize_domain(configured_domain)
    return domain == configured_domain or domain.endswith(f".{configured_domain}")

def is_probable_media_credit(value):
    cleaned = clean_text(value) or ""
    lowered = cleaned.lower()
    return (
        cleaned.startswith("©")
        or lowered.startswith("photo:")
        or lowered.startswith("image:")
        or lowered.startswith("credit:")
        or lowered.startswith(("ap -", "afp -", "reuters -", "epa -"))
    )

def is_probable_media_url(parsed_url):
    domain = normalize_domain(parsed_url.netloc)
    path = parsed_url.path.lower()
    return (
        domain.startswith(("s.", "static.", "media.", "images."))
        or "/media/" in path
        or "/image/" in path
        or path.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"))
    )

def get_source_name_from_entry(entry):
    """Extract the publisher name from RSS metadata before falling back to feed labels."""
    if hasattr(entry, "source") and entry.source:
        source = entry.source
        if isinstance(source, dict):
            title = source.get("title")
        else:
            title = getattr(source, "title", None)
        if title and not is_probable_media_credit(title):
            return clean_text(title)

    if hasattr(entry, "source_detail") and entry.source_detail:
        title = entry.source_detail.get("title") if isinstance(entry.source_detail, dict) else None
        if title and not is_probable_media_credit(title):
            return clean_text(title)

    if hasattr(entry, "source_info") and entry.source_info:
        return clean_text(entry.source_info)

    return None

def domain_from_source_alias(source_name):
    """Resolve common RSS source names, especially Google News source titles, to domains."""
    if not source_name:
        return ""

    normalized_name = re.sub(r"\s+", " ", source_name.lower()).strip()
    if normalized_name in SOURCE_NAME_ALIASES:
        return SOURCE_NAME_ALIASES[normalized_name]

    for alias, domain in SOURCE_NAME_ALIASES.items():
        if alias in normalized_name:
            return domain

    return ""

def extract_domain_from_entry_url(entry):
    """Extract the best available publisher domain from entry URL-like fields."""
    candidate_urls = []

    if hasattr(entry, "link") and entry.link:
        candidate_urls.append(entry.link)

    if hasattr(entry, "source") and entry.source:
        source = entry.source
        href = source.get("href") if isinstance(source, dict) else getattr(source, "href", None)
        if href:
            candidate_urls.append(href)

    if hasattr(entry, "source_detail") and entry.source_detail:
        href = entry.source_detail.get("href") if isinstance(entry.source_detail, dict) else None
        if href:
            candidate_urls.append(href)

    for candidate_url in candidate_urls:
        try:
            parsed = urlparse(candidate_url)
            domain = normalize_domain(parsed.netloc)
            if (
                domain
                and domain not in {"news.google.com", "google.com"}
                and not is_probable_media_url(parsed)
            ):
                return domain
        except Exception:
            continue

    return ""

def get_entry_domain(entry):
    """Return a canonical publisher domain for scoring."""
    domain = extract_domain_from_entry_url(entry)
    if domain:
        return domain

    source_name = get_source_name_from_entry(entry)
    alias_domain = domain_from_source_alias(source_name)
    if alias_domain:
        return alias_domain

    return ""

def match_configured_domain(domain, domains):
    for configured_domain in domains:
        if domain_matches(domain, configured_domain):
            return configured_domain
    return None

def get_source_authority(domain):
    """Map a domain to source tier and numeric authority score."""
    normalized_domain = normalize_domain(domain)
    for tier, tier_config in SOURCE_TIERS.items():
        if match_configured_domain(normalized_domain, tier_config["domains"]):
            return tier, tier_config["score"]
    return "Unknown", 20

def get_entry_source_tier(entry):
    return getattr(entry, "source_authority_tier", "Unknown")

def get_entry_total_score(entry):
    return getattr(entry, "total_score", None)

def filter_entries_by_domain(entries, domain, label):
    filtered_entries = []
    excluded_count = 0
    
    for entry in entries:
        entry_domain = get_entry_domain(entry)
        entry_link = getattr(entry, "link", "")
        if (
            (entry_domain and domain_matches(entry_domain, domain))
            or (entry_link and domain in entry_link)
        ):
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
    "weather forecast", "world cup", "premier league", "playoff",
    "tournament", "concert", "singer", "song", "artist", "eurovision",
    "shakira", "neymar", "prayer rally", "mass prayer",
    "christian origins",
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

CARIBBEAN_ENTITY_KEYWORDS = (
    "caribbean", "haiti", "cuba", "dominican republic", "jamaica",
    "barbados", "trinidad", "tobago", "guyana", "suriname", "belize",
    "bahamas", "grenada", "antigua", "barbuda", "saint lucia",
    "st. lucia", "st lucia", "st. vincent", "saint vincent",
    "st. kitts", "saint kitts",
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
    "protest", "protests", "protester", "demonstration", "strike",
    "blockade", "clash", "clashes", "violence", "gang", "cartel",
    "police", "homicide", "trafficking", "drug charges", "indict",
    "indictment", "prosecute", "prosecution", "criminal charges",
    "justice department", "doj", "lawsuit", "corruption",
    "humanitarian aid", "blackout", "energy crisis", "military action",
    "invasion", "war", "conflict", "armed attack", "shooting", "killed",
    "dead", "displacement", "drug", "narcotics", "political prisoner",
    "political prisoners", "human rights", "rights", "disappearances",
    "impunity", "hunger", "threat", "drone", "drones", "executive order",
    "pressure", "investigation", "investigated", "officials", "freeze",
    "freezes", "export", "exports",
)

US_DOMESTIC_ENTITY_KEYWORDS = (
    "united states", "u.s.", "us", "usa", "american", "white house",
    "congress", "senate", "house of representatives", "supreme court",
    "federal reserve", "fed", "treasury", "treasury department",
    "department of homeland security", "dhs", "trump administration",
    "biden administration", "california", "san diego", "new york",
    "washington", "philadelphia", "pennsylvania", "kentucky", "texas",
    "florida",
)

US_DOMESTIC_POLITICS_ECONOMY_KEYWORDS = (
    "u.s. congress", "us congress", "white house", "congress", "senate",
    "house of representatives", "federal reserve", "fed", "rate cut",
    "treasury", "dhs", "department of homeland security", "supreme court",
    "election", "midterm", "vote", "voter", "border", "immigration",
    "budget", "inflation", "jobs", "tax", "tariff", "interest rate",
    "trump administration", "biden administration", "shooting",
    "hate crime", "crime", "police",
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

def has_valid_americas_scope(text):
    return (
        contains_any(text, LATIN_AMERICA_ENTITY_KEYWORDS)
        or contains_any(text, CARIBBEAN_ENTITY_KEYWORDS)
        or is_us_domestic_politics_or_economy(text)
    )

def get_scope_exclusion_reason(entry):
    text = entry_search_text(entry)
    title_text = clean_text(getattr(entry, "title", None)) or ""

    if not text:
        return "缺少可检索文本"

    has_latin_america_entity = contains_any(text, LATIN_AMERICA_ENTITY_KEYWORDS)
    is_us_domestic_entry = is_us_domestic_politics_or_economy(text)
    has_americas_scope = has_valid_americas_scope(text)

    if (
        contains_any(title_text, CANADA_KEYWORDS)
        or (contains_any(text, CANADA_KEYWORDS) and not has_latin_america_entity)
    ):
        return "加拿大内容暂不纳入当前抓取范围"

    if contains_any(title_text, NOISE_KEYWORDS):
        return "噪音主题"

    if (
        contains_any(text, NON_AMERICAS_KEYWORDS)
        and not has_americas_scope
    ):
        return "非美洲主题"

    has_target_region = (
        contains_any(text, TARGET_REGION_KEYWORDS)
        or has_latin_america_entity
        or is_us_domestic_entry
    )
    has_politics_or_economy = contains_any(text, POLITICS_ECONOMY_KEYWORDS)

    if not has_target_region:
        return "未命中美洲地区关键词"
    if not has_politics_or_economy:
        return "未命中政治经济关键词"

    return None

def should_keep_entry(entry):
    return get_scope_exclusion_reason(entry) is None

def filter_entries_by_scope(entries, feed_name):
    filtered_entries = []
    excluded_items = []

    for entry in entries:
        reason = get_scope_exclusion_reason(entry)
        if reason is None:
            filtered_entries.append(entry)
            continue

        title = clean_text(getattr(entry, "title", None)) or getattr(entry, "link", None) or "未提供标题"
        excluded_items.append((title, reason))

    if excluded_items:
        print(f"Scope filter excluded {len(excluded_items)} entries from {feed_name}")
        for title, reason in excluded_items[:20]:
            print(f"范围过滤: [{feed_name}] {reason}: {title}")
        if len(excluded_items) > 20:
            print(f"范围过滤: [{feed_name}] 另有 {len(excluded_items) - 20} 条已省略")

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
            title = source.get('title')
            if not is_probable_media_credit(title):
                return clean_text(title)
        if hasattr(source, 'title') and source.title:
            if not is_probable_media_credit(source.title):
                return clean_text(source.title)
    if hasattr(entry, 'source_detail') and entry.source_detail and entry.source_detail.get('title'):
        title = entry.source_detail.get('title')
        if not is_probable_media_credit(title):
            return clean_text(title)
    if hasattr(entry, 'source_info') and entry.source_info:
        return entry.source_info
    if feed_name in SOURCE_LABELS:
        return SOURCE_LABELS[feed_name]
    if hasattr(entry, 'link') and entry.link:
        netloc = urlparse(entry.link).netloc.replace('www.', '')
        return netloc or feed_name
    return feed_name

def get_entry_datetime(entry):
    """Return a timezone-aware UTC datetime when RSS metadata provides one."""
    parsed_date = (
        getattr(entry, 'published_parsed', None)
        or getattr(entry, 'updated_parsed', None)
        or getattr(entry, 'created_parsed', None)
    )
    if parsed_date:
        try:
            return datetime.datetime(*parsed_date[:6], tzinfo=datetime.timezone.utc)
        except Exception:
            pass

    for field in ('published', 'updated', 'created'):
        value = getattr(entry, field, None)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(str(value))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            return parsed.astimezone(datetime.timezone.utc)
        except Exception:
            continue

    return None

def entry_age_days(entry, now):
    published = get_entry_datetime(entry)
    if not published:
        return None
    return max(0, (now - published).total_seconds() / 86400)

def matched_keywords(text, keywords):
    return {
        keyword for keyword in keywords
        if contains_any(text, (keyword,))
    }

_TITLE_STOPWORDS = frozenset({
    "about", "after", "again", "against", "amid", "among", "before",
    "being", "between", "could", "from", "have", "into", "more",
    "over", "said", "says", "than", "that", "their", "there", "this",
    "through", "under", "while", "with", "will", "would", "latin",
    "america", "american", "caribbean", "united", "states",
})

def title_tokens(title):
    cleaned = clean_text(title) or ""
    tokens = re.findall(r"[a-zA-Z][a-zA-Z'-]{3,}", cleaned.lower())
    return {
        token.strip("-'")
        for token in tokens
        if token.strip("-'") and token.strip("-'") not in _TITLE_STOPWORDS
    }

def score_recency(entry, now):
    """Score recent articles higher while still allowing slower institutional posts."""
    age = entry_age_days(entry, now)
    if age is None:
        return 4
    if age <= 1:
        return 25
    if age <= 3:
        return 22
    if age <= 7:
        return 16
    if age <= 14:
        return 10
    if age <= 30:
        return 5
    if age <= 60:
        return 2
    return 0

def score_americas_relevance(text):
    region_matches = matched_keywords(text, TARGET_REGION_KEYWORDS)
    latin_matches = matched_keywords(text, LATIN_AMERICA_ENTITY_KEYWORDS)
    caribbean_matches = matched_keywords(text, CARIBBEAN_ENTITY_KEYWORDS)

    score = 0
    if latin_matches:
        score += 12
    if caribbean_matches:
        score += 4
    if is_us_domestic_politics_or_economy(text):
        score += 10
    score += min(len(region_matches | latin_matches) * 2, 11)

    return min(score, 25), region_matches | latin_matches | caribbean_matches

def score_politics_economy_relevance(text):
    topic_matches = matched_keywords(text, POLITICS_ECONOMY_KEYWORDS)
    return min(len(topic_matches) * 3, 20), topic_matches

def score_noise_penalty(entry, text, now):
    """Penalize topics and stale items that pass the first-stage filter but are weak fits."""
    penalty = 0
    title_text = clean_text(getattr(entry, "title", None)) or ""

    if contains_any(title_text, NOISE_KEYWORDS):
        penalty += 40
    elif contains_any(text, NOISE_KEYWORDS):
        penalty += 12

    if contains_any(text, NON_AMERICAS_KEYWORDS) and not has_valid_americas_scope(text):
        penalty += 25

    age = entry_age_days(entry, now)
    domain = get_entry_domain(entry)
    is_think_tank = (
        match_configured_domain(domain, THINK_TANK_DOMAINS)
        or getattr(entry, "feed_category", "") == "智库"
    )

    if age is not None:
        if age > 60:
            penalty += 35
        elif age > 30:
            penalty += 20

        # Think-tank feeds often publish evergreen posts; keep them visible only
        # when still fresh enough for a daily monitoring product.
        if is_think_tank and age > 45:
            penalty += 45
        elif is_think_tank and age > 21:
            penalty += 25

    return penalty

def apply_source_metadata(entry):
    domain = get_entry_domain(entry)
    tier, source_score = get_source_authority(domain)
    entry.source_domain = domain or "unknown"
    entry.source_authority_tier = tier
    entry.source_authority_score = source_score
    return entry

def score_article(entry, now):
    """Score an article by authority, freshness, Americas fit, policy/economy fit and noise.

    Formula:
        total_score =
            source_authority_score
            + recency_score
            + americas_relevance_score
            + politics_economy_relevance_score
            + cross_source_bonus
            - noise_penalty
    """
    apply_source_metadata(entry)
    text = entry_search_text(entry)
    recency = score_recency(entry, now)
    americas_relevance, region_matches = score_americas_relevance(text)
    politics_economy, topic_matches = score_politics_economy_relevance(text)
    noise_penalty = score_noise_penalty(entry, text, now)
    cross_source_bonus = getattr(entry, "cross_source_bonus", 0)

    total_score = (
        entry.source_authority_score
        + recency
        + americas_relevance
        + politics_economy
        + cross_source_bonus
        - noise_penalty
    )

    entry.search_text = text
    entry.region_matches = region_matches
    entry.topic_matches = topic_matches
    entry.title_tokens = title_tokens(getattr(entry, "title", ""))
    entry.score_breakdown = {
        "source_authority": entry.source_authority_score,
        "recency": recency,
        "americas_relevance": americas_relevance,
        "politics_economy_relevance": politics_economy,
        "cross_source_bonus": cross_source_bonus,
        "noise_penalty": noise_penalty,
    }
    entry.total_score = round(total_score, 1)
    return entry.total_score

def articles_are_similar(entry_a, entry_b, now, max_days_apart=7):
    domain_a = getattr(entry_a, "source_domain", get_entry_domain(entry_a))
    domain_b = getattr(entry_b, "source_domain", get_entry_domain(entry_b))
    if domain_a and domain_b and domain_a == domain_b:
        return False

    date_a = get_entry_datetime(entry_a)
    date_b = get_entry_datetime(entry_b)
    if date_a and date_b:
        days_apart = abs((date_a - date_b).total_seconds()) / 86400
        if days_apart > max_days_apart:
            return False

    shared_regions = getattr(entry_a, "region_matches", set()) & getattr(entry_b, "region_matches", set())
    shared_topics = getattr(entry_a, "topic_matches", set()) & getattr(entry_b, "topic_matches", set())
    tokens_a = getattr(entry_a, "title_tokens", set())
    tokens_b = getattr(entry_b, "title_tokens", set())
    shared_title_tokens = tokens_a & tokens_b
    smaller_title_set = max(1, min(len(tokens_a), len(tokens_b)))
    title_overlap = len(shared_title_tokens) / smaller_title_set

    if shared_regions and (shared_topics or title_overlap >= 0.25):
        return True
    if title_overlap >= 0.4 and (shared_regions or shared_topics):
        return True
    return False

def apply_cross_source_bonuses(entries, now):
    """Add a capped bonus when independent sources appear to cover the same event."""
    bonuses = defaultdict(int)

    for index, entry_a in enumerate(entries):
        for entry_b in entries[index + 1:]:
            if articles_are_similar(entry_a, entry_b, now):
                bonuses[id(entry_a)] += 5
                bonuses[id(entry_b)] += 5

    for entry in entries:
        entry.cross_source_bonus = min(bonuses[id(entry)], 20)

_GOOGLE_NEWS_SOURCE_SUFFIX_PATTERN = re.compile(r"\s+[-–—]\s+([^-–—]{2,80})$")

def normalize_source_suffix(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()

def is_google_news_entry(entry):
    feed_name = clean_text(getattr(entry, "feed_name", None)) or ""
    source_info = clean_text(getattr(entry, "source_info", None)) or ""
    if feed_name.startswith("Google News") or source_info == "Google News":
        return True

    for field in ("feed_url", "link"):
        value = getattr(entry, field, None)
        if value and normalize_domain(urlparse(str(value)).netloc) == "news.google.com":
            return True

    return False

def is_known_google_news_source_suffix(suffix):
    if domain_from_source_alias(suffix):
        return True

    normalized_suffix = normalize_source_suffix(suffix)
    known_labels = {
        normalize_source_suffix(source_name)
        for source_name in SOURCE_LABELS.values()
    }
    return normalized_suffix in known_labels

def strip_google_news_source_suffix(title):
    cleaned = clean_text(title) or ""
    match = _GOOGLE_NEWS_SOURCE_SUFFIX_PATTERN.search(cleaned)
    if not match:
        return cleaned

    suffix = match.group(1).strip()
    if is_known_google_news_source_suffix(suffix):
        return cleaned[:match.start()].strip()

    return cleaned

def title_fingerprint(title, strip_source_suffix=False):
    if strip_source_suffix:
        title = strip_google_news_source_suffix(title)

    tokens = title_tokens(title)
    if not tokens:
        cleaned = clean_text(title) or ""
        return re.sub(r"[^a-z0-9]+", "", cleaned.lower())[:80]
    return " ".join(sorted(tokens))

def deduplicate_candidate_entries(entries):
    """Remove duplicate URLs and repeated source-title pairs before scoring."""
    seen_urls = set()
    seen_source_titles = set()
    unique_entries = []
    removed_by_url = 0
    removed_by_title = 0

    for entry in entries:
        link = getattr(entry, "link", "")
        normalized_link = normalize_url(link) if link else ""
        domain = get_entry_domain(entry) or "unknown"
        title_key = (
            domain,
            title_fingerprint(
                getattr(entry, "title", ""),
                strip_source_suffix=is_google_news_entry(entry),
            ),
        )

        if normalized_link and normalized_link in seen_urls:
            removed_by_url += 1
            continue
        if title_key[1] and title_key in seen_source_titles:
            removed_by_title += 1
            continue

        if normalized_link:
            seen_urls.add(normalized_link)
        seen_source_titles.add(title_key)
        unique_entries.append(entry)

    removed_total = removed_by_url + removed_by_title
    print(
        "Candidate deduplication removed "
        f"{removed_total} entries ({removed_by_url} by URL, {removed_by_title} by source/title)"
    )
    return unique_entries

def determine_article_category(entry):
    """Assign the output category after ranking, independent of the original feed."""
    domain = getattr(entry, "source_domain", get_entry_domain(entry))
    text = getattr(entry, "search_text", None) or entry_search_text(entry)

    if match_configured_domain(domain, THINK_TANK_DOMAINS) or getattr(entry, "feed_category", "") == "智库":
        return "智库"
    if match_configured_domain(domain, INTERNATIONAL_ORG_DOMAINS) or getattr(entry, "feed_category", "") == "国际组织":
        return "国际组织"
    if contains_any(text, CARIBBEAN_ENTITY_KEYWORDS):
        return "加勒比地区"
    if contains_any(text, LATIN_AMERICA_ENTITY_KEYWORDS):
        return "拉丁美洲"
    if is_us_domestic_politics_or_economy(text):
        return "美国"

    return getattr(entry, "feed_category", "拉丁美洲") or "拉丁美洲"

def max_articles_for_domain(entry):
    tier = get_entry_source_tier(entry)
    if tier == "Tier 1":
        return 6
    if tier == "Tier 2":
        return 5
    if tier == "Tier 3":
        return 3
    return 2

def ensure_minimum_category_counts(selected, ranked_entries, total_limit):
    """Backfill institutional/research categories when strong candidates exist."""
    selected = list(selected)
    selected_ids = {id(entry) for entry in selected}

    def count_categories(entries):
        counts = defaultdict(int)
        for item in entries:
            counts[determine_article_category(item)] += 1
        return counts

    category_counts = count_categories(selected)

    for category, minimum_count in CATEGORY_MIN_COUNTS.items():
        while category_counts[category] < minimum_count:
            candidate = next(
                (
                    entry for entry in ranked_entries
                    if id(entry) not in selected_ids
                    and determine_article_category(entry) == category
                    and (get_entry_total_score(entry) or 0) >= MIN_SELECTION_SCORE
                ),
                None,
            )
            if candidate is None:
                break

            if len(selected) < total_limit:
                selected.append(candidate)
                selected_ids.add(id(candidate))
                category_counts[category] += 1
                continue

            replaceable_entries = [
                entry for entry in selected
                if category_counts[determine_article_category(entry)] > CATEGORY_MIN_COUNTS.get(determine_article_category(entry), 0)
            ]
            if not replaceable_entries:
                break

            replacement = min(
                replaceable_entries,
                key=lambda entry: get_entry_total_score(entry) or -999,
            )
            selected.remove(replacement)
            selected_ids.remove(id(replacement))
            category_counts[determine_article_category(replacement)] -= 1
            selected.append(candidate)
            selected_ids.add(id(candidate))
            category_counts[category] += 1

    return selected

def select_top_articles(entries, total_limit=TOTAL_ARTICLE_LIMIT, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    ranked_entries = sorted(
        entries,
        key=lambda entry: (
            get_entry_total_score(entry) if get_entry_total_score(entry) is not None else -999,
            get_entry_datetime(entry) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
        ),
        reverse=True,
    )

    selected = []
    domain_counts = defaultdict(int)
    category_counts = defaultdict(int)
    skipped_low_score = 0
    skipped_domain_cap = 0
    skipped_event_cap = 0
    skipped_category_cap = 0

    for entry in ranked_entries:
        score = get_entry_total_score(entry) or 0
        if score < MIN_SELECTION_SCORE:
            skipped_low_score += 1
            continue

        category = determine_article_category(entry)
        if category_counts[category] >= CATEGORY_MAX_COUNTS.get(category, total_limit):
            skipped_category_cap += 1
            continue

        domain = getattr(entry, "source_domain", "unknown") or "unknown"
        if domain_counts[domain] >= max_articles_for_domain(entry):
            skipped_domain_cap += 1
            continue

        similar_selected_count = sum(
            1 for selected_entry in selected
            if articles_are_similar(entry, selected_entry, now)
        )
        if similar_selected_count >= MAX_ARTICLES_PER_EVENT_CLUSTER:
            skipped_event_cap += 1
            continue

        selected.append(entry)
        domain_counts[domain] += 1
        category_counts[category] += 1

        if len(selected) >= total_limit:
            break

    if not selected and ranked_entries:
        selected = ranked_entries[:min(10, total_limit)]

    selected = ensure_minimum_category_counts(selected, ranked_entries, total_limit)
    selected = sorted(
        selected,
        key=lambda entry: (
            get_entry_total_score(entry) if get_entry_total_score(entry) is not None else -999,
            get_entry_datetime(entry) or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc),
        ),
        reverse=True,
    )

    print(
        f"Selected {len(selected)} articles "
        f"(skipped {skipped_low_score} below score threshold, "
        f"{skipped_domain_cap} by source cap, {skipped_event_cap} by event cap, "
        f"{skipped_category_cap} by category cap)"
    )
    return selected, ranked_entries

def group_entries_by_category(entries):
    grouped = OrderedDict((category, []) for category in OUTPUT_CATEGORY_ORDER)
    for entry in entries:
        category = determine_article_category(entry)
        entry.output_category = category
        grouped.setdefault(category, []).append(entry)
    return grouped

def log_top_articles(entries, limit=TOP_LOG_COUNT):
    print(f"Top {min(limit, len(entries))} scored articles:")
    for index, entry in enumerate(entries[:limit], start=1):
        source = get_entry_source(entry, getattr(entry, "feed_name", ""))
        title = clean_text(getattr(entry, "title", "")) or "未提供标题"
        print(
            f"{index}. score={get_entry_total_score(entry)} "
            f"source={source} tier={get_entry_source_tier(entry)} "
            f"domain={getattr(entry, 'source_domain', 'unknown')} title={title}"
        )

def format_markdown_entry(entry, feed_name):
    """Render one RSS entry in the fixed Chinese research-screening format."""
    title = clean_text(getattr(entry, 'title', '')) or "未提供"
    link = getattr(entry, 'link', '') or "未提供"
    source = get_entry_source(entry, feed_name) or "未提供"
    source_tier = get_entry_source_tier(entry)
    total_score = get_entry_total_score(entry)
    published = get_entry_published(entry)
    category = get_category_label(feed_name)
    summary = get_entry_summary(entry)

    item = (
        f"- **原标题**：{title}\n"
        f"  - **来源**：{source}\n"
        f"  - **来源级别**：{source_tier}\n"
        f"  - **评分**：{total_score if total_score is not None else '未评分'}\n"
        f"  - **发布时间**：{published}\n"
        f"  - **地区分类**：{category}\n"
        f"  - **原文链接**：{link}\n"
    )
    if summary:
        item += f"  - **原文摘要**：{summary}\n"
    return item

def fetch_feed_entries(feed_url, feed_name=None):
    """指定されたURLからRSSフィードのエントリーを取得する"""
    feed_config = feed_url if isinstance(feed_url, dict) else None
    if feed_config:
        feed_url = feed_config["url"]
        feed_name = feed_config["name"]

    try:
        feed = feedparser.parse(feed_url)
        if getattr(feed, "bozo", False):
            print(f"Warning: feed parser reported a problem for {feed_name}: {getattr(feed, 'bozo_exception', '')}")
        feed_title = clean_text(feed.feed.get('title')) if feed.feed else None
        fallback_source = (
            (feed_config or {}).get("source_label")
            or SOURCE_LABELS.get(feed_name)
            or feed_title
            or urlparse(feed_url).netloc
        )
        feed_category = (feed_config or {}).get("category") or get_category_label(feed_name)
        
        # 各エントリに著者情報を追加
        for entry in feed.entries:
            entry.author_info = extract_author_info(entry)
            entry.source_info = fallback_source
            entry.feed_name = feed_name
            entry.feed_category = feed_category
            entry.feed_url = feed_url
            entry.source_info = get_entry_source(entry, feed_name) or fallback_source
        
        return feed.entries[:CANDIDATE_LIMIT_PER_FEED]
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
            source_tier = get_entry_source_tier(entry)
            total_score = get_entry_total_score(entry)
            item = ET.SubElement(channel, 'item')
            # RSSタイトルはプレーンテキストのみ（HTMLタグや絵文字を除去）
            clean_title = re.sub(r'<[^>]+>', '', entry.title)  # HTMLタグを除去
            ET.SubElement(item, 'title').text = clean_title
            ET.SubElement(item, 'link').text = entry.link
            score_text = total_score if total_score is not None else "未评分"
            ET.SubElement(item, 'description').text = (
                f'地区分类：{category}；来源：{source}；来源级别：{source_tier}；'
                f'评分：{score_text}；原标题：{clean_title}'
            )
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
    scoring_now = datetime.datetime.now(datetime.timezone.utc)
    
    candidate_entries = []
    feed_configs = FEEDS + FALLBACK_FEEDS

    for feed_config in feed_configs:
        name = feed_config["name"]
        print(f"Fetching entries from {name}...")
        entries = fetch_feed_entries(feed_config)
        fetched_count = len(entries)
        print(f"Fetched {fetched_count} candidates from {name}")
        
        for domain, label in EXCLUDED_DOMAINS.items():
            entries = filter_entries_by_domain(entries, domain, label)
        
        before_scope_count = len(entries)
        entries = filter_entries_by_scope(entries, name)
        print(
            f"Scope filter kept {len(entries)} of {before_scope_count} "
            f"post-domain-filter candidates from {name}"
        )
        candidate_entries.extend(entries)

    print(f"Collected {len(candidate_entries)} scoped candidates before deduplication")
    candidate_entries = deduplicate_candidate_entries(candidate_entries)

    for entry in candidate_entries:
        score_article(entry, scoring_now)

    apply_cross_source_bonuses(candidate_entries, scoring_now)

    for entry in candidate_entries:
        score_article(entry, scoring_now)

    selected_entries, ranked_entries = select_top_articles(candidate_entries, now=scoring_now)
    log_top_articles(ranked_entries)
    all_entries = group_entries_by_category(selected_entries)
    
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
