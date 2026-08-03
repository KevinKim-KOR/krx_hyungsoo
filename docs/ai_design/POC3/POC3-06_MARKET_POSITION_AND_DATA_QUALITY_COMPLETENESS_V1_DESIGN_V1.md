# 투자모델_v2 — POC3-06 Market Position & Data Quality Completeness v1 설계서

- 작성일: `20260803`
- 문서 번호: `POC3-06`
- 문서 상태: `설계 초안 / 레드팀 검수 전`
- 문서 성격: 설계서
- 선행 상태: `POC3-05 VERIFIED · PASS · CLOSED`
- 적용 대상: `오늘의 투자 점검`, `market_briefing`, `holdings_briefing`, 관련 자료 상태

---

## 0. 설계 결론

이번 Step의 결과물은 새 상세 화면이 아니다.

POC3-05에서 완성한 보유 ETF 확인 근거와 이번 Step에서 완성할 시장 위치·자료 상태를 **공통 판단 요약**으로 만들고, 사용자가 매일 접하는 다음 두 곳에서 바로 쓰이게 한다.

1. PC 첫 화면 `오늘의 투자 점검`
2. 기존 Telegram PUSH의 `market_briefing`과 `holdings_briefing`

세부 화면은 전체 수치와 원인을 확인하는 근거 보관소 역할을 유지한다. 핵심 정보가 세부 화면에만 있고 첫 화면과 PUSH에 연결되지 않으면 이번 Step은 완료가 아니다.

기존 3종 PUSH의 종류와 운영 경계는 유지한다.

- `market_briefing`: 시장 위치와 장 흐름 요약
- `holdings_briefing`: 보유 ETF 중 먼저 확인할 항목과 이유
- `spike_or_falling_alert`: 기존 급등락 조건형 알림

전체 PUSH 횟수를 하루 3회로 고정하지 않는다. 각 PUSH의 실행·발송 정책, 승인 흐름, OCI 전달 방식은 변경하지 않는다.

---

## 1. 현재 문제

POC3-01에서 `오늘의 투자 점검`이 만들어졌고 POC3-05에서 보유 ETF의 평가·최근 흐름·KODEX200 대비·자료 상태를 확인할 수 있게 됐다.

그러나 다음 결함이 남아 있다.

1. 기존 시장 판정의 흐름 지속 기간, KOSPI 최근 고점 대비 위치, 일간 수익률, 1년 수익률이 실제 값으로 완성되지 않았다.
2. VIX가 오래된 경우에도 시장 판단에 포함해도 되는지 즉시 알기 어렵다.
3. POC3-05의 보유 ETF 확인 근거가 세부 화면에서는 유용하지만 PUSH와 같은 기준으로 연결됐다는 보장이 없다.
4. Dashboard와 PUSH가 각각 계산·정렬하면 같은 날 서로 다른 종목·수치·기준일을 보여줄 수 있다.
5. 사용자가 세부 화면의 정보를 다시 조립해야 하므로 기능이 일상 운영으로 모이지 않는다.

이는 미관 문제가 아니라 POC3의 `상태 → 비교·판단 → 실행` 흐름을 막는 사용 결함이다.

---

## 2. 이번 Step의 단일 목표

> POC3-05의 보유 ETF 확인 근거와 기존 시장 시계열·자료 상태를 하나의 공통 판단 요약으로 만들고, 같은 근거와 기준일을 `오늘의 투자 점검`과 기존 PUSH에서 바로 활용하게 한다.

시스템은 계산 가능한 관찰값과 자료 상태를 제공하고, 사용자가 최종 판단한다. 새로운 투자 판단 알고리즘은 만들지 않는다.

완료 후 사용자는 다음을 할 수 있어야 한다.

- PC 첫 화면에서 10초 안에 시장 위치, 먼저 확인할 보유 ETF, 판단에 영향을 주는 자료 문제를 구분한다.
- `market_briefing` 첫 부분에서 시장 위치와 기준일을 확인한다.
- `holdings_briefing` 첫 부분에서 먼저 확인할 보유 ETF 최대 3건과 이유를 확인한다.
- 전체 수치가 필요할 때만 `확인 근거` 또는 `데이터 상태`로 이동한다.

---

## 3. 선행 설계와의 관계

