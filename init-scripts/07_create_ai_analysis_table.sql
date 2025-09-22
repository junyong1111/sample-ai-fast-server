-- AI 종합 분석 테이블 생성
CREATE TABLE IF NOT EXISTS ai_analysis_reports (
    id SERIAL PRIMARY KEY,
    analysis_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- 각 분석별 데이터 (티커별 key-value)
    chart_analysis JSONB,      -- { "BTC/USDT": {...}, "ETH/USDT": {...} }
    risk_analysis JSONB,       -- { "BTC/USDT": {...}, "ETH/USDT": {...} }
    social_analysis JSONB,     -- { "BTC/USDT": {...}, "ETH/USDT": {...} }

    -- 최종 종합 분석
    final_analysis JSONB,      -- 최종 종합 분석 결과

    -- 데이터 추적 정보 (ID 리스트)
    data_sources JSONB,        -- 어떤 레코드 ID들을 사용했는지
    total_coins INTEGER,       -- 분석한 코인 수

    -- 메타데이터
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '2 hours')
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_ai_analysis_timestamp ON ai_analysis_reports(analysis_timestamp);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_expires ON ai_analysis_reports(expires_at);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_chart_data ON ai_analysis_reports USING GIN(chart_analysis);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_risk_data ON ai_analysis_reports USING GIN(risk_analysis);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_social_data ON ai_analysis_reports USING GIN(social_analysis);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_final_data ON ai_analysis_reports USING GIN(final_analysis);
CREATE INDEX IF NOT EXISTS idx_ai_analysis_sources ON ai_analysis_reports USING GIN(data_sources);
