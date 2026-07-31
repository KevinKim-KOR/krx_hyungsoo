# 투자모델_v2 — POC3 통합 구현지도 V2

- 작성일: 2026-07-31 (레드팀 PASS 초안) / **canonical 등록 2026-08-01 (POC3-REF-02 Canonical Alignment Application)**
- 문서 성격: 남은 개발 전수 귀속·5분류·예상 Lane 지도. **현재 항목 귀속·5분류·예상 Lane 의 계획 권한을 이어받는 최신 canonical 구현지도.**
- 입력 범위: 제공된 `docs(1).zip` 108개 파일 전수
- 입력 스냅샷: ZIP SHA256 `ef7df7f41e92ccda29bc952892266f71bf87e6b4d92833a250480b15edd7f492`
- 문서 트리 해시: `968f41764f97e9dae0bd7d2bb4e2a4bb0df6ddde2dbffb12793cc67d49c7da3f`
- 현재 판정: **canonical 등록 완료 · POC3-REF-02 = CANONICAL_APPLICATION_AWAITING_VERIFICATION (검증자 판정 대기).**

> **문서 관계 (설계자 확정 2026-08-01)**: 본 V2 는 기존 마스터 `docs/handoff/POC3/POC3_PC_JUDGMENT_UI_RECOMPOSITION_MASTER_DESIGN_V1.md` 를 **삭제·파일 교체하지 않는다.** V1 은 UI 재조합의 초기 상위 설계 이력으로 보존(`SUPERSEDED_FOR_CURRENT_PLANNING`)되고, 본 V2 가 현재 항목 귀속·5분류·다음 Lane 의 계획 권한을 이어받는다. 최신 Step 상태는 `docs/STATE_LATEST.md` 우선.
>
> **canonical 등록 정정 (2026-08-01 · 실제 저장소 대조 반영)**:
> - POC3-01 사용자 실화면 PASS 날짜 = **2026-08-01** (commit `31428ce1`, VERIFIED). §2 S-03 표기의 "2026-07-31 사용자 최신 보고" 는 이 날짜로 대체.
> - POC3-REF-02 상태 = **`CANONICAL_APPLICATION_AWAITING_VERIFICATION`**. 검증자 PASS 전까지 `PASS / CLOSED` 로 기록하지 않는다.
> - POC3-03 = 다음 Step 으로 예정하되 **POC3-REF-02 검증 PASS 전 진입 금지.**

---

## 0. 결론

현재 다음 실제 개발 Step은 아래 하나로 고정한다.

> **POC3-03 Navigation Information Architecture v1 — 좌측 메뉴 1차 재편**

단일 목표는 기존 화면과 route key를 유지한 채, 좌측 메뉴를 사용자의 실제 과업 순서에 맞는 그룹과 진입 구조로 재배치하는 것이다. 신규 API·DB·산식·source·화면 기능은 추가하지 않는다.

이 판단의 근거는 다음과 같다.

1. `오늘의 투자 점검`과 `Judgment Workbench`는 실제 완료됐다.
2. 현재 사용자가 매일 통과하는 진입로가 평면적이고, 과거 사용자가 메뉴 구조를 사용할 수 없다고 판정한 문제가 남아 있다.
3. 친구 프로젝트 조사에서 채택 가치가 확인된 것은 19개 메뉴 자체가 아니라 **과업별 그룹핑과 평면 route를 분리하는 정보구조 방식**이다.
4. Operations Panel을 추가하기 전에 진입 구조를 고정해야 새 실행 화면이 또 하나의 고아 메뉴가 되지 않는다.

개발자가 기존 미구현·BACKLOG·친구 참고요소의 개발 여부와 순서를 결정하지 않는다. 개발자는 이후 설계서가 요구하는 소스 사실만 확인하며, 귀속·분류·순서는 설계자가 판정한다.

---

## 1. 이 지도의 구속력

이 지도에서 구속력을 갖는 것은 두 가지다.

