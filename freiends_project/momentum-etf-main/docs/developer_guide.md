# 개발자 가이드 (Developer Guide)

이 문서는 Momentum ETF 순위 시스템의 아키텍처, 데이터 흐름, 그리고 개발 시 반드시 지켜야 할 정합성 원칙을 설명합니다.

## 1. 시스템 아키텍처

### 모듈 구조
*   `core/strategy/`: 지표/점수/비중 계산 공용 전략 유틸
*   `services/`: **외부 API/데이터 연동 통합 계층**
    *   `price_service.py`: 실시간 가격/환율 오케스트레이션 및 TTL 캐시
    *   `reference_data_service.py`: KIS ETF 마스터, 종목 메타데이터, 상장일 조회
    *   `etf_holdings_service.py`: 한국 ETF 구성종목 비중을 네이버 `ETFComponent` API로 조회해 메타 캐시에 저장할 형태로 정규화합니다. 국내 구성종목은 6자리 종목코드, 해외 구성종목은 `componentReutersCode`에서 추출한 심볼을 표시용 `ticker`로 사용하고, 원본 ISIN은 `raw_code`에 저장합니다. 해외 구성종목 가격 조회는 응답 시점에 Yahoo를 사용하고 서비스 메모리 TTL 캐시를 적용합니다.
    *   `vkospi_service.py`: VKOSPI 등 외부 시장 지표 연동 및 메모리 캐시
    *   `fear_greed_service.py`: CNN 공포탐욕지수 연동 및 메모리 캐시
    *   **원칙**: 새로운 시장 지표, 가격 정보, 외부 데이터 크롤링 등은 혼동을 막기 위해 모두 이 폴더에서 각각의 서비스로 관리하고, 자체 캐시 시스템(TTL 등)을 구축합니다.
*   `utils/rankings.py`: 순위 테이블 계산 전용 유틸
*   `scripts/`: 데이터 수집, 캐시 갱신 등 유틸리티 스크립트
*   `utils/`:
    *   `cache_utils.py`: **Parquet 기반 캐시 I/O** 및 직렬화 관리
    *   `data_loader.py`: OHLCV 수집/보완 및 원천 fetch 함수
    *   `ai_summary.py`: AI용 요약 데이터 생성 공용 유틸
*   `.github/workflows/`: GitHub Actions를 이용한 일일 배포 및 자동화 정의

### 데이터 파이프라인 및 캐싱
1.  **데이터 수집**: `pykrx`, `yfinance` 등을 통해 원천 데이터 수집.
2.  **Parquet 캐싱**: 수집된 데이터는 `utils/cache_utils.py`를 통해 **Apache Parquet** 포맷으로 MongoDB에 저장됩니다. (기존 Pickle 방식의 버전 충돌 문제를 해결)
3.  **서비스 오케스트레이션**:
    *   `services/price_service.py`가 실시간 가격/환율과 TTL 캐시를 관리합니다.
    *   `services/reference_data_service.py`가 KIS ETF 목록과 메타데이터 조회를 관리합니다.
    *   `services/etf_holdings_service.py`가 한국 ETF 구성종목 비중을 네이버 `ETFComponent` API로 수집하고, 응답 시점에는 메타 캐시에 저장된 구성종목에 해외 가격만 Yahoo TTL 캐시로 보조합니다.
4.  **지표 계산**: `core/strategy/metrics.py`가 이동평균과 점수를 계산.
5.  **순위 생성**: `utils/rankings.py`가 종목별 점수, 규칙별 추세, RSI, 기간 수익률을 합쳐 화면용 DataFrame 생성.

### 종목 캐시 용어

이 프로젝트에서 **종목 캐시**는 다음 두 가지를 합친 상위 개념으로 사용합니다.

1.  **가격 캐시**
    *   OHLCV, 종가 시계열, 실시간 스냅샷
    *   `utils/cache_utils.py`, `utils/data_loader.py`, `services/price_service.py`
2.  **메타 캐시**
    *   상장일, 배당률, 보수, 순자산총액, ETF 구성종목 같은 저빈도 정보
    *   Mongo `stock_cache_meta` 컬렉션
    *   `utils/stock_cache_meta_io.py`, `services/stock_cache_service.py`
    *   한국 ETF 저빈도 메타와 구성종목은 `scripts/stock_meta_cache_updater.py`가 네이버 `ETFBase`, `ETFDividend`, `ETFComponent`를 조회해 `stock_cache_meta.meta_cache`, `stock_cache_meta.holdings_cache`로 저장합니다.