### 3.1 POC3-05는 다시 열지 않는다

다음 POC3-05 결과를 완료된 입력으로 사용한다.

- `보유 현황 / 종목 관리 / 확인 근거 / 데이터 상태` 화면 분리
- ticker별 평가액·평가 비중·평가손익
- 최근 5일·20일 수익률
- KODEX200 대비 20일 초과수익
- `자료 확인 필요` 의미
- 중복 ticker 통합 의미
- Dashboard 최대 3건 요약 규칙

이번 Step은 위 계산과 화면을 재설계하지 않고 Dashboard와 PUSH의 공통 입력으로 연결한다.

### 3.2 POC3-01의 미완성 항목 처리

다음 `개발 중` 항목은 이번 Step에서 실제 값으로 교체한다.

- 시장 판정 흐름 지속 거래일 수
- 최근 1년 고점 대비 위치
- KOSPI 일간 수익률
- KOSPI 1년 수익률

다음 미도입 항목은 이번 Step에서도 개발하지 않으며 매일 보는 주 화면의 미완성 기능 목록에서도 제거한다.

- 거래량 흐름
- 공격·방어 비중
- SuperTrend

보류·제외 이력은 통합지도와 BACKLOG에서 관리한다. `오늘의 투자 점검`을 프로젝트 할 일 목록으로 사용하지 않는다.

### 3.3 POC3-06 명칭

통합지도의 `Market Position & Data Quality Completeness v1` 명칭을 유지한다.

여기서 `Completeness`는 세부 화면에 값을 채우는 데서 끝나지 않고, 완성된 값이 Dashboard와 PUSH에서 실제 사용되는 상태까지를 의미한다.

---

## 4. 유지할 계약

1. `오늘의 투자 점검`이 PC 첫 진입 화면인 구조
2. KOSPI는 사용자 대표 시장, KODEX200은 기존 내부 비교·시장 판정 기준이라는 구분
3. POC3-05의 보유 평가·최근 흐름·자료 상태 의미
4. `Run → PENDING_APPROVAL → 승인 → OCI → Telegram` 흐름
5. `message_text`는 backend 또는 OCI runtime builder가 만들고 frontend는 조립하지 않는 원칙
6. `market_briefing / holdings_briefing / spike_or_falling_alert` 식별자
7. 기존 PARAM·scheduler·sent registry·중복 발송 차단 계약
8. 평가 실행 횟수와 사용자 알림 횟수를 구분하는 운영 원칙
9. 인간 최종 승인 원칙
10. BUY·SELL·교체·비중 조절·자동 주문 금지

---

## 5. 다시 조사하지 않는 확정 사실과 A구간 확인

### 5.1 확정 사실

1. KOSPI close는 기존 SQLite `market_benchmark_daily_price`에 장기간 저장돼 있다.
2. POC3-01에서 기존 `GET /market/price-series`를 확장한 KOSPI read 경로와 차트가 구현됐다.
3. 현재 시장 판정 라벨과 MA20·MA60 비교 의미는 KODEX200 기준이다.
4. KODEX200 판정을 KOSPI 판정으로 이름만 바꾸면 안 된다.
5. VIX는 기존 SQLite·read·독립 갱신 경로가 있으나 과거 실측에서 KOSPI보다 오래된 상태가 확인됐다.
6. `GET /holdings/market-evidence/latest`는 POC3-05에 필요한 ticker별 evidence를 한 번에 제공한다.
7. POC3-05 Dashboard 요약은 중복 ticker 제거 후 최대 3건이며, 5일 유효값 오름차순이다.
8. unavailable 항목은 최근 흐름 순위에 넣지 않고 `자료 확인 필요`로 분리한다.
9. PUSH는 `pc_evidence_snapshot → runtime_snapshot → push_context → message_text` 흐름을 사용한다.
10. `spike_or_falling_alert`용 안정적인 급락 latest read 계약은 아직 없다.

### 5.2 개발 PLAN 전 확인 범위

개발자는 전체 저장소를 다시 조사하지 않고 다음 직접 경로만 확인한다.