1. 모든 항목의 귀속 — 고아 항목 0건
2. 각 항목의 5분류

장기 순서는 현재 시점의 예상이다. **다음 실제 Step 하나만 확정**하며, 각 Step 종료 후 사용자 실화면·운영 판정으로 그다음 하나를 다시 확정한다. 이 원칙은 KS-8의 자물쇠 놀이와 낡은 장기 로드맵 재생산을 막기 위한 것이다.

### 1.1 5분류

| 분류 | 의미 |
|---|---|
| 완료 | 이미 구현·검증됐거나 최신 결정으로 해소됨. 다시 개발하지 않음 |
| 확정 개발 | POC3 완주에 필수. 예상 Lane과 선행조건을 지정 |
| 후속 개발 | 프로젝트 목적상 개발할 항목이지만 POC3 이후 또는 선행조건 이후 진행 |
| 조건부 보류 | 문서에 적힌 재검토 트리거가 실제 발생하기 전에는 개발하지 않음 |
| 제외·폐기 | 프로젝트 경계와 맞지 않거나 다른 구조로 대체됨. 개발하지 않음 |

### 1.2 운영에서 새 항목이 들어오는 경로

다음 입력은 각 Step 종료 시 지도에 등재하고 5분류를 다시 판정한다.

- 사용자 실화면에서 확인된 차단 결함
- First Real Decision Cycle과 AI Sessions에서 확인된 `필요했는데 없던 정보`
- Decision Outcome Ledger 구현 이후 원장에서 확인된 누락 evidence
- Telegram·OCI 실제 운영 실패와 stale 보고

운영에서 나온 누락 정보는 단순 아이디어보다 우선 검토한다. 단, 사용자 경험 하나만으로 factor·threshold·label을 즉시 확정하지 않는다.

---

## 2. 최신 실제 상태와 STALE 문서 정리

| ID | 항목 | 실제 상태 | 문서 상태·처리 |
|---|---|---|---|
| S-01 | POC3-01 초기 PC Status Dashboard + remediation | 완료 | 과거 이력. 재개발 금지 |
| S-02 | POC3-02 Judgment Workbench | **PASS / CLOSED** · 검증자 확인·1440×900 브라우저 확인 완료 · commit `c2b7df13` | `STATE_LATEST`·handoff의 `IMPLEMENTED_AWAITING_VERIFICATION`은 STALE |
| S-03 | POC3-01 오늘의 투자 점검 대시보드 전면 개편 | **COMPLETED / VERIFIED / 사용자 실화면 확인 완료 (2026-08-01)** · commit `31428ce1` | 결과서 AC-15·STATE의 대기 표기는 2026-08-01 사용자 실화면 PASS 로 대체됨(반영 완료) |
| S-04 | POC3-REF-01 친구 프로젝트 소스 사실 조사 | **VERIFIED / CLOSED** · commit `16d56702` push 완료 | 최신 결과서 표기와 일치 |
| S-05 | First Real Decision Cycle v1 | 운영 관찰 활성 · formal PASS 근거 없음 | Decision Outcome Ledger 선행 진입 금지 유지 |
| S-06 | BACKLOG 항목 수 | 현재 105개 | 감사 당시 91개 표기는 STALE. 이후 14개 추가 반영 필요 |
| S-07 | `docs/handoff/STATE_LATEST.md` | 비정규 pointer 문서 | redirect 외 Step 본문을 제거하고 canonical `docs/STATE_LATEST.md`만 갱신해야 함 |
| S-08 | POC3 번호 충돌 | 과거 문서명은 이력으로 유지 | 새 Step은 `POC3-03`부터 신규 순번으로 진행하고 `POC3-01/02`를 다시 쓰지 않음 |

최신 사용자·검증 결과보다 오래된 문서 상태를 우선하지 않는다. 과거 conclusion과 handoff는 역사적 증거로 유지하되, 현재 gate 판정에는 사용하지 않는다.

---

## 3. POC3 핵심 구현 항목 전수 귀속

