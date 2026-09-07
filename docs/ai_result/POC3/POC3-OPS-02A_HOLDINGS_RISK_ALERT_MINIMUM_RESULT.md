# POC3-OPS-02A — 보유 위험 즉시 알림 최소 기능 · 개발 결과서

- **입력 문서**: `docs/ai_plan/POC3/POC3-OPS-02A_HOLDINGS_RISK_ALERT_MINIMUM_PLAN_V1.md` (V1.4)
- **작성일**: 2026-09-07
- **라운드**: r3 (r1 `REJECTED` · r2 `VERIFIED_WITH_NOTES` + **사용자 문구 확정** 반영)
- **독자**: 검증자(Codex)
- **범위 밖(수행하지 않음)**: 실제 Telegram 발송 · OCI 배포 · flag 활성화 · cron 파일 편집

## 0) 현재 상태

| 항목 | 값 |
|---|---|
| `implementation` | `DONE` |
| `verification` | `VERIFIED_WITH_NOTES` |
| `verification_notes` | `RESOLVED` |
| `user_mock_check` | `APPROVED` |
| `deployment` | `NOT_DEPLOYED` |
| `autosend` | `DISABLED` |
| `step_status` | `IMPLEMENTED_NOT_OPERATIONAL` |

검증자 판정은 `VERIFIED_WITH_NOTES` 다. **`VERIFIED` 로 승격하지 않는다** —
지적된 메모 2건은 해소했지만(`verification_notes = RESOLVED`) 판정 자체는
검증자 권한이다.

---

> ⚠️ **본 문서에 현재 HEAD SHA 를 적지 않는다.** 커밋과 동시에 바뀌는 자기참조가
> 되기 때문이다. 최신 HEAD 는 `git log -1` 로 실측할 것.

---

## 1) 처리한 요구사항

PLAN §7.1 "한다" 항목 기준.

| # | 요구사항 | 상태 | 근거 |
|---|---|---|---|
| 1 | `DAY_DROP` **한 종류만 trigger** | DONE | `app/runtime_evidence/holdings_risk.py` — `select_risk_holdings` 의 유일한 판정식. 다른 trigger 없음 |
| 2 | 보조 정보 **본문 표시** | DONE | 현행 설계(PLAN V1.3 §4.2-b) 기준 **2종**(고점 대비 · 매입 대비). 시가 대비는 정식 제외됐으므로 미구현이 아니다 |
| 3 | 동시 발생 **한 메시지로 묶음** · 구간별 그룹 · 헤더 | DONE | `holdings_risk_render.render_risk_alert` — Top N 제한 없음 |
| 4 | 상태 변화 계약(§4.3) — `worst_state` 기반 | DONE | `holdings_risk_state.py` — `compute_risk_changes` · `merge_worst` |
| 5 | 신규 종류 `holdings_risk_alert` + 신규 flag(`false`) | DONE | `VALID_PUSH_KINDS` · `PUSH_KIND_FLAG_ENVS` · `ALLOWED_PUSH_KINDS` |
| 6 | mock/replay · **흐름 통과 테스트** | DONE | `tests/test_holdings_risk_alert_runner.py` **22건** — 러너 `run()` 실제 통과 (§9.2) |
| 7 | 역검증 **17종** | DONE | **31종** 실행 · 전부 탐지 (§9.3) |
| 8 | 결과서 + 목업 제출 | DONE | 본 문서 + `docs/handoff/POC3/OPS-02A_TELEGRAM_MOCK.html` |
| 9 | **부분 실패·결손 종목을 본문에 `데이터 확인 필요` 로 표시** (PLAN §4.6·§4.7) | DONE **(r2 신규)** | `holdings_risk_render.render_unavailable_group` · `holdings_risk_flow` 배선. r1 은 진단에만 남겼다 |
| 10 | **메시지 이름 `[보유 급락 알림]` · 단수 문구 분기** (PLAN §4.2-c) | DONE **(r3 신규)** | **사용자 직접 지시 2026-09-07.** 09:15 `[보유 종목 관찰 브리핑]` 과 혼동 방지 |

