# POC3-02C — 장중 통합 판단 브리핑 · 설계서

- **작성**: 설계자 · **수신**: 개발자 · **수신일**: 2026-09-15 ~ 2026-09-16
- **성격**: 설계서 보존본. 설계자가 웹에서 채팅으로 전달한 지시를 개발자가
  저장소에 기록한 것이다.

> **기록 경위** — 설계자는 웹 환경이라 저장소에 파일을 쓸 수 없다. 개발자가
> 수신한 지시를 보존한다. 02B-2 설계서와 같은 방식이다.
>
> 이 Step 은 설계 판단이 **네 번 정정**됐다. 정정 전 내용도 §6 에 남긴다 —
> 지우면 왜 이 구조가 됐는지 추적할 수 없다.

---

## 1. 최종 푸시 구조

| 시점 | 내용 | 횟수 |
|---|---|---:|
| 장 시작 전 | 오늘 장이 어떻게 흘러갈지 예측 | 08:00 **1회** |
| 장중 | 신규 진입 검토·회피 후보 + 보유종목 흐름 | **일 3회** |
| 장중 긴급 | 보유종목 급락 위험 | 조건 발생 시 |

```text
고정 메시지      = 4건/일   (08:00 시장 브리핑 1 + 장중 3)
조건부 급등락    = 0~7건/일
신규 고정 메시지 = 0건
```

**신규 고정 푸시를 추가하지 않는다.** 기존 급락 알림을 **보유종목과 시장 대표
ETF 를 함께 보는 조건부 급등락 알림**으로 바꾸는 것이다.

⚠ **미확정** — 설계자가 "08:00 별도 1회 + 장중 3회 = 하루 최대 4회" 로 이해한
것이 맞는지 사용자 확인을 요청했고, **아직 답이 오지 않았다.**

---

## 2. 장중 브리핑의 핵심

장중 급등락 ETF 를 **단순 나열하는 기능이 아니다.**

| 구분 | 뜻 |
|---|---|
| 신규 진입 검토 후보 | 급등락이 발생했고 **추가 검토할 근거가 있는** ETF |
| 신규 진입 회피 후보 | 과열·하락 지속·근거 부족 등 **지금 들어가면 위험한** ETF |
| 내 보유종목 흐름 | 상승·하락·이상 움직임과 확인할 사항 |

**급등했다고 무조건 좋은 후보가 아니고, 급락했다고 무조건 회피 후보도 아니다.**
급등락은 **탐지 신호**이고, 분류는 다른 evidence 와 함께 해야 한다.

### 2-1. 표현 제한

```text
진입 검토 후보 ≠ BUY
진입 회피 후보 ≠ SELL
최종 판단       = 사용자
```

---

## 3. 관찰 대상 — 사업군 대표 ETF 고정 방식

시장 전체 1,168종을 매번 훑지 않는다. **사업군별 대표 ETF 를 고정**한다.

이유 — 사용자가 이해하기 쉽고 · 호출량이 작고 · 섹터 순환이 잘 보이며 ·
관찰 대상이 매번 바뀌지 않고 · 진입 검토·회피 이유를 설명하기 쉽다.

### 3-1. 대표 ETF 선정 원칙

- 인버스·레버리지 제외
- 합성·선물형 제외
- 해당 사업군을 직접 추종
- 거래와 가격 데이터가 안정적
- 지나치게 좁은 단일 테마보다 대표성이 높음
- 가능하면 사업군당 1개
- 대표와 예비 ETF 를 함께 기록

**고정 대표 ETF 는 "오늘 많이 올랐기 때문에" 선택하지 않는다.**
대표 선정과 당일 급등락 판정은 **분리**한다.

### 3-2. 호출량 (설계자 산정)

`대표 ETF 수 × 장중 7회` 기준. 보유와 중복되면 1회만 조회한다.

| 대표 ETF | 변경 후 | 현재(290건/일) 대비 |
|---:|---:|---|
| 20종 | 430건/일 | +140 |
| **30종** | **500건/일** | **+210 (약 1.7배)** |
| 43종 | 591건/일 | +301 |