| ID | 항목 | 판정 | 귀속·선행조건 |
|---|---|---|---|
| P-01 | 초기 상태 Dashboard | 완료 | 재개발 금지 |
| P-02 | Judgment Workbench + 선택 가격 차트 | 완료 | benchmark 차트는 P-16으로 분리 |
| P-03 | 오늘의 투자 점검 대시보드 | 완료 | 결과서·STATE 문서 상태만 정정 |
| P-04 | 좌측 메뉴 과업별 1차 재편 | **확정 개발** | **다음 Step POC3-03**. route·기능·API 불변 |
| P-05 | Operations Panel 통합 | 확정 개발 | POC3-03 PASS 이후 예상. 판단 초안/승인, OCI, 정보 PUSH를 역할별 분리 |
| P-06 | 내가 가진 ETF의 위험 신호와 구체 이유 | 확정 개발 | P-05 이후 별도 evidence foundation. Q6 산식 선확정 금지 |
| P-07 | 코스피 흐름 지속 거래일 수 | 확정 개발 | 기존 시계열·기존 국면 계약으로 제공 가능한지 사실 확인 후 |
| P-08 | 최근 고점 대비 현재 위치 | 확정 개발 | 기존 KOSPI 시계열 재사용 가능성 확인 후 |
| P-09 | 코스피 일간·1년 수익률 | 확정 개발 | 시장 위치 evidence 보완 Lane. 임시 숫자 금지 |
| P-10 | 거래량 흐름 | 조건부 보류 | 저장 데이터와 판단 가치가 모두 확인될 때. 새 source 선도입 금지 |
| P-11 | 기존 판정 기준선까지 거리 | 완료 | MA20/MA60 기반·한계 툴팁 포함 |
| P-12 | 공격·방어 비중 | 제외·폐기 | 친구 구조 복제이며 자동 비중 판단 경계를 침범 |
| P-13 | SuperTrend 신규 도입 | 제외·폐기 | 신규 산식·threshold 선확정 금지 |
| P-14 | 자료 최신화 판정 기준·ⓘ 근거 표준 | 확정 개발 | VIX/data quality Lane에서 기존 상태계약 기준으로 확정 |
| P-15 | VIX stale 결함 | 확정 개발 | POC3 Closeout 전 적재 정상화 또는 현재 판단 영역 제외 중 하나를 별도 Step에서 판정 |
| P-16 | Workbench benchmark 비교 시계열 | 조건부 보류 | 표의 기존 초과수익만으로 실제 판단이 막힌다는 사용자 보고 시 |
| P-17 | Dashboard 캐시 무효화 실제 컴포넌트 통합 테스트 | 확정 개발 | POC3 Flow Closeout에 포함. 신규 기능 아님 |
| P-18 | 상태→판정→실행 전체 동선 Closeout | 확정 개발 | P-04, P-05 및 Closeout 필수 데이터 결함 처리 후 |
| P-19 | Decision Outcome Ledger | 후속 개발 | First Real Decision Cycle formal PASS와 실제 판단 1건 기록 후 |
| P-20 | ML·백테스트·튜닝 | 후속 개발 | P-19 이후. factor·label·threshold는 해당 Step에서만 확정 |

---

## 4. 예상 Lane 지도

다음 Step 하나만 확정하며 아래 순서는 예상이다.

| 예상 Lane | 목표 | 상태 |
|---|---|---|
| POC3-03 | Navigation Information Architecture v1 | **다음 Step 예정 · POC3-REF-02 검증 PASS 전 진입 금지** |
| POC3-04 | Operations Panel Consolidation v1 | 예상 |
| POC3-05 | Holdings Risk Evidence Foundation v1 | 예상 · 산식 미확정 |
| POC3-06 | Market Position & Data Quality Completeness v1 | 예상 · VIX/freshness/시장 위치 누락 귀속 |
| POC3-07 | PC Judgment Flow Closeout v1 | 예상 |
| POC4 | Decision Outcome Ledger v1 | 선행 gate 충족 후 |
| POC5 | Universe·ML·Backtest·Tuning | Ledger evidence 이후 |