PLAN §7.2 "하지 않는다" — `CONCENTRATION`·동조 미구현, 실제 발송 0건, OCI 배포 0건,
flag 활성화 0건, cron 편집 0건, spike 로직 재사용 0건, 신규 수집기·스키마 0건.

---

## 2) 변경된 파일 목록

### 신규

| 파일 | 줄 | 역할 |
|---|---:|---|
| `app/runtime_evidence/holdings_risk.py` | 274 | `DAY_DROP` 판정 · 구간 분류 · 선정 · fingerprint |
| `app/runtime_evidence/holdings_risk_state.py` | 190 | `worst_state` 상태 로드/변화 판정/원자 저장 |
| `app/runtime_evidence/holdings_risk_render.py` | 136 | 본문 렌더 (두 줄 배치 · 구간 그룹 · **데이터 확인 필요 그룹**) |
| `app/runtime_evidence/holdings_risk_flow.py` | 236 | 조립 흐름 (§3-d) — 가드 재사용 · 본문 생성 · **결손 종목 이름 매핑** |
| `app/three_push_runtime/runner_duplicate.py` | 68 | **KS-10 분리** — 비-spike 중복 가드 |
| `app/three_push_runtime/runner_evidence.py` | 129 | **KS-10 분리** — §4 evidence 조립 · §8 발송 성공 기록 |
| `tests/test_holdings_risk_alert.py` | — | 단위 **35건** |
| `tests/test_holdings_risk_alert_runner.py` | — | 흐름 통과 **22건** |
| `docs/handoff/POC3/OPS-02A_TELEGRAM_MOCK.html` | — | 목업 (실 렌더러 출력) |

### 수정

| 파일 | 변경 |
|---|---|
| `scripts/run_three_push_runtime_oci.py` | §3-d 조립 · §6-c 판정 · §7 중복키 슬롯 · §8 상태 저장 배선 + **KS-10 분리 4건** |
| `app/three_push_runner_common.py` | `VALID_PUSH_KINDS` · `PUSH_KIND_FLAG_ENVS` 에 종류·flag 추가 |
| `app/three_push_runtime_param.py` | `ALLOWED_PUSH_KINDS` 에 `holdings_risk_alert` 추가 |
| `app/three_push_runtime/target_tickers.py` | 위험 알림 대상 = 보유 원장 (spike universe 아님) |
| `app/three_push_runtime/price_refresh.py` | `holdings_risk_alert` 시세 조회 대상 + `evaluate_price_refresh` 분리 · **부분 실패 허용 종류에 위험 알림 추가** |
| `tests/conftest.py` | 라이브 state 격리 fixture 를 **위험 상태 파일까지** 확장 |
| `tests/test_three_push_runtime_param.py` | `ALLOWED_PUSH_KINDS` 계약 테스트를 4종으로 갱신 |
| `docs/ai_plan/.../PLAN_V1.md` | V1.3 — 시가 대비 제외(§4.2-b) · R-1b 추가 |

**git 상태 (보고 시점 실측, 본 작업분만 발췌)**

```
A  app/runtime_evidence/holdings_risk.py
A  app/runtime_evidence/holdings_risk_flow.py
A  app/runtime_evidence/holdings_risk_render.py
A  app/runtime_evidence/holdings_risk_state.py
M  app/three_push_runner_common.py
M  app/three_push_runtime/price_refresh.py
A  app/three_push_runtime/runner_duplicate.py
A  app/three_push_runtime/runner_evidence.py
M  app/three_push_runtime/target_tickers.py
M  app/three_push_runtime_param.py
M  docs/ai_plan/POC3/POC3-OPS-02A_HOLDINGS_RISK_ALERT_MINIMUM_PLAN_V1.md
A  docs/ai_result/POC3/POC3-OPS-02A_HOLDINGS_RISK_ALERT_MINIMUM_RESULT.md
A  docs/handoff/POC3/OPS-02A_TELEGRAM_MOCK.html
M  scripts/run_three_push_runtime_oci.py
M  tests/conftest.py
A  tests/test_holdings_risk_alert.py
A  tests/test_holdings_risk_alert_runner.py
M  tests/test_three_push_runtime_param.py
```

