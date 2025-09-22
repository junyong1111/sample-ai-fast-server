-- 소셜 분석 테이블 생성
CREATE TABLE social_analysis_reports (
    id SERIAL PRIMARY KEY,
    asset_symbol VARCHAR(32) NOT NULL,
    social_score NUMERIC(5,2) DEFAULT 0,
    sentiment VARCHAR(16) DEFAULT 'neutral',
    social_sources JSONB,
    full_analysis_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '1 hour')
);

-- 인덱스 생성
CREATE INDEX idx_social_analysis_symbol ON social_analysis_reports(asset_symbol);
CREATE INDEX idx_social_analysis_timestamp ON social_analysis_reports(created_at);
CREATE INDEX idx_social_analysis_expires ON social_analysis_reports(expires_at);
CREATE INDEX idx_social_analysis_sentiment ON social_analysis_reports(sentiment);
CREATE INDEX idx_social_analysis_sources ON social_analysis_reports USING GIN(social_sources);
CREATE INDEX idx_social_analysis_data ON social_analysis_reports USING GIN(full_analysis_data);