POC3-03 종료 후 사용자가 보유 위험을 더 급한 차단 결함으로 판정하면 POC3-05를 POC3-04보다 먼저 열 수 있다. 순서 변경은 새 사용자 실화면·운영 evidence를 근거로 기록한다.

---

## 5. 친구 프로젝트 참고요소 채택·변형·제외 판정

| ID | 확인 요소 | 판정 | 우리 프로젝트 처리 |
|---|---|---|---|
| F-01 | 자산/정보/시스템 그룹과 평면 route 분리 | 확정 개발·변형 | 메뉴 개수·명칭은 복제하지 않고 과업별 접힘 그룹 원리만 POC3-03에 사용 |
| F-02 | 첫 화면 고밀도 요약·차트 | 완료·변형 | 오늘의 투자 점검과 Workbench에 이미 반영 |
| F-03 | 스파크라인·차트 중심 표현 | 조건부 보류 | 수치 관계를 더 잘 설명할 때만. 장식용 차트 금지 |
| F-04 | 19개 메뉴 전체 구조 | 제외·폐기 | 친구의 자산관리 범위를 통째 복제하지 않음 |
| F-05 | 상단 GlobalTickerSearch 비메뉴 진입 | 조건부 보류 | Workbench 검색으로 부족하다는 사용자 보고 시 |
| F-06 | Recharts·AG Grid 특정 라이브러리 | 조건부 보류 | 구현 Step 실측으로만 결정. 라이브러리 선채택 금지 |
| F-07 | 회귀 기울기+deadband+이력유지 레짐 | 조건부 보류 | Q6 위험 구간 분류의 비교 후보일 뿐 직접 이식 금지 |
| F-08 | 1시간 3% 급변 알림 개념 | 완료·제외 | 우리 Spike/Falling 운영이 이미 존재. 친구의 3% 수치는 채택하지 않음 |
| F-09 | 대시보드 no-store·무폴링·무서버캐시 | 조건부 보류 | 성능/stale 실측 전 캐시 계층 추가·제거 판단 금지 |
| F-10 | MongoDB snapshot+실시간 혼합 대시보드 | 제외·폐기 | SQLite 중심 PC/OCI 경계와 충돌 |
| F-11 | 미사용 `weight_allocator` | 제외·폐기 | 호출자 0건. 참고 가치 없음 |
| F-12 | 자동 주문·손절 연결 | 제외·폐기 | 조사 범위에서 발견되지 않았고 우리 프로젝트에서도 금지 |
| F-13 | Google OAuth·MongoDB | 제외·폐기 | KILL_SWITCH 이식 금지 |
| F-14 | bucket·다계좌 구조 | 조건부 보류 | 실제 다계좌·가족 공유 요구가 생길 때만 |
| F-15 | Slack cron 시각과 배치 구조 | 제외·폐기 | 우리 Telegram·OCI 운영 계약이 이미 별도로 확정 |
| F-16 | 금액 가리기 토글 | 조건부 보류 | 실제 화면 공유·노출 요구 시 |
| F-17 | 일/주/월/년·스냅샷 전용 메뉴 | 제외·폐기 | 현재 판단 흐름에 불필요한 자산관리 화면 확장 |

---

## 6. BACKLOG 105개 전수 판정

아래 ID는 2026-07-31 제공본 `docs/backlog/BACKLOG.md`의 출현 순서다. 같은 목적의 항목은 삭제하지 않고 canonical Lane에 귀속해 중복 개발을 막는다.

판정 합계: **완료 17 · 확정 개발 3 · 후속 개발 16 · 조건부 보류 65 · 제외·폐기 4 = 105**.

### 6.1 ML·위험·데이터

