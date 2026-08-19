# POC3 — 구성종목 수집 깊이 30 + 등락률 열 제거 (개발 결과서)

- **성격**: **설계자 확정문에 따른 구현.** 앞선 UI 라운드에서 사용자가 발견한 2건
  (`상위 10건 제한` · `등락률 미연결`)에 대한 설계 판단이 내려와 그대로 구현했다.
- **작업일**: 2026-08-19 (맥북 환경)
- **상태**: 구현 완료 · **검증자 대상** — 앞선 UI 라운드와 달리 **`app/` 4개 파일을
  변경**했다. UI 전용이 아니므로 검증 예외에 해당하지 않는다.
- **입력 문서**: `docs/handoff/POC3/POC3_CONSTITUENTS_TOPK_AND_CHANGE_RATE_QUESTION.md`
  (개발자 질의 + 설계 확정문 + 구현 결과 §5)
- **선행**: `POC3-OVERLAP_TAB_CARD_CONVERSION_RESULT.md`

---

## 1) 처리한 요구사항

확정문 원문:

> 구성종목은 같은 source·endpoint·스키마를 유지하면서 ETF당 최대 30건까지 한 번
> 수집한다. 구성종목 탭은 최대 30건을 표시하되, 기존 중복률은 rank 1~10만 사용하여
> `Top 10 기준` 계약을 유지한다. ETF 1회 처리 상한 10개·시간 예산·캐시 정책은 유지한다.
> 등락률은 신규 수집하지 않고 정상 화면의 컬럼과 unavailable 안내를 제거한다.
> 개별주 등락률 수집은 BACKLOG로 둔다.

| 확정 항목 | 결과 |
|---|---|
| ETF당 최대 30건 **한 번** 수집·저장 | **DONE** — `DEFAULT_TOP_K`·`MAX_TOP_K` = 30 |
| 구성종목 탭은 저장된 최대 30건 표시 | **DONE** — 조회 깊이 30 |
| 중복률은 계속 상위 10건만 사용 | **DONE** — 표시 깊이와 분리, 항상 10 고정 |
| 중복률 화면 `Top 10 기준` 문구 유지 | **DONE** — 문구 무변경 |
| `MAX_TICKERS_PER_REQUEST = 10` 유지 | **DONE** |
| 지연시간·30초 예산·캐시 우선 유지 | **DONE** |
| 신규 source·endpoint·DB 스키마 추가 금지 | **DONE** — 0건 |
| 화면 진입 시 외부 조회 금지 | **DONE** — 기존과 동일(수집은 명시 클릭) |
| 제목 `상위 구성종목` | **DONE** |
| 요약 `상위 N개 표시 · 표시 비중 합계 XX.XX%` | **DONE** |
| 30건 미만이면 실제 확보 건수만 표시 | **DONE** — `top_holdings.length` 그대로 |
| `전체 구성종목` 표현 금지 | **DONE** — 해당 문구 없음 |
| 값 없는 종목을 채우거나 추정하지 않음 | **DONE** — 기존 정책 유지 |
| 기존 Top 10 캐시를 Top 30 완료로 간주 금지 | **DONE** — §3.2 |
| 깊은 30건을 이후 10건으로 축소 덮어쓰기 금지 | **DONE** — §3.3 |
| 등락률 열 제거 | **DONE** |
| `등락률 unavailable` 안내문 제거 | **DONE** |
| `0%`·ETF 자체 등락률·추정값 대체 금지 | **DONE** — 대체 없음 |
| API·DB 에 빈 등락률 필드 추가 금지 | **DONE** — 추가 0건 |
| 개별주 등락률 BACKLOG 이관 | **DONE** — §5 |

---

## 2) 착수 전 확인 — 확정문의 중단 조건

확정문: *"개발자가 확인했을 때 30건 확보를 위해 구성종목별 추가 호출이 필요하다면
구현을 중단하고 다시 보고해야 합니다."*

**착수 전에는 확인 불가능한 상태였다.** 코드의 요청은 `pageSize=20` 고정이었고
(받은 뒤 10건으로 자름), source 가 `pageSize=30` 을 존중하는지는 응답을 받아봐야
알 수 있었다. **사용자 허락을 받고 진단 호출 1회**를 실행했다.

