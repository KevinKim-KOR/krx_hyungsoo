# BACKLOG_RECONCILIATION_V2 — 최종 정합 결론 **R2**

- **수신**: 설계자 · 사용자 → (재판정 후) 검증자
- **발신**: 개발자
- **작성일**: 2026-08-21
- **선행**: 1차 `..._V2_INPUT.md`(`PARTIAL`) → 2차 본 문서 초판(`REJECTED`) → **본 R2**
- **성격**: **읽기 전용.** 코드·`BACKLOG.md`·`STATE_LATEST`·ML **전부 무변경** ·
  외부 데이터 호출 0 · 운영 write 0 · **commit·push 미수행**(지시 대기).
- **R2 의 핵심**: **67행 원장표 하나를 단일 진실로 두고, 모든 집계·처리 목록을 그 표에서
  기계적으로 파생**시켰다. 손으로 센 숫자가 문서에 남아 있지 않다.

---

## 0. R2 에서 바로잡은 것

### 0.1 계상 오류 — 세 번째이자 마지막

1차는 `VALID_FUTURE 46` 이라 했고(실제 49), 2차는 합계를 67로 맞췄으나 **7개 항목이 두
분류에 걸쳐 있었다.** 두 번 모두 **"슬롯을 센 것" 을 "항목을 센 것" 처럼 보고**한 오류다.

**R2 의 구조적 방지책**: 분류를 `원장번호 → (분류, 근거, 처리)` **딕셔너리 하나**로만
정의했다. 키가 유일하므로 **한 항목이 두 분류에 들어가는 것이 물리적으로 불가능**하다.
집계표·처리 목록은 전부 이 딕셔너리에서 파생 생성했다.

```
원장 항목 67건 · 고유 67건 · 분류 dict 67건
set(원장번호) == set(분류키)   ✓ assert 통과
분류별 합계 55+4+4+2+1+1 = 67  ✓ 표에서 파생
```

### 0.2 ⚠ 완료 판정 4건이 **전부** 뒤집혔다

설계자가 *"파일이나 함수가 있다만으로 완료 판정하기 부족하다"* 며 계약 단위 보강을
요구한 4건을 다시 확인했다. **보강 결과 4건 전부 완료가 아니었다.**

> **정정(검증자 지적)**: 초판은 *"4건 중 3건"* 이라고 적었으나 아래 표는 **#4·#33·#43·#45 네 건 모두** `COMPLETED → VALID_FUTURE` 로 철회하고 있다. 표와 서술이 어긋났다.

| # | 2차 판정 | 계약 단위 재확인 | R2 판정 |
|---|---|---|---|
| **#4** 급락 후보 latest GET 계약 | `COMPLETED` | **`app/api_universe.py` 에 `@router.post` 만 있고 GET 라우트가 0건.** 파일 주석 L9 가 *"신규 endpoint 추가 금지 — GET `/universe/momentum/latest` **제거**"* 라고 명시 | **`VALID_FUTURE`** — 응답 모델에 필드가 있는 것을 GET 계약으로 착각했다 |
| **#33** draft_payload 마이그레이션 | `COMPLETED` | 마이그레이션 2개는 **`decision_evidence` 테이블 대상**. `draft_payload` 는 `app/store.py:62,76` 에 **별도 저장**되고 해당 마이그레이션이 없다 | **`VALID_FUTURE`** — 테이블을 확인하지 않았다 |
| **#43** Telegram 렌더 차이 자동 검증 | `COMPLETED` | `test_telegram_send_chunking.py` 의 `test_split_*` **7건**은 **분할·길이 제한만** 검증(파일 전체 15건 중 나머지 8건은 전송 성공·실패 경로). 실제 송신은 `three_push_runner_common.py:302` 에서 **`parse_mode: "HTML"`** 인데 **HTML 실제 렌더 대조 검증 0건** | **`VALID_FUTURE`** — 파일명만 보고 판단했다 |
| **#45** 상세 에러 UX | `COMPLETED` | `describeError` 가 **12개 파일에만 부분 적용**(참고 분모 — 최상위 `components/*.tsx` 45개 · **재귀 비테스트 58개**) | **`VALID_FUTURE`** — 일부 사용을 전체 충족으로 봤다 |

**#12·#30 은 설계자 확정대로** 처리했다(#12 → `VALID_FUTURE` 범위 축소, #30 → `COMPLETED`).

> 결과적으로 `COMPLETED` 는 2차 9건 → **R2 4건**으로 줄었다.

### 0.3 설계자 확정 분류 반영 (중복 제거)

| 항목 | 확정 | 반영 |
|---|---|---|
| #6 구성종목 등락률 | `VALID_FUTURE` · 중복은 이력만 | `DUPLICATE` 건수에서 **제외** |
| #12 Naver 동시성 | `VALID_FUTURE` · **시세 경로로 범위 축소** | `COMPLETED` 에서 **제외** |
| #30 복수 계좌 | `COMPLETED` · 가족·다중 제외를 완료 근거에 병기 | `EXCLUDED` 에서 **제외** |
| #53 운영 필드 | `VALID_FUTURE` · 잔여 3필드로 축소 | `UNKNOWN` 에서 **제외** |
| #57 runtime source | `VALID_FUTURE` · VIX 제외 | `UNKNOWN` 에서 **제외** |
| #61~63 Layer B/C | `VALID_FUTURE` · **라벨만 제목·섹션에서 제거** | `UNKNOWN`·결함에서 **제외** |
| #65 와이프 UI | `VALID_FUTURE` (조건부 미래 과제) | `UNKNOWN` 에서 **제외** |
| #66 PC package | `UNKNOWN` | **유일한 `UNKNOWN`** |
| 원장 밖 결함 | 별도 표 | **67건 합계에서 제외**(§4) |