> r1 검증자 B-5 지적(신규 운영 모듈이 Git 추적 대상 아님) 반영 — **전부
> staged** 로 올렸다(좌측 `A`/`M`, 우측 컬럼 공백 · `??` 0건). **커밋은
> 하지 않았다** — 사용자 지시를 기다린다. 저장소에는 이 작업과 무관한 다른
> 작업의 변경(`app/ml_score_validity_*` 등 POC3-ML-02 계열)도 남아 있어 위
> 목록에서 제외했다.

---

## 3) 신규 추가된 의존성

**없음.** 표준 라이브러리(`json`·`os`·`tempfile`·`dataclasses`·`pathlib`)와 기존
사내 모듈만 쓴다. 신규 외부 조회·신규 endpoint·신규 스키마 0건.

---

## 4) 지시문 외 변경

| # | 변경 | 이유 |
|---|---|---|
| 1 | **KS-10 분리 4건** — 러너 §3(가격 판정)·§4(evidence)·§7(중복 가드)·§8(발송 기록)을 helper 로 이동 | 배선 후 러너가 **709줄**이 되어 KS-10(650) 위반. 기계적 이동이며 **판정 로직 변경 0건**. 결과 **637줄** |
| 2 | `ALLOWED_PUSH_KINDS` 에 종류 추가 + 해당 계약 테스트 갱신 | 없으면 러너 §2 가 `push_kind_not_in_param` 으로 끊어 기능이 **영영 동작하지 않는다**. PLAN §7.1 "신규 종류" 범위로 판단 |
| 3 | `price_refresh` **부분 실패 허용 종류에 위험 알림 추가** | PLAN §4.6 "부분 실패 — 오늘 quote 하나라도 있으면 실패 종목만 표시하고 진행". 기존 코드는 `holdings_briefing` 만 면제해 위험 알림은 부분 실패 시 전면 차단됐다 |
| 4 | `tests/conftest.py` 격리 fixture 확장 | 같은 러너 §8 이 쓰는 **두 번째** 상태 파일. 하나만 막으면 "한 통로 막기" |
| 5 | 구간 전이 표기를 짧은 라벨로 (`(7~10% → 10% 이상)`) | 그룹 헤더에 이미 전체 라벨이 있어 줄이 두 배가 됐다. **PLAN 이 고정한 문자열이 아니다**(그룹 헤더·본문 헤더는 그대로) |
| 6 | **메시지 이름·단수 문구 변경** (r3) | **지시문 외가 아니라 사용자 직접 지시다.** PLAN §4.2 확정 문구를 바꾸는 것이라 개발자가 임의로 하지 않고 목업 확인 후 사용자 결정을 받았다. PLAN §4.2-c 에 **사용자 지시임을 명시**했다 |

---

## 5) 알려진 한계 / 미완성

| # | 한계 |
|---|---|
| 1 | **결손만으로는 발송하지 않는다** — `데이터 확인 필요` 는 신규·악화가 있어 **발송이 성립할 때 함께** 실린다. 결손만 있는 틱은 미발송이다(§8.5). PLAN §4.3 발송 표에 결손 항목이 없고, 촉발시키면 억제 계약이 없어 매 틱 알림이 나간다 |
| 2 | **`.env` 에 신규 flag 줄이 없다** — `env_bool` 이 미기재 키를 `false` 로 읽어 fail-closed 는 성립한다. 다만 **활성화하려면 배포 시 `.env` 에 줄을 추가**해야 한다 (§7-1) |
| 3 | **활성 PARAM 재발급 필요** — `ALLOWED_PUSH_KINDS` 는 늘렸지만 **이미 저장된 활성 PARAM row 의 `enabled_push_kinds` 에는 없다.** 새 PARAM 버전을 만들어 활성화해야 러너 §2 를 통과한다 (§7-2) |
| 4 | **cron 미편집** — PLAN §4.4 방법 (c)(시각 유지·push-kind 교체)는 OCI 쓰기라 수행하지 않았다 (§7-3) |
| 5 | `CONCENTRATION`·동조 움직임 미구현 (PLAN §7.2 로 범위 밖) |
| 6 | 실제 Telegram 발송·OCI 실측 0건. 모든 확인은 mock/replay 다 |

