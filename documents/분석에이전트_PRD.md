Phase 1: 코어 인프라 리팩토링 (Core Infrastructure)
목표: 여러 자산을 효율적으로 분석하고 비용을 최적화할 수 있는 기반을 구축합니다.

[ ] 1-1. 하이브리드 분석 시스템 구축 (Caching & Scheduling)

[ ] 1-1-1. 데이터베이스 설계: latest_analysis_reports 테이블을 신규 생성하여, 각 자산(asset_symbol)별 전체 분석 결과(full_report)와 타임스탬프를 저장할 수 있도록 설계.

[ ] 1-1-2. 백그라운드 스케줄러 구축: 5분마다 주요 코인(BTC, ETH 등)을 미리 분석하고 결과를 DB에 저장하는 Analysis_Scheduler 워크플로우를 신규 개발.

[ ] 1-1-3. 통합 분석 API 엔드포인트 개발: GET /api/v2/analysis API를 신규 개발. 이 API는 요청받은 자산에 대해 DB를 우선 조회하고, 데이터가 없을 경우에만 실시간 분석을 호출하는 캐싱 로직을 포함.

Phase 2: 분석 에이전트 고도화 (Agent Advancement)
목표: 기존의 BTC 전용 분석 에이전트들을, 어떤 자산이든 분석할 수 있는 범용 모듈로 확장하고 기능을 보강합니다.

[ ] 2-1. 📈 퀀트 분석 에이전트 (AXIS-Quant) 고도화

[x] 바이낸스 API로 OHLCV 데이터 수집 기능 구현

[x] TA-Lib을 이용해 기술적 지표 계산 로직 구현

[x] 시장 레짐(추세/횡보) 진단 로직 구현

[x] 최종 Technical Score를 JSON으로 출력하는 FastAPI 엔드포인트 생성

[ ] 2-1-1. [신규] API 일반화: FastAPI 엔드포인트를 /analyze/quant/{asset_symbol} 형태로 수정하여, 모든 자산을 동적으로 분석할 수 있도록 변경.

[ ] 2-2. 🌐 컨텍스트/심리 분석 에이전트 (AXIS-Social) 고도화

[x] Reddit API 연동 및 투자 심리 분석 로직 구현

[ ] 2-2-1. [신규] News API 연동 및 키워드 기반 뉴스 감성 분석 로직 구현.

[ ] 2-2-2. [신규] Glassnode API 연동 및 온체인 데이터 수집/분석 로직 구현.

[ ] 2-2-3. [신규] API 일반화: FastAPI 엔드포인트를 /analyze/social/{asset_symbol} 형태로 수정하고, 내부 툴과 프롬프트가 asset_symbol 변수를 사용하도록 변경.

[ ] 2-2-4. [신규] 최종 스코어 통합: On-chain Score, Off-chain Score 등을 종합하여 Social Score를 JSON으로 출력하도록 로직 완성.

[ ] 2-3. 🛡️ 리스크 분석 에이전트 (AXIS-Risk) 고도화

[x] yfinance 등을 이용해 나스닥, 달러 인덱스 데이터 수집 기능 구현

[x] LangChain/LangGraph를 활용한 AI 분석 및 요약 기능 구현

[x] Market Risk Level을 JSON으로 출력하는 FastAPI 엔드포인트 생성

[ ] 2-3-1. [신규] 다각화 리스크 분석: 비트코인 변동성뿐만 아니라, 요청된 자산(asset_symbol)과 다른 주요 자산들 간의 상관관계를 동적으로 계산하는 로직으로 확장.

[ ] 2-3-2. [신규] API 일반화: FastAPI 엔드포인트를 /analyze/risk/{asset_symbol} 형태로 수정하여, 모든 자산 기반의 시장 리스크를 분석할 수 있도록 변경.