---

## 1. 최종 분류별 건수 — 67행 원장표에서 파생

| 분류 | 건수 | 해당 원장 번호 |
|---|---|---|
| `VALID_FUTURE` | **55** | #3, #4, #5, #6, #7, #8, #9, #11, #12, #13, #14, #15, #16, #17, #18, #19, #22, #23, #24, #25, #27, #28, #29, #32, #33, #34, #37, #38, #39, #40, #41, #42, #43, #44, #45, #46, #47, #48, #50, #51, #52, #53, #54, #55, #56, #57, #58, #60, #61, #62, #63, #64, #65, #67, #68 |
| `COMPLETED` | **4** | #20, #26, #30, #49 |
| `EXCLUDED` | **4** | #31, #35, #36, #59 |
| `CURRENT_DEFECT` | **2** | #2, #10 |
| `DUPLICATE` | **1** | #21 |
| `UNKNOWN` | **1** | #66 |

> **합계 67 = 고유 원장 항목 67.** 위 번호 목록에 **중복 등장하는 번호가 없다**(§7 검산).

---

## 2. 67행 원장표 (단일 진실)

**원장의 `- **항목**:` 출현 순서. 한 행 = 한 항목 = 한 분류.**

| 원장 # | B-ID | 항목명 | 최종 분류 | 직접 근거 | canonical 처리 |
|---|---|---|---|---|---|
| #2 | `B-002` | ML 기반 초안 생성 / 분석 연결 (추천 로직 / 정렬 / score 도입, 추천 판단 사유 message 노출) | **`CURRENT_DEFECT`** | `etf_ml_feature_daily` 0행 · `relative_upside_score_latest.json` 부재 · 마지막 job `failed` | **결함 `DEF-ML-CHAIN` 으로 승격** — 원장에서 결함 목록으로 이동 |
| #3 | `B-005` | 급락 신호 UI 고도화 | **`VALID_FUTURE`** | `HoldingsRiskEvidenceSection.tsx:7` — *"GET 계약 부재로 이번 Step 제외"* | 유지. **선행 조건(#4)이 아직 미충족**이므로 보류 사유 그대로 유효 |
| #4 | `신규` | 급락 후보(`falling_candidate`)의 안정적 latest 읽기 GET 계약 (POC3-05 §13.1) | **`VALID_FUTURE`** | `app/api_universe.py` 라우트 실측 — **`@router.post` 만 존재, GET 0건**. 파일 주석 L9: *"신규 endpoint 추가 금지 — GET /universe/momentum/latest **제거**"* | 유지. **1차·2차의 `COMPLETED` 판정을 철회**(§0.2) |
| #5 | `B-001` | 보유 ETF 종합 위험 구간 분류 (factor·threshold·label) (POC3-05 §13.2) | **`VALID_FUTURE`** | `app/ml_baseline_risk.py` 존재하나 화면 노출 0건 | 유지 |
| #6 | `B-008` | 구성종목 등락률 (가격 시계열 source 진단 · 개별주 시세 수집) | **`VALID_FUTURE`** | 설계 확정으로 화면 등락률 열 제거 완료(2026-08-19). 수집은 미착수 | 유지. **중복은 이미 병합됨(이력만 기록)** — `DUPLICATE` 로 세지 않음 |
| #7 | `B-009` | Naver Mobile stock integration API 운영 안정성 추가 진단 | **`VALID_FUTURE`** | `app/market_naver.py:71-84` timeout·예외처리는 있으나 진단 리포트 없음 | 유지 |
| #8 | `B-010` | NAV source + FDR 시장가격 결합 패턴 | **`VALID_FUTURE`** | `market_refresh_service.py:31` — NAV·FDR 순차 실행뿐, 결합 없음 | 유지 |
| #9 | `B-012` | pykrx ETF endpoint 자체 동작 진단 | **`VALID_FUTURE`** | `app/price_history_pykrx.py` 등 5파일 존재 · 진단 절차 없음 | 유지 |
| #10 | `B-014` | FDR 외부 의존 약관 / 안정성 / 단일 호출 timeout 부재 | **`CURRENT_DEFECT`** | 호출자 3곳 전부 상위 timeout 없음. `market_refresh_log` 실측 — 2026-08-20 1,171종목 140.4초 실행 | **결함 `DEF-FDR-TIMEOUT` 으로 승격** |
| #11 | `B-015` | Naver endpoint 변경 / 차단 대응 | **`VALID_FUTURE`** | 단일 endpoint 하드코딩 · 대안 경로 없음 | 유지 |
| #12 | `B-016` | Naver fetch 동시성 / 배치 / rate limit | **`VALID_FUTURE`** | 구성종목 경로는 `delay 0.5s`+`budget 30s`+`max 10` 방어 완료. **시세 경로(`market_naver.py`)는 종목별 순차 호출, 배치·동시성 없음** | **범위 축소 — 제목을 시세 경로로 한정.** `COMPLETED` 로 세지 않음 |
| #13 | `B-017` | pykrx EOD fallback 추가 (POC2-Step2A) | **`VALID_FUTURE`** | `market_refresh_service.py` FDR 단일 · fallback 없음 | 유지 |
| #14 | `B-018` | market_cache TTL / 만료 정책 | **`VALID_FUTURE`** | `app/market_cache.py:9` — *"TTL/만료 정책 도입 안 함"* 명시 | 유지(의도적 미도입) |
| #15 | `B-020` | Naver 응답 캐싱 헤더 / ETag 활용 | **`VALID_FUTURE`** | `grep ETag app/` 0건 | 유지 |
| #16 | `B-021` | market_cache 복수 source 우선순위 / 메타데이터 | **`VALID_FUTURE`** | `market_cache.py:52` `price_source: str = "naver"` 단일 | 유지 |
| #17 | `B-022` | GET /holdings/enriched 응답 캐싱 / 조건부 응답 | **`VALID_FUTURE`** | `grep "Cache-Control|304" app/api.py` 0건 | 유지 |
| #18 | `B-023` | enrichment 단계 로깅 / 감사 추적 | **`VALID_FUTURE`** | `app/holdings_enrich.py` 에 `logger` 0건 | 유지 |
| #19 | `B-024` | 가격 미확인 종목 반복 실패 관리 | **`VALID_FUTURE`** | `price_missing` 1회성 플래그만 · 누적 관리 없음 | 유지 |
| #20 | `B-025` | 종목명 자동 조회 — **개별주 잔여분** (ETF 는 해소) | **`COMPLETED`** | `GET /holdings/etf-name`(`api.py:291`) + `HoldingsManageView.lookupTicker`. **ETF 자동조회 동작** · 개별주는 사용자 확정으로 수동 입력 | **활성 BACKLOG 에서 제거**(설계 확정) |
| #21 | `B-026` | 종목명 자동 보정 (사용자 입력 vs Naver 응답 충돌) | **`DUPLICATE`** | #20 과 같은 `etf-name` 조회 경로 | **#20 이력에 병합 후 제거** |
| #22 | `B-028` | 시세 표시 정밀도 / 통화 / 단위 | **`VALID_FUTURE`** | 원화 고정 표시 | 유지 |
| #23 | `B-029` | Market Discovery 기본 조회 기준 설정 UI | **`VALID_FUTURE`** | `basis`·`order` URL 파라미터만 · 설정 UI 없음 | 유지 |
| #24 | `B-032` | ETF Category 라벨 매핑 | **`VALID_FUTURE`** | **컬럼과 원시 코드는 존재한다** — `market_data_store.py:25` `category TEXT`, DB 실측 `etf_master` **1,171행 전부 category 보유 · 고유값 `1`~`7`**. 없는 것은 **코드 → 사용자 표시 라벨 매핑** | 유지 |
| #25 | `B-033` | ETF 구성종목 fetcher 다변화 + chain fallback | **`VALID_FUTURE`** | `_pykrx_pdf_fetcher` 정의만 있고 기본은 Naver 단일 · chain 미구성 | 유지 |
| #26 | `B-034` | ETF 구성종목 fetcher timeout 가드 | **`COMPLETED`** | `etf_constituents_fetcher.py` `NAVER_TIMEOUT_SEC = 10`. 원장 보류 사유도 *"Naver 10s 명시 timeout"* 로 인정 | **제거**(설계 확정). pykrx 도입 시 재등재 |
| #27 | `B-035` | 중복률 임계 기반 경고 | **`VALID_FUTURE`** | `etf_constituents_analysis.py` 에 임계 상수 없음 | 유지 |
| #28 | `B-036` | 구성종목 fuzzy 매칭 | **`VALID_FUTURE`** | ticker/reuters/ISIN/정규화 name 매칭까지만 | 유지 |
| #29 | `B-039` | holdings 스키마 확장 (평균단가 외 필드 — 매수일자 / 메모 / 목표가) | **`VALID_FUTURE`** | `app/holdings.py` 에 매수일자·메모·목표가 필드 없음 | 유지 |
| #30 | `B-041` | 복수 포트폴리오 / 계좌 지원 (계좌번호 / 증권사 / 가족별) | **`COMPLETED`** | `holdings.py:11-21,47` `account_group` + `normalize_account_group()` + `(ticker, account_group, avg_buy_price)` 삼중키. **실측 32건 = 일반 12 / ISA 13 / 오픈뱅킹 7** | **제거.** 완료 근거에 *"가족·다중 사용자 포트폴리오는 프로젝트 제외"* 병기(설계 확정) |
| #31 | `B-042` | 계좌별 세금 / 절세 판단 | **`EXCLUDED`** | 매매·세무 판단 제공 안 함 원칙 | **폐기**(설계 확정) |
| #32 | `B-043` | account_group 라벨 병합 / 관리 UI | **`VALID_FUTURE`** | `HoldingsManageView.tsx:48,91,127` 라벨 입력·정렬만 · 병합 UI 없음 | 유지 |
| #33 | `B-044` | 과거 draft_payload 영구 마이그레이션 | **`VALID_FUTURE`** | `decision_evidence_store.py:79,167` 마이그레이션은 **`decision_evidence` 테이블 대상**. `draft_payload` 는 `app/store.py:62,76` 에 별도 저장 — **해당 마이그레이션 없음** | 유지. **2차의 `COMPLETED` 판정을 철회**(§0.2) |
| #34 | `B-045` | stable holding_id 영구 저장 | **`VALID_FUTURE`** | `app/holdings.py` 에 `holding_id` 0건 | 유지 |
| #35 | `B-046` | 인증 / 사용자 구분 | **`EXCLUDED`** | 1인 사용 프로젝트 | **폐기**(설계 확정) |
| #36 | `B-047` | 메시지 포맷 / 알림 채널 고도화 (Slack / Email / 모바일 PUSH 등) | **`EXCLUDED`** | Telegram 단일 채널 확정 | **폐기**(설계 확정) |
| #37 | `B-048` | Telegram 메시지 Top N 설정값 UI 화 | **`VALID_FUTURE`** | `draft_message_focus.py:34-36` `TOP_N_* = 3` 하드코딩 · UI 없음 | 유지 |
| #38 | `B-050` | 계좌별 Telegram 요약 / 채널 분리 | **`VALID_FUTURE`** | 단일 chat_id | 유지 |
| #39 | `B-051` | 시세 확인 종목 기준 요약 UX 고도화 | **`VALID_FUTURE`** | 해당 UX 미구현 | 유지 |
| #40 | `B-052` | 누락 데이터 많은 포트폴리오 별도 경고 정책 | **`VALID_FUTURE`** | 해당 정책 미구현 | 유지 |
| #41 | `B-053` | 시세 미확인 계좌 UX 고도화 | **`VALID_FUTURE`** | 해당 UX 미구현 | 유지 |
| #42 | `B-054` | PnL 산식 설명 고도화 | **`VALID_FUTURE`** | 해당 설명 미구현 | 유지 |
| #43 | `B-055` | message_text 와 Telegram 실제 렌더 차이 자동 검증 | **`VALID_FUTURE`** | `test_split_*` **7건**은 분할·길이 제한만 검증(파일 전체 15건). 실제 송신 `parse_mode` 는 **`HTML`**(`three_push_runner_common.py:302`)인데 **HTML 실제 렌더 검증 0건** | 유지. **2차의 `COMPLETED` 판정을 철회**(§0.2) |
| #44 | `B-057` | 근거 데이터 접힘 상태 영구 저장 (localStorage / URL Query) | **`VALID_FUTURE`** | `LeftSidebar.tsx:15` — *"접힘 영구저장은 **B-057** 보류 유지"* 코드가 B-ID 직접 참조 | 유지(의도적 보류) |
| #45 | `B-058` | 상세 에러 UX 개선 | **`VALID_FUTURE`** | `describeError` 가 **12개 파일에만 부분 적용** (분모: 최상위 `components/*.tsx` **45** · 재귀 비테스트 **58**). 원장의 '상세 에러 UX' 범위 미충족 | 유지. **2차의 `COMPLETED` 판정을 철회**(§0.2) |
| #46 | `신규` | 그리드 디자인 — **컬럼 프리셋 잔여분** (2026-08-02 사용자 지적분 중) | **`VALID_FUTURE`** | `grep 프리셋 frontend/` 0건 | 유지 |
| #47 | `B-059` | 수동 새로고침 시 run_id 유실 방지 | **`VALID_FUTURE`** | `MainPanel.tsx` 에 `run_id` 0건 | 유지 |
| #48 | `B-061` | 모바일 최적화 (compact table / 터치 UX) | **`VALID_FUTURE`** | 모바일 대응 미구현 | 유지. **1차 `EXCLUDED` 철회**(설계 확정) |
| #49 | `B-062` | 샘플 입력 폼 완전 제거 | **`COMPLETED`** | 샘플·미리보기가 `개발·실험용` 화면으로 격리 완료(`DiagnosticsView.tsx:35` — *"정상 업무 화면이 아닙니다"*) | **제거**(설계 확정) |
| #50 | `B-063` | app/api.py 라우터 분리 | **`VALID_FUTURE`** | 실측 **632줄 · `include_router` 16개** | 유지. KS-10 트리거 판단은 설계자 몫 |
| #51 | `B-064` | 실패 상태 세분화 (DRAFT_FAILED / PUSH_FAILED / ALERT_FAILED) | **`VALID_FUTURE`** | `grep "DRAFT_FAILED|PUSH_FAILED" app/` 0건 | 유지 |
| #52 | `B-065` | 부분 재시도 정책 (Retry Push / Retry Alert) | **`VALID_FUTURE`** | 부분 재시도 미구현 | 유지 |
| #53 | `B-066` | 운영 필드 확장 (approved_at / rejected_at / error_code / error_message) | **`VALID_FUTURE`** | `approved_at` 은 **구현됨**(`delivery.py:128`·`runtime_state_db.py:39`). `rejected_at`·`error_code`·`error_message` 0건 | **범위 축소 — 잔여 3필드로 한정**(설계 확정). `UNKNOWN` 으로 세지 않음 |
| #54 | `B-067` | DELIVERING polling / timeout / orphan 처리 고도화 | **`VALID_FUTURE`** | DELIVERING polling/orphan 미구현 | 유지 |
| #55 | `B-070` | 알림 재시도 정책 (5xx / 429) | **`VALID_FUTURE`** | 5xx/429 재시도 미구현 | 유지 |
| #56 | `B-071` | OCI 측 처리 timeout / orphan 대응 | **`VALID_FUTURE`** | OCI timeout/orphan 미구현 | 유지 |
| #57 | `B-074` | runtime data source 확장 (CNN F&G / VIX / USD KRW / 원유 / news / holdings valuation) | **`VALID_FUTURE`** | **VIX 는 구현됨**(`api_market_topn_models.py:228`·`api_decision_draft_preview.py:42`). CNN F&G·USD/KRW·원유·news 는 0건 | **범위 축소 — VIX 제외**(설계 확정). `UNKNOWN` 으로 세지 않음 |
| #58 | `B-080` | pykrx 외 fallback 데이터 source | **`VALID_FUTURE`** | pykrx 외 fallback 미구현 | 유지 |
| #59 | `B-081` | Cboe VIX 자료를 이용한 수동 과거 보정 또는 보조 검증 | **`EXCLUDED`** | 수동 데이터 주입 경로를 만들지 않음 | **폐기**(설계 확정) |
| #60 | `B-084` | 2014-04-07 이전 ETF 시계열 보강 | **`VALID_FUTURE`** | 실측 `etf_daily_price` 최소 asof **2014-04-09**(1,379,939행) — 항목 기술과 정합 | 유지 |
| #61 | `B-087` | Layer B — 무릎 / 머리 / 어깨 정량 기준 | **`VALID_FUTURE`** | `POC2_STEP7...DESIGN.md` **§9.4** 정의 + **AC-10** *"무릎/머리/어깨 기준은 확정하지 않는다"*. 복귀 조건 명시 | 유지. **정의 없는 `Layer B` 라벨만 제목·섹션에서 제거**(설계 확정) |
| #62 | `B-088` | Layer B — 보유 점검과 외부 발굴 가중치 | **`VALID_FUTURE`** | `POC2_STEP4...DESIGN.md:73` — *"외부 발굴과 보유 점검은 별도 로직이 아니라…"* | 유지. **`Layer B` 라벨 제거** |
| #63 | `B-089` | Layer C — RS / 거래량 / 정배열 복합 지표 | **`VALID_FUTURE`** | `POC2_STEP7...DESIGN.md` **§9.6** 정의 + **AC-12** *"RS/거래량/정배열 등 복합 지표는 도입하지 않는다"* | 유지. **`Layer C` 라벨 제거** |
| #64 | `B-093` | manual seed 입력 UX 개선 (seed 편집 UI) | **`VALID_FUTURE`** | seed 편집 UI 미구현 | 유지 |
| #65 | `B-094` | 와이프 UI 이해도 검증 | **`VALID_FUTURE`** | 검증 수행 기록 없음 | 유지. **조건부 미래 과제**(설계 확정) — `UNKNOWN` 아님 |
| #66 | `B-095` | PC package fallback 경로 재활성화 (`state/three_push/packages/` 생성 파이프라인) | **`UNKNOWN`** | 맥에 `state/three_push/` 없음. **맥은 운영기가 아니라 판정 불가** | **PC 실측 전까지 보류** — 유일한 `UNKNOWN` |
| #67 | `B-096` | 보유/외부 후보 비율 가변화 (현재는 10/10 고정) | **`VALID_FUTURE`** | 10/10 고정 · 가변화 미구현 | 유지 |
| #68 | `B-099` | ML·백테스트 기반 seed 품질 개선 | **`VALID_FUTURE`** | ML feature 0행 → 선행 조건 미충족 | 유지 |
---

