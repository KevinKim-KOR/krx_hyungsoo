# 2025-12-08 백테스트/튜닝 수정 작업 기록

## 작업 개요

**날짜**: 2025-12-08  
**목표**: 백테스트 엔진 문제 해결 및 튜닝 기능 정상화

---

## 1. 해결된 문제들

### 1.1 API 서버 문제
| 문제 | 원인 | 해결 |
|------|------|------|
| 포트 충돌 | 이전 프로세스 미종료 | `taskkill /PID` 실행 |
| 422 에러 | `TuningRequest` 기본값 누락 | 기본값 추가 |
| `threading` import 누락 | 캐시 업데이트 기능 추가 시 누락 | import 추가 |

### 1.2 데이터 타입 문제
| 문제 | 원인 | 해결 |
|------|------|------|
| `Cannot compare Timestamp with datetime.date` | 캐시 인덱스 타입 불일치 | 인덱스를 `pd.Timestamp`로 통일 |
| `sort_index()` 오류 | 혼합 인덱스 타입 | 병합 전 타입 변환 |

### 1.3 성과 계산 문제
| 문제 | 원인 | 해결 |
|------|------|------|
| CAGR 12000% | 짧은 기간 연율화 왜곡 | 제한 적용 (임시) |
| MDD -400% | 이중 퍼센트 변환 | 변환 제거 |
| 승률 0% | `Trade` 클래스에 `pnl` 없음 | 엔진 metrics 사용 |

### 1.4 캐시 업데이트 문제
| 문제 | 원인 | 해결 |
|------|------|------|
| 619개 실패 | 타입 비교 오류 | 인덱스 타입 통일 |
| UI 진행 상황 미표시 | 폴링 로직 오류 | 항상 폴링하도록 수정 |
| 스킵/실패 구분 안됨 | 상태 분리 안됨 | `skipped`, `failed` 분리 |

### 1.5 클라우드 Crontab 문제
| 문제 | 원인 | 해결 |
|------|------|------|
| 평일 작업 미실행 | cron 서비스 문제 | `systemctl restart cron` |

---

## 2. 수정된 파일 목록

### 백엔드
- `api_backtest.py` - 캐시 업데이트 API, threading import
- `app/services/backtest_service.py` - 컬럼명 매핑, 퍼센트 변환 수정
- `app/services/tuning_service.py` - end_date 캐시 범위 검증
- `app/services/history_service.py` - 로컬 타임존 적용
- `core/engine/backtest.py` - CAGR 제한 적용
- `core/data/filtering.py` - ETF 코드 필터링 개선
- `extensions/backtest/runner.py` - date→Timestamp 변환

### 프론트엔드
- `web/dashboard/src/pages/Strategy.tsx` - 캐시 관리 UI 추가

### 스크립트
- `scripts/update_cache.py` - 캐시 업데이트 스크립트
- `scripts/automation/cron_wrapper.sh` - cron 래퍼 스크립트

---

## 3. 남은 작업

### 3.1 근본적 개선 필요
- [ ] CAGR 계산 로직 수정 (Jason 방식 적용)
- [ ] MDD 부호 통일 (양수로 표시)
- [ ] Sharpe 계산 수정 (일간 수익률 기반)
- [ ] 캐시 인덱스 전체 마이그레이션

### 3.2 문서화
- [x] 비교 분석 문서 작성
- [x] 개선 계획 문서 작성
- [x] 작업 기록 문서 작성

---

## 4. 커밋 이력

```
1cb7ee6a - Fix cache update: convert existing index to Timestamp before sort_index
3b6b4d48 - Fix cache update: Timestamp vs date comparison error
f9c73e6f - Improve cache update: distinguish skip vs fail, show error details
27f26d4f - Fix cache UI: always poll status, immediate feedback on click
90a7aaee - Fix: add missing threading import
3ea24d55 - Add cache update UI: status display, update button with progress
fad6809a - Fix: local timezone for DB, cache update script, cron wrapper, limit CAGR annualization
843c72b9 - Fix tuning: validate end_date against cache data range, fix win_rate calculation
```

---

## 5. 참고 사항

### 5.1 클라우드 Crontab
- 서비스: Oracle Cloud VM (Ubuntu)
- 경로: `/home/ubuntu/krx_hyungsoo`
- 재시작 명령: `sudo systemctl restart cron`

### 5.2 캐시 데이터
- 경로: `data/cache/`
- 파일 수: 712개 ETF
- 최신 날짜: 2025-12-08

### 5.3 다음 분석 대상
- Jason GitHub: https://github.com/jasonisdoing/momentum-etf
- 핵심 파일: `logic/backtest/account_runner.py`
