# MongoDB 데이터 저장 및 히스토리 관리 가이드

## 🚀 개요

이 프로젝트는 MongoDB를 사용하여 차트 데이터, 지표, AI 분석 결과를 저장하고 관리합니다. 실시간 데이터 수집부터 과거 데이터 분석까지 모든 기능을 제공합니다.

## 📊 데이터 구조

### 1. 차트 데이터 (charts 컬렉션)
```json
{
  "_id": ObjectId,
  "market": "KRW-BTC",
  "timeframe": "minutes:60",
  "timestamp": ISODate("2025-01-23T18:15:00Z"),
  "candle": {
    "open": 159800000,
    "high": 159900000,
    "low": 159700000,
    "close": 159786000,
    "volume": 1234.56
  },
  "indicators": {
    "momentum_cumret": -0.0013,
    "momentum_sharpe_like": -1.46,
    "volume_z": -2.52,
    "return_over_vol": -0.073,
    "rsi": 42.87,
    "bb_pct_b": 0.2428,
    "bb_bandwidth": 0.0049,
    "macd": -138508.79,
    "macd_signal": -147344.76,
    "macd_hist": 8835.97,
    "macd_cross": "none"
  },
  "signals": {
    "rule1_momentum": "neutral",
    "rule2_volume": "neutral",
    "rule3_ret_over_vol": "neutral",
    "rule4_rsi": "neutral",
    "rule5_bollinger": "neutral",
    "rule6_macd": "neutral",
    "overall": "HOLD"
  },
  "created_at": ISODate("2025-01-23T18:15:00Z")
}
```

### 2. AI 분석 결과 (ai_analysis 컬렉션)
```json
{
  "_id": ObjectId,
  "market": "KRW-BTC",
  "timestamp": ISODate("2025-01-23T18:15:00Z"),
  "analysis": {
    "confidence": 0.85,
    "recommendation": "BUY",
    "reasoning": "RSI 과매도 + 볼린저 밴드 하단 + MACD 상향 돌파",
    "risk_level": "medium",
    "target_price": 162000000,
    "stop_loss": 158000000
  },
  "created_at": ISODate("2025-01-23T18:15:00Z")
}
```

## 🔧 설치 및 설정

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. MongoDB 설치 및 실행
```bash
# Docker로 MongoDB 실행
docker run -d --name mongodb \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=admin \
  -e MONGO_INITDB_ROOT_PASSWORD=password \
  mongo:7.0

# 또는 로컬 설치
# https://docs.mongodb.com/manual/installation/
```

### 3. 환경 변수 설정
```bash
export MONGO_URI="mongodb://localhost:27017"
export MONGO_DB="trading_ai"
export MONGO_TTL_DAYS="90"
```

## 📡 API 엔드포인트

### 기본 시그널 API
- `GET /charts/signals/overall` - 기본 시그널 조회
- `GET /charts/signals/overall-with-db` - 시그널 조회 + DB 저장
- `GET /charts/indicators` - 지표 조회
- `GET /charts/indicator/{name}` - 특정 지표 조회
- `GET /charts/rule/{rule}` - 특정 규칙 조회
- `GET /charts/card` - 요약 카드

### 히스토리 API
- `GET /charts/history/analysis` - 과거 데이터 분석
- `GET /charts/history/statistics` - 마켓 통계
- `GET /charts/history/daily-aggregation` - 일별 집계

### AI 분석 API
- `POST /charts/ai/analysis` - AI 분석 결과 저장

### 관리 API
- `POST /charts/admin/cleanup` - 오래된 데이터 정리

## 💻 사용 예시

### 1. 실시간 데이터 저장 및 조회
```python
import requests
import json

# 시그널 계산 + DB 저장
response = requests.get(
    "http://localhost:7000/charts/signals/overall-with-db",
    params={
        "market": "KRW-BTC",
        "tf": "minutes:60",
        "count": 200,
        "save_to_db": True
    }
)

data = response.json()
print(f"저장 상태: {data['saved_to_db']}")
print(f"DB ID: {data.get('db_id')}")
```