## 3. 완료 후보 4건 — 계약 단위 근거 (설계자 요구 §6)

`COMPLETED` 로 남은 4건은 **"파일이 있다" 가 아니라 계약이 성립하는지**로 확인했다.

| # | 항목 | 계약 단위 근거 |
|---|---|---|
| #20 | 종목명 자동 조회 | **경로 전체 확인** — `GET /holdings/etf-name`(`app/api.py:291-299`) → `market_data_store.get_etf_name` → `etf_master` 조회. 프론트 `HoldingsManageView.lookupTicker` 가 형식검증→조회→`autoName` 채움까지 수행하며 **stale 방지**(응답 적용 직전 ticker 재확인)까지 구현. **개별주는 `etf_master` 에 없어 `None`**(실측: `005930`·`000660` → `None`)이며 이는 **사용자가 수동 입력으로 확정**한 범위 |
| #26 | 구성종목 fetcher timeout | **현행 단일 fetcher 에 대해 계약 성립** — `NAVER_TIMEOUT_SEC = 10` 이 `_naver_http_get` 에 적용. 원장 보류 사유 본문도 *"Naver 10s 명시 timeout. pykrx 부재"* 로 이미 인정. **pykrx 를 도입하면 재등재 필요**(처리 열에 명시) |
| #30 | 복수 포트폴리오·계좌 中 본인 다계좌 | **저장·검증·표시 3계층 확인** — 저장 `holdings.py` `account_group` 필드, 중복 차단 키가 `(ticker, account_group, avg_buy_price)` **삼중 조합**, 표시 `HoldingsManageView` 계좌별 그룹. **실측 32건이 3계좌로 분산 운영 중**. 가족·다중 사용자는 프로젝트 제외 |
| #49 | 샘플 입력 폼 제거 | **정상 업무 화면에서 제거 + 격리 확인** — `DiagnosticsView.tsx:35` 가 *"정상 업무 화면이 아닙니다. 미리보기·샘플(PREVIEW/TEST)…"* 안내와 함께 `개발·실험용` 메뉴로 격리. `ApprovalTelegramView.tsx:9` 주석이 이동 사실을 기록 |