```
GET https://stock.naver.com/api/domestic/detail/069500/ETFComponent?startIdx=0&pageSize=30
HTTP 200 · 반환 건수 30 · referenceDate 2026-08-19 · componentCount 200
```

→ **중단 조건 해당 없음.** ETF당 호출 1회로 30건이 온다. 페이지네이션 불필요.

> `componentCount = 200` 은 해당 ETF 의 전체 구성종목 수다. 표시에 쓰면 유용하나
> **저장하면 스키마 추가**라 담지 않았다(확정문 금지 항목).

### 2.1 ⚠ 보고 정확성 위반 — 설계 판단 근거에 잘못된 사실이 들어갔다

질의 문서에 *"캐시에 ETF당 30건 저장된 과거분이 있다(`2026-06-22` 수집분 6개).
지금 재수집하면 10건으로 덮인다"* 라고 적었고, **확정문도 이를 근거의 하나로 인용**했다
(*"과거 30건 수집 이력이 있고 …"*). **사실이 아니다.**

```
최대 rank(전체): 10
스냅샷(ETF+asof) 그룹별 행수 분포: [(10, 50)]   ← 50개 스냅샷 전부 10행

0167A0:  2026-06-17 → 10행 / 2026-06-19 → 10행 / 2026-06-22 → 10행
```

`group by etf_ticker` 로만 세어 **서로 다른 날짜 3개를 한 스냅샷으로 착각**했다.
ETF당 30건이 저장된 적은 없고, 따라서 "덮인다" 는 걱정도 근거가 없었다.

**결론에는 영향이 없다** — 실측으로 *한 번의 호출로 30건이 온다* 는 것이 확인돼
확정문이 그대로 성립한다. 그러나 **틀린 사실이 설계 판단 입력으로 쓰였다는 점은
그 자체로 위반**이며, 질의 문서·앞선 결과서·STATE 세 곳에 정정을 남겼다.

---

## 3) 구현

### 3.1 깊이 30 — 호출 수는 그대로

`app/etf_constituents_service.py`

```python
MAX_TICKERS_PER_REQUEST = 10   # 외부 호출 수 상한 — 그대로
DEFAULT_TOP_K = 30             # ETF 안에서 담는 깊이 — 넓힘
MAX_TOP_K = 30
LEGACY_TOP_K = 10              # 구 정책 잔재 판별용 (§3.2)
PER_TICKER_DELAY_SECONDS = 0.5 # 그대로
TIME_BUDGET_SECONDS = 30.0     # 그대로
```

`app/etf_constituents_fetcher.py` — 같은 endpoint 를 **한 번** 부르되 `pageSize` 를
요청 깊이에 맞춘다. 이 값이 20 에 고정돼 있으면 30 을 요청해도 20 까지만 온다.

```python
page_size = max(NAVER_DEFAULT_PAGE_SIZE, max(1, top_k))
```

응답이 `top_k` 보다 적으면 그게 그 ETF 의 전부다 — **추가 페이지를 부르지 않는다.**

### 3.2 캐시 규칙 — "Top 10 캐시를 Top 30 완료로 간주 금지"

**정확히 10건인 스냅샷만** 구 정책의 잘린 결과로 보고 재수집한다.

```python
stale_depth = (
    existing is not None
    and len(existing) < capped_top_k
    and len(existing) == LEGACY_TOP_K
)
if existing and not stale_depth:
    ...  # 캐시 사용
```

**단순히 `len(existing) < top_k` 로 하지 않은 이유**: 구성종목이 30개 미만인 ETF 는
아무리 다시 불러도 30건이 안 되므로 **매 수집마다 재조회**되어 *"캐시 우선 정책 유지"*
가 깨진다. 12건 저장돼 있으면 그건 *source 가 그만큼뿐* 이라는 뜻이다.

### 3.3 축소 덮어쓰기 방지

별도 코드가 필요 없었다. `upsert_constituents` 가
`(etf_ticker, asof, source, rank)` 단위 `INSERT ... ON CONFLICT DO UPDATE` 라
**삭제를 하지 않는다.** 30건 위에 10건을 써도 rank 11~30 이 남는다.
**의존하고 있는 성질이므로 회귀 테스트로 고정**했다.