### 2. 과거 데이터 분석
```python
# 7일간 히스토리 조회
response = requests.get(
    "http://localhost:7000/charts/history/analysis",
    params={
        "market": "KRW-BTC",
        "tf": "minutes:60",
        "days": 7
    }
)

history = response.json()
print(f"데이터 포인트: {history['data_points']}")
print(f"AI 분석 결과: {len(history['ai_analysis'])}개")
```

### 3. 마켓 통계 조회
```python
# 30일간 통계
response = requests.get(
    "http://localhost:7000/charts/history/statistics",
    params={
        "market": "KRW-BTC",
        "tf": "minutes:60",
        "days": 30
    }
)

stats = response.json()
print(f"총 레코드: {stats['total_records']}")
print(f"평균 RSI: {stats['avg_rsi']:.2f}")
print(f"신호 분포: {stats['signals_summary']}")
```

### 4. AI 분석 결과 저장
```python
# AI 분석 결과 저장
analysis_data = {
    "confidence": 0.92,
    "recommendation": "SELL",
    "reasoning": "RSI 과매수 + 볼린저 밴드 상단 + MACD 하향 돌파",
    "risk_level": "high",
    "target_price": 155000000,
    "stop_loss": 160000000
}

response = requests.post(
    "http://localhost:7000/charts/ai/analysis",
    params={"market": "KRW-BTC"},
    json=analysis_data
)

result = response.json()
print(f"저장 성공: {result['success']}")
```

## 🔍 MongoDB 쿼리 예시

### 1. 특정 마켓의 최신 데이터 조회
```javascript
db.charts.find(
    { "market": "KRW-BTC" },
    { "timestamp": 1, "indicators.rsi": 1, "signals.overall": 1 }
).sort({ "timestamp": -1 }).limit(10)
```

### 2. RSI 과매수/과매도 구간 찾기
```javascript
db.charts.find({
    "market": "KRW-BTC",
    "indicators.rsi": {
        "$or": [
            { "$lt": 30 },  // 과매도
            { "$gt": 70 }   // 과매수
        ]
    }
}).sort({ "timestamp": -1 })
```

### 3. 매수 신호가 많은 구간 찾기
```javascript
db.charts.aggregate([
    {
        "$match": {
            "market": "KRW-BTC",
            "signals.overall": "BUY"
        }
    },
    {
        "$group": {
            "_id": {
                "year": { "$year": "$timestamp" },
                "month": { "$month": "$timestamp" },
                "day": { "$dayOfMonth": "$timestamp" }
            },
            "buy_signals": { "$sum": 1 }
        }
    },
    {
        "$sort": { "_id": -1 }
    }
])
```

### 4. AI 분석 결과 통계
```javascript
db.ai_analysis.aggregate([
    {
        "$match": { "market": "KRW-BTC" }
    },
    {
        "$group": {
            "_id": "$analysis.recommendation",
            "count": { "$sum": 1 },
            "avg_confidence": { "$avg": "$analysis.confidence" }
        }
    }
])
```

## 🚨 주의사항

### 1. 데이터 보존
- TTL 인덱스로 90일 후 자동 삭제
- 중요 데이터는 별도 백업 필요
- `cleanup_old_data` API로 수동 정리 가능

### 2. 성능 최적화
- 복합 인덱스로 빠른 조회 보장
- 집계 파이프라인으로 효율적인 통계 계산
- 연결 풀 설정으로 동시 접속 관리

### 3. 에러 처리
- MongoDB 연결 실패 시 자동 비활성화
- 각 API에서 적절한 에러 메시지 반환
- 로깅으로 문제 추적 가능

## 🔮 향후 확장 계획

### 1. 백테스팅 데이터
- 과거 전략 성과 분석
- 다양한 파라미터 조합 테스트
- 수익률/리스크 지표 계산

### 2. 실시간 알림
- 특정 조건 달성 시 알림
- Slack/Telegram 연동
- 이메일 알림 기능

### 3. 데이터 시각화
- Grafana 대시보드 연동
- 차트 및 지표 시각화
- 실시간 모니터링

## 📞 지원

문제가 발생하거나 질문이 있으시면:
1. 로그 파일 확인 (`logs/app.log`)
2. MongoDB 연결 상태 체크 (`/charts/health`)
3. 에러 메시지 상세 분석

이 가이드를 통해 MongoDB 기반의 완전한 데이터 관리 시스템을 구축할 수 있습니다! 🎯