---

## 4. 결함 목록 — **원장 승격 2건 + 원장 밖 2건**

> **정정(검증자 지적)**: 초판 제목은 표 전체를 *"기존 67건 밖에서 발견한 결함"* 이라고 했으나 사실과 다르다. `DEF-ML-CHAIN`·`DEF-FDR-TIMEOUT` 은 **원장 #2·#10 이 승격된 것**이고, **원장 밖은 `DEF-BACKLOG-TERM`·`DEF-LAYER-LABEL` 두 건뿐**이다. 본문 계상은 처음부터 올바랐고 제목만 경계를 잘못 설명했다.

| ID | 결함 | 출처 | 근거 | 처리 |
|---|---|---|---|---|
| `DEF-ML-CHAIN` | **ML feature/evidence 생성 체인 미작동** | **원장 #2 승격** | `etf_ml_feature_daily` **0행** · `market_risk_feature_daily` **0행** · `state/ml/relative_upside_score_latest.json` **부재** · 마지막 job `failed`(`sanity_status=error / errors=3`) | 원장에서 결함 목록으로 이동. 참고점수·사유·`고점 대비` 가 전 종목 빈칸(열·정렬은 설계 확정대로 **유지**) |
| `DEF-FDR-TIMEOUT` | FDR 호출 timeout 부재 | **원장 #10 승격** | §5 | 원장에서 결함 목록으로 이동 |
| `DEF-BACKLOG-TERM` | `BACKLOG 후보` 내부 용어가 사용자 화면에 노출 | **BACKLOG 밖 UI 결함** | `MLTimeseriesReadinessCard.tsx:147` | 별도 관리 |
| `DEF-LAYER-LABEL` | 섹션 `14. Layer 활성 관리 (ASSUMPTIONS 연계)` 가 실제로는 `Layer A` 하고만 연계 | **BACKLOG 밖 문서 결함** | `ASSUMPTIONS.md:72` 만 `Layer A` 정의 | 이번 정합에서 라벨 제거로 해소(§6.2) |

