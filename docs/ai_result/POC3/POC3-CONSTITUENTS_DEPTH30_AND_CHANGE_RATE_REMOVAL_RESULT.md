# POC3 — 구성종목 수집 깊이 30 + 등락률 열 제거 (개발 결과서)

- **성격**: **설계자 확정문에 따른 구현.** 앞선 UI 라운드에서 사용자가 발견한 2건
  (`상위 10건 제한` · `등락률 미연결`)에 대한 설계 판단이 내려와 그대로 구현했다.
- **작업일**: 2026-08-19 (맥북 환경)
- **상태**: **r1·r2 `REJECTED` → r3 재작업 완료 (재검증 대기).** 검증자 대상 —
  앞선 UI 라운드와 달리 `app/` 4개 파일을 변경했다. UI 전용이 아니므로 검증 예외가
  아니다. r1 지적 4건과 조치는 **§11**, r2 지적(보고 정확성)과 조치는 **§12**.
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
  (`analysis.overlap_top_k` — **r2 에서 `?? 10` fallback 제거**, §11.5)
- **등락률 열 · `등락률 unavailable` 안내문 제거.** 대체값 없음
- 조회 깊이 `10` → `30`. **r2 에서 수집 버튼 경로까지 일괄 적용**(§11.1)
- 중복률 화면 `ETF 쌍별 중복률 (Top 10 기준)` **문구 무변경**

---

## 4) 변경된 파일 목록

> **측정 방법 (r3 정정)**: 아래 수치는 **커밋된 결과에서** `git show --numstat <sha>` 로
> 뽑았다. r1·r2 는 커밋 **직전** `git diff --numstat` 값을 적었는데, 그 뒤에 문서를 더
> 고치면서 값이 어긋났다(`STATE_LATEST` 38/4 로 보고 → 실제 47/3). 커밋 전 측정값을
> 최종 수치로 쓰면 안 된다.

### 4.1 r1 — 커밋 `004517f8` (16개 파일)

`git show --numstat 004517f8` 실측:

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
| `docs/PROGRAM_TRUTH.md` | 수정 (최종 반영 항목 추가) | 2 | 1 |
| `docs/STATE_LATEST.md` | 수정 (오보고 정정 + 이번 라운드) | 47 | 3 |
| `docs/ai_result/POC3/(본 문서)` | **신규** | 271 | 0 |

> **A-2 정정 (검증자 r1 P1)**: 최초 이 표에서 **`docs/PROGRAM_TRUTH.md` 를 빠뜨렸다**
> (16개 파일인데 15개로 보고). **r3 추가 정정**: `STATE_LATEST` 수치도 `38/4` 로 틀렸다
> — 실제는 `47/3`.

### 4.2 r2 — 커밋 `dffac9ef` (6개 파일)

`git show --numstat dffac9ef` 실측:

| 파일 | 구분 | 추가 | 삭제 |
|---|---|---|---|
| `frontend/app/components/ConstituentsTab.test.tsx` | **신규** | 206 | 0 |
| `frontend/app/components/ConstituentsTab.tsx` | 수정 (수집 경로 깊이 · 비중 합계 계약) | 40 | 19 |
| `frontend/lib/api/etfExposure.ts` | 수정 (`CONSTITUENTS_TOP_K` 신설 · `overlap_top_k` optional 제거) | 8 | 2 |
| `frontend/app/components/ETFExposureView.tsx` | 수정 (상수 사용) | 2 | 1 |
| `docs/ai_result/POC3/(본 문서)` | 수정 (§11 재작업 기록) | 119 | 6 |
| `docs/STATE_LATEST.md` | 수정 (r2 반영) | 23 | 2 |

> **A-2 정정 (검증자 r2 P1)**: 최초 이 표는 **프론트 4개만** 적어 문서 2개
> (`STATE_LATEST` · 본 문서)를 빠뜨렸다. 커밋은 6개 파일이다.

### 4.3 r3 — 본 정정 라운드

변경 파일 3개 — `frontend/app/components/ConstituentsTab.test.tsx`(§12.4 판별 케이스
1건 추가) · `docs/ai_result/POC3/(본 문서)` · `docs/STATE_LATEST.md`.
**운영 코드 변경 0건.**

**수치를 적지 않는 이유**: 본 문서 자체가 변경 대상이라 **지금 수치를 쓰면 그 행위가
수치를 바꾸는 자기참조**가 된다. 커밋 후 `git show --stat <r3 sha>` 로 확인해야 한다.
(같은 이유로 결과서 본문에 현재 HEAD SHA 를 박지 않는다.)