| 확인 대상 | 확인할 사실 |
|---|---|
| KOSPI read | 최신 기준일, 1년 구간 행 수, 직전 거래일 조회 가능 여부 |
| 기존 시장 판정 | 동일 규칙으로 과거 KODEX200 라벨을 재현해 현재 라벨 지속일을 계산할 수 있는지 |
| POC3-05 요약 | 최대 3건 선택의 현재 위치와 server-side 재사용 경로 |
| PUSH package | 두 PUSH의 evidence snapshot과 message builder 직접 경로 |
| 자료 상태 | KOSPI·KODEX200·VIX·Holdings·Market Evidence의 status·기준일 원천 |
| VIX | 기존 갱신 경로의 연결 가능 여부와 stale 원인 |
| 이동 | Dashboard의 `확인 근거`·`데이터 상태` 도착 key 정합성 |

확정 사실과 실제 코드가 충돌하거나 공통 요약에 신규 source·endpoint·저장 체계가 필요하면 구현하지 않고 설계자에게 복귀한다.

---

## 6. 공통 판단 요약 계약

### 6.1 단일 계산 원칙

Dashboard와 PUSH는 화면별로 값을 다시 계산하거나 서로 다른 정렬을 사용하지 않는다.

backend의 동일한 요약 결과를 PC read 응답과 PUSH package가 함께 사용한다. 표현 길이는 달라도 값·단위·ticker 선택·상태 의미·기준일·제외 사유는 같아야 한다.

### 6.2 시장 위치

| 표시 | 의미 |
|---|---|
| KOSPI 기준일 | 최신 유효 KOSPI close 날짜 |
| KOSPI 일간 수익률 | 최신 close와 직전 유효 거래일 close의 단순 수익률 |
| KOSPI 1년 수익률 | 최신 기준일과 1년 전 기준일에 가장 가까운 이전 유효 거래일 close의 단순 수익률 |
| 최근 1년 고점 대비 | 최신 기준일 직전 1년 구간의 최고 close 대비 현재 close 비율 |
| 기존 시장 판정 | 현재 KODEX200 기준 시장 판정 라벨 |
| 판정 지속 거래일 | 동일한 기존 판정 규칙으로 재현한 현재 라벨의 연속 거래일 수 |
| MA20·MA60 대비 | 기존 KODEX200 기준선 거리 |

달력 전일을 거래일로 간주하지 않는다. 1년 이력이 부족하면 계산 불가 상태를 유지한다. 화면에는 모호한 `최근 고점` 대신 `최근 1년 고점`이라고 표시한다.

KOSPI와 KODEX200 기준을 섞지 않는다.

허용:

> KOSPI는 최근 1년 고점 대비 -○○%입니다. 기존 시장 판정은 KODEX200 기준 ○○ 흐름 ○거래일째입니다.

금지:

> KOSPI 상승장 ○거래일째

### 6.3 보유 ETF 요약

POC3-05 규칙을 그대로 사용한다.

- `status=ok`이고 5일 값이 유효한 ticker만 최근 흐름 정렬 대상
- `return_5d_pct` 오름차순, 동률은 ticker 오름차순
- 중복 ticker 제거 후 최대 3건
- 평가 비중·평가손익·5일·20일·KODEX200 대비 20일을 핵심 근거로 사용
- unavailable은 최근 흐름 순위와 분리해 `자료 확인 필요`로 표시
- `topn_match`, 안정적 GET 계약이 없는 급락 후보는 제외

이 순서는 표시 우선순위일 뿐 위험 점수·매도 순위·저장 rank가 아니다.

### 6.4 자료 상태와 snapshot

자료 상태를 하나의 종합 위험 등급으로 합치지 않는다. 자료별 status·실제 기준일·사용 여부·제외 사유를 유지한다.

`0건`, `최신`, `정상`은 read가 성공하고 기존 계약 기준으로 확인된 경우에만 표시한다.

Dashboard는 현재 read 결과를 표시한다. PUSH 생성 시 사용한 요약은 `pc_evidence_snapshot`에 보존한다. 이후 Dashboard가 갱신돼 PUSH와 기준일이 달라질 수 있으며, 양쪽 기준일을 숨기지 않는다.

---

## 7. 출력 화면 계약

### 7.1 `오늘의 투자 점검`

최상단 KOSPI 영역에는 다음을 한 흐름으로 배치한다.