**30종 전후가 적당하다.** 전체 ETF 스캔(약 12.8배)보다 훨씬 안전하다.

### 3-3. 전체 ETF 장중 스캔은 범위에서 제외

대표 ETF 밖의 신생 테마를 놓칠 수 있으나, **실제 누락이 반복될 때만** 동적
후보군을 추가한다.

---

## 4. 역할 분리 — PC / OCI / 사용자

| 역할 | 책임 |
|---|---|
| **PC** | ML·퀀트 계산, 사업군 구성, 대표·대체 ETF 선정, 급등락 판정 파라미터 생성·검증·OCI 전달 |
| **OCI** | 전달받은 최신 **유효 승인** 버전으로 장중 조회·판정·조건부 발송 |
| **사용자** | 결과를 보고 **실제 매매만** 결정 |
| **장애 시** | OCI 가 직전 정상 버전을 계속 사용하고 **임의 재선정하지 않음** |

### 4-1. 승인 계약 (설계자 최종 확정 — `DESIGNER_DECISION = (a)`)

```text
PC 자동 산출                 = YES
사용자의 종목별 직접 선택      = NO
변경된 PARAM 의 버전 단위 승인 = YES
승인 없는 자동 승격           = NO
OCI 의 일상 운영              = AUTO
사용자의 최종 매매 판단        = MANUAL
```

```text
USER_SELECTS_SECTORS_OR_ETFS        = false
PC_AUTOMATED_SELECTION              = true
PC_AUTOMATED_PARAM_GENERATION       = true
USER_APPROVES_NEW_EFFECTIVE_VERSION = true
AUTO_PROMOTION_WITHOUT_APPROVAL     = false
OCI_USES_LATEST_APPROVED_PARAM      = true
NO_CHANGE_REAPPROVAL_REQUIRED       = false
```

사용자는 종목을 하나씩 고르는 것이 아니라, **운영 대상을 바꾸는 새 버전의 변경
요약을 보고 승인**한다. 변경이 없는 동안에는 기존 승인 버전으로 OCI 가 계속
자동 운영하므로 **매일 승인할 필요가 없다.**

### 4-2. 운영 계약 7항

1. PC 가 사업군·대표 ETF·대체 ETF·급등락 PARAM 을 자동 산출한다.
2. PC 가 검증 결과와 **직전 승인 버전 대비 변경사항**을 만든다.
3. 사용자는 종목별 선택이 아닌 **새 유효 버전 전체**를 승인한다.
4. **승인된 버전만** OCI 에 전달·활성화한다.
5. 새 버전이 없으면 재승인 없이 기존 버전으로 자동 운영한다.
6. 생성·전달·검증 실패 시 OCI 는 **직전 정상 승인 버전을 유지**한다.
7. 사용자는 Telegram 근거를 보고 최종 매매를 결정한다.

### 4-3. 승인 화면 — 최소 정보만

- 추가·제외·교체된 사업군 및 대표 ETF
- 변경 사유와 핵심 산출 근거
- 판정 PARAM 변경 내역
- 데이터 기준일
- version / checksum
- 승인 또는 기각

**직접 종목을 고르는 편집 화면은 설계하지 않는다.**

---

## 5. 작업 단위

| 단위 | 목표 |
|---|---|
| **`POC3-02C-OPS-01`** | PC 자동 사업군·대표 ETF universe 산출 및 OCI 전달 |
| **`POC3-02C-OPS-02`** | PC 산출 파라미터 기반 장중 조건부 급등락 알림 |

사용자의 **일상적인 수동 설정 단계는 두지 않는다.**

대표 ETF 의 구체적인 **교체 주기나 점수 산식은 아직 고정하지 않는다.** 먼저 최초
문서와 기존 PC→OCI 파라미터 배포 경로를 확인한 뒤, 그 구조를 재사용하는 범위에서
정한다.

### 5-1. `OPS-01` PLAN 필수 포함 항목

1. PC 자동 산출 트리거 — 기존 PC universe·ML 작업 완료 시 자동 계산 ·
   **별도 PC cron 없음** · 동일 hash 면 새 버전 생성 없음