| ID | 항목 | 판정 | 귀속·재검토 기준 |
|---|---|---|---|
| B-001 | 상대상승 축1 이후 factor·threshold·위험 축2 | 후속 개발 | POC5 · Ledger 이후 |
| B-002 | ML 기반 초안 생성·분석 연결 | 조건부 보류 | ML 신뢰도 합의 후에만 |
| B-003 | 위험 evidence 급락·국면 경계 검증 | 확정 개발 | POC3-05의 핵심 입력 |
| B-004 | 급락 기준 기간 비교 | 후속 개발 | POC3-05/POC5에서 운영·백테스트 근거로 판정 |
| B-005 | 급락 신호 UI 고도화 | 조건부 보류 | 사용자가 가격 흐름 근거 부족을 보고할 때 |
| B-006 | 위험 지표 시계열 적재 | 후속 개발 | Q6에서 선택된 1~2개 축만 |
| B-007 | MDD·Sharpe 계산 | 후속 개발 | POC5 백테스트 Lane |
| B-008 | 구성종목 가격 시계열 source 진단 | 조건부 보류 | Exposure 또는 factor 판단을 실제로 막을 때 |
| B-009 | Naver Mobile 안정성 추가 진단 | 조건부 보류 | schema/429/차단 실측 시 |
| B-010 | NAV+FDR 시장가격 결합 | 조건부 보류 | source 안정성 문제 확인 시 |
| B-011 | KRX Open API 인증키 | 제외·폐기 | 사용자 운영 부담 결정으로 제외 |
| B-012 | pykrx ETF endpoint 재진단 | 조건부 보류 | upstream·정책 변경 시 |
| B-013 | NAV·괴리율 source 진단 | 완료 | 진단 및 Naver Universe NAV 연동 완료 |
| B-014 | FDR 약관·안정성·timeout | 조건부 보류 | 1회 실패 또는 장시간 hang 시 |
| B-015 | Naver endpoint 변경·차단 대응 | 조건부 보류 | 차단 실측 시 |
| B-016 | Naver 동시성·배치·rate limit | 조건부 보류 | 보유 50+ 또는 latency 발생 시 |
| B-017 | pykrx EOD fallback | 조건부 보류 | Naver 차단 시 |
| B-018 | market_cache TTL | 조건부 보류 | stale 노출 실측 시 |
| B-019 | refresh 실패 안내·재시도 UX | 완료 | 오늘의 투자 점검 정비 큐에 흡수 |
| B-020 | Naver ETag | 조건부 보류 | 호출량 증가 시 |
| B-021 | 복수 source 우선순위·메타 | 조건부 보류 | 실제 복수 source 도입 시 |
| B-022 | holdings/enriched 캐싱 | 조건부 보류 | 보유 100+ 또는 latency 시 |
| B-023 | enrichment 감사 로그 | 조건부 보류 | 반복 실패 원인 추적 필요 시 |
| B-024 | 가격 미확인 반복 실패 | 조건부 보류 | 동일 종목 7일+ 실패 시 |
| B-025 | 종목명 자동 조회 | 조건부 보류 | ticker 식별 곤란 시 |
| B-026 | 종목명 자동 보정 | 조건부 보류 | 실제 충돌 시 |
| B-027 | holdings ticker 검증 강화 | 조건부 보류 | 형식 오류 반복 시 |
| B-028 | 시세 정밀도·통화·단위 | 조건부 보류 | 외화 종목 보유 시 |

### 6.2 Market Discovery·구성종목·국면·판단 기록