- KOSPI 일간·1년 수익률
- 최근 1년 고점 대비 위치
- KODEX200 기준 기존 시장 판정과 지속 거래일
- KODEX200 MA20·MA60 대비
- 각 기준일

상단에는 공통 요약 한 문장을 먼저 보여주고 수치는 그 근거로 둔다. 작은 카드 여러 개를 나열해 사용자가 다시 문장을 만들게 하지 않는다.

`내가 가진 ETF 중 확인할 종목`에는 공통 요약의 최대 3건, 한 줄 이유, 핵심 수치, `확인 근거 보기`를 제공한다.

자료 불완전 종목은 최근 흐름 순위와 섞지 않고 `자료 확인 필요` 건수와 이유로 분리한다.

KOSPI·KODEX200·VIX·Holdings·Market Evidence 중 판단에 영향을 주는 문제만 `자료 업데이트 필요`에 표시하고 `데이터 상태` 또는 기존 업데이트 화면으로 연결한다.

전체 종목표·개별 차트·NAV·구성종목·중복률은 Dashboard에 복제하지 않는다.

### 7.2 `market_briefing`

본문 선두에 다음을 반영한다.

- KOSPI 일간·1년 수익률
- 최근 1년 고점 대비 위치
- KODEX200 기준 기존 시장 판정과 지속 거래일
- KOSPI·KODEX200 기준일

기존 Market Discovery·미국 시장 runtime 관찰은 유지하되 시장 위치 요약보다 먼저 길게 나오지 않게 한다.

VIX를 실제 해석에 사용했다면 기준일을 표시한다. 사용하지 않았다면 정상 값처럼 문장에 포함하지 않는다.

### 7.3 `holdings_briefing`

본문 선두에 Dashboard와 동일한 `오늘 확인할 보유 ETF`를 제공한다.

- 동일 ticker 최대 3건
- 동일 순서
- 실제 제공 가능한 평가 비중·평가손익·5일·20일·KODEX200 대비
- Holdings 기준일과 Market Evidence 기준일
- `자료 확인 필요`가 있으면 정상 종목과 분리한 제한 문장

전체 보유 종목의 긴 표를 PUSH의 핵심 본문으로 반복하지 않는다. 전체 목록과 상세 근거는 PC `확인 근거`가 담당한다.

### 7.4 `spike_or_falling_alert`

이번 Step에서 선정·임계값·본문·발송 조건을 변경하지 않는다.

급락 latest 정보를 보유 요약에 억지로 연결하지 않으며 입력 미확인을 `급등락 없음` 또는 `0건`으로 바꾸지 않는 기존 안전 계약만 유지한다.

---

## 8. VIX 처리

VIX는 다음 둘 중 하나로 닫아야 한다.

1. 기존 FDR·SQLite·갱신 경로로 정상화하고 실제 기준일을 Dashboard와 사용한 PUSH에 표시
2. 신뢰할 수 없으면 시장 요약과 PUSH 해석에서 제외하고 `자료 업데이트 필요`에 실제 기준일과 제외 이유 표시

VIX 부재가 사용 가능한 KOSPI·KODEX200·Holdings 근거까지 막지는 않는다.

금지:

- 신규 VIX source·Cboe scraping·수동 CSV·API key
- 새 stale 일수 threshold
- 오래된 VIX를 최신값처럼 사용
- VIX만으로 시장 위험 라벨 생성

정상화와 제외 중 어느 쪽을 택할지는 A구간 실측 결과로 결정한다.

---

## 9. 변경 범위와 금지사항

### 9.1 허용

- 기존 KOSPI·KODEX200·VIX·Holdings 저장값 read
- §6.2의 단순 관찰값 계산
- 기존 시장 판정 규칙의 동일 적용을 통한 지속일 계산
- 기존 read 응답과 `pc_evidence_snapshot`의 additive 확장
- Dashboard와 PUSH가 함께 사용하는 server-side summary composer
- 기존 status·기준일·unavailable 사유 전달
- `market_briefing`·`holdings_briefing` 요약 문구 재구성

### 9.2 금지