### 3.4 표시 깊이 ≠ 중복률 깊이

`app/etf_constituents_analysis.py` 의 `compute_analysis(top_k=...)` 는 이전에
`top_holdings` 표시 · 쌍 중복률 · 반복 등장 집계 **세 곳에 같은 값**을 썼다.
표시 깊이만 30 으로 올리면 중복률까지 30 기준이 되어
**`Top 10 기준` 문구와 `common_count_top10` 필드명이 거짓이 된다.**

```python
pair = compute_pair_overlap(left_rows, right_rows, top_k=DEFAULT_TOP_K_FOR_OVERLAP)
repeated = compute_repeated_core_holdings(per_ticker_rows, top_k=DEFAULT_TOP_K_FOR_OVERLAP)
```

응답에 **`overlap_top_k`** 를 추가해 소비자가 두 기준을 구분할 수 있게 했다.

### 3.5 프론트

- 제목 `구성종목 펼쳐보기 (상위 10) + 집중도` → **`상위 구성종목`**
- 표 아래 요약 **`상위 N개 표시 · 표시 비중 합계 XX.XX%`**
  (`N` 은 실제 확보 건수 — 30 미만이면 그 값)
- 상단 안내에 *"중복률은 이 표시 깊이와 무관하게 상위 N건 기준"* 명시
  (`analysis.overlap_top_k ?? 10`)
- **등락률 열 · `등락률 unavailable` 안내문 제거.** 대체값 없음
- 조회 깊이 `10` → `30`
- 중복률 화면 `ETF 쌍별 중복률 (Top 10 기준)` **문구 무변경**

---

## 4) 변경된 파일 목록

`git diff --numstat` 실측:

| 파일 | 구분 | 추가 | 삭제 |
|---|---|---|---|
| `app/etf_constituents_service.py` | 수정 (깊이 30 · 캐시 규칙) | 18 | 3 |
| `app/etf_constituents_analysis.py` | 수정 (깊이 분리 · `overlap_top_k`) | 16 | 2 |
| `app/etf_constituents_fetcher.py` | 수정 (`pageSize` 추종) | 5 | 1 |
| `app/api_etf_constituents.py` | 수정 (`overlap_top_k` 응답 필드) | 4 | 0 |
| `tests/test_etf_constituents_service.py` | 수정 (회귀 5건) | 117 | 0 |
| `tests/test_etf_constituents_analysis.py` | 수정 (회귀 2건) | 63 | 0 |
| `tests/test_etf_constituents_naver_fetcher.py` | 수정 (회귀 3건) | 53 | 0 |
| `frontend/app/components/ConstituentsTab.tsx` | 수정 (표시 계약 · 등락률 제거) | 21 | 18 |
| `frontend/app/components/ETFExposureView.tsx` | 수정 (조회 깊이 30) | 3 | 1 |
| `frontend/lib/api/etfExposure.ts` | 수정 (`overlap_top_k` 타입) | 3 | 0 |
| `docs/backlog/BACKLOG.md` | 수정 (기존 항목 갱신) | 5 | 4 |
| `docs/handoff/POC3/..._QUESTION.md` | 수정 (확정문 + 구현 결과 §5) | 72 | 0 |
| `docs/ai_result/POC3/POC3-OVERLAP_TAB_..._RESULT.md` | 수정 (오보고 정정) | 6 | 2 |
| `docs/STATE_LATEST.md` | 수정 (오보고 정정 + 이번 라운드) | — | — |
| `docs/ai_result/POC3/(본 문서)` | **신규** | — | — |

**DB 스키마 변경 0건. 신규 endpoint 0건. 신규 의존성 0건.**

---

## 5) 회귀 테스트 10건

