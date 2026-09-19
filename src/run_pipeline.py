"""
End-to-End Pipeline Runner (src/run_pipeline.py)
Orchestrates collection -> cleaning -> recommendation -> dashboard building.
Handles timeouts, HTTP errors, rate-limits, and data shortages gracefully with fallback support.
Logs pipeline execution details to logs/pipeline.log.
"""

import os
import sys
import logging
from datetime import datetime

# Set project root in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "pipeline.log")

# Setup dedicated pipeline logger
logger = logging.getLogger("PipelineRunner")
logger.setLevel(logging.INFO)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
file_handler.setFormatter(file_formatter)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(logging.INFO)
stream_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
stream_handler.setFormatter(stream_formatter)

if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

from src.crawler import MarketCrawler
from src.cleaner import DataCleaner
from src.recommender import MarketRecommender
from src.build_site import build

class PipelineOrchestrator:
    def __init__(self):
        self.stage_status = {
            "1_COLLECTION": "NOT_STARTED",
            "2_CLEANING": "NOT_STARTED",
            "3_RECOMMENDATION": "NOT_STARTED",
            "4_DASHBOARD": "NOT_STARTED"
        }
        self.metrics = {}

    def run_stage_collection(self) -> bool:
        """Stage 1: Crawl market news, handle source failures and ensure >= 200 items."""
        stage_name = "1_COLLECTION"
        logger.info(">>> [STAGE 1] Starting Market Data Collection...")
        try:
            crawler = MarketCrawler()
            
            # Primary sources
            crawler.run_primary_sources()
            
            # If < 200, try alternative sources
            if len(crawler.results) < 200:
                logger.warning(f"Primary crawl yielded {len(crawler.results)} items (< 200). Running alternative sources...")
                crawler.run_alternative_sources()
            
            # If still < 200, merge fallback data
            fallback_added = 0
            if len(crawler.results) < 200:
                logger.warning(f"Live sources yielded {len(crawler.results)} items (< 200). Merging fallback dataset...")
                fallback_added = crawler.merge_fallback_if_needed(target_count=200)

            raw_csv = "data/raw/crawled_market_news.csv"
            df_raw = crawler.save_results(raw_csv)
            
            self.metrics["raw_count"] = len(df_raw)
            self.metrics["live_count"] = len(df_raw) - fallback_added
            self.metrics["fallback_count"] = fallback_added
            self.metrics["failed_sources"] = len(crawler.failed_sources)

            if len(df_raw) < 200:
                self.stage_status[stage_name] = "FAILED"
                logger.error(f"[STAGE 1 FAILED] Target count not met: {len(df_raw)} < 200")
                return False
            elif crawler.failed_sources or fallback_added > 0:
                self.stage_status[stage_name] = "WARNING"
                logger.warning(f"[STAGE 1 WARNING] Completed with {len(df_raw)} items ({len(crawler.failed_sources)} failed sources handled, {fallback_added} fallback used)")
            else:
                self.stage_status[stage_name] = "SUCCESS"
                logger.info(f"[STAGE 1 SUCCESS] Completed with {len(df_raw)} items from {len(crawler.successful_sources)} sources.")
            return True
        except Exception as e:
            self.stage_status[stage_name] = "FAILED"
            logger.error(f"[STAGE 1 FAILED] Uncaught exception during collection: {e}", exc_info=True)
            return False

    def run_stage_cleaning(self) -> bool:
        """Stage 2: Clean, normalize dates, remove HTML entities and duplicates."""
        stage_name = "2_CLEANING"
        logger.info(">>> [STAGE 2] Starting Data Cleaning & Deduplication...")
        try:
            raw_path = "data/raw/crawled_market_news.csv"
            out_path = "data/processed/cleaned_market_news.csv"
            cleaner = DataCleaner(raw_path=raw_path, output_path=out_path)
            df_cleaned = cleaner.clean()

            self.metrics["cleaned_count"] = len(df_cleaned)
            self.metrics["removed_count"] = cleaner.metrics["total_removed"]

            if len(df_cleaned) == 0:
                self.stage_status[stage_name] = "FAILED"
                logger.error("[STAGE 2 FAILED] Cleaned dataset is empty.")
                return False

            self.stage_status[stage_name] = "SUCCESS"
            logger.info(f"[STAGE 2 SUCCESS] Successfully cleaned {len(df_cleaned)} records (removed {cleaner.metrics['total_removed']} rows).")
            return True
        except Exception as e:
            self.stage_status[stage_name] = "FAILED"
            logger.error(f"[STAGE 2 FAILED] Cleaning error: {e}", exc_info=True)
            return False

    def run_stage_recommendation(self) -> bool:
        """Stage 3: Calculate relevance scores and produce top 30 recommendations."""
        stage_name = "3_RECOMMENDATION"
        logger.info(">>> [STAGE 3] Starting Custom Intelligence Recommendation...")
        try:
            cleaned_path = "data/processed/cleaned_market_news.csv"
            rec = MarketRecommender(cleaned_csv_path=cleaned_path)
            top_df = rec.run_recommendation(top_k=30)

            self.metrics["recommended_count"] = len(top_df)
            self.metrics["llm_used"] = rec.use_llm

            if len(top_df) < 10:
                self.stage_status[stage_name] = "WARNING"
                logger.warning(f"[STAGE 3 WARNING] Recommended items below 10: {len(top_df)}")
            else:
                self.stage_status[stage_name] = "SUCCESS"
                logger.info(f"[STAGE 3 SUCCESS] Generated TOP {len(top_df)} recommendations (LLM evaluation: {rec.use_llm}).")
            return True
        except Exception as e:
            self.stage_status[stage_name] = "FAILED"
            logger.error(f"[STAGE 3 FAILED] Recommendation error: {e}", exc_info=True)
            return False

    def run_stage_dashboard(self) -> bool:
        """Stage 4: Build static HTML dashboard and JSON report."""
        stage_name = "4_DASHBOARD"
        logger.info(">>> [STAGE 4] Building Static Dashboard & Report...")
        try:
            build()
            index_path = os.path.join(BASE_DIR, "docs", "index.html")
            report_path = os.path.join(BASE_DIR, "docs", "report.json")

            if not os.path.exists(index_path) or not os.path.exists(report_path):
                self.stage_status[stage_name] = "FAILED"
                logger.error("[STAGE 4 FAILED] Output files (index.html or report.json) missing.")
                return False

            self.stage_status[stage_name] = "SUCCESS"
            logger.info("[STAGE 4 SUCCESS] Successfully generated docs/index.html and docs/report.json.")
            return True
        except Exception as e:
            self.stage_status[stage_name] = "FAILED"
            logger.error(f"[STAGE 4 FAILED] Dashboard build error: {e}", exc_info=True)
            return False

    def execute_all(self):
        logger.info("==================================================")
        logger.info("   PROJECT 1: MARKET AGENT PIPELINE EXECUTION     ")
        logger.info("==================================================")
        start_time = datetime.now()

        # Step 1: Collect
        if not self.run_stage_collection():
            logger.error("Pipeline aborted at Stage 1.")
            self._print_summary(start_time)
            return False

        # Step 2: Clean
        if not self.run_stage_cleaning():
            logger.error("Pipeline aborted at Stage 2.")
            self._print_summary(start_time)
            return False

        # Step 3: Recommend
        if not self.run_stage_recommendation():
            logger.error("Pipeline aborted at Stage 3.")
            self._print_summary(start_time)
            return False

        # Step 4: Build Site
        if not self.run_stage_dashboard():
            logger.error("Pipeline aborted at Stage 4.")
            self._print_summary(start_time)
            return False

        self._print_summary(start_time)
        return True

    def _print_summary(self, start_time: datetime):
        duration = (datetime.now() - start_time).total_seconds()
        logger.info("==================================================")
        logger.info("             PIPELINE EXECUTION SUMMARY           ")
        logger.info("==================================================")
        for stage, status in self.stage_status.items():
            logger.info(f"  {stage:<18}: [{status}]")
        logger.info("--------------------------------------------------")
        logger.info(f"  Raw Articles Collected : {self.metrics.get('raw_count', 0)}")
        logger.info(f"  Cleaned Valid Articles : {self.metrics.get('cleaned_count', 0)}")
        logger.info(f"  Final Recommendations  : {self.metrics.get('recommended_count', 0)}")
        logger.info(f"  LLM Evaluation Mode    : {self.metrics.get('llm_used', False)}")
        logger.info(f"  Total Duration         : {duration:.2f} seconds")
        logger.info("==================================================")

def main():
    orchestrator = PipelineOrchestrator()
    success = orchestrator.execute_all()
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