- 신규 endpoint·DB·table·cache·history 저장소
- 신규 외부 source·proxy
- 새로운 시장 국면 알고리즘·위험 점수·등급·threshold
- frontend 전용 파생 산식
- Dashboard용과 PUSH용 별도 계산
- 요약 결과의 signal·rank 저장
- 신규 메뉴·화면·route
- 기존 상세 화면 재설계와 그리드 전면 개선
- 거래량·공격방어·SuperTrend
- 급락 latest read 계약 신설
- Market Discovery·Holdings·NAV·구성종목 계산 변경
- ML·백테스트·튜닝
- BUY·SELL·손절·교체·자동 비중·주문
- PUSH 종류·스케줄·승인·OCI·중복 차단 변경
- 모바일 UI

### 9.3 사용자 표현

사용자 화면과 Telegram에는 `Evidence`, `stale`, `unavailable`, `push_context`, `snapshot`, `regime`을 노출하지 않는다.

`확인 근거`, `업데이트 필요`, `자료 없음`, `기존 시장 판정`, `기준일`, `확인할 종목`으로 표현한다.

결측·실패를 `-`, `0`, `정상`, `문제없음`으로 메우지 않는다.

---

## 10. 구현 게이트

1. **A구간:** §5.2 직접 경로 확인과 PLAN 확정
2. **B구간:** 공통 시장·보유 요약과 자료 상태 완성
3. **C구간:** `오늘의 투자 점검` 연결 및 사용자 10초 과업 확인
4. **D구간:** 두 PUSH preview 연결, Dashboard와 값·ticker·기준일 대조
5. **E구간:** 사용자 명시 승인 후 `market_briefing`·`holdings_briefing` 각 1회 실제 수신 확인

C구간 사용자 실화면 확인 전 D로 전진하지 않는다. Preview가 Dashboard와 다르면 어느 한쪽을 임의 정답으로 두지 않고 공통 요약 경로를 수정한다.

실제 수신 승인이 없거나 preview와 Telegram `message_text`가 다르면 `PASS / CLOSED`로 판정하지 않는다. `spike_or_falling_alert` 실제 발송은 이번 검증 대상이 아니다.

---

## 11. 설계자 복귀 조건

다음 중 하나라도 확인되면 개발자가 임의로 결정하지 않는다.

1. 기존 KOSPI read로 1년 관찰값을 만들 수 없다.
2. 새 추세 규칙을 만들어야 판정 지속일을 계산할 수 있다.
3. 공통 요약에 신규 endpoint·DB·source가 필요하다.
4. POC3-05 최대 3건 재사용에 새 순위·위험 점수 저장이 필요하다.
5. VIX 판정에 새 stale threshold가 필요하다.
6. 기존 package의 additive 확장만으로 PUSH 사용값을 보존할 수 없다.
7. PUSH 개선에 승인·OCI·scheduler·중복 차단 변경이 필요하다.
8. 같은 기준일의 Dashboard와 PUSH가 서로 다른 값이나 ticker를 반환한다.
9. KOSPI와 KODEX200 기준을 사용자 화면에서 분리할 수 없다.
10. `spike_or_falling_alert` 선정·발송 조건이 달라진다.

동일 계약 안의 함수명·helper·컴포넌트 분리·additive 필드 배치는 개발자가 판단한다.

---

## 12. 완료 기준 AC

