"""
Site Builder Module (src/build_site.py)
Generates docs/index.html and docs/report.json from recommended_market_news.csv.
Creates a responsive, production-ready static dashboard for GitHub Pages.
"""

import os
import sys
import json
import logging
from datetime import datetime
import pandas as pd
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS_DIR = os.path.join(BASE_DIR, "docs")
DATA_DIR = os.path.join(BASE_DIR, "data", "processed")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("BuildSite")

def load_profile() -> dict:
    profile_path = os.path.join(BASE_DIR, "config", "company_profile.yaml")
    if os.path.exists(profile_path):
        with open(profile_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def build():
    os.makedirs(DOCS_DIR, exist_ok=True)
    rec_csv_path = os.path.join(DATA_DIR, "recommended_market_news.csv")
    cleaned_csv_path = os.path.join(DATA_DIR, "cleaned_market_news.csv")

    if not os.path.exists(rec_csv_path):
        raise FileNotFoundError(f"Recommended news CSV not found at: {rec_csv_path}")

    df_rec = pd.read_csv(rec_csv_path, encoding="utf-8-sig")
    total_evaluated = len(pd.read_csv(cleaned_csv_path, encoding="utf-8-sig")) if os.path.exists(cleaned_csv_path) else len(df_rec)
    
    profile = load_profile()
    company_name = profile.get("company_name", "NovaFactory AI")
    business_area = profile.get("business_area", "제조업 AI 비전 품질검사")
    
    # 1. Create docs/report.json
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    top_10 = df_rec.head(10).to_dict(orient="records")
    all_30 = df_rec.to_dict(orient="records")
    category_counts = df_rec["category"].value_counts().to_dict()

    report_data = {
        "metadata": {
            "title": f"{company_name} 시장·경쟁사·정책 추천 인텔리전스 리포트",
            "generated_at": now_str,
            "company_name": company_name,
            "business_area": business_area,
            "total_evaluated_articles": total_evaluated,
            "top_recommended_count": len(df_rec),
            "scoring_mode": "Gemini AI" if any("[Gemini AI]" in str(r.get("recommendation_reason", "")) for r in all_30) else "Rule-based Engine"
        },
        "category_statistics": category_counts,
        "top_10_articles": top_10,
        "all_recommended_articles": all_30
    }

    report_json_path = os.path.join(DOCS_DIR, "report.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved JSON report to: {report_json_path}")

    # 2. Build HTML Dashboard (docs/index.html)
    # Generate Top 10 HTML Cards
    top_10_html = ""
    category_color_map = {
        "tech": ("#2563eb", "기술·R&D"),
        "policy": ("#059669", "정부지원·정책"),
        "market": ("#7c3aed", "시장동향"),
        "competitor": ("#d97706", "경쟁사분석")
    }

    for idx, row in df_rec.head(10).iterrows():
        cat = str(row.get("category", "tech")).lower()
        color, cat_name = category_color_map.get(cat, ("#4b5563", cat.upper()))
        rank = idx + 1
        score = row.get("score", 0.0)
        title = row.get("title", "")
        url = row.get("source_url", "#")
        source = row.get("source_name", "미디어")
        date_val = row.get("date", "")
        reason = row.get("recommendation_reason", "")

        top_10_html += f"""
        <div class="card top-card">
            <div class="card-header">
                <div class="rank-badge">#{rank:02d}</div>
                <div class="tags">
                    <span class="badge" style="background-color: {color}20; color: {color}; border: 1px solid {color}40;">{cat_name}</span>
                    <span class="score-pill">{score:.1f}점</span>
                </div>
            </div>
            <h3 class="card-title">
                <a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>
            </h3>
            <div class="card-meta">
                <span>📰 {source}</span>
                <span>📅 {date_val}</span>
            </div>
            <div class="reason-box">
                <div class="reason-label">💡 맞춤 추천 이유</div>
                <p class="reason-text">{reason}</p>
            </div>
            <div class="card-footer">
                <a href="{url}" target="_blank" class="link-btn" rel="noopener noreferrer">원문 기사 바로가기 &rarr;</a>
            </div>
        </div>
        """

    # Generate Top 30 Table rows
    table_rows_html = ""
    for idx, row in df_rec.iterrows():
        cat = str(row.get("category", "tech")).lower()
        color, cat_name = category_color_map.get(cat, ("#4b5563", cat.upper()))
        rank = idx + 1
        score = row.get("score", 0.0)
        title = row.get("title", "")
        url = row.get("source_url", "#")
        source = row.get("source_name", "미디어")
        date_val = row.get("date", "")
        reason = row.get("recommendation_reason", "")

        table_rows_html += f"""
        <tr class="table-row" data-category="{cat}">
            <td class="td-rank">#{rank}</td>
            <td><span class="badge" style="background-color: {color}20; color: {color};">{cat_name}</span></td>
            <td class="td-title">
                <a href="{url}" target="_blank" rel="noopener noreferrer" class="title-link">{title}</a>
                <div class="row-reason">{reason}</div>
            </td>
            <td class="td-meta">{source}<br><small style="color: #64748b;">{date_val}</small></td>
            <td class="td-score"><strong>{score:.1f}</strong></td>
            <td><a href="{url}" target="_blank" class="table-btn" rel="noopener noreferrer">원문</a></td>
        </tr>
        """

    scoring_mode_badge = report_data["metadata"]["scoring_mode"]

    html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{company_name} - 인텔리전스 마켓 대시보드</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --surface-color: #1e293b;
            --surface-border: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --primary-accent: #38bdf8;
            --primary-gradient: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
            --card-hover: #243248;
        }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Pretendard", "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            line-height: 1.6;
            padding: 24px;
        }}
        .container {{
            max-width: 1240px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 32px;
            padding-bottom: 24px;
            border-bottom: 1px solid var(--surface-border);
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header-title h1 {{
            font-size: 2rem;
            font-weight: 800;
            background: var(--primary-gradient);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 6px;
        }}
        .header-subtitle {{
            color: var(--text-secondary);
            font-size: 0.95rem;
        }}
        .header-badge {{
            background: #0369a1;
            color: #e0f2fe;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 0.85rem;
            font-weight: 600;
            display: inline-block;
        }}
        /* KPI Metrics */
        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 16px;
            margin-bottom: 32px;
        }}
        .kpi-card {{
            background-color: var(--surface-color);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
            padding: 20px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .kpi-label {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .kpi-value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #f1f5f9;
        }}
        .kpi-subtext {{
            font-size: 0.8rem;
            color: #38bdf8;
        }}
        /* Section styling */
        .section-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 40px 0 20px 0;
        }}
        .section-title {{
            font-size: 1.4rem;
            font-weight: 700;
            color: #f8fafc;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        /* Top 10 Grid */
        .top-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 48px;
        }}
        .card {{
            background-color: var(--surface-color);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
            padding: 22px;
            display: flex;
            flex-direction: column;
            transition: transform 0.2s, background-color 0.2s, border-color 0.2s;
        }}
        .card:hover {{
            transform: translateY(-3px);
            background-color: var(--card-hover);
            border-color: #475569;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .rank-badge {{
            font-size: 1.1rem;
            font-weight: 800;
            color: #38bdf8;
        }}
        .tags {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .badge {{
            font-size: 0.75rem;
            padding: 3px 10px;
            border-radius: 9999px;
            font-weight: 600;
        }}
        .score-pill {{
            background: #334155;
            color: #f8fafc;
            font-size: 0.8rem;
            font-weight: 700;
            padding: 3px 8px;
            border-radius: 6px;
        }}
        .card-title {{
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.45;
            margin-bottom: 12px;
        }}
        .card-title a {{
            color: #f1f5f9;
            text-decoration: none;
        }}
        .card-title a:hover {{
            color: #38bdf8;
            text-decoration: underline;
        }}
        .card-meta {{
            font-size: 0.82rem;
            color: var(--text-secondary);
            display: flex;
            gap: 14px;
            margin-bottom: 16px;
        }}
        .reason-box {{
            background: #0f172a80;
            border-left: 3px solid #38bdf8;
            padding: 10px 14px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 18px;
            flex-grow: 1;
        }}
        .reason-label {{
            font-size: 0.75rem;
            font-weight: 700;
            color: #38bdf8;
            margin-bottom: 4px;
        }}
        .reason-text {{
            font-size: 0.88rem;
            color: #cbd5e1;
            line-height: 1.4;
        }}
        .card-footer {{
            margin-top: auto;
            text-align: right;
        }}
        .link-btn {{
            color: #38bdf8;
            text-decoration: none;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .link-btn:hover {{
            text-decoration: underline;
        }}
        /* Table Controls */
        .controls {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            margin-bottom: 16px;
        }}
        .filter-buttons {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .filter-btn {{
            background: var(--surface-color);
            color: var(--text-secondary);
            border: 1px solid var(--surface-border);
            padding: 6px 14px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.85rem;
            font-weight: 600;
            transition: all 0.2s;
        }}
        .filter-btn:hover, .filter-btn.active {{
            background: #0284c7;
            color: #ffffff;
            border-color: #0284c7;
        }}
        .search-input {{
            background: var(--surface-color);
            border: 1px solid var(--surface-border);
            color: #ffffff;
            padding: 7px 14px;
            border-radius: 8px;
            font-size: 0.88rem;
            width: 250px;
        }}
        .search-input:focus {{
            outline: none;
            border-color: #38bdf8;
        }}
        /* Table Styles */
        .table-wrap {{
            overflow-x: auto;
            background: var(--surface-color);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }}
        th {{
            background: #1e293b;
            padding: 14px 16px;
            font-weight: 700;
            color: var(--text-secondary);
            border-bottom: 1px solid var(--surface-border);
        }}
        td {{
            padding: 14px 16px;
            border-bottom: 1px solid #33415550;
            vertical-align: middle;
        }}
        tr:hover td {{
            background: #24324880;
        }}
        .td-rank {{
            font-weight: 700;
            color: #94a3b8;
            width: 50px;
        }}
        .td-title {{
            max-width: 450px;
        }}
        .title-link {{
            color: #f1f5f9;
            text-decoration: none;
            font-weight: 600;
        }}
        .title-link:hover {{
            color: #38bdf8;
        }}
        .row-reason {{
            font-size: 0.78rem;
            color: #94a3b8;
            margin-top: 4px;
        }}
        .td-meta {{
            font-size: 0.82rem;
            white-space: nowrap;
        }}
        .td-score {{
            color: #38bdf8;
            font-size: 1rem;
        }}
        .table-btn {{
            display: inline-block;
            background: #334155;
            color: #f1f5f9;
            padding: 4px 10px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.78rem;
            font-weight: 600;
        }}
        .table-btn:hover {{
            background: #0284c7;
        }}
        footer {{
            margin-top: 60px;
            padding-top: 24px;
            border-top: 1px solid var(--surface-border);
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="header-title">
                <h1>{company_name} 인텔리전스 대시보드</h1>
                <div class="header-subtitle">
                    분야: <strong>{business_area}</strong> | 기준 일자: {now_str}
                </div>
            </div>
            <div>
                <span class="header-badge">평가 엔진: {scoring_mode_badge}</span>
            </div>
        </header>

        <!-- KPI Metrics -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <span class="kpi-label">전체 분석 수집량</span>
                <span class="kpi-value">{total_evaluated:,}</span>
                <span class="kpi-subtext">실시간 RSS 및 공개 API</span>
            </div>
            <div class="kpi-card">
                <span class="kpi-label">최종 선별 추천 건수</span>
                <span class="kpi-value">{len(df_rec)}</span>
                <span class="kpi-subtext">관련도 상위 30건 엄선</span>
            </div>
            <div class="kpi-card">
                <span class="kpi-label">TOP 1 최고 연관 점수</span>
                <span class="kpi-value">{df_rec['score'].max():.1f}점</span>
                <span class="kpi-subtext">NovaFactory 핵심 제품 매칭</span>
            </div>
            <div class="kpi-card">
                <span class="kpi-label">카테고리 구성</span>
                <span class="kpi-value" style="font-size: 1.25rem; font-weight: 600; margin-top: 6px;">
                    기술({category_counts.get('tech', 0)}) · 정책({category_counts.get('policy', 0)}) · 시장({category_counts.get('market', 0)})
                </span>
                <span class="kpi-subtext">다각도 산업 분석</span>
            </div>
        </div>

        <!-- Section: Top 10 Priority Intelligence -->
        <div class="section-header">
            <h2 class="section-title">🔥 실시간 전략 추천 TOP 10</h2>
        </div>
        <div class="top-grid">
            {top_10_html}
        </div>

        <!-- Section: All 30 Recommended News Table -->
        <div class="section-header">
            <h2 class="section-title">📋 추천 뉴스 종합 (상위 30선)</h2>
        </div>

        <div class="controls">
            <div class="filter-buttons">
                <button class="filter-btn active" onclick="filterCategory('all', this)">전체보기 ({len(df_rec)})</button>
                <button class="filter-btn" onclick="filterCategory('tech', this)">기술·R&D ({category_counts.get('tech', 0)})</button>
                <button class="filter-btn" onclick="filterCategory('policy', this)">정부지원·정책 ({category_counts.get('policy', 0)})</button>
                <button class="filter-btn" onclick="filterCategory('market', this)">시장동향 ({category_counts.get('market', 0)})</button>
                <button class="filter-btn" onclick="filterCategory('competitor', this)">경쟁사 ({category_counts.get('competitor', 0)})</button>
            </div>
            <input type="text" id="searchInput" class="search-input" placeholder="키워드/제목 실시간 검색..." onkeyup="searchTable()">
        </div>

        <div class="table-wrap">
            <table id="newsTable">
                <thead>
                    <tr>
                        <th>순위</th>
                        <th>구분</th>
                        <th>기사 제목 및 추천 이유</th>
                        <th>출처 / 일자</th>
                        <th>점수</th>
                        <th>링크</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows_html}
                </tbody>
            </table>
        </div>

        <footer>
            <p>Generated by <strong>Project 1: Market Intelligence Agent</strong> for {company_name}</p>
            <p>Hosted on GitHub Pages | Static Intelligence System</p>
        </footer>
    </div>

    <script>
        function filterCategory(category, btn) {{
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            const rows = document.querySelectorAll('.table-row');
            rows.forEach(row => {{
                if (category === 'all' || row.getAttribute('data-category') === category) {{
                    row.style.display = '';
                }} else {{
                    row.style.display = 'none';
                }}
            }});
        }}

        function searchTable() {{
            const query = document.getElementById('searchInput').value.toLowerCase();
            const rows = document.querySelectorAll('.table-row');
            rows.forEach(row => {{
                const text = row.innerText.toLowerCase();
                if (text.includes(query)) {{
                    row.style.display = '';
                }} else {{
                    row.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
"""

    index_html_path = os.path.join(DOCS_DIR, "index.html")
    with open(index_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"Saved static HTML dashboard to: {index_html_path}")

def main():
    build()

if __name__ == "__main__":
    main()