---

## 6) 다음 검증자(Codex)에게 알릴 점

### 6.1 우선 볼 곳

| # | 항목 |
|---|---|
| 1 | **가드 순서** — `holdings_risk_flow.assemble_holdings_risk_push` 는 `fail`·`skip_non_trading_day` 를 **돌려주기만** 하고, 결정은 러너 §6-c(`scripts/run_three_push_runtime_oci.py`)가 flag guard 뒤에서 한다. 역검증 R-11·R-11b 로 고정 |
| 2 | **중복키 슬롯** — 위험 알림만 `HH:MM`(`2026-09-07#10:30`). 일 단위 키면 같은 날 **악화 재발송이 막힌다**. `runner_duplicate.resolve_duplicate_slot` · 역검증 R-18 |
| 3 | **`worst_state` 를 낮추지 않는다** — 낮추면 완화 후 같은 날 재진입이 신규로 잡혀 재발송된다. `merge_worst` · 역검증 R-6·R-8 |
| 4 | **KS-10 분리 4건이 판정을 바꾸지 않았는지** — 분리 전후 러너 관련 테스트 동일 통과를 확인했으나, 검증자가 diff 를 직접 볼 것 |
| 5 | **`데이터 확인 필요` 배선** (r2 신규) — `select_risk_holdings` 의 `unavailable` → `HoldingsRiskOutcome.unavailable`(이름 매핑) → `render_risk_alert(unavailable=...)` → 본문. 역검증 R-19·R-19b·R-19c 로 각 구간을 따로 고정했다 |
| 6 | **`registry_date_field` 배선** — §7 에서 조회한 키와 §8 `mark_sent` 가 기록하는 키가 같아야 한다. 분리하면서 `check_plain_duplicate` 가 그 값을 함께 반환하도록 했다. spike 경로는 `None` 으로 초기화 후 §8 에서 fingerprint 별로 다시 만든다 |

### 6.2 판단이 어려웠던 부분

| # | 항목 |
|---|---|
| 1 | ~~헤더의 "동시 하락"~~ — **r3 에서 해결됨.** r1·r2 시점에는 PLAN §4.2 확정 문구라 `M=1` 일 때 `1종목 동시 하락` 이 되는 것을 개발자가 임의로 바꾸지 않고 사용자 확인에 올렸다. 사용자 확정(PLAN §4.2-c)으로 `1종목 하락` 분기를 넣었다. **현재 남은 문제가 아니다** (§9.7) |
| 2 | **부분 실패 면제 추가**(§4-3) — PLAN §4.6 표의 재사용 계약을 근거로 판단했으나, 기존 코드가 `holdings_briefing` 만 면제한 것이 의도였을 가능성도 있다 |
| 3 | **결손 종목이 발송을 촉발해야 하는가** — 촉발시키지 않기로 했다. PLAN §4.3 발송 표에 결손 항목이 없고, 억제 계약도 없어 촉발시키면 결손이 해소될 때까지 **매 틱 알림**이 나간다. 대신 발송이 성립할 때 반드시 함께 싣는다. 역검증 R-19d 가 반대 방향(촉발)을 탐지한다. **설계자 확정 사항이 아니라 개발자 판단**이므로 검증자가 볼 것 |
| 4 | **R-11 첫 사보타주가 무효였다** — 조립 단계 `out.fail` 만 바꾸는 사보타주는 러너가 그 값을 §6-c 로 미루므로 **시점을 바꾸지 못한다**. 미탐지로 나온 원인이 테스트 공백이 아니라 사보타주 무효였다. 러너에서 실제로 앞당기도록 고쳐 재실행 → 탐지 |

---

## 7) 배포 전 남은 조건

문구 확인은 **완료**됐다(사용자 `APPROVED` · §9.7). 아래는 **운영 전환에 필요한
조건**이며, 전부 OCI 쓰기이거나 사용자 승인 사항이라 본 작업에서 수행하지 않았다.