> **`DEF-ML-CHAIN`·`DEF-FDR-TIMEOUT` 은 원장 #2·#10 이 승격된 것**이므로 원장표에
> `CURRENT_DEFECT` 로 **한 번만** 등장한다. `DEF-BACKLOG-TERM`·`DEF-LAYER-LABEL` 은
> **원장에 없던 것**이라 67건 어디에도 세지 않는다.

---

## 5. FDR timeout 판정 근거 (지시문 §5)

| 확인 항목 | 실측 |
|---|---|
| 직접 호출자 | 3곳 — `market_refresh_service.py:33` · `market_benchmark_store.py:189` · `three_push_runtime/market_data_batch.py:147` |
| 정상 운영 경로인가 | **그렇다.** `market_refresh_log` — `FinanceDataReader/prices` 가 2026-08-20 **1,171종목 · 140.4초**(성공 1171 / 실패 0) |
| fallback / 비활성인가 | **아니다.** 시장 갱신의 주 경로 |
| 상위 timeout·budget | **없다.** 세 호출자 전부 `timeout`·`budget`·`deadline` 0건 |
| 실제 hang 관측 | **없다.** 최근 8건 로그 전부 `fail_count = 0` |

**판정 `CURRENT_DEFECT`** — 지시문 기준 *"현재 필수 운영 경로"*. hang 이력은 없으나
**방어 수단이 어느 계층에도 없고, 1,171종목 순차 호출이라 한 종목이 멈추면 갱신 전체가 멈춘다.**
외부 FDR 호출은 실행하지 않았다(정적 확인 + 기존 DB 로그 조회).

