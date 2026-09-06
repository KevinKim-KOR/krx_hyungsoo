# POC3-OPS-01A 인계 — 보유 PUSH 선별·그룹화·반복 억제

- **작성**: 2026-09-05 · 개발자(VSCode Claude)
- **독자**: 다음 세션 개발자 · 설계자
- **상태**: **`CLOSED`** — 검증자 **`VERIFIED`**(r10) + 사용자 형식 확인(**조건부**) · **⚠️ OCI 미배포**

> 검증 라운드별 상세·AC 대조는 결과서에 있다. 여기에는 **다음 사람이 알아야 할
> 것만** 적는다.

---

## 1. 무엇을 했나

보유 브리핑이 보유 **전 종목**을 나열하던 것을 **선정된 종목만** 보내도록 바꿨다.
2026-06-30 기준 preview 로 **8,690자 → 621자(11종목)**.

선정 이유는 두 가지뿐이다 — `RECENT_DECLINE`(20거래일 하락) ·
`DATA_UNAVAILABLE_OR_STALE`. 이유가 없는 종목은 **아예 넣지 않는다.**

슬롯별로 OPEN(09:15)은 전체 현재 상태, MIDDAY·CLOSE는 **변화분만** 보낸다.
같은 종목·이유·구간이 반복되면 재발송하지 않는다.

---

## 2. 신규 진입점·계약

| 모듈 | 역할 |
|---|---|
| `app/runtime_evidence/holdings_selection.py` | 선정 판정 · 구간 · fingerprint. **순수 함수** |
| `app/runtime_evidence/holdings_selection_source.py` | 보유 원장·가격 이력·**거래일 축** 로드 |
| `app/runtime_evidence/holdings_selection_state.py` | 상태 저장 · 변화 판정 |
| `app/runtime_evidence/holdings_selection_render.py` | 본문 렌더 |
| `app/runtime_evidence/holdings_selection_flow.py` | 흐름 조립 · 비거래일 · privacy · `assemble_holdings_push` |
| `app/three_push_runtime/non_trading_day.py` | 비거래일 판정(**집합 일치**) |
| `scripts/build_holdings_selection_preview.py` | 미발송 preview 생성 |

**꼭 알아야 할 계약 3개**

1. **분모는 "거래일 축에서 실행일보다 앞선 20번째 거래일의 *그 날짜* 종가"** 다.
   없으면 `DATA_UNAVAILABLE_OR_STALE` — **더 오래된 종가로 대체하지 않는다.**
   달력일 임계(`MAX_PRICE_STALE_DAYS`)는 **폐기**됐다. 되살리지 말 것.
2. **완전성은 고유 ticker 집합 일치**다. `attempted`(보유 **행** 수, 32)를 분모로
   쓰면 고유 ticker 수(29)와 달라 가드가 죽는다. 실제로 그 결함이 있었다.
3. **모든 skip·fail 결정은 enable flag guard 뒤(§6-c)** 다. 조립(§3-c)에서 바로
   `return` 하면 push_kind 가 비활성인데도 데이터 실패가 `push_kind_disabled` 를
   가로챈다. 이 실수를 **세 번** 반복했다.

---

## 3. ⚠️ 남은 GAP

| # | 항목 | 내용 |
|---|---|---|
| 1 | ~~사용자 preview 확인~~ | **완료(조건부)** — *"받아보면서 결정하겠습니다"*. 운영 수신 후 형식 조정 가능 |
| 2 | **OCI 배포 — 미수행** | 저장소에만 반영. **배포 전까지 실제 발송 본문은 이전 형식.** OCI 는 `a0a0b192` 로 **69 커밋** 뒤. cron 진입점은 러너 1개지만 `app/`·`scripts/` **38파일**이 함께 간다. 쓰기 작업이라 개발자가 하지 않음 |
| 3 | ~~`DEF-PRICE-EQUITY-REFRESH`~~ | **철회 — 개발자 오등재(2026-09-06).** OCI 는 정상(개별주 종가 2026-09-03, 배치 41/41). **로컬 개발 DB만 ETF 유니버스를 갱신**해 개별주가 정체된 것이다. 로컬에서 보유 개별주 분석 시 주의 |
| 4 | KS-10 | 러너 644줄 — 임계 650까지 **6줄**. 다음에 러너를 건드리면 먼저 줄일 것 |

---

## 4. 이번에 얻은 교훈

- **역검증 스크립트는 강제 종료·바이트코드 캐시에 취약하다.** 2분 타임아웃으로
  사보타주 적용 직후 죽어 소스에 남았고, 이어진 실행 전체가 오염됐다. 또 **같은
  크기** 사보타주를 같은 초에 복원하면 Python 이 `(mtime, size)` 기준으로 stale
  `.pyc` 를 계속 써서 "복원했는데 동작은 사보타주" 가 된다. 스크립트에 `atexit` +
  시그널 핸들러 + `__pycache__` 삭제 + `PYTHONDONTWRITEBYTECODE=1` 을 넣었다.
- **역검증 사보타주가 "실질적 무력화" 인지 먼저 확인해야 한다.** 기본값만 바꾸거나
  `sorted`→`list` 처럼 결과가 같은 조작은 미탐지로 나와 헛돈다.
- **결과서 수치는 손으로 적지 말고 실측에서 생성한다.** 줄 수·건수·회귀 수치가
  라운드마다 stale 이 됐다. 지금은 `wc -l`·`--co`·회귀 로그와 자동 대조한다
  (검사기 16종, 스크립트는 세션 scratchpad — 필요하면 결과서 §9.10·§9.13 참조).
- **라운드 기록을 문서에 덧붙이면 "최신 라운드" 가 바뀌어 새 자기참조 모순이
  생긴다.** r7~r10 이 그것만 오갔다. 검증자가 판정 기준을 조정해 끝냈다 —
  경미한 이력 표기는 비차단, 문서만 바뀌면 전체 코드 검증 반복 안 함.

---

## 5. 다음 게이트

1. ~~사용자 preview 형식 확인~~ → **완료. 결과서·STATE `CLOSED`**
2. OCI 배포 → `PROGRAM_TRUTH` 프로세스 **C-1** 의 "미배포" 표시 제거
3. ~~`DEF-PRICE-EQUITY-REFRESH` 처리~~ → **불필요** (철회)
