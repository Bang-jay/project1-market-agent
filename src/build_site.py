"""
Site Builder Module (src/build_site.py)
Generates docs/index.html and docs/report.json from recommended_market_news.csv.
Creates a responsive, production-ready static dashboard for GitHub Pages with Domain Navigation (Manufacturing AI vs. AI Marketing).
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
    business_area = profile.get("business_area", "제조업 AI 비전 품질검사 및 AI 마케팅 인텔리전스")
    
    # 1. Create docs/report.json
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    top_10 = df_rec.head(10).to_dict(orient="records")
    all_recs = df_rec.to_dict(orient="records")
    category_counts = df_rec["category"].value_counts().to_dict()

    mfg_count = len(df_rec[df_rec["category"] != "marketing"])
    mkt_count = len(df_rec[df_rec["category"] == "marketing"])

    report_data = {
        "metadata": {
            "title": f"{company_name} 다분야 시장·경쟁사·마케팅 추천 인텔리전스 리포트",
            "generated_at": now_str,
            "company_name": company_name,
            "business_area": business_area,
            "total_evaluated_articles": total_evaluated,
            "top_recommended_count": len(df_rec),
            "domain_statistics": {
                "manufacturing_ai": mfg_count,
                "marketing_ai": mkt_count
            },
            "scoring_mode": "Gemini AI" if any("[Gemini AI]" in str(r.get("recommendation_reason", "")) for r in all_recs) else "Rule-based Engine"
        },
        "category_statistics": category_counts,
        "top_10_articles": top_10,
        "all_recommended_articles": all_recs
    }

    report_json_path = os.path.join(DOCS_DIR, "report.json")
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved JSON report to: {report_json_path}")

    # 2. Build HTML Dashboard (docs/index.html)
    category_color_map = {
        "tech": ("#2563eb", "기술·R&D"),
        "policy": ("#059669", "정부지원·정책"),
        "market": ("#7c3aed", "시장동향"),
        "competitor": ("#d97706", "경쟁사분석"),
        "marketing": ("#ec4899", "AI 마케팅·애드테크")
    }

    # Generate Top 10 HTML Cards
    top_10_html = ""
    for idx, row in df_rec.head(10).iterrows():
        cat = str(row.get("category", "tech")).lower()
        domain = "marketing" if cat == "marketing" else "manufacturing"
        color, cat_name = category_color_map.get(cat, ("#4b5563", cat.upper()))
        rank = idx + 1
        score = row.get("score", 0.0)
        title = row.get("title", "")
        url = row.get("source_url", "#")
        source = row.get("source_name", "미디어")
        date_val = row.get("date", "")
        reason = row.get("recommendation_reason", "")

        domain_label = "📢 마케팅" if domain == "marketing" else "🏭 제조AI"
        domain_badge_style = "background: rgba(236,72,153,0.15); color: #f472b6;" if domain == "marketing" else "background: rgba(56,189,248,0.15); color: #38bdf8;"

        top_10_html += f"""
        <div class="card top-card" data-domain="{domain}" data-category="{cat}">
            <div class="card-header">
                <div class="rank-badge">#{rank:02d}</div>
                <div class="badge-group">
                    <span class="badge" style="{domain_badge_style}">{domain_label}</span>
                    <span class="badge" style="background-color: {color}20; color: {color}; border-color: {color}40;">{cat_name}</span>
                </div>
                <div class="score-badge">{score:.1f}점</div>
            </div>
            <h3 class="card-title">
                <a href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>
            </h3>
            <div class="card-reason">
                <strong>추천 사유:</strong> {reason}
            </div>
            <div class="card-footer">
                <span class="source-info">📰 {source} · 📅 {date_val}</span>
                <a href="{url}" target="_blank" rel="noopener noreferrer" class="link-btn">원문 보기 →</a>
            </div>
        </div>
        """

    # Generate All Table Rows
    table_rows_html = ""
    for idx, row in df_rec.iterrows():
        cat = str(row.get("category", "tech")).lower()
        domain = "marketing" if cat == "marketing" else "manufacturing"
        color, cat_name = category_color_map.get(cat, ("#4b5563", cat.upper()))
        rank = idx + 1
        score = row.get("score", 0.0)
        title = row.get("title", "")
        url = row.get("source_url", "#")
        source = row.get("source_name", "미디어")
        date_val = row.get("date", "")
        reason = row.get("recommendation_reason", "")

        domain_label = "📢 마케팅" if domain == "marketing" else "🏭 제조AI"
        domain_badge_style = "background: rgba(236,72,153,0.15); color: #f472b6;" if domain == "marketing" else "background: rgba(56,189,248,0.15); color: #38bdf8;"

        table_rows_html += f"""
        <tr class="table-row" data-domain="{domain}" data-category="{cat}">
            <td class="td-rank">#{rank}</td>
            <td>
                <span class="badge" style="{domain_badge_style} margin-bottom: 4px; display: inline-block;">{domain_label}</span><br>
                <span class="badge" style="background-color: {color}20; color: {color};">{cat_name}</span>
            </td>
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
    <title>{company_name} - 통합 인텔리전스 마켓 대시보드</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --surface-color: #1e293b;
            --surface-border: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --primary-accent: #38bdf8;
            --marketing-accent: #ec4899;
            --primary-gradient: linear-gradient(135deg, #38bdf8 0%, #ec4899 100%);
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
            max-width: 1280px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 24px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--surface-border);
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            flex-wrap: wrap;
            gap: 16px;
        }}
        .header-title h1 {{
            font-size: 2.1rem;
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
        .header-meta {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
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
        
        /* Domain Navbar (분야별 메뉴바) */
        .domain-navbar {{
            display: flex;
            background: var(--surface-color);
            padding: 6px;
            border-radius: 14px;
            border: 1px solid var(--surface-border);
            margin-bottom: 28px;
            gap: 8px;
            flex-wrap: wrap;
        }}
        .nav-tab {{
            flex: 1;
            min-width: 180px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            background: transparent;
            color: var(--text-secondary);
            border: none;
            padding: 14px 20px;
            border-radius: 10px;
            cursor: pointer;
            font-size: 1rem;
            font-weight: 700;
            transition: all 0.25s ease;
        }}
        .nav-tab:hover {{
            color: #ffffff;
            background: rgba(255, 255, 255, 0.05);
        }}
        .nav-tab.active {{
            background: #0284c7;
            color: #ffffff;
            box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35);
        }}
        .nav-tab.active.marketing-active {{
            background: #db2777;
            box-shadow: 0 4px 12px rgba(219, 39, 119, 0.35);
        }}
        .nav-badge {{
            background: rgba(0, 0, 0, 0.25);
            padding: 2px 9px;
            border-radius: 9999px;
            font-size: 0.82rem;
            font-weight: 700;
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
            transition: transform 0.2s, border-color 0.2s;
        }}
        .kpi-card:hover {{
            transform: translateY(-2px);
            border-color: #475569;
        }}
        .kpi-title {{
            font-size: 0.85rem;
            color: var(--text-secondary);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .kpi-value {{
            font-size: 1.85rem;
            font-weight: 800;
            color: var(--text-primary);
        }}
        .kpi-subtext {{
            font-size: 0.78rem;
            color: #64748b;
        }}

        /* Section Layout */
        .section-header {{
            margin-bottom: 18px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .section-title {{
            font-size: 1.35rem;
            font-weight: 700;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        /* Top 10 Cards Grid */
        .top-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .card {{
            background: var(--surface-color);
            border: 1px solid var(--surface-border);
            border-radius: 12px;
            padding: 22px;
            display: flex;
            flex-direction: column;
            gap: 14px;
            transition: all 0.2s ease;
        }}
        .card:hover {{
            background: var(--card-hover);
            border-color: #0284c7;
            transform: translateY(-3px);
            box-shadow: 0 10px 20px -5px rgba(0, 0, 0, 0.4);
        }}
        .card-header {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .rank-badge {{
            background: #334155;
            color: #f8fafc;
            font-size: 0.85rem;
            font-weight: 800;
            padding: 4px 10px;
            border-radius: 8px;
        }}
        .badge-group {{
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 6px;
            font-size: 0.76rem;
            font-weight: 700;
            border: 1px solid transparent;
        }}
        .score-badge {{
            margin-left: auto;
            color: #38bdf8;
            font-weight: 800;
            font-size: 1.05rem;
        }}
        .card-title {{
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.45;
        }}
        .card-title a {{
            color: var(--text-primary);
            text-decoration: none;
            transition: color 0.15s;
        }}
        .card-title a:hover {{
            color: var(--primary-accent);
        }}
        .card-reason {{
            background: rgba(15, 23, 42, 0.6);
            border-left: 3px solid #38bdf8;
            padding: 10px 12px;
            border-radius: 0 8px 8px 0;
            font-size: 0.84rem;
            color: #cbd5e1;
            line-height: 1.5;
        }}
        .card-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid #33415580;
            padding-top: 12px;
            font-size: 0.8rem;
            color: var(--text-secondary);
            margin-top: auto;
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
            padding: 8px 14px;
            border-radius: 8px;
            font-size: 0.88rem;
            width: 260px;
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
            max-width: 480px;
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
            color: var(--text-secondary);
            white-space: nowrap;
        }}
        .td-score {{
            font-size: 1rem;
            color: #38bdf8;
            font-weight: 700;
            white-space: nowrap;
        }}
        .table-btn {{
            background: #334155;
            color: #f8fafc;
            padding: 5px 12px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.8rem;
            font-weight: 600;
            display: inline-block;
        }}
        .table-btn:hover {{
            background: #0284c7;
        }}
        footer {{
            margin-top: 48px;
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
                <h1>{company_name} 통합 인텔리전스 마켓 에이전트</h1>
                <div class="header-subtitle">
                    분야별 실시간 모니터링: <strong>제조업 AI 비전 검사</strong> & <strong>AI B2B 마케팅 자동화</strong>
                </div>
            </div>
            <div class="header-meta">
                <span class="header-badge">추천 엔진: {scoring_mode_badge}</span>
                <span class="header-badge" style="background: #1e293b; color: #94a3b8;">생성: {now_str}</span>
            </div>
        </header>

        <!-- TOP Menu Navigation Bar (분야별 메뉴바) -->
        <nav class="domain-navbar">
            <button class="nav-tab active" id="tabAll" onclick="switchDomain('all', this)">
                <span>🌐</span> 전체 통합 인텔리전스 <span class="nav-badge" id="badgeAll">{len(df_rec)}</span>
            </button>
            <button class="nav-tab" id="tabMfg" onclick="switchDomain('manufacturing', this)">
                <span>🏭</span> 제조업 AI 분야 <span class="nav-badge" id="badgeMfg">{mfg_count}</span>
            </button>
            <button class="nav-tab" id="tabMkt" onclick="switchDomain('marketing', this)">
                <span>📢</span> AI 마케팅 분야 <span class="nav-badge" id="badgeMkt">{mkt_count}</span>
            </button>
        </nav>

        <!-- KPI Metrics Grid -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <span class="kpi-title">총 수집 분석 기사</span>
                <span class="kpi-value">{total_evaluated}건</span>
                <span class="kpi-subtext">공개 RSS, 포털, 논문 실시간 집계</span>
            </div>
            <div class="kpi-card">
                <span class="kpi-title">엄선 추천 인텔리전스</span>
                <span class="kpi-value" style="color: #38bdf8;">{len(df_rec)}선</span>
                <span class="kpi-subtext">맞춤형 가중치 및 LLM 전략 평가</span>
            </div>
            <div class="kpi-card">
                <span class="kpi-title">제조업 AI 추천 비중</span>
                <span class="kpi-value" style="color: #60a5fa;">{mfg_count}건</span>
                <span class="kpi-subtext">비전 품질검사 / 스마트공장 R&D</span>
            </div>
            <div class="kpi-card">
                <span class="kpi-title">AI 마케팅 추천 비중</span>
                <span class="kpi-value" style="color: #f472b6;">{mkt_count}건</span>
                <span class="kpi-subtext">애드테크 / 마케팅 자동화 / CRM</span>
            </div>
        </div>

        <!-- Section: Top 10 Priority Intelligence -->
        <div class="section-header">
            <h2 class="section-title">🔥 분야별 실시간 전략 추천 TOP 10</h2>
            <span style="font-size: 0.88rem; color: #94a3b8;" id="topSubtext">현재 메뉴: 전체 인텔리전스</span>
        </div>
        <div class="top-grid" id="topGrid">
            {top_10_html}
        </div>

        <!-- Section: All Recommended News Table -->
        <div class="section-header">
            <h2 class="section-title">📋 인텔리전스 종합 리스트</h2>
        </div>

        <div class="controls">
            <div class="filter-buttons">
                <button class="filter-btn active" onclick="filterCategory('all', this)">전체 ({len(df_rec)})</button>
                <button class="filter-btn" onclick="filterCategory('marketing', this)">📢 AI 마케팅 ({category_counts.get('marketing', 0)})</button>
                <button class="filter-btn" onclick="filterCategory('tech', this)">🔬 기술·R&D ({category_counts.get('tech', 0)})</button>
                <button class="filter-btn" onclick="filterCategory('policy', this)">🏛️ 정부지원·정책 ({category_counts.get('policy', 0)})</button>
                <button class="filter-btn" onclick="filterCategory('market', this)">📈 시장동향 ({category_counts.get('market', 0)})</button>
                <button class="filter-btn" onclick="filterCategory('competitor', this)">⚔️ 경쟁사 ({category_counts.get('competitor', 0)})</button>
            </div>
            <input type="text" id="searchInput" class="search-input" placeholder="키워드/제목 실시간 검색..." onkeyup="applyAllFilters()">
        </div>

        <div class="table-wrap">
            <table id="newsTable">
                <thead>
                    <tr>
                        <th>순위</th>
                        <th>분야 / 카테고리</th>
                        <th>기사 제목 및 추천 이유</th>
                        <th>출처 / 일자</th>
                        <th>점수</th>
                        <th>링크</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
                    {table_rows_html}
                </tbody>
            </table>
        </div>

        <footer>
            <p>Generated by <strong>Project 1: Market Intelligence Agent</strong> for {company_name}</p>
            <p>Hosted on GitHub Pages | Static Multi-Domain Intelligence System</p>
        </footer>
    </div>

    <script>
        let currentDomain = 'all';
        let currentCategory = 'all';

        function switchDomain(domain, btn) {{
            currentDomain = domain;
            document.querySelectorAll('.nav-tab').forEach(t => {{
                t.classList.remove('active');
                t.classList.remove('marketing-active');
            }});
            btn.classList.add('active');
            if (domain === 'marketing') {{
                btn.classList.add('marketing-active');
            }}

            const subtext = document.getElementById('topSubtext');
            if (domain === 'all') subtext.innerText = '현재 메뉴: 전체 통합 인텔리전스';
            else if (domain === 'manufacturing') subtext.innerText = '현재 메뉴: 제조업 AI 인텔리전스';
            else if (domain === 'marketing') subtext.innerText = '현재 메뉴: AI 마케팅 인텔리전스';

            applyAllFilters();
        }}

        function filterCategory(category, btn) {{
            currentCategory = category;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            applyAllFilters();
        }}

        function applyAllFilters() {{
            const searchVal = document.getElementById('searchInput').value.toLowerCase().trim();

            // Filter TOP 10 Cards
            const cards = document.querySelectorAll('.top-card');
            cards.forEach(card => {{
                const d = card.getAttribute('data-domain');
                const c = card.getAttribute('data-category');
                const text = card.innerText.toLowerCase();

                const matchDomain = (currentDomain === 'all' || d === currentDomain);
                const matchCat = (currentCategory === 'all' || c === currentCategory);
                const matchSearch = (!searchVal || text.includes(searchVal));

                if (matchDomain && matchCat && matchSearch) {{
                    card.style.display = '';
                }} else {{
                    card.style.display = 'none';
                }}
            }});

            // Filter Table Rows
            const rows = document.querySelectorAll('.table-row');
            rows.forEach(row => {{
                const d = row.getAttribute('data-domain');
                const c = row.getAttribute('data-category');
                const text = row.innerText.toLowerCase();

                const matchDomain = (currentDomain === 'all' || d === currentDomain);
                const matchCat = (currentCategory === 'all' || c === currentCategory);
                const matchSearch = (!searchVal || text.includes(searchVal));

                if (matchDomain && matchCat && matchSearch) {{
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