| ID | 항목 | 판정 | 귀속·재검토 기준 |
|---|---|---|---|
| B-029 | Market Discovery 기본 조회 기준 UI | 조건부 보류 | 기본 1개월이 부적합하다는 사용자 보고 시 |
| B-030 | 레버리지·인버스·합성 필터 | 완료 | 현재 필터 계약에 반영 |
| B-031 | Data Status 실제 연결 | 완료 | NAV·ML readiness·상태 화면 연결 완료 |
| B-032 | ETF Category 라벨 | 조건부 보류 | ETF명 기반 해석으로 부족할 때 |
| B-033 | 구성종목 fetcher 다변화 | 조건부 보류 | 비교 불가 비율이 실제 판단을 차단할 때 |
| B-034 | 구성종목 fetcher timeout | 조건부 보류 | pykrx 등 추가 fetcher 도입 시 |
| B-035 | 중복률 임계 경고 | 조건부 보류 | 반복 노출 실측 후 기준 합의 시 |
| B-036 | 구성종목 fuzzy 매칭 | 조건부 보류 | 실제 미스매치 시 |
| B-037 | 시장 국면 고도화 | 후속 개발 | POC3-05 이후 Q6/POC5 |
| B-038 | 판단 근거 저장 후속·성과 추적 | 후속 개발 | POC4 Decision Outcome Ledger로 통합 |

### 6.3 Holdings·Telegram·UI

| ID | 항목 | 판정 | 귀속·재검토 기준 |
|---|---|---|---|
| B-039 | holdings 스키마 확장 | 조건부 보류 | 매수일·메모·목표가 명시 요구 시 |
| B-040 | holdings 편집 UX | 완료 | Holdings 입력·관리 화면 존재 |
| B-041 | 복수 포트폴리오·계좌 | 조건부 보류 | 가족·다계좌 실제 운영 시 |
| B-042 | 계좌별 세금 | 조건부 보류 | 사용자 요구 시 |
| B-043 | account_group 병합 UI | 조건부 보류 | 라벨 파편화 실측 시 |
| B-044 | 과거 draft 마이그레이션 | 조건부 보류 | 과거 run 재현 요청 시 |
| B-045 | stable holding_id | 조건부 보류 | 동일 ticker 다계좌 운영 시 |
| B-046 | 인증·사용자 구분 | 조건부 보류 | 다중 사용자 진입 시 |
| B-047 | Slack·Email·모바일 PUSH | 조건부 보류 | Telegram 차단 또는 명시 요청 시 |
| B-048 | Telegram Top N 설정 UI | 조건부 보류 | 사용자 요구 시 |
| B-049 | Telegram split 발송 | 완료 | 4096자 분할·partial_delivery 구현 완료 |
| B-050 | 계좌별 Telegram 분리 | 조건부 보류 | 가족 공유 시 |
| B-051 | 시세 확인 기준 요약 UX | 조건부 보류 | 누적 혼란 보고 시 |
| B-052 | 누락 데이터 포트폴리오 경고 | 조건부 보류 | 누락률이 판단을 왜곡한 실측 시 |
| B-053 | 시세 미확인 계좌 UX | 조건부 보류 | 7일+ 계산 불가 시 |
| B-054 | PnL 산식 설명 | 조건부 보류 | 사용자 질문 시 |
| B-055 | Telegram 실제 렌더 자동 검증 | 조건부 보류 | 깨짐 보고 또는 API 변경 시 |
| B-056 | 역할별 페이지 분리 | 완료 | Dashboard·Workbench·상세 화면으로 재조합 |
| B-057 | 접힘 상태 영구 저장 | 조건부 보류 | F5 컨텍스트 손실 보고 시 |
| B-058 | 상세 에러 UX | 조건부 보류 | 실제 오류 분류 요구 시 |
| B-059 | 새로고침 run_id 유실 | 조건부 보류 | 재현 보고 시 |
| B-060 | timezone·사람이 읽는 시각 | 완료 | POC3 주 판단 흐름 KST·사용자 언어로 정리 |
| B-061 | 모바일 최적화 | 조건부 보류 | Mobile Deferred 4조건 전부 충족 시 |
| B-062 | 샘플 입력 폼 제거 | 조건부 보류 | 운영 안정 후 잔존 혼란 시 |
| B-063 | app/api.py 라우터 분리 | 조건부 보류 | KS-10 trigger·near 실측 시 |

### 6.4 OCI·운영·history