`stock_meta` 컬렉션은 종목 관리 원본(버킷, 종목명 등)으로 유지하고, 저빈도 메타 캐시는 `stock_cache_meta`로 분리하는 것을 기본 방향으로 삼습니다. 종목 삭제는 별도 휴지통 없이 즉시 하드 딜리트를 기본으로 합니다.

국가별 거래일 캘린더는 DB가 아니라 파일 캐시로 관리합니다. 런타임은 `zcountry/{country}/market_calendars.json`만 읽고, 파일이 없거나 범위를 벗어나면 즉시 에러를 발생시킵니다.

### 서비스 사용 원칙

1.  실시간 가격/환율 조회는 `services/price_service.py`를 먼저 사용합니다.
2.  KIS ETF 마스터, 종목 메타데이터, 상장일 조회는 `services/reference_data_service.py`를 먼저 사용합니다.
3.  **외부 연동 일원화**: 시장 지표나 새로운 데이터를 외부에서 파싱/API 통신해야 한다면 `services/` 하위에 위치시키며, 무분별한 요청을 방지하기 위한 캐싱 로직을 포함해야 합니다.
4.  화면 계층과 일반 유틸은 외부 데이터 소스를 직접 호출하지 않고, 가능하면 `services/` 계층을 통해 접근합니다.
5.  `utils/data_loader.py`는 원천 fetch 함수와 OHLCV 보완 로직을 포함하지만, 신규 호출부를 작성할 때는 직접 진입점으로 우선 사용하지 않습니다.
6.  실시간 가격데이터를 제외한 값은 우선 `종목 캐시`에 저장하고 읽습니다. 화면 진입 시 외부 원천을 다시 호출하지 않고, 캐시된 메타/구성종목을 한꺼번에 읽어 응답 속도를 유지하는 것을 기본 원칙으로 삼습니다.
7.  한국 ETF 구성종목 비중은 `stock_cache_meta.holdings_cache`를 우선 사용합니다. `/ticker`는 구성종목 목록/비중을 실시간 조회하지 않습니다.
8.  배당률, 보수, 순자산총액, 상장일 같은 저빈도 ETF 메타는 `stock_cache_meta.meta_cache`를 우선 사용합니다.
9.  앞으로 새로운 저빈도 항목(예: ETF 메타, 구성종목 속성, 기초지수 관련 부가정보)을 발견하면, 실시간 가격데이터가 아닌 이상 먼저 `stock_cache_meta`에 저장하는 방향을 기본값으로 삼습니다.

## 2. 순위 화면 정합성 원칙

> **Critical**: 이 시스템은 **순위 화면이 단일 진실 원천(single source of truth)** 입니다. 화면에서 보이는 값은 계좌 종목 목록, 가격 캐시, 실제 보유 데이터로 직접 계산되어야 합니다.

### 핵심 구조
| 파일/경로 | 역할 |
|-----------------|------|
| `web/app/*` | Next.js 기반 사용자 화면과 API 라우트 |
| `utils/rankings.py` | 순위 계산과 정렬 |
| `core/strategy/metrics.py` | 이동평균 점수 계산 |
| `services/price_service.py` | 실시간 가격/환율 조회의 공식 진입점 |
| `services/reference_data_service.py` | ETF 마스터/메타데이터/상장일 조회의 공식 진입점 |
| `utils/account_notes.py` | 계좌 메모 저장/조회 |

### 핵심 일관성 체크리스트

1.  **입력 단순화**: 종목풀 설정의 `MA_RULES`를 기본값으로 사용하되, 순위 화면에서는 `추세1`, `추세2`를 각각 변경할 수 있다.
2.  **정렬 기준 고정**: `점수`가 있는 종목을 `점수` 내림차순으로 정렬하고, 계산 불가 종목은 맨 아래로 보낸다.
3.  **데이터 기준**:
    *   모든 의사결정은 **판단 시점의 전일 종가 데이터**를 기준으로 함
    *   "오늘"의 순위는 "어제까지의 마감 데이터"를 보고 계산된 것임
    *   최신 거래일 판단의 기준 날짜는 모든 시장 공통으로 **한국 날짜**를 사용함
4.  **엄격한 설정 원칙 (Rule 7)**:
    *   코드에 암묵적인 기본값(fallback)을 사용하지 않습니다.
    *   필수 순위 파라미터가 누락된 경우 명확한 `ValueError`를 발생시킵니다.

## 3. 전략 설정 규칙

종목풀 설정 포맷(`ztickers/<order>_<ticker_type>/config.json`):