---

## 6. Layer B/C 조사 결과

### 6.1 항목 **내용**은 정의가 있다 — 1차 결론 정정

1차의 *"`ASSUMPTIONS.md` 에 문자열 0건"* 은 **그 파일만 본 오류**였다.

**출처**: `docs/handoff/POC2/POC2_STEP7_SYSTEM_OUTPUT_3_PUSH_REALIGNMENT_DESIGN.md`
(2026-05-11 · **레드팀 CONDITIONAL_PASS**)

| 원장 # | 정의 위치 | 완료 기준 AC |
|---|---|---|
| #61 무릎/머리/어깨 | **§9.4** — 보류 사유·위험·복귀 조건 3필드 완비 | **AC-10** *"무릎/머리/어깨 기준은 확정하지 않는다"* |
| #63 RS/거래량/정배열 | **§9.6** — 친구식 복합 점수체계 회귀 위험 | **AC-12** *"RS / 거래량 / 정배열 등 복합 지표는 도입하지 않는다"* |
| #62 보유 점검 vs 외부 발굴 | `POC2_STEP4...DESIGN.md:73` | — |

**"아직 안 한 것" 이 아니라 "안 하기로 명시한 것" 이며 복귀 조건이 문서화돼 있다** →
`VALID_FUTURE` 유지가 맞다(폐기 아님).