| AC | 완료 조건 |
|---|---|
| AC-1 | POC3-05의 PASS 상태와 보유 화면·계산 계약이 유지된다. |
| AC-2 | Dashboard와 PUSH가 동일한 server-side 시장·보유 요약을 사용하며 화면별 중복 계산이 없다. |
| AC-3 | 실제 KOSPI 일간·1년 수익률, 최근 1년 고점 대비 위치, 기준일을 확인할 수 있다. |
| AC-4 | KODEX200 기준 기존 시장 판정과 동일 라벨 지속 거래일을 확인할 수 있고 KOSPI 판정으로 오표기되지 않는다. |
| AC-5 | MA20·MA60 대비가 미래 예측이나 시장 전환 확정으로 표현되지 않는다. |
| AC-6 | Dashboard와 `holdings_briefing`이 POC3-05와 동일한 최대 3건을 같은 순서로 보여준다. |
| AC-7 | 같은 ticker·기준일의 평가 비중·손익·5일·20일·KODEX200 대비 값이 `확인 근거`, Dashboard, PUSH preview에서 일치한다. |
| AC-8 | partial·unavailable·not_loaded가 최근 흐름 순위와 섞이지 않고 `자료 확인 필요`로 분리된다. |
| AC-9 | 실패·결측·오래된 값이 0건·정상·최신으로 표시되지 않으며 실제 기준일을 숨기지 않는다. |
| AC-10 | VIX가 기존 경로로 정상화되거나 Dashboard·PUSH 해석에서 명시적으로 제외된다. |
| AC-11 | 실제 첫 화면에서 사용자가 10초 안에 시장 위치, 확인할 보유 ETF, 자료 문제를 구분한다. |
| AC-12 | Dashboard에 전체 종목표·차트·NAV·구성종목·중복률이 중복되지 않고 상세 이동이 동작한다. |
| AC-13 | 완료 항목은 `개발 중`에 남지 않고 거래량·공격방어·SuperTrend가 주 화면을 차지하지 않는다. |
| AC-14 | `market_briefing` preview와 실제 수신 선두에 시장 위치 요약·기준일이 반영된다. |
| AC-15 | `holdings_briefing` preview와 실제 수신 선두에 동일 보유 ETF 최대 3건·이유·기준일이 반영된다. |
| AC-16 | PUSH preview와 Telegram이 저장된 동일 `message_text`를 사용하며 frontend 본문 조립이 없다. |
| AC-17 | PUSH 종류·스케줄·승인·OCI·중복 차단·sent registry 의미가 변경되지 않는다. |
| AC-18 | BUY·SELL·매수·매도·교체·손절·자동 비중·주문 지시가 없다. |
| AC-19 | 신규 endpoint·DB·source·시장 알고리즘·위험 score·threshold·저장 rank가 0건이다. |
| AC-20 | 사용자가 실제 Dashboard와 두 PUSH 수신 결과를 확인해 PASS한다. |

AC-1~20 중 하나라도 충족하지 않으면 `PASS / CLOSED`로 판정하지 않는다.

---

## 13. BACKLOG 유지

### 13.1 급락 후보 latest read 계약

이 항목은 이번 Step에 넣으면 신규 API·저장 계약으로 범위가 커지므로 BACKLOG로 유지한다.

- 보류 사유: 자동 조회 가능한 안정적 GET 계약 부재
- 보류된 위험: 보유 ETF와 급락 후보의 일치 여부를 Dashboard·holdings PUSH에서 확인할 수 없음
- 재검토 트리거: 안정적 latest 저장·read 계약과 반복 운영 필요성이 함께 확인될 때

### 13.2 거래량 흐름

이 항목은 신규 데이터 source·저장 계약이 필요하므로 BACKLOG로 유지한다.

- 보류 사유: 현재 KOSPI·KODEX200 저장 계약에 거래량이 없음
- 보류된 위험: 가격 흐름만으로 시장 강도를 해석하는 한계
- 재검토 트리거: 기존 source의 안정적 거래량 계약과 판단 가치가 함께 확인될 때

### 13.3 VIX 보조 source

이 항목은 신규 외부 source로 범위가 커지므로 기존 BACKLOG를 유지한다.

- 보류 사유: 현재 FDR 단일 경로 유지
- 보류된 위험: FDR 실패가 장기화되면 VIX를 계속 제외해야 함
- 재검토 트리거: FDR VIX 반복 실패가 운영에서 확인될 때

### 13.4 그리드 디자인 전면 개선

이 항목은 이번 Step의 판단 요약 연결과 무관하므로 BACKLOG로 유지한다.

- 보류 사유: 현재 핵심 과업을 막는 결함으로 판정되지 않음
- 보류된 위험: 상세 표의 시각적 완성도가 낮게 느껴질 수 있음
- 재검토 트리거: 실제 화면에서 핵심 수치 판독 실패가 확인될 때

---

## 14. Closeout

PASS 후 POC3-06 RESULT·CLOSEOUT, 두 STATE_LATEST, POC3 통합지도를 갱신한다. 새 보류 항목이 생긴 경우에만 BACKLOG를 갱신한다.

과거 POC3-01·POC3-05 문서는 이력으로 보존한다.

세부 화면에만 값이 추가되거나 PUSH preview까지만 확인된 상태는 `PARTIAL`이다.

POC3-06이 `PASS / CLOSED`가 되기 전에는 POC3-07 PC Judgment Flow Closeout으로 전진하지 않는다.
