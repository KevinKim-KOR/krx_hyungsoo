# POC3-OPS-02B-2 — 08:00 시장 흐름 브리핑 메시지·억제·운영 · 설계서

- **작성**: 설계자 · **수신**: 개발자 · **수신일**: 2026-09-11
- **성격**: 설계서. **구현 금지 — PLAN·모호점 선제출**

> 원문 전체는 개발 지시문으로 수신했다. 아래는 개발자가 참조하는 보존본이다.

## 0. 지금 수행할 일

즉시 구현하지 말고 **`PLAN·모호점`만** 제출한다. 현재 승인 범위는 읽기와 사실
조사까지다.

코드 수정 금지 · commit/push 금지 · OCI write·배포 금지 · Telegram 실발송 금지 ·
`PUSH_AUTOSEND_MARKET_BRIEFING_ENABLED=false` 유지 · 비밀값/`.env` 출력 금지.

모호점이 없으면 **`모호점 없음`** 이라고 명시한다.

## 1. 목표

```text
POC3 = IN_PROGRESS   OPERATIONAL_PUSH = 2_OF_3   CURRENT_STEP = POC3-OPS-02B-2
```

`OPS-02B-1` 확정 Gate — `OUTLOOK_RELATIONSHIP=ADOPT` · `OPERATING_RULE=SP500_SIGN_V1` ·
`OLS=RESEARCH_REFERENCE` · `SECTOR=NOT_EVALUATED` · `INDEX_LEADERSHIP=AVAILABLE` ·
`KOSPI_VIX_INTEGRITY=PASS`.

두 정보를 아침에 바로 읽히는 짧은 Telegram 메시지로 만들고, 반복·stale·불완전
데이터를 차단한 뒤 OCI 운영에 연결한다. **예상 개장 등락률을 산출하는 Step이
아니다.**

## 2. 범위

**포함** — 시장 브리핑 전용 evidence 조립 · Telegram 본문 · API↔CSV 일별 정합성 ·
API-only 신규 ticker 감지 · `CSV_REFRESH_REQUIRED` 산출 · 기초지수 블록
fail-closed · fingerprint·반복 억제 · 상태 파일·runner 연결 · mock/no-send/격리 ·
정상·차단·억제 경로 테스트와 역검증 · 문서 반영.

**제외** — 정적 CSV 자동 다운로드 · 신규 외부 source · 신규 API endpoint · 신규
DB·대규모 migration · 예상 개장 등락률 · OLS 운영 사용 · 섹터·테마 추론 ·
ETF명·기초지수명 의미 해석 · 신규 ML · `relative_upside_v0` 재사용 ·
`etf_daily_price.open/close` 수정 · 비차단 BACKLOG 본조사 · cron 시간 변경.

신규 dependency·DB·source 가 필요하면 구현하지 말고 근거와 대안을 PLAN 에 낸다.

## 3. 메시지 계약

### 3.1 형식

```text
[시장 흐름 브리핑] 08:00

오늘 한 문장
최근 S&P500 상승은 오늘 한국 개장에 상승 압력으로 해석됩니다.

오늘 볼 기초지수
• {공식 기초지수명}: 5일 {수익률} · 20일 {수익률} · 추종 ETF {n}개
• {공식 기초지수명}: 5일 {수익률} · 20일 {수익률} · 추종 ETF {n}개

근거
S&P500 {전일 변화} · Nasdaq {전일 변화} · 반도체지수 {전일 변화}

기준
미국 {실제 기준일} 종가 · 국내 {실제 기준일} 종가
```

### 3.2 방향 문구

`SP500_SIGN_V1` **만** 운영 규칙이다.

| 상태 | 문구 |
|---|---|
| `UP` | `최근 S&P500 상승은 오늘 한국 개장에 상승 압력으로 해석됩니다.` |
| `DOWN` | `최근 S&P500 하락은 오늘 한국 개장에 하락 압력으로 해석됩니다.` |
| `NONE` | 유효한 S&P500 방향을 산출하지 못한 상태 |

**`MIXED` 는 사용하지 않는다.** Nasdaq·반도체지수 방향이 달라도 상태를 `MIXED`
로 바꾸거나 가중치를 만들지 않는다. 두 지수는 **신선한 값이 있을 때만 수치
근거로 표시**하고, S&P500 전망을 결정·보정하지 않는다.

### 3.3 부분 산출

| Outlook | 기초지수 | 처리 |
|---|---|---|
| 사용 가능 | 후보 있음 | 전체 메시지 |
| 사용 가능 | **정상 산출** 결과 후보 0개 | 기초지수 문단 **완전 생략**, 전망만 발송 |
| 사용 가능 | 정합성·freshness 실패 | 기초지수 블록 제외하고 전망 발송 |
| 사용 불가 | 후보 있음 | 전망 숫자 없이 기초지수 중심 |
| 사용 불가 | 후보 없음 또는 블록 산출 불가 | **미발송** |
| 모든 데이터 stale | — | 미발송 · 실행 이력만 |