2. 신규 단일 승인 번들 `INTRADAY_ALERT_CONFIG`
   (`sector_representative_universe` + `intraday_alert_policy` ·
   같은 version/checksum 으로 **원자 적용**)
3. 저장 경계 — 기존 `runtime_param` 과 **논리적 분리** · 기존
   `runtime_state.sqlite` **재사용** · **신규 DB 파일 금지** ·
   DB version/approval/active 가 **SSOT** · JSON 은 전송·archive 만
4. 승인 강제 — 자동 산출은 **미승인 후보만** 생성 · 사용자가 버전 전체를
   승인/기각 · `approved_at/by` 없는 버전은 **activate 거부** ·
   ETF 직접 선택 UI **금지**
5. PC→OCI 실제 호출 사슬 8단계
   ```text
   PC 승인 DB → 전송 JSON export → SCP/atomic rename → OCI verify
   → OCI DB version 적재 → 승인 확인 → active pointer 갱신
   → version/hash 재독출 대조
   ```
   **현재 코드에 OCI DB 적재·활성화 단계가 없다면 신규 구현 범위로 명시한다.**
6. 실패 계약 — 실패 시 OCI 직전 active 유지 · 기존 PUSH 3종 유지 ·
   **holdings 경로 우선** · 후보 경로 실패가 holdings 발송을 막지 않음
7. PC 화면 (§4-3)
8. 변경 파일 · DB migration · focused test · 전체 회귀 · 프론트 테스트 ·
   KS-10 전수 측정 계획

---

## 6. 정정 이력 — 폐기된 판단 4건

설계자가 스스로 정정한 것들이다. **지우지 않고 남긴다.**

| # | 폐기된 판단 | 정정 사유 |
|---|---|---|
| 1 | 사용자가 사업군 행을 만들고 대표 ETF 를 직접 선택한다 | 역할 분리 위반. PC 가 자동 산출하고 사용자는 매매만 결정한다 |
| 2 | `USER_APPROVES_EACH_POOL_VERSION = false` | **철회.** `PROJECT_ORIGIN_INTENT` 가 PC 역할에 "사용자 승인" 을 명시하고 PARAM 을 일관되게 "approved PARAM" 으로 부른다. 개발자 검증으로 확인돼 `(a) 기존 승인 계약 유지` 로 확정 |
| 3 | 급락만 우선 운영하고 급등은 나중에 | **철회.** 급등 알림도 원래 목적이면 `spike=false` 는 미완료가 맞다 |
| 4 | 기존 `spike_or_falling_alert` 를 부활시킨다 | **폐기.** 기존 spike 는 장중 급변이 아니라 **1개월 하락 스크리닝**이고 보유와 무관하다(`OPS-01C` `REJECT`). 사용자 목적과 다르다 |

```text
LEGACY_SPIKE              = KEEP_DEPRECATED
LEGACY_SPIKE_CRON         = 생성하지 않음
HOLDINGS_BRIEFING_CURRENT = 운영 유지
HOLDINGS_RISK_ALERT       = 운영 유지
NEW_INTRADAY_BRIEFING     = 신규 설계
```

새 메시지가 검증되고 사용자가 확정하기 전까지 기존 `holdings_briefing` 3회와
`holdings_risk_alert` 는 **그대로 운영**한다. 미리 cron 을 교체하지 않는다.

---

## 7. 사전 사실조사 지시 (완료)

설계자가 코드 수정 없이 사실조사만 지시했고 개발자가 두 건을 제출했다.

| 조사 | 산출물 |
|---|---|
| 사업군별 대표 ETF 후보 | `docs/ai_result/POC3/POC3-OPS-02C_SECTOR_ETF_SURVEY.md` |
| PC→OCI PARAM 전달 계약 | `docs/ai_result/POC3/POC3-OPS-02C_PARAM_DELIVERY_SURVEY.md` |

```text
ADDITIONAL_SURVEY_ROUND = NO   (설계자 종료 선언 2026-09-16)
```

---

## 8. 비차단 별도 작업 — 시장 브리핑 운영 실측

내일 07:20 KST 정기 배치 후 **한 번만** 읽기 전용 확인.