**DB 스키마 변경 0건. 신규 endpoint 0건. 신규 의존성 0건.**

---

## 5) 회귀 테스트 — 백엔드 10건 (r2 프론트 6건은 §11.4)

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


---

## 11) r1 검증자 REJECTED — 지적 4건과 조치 (2026-08-19)

### 11.1 [P1] 수집 버튼이 여전히 10건만 요청 — **지적이 정확했다**

백엔드 깊이를 30 으로 올리고 **조회 한 곳(`ETFExposureView` 마운트 시점)만** 고쳤다.
정작 사용자가 누르는 **수집 버튼(POST)과 수집 직후 재조회(GET)** 에는 리터럴 `10` 이
그대로 남아 있었다. 백엔드는 *"10건 요청 + 10건 캐시"* 를 완료로 판단하므로
**실제 사용자 경로에서는 재수집도 30건 표시도 일어나지 않았다.** 안내문도 여전히
`상위 10개 구성종목을 수집` 이라고 적혀 있었다.

**원인**: 착수 시 `top_k` 가 프론트 어디에 흩어져 있는지 **grep 으로 열거하지 않았다.**
`CLAUDE.md §11` 의 *"안전 가드는 모든 layer 일괄 — 먼저 grep 으로 위반 가능한 모든
layer 를 열거"* 를 지키지 않은 것이다.

**조치**: 리터럴을 없애고 **단일 상수**로 모았다.

```ts
// frontend/lib/api/etfExposure.ts
export const CONSTITUENTS_TOP_K = 30;
```

| 경로 | 이전 | 이후 |
|---|---|---|
| 수집 `POST /market/constituents/refresh` | `top_k: 10` | `CONSTITUENTS_TOP_K` |
| 수집 직후 `GET .../analysis` | `10` | `CONSTITUENTS_TOP_K` |
| 마운트 시점 `GET .../analysis` | `30` (리터럴) | `CONSTITUENTS_TOP_K` |
| `fetchConstituentsAnalysis` 기본값 | `10` | `CONSTITUENTS_TOP_K` |
| 안내문 | `상위 10개 구성종목` | `상위 {CONSTITUENTS_TOP_K}개 구성종목` |

`grep -rn "top_k\|상위 10\|10개 구성종목" frontend/app frontend/lib` 로 전 경로를
열거한 뒤 일괄 적용했다. 남은 `10` 은 **중복률 기준(`overlap_top_k`)** 뿐이며 이는
설계 확정대로 고정값이다.

### 11.2 [P2] 누락 비중을 0 으로 합산 — **지적이 정확했다**

개별 표에서는 비중 누락을 `-` 로 표시하면서 요약 합계에서는 `weight_pct ?? 0` 으로
조용히 0 을 더했다. **값이 없는데 완성된 합계처럼 보인다.**

**조치**: 값이 있는 것만 더하고, **빠진 개수를 밝힌다.** 전부 없으면 `0.00%` 가 아니라
`확인 불가` 로 적는다.

```
상위 2개 표시 · 표시 비중 합계 34.19% (비중 미확인 1개 제외)
```

### 11.3 [P1] 변경 파일 목록 누락 — **지적이 정확했다**

`docs/PROGRAM_TRUTH.md` 를 빠뜨려 15개로 보고했으나 커밋은 16개였다. §4 에 추가하고
정정 문구를 남겼다.

### 11.4 [B-6] 프론트 수집 경로 테스트 부재 — **지적이 정확했다**

백엔드 회귀 10건은 전부 통과했지만 **함수만 검사**했다. 화면이 서버에 무엇을 보내는지
확인하는 테스트가 없어 §11.1 의 연결 누락을 잡지 못했다.

**조치**: `ConstituentsTab.test.tsx` **신규 6건**.

| 테스트 | 검사 |
|---|---|
| 수집 버튼 POST · 직후 GET | 둘 다 `top_k = 30` |
| 안내문 | 실제 수집 깊이와 같은 숫자 |
| 비중 일부 누락 | 값 있는 것만 합산 + **제외 개수 명시** |
| 비중 전부 누락 | `확인 불가` (0.00% 아님) |
| 등락률 | 열·안내문 없음 |
| 중복률 기준 | 응답 값 그대로 (임의값으로 안 메움) |

**역검증**: 검증자가 REJECT 한 커밋(`004517f8`)의 `ConstituentsTab.tsx` 로 되돌리면
**6건 중 4건이 실패**한다. 테스트가 실제 결함을 잡는다.