| 테스트 | 검사 |
|---|---|
| `test_default_top_k_is_30_and_cap_allows_30` | 깊이 30 · **호출 수 상한은 10 그대로** |
| `test_legacy_10_row_cache_is_refetched_at_depth_30` | 10건 캐시를 완료로 보지 않음 |
| `test_deep_cache_is_not_refetched` | 깊이 충족 캐시는 외부 호출 없음(`boom` fetcher) |
| `test_exhausted_source_cache_is_not_refetched` | 12건(고갈)은 재수집 안 함 |
| `test_deep_snapshot_not_shrunk_by_shallow_refetch` | 30건 위 10건 수집 후에도 **30행 유지** |
| `test_naver_fetcher_page_size_follows_top_k` | `pageSize=30` · **호출 1회** |
| `test_naver_fetcher_small_top_k_keeps_default_page_size` | 기본 pageSize 아래로 안 내려감 |
| `test_naver_fetcher_no_pagination_when_source_returns_fewer` | 적게 오면 추가 호출 없음 |
| `test_display_depth_does_not_change_overlap_basis` | **11~20위에서만 겹치는 데이터** → 중복률 0 |
| `test_overlap_still_detected_within_top10` | 상위 10 안에서 겹치면 잡힘(역검증) |

**작성 중 잡은 자체 오류 2건**:
- 처음에 양쪽 ETF 구성종목에 **rank 기반 같은 티커**를 넣어 겹침이 항상 잡혔다.
  겹침은 티커로 판정되므로 이름에서 파생시키도록 고쳤다.
- 그 파생에 `hash()` 를 썼다가 **실행마다 값이 바뀌는** 것을 발견해 결정적 값으로
  교체하고 3회 반복 통과를 확인했다.

---

## 6) 지시문 외 변경

없음.

---

## 7) 알려진 한계 / 미완성

### 7.1 구성종목이 정확히 10개인 ETF 는 매 수집마다 재조회된다

§3.2 의 판별이 *"정확히 10건이면 구 정책 잔재"* 이므로, **실제로 구성종목이 10개뿐인
ETF** 는 캐시가 있어도 매번 다시 불린다. 드물고 호출 수 상한·시간 예산 안에 있으나,
`len(existing) < top_k` 전면 적용(30 미만 ETF 전부 매번 재조회)과의 트레이드오프로
전자를 택한 결과다.

### 7.2 이미 저장된 10건 스냅샷은 자동으로 깊어지지 않는다

확정문대로 **사용자가 다음 수집을 실행할 때** 30건으로 갱신된다. 배포 시점에
자동 재수집을 돌리지 않는다(외부 호출을 임의로 발생시키지 않는다).

### 7.3 `componentCount`(전체 구성종목 수)를 쓰지 않는다

응답에 있으나 **저장하려면 스키마 추가**라 담지 않았다. 화면은 "전체 중 몇 개" 가
아니라 "상위 N개 표시" 로만 말한다.

---

## 8) 다음 검증자(Codex)에게 알릴 점

- **§2.1 을 먼저 봐주기 바란다.** 설계 판단 입력에 잘못된 사실을 넣었다. 결론은
  실측으로 독립 확인됐으나, 보고 정확성 위반이다.
- **§3.2 의 캐시 판별 규칙**이 이번 구현에서 가장 판단이 갈린 지점이다. 확정문의
  *"기존 Top 10 캐시를 완료로 간주하지 않음"* 과 *"캐시 우선 정책 유지"* 가 동시에
  성립하는 구현을 찾은 결과이며, §7.1 의 예외가 남는다.
- **§3.3 은 기존 `upsert` 의 성질에 의존**한다. 코드를 새로 넣지 않았으므로 회귀
  테스트가 유일한 보호막이다.
- 진단 목적 **외부 호출 1회**(§2)를 실행했다. 사용자 사전 허락을 받았고 저장하지 않았다.

---

## 9) 사용자 확인이 필요한 항목

- **실화면 확인 전 구성종목 재수집이 필요하다.** 현재 캐시는 10건 스냅샷이라 화면에
  30건이 나오지 않는다. 수집 버튼을 누르면 §3.2 규칙으로 재수집돼 30건이 채워진다.

---

## 10) 검증 실측

| 항목 | 결과 |
|---|---|
| `black --check app tests` | `246 files would be left unchanged.` |
| `flake8 app tests` | 0건 |
| 백엔드 `pytest tests/` | **1157 passed** (직전 1147 + 신규 10) |
| `npx tsc --noEmit` | 통과 |
| `npm run lint` | 0건 |
| `npx vitest run` | **167 passed (15 files)** |