| ID | 항목 | 판정 | 귀속·재검토 기준 |
|---|---|---|---|
| B-064 | 실패 상태 세분화 | 조건부 보류 | 실패 유형 다양화 시 |
| B-065 | 부분 재시도 | 조건부 보류 | 외부 실패 증가 시 |
| B-066 | 운영 필드 확장 | 조건부 보류 | SLA 요구 시 |
| B-067 | DELIVERING timeout·orphan | 조건부 보류 | orphan 실측 시 |
| B-068 | 실제 운영 배포 구조 통합 | 제외·폐기 | PC 분석·OCI 운영 평면 분리 결정으로 대체 |
| B-069 | OCI handoff artifact 고도화 | 완료 | PARAM DB·published evidence·runtime 계약으로 대체 |
| B-070 | 알림 5xx·429 재시도 | 조건부 보류 | 실패 빈도 증가 시 |
| B-071 | OCI timeout·orphan | 조건부 보류 | inbox 적체 실측 시 |
| B-072 | 전달 결과 대시보드 | 확정 개발 | POC3-04 Operations Panel에 흡수 |
| B-073 | OCI holdings source 부재 | 완료 | Holdings evidence publication·runtime 운영 완료 |
| B-074 | runtime source 확장 | 조건부 보류 | source별 운영 가치가 확인될 때만 |
| B-075 | 운영 결과·snapshot·변화 기록 | 완료 | runtime history·sent registry 구축. 판단 성과는 B-038로 분리 |
| B-076 | 비동기 universe refresh | 완료 | background 상태·SQLite 영속화 흐름으로 대체 |
| B-077 | pykrx 가격 history 캐시 | 제외·폐기 | SQLite 적재·FDR/Naver 경로로 대체 |
| B-078 | universe history | 후속 개발 | POC4/POC5 성과·생존편향 분석 전 |
| B-079 | ML dataset 저장 | 완료 | feature daily·market risk·training dataset 존재 |
| B-080 | pykrx 외 fallback | 조건부 보류 | 현 source 차단 시 |
| B-081 | Cboe VIX 과거 보정 | 조건부 보류 | FDR VIX 반복 실패·과거 구간 필요 시 |
| B-082 | 모델 고도화·전략 백테스트 | 후속 개발 | POC5 |
| B-083 | ETF universe 생존 편향 | 후속 개발 | POC5 성능 판정 전 보정·민감도 분석 |
| B-084 | 2014-04-07 이전 시계열 | 조건부 보류 | 백테스트에 실질 필요할 때 |

### 6.5 운영 질문·가드·seed·후속

| ID | 항목 | 판정 | 귀속·재검토 기준 |
|---|---|---|---|
| B-085 | Q4 발굴 단위 | 후속 개발 | 운영·Ledger 데이터로 결정 |
| B-086 | Q4 시간 측정 기간 | 후속 개발 | POC5 비교 실험 |
| B-087 | 무릎·머리·어깨 정량 기준 | 조건부 보류 | 보유 점검값 부족이 실측될 때 |
| B-088 | 보유 점검 vs 외부 발굴 가중치 | 조건부 보류 | 실제 충돌 시 |
| B-089 | RS·거래량·정배열 복합지표 | 조건부 보류 | POC5에서 단일 목표로 승인될 때 |
| B-090 | factor_signals 외 메타키 금지 | 제외·폐기 | 개발항목이 아니라 항구적 가드로 유지 |
| B-091 | 운영 빈도 문서 정합성 | 완료 | 2026-07-24/26 운영 계약으로 정정 완료 |
| B-092 | AI 토론 점수체계 검증 | 후속 개발 | AI Sessions·Ledger 1개월+ 누적 후 |
| B-093 | manual seed 편집 UI | 조건부 보류 | 실제 수기 변경 병목 1회+ 발생 시 |
| B-094 | 와이프 UI 이해도 검증 | 조건부 보류 | PC 흐름 안정·Mobile 재개 시 |
| B-095 | PC package fallback 재활성화 | 조건부 보류 | DB/PARAM 운영 실패 후 backup 필요가 실증될 때 |
| B-096 | 보유/외부 후보 비율 가변화 | 조건부 보류 | 운영 데이터로 10/10 부적합 확인 시 |
| B-097 | 유동성·변동성·테마중복·overlap seed 품질 | 후속 개발 | POC5 Universe 품질 Lane에서 한 축씩 |
| B-098 | seed 유지·교체·갱신·재승인 | 후속 개발 | 첫 seed 30일과 실제 stale 관찰 후 |
| B-099 | ML 기반 seed 품질 | 조건부 보류 | ML 신뢰도 합의 후 |
| B-100 | spike all-unavailable test fixture | 완료 | Telegram Spike closeout에서 해소 |
| B-101 | PUSH2 금지문구 substring test | 완료 | Telegram Spike closeout에서 해소 |
| B-102 | 저빈도 scheduler 운영 | 완료 | Market/Holdings/Spike OCI ACTIVE |
| B-103 | Decision Outcome Ledger | 후속 개발 | B-038과 통합 · First Real Decision Cycle PASS 후 |
| B-104 | Universe·ML·factor·PC UI 품질 개선 | 후속 개발 | umbrella 항목. B-082·B-085·B-097로 실행 분할 |
| B-105 | Dashboard 캐시 무효화 통합 테스트 | 확정 개발 | POC3-07 Closeout |

