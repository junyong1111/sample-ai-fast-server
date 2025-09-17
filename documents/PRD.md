AXIS: AI 기반 자동매매 시스템 제품 요구사항 명세서 (PRD)
문서 버전: 1.0

작성일: 2025년 9월 17일

프로젝트 오너: 준용

1. 개요 (Introduction)
1.1. 프로젝트 비전
**AXIS (Automated eXchange Investment System)**는 24시간 변동하는 암호화폐 시장에 대응하여, 데이터 기반의 지능적인 의사결정을 통해 사용자의 자산을 자동으로 운용하는 AI 포트폴리오 관리 시스템을 구축하는 것을 목표로 한다. 인간의 감정적 판단을 배제하고, 복잡한 시장 데이터를 실시간으로 분석하여 지속 가능한 수익 창출을 추구한다.

1.2. 문제 정의 (Problem Statement)
기회의 상실: 개인 투자자는 24시간 시장에 대응할 수 없어, 상승장 내의 단기적인 수익 기회("발라먹기")를 놓치거나 급작스러운 하락에 제때 대응하지 못한다.

정보의 비대칭성: 시장에는 수많은 데이터(차트, 뉴스, 온체인)가 존재하지만, 이를 종합적으로 분석하여 투자 결정에 활용하기는 매우 어렵다.

비용의 비효율성: 여러 명의 사용자가 동일한 자산을 분석할 때마다 중복으로 API가 호출되어, 시스템 확장 시 비용이 기하급수적으로 증가한다.

경직된 전략: 기존의 트레이딩 봇은 대부분 정해진 규칙(Rule-based)에 따라 움직여, 시장 상황 변화에 유연하게 대처하지 못한다.

1.3. 목표 고객 (Target Audience)
데이터 기반의 체계적인 투자에 관심이 많은 기술 친화적 암호화폐 투자자.

시간 제약으로 인해 24시간 시장을 모니터링하기 어려운 직장인 또는 전문직 투자자.

다양한 투자 성향(안정 추구형부터 공격적인 단기 트레이더까지)을 가진 개인 투자자.

2. 시스템 아키텍처 (System Architecture)
본 시스템은 '백그라운드 스케줄러' 가 주요 자산을 주기적으로 사전 분석하고, '통합 분석 API' 가 이를 캐시처럼 활용하며, 필요시 알트코인을 실시간 분석하는 하이브리드 구조를 채택한다. 최종 결정은 'The Brain' 이 내리고 '실행 에이전트' 가 거래를 수행한다.

graph TD
    subgraph "백그라운드 (5분마다 실행)"
        Scheduler["Scheduler Trigger"] --> Major_Coins["주요 코인 목록"]
        Major_Coins --> BG_Analysts["The Analysts 호출"]
        BG_Analysts --> DB_Cache["DB에 분석 결과 저장"]
    end

    subgraph "실시간 (사용자 요청 시 실행)"
        User_Request["Autotrading 워크플로우"] --> API["통합 분석 API 호출"]
        API -- "DB 조회 (캐시 확인)" --> DB_Cache
        API -- "실시간 분석 (캐시 없음)" --> RT_Analysts["The Analysts 호출"]
        RT_Analysts --> API
        API --> The_Brain["The Brain (의사결정)"]
        The_Brain --> Execution["거래 실행 에이전트"]
        Execution --> Exchange["거래소 API"]
    end

    subgraph "데이터 저장소"
        DB_Cache[(Database: latest_analysis_reports)]
    end

3. n8n 워크플로우 시각화 (n8n Workflow Visualization)
3.1. Autotrading(준용) 워크플로우
역할: 전체 자동매매 프로세스를 오케스트레이션하는 메인 워크플로우. The Analysts를 호출하여 분석 보고서를 받고, The Brain을 통해 최종 거래 결정을 내린 후 주문을 실행합니다.

graph TD
    A["Schedule Trigger (5분)"] --> B["Get User Trading Info"];
    B --> C["Call 'The Analysts-refactoring'"];
    C --> D["Get My Account (잔고조회)"];
    B & C & D --> E["Merge Data"];
    E --> F["The Brain AI Agent"];
    F --> G["Parse AI Output (Code Node)"];
    G --> H{"Action != HOLD?"};
    H -- Yes --> I["Execute Trade API"];
    H -- No --> J["End"];
    I --> J;

3.2. The Analysts-refactoring 워크플로우
역할: 특정 자산(asset_symbol)에 대한 모든 분석(Quant, Social, Risk)을 수행하고, 하나의 종합 보고서를 반환하는 서브 워크플로우.

graph TD
    subgraph "The Analysts-refactoring"
        A["Webhook Trigger (asset_symbol 입력)"] --> B{"분석 병렬 실행"};
        B -- Quant --> C["Chart Analysis Agent"];
        B -- Social --> D["Social Analysis Agent"];
        B -- Risk --> E["Risk Analysis Agent"];
        C & D & E --> F["Aggregate Results"];
        F --> G["Respond to Webhook"];
    end