```
× 수집 버튼이 top_k=30 으로 POST 하고, 직후 조회도 30 으로 한다
× 안내문이 실제 수집 깊이와 같은 숫자를 말한다
× 비중이 없는 종목을 0 으로 합산하지 않고 제외 개수를 밝힌다
× 비중이 전부 없으면 0.00% 가 아니라 확인 불가 로 적는다
Tests  4 failed | 2 passed (6)
```

### 11.5 [B-1] `overlap_top_k ?? 10` fallback — **지적이 정확했다**

응답 필드를 optional 로 선언하고 `?? 10` 으로 누락을 메웠다. 백엔드 모델은 기본값을
가진 필수 필드이므로 **항상 온다.** 타입에서 optional 을 벗기고 fallback 을 제거했다.

### 11.6 [A-3] 문서와 코드 불일치

`STATE_LATEST` 의 *"수집 버튼을 누르면 30건으로 재수집된다"* 가 §11.1 수정으로
**사실이 됐다.** `PROGRAM_TRUTH` · 결과서의 "구성종목 탭 30건" 도 마찬가지다.

### 11.7 r2 검증 실측

| 항목 | 결과 |
|---|---|
| `npx tsc --noEmit` | 통과 |
| `npm run lint` | 0건 |
| `npx vitest run` | **173 passed (16 files)** — 직전 167 + 신규 6 |
| 백엔드 | **변경 없음** — r2 는 프론트 전용 (r1 의 1157 passed 유효) |


---

## 12) r2 검증자 REJECTED — 보고 정확성 2건 (2026-08-19)

기능 결함은 r2 에서 해소됐고(**A-1·A-3·B 전 항목 통과 · 위험 NONE · 폭주 NONE**),
남은 것은 **A-2 보고 정확성** 이다. 지적 2건 모두 타당했다.

### 12.1 [P1] r2 변경 파일 목록에서 문서 2개 누락

r2 커밋 `dffac9ef` 는 **6개 파일**인데 표에는 **프론트 4개만** 적었다.
`docs/STATE_LATEST.md` 와 **본 결과서 자체**가 빠졌다.

### 12.2 [P1] `STATE_LATEST` numstat 불일치

`38 추가 / 4 삭제` 로 적었으나 실제는 **`47 추가 / 3 삭제`** 다.

### 12.3 두 건의 공통 원인 — 측정 시점이 틀렸다

`git diff --numstat` 을 **커밋 직전에** 실행해 그 값을 표에 적었고, **그 뒤에도 문서를
계속 고쳤다.** 그래서 (a) 나중에 만진 문서가 목록에서 빠지고 (b) 미리 잰 수치가 최종
커밋과 어긋났다. *"실측"* 이라고 쓴 것이 측정 시점 때문에 사실이 아니게 됐다.

**조치**: 수치를 **커밋된 결과에서** `git show --numstat <sha>` 로 다시 뽑아 §4.1·§4.2 를
재작성하고, 측정 방법을 §4 머리에 명시했다. 본 라운드(§4.3)처럼 **결과서 자신이 변경
대상일 때는 수치를 적지 않는다** — 적는 행위가 수치를 바꾸는 자기참조이기 때문이다.

### 12.4 [B-6 참고] 중복률 테스트가 옛 fallback 을 구별하지 못한다

검증자 지적대로, 기존 `overlap_top_k` 테스트는 입력값이 **옛 fallback 과 같은 10** 이라
그 하나만으로는 `?? 10` 제거를 증명하지 못한다.

**조치**: 10 이 아닌 값으로 판별하는 케이스를 추가했다 — 응답이 `overlap_top_k: 7` 이면
화면도 `상위 7건 기준` 이라고 말하고 `10건` 문구는 없어야 한다.

**한계도 그대로 적는다**: 옛 코드(`?? 10`)도 값이 있으면 7 을 쓰므로, **이 테스트가 옛
구현에서 실패하지는 않는다.** 실질적 보증은 **타입에서 optional 을 벗겨 누락 자체를
불가능하게 만든 것**이고, 테스트는 *"응답 값을 그대로 쓴다"* 는 계약을 고정하는 역할이다.

### 12.5 r3 검증 실측

| 항목 | 결과 |
|---|---|
| 운영 코드 변경 | **0건** (테스트 1건 추가 + 문서 정정) |
| `npx tsc --noEmit` | 통과 |
| `npm run lint` | 0건 |
| `npx vitest run` | **174 passed (16 files)** — r2 173 + §12.4 신규 1 |
| 백엔드 | r2·r3 모두 백엔드 diff 0건 — r1 의 **1157 passed** 유효 |