확인: 배치 실행 시각·status · API 가 선택한 `basis_date` · DB 최신 거래일 ·
08:00 기준 trading-day lag · 기초지수 문단 포함/생략 · Telegram 실행 결과.

금지: 수동 배치 재실행 · DB·코드·flag·cron 변경 ·
`MAX_STALE_TRADING_DAYS` 변경 · 장기 모니터링 전환.

**결과가 `2026-09-11` 에 그대로 머물러도 임의 수정하지 말고 실측값만 보고한다.**
이 관찰은 `OPS-01` 의 **선행조건이 아니다.**

---

## 9. 진행 순서

```text
1. 개발자 PLAN V1 제출          ← 완료
2. 설계자 승인 또는 필수 수정 확정   ← 대기
3. 개발자 구현
4. 검증자 검증
5. POC3-02C-OPS-02 장중 급등락 알림 구현
```

---

## 10. `OPS-01` PLAN V1 판정 및 필수 보완 (설계자 · 2026-09-16)

```text
PLAN_V1                   = PASS_WITH_MANDATORY_AMENDMENTS
IMPLEMENTATION_AUTHORIZED = YES
PLAN_RESUBMISSION         = NO

판단 A = (b) 신규 번들만 완결
판단 B = B-2 공식 지수명 토큰 사전
판단 C = 승인 (sector_label = 공식 토큰 그대로)
판단 D = 신규 카드 승인
```

### 10-1. 판단 A — 기존 `runtime_param` 공백은 이번에 고치지 않는다

기존 PUSH 3종은 OCI 에서 직접 생성한 DB 버전으로 정상 운영 중이다. 기존 경로까지
손대면 범위와 회귀 위험만 커진다.

- 기존 코드·DB·sync 경로 **변경 금지**
- 현재 공백은 `PROGRAM_TRUTH` 에 정확히 기록
- 신규 `INTRADAY_ALERT_CONFIG` 만 PC→OCI→DB 활성화 사슬을 완결
- 이후 기존 PARAM 통합 여부는 **별도 Cleanup**

### 10-2. 판단 B — 토큰 사전

- PC 가 공식 지수명을 토큰 사전으로 **자동 분류**
- 사전은 코드 하드코딩이 아니라 **번들 데이터**
- 한 지수는 **최대 한 사업군**에만 배정
- **긴 토큰 우선 매칭**
- 충돌하거나 매칭되지 않으면 **임의 분류하지 않고 제외·기록**
- 사용자는 자동 산출된 **버전 전체만** 승인

대표 선정 기준 (기존 조사 기준 그대로):

```text
적격  국내 주식형 · 비레버리지 · 비인버스 · 비합성
      광의시장지수 · 파생전략 제외
대표  시가총액 1위
대체  시가총액 2위
동률  ticker 오름차순
```

**대표 1개 + 대체 1개만** 둔다. 대체는 평상시 함께 조회하지 않고 **대표 조회
실패 시에만** 사용한다.

### 10-3. 필수 보완 6건

#### (1) 해시 분리 — 매일 승인 요청이 생기는 오류

PLAN 의 `input_hash` 에 가격 기준일이 들어가 **거래일마다 새 버전**이 생긴다.

```text
evaluation_input_hash   데이터·기준일·규칙 변경 감지 · 계산 이력에만 사용
effective_config_hash   대표·대체 ETF·분류 사전·정책이 실제로 달라졌는지 판정
```

**새 승인 버전은 `effective_config_hash` 가 달라질 때만 생성한다.**

| 변경 | 새 버전 |
|---|---|
| 가격 기준일만 | **없음** |
| 보유종목만 | **없음** |
| 동일 결과 재계산 | **없음** |
| 대표·대체·사전·정책 변경 | 새 후보 버전 |

**보유 여부는 장중 메시지에서 판정할 정보이지 대표 ETF 선정 입력이 아니다.**

#### (2) PC 자동 산출 시점

별도 cron 을 만들지 않는다.

- PC 백엔드 **시작 시 미수행 작업 catch-up**
- 관련 시장 데이터 갱신 **성공 후 재계산**
- **최초 1회 즉시** 산출
- 이후 대표 풀 재평가는 **최대 20거래일에 한 번**
- 현재 대표가 **적격성을 잃으면 주기와 무관하게** 재평가
- PC 가 꺼져 있으면 OCI 는 기존 승인 버전 유지

