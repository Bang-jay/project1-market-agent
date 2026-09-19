"""
Data Cleaner Module (src/cleaner.py)
Cleans, normalizes, and deduplicates raw crawled market news data.
Saves the processed output to data/processed/cleaned_market_news.csv.
"""

import os
import sys
import re
import html
import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "cleaner.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Cleaner")

def clean_html_text(text: str) -> str:
    """Remove HTML tags, decode entities, and normalize whitespace."""
    if pd.isna(text) or text is None:
        return ""
    text = str(text)
    # Remove HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", text)
    # Unescape HTML entities like &quot;, &amp;, &#39;
    cleaned = html.unescape(cleaned)
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned

def normalize_date(date_val: str, fallback_date: str = None) -> str:
    """Standardize date to YYYY-MM-DD format."""
    if pd.isna(date_val) or not date_val:
        if fallback_date and not pd.isna(fallback_date):
            return normalize_date(fallback_date)
        return datetime.now().strftime("%Y-%m-%d")
        
    date_str = str(date_val).strip()
    # Try ISO date pattern YYYY-MM-DD
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", date_str)
    if m:
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
            
    # Try RFC 2822 / email format (e.g. Thu, 17 Sep 2026 08:30:00 GMT)
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass
        
    return datetime.now().strftime("%Y-%m-%d")

def normalize_for_dedup(text: str) -> str:
    """Normalize string for fuzzy duplicate title comparison."""
    if not text:
        return ""
    # Remove all spaces and punctuation, convert to lowercase
    return re.sub(r"[\s\W_]+", "", text).lower()

class DataCleaner:
    def __init__(self, raw_path: str = "data/raw/crawled_market_news.csv", output_path: str = "data/processed/cleaned_market_news.csv"):
        self.raw_path = os.path.join(BASE_DIR, raw_path)
        self.output_path = os.path.join(BASE_DIR, output_path)
        
        self.metrics = {
            "raw_count": 0,
            "final_count": 0,
            "exact_duplicates": 0,
            "null_title_dropped": 0,
            "short_title_dropped": 0,
            "url_duplicates_dropped": 0,
            "title_duplicates_dropped": 0,
            "invalid_url_dropped": 0,
            "total_removed": 0
        }

    def clean(self) -> pd.DataFrame:
        logger.info(f"Loading raw data from: {self.raw_path}")
        if not os.path.exists(self.raw_path):
            raise FileNotFoundError(f"Raw data file not found: {self.raw_path}")
            
        df = pd.read_csv(self.raw_path, encoding="utf-8-sig")
        self.metrics["raw_count"] = len(df)
        logger.info(f"Loaded {len(df)} raw records.")

        # Step 1: Remove exact row duplicates
        initial_count = len(df)
        df = df.drop_duplicates()
        self.metrics["exact_duplicates"] = initial_count - len(df)

        # Step 2: Clean HTML and text fields
        text_cols = ["title", "content", "summary", "source_name"]
        for col in text_cols:
            if col in df.columns:
                df[col] = df[col].apply(clean_html_text)

        # Step 3: Filter null and overly short titles (< 5 characters)
        before_title_filter = len(df)
        null_titles = df["title"].isna() | (df["title"].str.strip() == "")
        self.metrics["null_title_dropped"] = int(null_titles.sum())
        df = df[~null_titles].copy()

        short_titles = df["title"].str.len() < 5
        self.metrics["short_title_dropped"] = int(short_titles.sum())
        df = df[~short_titles].copy()

        # Step 4: Normalize dates
        fallback_col = "collected_at" if "collected_at" in df.columns else None
        df["date"] = df.apply(
            lambda r: normalize_date(r.get("date"), r.get(fallback_col) if fallback_col else None),
            axis=1
        )

        # Step 5: Validate and clean URLs
        if "source_url" in df.columns:
            df["source_url"] = df["source_url"].astype(str).str.strip()
            valid_url = df["source_url"].str.startswith("http://") | df["source_url"].str.startswith("https://")
            self.metrics["invalid_url_dropped"] = int((~valid_url).sum())
            df = df[valid_url].copy()

        # Step 6: Deduplicate by URL
        before_url_dedup = len(df)
        df = df.drop_duplicates(subset=["source_url"], keep="first")
        self.metrics["url_duplicates_dropped"] = before_url_dedup - len(df)

        # Step 7: Deduplicate by normalized Title
        df["clean_title_key"] = df["title"].apply(normalize_for_dedup)
        before_title_dedup = len(df)
        df = df.drop_duplicates(subset=["clean_title_key"], keep="first")
        self.metrics["title_duplicates_dropped"] = before_title_dedup - len(df)
        df = df.drop(columns=["clean_title_key"])

        # Step 8: Standardize nulls in optional columns
        if "company_tag" in df.columns:
            df["company_tag"] = df["company_tag"].fillna("").astype(str).replace("nan", "")
        if "keywords" in df.columns:
            df["keywords"] = df["keywords"].fillna("").astype(str).replace("nan", "")
        if "has_null" in df.columns:
            df["has_null"] = "false"
        if "is_duplicate_seed" in df.columns:
            df["is_duplicate_seed"] = "false"

        # Step 9: Re-generate clean, unique article_ids
        df = df.reset_index(drop=True)
        df["article_id"] = [f"CLEAN-{i+1:04d}" for i in range(len(df))]

        self.metrics["final_count"] = len(df)
        self.metrics["total_removed"] = self.metrics["raw_count"] - self.metrics["final_count"]

        # Step 10: Save to processed CSV
        os.makedirs(os.path.dirname(self.output_path), exist_ok=True)
        df.to_csv(self.output_path, index=False, encoding="utf-8-sig")
        logger.info(f"Saved {len(df)} cleaned records to: {self.output_path}")

        return df

    def print_report(self):
        m = self.metrics
        print("\n" + "="*50)
        print("           DATA CLEANING REPORT               ")
        print("="*50)
        print(f"Raw Input Count      : {m['raw_count']} rows")
        print(f"Final Cleaned Count  : {m['final_count']} rows")
        print(f"Total Removed Rows   : {m['total_removed']} rows")
        print("-" * 50)
        print(f"- Exact Duplicates   : {m['exact_duplicates']}")
        print(f"- Null Titles        : {m['null_title_dropped']}")
        print(f"- Short Titles (<5)  : {m['short_title_dropped']}")
        print(f"- Invalid URLs       : {m['invalid_url_dropped']}")
        print(f"- Duplicate URLs     : {m['url_duplicates_dropped']}")
        print(f"- Duplicate Titles   : {m['title_duplicates_dropped']}")
        print("="*50 + "\n")

def main():
    cleaner = DataCleaner()
    df = cleaner.clean()
    cleaner.print_report()

if __name__ == "__main__":
    main()
