# 🚀 자동 매매 시스템 (Auto Trading System)

Binance Testnet을 이용한 거래 신호 기반 자동 매매 시스템입니다.

## 📋 목차

- [기능 소개](#-기능-소개)
- [설치 및 설정](#-설치-및-설정)
- [사용 방법](#-사용-방법)
- [API 엔드포인트](#-api-엔드포인트)
- [테스트](#-테스트)
- [주의사항](#-주의사항)

## ✨ 기능 소개

### 🔍 거래 신호 분석
- **기술적 지표**: RSI, MACD, 볼린저 밴드, 모멘텀 등
- **자동 신호 생성**: BUY/SELL/HOLD 신호 자동 생성
- **MongoDB 저장**: 모든 거래 신호를 데이터베이스에 저장

### 🚀 자동 매매 실행
- **거래 신호 기반**: 분석된 신호에 따른 자동 매매
- **리스크 관리**: 거래당 리스크 비율 설정 가능
- **다양한 주문 타입**: 시장가, 지정가 주문 지원

### 📊 계정 관리
- **잔고 조회**: 실시간 계정 잔고 확인
- **주문 관리**: 주문 상태 조회, 취소 등
- **거래 내역**: 모든 거래 내역 추적

## 🛠️ 설치 및 설정

### 1. Binance Testnet API 키 발급

1. [Binance Testnet](https://testnet.binance.vision/) 접속
2. 로그인 또는 회원가입
3. **"Generate HMAC_SHA256 Key"** 클릭
4. API Key와 Secret Key 저장

### 2. 환경변수 설정

```bash
# Binance Testnet 설정
export BINANCE_TESTNET_API_KEY="your_testnet_api_key"
export BINANCE_TESTNET_SECRET_KEY="your_testnet_secret_key"
export BINANCE_TESTNET_URL="https://testnet.binance.vision"

# MongoDB 설정 (이미 설정되어 있음)
export MONGODB_URL="mongodb://localhost:27017"
export MONGODB_DATABASE="autotrading"
```

### 3. 서비스 시작

```bash
# Docker Compose로 서비스 시작
docker compose up -d

# 또는 개별 서비스 시작
docker compose up fastapi mongodb -d
```

## 📖 사용 방법

### 1. 거래 신호 확인

```bash
# 상세 거래 신호 조회
curl "http://localhost:8000/api/v1/autotrading/charts/signal/binance/BTC/USDT/detailed?count=100&period=1d"
```

### 2. 계정 상태 확인

```bash
# 계정 잔고 및 상태 확인
curl "http://localhost:8000/api/v1/autotrading/trading/account/status"
```

### 3. 자동 매매 실행

```bash
# 거래 신호 기반 전략 실행
curl -X POST "http://localhost:8000/api/v1/autotrading/trading/execute/strategy?market=BTC/USDT&risk_per_trade=0.01&order_type=market"
```

### 4. 주문 관리

```bash
# 미체결 주문 조회
curl "http://localhost:8000/api/v1/autotrading/trading/orders/open"

# 특정 주문 상태 조회
curl "http://localhost:8000/api/v1/autotrading/trading/orders/{order_id}/status?market=BTC/USDT"

# 주문 취소
curl -X DELETE "http://localhost:8000/api/v1/autotrading/trading/orders/{order_id}?market=BTC/USDT"
```

## 🔌 API 엔드포인트

### 💰 거래 계정
- `GET /trading/account/status` - 계정 상태 확인

### 🚀 자동 매매
- `POST /trading/execute/signal` - 거래 신호 실행
- `POST /trading/execute/strategy` - 전략 실행

### 📋 주문 관리
- `GET /trading/orders/{order_id}/status` - 주문 상태 조회
- `DELETE /trading/orders/{order_id}` - 주문 취소
- `GET /trading/orders/open` - 미체결 주문 조회

### 🧪 테스트
- `GET /trading/test/connection` - 연결 테스트

## 🧪 테스트

### 1. 테스트 스크립트 실행

```bash
# 거래 기능 테스트
python test_trading.py
```

### 2. API 연결 테스트

```bash
# FastAPI 서버 상태 확인
curl "http://localhost:8000/health"

# Binance 연결 테스트
curl "http://localhost:8000/api/v1/autotrading/trading/test/connection"
```

### 3. 거래 신호 테스트

```bash
# 거래 신호 생성 및 저장 테스트
curl "http://localhost:8000/api/v1/autotrading/charts/signal/binance/BTC/USDT/detailed?count=100&period=1d"

# 저장된 신호 조회
curl "http://localhost:8000/api/v1/autotrading/charts/signals/history?exchange=binance&market=BTC/USDT&limit=10&skip=0"
```

## ⚠️ 주의사항

### 🔒 보안
- **API 키는 절대 공개하지 마세요!**
- **Secret Key는 안전한 곳에 보관하세요!**
- **테스트넷 API 키는 실제 거래에 사용하지 마세요!**

### 💰 리스크 관리
- **거래당 리스크 비율을 적절히 설정하세요** (기본값: 1%)
- **테스트넷에서 충분히 테스트한 후 실제 거래를 고려하세요**
- **자동 매매 시스템의 성능을 지속적으로 모니터링하세요**

### 🔄 테스트넷 특성
- **월 1회 리셋**: 테스트넷은 월 1회 데이터가 리셋됩니다
- **가상 자금**: 실제 자금은 사용되지 않습니다
- **API 제한**: 실제 API와 동일한 제한이 적용됩니다

## 🚀 다음 단계

1. **실제 API 연동**: Live Binance API로 전환
2. **고급 전략**: 더 복잡한 거래 전략 구현
3. **백테스팅**: 과거 데이터를 이용한 전략 검증
4. **모니터링**: 실시간 거래 모니터링 시스템 구축
5. **알림**: 텔레그램, 이메일 등 알림 시스템 연동

## 📞 지원

문제가 발생하거나 질문이 있으시면:
1. 로그 확인: `docker logs fastapi`
2. API 상태 확인: `/health` 엔드포인트
3. 연결 테스트: `/trading/test/connection` 엔드포인트

---

**🎯 안전하고 수익성 있는 자동 매매를 위한 첫 걸음을 시작하세요!**
