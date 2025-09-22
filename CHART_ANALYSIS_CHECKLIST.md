# 차트 분석 자동화 체크리스트

## 📋 요구사항 정리
- **대장주/인기 코인**: 5분마다 자동 갱신 (BTC, ETH, ADA 등)
- **알트코인**: 유저 API 요청 시에만 분석
- **기존 테이블 활용**: `latest_analysis_reports` 대신 기존 테이블 사용
- **리소스 절약**: 중복 분석 방지, 캐시 활용

## ✅ 체크리스트

### 1단계: 기존 테이블 구조 파악 및 수정
- [x] 기존 테이블 스키마 확인 (`asset_symbol`, `quant_score`, `social_score`, `risk_score`, `overall_score`, `market_regime`, `analyst_summary`, `full_report`, `status`, `created_at`, `expires_at`)
- [x] 테이블명 확인 (`latest_analysis_reports`)
- [x] 인덱스 및 제약조건 확인 (asset_symbol이 PK)
- [x] 필요시 테이블 구조 수정 (expires_at 활용한 캐시 로직)

### 2단계: 대장주/인기 코인 목록 정의
- [x] 정기 분석할 코인 목록 정의 (BTC/USDT, ETH/USDT, XRP/USDT, ADA/USDT, SOL/USDT, DOT/USDT, MATIC/USDT, AVAX/USDT)
- [x] Celery Beat 스케줄에 각 코인별 태스크 추가
- [x] 코인별 분석 주기 설정 (5분마다)

### 3단계: 기존 API 연동 방식 설계
- [x] 기존 차트 분석 API 확인 (`/quantitative/analyze`)
- [x] API 호출 방식 결정 (내부 호출 - QuantitativeServiceV2 직접 사용)
- [x] 요청/응답 데이터 매핑 설계 (analysis → quant_score, detailed_data → full_report)
- [x] 에러 처리 및 재시도 로직 설계

### 4단계: Repository 레이어 수정
- [x] 기존 테이블에 맞는 Repository 메서드 구현
- [x] 캐시 로직 구현 (expires_at 기반)
- [x] UPSERT 로직 구현 (기존 데이터 업데이트)
- [x] 조회 메서드 구현 (캐시된 데이터 반환)

### 5단계: Function 레이어 수정
- [x] 기존 API 호출 로직 구현 (QuantitativeServiceV2 직접 사용)
- [x] 데이터 변환 로직 구현 (API 응답 → DB 스키마)
- [x] 캐시 확인 로직 구현 (expires_at 기반)
- [x] 에러 처리 및 로깅 구현
- [x] 배치 처리 로직 구현 (한 번에 여러 코인 처리)

### 6단계: Celery 태스크 구현
- [x] 정기 분석 태스크 구현 (대장주/인기 코인) - 배치 처리 방식
- [x] 온디맨드 분석 태스크 구현 (알트코인) - 단일 코인 분석
- [x] 태스크 스케줄링 설정 (5분마다 배치 분석)
- [x] 태스크 모니터링 및 로깅

### 7단계: API 엔드포인트 수정
- [x] 기존 API에 캐시 확인 로직 추가
- [x] 캐시된 데이터가 있으면 즉시 반환
- [x] 캐시된 데이터가 없으면 분석 실행 후 반환
- [x] 알트코인 요청 시 온디맨드 분석 트리거

### 8단계: 테스트 및 검증
- [x] 단위 테스트 작성 (test_chart_analysis.py)
- [x] 통합 테스트 실행 (시스템 전체 테스트)
- [x] 성능 테스트 (리소스 사용량 확인)
- [x] 캐시 동작 검증 (expires_at 기반)

### 9단계: 배포 및 모니터링
- [x] Docker Compose 설정 업데이트 (Redis 서비스 추가)
- [x] Celery Worker/Beat 실행 스크립트 작성
- [x] 로깅 및 모니터링 설정
- [ ] 운영 환경 배포

## 🎯 현재 상태
- [x] 요구사항 파악 완료
- [x] 체크리스트 작성 완료
- [x] 1-8단계 완료 ✅
- [x] 시스템 구현 완료 ✅

## 🎉 구현 완료!

**차트 분석 자동화 시스템**이 성공적으로 구현되었습니다!

### ✅ 완료된 기능:
1. **배치 처리 방식** - 8개 주요 코인을 한 번에 처리
2. **캐시 시스템** - `expires_at` 기반 5분 캐시
3. **온디맨드 분석** - 알트코인 요청 시 즉시 분석
4. **API 엔드포인트** - 캐시 기반 분석 API 제공
5. **모니터링** - 상세한 로깅 및 통계

### 🚀 사용 방법:
1. **Docker Compose 실행**: `docker-compose up -d`
2. **Celery Worker 실행**: `./scripts/start_celery_worker.sh`
3. **Celery Beat 실행**: `./scripts/start_celery_beat.sh`
4. **테스트 실행**: `python scripts/test_chart_analysis.py`

### 📊 API 엔드포인트:
- `GET /quantitative/analyze/cached` - 캐시 기반 분석
- `GET /quantitative/analyze/all` - 모든 코인 조회
- `POST /quantitative/analyze/trigger` - 알트코인 분석 트리거
