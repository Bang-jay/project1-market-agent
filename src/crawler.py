"""
Market Agent Crawler (src/crawler.py)
Collects market, technology, competitor, and government policy data based on config/company_profile.yaml and logs/source_plan.md.
"""

import os
import sys
import re
import csv
import html
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
import urllib.parse
import xml.etree.ElementTree as ET

import requests
import yaml
import pandas as pd

# Setup logging
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "crawler.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Crawler")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}
REQUEST_TIMEOUT = 12

def clean_html(text: str) -> str:
    """Strip HTML tags and unescape HTML entities."""
    if not text:
        return ""
    clean = re.sub(r"<[^>]+>", "", text)
    clean = html.unescape(clean)
    return re.sub(r"\s+", " ", clean).strip()

def parse_date(date_str: str) -> str:
    """Parse various date strings into YYYY-MM-DD."""
    if not date_str:
        return datetime.now().strftime("%Y-%m-%d")
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
    try:
        m = re.search(r"(\d{4})[-/.](\d{2})[-/.](\d{2})", date_str)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    except Exception:
        pass
    return datetime.now().strftime("%Y-%m-%d")

def load_company_profile(profile_path: str) -> dict:
    """Load configuration from YAML."""
    if not os.path.exists(profile_path):
        logger.warning(f"Profile file not found at {profile_path}, using defaults.")
        return {}
    with open(profile_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

class MarketCrawler:
    def __init__(self, config_path: str = "config/company_profile.yaml"):
        full_config_path = os.path.join(BASE_DIR, config_path)
        self.config = load_company_profile(full_config_path)
        self.company_name = self.config.get("company_name", "NovaFactory AI")
        self.competitors = self.config.get("competitors", ["VisionForge", "InspectAI", "FactoryMind", "QualiBot"])
        self.interest_keywords = self.config.get("interest_keywords", ["AI", "스마트팩토리", "품질검사", "자동화", "클라우드", "제조 AX"])
        self.funding_keywords = self.config.get("funding_keywords", ["창업지원", "AI 바우처", "스마트공장", "R&D", "사업화 자금"])
        
        self.results = []
        self.seen_urls = set()
        self.seen_titles = set()
        self.failed_sources = []
        self.successful_sources = []
        self.article_counter = 1

    def _is_duplicate(self, title: str, url: str) -> bool:
        clean_t = re.sub(r"[\s\W_]+", "", title).lower()
        if url in self.seen_urls or clean_t in self.seen_titles:
            return True
        self.seen_urls.add(url)
        self.seen_titles.add(clean_t)
        return False

    def _add_article(self, title: str, url: str, source_name: str, category: str, content: str, date_str: str, keywords: str, company_tag: str = ""):
        title = clean_html(title)
        content = clean_html(content)
        url = url.strip() if url else ""
        
        if not title or not url or len(title) < 5:
            return False
            
        if self._is_duplicate(title, url):
            return False

        summary = content[:200] + ("..." if len(content) > 200 else "") if content else title
        now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+09:00")
        
        article = {
            "article_id": f"LIVE-{self.article_counter:04d}",
            "category": category,
            "title": title,
            "date": parse_date(date_str),
            "content": content if content else title,
            "summary": summary,
            "source_url": url,
            "source_name": source_name,
            "company_tag": company_tag,
            "keywords": keywords,
            "collected_at": now_iso,
            "has_null": "false",
            "is_duplicate_seed": "false",
            "data_origin": "live"
        }
        self.article_counter += 1
        self.results.append(article)
        return True

    def crawl_google_news_query(self, query: str, category: str, source_label: str, keywords_tag: str, company_tag: str = ""):
        """Crawl Google News RSS for a specific search query."""
        source_id = f"Google News RSS ({source_label}: '{query}')"
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        try:
            logger.info(f"Crawling {source_id}...")
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            count = 0
            for item in items:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                desc = item.findtext("description", "")
                source_elem = item.find("source")
                publisher = source_elem.text if source_elem is not None and source_elem.text else "Google News"
                
                # Check for competitor match in title
                matched_company = company_tag
                if not matched_company:
                    for comp in self.competitors:
                        if comp.lower() in title.lower():
                            matched_company = comp
                            break

                added = self._add_article(
                    title=title,
                    url=link,
                    source_name=publisher,
                    category=category,
                    content=desc,
                    date_str=pub_date,
                    keywords=keywords_tag,
                    company_tag=matched_company
                )
                if added:
                    count += 1
            logger.info(f"-> {source_id}: collected {count} articles")
            self.successful_sources.append((source_id, count))
        except Exception as e:
            logger.warning(f"Failed to crawl {source_id}: {e}")
            self.failed_sources.append((source_id, str(e)))

    def crawl_ai_times(self):
        """Crawl AI Times RSS feed."""
        source_id = "AI Times RSS"
        url = "https://www.aitimes.com/rss/allArticle.xml"
        try:
            logger.info(f"Crawling {source_id}...")
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            count = 0
            for item in items:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                desc = item.findtext("description", "")
                added = self._add_article(
                    title=title,
                    url=link,
                    source_name="AI Times",
                    category="tech",
                    content=desc,
                    date_str=pub_date,
                    keywords="AI|인공지능|산업동향"
                )
                if added:
                    count += 1
            logger.info(f"-> {source_id}: collected {count} articles")
            self.successful_sources.append((source_id, count))
        except Exception as e:
            logger.warning(f"Failed to crawl {source_id}: {e}")
            self.failed_sources.append((source_id, str(e)))

    def crawl_zdnet_korea(self):
        """Crawl ZDNet Korea RSS feed (intentionally tests mirror fallback and failure handling)."""
        source_id = "ZDNet Korea RSS"
        urls = [
            "http://feeds.feedburner.com/zdnetkorea",
            "https://zdnet.co.kr/rss/"
        ]
        success = False
        for url in urls:
            try:
                logger.info(f"Crawling {source_id} via {url}...")
                resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                root = ET.fromstring(resp.content)
                items = root.findall(".//item")
                count = 0
                for item in items:
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    pub_date = item.findtext("pubDate", "")
                    desc = item.findtext("description", "")
                    added = self._add_article(
                        title=title,
                        url=link,
                        source_name="ZDNet Korea",
                        category="market",
                        content=desc,
                        date_str=pub_date,
                        keywords="IT|스마트팩토리|클라우드"
                    )
                    if added:
                        count += 1
                logger.info(f"-> {source_id}: collected {count} articles")
                self.successful_sources.append((source_id, count))
                success = True
                break
            except Exception as e:
                logger.warning(f"Sub-source {url} failed: {e}")
                continue
        if not success:
            self.failed_sources.append((source_id, "All mirror URLs failed (404 / entity error)"))

    def crawl_cio_korea(self):
        """Crawl CIO Korea RSS feed (alternative verified RSS)."""
        source_id = "CIO Korea RSS"
        url = "https://www.ciokorea.com/rss/feed/index.php"
        try:
            logger.info(f"Crawling {source_id}...")
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            items = root.findall(".//item")
            count = 0
            for item in items:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                pub_date = item.findtext("pubDate", "")
                desc = item.findtext("description", "")
                added = self._add_article(
                    title=title,
                    url=link,
                    source_name="CIO Korea",
                    category="market",
                    content=desc,
                    date_str=pub_date,
                    keywords="엔터프라이즈IT|클라우드|제조DX"
                )
                if added:
                    count += 1
            logger.info(f"-> {source_id}: collected {count} articles")
            self.successful_sources.append((source_id, count))
        except Exception as e:
            logger.warning(f"Failed to crawl {source_id}: {e}")
            self.failed_sources.append((source_id, str(e)))

    def crawl_arxiv_api(self, max_results: int = 50):
        """Crawl ArXiv API for vision AI and defect detection papers."""
        source_id = "ArXiv API (Defect Detection & Vision AI)"
        query = "all:defect+detection+OR+all:manufacturing+inspection"
        url = f"http://export.arxiv.org/api/query?search_query={query}&start=0&max_results={max_results}"
        try:
            logger.info(f"Crawling {source_id}...")
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            root = ET.fromstring(resp.content)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            entries = root.findall(".//atom:entry", ns)
            count = 0
            for entry in entries:
                title = entry.findtext("atom:title", "", ns)
                link = entry.findtext("atom:id", "", ns)
                pub_date = entry.findtext("atom:published", "", ns)
                summary = entry.findtext("atom:summary", "", ns)
                added = self._add_article(
                    title=f"[R&D] {title}",
                    url=link,
                    source_name="ArXiv",
                    category="tech",
                    content=summary,
                    date_str=pub_date,
                    keywords="컴퓨터비전|불량탐지|R&D"
                )
                if added:
                    count += 1
            logger.info(f"-> {source_id}: collected {count} papers")
            self.successful_sources.append((source_id, count))
        except Exception as e:
            logger.warning(f"Failed to crawl {source_id}: {e}")
            self.failed_sources.append((source_id, str(e)))

    def run_primary_sources(self):
        """Execute Stage 1: Primary source crawling covering market, tech, competitor, policy."""
        logger.info("=== Stage 1: Crawling Primary Sources ===")
        
        # 1. Market Trends
        self.crawl_google_news_query("스마트팩토리 시장 전망 OR 제조업 AI 시장", "market", "Market Trends", "스마트팩토리|시장규모|동향")
        
        # 2. Tech & Defect Vision Trends
        self.crawl_google_news_query("스마트팩토리 AI", "tech", "Tech Trends", "스마트팩토리|AI")
        self.crawl_google_news_query("제조업 비전 품질검사", "tech", "Quality Vision", "품질검사|머신비전")
        self.crawl_google_news_query("머신비전 불량탐지", "tech", "Defect Detection", "불량탐지|비전AI")
        
        # 3. Competitors & Industry
        comp_query = " OR ".join(self.competitors)
        self.crawl_google_news_query(comp_query, "competitor", "Named Competitors", "경쟁사|동향")
        self.crawl_google_news_query("머신비전 검사 솔루션 기업 OR 스마트팩토리 전문기업", "competitor", "Industry Competitors", "비전검사|솔루션기업")
        
        # 4. Policy & Funding Subsidies
        self.crawl_google_news_query("AI 바우처 OR 스마트공장 지원사업", "policy", "Policy & Funding", "AI바우처|스마트공장|지원사업")
        self.crawl_google_news_query("제조 중소기업 R&D 지원", "policy", "R&D Subsidies", "R&D|정부지원|제조업")

        # 5. Marketing AI Domain (Target: 50~100 articles)
        self.crawl_google_news_query("생성형 AI 마케팅 OR 마케팅 자동화 솔루션", "marketing", "AI Marketing Automation", "AI마케팅|자동화|생성형AI")
        self.crawl_google_news_query("애드테크 OR 퍼포먼스 마케팅 AI OR 디지털 광고 AI", "marketing", "AdTech & Performance Marketing", "애드테크|디지털마케팅|광고AI")
        self.crawl_google_news_query("고객 데이터 플랫폼 CDP OR AI CRM 마케팅", "marketing", "Customer Analytics & CRM", "CDP|고객분석|CRM")
        
        # 6. Media RSS Feeds
        self.crawl_ai_times()
        self.crawl_zdnet_korea()  # Handled failure testing
        self.crawl_cio_korea()
        
        # 7. ArXiv Papers
        self.crawl_arxiv_api(max_results=50)

    def run_alternative_sources(self):
        """Execute Stage 2: Alternative sources if collected < 200."""
        logger.info(f"=== Stage 2: Running Alternative Sources (Current: {len(self.results)}) ===")
        alt_queries = [
            ("제조 AX", "tech", "Manufacturing AX", "제조AX|디지털전환"),
            ("스마트팩토리 클라우드", "market", "Smart Factory Cloud", "클라우드|스마트팩토리"),
            ("공장 자동화 AI", "tech", "Factory Automation", "자동화|AI"),
            ("산업용 AI 솔루션", "market", "Industrial AI", "산업용AI|SaaS"),
            ("중소기업 스마트제조혁신", "policy", "Manufacturing Innovation", "스마트제조혁신|중기부")
        ]
        for query, cat, label, kw in alt_queries:
            if len(self.results) >= 200:
                break
            self.crawl_google_news_query(query, cat, f"Alt-{label}", kw)

    def merge_fallback_if_needed(self, fallback_path: str = "data/fallback/fallback_market_news.csv", target_count: int = 200) -> int:
        """Execute Stage 3: Merge fallback CSV if count < target_count."""
        live_count = len(self.results)
        if live_count >= target_count:
            logger.info(f"Live count ({live_count}) meets requirement ({target_count}). Fallback merge skipped.")
            return 0

        logger.info(f"Live count ({live_count}) < {target_count}. Merging fallback data...")
        full_fallback_path = os.path.join(BASE_DIR, fallback_path)
        if not os.path.exists(full_fallback_path):
            logger.error(f"Fallback file not found at {full_fallback_path}!")
            return 0

        fallback_df = pd.read_csv(full_fallback_path, encoding="utf-8-sig")
        needed = target_count - live_count
        fallback_added = 0

        for _, row in fallback_df.iterrows():
            title = str(row.get("title", ""))
            url = str(row.get("source_url", ""))
            if self._is_duplicate(title, url):
                continue
            
            article = {
                "article_id": f"FB-{len(self.results) + 1:04d}",
                "category": str(row.get("category", "market")),
                "title": title,
                "date": parse_date(str(row.get("date", ""))),
                "content": str(row.get("content", title)),
                "summary": str(row.get("summary", title[:150])),
                "source_url": url,
                "source_name": str(row.get("source_name", "Fallback News")),
                "company_tag": str(row.get("company_tag", "")) if pd.notna(row.get("company_tag")) else "",
                "keywords": str(row.get("keywords", "")) if pd.notna(row.get("keywords")) else "",
                "collected_at": str(row.get("collected_at", datetime.now().isoformat())),
                "has_null": "false",
                "is_duplicate_seed": "false",
                "data_origin": "fallback"
            }
            self.results.append(article)
            fallback_added += 1
            if len(self.results) >= target_count:
                break

        logger.info(f"Merged {fallback_added} fallback articles. Total is now {len(self.results)}.")
        return fallback_added

    def save_results(self, output_path: str = "data/raw/crawled_market_news.csv"):
        """Save collected articles to CSV."""
        full_output_path = os.path.join(BASE_DIR, output_path)
        os.makedirs(os.path.dirname(full_output_path), exist_ok=True)
        df = pd.DataFrame(self.results)
        df.to_csv(full_output_path, index=False, encoding="utf-8-sig")
        logger.info(f"Successfully saved {len(df)} articles to {full_output_path}")
        return df

def main():
    crawler = MarketCrawler()
    
    # 1. Primary sources
    crawler.run_primary_sources()
    live_primary_count = len(crawler.results)
    
    # 2. Alternative sources if < 200
    if len(crawler.results) < 200:
        crawler.run_alternative_sources()
    
    live_final_count = len(crawler.results)
    
    # 3. Merge fallback if still < 200
    fallback_count = 0
    if len(crawler.results) < 200:
        fallback_count = crawler.merge_fallback_if_needed(target_count=200)
        
    # 4. Save to data/raw/crawled_market_news.csv
    output_path = "data/raw/crawled_market_news.csv"
    df = crawler.save_results(output_path)
    
    # 5. Output Summary Report
    print("\n" + "="*55)
    print("           CRAWLER EXECUTION SUMMARY          ")
    print("="*55)
    print(f"Total Collected Items : {len(df)}")
    print(f"Live Crawled Items    : {live_final_count}")
    print(f"Fallback Items Merged : {fallback_count}")
    print(f"Successful Sources    : {len(crawler.successful_sources)}")
    print(f"Failed Sources        : {len(crawler.failed_sources)}")
    print("\n[Categories Distribution]")
    if "category" in df.columns:
        print(df["category"].value_counts().to_string())
    print("\n[Data Origin Distribution]")
    if "data_origin" in df.columns:
        print(df["data_origin"].value_counts().to_string())
    print("="*55 + "\n")
    
    if crawler.failed_sources:
        print("[Failed Sources Details]")
        for src, err in crawler.failed_sources:
            print(f"- {src}: {err}")

if __name__ == "__main__":
    main()
