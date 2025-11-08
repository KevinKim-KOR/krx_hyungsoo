# ARCHITECTURE — 시스템 구조 및 설계 (v2 재작성)

## 1. 설계 목표
- **순차 처리 우선**: 모든 데이터와 연산은 순차적으로 처리한다. 병렬/멀티프로세싱은 금지 (튜닝 단계만 예외).
- **Clean Architecture** 기반: 도메인(core) 독립성 확보, 외부 의존성(infra) 분리.
- **NAS–PC 병행 구조**: NAS(Py3.8)는 운영/알림, PC(Py3.11+)는 백테스트/튜닝.
- **핵심 보유 종목(HOLD_CORE)** 로직을 전략 및 백테스트 단계 모두에 통합.

---

## 2. 시스템 계층 구조
```
app/                    # 애플리케이션 진입점(CLI, API)
 ├─ cli/                # 공용 CLI (Py3.8 호환)
 ├─ services/backtest_api/  # (PC 전용) FastAPI 서비스
core/                   # 도메인 로직 (순수 파이썬, Py3.8 호환)
 ├─ strategy/           # 전략 정의 및 룩백 규칙
 ├─ engine/             # 추천·백테스트 엔진
 ├─ risk/               # 리스크 및 포지션 규칙
 └─ metrics/            # 성과·지표 계산
extensions/             # (Py3.11+) 백테스트·튜닝·병렬화 모듈
infra/                  # 외부 시스템 어댑터
 ├─ data/               # pykrx, naver, yfinance 데이터소스
 ├─ notify/             # Slack, Telegram 등 알림 어댑터
 └─ storage/            # 파일/DB 입출력
configs/                # YAML 설정 (전략·유니버스·알림 등)
reports/                # 생성 리포트 및 결과물
scripts/                # NAS·PC 운영 스크립트
tests/                  # 단위 및 통합 테스트
```

---

## 3. 데이터 처리 및 휴장일 정책
- **데이터는 순차 인입 후 캐시 저장.**
- **휴장일 처리 원칙:**
  - 개장일 자정 이후는 다음 거래일로 간주.
  - 휴장일에는 캐시 데이터를 그대로 재사용.
  - 추천 및 알림 생성은 “다음 거래일 기준” 데이터로 수행.
- **데이터 소스 우선순위:**
  1. 한국: `pykrx` → `naver 금융`
  2. 해외: `yfinance`

---

## 4. HOLD_CORE 구조
| 요소 | 설명 |
|------|------|
| 정의 위치 | `core/strategy/rules.py` (`core_holdings: List[str]`) |
| 추천 로직 | 매도 무시, 미보유 시 자동 매수, TOPN 제외 |
| 백테스트 | 동일 로직 반영 (`extensions/backtest/portfolio_runner.py`) |
| 상태 값 | `HOLD_CORE` (매도 금지, TOPN 제외, Slack 리포트 표시) |

---

## 5. NAS–PC 파이프라인
```mermaid
graph TD;
  A[데이터 인입 (NAS)] --> B[전략 스캐너]
  B --> C[TopN + HOLD_CORE 포함 알림]
  C --> D[백테스트 요청 생성]
  D --> E[PC 백테스트 수행]
  E --> F[리포트 저장 및 NAS 동기화]
```

---

## 6. 로깅 및 예외 처리
- **로그 수준**: DEBUG / INFO / WARNING / ERROR.
- **에러 보고**: `send_verbose_log_to_slack()` 자동 호출.
- **비정상 데이터 처리**:
  - 음수 가격, 결측, NaN → ERROR 로그 후 스킵.
  - 거래정지/폐지 종목은 제외하되, 로그에 기록.
  - 거래 데이터 부족 종목은 경고 후 제외.

---

## 7. 실행 환경 구분
| 환경 | 역할 | Python | 설치 명령 |
|------|------|---------|-------------|
| NAS | 인입·스캔·알림 | 3.8 | `uv pip install -e .` |
| PC | 백테스트·튜닝·룩백 | 3.11+ | `uv pip install -e "[backtest,tuning]"` |

---

## 8. 테스트 및 품질 관리
- **CI 매트릭스**: Python 3.8 / 3.11 모두 테스트.
- **테스트 분리**: `tests/core`(공통) / `tests/extensions`(Py3.11 전용).
- **회귀 검증**: 동일 dataset_id 결과 비교, 오차 허용치 ±0.1%.
- **코드 품질 도구**: `ruff`, `black`, `flake8`, `mypy`.

---

## 9. 향후 확장 계획
- GPU 백테스트 지원 (numba/jax)
- HOLD_CORE 시각화 리포트 자동 생성
- 거래소 캘린더 API 기반 휴장일 자동 감지

> v2에서는 병렬처리 금지, 휴장일 캐시 정책, HOLD_CORE 통합 로직, 에러 로깅 정책을 반영했다.