**정상 0개**와 **데이터 문제로 미산출**을 내부 상태에서 구분한다.

`CSV_REFRESH_REQUIRED` 는 Telegram 에 기술 상태명을 노출하지 않고 다음 문장만
쓸 수 있다.

```text
기초지수 정보는 공식 기준정보 갱신이 필요해 제외했습니다.
```

내부 상태·실행 결과에는 `CSV_REFRESH_REQUIRED` 를 정확히 남긴다.

### 3.4 표현 금지

예상 개장 등락률 숫자 · 매수/매도/교체 지시 · `상승 섹터`/`유망 테마` 등 임의
분류 · 확률·적중률을 오늘의 확정성처럼 표현 · unavailable 을 `0` 으로 표시 ·
기준일이 다른 값을 하나의 기준일로 표시 · 기존 `확인된 항목 / 별도 확인 필요`
목록 부활 · 기술 식별자·source key·param ID·경로·secret 노출.

메시지는 **한 개 Telegram 본문**으로 끝나야 한다. 임의 글자 수 기준을 만들지
말고, 모든 목업의 **실제 글자 수와 분할 수**를 결과에 제출한다. 최종 길이와
읽을 가치는 사용자가 판정한다.

## 4. 기초지수 계약

`OPS-02B-1` 검증 계약을 재사용하고 **새 순위 산식을 만들지 않는다.**

식별자 `지수산출기관 + 기초지수명` 완전일치 · 주식형만 · 레버리지·인버스 제외 ·
합성 제외 · 필터 후 **서로 다른 ETF ticker 2개 이상** · `n=1` 은 진단에만 ·
수익률은 **중앙값** · **5일·20일 모두 양수** · 20일 기준 **최대 2개** · 후보가
하나면 하나만 · 가격 기준일과 추종 ETF 수를 evidence 에 보존.

**동률 순서** — ① 20일 수익률 내림차순 ② 5일 수익률 내림차순 ③ 공식 식별자
오름차순.

표시명은 **공식 기초지수명 그대로**. 축약·번역·테마명 변환 금지.

## 5. API·CSV 정합성과 freshness

### 5.1 원천 역할

- **일별 KRX Open API**: ticker · 최신 기초지수명
- **versioned 공식 KRX CSV**: 지수산출기관 · 추적배수 · 복제방법 · 기초자산분류

CSV 를 수동 편집본·개발자 가공본으로 대체하지 않는다.

### 5.2 필수 차단

매일 API 기준으로 CSV 를 대조한다. 다음 중 하나라도 발생하면
**`CSV_REFRESH_REQUIRED`** 로 판정하고 **기초지수 블록 전체를 산출하지 않는다.**

- API 에는 있으나 CSV 에는 없는 **신규 ticker**
- 동일 ticker 의 **API 기초지수명 ≠ CSV 기초지수명**

**불일치 종목만 빼고 나머지로 만드는 fallback 은 허용하지 않는다.**

추가로 exact join coverage **95% 미만이면 원인과 무관하게 블록 전체 미산출**.

**API 조회 실패·빈 응답**은 CSV 불일치로 위장하지 말고 **별도의 조회 실패**로
기록한 뒤 fail-closed 처리한다.

CSV 기준일·hash·행 수 · API 행 수 · API-only ticker 수 · 지수명 불일치 수 ·
join coverage 를 실행 evidence 에 남긴다. **수치를 손으로 옮겨 적지 않는다.**

### 5.3 freshness

기존 `app/market_benchmark_freshness.py` 기준 재사용 · benchmark 마다 자기
`as_of_date` · 전역 기준일 덮어쓰기 금지 · stale 값은 문장·수익률·근거에서
제외 · 과거 행에 timestamp 소급 생성 금지 · **표시된 값의 실제 기준일만**
메시지 `기준` 에 사용.

미국과 국내 기준일이 다르면 **그대로 분리 표시**한다. 여러 항목의 기준일이
다르면 단일 날짜로 뭉개지 말고 실제 날짜가 드러나게 구성한다.

## 6. fingerprint 와 상태 저장

```text
state_fingerprint = "{outlook_state}#{index_leadership_state}"
outlook_state          = UP | DOWN | NONE
index_leadership_state = 표시 대상 공식 기초지수 식별자 집합을 정렬해 "|" 결합
                         후보 없음 또는 블록 미산출이면 NONE
```

수익률·ETF 수·기준일·미국지수 등락률 등 **매일 흔들리는 근거 숫자는 넣지
않는다.**

