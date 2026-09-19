"""
Market Agent Recommender (src/recommender.py)
Calculates relevance scores based on company_profile.yaml and generates top 30 recommendations.
Supports optional Gemini LLM evaluation if GEMINI_API_KEY is provided, otherwise falls back to rule-based scoring.
"""

import os
import sys
import json
import logging
from datetime import datetime
import pandas as pd
import requests
import yaml
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "recommender.log")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("Recommender")

load_dotenv(os.path.join(BASE_DIR, ".env"))

def load_profile(profile_path: str = "config/company_profile.yaml") -> dict:
    full_path = os.path.join(BASE_DIR, profile_path)
    if not os.path.exists(full_path):
        logger.warning(f"Profile {full_path} not found.")
        return {}
    with open(full_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

class MarketRecommender:
    def __init__(self, cleaned_csv_path: str = "data/processed/cleaned_market_news.csv"):
        self.cleaned_csv_path = os.path.join(BASE_DIR, cleaned_csv_path)
        self.profile = load_profile()
        self.company_name = self.profile.get("company_name", "NovaFactory AI")
        self.business_area = self.profile.get("business_area", "제조업 AI 비전 품질검사")
        self.products = self.profile.get("products", ["비전 기반 불량 탐지 SaaS", "제조 품질 리포트 자동화"])
        self.target_markets = self.profile.get("target_market", ["중소·중견 제조기업", "스마트팩토리 구축 기업"])
        self.competitors = [c.lower() for c in self.profile.get("competitors", ["visionforge", "inspectai", "factorymind", "qualibot"])]
        self.interest_keywords = [k.lower() for k in self.profile.get("interest_keywords", ["ai", "스마트팩토리", "품질검사", "자동화", "클라우드", "제조 ax"])]
        self.funding_keywords = [f.lower() for f in self.profile.get("funding_keywords", ["창업지원", "ai 바우처", "스마트공장", "r&d", "사업화 자금"])]
        
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.use_llm = bool(self.api_key and os.environ.get("ENABLE_LLM_RELEVANCE", "true").lower() != "false")

    def _calc_rule_score(self, row: pd.Series) -> tuple[float, str]:
        title = str(row.get("title", ""))
        content = str(row.get("content", ""))
        category = str(row.get("category", "")).lower()
        date_str = str(row.get("date", ""))
        text_lower = f"{title} {content}".lower()

        score = 40.0
        reasons = []

        # 1. Core Vision AI & Defect keywords (High domain priority)
        core_vision_kw = ["비전", "불량", "품질검사", "머신비전", "defect", "inspection", "외관검사", "이상탐지"]
        vision_matches = [w for w in core_vision_kw if w in text_lower]
        if vision_matches:
            pts = min(len(vision_matches) * 6.0, 24.0)
            score += pts
            reasons.append(f"핵심 도메인 키워드({', '.join(vision_matches[:2])}) 일치")

        # 2. Interest keywords matching
        interest_matches = [k for k in self.interest_keywords if k in text_lower]
        if interest_matches:
            pts = min(len(interest_matches) * 4.0, 16.0)
            score += pts
            reasons.append(f"관심 기술 분야({', '.join(interest_matches[:2])}) 부합")

        # 3. Policy & Funding keywords matching
        funding_matches = [f for f in self.funding_keywords if f in text_lower]
        if funding_matches or category == "policy":
            pts = min(max(len(funding_matches) * 5.0, 10.0), 20.0)
            score += pts
            if funding_matches:
                reasons.append(f"정부지원/사업화 기회({', '.join(funding_matches[:2])}) 포착")
            else:
                reasons.append("중소제조 관련 정부 정책/규제 동향")

        # 4. Competitor & Industry mentions
        comp_matches = [c for c in self.competitors if c in text_lower]
        if comp_matches or category == "competitor":
            score += 15.0
            if comp_matches:
                reasons.append(f"주요 경쟁사({', '.join(comp_matches)}) 직접 동향")
            else:
                reasons.append("머신비전/스마트팩토리 시장 경쟁사 및 생태계 동향")

        # 5. Target market / Product relevance
        target_kw = ["중소기업", "중견기업", "제조업", "공장", "saas", "리포트", "자동화"]
        target_matches = [t for t in target_kw if t in text_lower]
        if target_matches:
            score += min(len(target_matches) * 3.0, 12.0)

        # 6. Recency score (newer is slightly preferred)
        try:
            pub_dt = datetime.strptime(date_str, "%Y-%m-%d")
            days_diff = (datetime.now() - pub_dt).days
            if days_diff <= 30:
                score += 5.0
            elif days_diff <= 90:
                score += 3.0
        except Exception:
            pass

        final_score = min(round(score, 1), 100.0)

        # Generate synthesized recommendation reason
        if not reasons:
            reason_text = "제조 스마트팩토리 및 비전 AI 산업 생태계 일반 동향"
        else:
            reason_text = " · ".join(reasons)

        # Prepend strategic context
        if category == "policy":
            reason_summary = f"[자금/정책] {reason_text} - NovaFactory AI의 고객사 AI 바우처 및 제조 R&D 수혜 가능성 높음"
        elif category == "tech":
            reason_summary = f"[기술/R&D] {reason_text} - 비전 불량 탐지 및 모델 정확도 고도화에 즉시 참고 가능한 기술 정보"
        elif category == "competitor":
            reason_summary = f"[경쟁 분석] {reason_text} - 주요 경쟁사 및 인접 비전 솔루션 사의 시장 점유 전략 대응 필요"
        else:
            reason_summary = f"[시장 동향] {reason_text} - 타깃 시장(중소·중견 제조기업)의 AX 도입 및 시장 규모 확대 기회"

        return final_score, reason_summary

    def _evaluate_with_llm(self, df: pd.DataFrame) -> pd.DataFrame:
        """Evaluate top candidates with Gemini API (REST endpoint)."""
        logger.info("Evaluating top candidates using Gemini REST API...")
        models_to_try = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.5-pro", "gemini-1.5-flash"]
        
        # Test basic connectivity first
        working_model = None
        for m in models_to_try:
            test_url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
            try:
                test_res = requests.post(
                    test_url,
                    json={"contents": [{"parts": [{"text": "Hello"}]}]},
                    headers={"Content-Type": "application/json"},
                    timeout=5
                )
                if test_res.status_code == 200:
                    working_model = m
                    logger.info(f"Gemini API connected successfully using model: {working_model}")
                    break
                else:
                    logger.warning(f"Model {m} returned status {test_res.status_code}: {test_res.text[:100]}")
            except Exception as e:
                logger.warning(f"Connection error for {m}: {e}")

        if not working_model:
            logger.warning("Could not connect to Gemini models with the provided key. Using rule-based scoring.")
            return df

        # Evaluate top 10 candidates with LLM
        eval_url = f"https://generativelanguage.googleapis.com/v1beta/models/{working_model}:generateContent?key={self.api_key}"
        for idx in range(min(10, len(df))):
            row = df.iloc[idx]
            prompt = (
                f"당신은 제조업 AI 비전 품질검사 기업 '{self.company_name}'의 시장 전략 분석가입니다.\n"
                f"주력 사업: {self.business_area}\n"
                f"제품군: {', '.join(self.products)}\n"
                f"기사 제목: {row['title']}\n"
                f"기사 요약: {row['summary'][:150]}\n"
                f"카테고리: {row['category']}\n\n"
                f"이 기사가 우리 회사에 미치는 영향도와 추천 점수(75~99점) 및 1문장의 핵심 추천 이유를 작성하세요.\n"
                f"반드시 다음 JSON 형식으로만 응답하세요:\n"
                f"{{\"score\": 95.0, \"recommendation_reason\": \"...\"}}"
            )
            try:
                res = requests.post(
                    eval_url,
                    json={"contents": [{"parts": [{"text": prompt}]}]},
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                if res.status_code == 200:
                    res_json = res.json()
                    candidate_text = res_json["candidates"][0]["content"]["parts"][0]["text"]
                    clean_text = candidate_text.replace("```json", "").replace("```", "").strip()
                    data = json.loads(clean_text)
                    if "score" in data and "recommendation_reason" in data:
                        df.at[idx, "score"] = float(data["score"])
                        df.at[idx, "recommendation_reason"] = f"[Gemini AI] {data['recommendation_reason']}"
                        logger.info(f"Row {idx+1}: Evaluated by Gemini -> {data['score']}점")
            except Exception as e:
                logger.warning(f"Row {idx+1} Gemini eval exception: {e}")

        return df

    def run_recommendation(self, top_k: int = 30) -> pd.DataFrame:
        logger.info(f"Loading cleaned data from: {self.cleaned_csv_path}")
        if not os.path.exists(self.cleaned_csv_path):
            raise FileNotFoundError(f"Cleaned CSV not found at: {self.cleaned_csv_path}")

        df = pd.read_csv(self.cleaned_csv_path, encoding="utf-8-sig")
        logger.info(f"Scoring {len(df)} cleaned articles...")

        scores = []
        reasons = []
        for _, row in df.iterrows():
            s, r = self._calc_rule_score(row)
            scores.append(s)
            reasons.append(r)

        df["score"] = scores
        df["recommendation_reason"] = reasons

        # Sort by score descending, then date descending
        df = df.sort_values(by=["score", "date"], ascending=[False, False]).reset_index(drop=True)

        top_candidates = df.head(top_k).copy()

        # Step 2: Use LLM if key is present
        if self.use_llm:
            logger.info("Gemini API key detected. Running LLM evaluation on top candidates...")
            top_candidates = self._evaluate_with_llm(top_candidates)
            top_candidates = top_candidates.sort_values(by=["score", "date"], ascending=[False, False]).reset_index(drop=True)
        else:
            logger.info("No Gemini API key or disabled. Proceeding with rule-based scoring.")

        # Save to data/processed/recommended_market_news.csv
        out_csv = os.path.join(BASE_DIR, "data", "processed", "recommended_market_news.csv")
        os.makedirs(os.path.dirname(out_csv), exist_ok=True)
        top_candidates.to_csv(out_csv, index=False, encoding="utf-8-sig")
        logger.info(f"Saved TOP {len(top_candidates)} recommendations to: {out_csv}")

        return top_candidates

def main():
    rec = MarketRecommender()
    top_df = rec.run_recommendation(top_k=30)
    
    print("\n" + "="*60)
    print("        RECOMMENDER EXECUTION RESULT (TOP 10)         ")
    print("="*60)
    print(f"LLM Applied   : {rec.use_llm}")
    print(f"Total Saved   : {len(top_df)} articles")
    print("-" * 60)
    for i, row in top_df.head(10).iterrows():
        print(f"#{i+1:02d} [{row['score']}점] [{row['category'].upper()}] {row['title'][:45]}...")
        print(f"     이유: {row['recommendation_reason']}")
        print(f"     링크: {row['source_url']}")
        print()
    print("="*60 + "\n")

if __name__ == "__main__":
    main()