4. 데이터베이스 구조 (Database Schema)
제공해주신 테이블 구조를 바탕으로 한 Entity-Relationship Diagram (ERD) 입니다.

erDiagram
    user_master {
        int idx PK
        varchar user_id
        varchar name
        text role
        bool status
    }

    user_trading_settings {
        int user_idx PK, FK
        varchar personality FK
        numeric max_position_pct
    }

    user_exchange_credentials {
        int idx PK
        int user_idx FK
        int exchange_idx FK
        text access_key_ref
        text secret_key_ref
    }

    exchange_master {
        int idx PK
        varchar code
        varchar name
    }

    trading_cycles {
        int idx PK
        int user_idx FK
        int analysis_report_idx FK
        jsonb used_strategy_weights
        jsonb prime_agent_decision
    }

    analysis_reports {
        int idx PK
        int user_idx FK
        varchar market_regime
        jsonb used_regime_weights
        jsonb quant_report
        jsonb social_report
        jsonb risk_report
        jsonb analyst_summary
    }

    trades {
        int idx PK
        int cycle_idx FK
        varchar market
        varchar action
        numeric quantity
        numeric price
    }

    positions {
        int idx PK
        int user_idx FK
        varchar market
        varchar status
        int entry_cycle_idx FK
        int exit_cycle_idx FK
    }

    portfolio_snapshots {
        int idx PK
        int cycle_idx FK
        numeric total_value_usdt
        jsonb asset_balances
    }

    strategy_weights {
        int idx PK
        varchar personality PK
        numeric weight_quant
        numeric weight_social
        numeric weight_risk
    }

    regime_weights_trend {
        int idx PK
        varchar indicator
        numeric weight
    }

    regime_weights_range {
        int idx PK
        varchar indicator
        numeric weight
    }

    user_master ||--o{ user_trading_settings : "has"
    user_master ||--o{ user_exchange_credentials : "has"
    user_master ||--o{ trading_cycles : "has"
    user_master ||--o{ analysis_reports : "has"
    user_master ||--o{ positions : "has"
    exchange_master ||--o{ user_exchange_credentials : "belongs to"
    trading_cycles ||--o{ trades : "generates"
    trading_cycles ||--o{ positions : "opens/closes"
    trading_cycles ||--o{ portfolio_snapshots : "creates"
    trading_cycles }|--|| analysis_reports : "uses"
    strategy_weights }|--|| user_trading_settings : "defines"

5. 개발 계획 및 체크리스트 (Roadmap & Checklist)
Phase 1: 코어 인프라 리팩토링 (Core Infrastructure)
[ ] 1-1. 하이브리드 분석 시스템 구축 (Caching & Scheduling)

[ ] 1-1-1. 데이터베이스 설계: latest_analysis_reports 테이블을 신규 생성.

[ ] 1-1-2. 백그라운드 스케줄러 구축: 5분마다 주요 코인을 미리 분석하는 Analysis_Scheduler 워크플로우를 신규 개발.

[ ] 1-1-3. 통합 분석 API 엔드포인트 개발: GET /api/v2/analysis API를 신규 개발 (캐싱 로직 포함).

Phase 2: 분석 에이전트 고도화 (Agent Advancement)
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

Phase 3: 마스터 에이전트 고도화 (The Brain Advancement)
[ ] 3-1. 전술적 트레이딩 기능 도입 (Tactical Trading)

[ ] 3-1-1. 기반 구축: tactical_profit_target_pct 컬럼 추가 및 신규 툴(get_active_position_details, get_short_term_momentum_signals) 개발.

[ ] 3-1-2. The Brain 지능 강화: 프롬프트에 '발라먹기' 로직 추가.

[ ] 3-2. 포트폴리오 다각화 기능 도입 (Portfolio Diversification)

[ ] 3-2-1. The Brain의 CIO 진화: The Brain이 전체 포트폴리오의 목표 배분안을 출력하도록 프롬프트 수정.

[ ] 3-2-2. 리밸런싱 로직 구현: '목표'와 '현재' 포트폴리오를 비교하여, 실행할 거래 목록을 계산하고 순차적으로 실행하는 로직 구현.

Phase 4: 자가 학습 루프 구현 (The Evolution Engine)
[ ] 4-1. 예측 검증 루프 도입 (Prediction Verification)

[ ] 4-1-1. 데이터베이스 확장: positions 테이블에 AI의 미래 예측을 저장할 prediction 컬럼 추가.

[ ] 4-1-2. 신규 에이전트(Performance Reviewer) 개발: 과거 예측과 현실의 차이를 분석하여 "성과 리뷰 보고서"를 생성.

[ ] 4.2. 규칙 자동 최적화 (Automated Rule Tuning)

[ ] 4-2-1. 성과 데이터 분석: 자산별, 전략별 PnL을 분석하는 기능 구현.

[ ] 4-2-2. 규칙 자동 업데이트 (최종 목표): 성과 분석 결과를 바탕으로 DB에 저장된 투자 규칙을 AI가 스스로 미세 조정하는 기능 구현.