| # | 조건 | 상태 |
|---|---|---|
| 1 | `.env` 에 `PUSH_AUTOSEND_HOLDINGS_RISK_ALERT_ENABLED` 줄 추가 | 미수행 — 현재 미기재라 `env_bool` 이 `false` 로 읽어 fail-closed |
| 2 | 활성 PARAM 재발급 (`enabled_push_kinds` 에 신규 종류 포함) | 미수행 — 없으면 `push_kind_not_in_param` 으로 skip |
| 3 | 기존 **7개 cron** 의 push-kind 교체 (PLAN §4.4 방법 (c) — 시각 유지) | 미수행 — OCI 쓰기 |
| 4 | OCI 배포 | 미수행 |
| 5 | 실제 운영 확인 (no-signal 또는 신호 발생 경로) | 미수행 — flag `false` 인 채 배포 후 비활성 차단 확인이 선행 |

---

## 8) 계약 요약 (검증자 대조용)

### 8.1 판정식

```
DAY_DROP = runtime 현재가 / 직전 거래일 종가 - 1
```

- 분모: **직전 거래일 종가** (당일 시가 아님 — 갭 하락을 놓친다)
- 분자: runtime 현재가. `price_asof` 가 **실행일**이어야 유효
- 직전 거래일 종가가 **정확히 없으면 대체하지 않고** 데이터 확인 대상으로 뺀다
- 거래일 축 = KODEX200(`069500`) 시퀀스 재사용 (신규 캘린더 없음)

### 8.2 구간 (상한 배타 · 하한 포함)

| 구간 | 범위 | 정확히 경계일 때 |
|---|---|---|
| `D5_7` | −7% < x ≤ −5% | −5.0% → `D5_7` |
| `D7_10` | −10% < x ≤ −7% | −7.0% → `D7_10` |
| `D10_PLUS` | x ≤ −10% | −10.0% → `D10_PLUS` |

### 8.3 발송 여부

| 상황 | 발송 |
|---|---|
| 처음 구간 진입 | O |
| 더 나쁜 구간으로 이동 | O |
| 같은 구간 유지 | X |
| 완화 · 해소 | X |
| 완화 후 같은 날 재진입 | X (`worst_state` 유지 때문) |
| 다음 거래일 첫 진입 | O (상태 초기화) |
| 상태 파일 없음/손상/스키마 불일치 | O (전부 신규 — 조용한 억제 금지) |

### 8.4 fingerprint

```
{ticker}#DAY_DROP#{state}
```

보조 2종·근거 값은 **넣지 않는다** — 값이 미세하게 흔들릴 때마다 재발송된다.

### 8.0 메시지 이름 (r3 · 사용자 지시)

| | 문구 |
|---|---|
| 09:15 (운영 중, 본 작업 대상 아님) | `[보유 종목 관찰 브리핑]` |
| **본 작업** | **`[보유 급락 알림]`** |

`push_kind` 식별자 `holdings_risk_alert` 와 flag 이름은 **바꾸지 않았다** — 표시
문구만 바뀌었고, 식별자를 바꾸면 registry·PARAM·cron 계약이 함께 깨진다.

헤더 단수 분기:

| 종목 수 | 헤더 |
|---|---|
| 1종목 | `보유 23종목 중 1종목 하락` |
| 2종목 이상 | `보유 23종목 중 5종목 동시 하락` |

### 8.5 데이터 결손 표시 (r2 신규)

| 상황 | 처리 |
|---|---|
| 시세 조회 실패 (부분 실패) | 선정 제외 · **본문 `데이터 확인 필요` 그룹에 표시** |
| 직전 거래일 종가 결손 | 대체 금지(§4.7) · 선정 제외 · **본문 표시** |
| 다계좌 결손 종목 | ticker 기준 **한 번만** |
| 결손만 있고 신규·악화 0건 | **미발송** — 진단에만 남는다 |

본문 형태 (구간 그룹 **뒤**):

```
■ 데이터 확인 필요 (1)
  KODEX 200TR
      직전 거래일 종가 또는 오늘 시세를 확인할 수 없음
```