자동 재평가는 하되 **교체를 위한 강제 순환은 하지 않는다.**

#### (3) 승인과 적용은 사용자 한 번의 동작

내부 상태는 분리하되 버튼을 두 번 누르게 하지 않는다.

```text
[승인하고 OCI 적용]
  1 PC 승인 기록 → 2 JSON export → 3 OCI 전달·검증 → 4 OCI DB 적재
  → 5 승인 게이트 검사 → 6 active pointer 변경 → 7 hash 재검증
```

전달 실패 시 **`APPROVED_NOT_DEPLOYED`** 로 남기고 직전 OCI active 를 유지한다.
**재시도할 때 재승인을 요구하지 않는다.**

#### (4) PC / OCI DB 역할 구분

```text
PC  runtime_state.sqlite   후보 버전 · 사용자 승인 · 전달 결과의 SSOT
OCI runtime_state.sqlite   실제 운영 active 버전의 SSOT
JSON                       두 DB 사이의 전송·archive 형식
```

**DB 파일 자체를 복사하거나 덮어쓰지 않는다.**

#### (5) checksum 범위

`source_hash_sha256` 은 **가변값을 제외한 정규화 payload** 로 계산한다.

제외: `created_at` · `approved_at` · `approved_by` · sync 상태 · hash 필드 자체.

**승인 시각이 바뀌었다고 설정 내용의 checksum 이 바뀌면 안 된다.**

#### (6) 임계값 부재 — 최초 번들은 비활성

이번 Step 은 장중 소비를 하지 않으므로 최초 번들을 이렇게 전달한다.

```text
enabled       = false
policy_status = NOT_CONFIGURED
```

`enabled=true` 인 경우에는 급등·급락 임계값 · cooldown · 중복 억제 · 발송 상한이
**모두 있어야만 검증을 통과**한다.

**이번 구현으로 Telegram·Naver·러너 동작은 바뀌지 않는다.** 실제 정책은
`POC3-02C-OPS-02` 에서 확정한다.

### 10-4. 구현 완료 조건

```text
기존 runtime_param 변경      = 0
기존 PUSH 실행 경로 변경      = 0
RUNNER_LINES                 = 648
신규 번들 enabled            = false
미승인 활성화                = 차단
전달 실패 시 OCI active 변경  = 0
PC/OCI version·hash 대조     = 일치
Telegram / Naver 호출        = 0
전체 회귀                    = PASS
프론트 기존 테스트            = PASS
KS-10 TRIGGER                = 0
```

---

## 11. `POC3-02B-OPS-03` 정기 PUSH 중복 억제 판정 (설계자 · 2026-09-16)

§8 실측이 만든 파생 지시다. **개발자가 웹에서 수신해 기록한 설계자 판정**이며,
§8 관찰이 `OPS-01` 의 선행조건이 아니라는 원칙은 그대로다 — 이 건은 같은 제출에
함께 담되 별도 PLAN 은 요구하지 않는다.

### 11-1. 실측이 드러낸 것

```text
2026-09-16 08:00  market_briefing   skipped  no_change
2026-09-16 12:30  holdings_briefing skipped  no_change
```

07:20 배치는 정상이었다(적재 21→22일 · 최신 `2026-09-14` · lag 1 · 임계 이내).
데이터 문제가 아니라 **억제 계약 자체가 정기 브리핑의 목적과 어긋난 것**이다.

지난 9거래일: 전망 상태 변경 3회 → 발송 4일 · 억제 5일.
`2026-09-07~09-11` 은 5거래일 연속 `DOWN` — 그 주 브리핑이 1회였을 것이다.

### 11-2. 판정 — **(b) 정기 PUSH 의 콘텐츠 동일 억제를 해제한다**

| PUSH | 성격 | 억제 |
|---|---|---|
| 08:00 시장 브리핑 | 정기 | 거래일마다 발송. **전일과 같아도 발송** |
| 보유 브리핑 3슬롯 | 정기 | 슬롯마다 발송. **내용이 같아도 발송** |
| 보유 급락 알림 7틱 | 사건 | 동일 위험·중복 신호 억제 **유지** |