---

## 7. 중복 통합 키

| Canonical Lane | 통합되는 항목 |
|---|---|
| Holdings Risk Evidence | P-06, B-003, B-004, B-006, B-037, F-07 |
| Market Position Completeness | P-07, P-08, P-09, P-10 |
| Data Quality & Freshness | P-14, P-15, B-009~B-024 중 트리거 도달 항목 |
| Operations Panel | P-05, B-072 |
| Decision Outcome Ledger | P-19, B-038, B-103 |
| ML·Backtest·Tuning | P-20, B-001, B-007, B-082~B-086, B-092, B-097, B-104 |
| Dashboard cache regression | P-17, B-105 |

중복 통합은 원항목 삭제를 의미하지 않는다. 실행 Step을 한 번만 열기 위한 귀속이다.

---

## 8. POC3-03 진입 경계

이번 통합지도 승인 후 설계할 다음 Step의 범위는 아래까지만이다.

### 단일 목표

사용자가 좌측 메뉴에서 `오늘 확인 → 비교·판단 → 관리·상세 → 실행·운영`의 위치를 즉시 찾게 한다.

### 허용

- 기존 메뉴 key·route를 유지한 그룹 재배치
- 그룹명과 사용자 노출 라벨 정리
- 현재 선택 상태·접힘 동작
- 기존 화면 진입 경로의 중복·고아 여부 정리

### 금지

- 신규 API·DB·source·산식·threshold
- 화면 기능 추가
- 기존 화면 삭제
- Operations Panel 선구현
- 친구 프로젝트 19개 메뉴 복제
- 자동 주문·손절·공격/방어 비중

### 설계자 복귀 조건

기존 route만으로 과업 그룹을 만들 수 없거나, 메뉴 재편이 화면 역할·데이터 의미·저장 정책을 바꾸는 경우 개발자는 임의 결정하지 않고 설계자에게 복귀한다.

---

## 9. 통합지도 완료 기준

- 제공된 108개 문서의 미구현·보류·완료·폐기 후보가 P/F/B 항목에 모두 귀속됐다.
- 현재 BACKLOG 105개가 B-001~B-105로 1:1 대응한다.
- POC3 현재 화면의 `개발 중`·`이번 단계 미도입` 항목이 P-06~P-16에 귀속됐다.
- 친구 프로젝트 참고요소가 F-01~F-17로 채택·변형·보류·제외 판정을 받았다.
- POC3-01·POC3-02의 실제 완료 상태가 오래된 문서보다 우선하도록 정정됐다.
- 다음 실제 개발 Step은 POC3-03 하나만 확정됐다.

따라서 이 지도의 `orphan_count = 0`이다.