### 6.2 `Layer B`/`Layer C` **라벨**은 정의가 없다

| 라벨 | 정의 |
|---|---|
| `Layer A` | `docs/ASSUMPTIONS.md:72` **정의 있음** |
| `Layer B` | **없음** — BACKLOG 섹션명·항목 제목에만 등장 |
| `Layer C` | **없음** — §9.5 에 *"§9.6 Layer C 와 연결"* 참조만 있고 규정한 곳이 없다 |

**설계자 확정 반영**: 항목은 `VALID_FUTURE` 로 유지하고 **정의되지 않은 라벨만 제목과
섹션명에서 제거**한다(§8.5). 개발자는 의미를 새로 만들지 않았다.

---

## 7. 정합 검산 (기계 실행 결과)

문서를 손으로 세지 않았음을 보이는 실행 출력이다.

```
원장 항목 67건 · 고유 67건 · 분류 dict 67건
assert len(C) == 67                      ✓
assert len(nums) == 67 == len(set(nums)) ✓
assert set(nums) == set(C)               ✓   ← 원장번호 집합 == 분류키 집합

분류별 (dict 에서 파생):
  VALID_FUTURE     55
  COMPLETED         4
  EXCLUDED          4
  CURRENT_DEFECT    2
  DUPLICATE         1
  UNKNOWN           1
  합계             67
총 67건 · 고유 67건
```

**한 항목이 두 분류에 들어가는 것이 구조적으로 불가능하다** — 분류가 `원장번호 → 분류`
딕셔너리 하나이고, 키는 유일하기 때문이다. §1 집계표·§2 원장표·§8 처리 목록은 전부
같은 딕셔너리에서 생성했다.

---

## 8. canonical BACKLOG 수정 예정 목록 — 원장표에서 파생

**개발자는 `BACKLOG.md` 를 수정하지 않았다.**

### 8.1 제거 — `COMPLETED` (4건)

#20 종목명 자동 조회 · #26 구성종목 fetcher timeout · #30 복수 포트폴리오·계좌 ·
#49 샘플 입력 폼 제거

### 8.2 병합 후 제거 — `DUPLICATE` (1건)

#21 종목명 자동 보정 → **#20 이력에 병합**

### 8.3 폐기 — `EXCLUDED` (4건)

#31 계좌별 세금 · #35 인증·사용자 구분 · #36 Slack·Email·모바일 PUSH ·
#59 Cboe VIX 수동 보정

### 8.4 결함으로 승격 (2건, 원장에서 이동)

#2 → `DEF-ML-CHAIN` · #10 → `DEF-FDR-TIMEOUT`

### 8.5 항목 **범위 축소 / 제목 수정** (6건 — 분류는 `VALID_FUTURE` 유지)

| # | 수정 |
|---|---|
| #12 | 제목을 **시세 경로**로 한정 (구성종목 경로 방어는 완료) |
| #53 | `approved_at` 제외 → **잔여 3필드**(`rejected_at`·`error_code`·`error_message`) |
| #57 | **VIX 제외** → 잔여 source (CNN F&G · USD/KRW · 원유 · news · holdings valuation) |
| #61 | 제목에서 **`Layer B —`** 제거 |
| #62 | 제목에서 **`Layer B —`** 제거 |
| #63 | 제목에서 **`Layer C —`** 제거 |

### 8.6 이력만 기록 (1건)

#6 구성종목 등락률 — 2026-08-19 에 §5 신규 생성 시도를 §2 기존 항목에 병합한 이력.
**`DUPLICATE` 건수에는 넣지 않는다**(설계 확정).

### 8.7 보류 — `UNKNOWN` (1건)

#66 PC package fallback — **PC 실측 전까지 판정 보류**

### 8.8 원장 자체 정합 보정 (2건)

| 항목 | 보정 |
|---|---|
| 섹션 `14. Layer 활성 관리 (ASSUMPTIONS 연계)` | 실제 연계 대상은 `Layer A` 뿐 → 섹션명에서 `Layer` 제거 또는 연계 대상 정정 |
| 문서 서식 예시(L6 `- **항목**: 한 줄 요약`) | 항목 카운트에 섞여 **원시 68 / 실제 67** 혼동을 만든다 |

---

## 9. 65 → 67 증가분 이력

`git show <sha>:docs/backlog/BACKLOG.md | grep -c "^- \*\*항목\*\*"` 실측
(원시 카운트는 서식 예시 1건 포함 → 실제 = 원시 − 1):

| 커밋 | 날짜 | 원시 | 실제 | 증감 |
|---|---|---|---|---|
| `35d718f0` | 2026-08-01 | 66 | **65** | 기준점(Canonical Alignment) |
| `c9abd4eb` | 2026-08-03 | 69 | **68** | **+3** |
| `6d818d4d` | 2026-08-16 | 68 | **67** | **−1** |
| `2033d221` | 2026-08-16 | 68 | 67 | 0 (문구만) |
| `004517f8` | 2026-08-20 | 68 | 67 | 0 (제목 변경) |
| `HEAD` | 2026-08-21 | 68 | **67** | — |