구간(하락률)을 붙이지 않는다 — 계산할 수 없기 때문이다.

---

## 9) 검증 실행 결과 (실측)

### 9.1 품질 게이트

| 항목 | 결과 |
|---|---|
| `black --check app scripts tests` | `306 files would be left unchanged` |
| `flake8 app scripts tests` | exit 0 (출력 없음) |
| `py_compile` (신규 6 + 러너) | exit 0 |
| KS-10 (650줄) | 러너 **637** · 신규 최대 **274** — 전부 미달 |

### 9.2 테스트

| 대상 | 건수 |
|---|---:|
| `tests/test_holdings_risk_alert.py` (단위) | 35 passed |
| `tests/test_holdings_risk_alert_runner.py` (흐름 통과) | 22 passed |
| 역검증 기준선 (위험·보유·러너 5파일) | **182 passed / 0 failed** |
| 전체 백엔드 회귀 `pytest tests/` | §9.4 참조 |

### 9.3 역검증 31종 — **전부 탐지 · 미탐지 0**

기준선 **182 passed**. r2 에서 R-19 계열 4종, r3 에서 R-20 계열 2종을 추가했다.

| # | 무력화 | 실패 |
|---|---|---:|
| R-1 | 분모를 직전 종가 대신 당일 시가로 | 1 |
| R-1b | 외부 계산 등락률(`fluctuationsRatio`)로 trigger 대체 | 1 |
| R-2 | 분자를 현재가 대신 전일 종가로 | 1 |
| R-2b | 분자의 당일(`price_asof`) 검사 제거 | 1 |
| R-3 | 완화도 발송 | 1 |
| R-4 | 해소도 발송 | 1 |
| R-5 | 동일 구간 억제 제거 | 1 |
| R-6 | 완화 시 기존 `worst` 기록을 버림 | 1 |
| R-7 | 거래일 경계 초기화 제거 (전일 상태 이월) | 1 |
| R-8 | `worst` 를 낮춤 (직전 구간과 비교) | 1 |
| R-9 | 비거래일 판정 우회 | 1 |
| R-10 | 발송 실패·부분 전달에도 state 저장 | 1 |
| R-10b | §8 기록을 발송 성공 여부와 무관하게 호출 | 1 |
| R-11 | skip·fail 결정을 러너 §3-d 로 (flag guard 앞) | 1 |
| R-11b | §6-c 위험 알림 skip 을 flag guard 앞으로 | 1 |
| R-12 | 보조 2종을 fingerprint 에 포함 | 1 |
| R-12b | 근거 값(`day_drop_pct`)을 fingerprint 에 포함 | 1 |
| R-13 | 위험 알림을 evidence/spike 조립 경로로 되돌림 | 1 |
| R-14 | 동시 발생을 Top 3 로 잘라냄 | 1 |
| R-14b | 구간 그룹을 하나만 렌더 | 1 |
| R-15 | 구간 경계를 배타로 (정확히 −5/−7/−10% 오분류) | 2 |
| R-16 | 직전 종가 없을 때 더 오래된 종가로 대체 | 1 |
| R-17 | 다계좌 종목을 여러 행으로 | 1 |
| R-17b | 다계좌 계좌 수 표기 제거 | 1 |
| R-18 | 위험 알림 중복키를 일 단위로 | 1 |
| **R-19** | 결손·부분 실패 종목을 본문에서 누락 (진단에만 기록) | 1 |
| **R-19b** | 결손 목록을 렌더러에 전달하지 않음 (배선 유실) | 1 |
| **R-19c** | 결손 종목 이름 매핑을 비움 | 1 |
| **R-19d** | 결손만으로도 발송을 촉발 (매 틱 알림) | 1 |
| **R-20** | 메시지 이름을 09:15 브리핑과 같은 계열로 되돌림 | 1 |
| **R-20b** | 1종목에도 `동시 하락` 을 붙임 | 1 |

**PLAN §5 의 R-1~R-17 17종을 모두 포함하고, 14종(R-1b·R-2b·R-10b·R-11b·R-12b·R-14b·R-17b·R-18·R-19·R-19b·R-19c·R-19d·R-20·R-20b)을 추가했다.** R-19 계열 4종은 **r1 검증자 지적(A-1·A-3·B-6)에서 나온 것**이다 — r1 에는 본문 표시를 검사하는 테스트가 없어 누락이 통과했다.