**fingerprint 를 제거하지 않는다.** 용도를 바꾼다 — 메시지 비교·운영 기록에
쓰고, 발송은 막지 않는다. 같은 날 같은 슬롯의 중복 실행은 이미 있는
`registry_key` 가 막는다.

```text
market_briefing   registry_key(push_kind, param_id, runtime_date_kst)
holdings_briefing registry_key(..., slot_id=...)  →  runtime_date_kst#slot_id
```

정기와 사건형을 가르는 기준: **정기는 "오늘 상태를 알려주는 것"이라 같은 답도
알 가치가 있고, 사건형은 "지금 대응하라는 것"이라 반복이 피로다.**

### 11-3. 12:30 건 판정 요구

`holdings_briefing` 의 `no_change` 가 (ㄱ) 같은 날 OPEN 슬롯과의 콘텐츠 비교인지
(ㄴ) 동일 슬롯 재실행 차단인지 실측해 구분하고, (ㄱ)이면 수정 대상이다.

### 11-4. 진행 순서

```text
1. OPS-01 구현 + UI 배치        ← 완료
2. OPS-03 억제 해제 구현         ← 이 지시
3. 역검증 · 문서검증
4. OPS-01 + UI + OPS-03 묶어 검증자 제출
5. POC3-02C-OPS-02 장중 급등락 알림 구현
```

---

## 12. `deploy_unconfirmed` 계약 확정 (설계자 · 2026-09-18)

검증자 r3 이 "설계 계약에 없는 상태" 로 반려한 건에 대한 설계자 판정이다.
개발자가 웹에서 수신해 기록한다.

```text
DESIGNER_DECISION        = APPROVED
DEPLOY_UNCONFIRMED       = VALID_STATE
BOUNDED_READ_RETRY       = IMPLEMENT_NOW
AUTOMATIC_REAPPLY        = FORBIDDEN
```

### 12-1. 판정 근거

`deploy_unconfirmed` 는 **기존 계약 위반이 아니라 기존 계약이 다루지 못한
분산 처리의 불확정 결과**다. 모르는 것을 실패라고 단정하는 것보다 별도 상태가
정확하다.

### 12-2. 원격 적용 결과 3종

| 상태 | 의미 |
|---|---|
| `deployed` | 목표 version/hash 가 OCI active 임을 **재조회로 확인** |
| `remote_apply_failed` | 적용되지 않았고 직전 active 가 유지됨을 **확인** |
| `deploy_unconfirmed` | 적용 명령 이후 OCI 상태를 재조회하지 못해 **결과를 모름** |

### 12-3. read-back 재시도 — 조회만 3회

```text
1차 즉시 · 2차 2초 후 · 3차 5초 후
```

- 재시도는 **조회만** 한다. 적용 명령을 자동으로 다시 실행하지 않는다.
- 어느 회차든 **목표** version/hash 확인 → `deployed`
- **직전** version/hash 확인 → `remote_apply_failed`
- 3회 모두 조회 실패 또는 예상 밖 상태 → `deploy_unconfirmed`

### 12-4. `deploy_unconfirmed` 일 때 금지·의무

```text
금지  OCI active 추정 · PC 완료 표시 · 자동 재적용
의무  화면에 「OCI 적용 여부 확인 필요」 · 사람이 확인 후 재시도
```

### 12-5. 판정 시점의 실제 상태 (설계자 확인)

```text
CODE_DEPLOYED            = YES (b077641f)
INTRADAY_CONFIG_CREATED  = NO
INTRADAY_CONFIG_DEPLOYED = NO
DEPLOY_UNCONFIRMED       = NO
```

승인 버튼을 누른 적이 없으므로 현재는 단순히 `not_deployed` 다.

### 12-6. 진행 순서

```text
1. read-back 재시도 구현 + focused test   ← 이 지시
2. 전체 회귀 재통과 · 검증자 제한 재검증
3. POC3-02C-OPS-01 종료
4. 정기 PUSH no_change 억제 수정(§11) 이어서
```