**추가 3건 — `c9abd4eb`(POC3-05 Closeout, 2026-08-03)**

| 항목 | 사유 | B-ID |
|---|---|---|
| 급락 후보 안정적 latest 읽기 GET 계약 (POC3-05 §13.1) | Closeout 이월 | **신규** |
| 보유 ETF 종합 위험 구간 분류 (POC3-05 §13.2) | Closeout 이월 | B-001 계열 |
| 그리드(테이블) 디자인 완성도 개선 | 사용자 실화면 지적(2026-08-02) | **신규** |

**제거 1건 — `6d818d4d`(2026-08-16)**

`holdings ticker 형식 검증 강화` → **POC3-08 (A) 에서 구현됨**
(`app/holdings.py:45` `TICKER_PATTERN = ^[0-9A-Z]{6}$`)

**제목만 변경 3건**: 종목명 자동 조회 → 개별주 잔여분(`6d818d4d`) ·
그리드 디자인 → 컬럼 프리셋 잔여분(`6d818d4d`) ·
구성종목 가격 시계열 → 구성종목 등락률(`004517f8`)

**`+3 −1 = +2` 로 완전히 설명된다. 미확인 증가분 없음.**

---

## 10. B-ID 대응 — §2 원장표 2열에 포함

`POC3-00_PC_JUDGMENT_UI_INTEGRATED_IMPLEMENTATION_MAP_V2.md` §6 `B-001~B-105` 기준.
**67건 중 65건 대응 · 2건(#4·#46)은 그 이후 신규 추가분**(§9).

**교차 검증**: `LeftSidebar.tsx:15` 주석이 **`B-057` 을 직접 인용**
(*"접힘 영구저장은 B-057 보류 유지"*) → 원장표의 `#44 → B-057` 과 일치.

**섹션 번호는 재번호하지 않았다.**

---

## 11. 남은 `UNKNOWN` 1건과 필요한 실측

| ID | 항목 | 확인 주체 | 확인 조건 |
|---|---|---|---|
| #66 | PC package fallback 경로 재활성화 | **사용자(PC)** | 아래 5개 |

1. 설정된 package 경로 — `app/three_push_package_exporter.py` 경로 상수
2. `state/three_push/` 존재 — `ls -la state/three_push/`
3. 최근 artifact·수정 시각 — `ls -lt state/three_push/packages/ | head`
4. exporter 실제 호출자 — `grep -rn "three_push_package_exporter" app/ scripts/`
5. 현재 운영의 fallback 사용 여부 — 최근 운영 로그의 package 경로 참조

**맥 관찰(참고)**: `state/three_push/` 없음. 코드는 `three_push_package_exporter.py:7`
에서 그 경로에 쓰도록 되어 있다. **맥은 운영기가 아니므로 결함이라 판정하지 않는다.**
디렉터리 생성·package 실행·환경 설정 변경 **하지 않았다.**

---

## 12. 완료 조건 대조 (R2 지시문 1~10)

| 지시 | 결과 |
|---|---|
| 1. 67개를 정확히 67행으로 | **완료** — §2, 기계 검증 `grep -cE "^\| #[0-9]+ \| \`"` = **67** |
| 2. 행마다 원장번호/B-ID/항목명/분류/근거/처리 | **완료** — 6열 |
| 3. 동일 원장번호가 두 분류에 등장하지 않도록 **기계적 중복 검사** | **완료** — 분류를 딕셔너리 단일 정의로 두어 **구조적으로 불가능**. `assert set(nums) == set(C)` 통과(§7) |
| 4. 설계자 확정 분류 반영 | **완료** — §0.3 |
| 5. 원장 밖 결함을 별도 표로 분리·합계 제외 | **완료** — §4 |
| 6. #4·#33·#43·#45 완료 근거 계약 단위 보강 | **완료** — 보강 결과 **4건 전부 완료가 아님이 드러나 판정 철회**(§0.2) |
| 7. 모든 집계표·처리 목록을 67행 표와 일치하게 재계산 | **완료** — §1·§8 전부 같은 딕셔너리에서 파생 생성 |
| 8. 코드·BACKLOG·STATE·ML 무변경 | **완료** — §13 |
| 9. 기존 결론본을 R2 전체 통합본으로 갱신 | **완료** — 본 문서가 같은 파일을 대체 |
| 10. commit·push 하지 않음 | **준수** |

---

## 13. 금지사항 준수

코드 수정 0 · ML 실행 0 · 기능 구현 0 · 외부 데이터 호출 0 · 운영 write 0 ·
`BACKLOG.md` 수정 0 · `STATE_LATEST` 변경 0 · 다음 기능 Step 착수 없음 ·
factor·label·threshold·source 신규 결정 없음 · **commit·push 미수행**.

**검증자 전달**: 설계자 재판정 후. 검증 범위는 67행·1항목 1분류 · 집계 일치 ·
B-ID 대응 · 완료 후보 계약 근거 · 65→67 Git 이력 · Layer B/C 근거 · FDR 운영 호출 근거 ·
코드·BACKLOG·STATE·ML 무변경.
