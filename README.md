# Project 1: Market Agent (`project1-market-agent`)

NovaFactory AI를 위한 시장, 경쟁사, 정책 및 정부지원, 기술동향 수집 및 분석 자동화 에이전트 프로젝트입니다.

## 1. 프로젝트 구조 (Project Structure)
```
ex1/
├── .github/
│   └── workflows/
├── config/
│   └── company_profile.yaml   # 기업 프로필, 경쟁사, 키워드 설정
├── data/
│   ├── fallback/              # 합성 fallback 데이터셋
│   ├── raw/                   # 수집된 원본 데이터 저장소
│   └── processed/             # 전처리/정제 완료된 데이터 저장소
├── docs/                      # 프로젝트 문서 및 산출물
├── logs/                      # 실행 로그 및 계획서
├── src/                       # 핵심 소스 코드 모듈
├── .env.example               # 환경변수 예시 파일
├── .gitignore                 # Git 제외 파일 목록
├── README.md                  # 프로젝트 안내서
└── requirements.txt           # 의존성 패키지 목록
```

## 2. 기업 프로필 및 분석 기준 (`config/company_profile.yaml`)
- **기업명**: NovaFactory AI
- **주요 사업**: 제조업 AI 비전 품질검사
- **핵심 제품**:
  - 비전 기반 불량 탐지 SaaS
  - 제조 품질 리포트 자동화
- **타깃 시장**: 중소·중견 제조기업, 스마트팩토리 구축 기업
- **주요 경쟁사**: VisionForge, InspectAI, FactoryMind, QualiBot
- **관심 키워드**: AI, 스마트팩토리, 품질검사, 자동화, 클라우드, 제조 AX
- **지원/정책 키워드**: 창업지원, AI 바우처, 스마트공장, R&D, 사업화 자금

## 3. 시작하기 (Quick Start)
```bash
# 가상환경 생성 및 활성화
py -3.12 -m venv .venv
.venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```