```json
{
  "icon": "🇰🇷",
  "name": "국내상장 국내",
  "country_code": "kor",
  "currency": "KRW",
  "MA_RULES": [
    { "order": 1, "MA_TYPE": "SMA", "MA_MONTHS": 10 },
    { "order": 2, "MA_TYPE": "ALMA", "MA_MONTHS": 3 }
  ]
}
```

종목풀 설정의 `country_code`는 현재 `kor`, `au`, `us`를 허용합니다.

검증 원칙(현재 운영):

* 종목풀: `MA_RULES` 필수
* 필수값 누락 시 fallback 없이 명시적 에러

## 4. 테스트 및 검증

코드를 수정할 때는 다음 절차를 따르세요.

1.  **로직 수정**: `utils/rankings.py`, `core/strategy/metrics.py`, `web/app/*`, `web/lib/*`를 우선 확인
    *   가격/환율 문제면 `services/price_service.py`를 함께 확인
    *   KIS ETF 목록/메타데이터/상장일 문제면 `services/reference_data_service.py`를 함께 확인
2.  **검증**:
    *   순위 화면에서 종목풀 변경 또는 `추세1`, `추세2` 변경 시 컬럼과 점수가 즉시 갱신되는지 확인
    *   실제 보유 종목이 녹색 행으로 표시되는지 확인
3.  **확인**:
    *   `점수`, 규칙별 `추세(...)` 컬럼이 `현재가` 뒤에 표시되는지 확인

## 5. 순위 화면의 정의

**"순위(Rank)"**는 종목풀의 현재 종목 유니버스에서 `MA_RULES` 기준 점수를 계산한 결과입니다.

### 핵심 원칙
1.  **화면 기준 계산**: 순위는 별도 저장 결과를 읽지 않고, 가격 캐시와 계좌 종목으로 즉시 계산합니다.
2.  **실보유 구분**: 실제 보유 종목만 행 색상으로 표시합니다.
3.  **정렬 규칙**: `점수` 내림차순, `점수` 계산 불가 종목은 맨 아래입니다.
4.  **계좌 종목 직접 관리**: 계좌가 자신의 종목 유니버스를 직접 보유하며, 별도 종목풀 fallback은 사용하지 않습니다.

## 6. 화면 UI 표준

AG Grid 기반 주요 화면은 현재 `/stocks`에서 정리한 레이아웃을 공통 기준으로 사용합니다.

### 공통 레이아웃 순서
1.  **메뉴 헤더**
    *   왼쪽: 메뉴명
    *   오른쪽: 총 개수, 선택 개수, 활성 주차 같은 정보
2.  **메인 헤더**
    *   왼쪽: 계좌 셀렉터, 보기 전환 토글, 검색/필터 같은 주 제어
    *   오른쪽: CRUD가 아닌 특별한 버튼, 예를 들어서 금액 가리기
3.  **보조 액션 헤더**
    *   버튼이 있을 때만 사용
    *   버튼은 항상 오른쪽 정렬
    *   `추가`, `저장`, `삭제` 같은 CRUD 액션만 둔다
4.  **테이블**
    *   카드 내부 스크롤을 사용

### 공통 스타일 규칙

1.  헤더 높이, 버튼 높이, 입력창 높이는 `web/app/globals.css`의 공통 클래스 기준으로 맞춘다.
2.  새 화면을 만들 때 개별 인라인 스타일보다 공통 클래스(`appMainHeader`, `appActionHeader`, `appHeaderMetrics`, `appSegmentedToggle`)를 우선 사용한다.
3.  토글 버튼은 글자 길이에 맞는 폭을 사용하고, 불필요한 고정 최소폭을 두지 않는다.
4.  컬럼 헤더 텍스트는 가운데 정렬, 데이터 셀은 텍스트 왼쪽 정렬 / 숫자 오른쪽 정렬을 유지한다.
5.  수정 가능한 셀 강조, 수정된 셀 강조, 선택/삭제 버튼 배치는 화면마다 임의로 다르게 만들지 않는다.
6.  종목 관리 삭제는 즉시 하드 딜리트로 처리하고, 삭제 사유/삭제일자/휴지통 개념을 새로 만들지 않는다.

### 화면별 예외 원칙

1.  `/market`처럼 검색 입력이 여러 개인 화면은 메인 헤더 한 줄을 유지하는 전용 예외 클래스를 둘 수 있다.
2.  예외를 추가하더라도 메인 헤더, 보조 액션 헤더, 테이블의 3단 구조 자체는 최대한 유지한다.
3.  새 예외 스타일을 만들면 먼저 공통 클래스 확장으로 해결 가능한지 검토하고, 불가할 때만 화면 전용 클래스를 추가한다.