**역검증 운영 규칙 준수**

- `atexit` + SIGTERM/SIGINT/SIGHUP 핸들러 — 어떤 경로로 죽어도 원본 복원
- 적용·복원 양쪽에서 `__pycache__` 삭제 + 하위 pytest `PYTHONDONTWRITEBYTECODE=1`
- 대상 문자열 없음·소스 불변이면 **SKIP 이 아니라 오류**로 세움 (조용한 SKIP 이
  "탐지" 로 오독되는 것을 막는다)
- **발송 0건** — `telegram_send` 를 mock 으로 교체, 호출 본문을 리스트로 수집
- **라이브 state 미접근** — 상태 경로를 `tmp_path` 로 주입 + conftest 가 라이브
  파일 **내용 변경까지** 감지해 실패시킴

**잔여 사보타주 확인** — 복원 후 grep **0건**:

```
grep -rn "current \* 0.99|fluctuations_ratio|base / base|GROUP_ORDER\[:1\]|if False:" \
  app/runtime_evidence app/three_push_runtime scripts/run_three_push_runtime_oci.py
→ 잔여 0건
```

> 신규 모듈은 아직 `??`(untracked)라 `git diff` 로는 잔여가 잡히지 않는다.
> 그래서 **git 이 아니라 grep 으로** 확인했다.

### 9.4 전체 백엔드 회귀

```
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/ -q --no-header
→ 1422 passed, 1 warning in 146.23s (0:02:26)
```

| 시점 | 결과 |
|---|---|
| r1 최종 | 1,411 passed / 0 failed |
| r2 최종 (결손 본문 표시 + 테스트 8건 추가) | 1,419 passed / 0 failed |
| **r3 최종** (문구 확정 + 테스트 3건 추가) | **1,422 passed / 0 failed** |

실패 0건. 급락 알림 관련 신규 **57건**(단위 35 + 흐름 22)이 여기에 포함된다.

---

## 9.5) r1 검증자 `REJECTED` — 처리 내역

| # | 지적 | 처리 |
|---|---|---|
| A-1 | PLAN §4.6 은 부분 실패 종목을 `데이터 확인 필요` 로 **표시**하라는데 진단 목록에만 저장했다 | **수정.** `render_unavailable_group` 신설 + `holdings_risk_flow` 가 `(ticker, 종목명)` 을 렌더러로 전달. 발송이 성립할 때 본문 말미에 그룹으로 실린다 |
| A-2 | "데이터 확인 필요 표시가 실제 OCI 경로에서 작동한다" 는 설명과 출력이 다르다 | **정정.** 해당 문구는 `price_refresh` 코드 주석(보유 브리핑 계약)에서 온 것이고, 위험 알림 본문에는 실제로 없었다. 이제 실제로 나온다 |
| A-2 | 시가 대비는 V1.3 에서 정식 제외됐으므로 요구사항 2 는 `PARTIAL` 이 아니라 완료 | **정정.** §1 표에서 `DONE` 으로 |
| A-3 | 독립 재현 — A는 −10%, B는 조회 실패 → 본문에 A만 | **수정 + 그 시나리오를 테스트로 고정.** `test_partial_failure_ticker_appears_in_sent_body` |
| B-5 | 신규 운영 모듈이 Git 추적 대상이 아니다 | **staged 로 올렸다** (§2). 커밋은 사용자 지시를 기다린다 |
| B-6 | 테스트가 진단에 남는지만 확인하고 본문 표시는 검사하지 않는다 | **흐름 테스트 4건 추가** — 부분 실패 / 직전 종가 결손 / 결손 단독 미발송 / 다계좌 결손 1회. 단위 4건 추가. 역검증 R-19 계열 4종 추가 |

---

## 9.6) r2 검증자 `VERIFIED_WITH_NOTES` — 처리 내역