| 상황 | 처리 |
|---|---|
| 최초 유효 상태 또는 fingerprint 변경 | 발송 대상 |
| fingerprint 동일 | `no_change` 미발송 |
| 의미 있는 본문 없음 | 미발송 |
| 문장 생성 실패 | 미발송 |
| Telegram 실패 | 상태 불변 |
| Telegram 전체 성공 | **그 뒤에만** 상태 저장 |

상태 경로 `state/three_push/market_briefing_state_latest.json` · 다음 거래일에도
직전 발송 상태를 유지해 **일 단위 비교** · registry 중복키 **일 단위** ·
dry-run·mock·no-send·동일 상태·실패에서는 suppression state 미저장 · Telegram 이
여러 호출이면 **전체 성공 후에만** 저장 · **state write 실패를 Telegram 미발송으로
기록하지 말고** 발송 사실과 저장 실패를 분리 기록.

실행 history 는 성공 여부와 무관하게 기록할 수 있으나 **history 와 suppression
state 를 같은 것으로 취급하지 않는다.**

## 7. runner 와 실행 순서

`run_three_push_runtime_oci.py` 에 **본문 조립 책임을 추가하지 않는다.** 직전
실측 **637줄**이므로 helper 호출 **최소 배선만** 허용한다.

```text
외부 evidence 조회 → freshness·정합성 평가 → 후보 본문 조립
→ global/kind flag guard → stale·실패·no_change 등 최종 분기
→ Telegram 발송 → 전체 성공 후 registry·suppression state 저장
```

- **flag guard 전에 `stale`·`no_change`·`failed` 로 조기 반환하지 않는다.**
- dry-run 과 send mode 차이 유지.
- 실행 순서를 **추정하지 말고** PLAN 에서 현재 runner 의 실제 호출 경로와 변경 후
  경로를 **비교 제출**한다.
- 이 순서를 제거·변경하면 실패하는 **flow-through 테스트**를 둔다.

**국내 휴장일을 08:00 에 판정할 수 있는 기존 승인 경로가 있는지 PLAN 에서
확인**한다. 없으면 **신규 캘린더·source 를 임의 추가하지 말고 모호점으로 보고**한다.

## 8. 필수 테스트와 역검증

24개 계약(① S&P500 상승·하락 문구 ~ ㉔ 기존 보유 브리핑·급락 알림 회귀 없음)을
테스트한다. 원문 목록은 지시문 §8.

**역검증** — 실제 보호 분기를 먼저 특정 · 무력화 시 대응 테스트가 실제로 실패 ·
fixture 는 기본값과 결과가 우연히 같지 않게 · 대상 코드가 없으면 **SKIP 금지,
실패** · sender mock 으로 **발송 0건** · 외부 조회·live DB·live state 차단 ·
임시 state 경로 · 복원과 bytecode cache 제거 · **무력화 전 PASS / 무력화 후 FAIL /
복원 후 PASS** 제출.

테스트 **개수만 보고하지 말고** 각 테스트가 **어떤 계약과 실제 보호 분기**를
검증하는지 매핑한다.

## 9. 사용자 목업 Gate

구현·검증 후 **배포 전** 7종 목업을 사용자에게 제시한다 — ① 상승+지수2 ②
하락+지수1 ③ 전망만(정상 0개) ④ 전망 불가+지수만 ⑤ `CSV_REFRESH_REQUIRED` ⑥
전체 stale ⑦ 동일 fingerprint 미발송.

각 목업에 **실제 본문 · 글자 수 · 분할 수 · 사용 기준일 · 발송/미발송 사유 ·
저장 상태 변경 여부**를 함께 제출한다.

**사용자 승인 전에는 배포·autosend 활성화·실발송으로 넘어가지 않는다.**

## 10. PLAN 필수 반환 항목

**A** 현재 구현 사실 · **B** 변경 계획(표) · **C** 데이터 흐름 · **D** 상태
결정표 · **E** 테스트·역검증 계획 · **F** 모호점과 범위 영향. 상세는 지시문 §10.

## 11. PLAN 승인 이후 결과 보고

변경 파일·최종 줄 수 · 계약별 구현 위치 · 테스트와 전체 회귀 · 보호 로직별
역검증 · 목업 7종 · 외부 조회/DB write/state write/Telegram 발송 실적 · autosend
가 여전히 `false` 임을 확인한 결과 · 알려진 한계와 BACKLOG 비승격 근거 ·
commit/push/OCI 배포 수행 여부.

**별도 사용자 승인 없이는 commit·push·OCI 배포·autosend 활성화·실발송을 수행하지
않는다.**

## 12. 완료 기준

지시문 §12 전 항목. **구현·테스트가 끝나도 즉시 `PUSH 3_OF_3` 또는 POC3 완료로
기록하지 않는다.** 실제 OCI 배포 · 08:00 수신 · 기준일·길이·읽을 가치 확인 ·
같은 상태 반복 억제까지 확인된 뒤에만 운영 상태로 격상하며, **POC3 Closeout 은
별도로 수행**한다.