| # | 메모 | 처리 |
|---|---|---|
| A-2 | §1 요구사항 6 의 흐름 테스트 `18건` 이 stale | **22건** 으로 정정 + 근거 `§9.2` 링크 |
| A-2 | §1 요구사항 7 의 역검증 `25종` 이 stale | **29종** → r3 에서 **31종** 으로 갱신. 근거를 `§5`(PLAN 절 번호 오참조) → **`§9.3`** 으로 정정 |

같은 패턴(`18건`·`25종`·`28건`·`46건`·`171 passed`)을 전 문서 grep → 잔존 0건.
`1,411` 은 `r1 최종` 라벨이 붙은 이력 행이라 유지했다.

---

## 9.7) r3 — 사용자 문구 확정 반영

목업 확인 후 사용자가 두 가지를 직접 지시했다 (PLAN §4.2-c).

| # | 지시 | 처리 |
|---|---|---|
| 1 | 메시지 이름 `[보유 종목 위험 알림]` → **`[보유 급락 알림]`** | `HEADER`·`PREVIEW_HEADER` 변경. 09:15 `[보유 종목 관찰 브리핑]` 과 혼동을 막는다 |
| 2 | 1종목이면 `동시` 없이 **`1종목 하락`** | `render_risk_alert` 헤더 분기 |

**검증 범위 판단** — 표시 문구만 바뀌었고 판정식·상태·가드 계약은 그대로다.
그래서 (a) 해당 문자열을 단언하는 테스트 갱신 · (b) 새 계약 역검증 **2종 신규**
(R-20·R-20b) · (c) **전체 회귀**(다른 파일이 옛 문자열을 단언할 수 있으므로) 를
했다. R-1~R-19 는 렌더 문구와 무관해 재실행이 필요한 변경이 아니다(스크립트가
케이스 선택을 지원하지 않아 결과적으로 함께 돌았을 뿐이다).

**옛 문구 잔존 확인** — `보유 종목 위험 알림` 을 코드·테스트·목업 전체 grep
(PLAN·결과서의 이력 서술 제외) → **0건**.

---

## 10) 목업

`docs/handoff/POC3/OPS-02A_TELEGRAM_MOCK.html` — 브라우저로 열면 Telegram 말풍선
형태로 3장면을 볼 수 있다. **실제 렌더러(`render_risk_alert`) 출력 그대로**이며
종목·수치만 합성이다.

```
[보유 급락 알림] 10:30 — 보유 23종목 중 5종목 동시 하락
기준: 직전 거래일 종가 2026-09-04 · 시세 09-07 10:30

■ 전일 대비 하락 10% 이상 (2)
  SOL 미국AI전력인프라
      전일 대비 -12.4% · 고점 대비 -18.2% · 매입대비 +31.5%
  KODEX 미국AI전력핵심
      전일 대비 -11.1% · 고점 대비 -16.0% · 매입대비 +8.4%

■ 전일 대비 하락 7~10% (2)
  KODEX AI전력 (2개 계좌)
      전일 대비 -8.6% · 고점 대비 -12.7% · 매입대비 -3.2%
  TIGER 미국AI빅테크
      전일 대비 -7.2% · 고점 대비 -10.4% · 매입대비 +44.0%

■ 전일 대비 하락 5~7% (1)
  KODEX 미국S&P500
      전일 대비 -5.4% · 고점 대비 -6.9% · 매입대비 +62.1%

■ 데이터 확인 필요 (1)
  KODEX 200TR
      직전 거래일 종가 또는 오늘 시세를 확인할 수 없음
```

두 번째 장면(12:30)은 **악화 1건 + 신규 1건만** 싣는다 — 억제된 3종목은 다시
나오지 않는다:

```
■ 전일 대비 하락 10% 이상 (1)
  KODEX AI전력 (2개 계좌)
      전일 대비 -13.9% · 고점 대비 -18.0% · 매입대비 -8.5%   (7~10% → 10% 이상)
```

배치가 두 줄인 이유: 발송이 `parse_mode="HTML"` 이라 Telegram 이 **비례 글꼴**로
렌더해 공백 정렬이 성립하지 않는다(OPS-01A 와 같은 결론).
