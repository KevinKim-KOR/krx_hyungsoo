# BACKLOG

POC 1단계부터 누적된 의도적으로 미룬 항목.
**Step5 진입 전 정돈 (2026-04-30)**: 완료된 항목은 CLOSED / RESOLVED 로 이동, ML / polling / 메시지·채널 / snapshot 관련 중복 항목 4개 통합, Step5 영향 항목 5개를 ACTIVE REVIEW BEFORE STEP5 로 분리. **항목 삭제는 하지 않았다.**

**Step6 종료 + Step7 진입 전 정돈 (2026-05-11)**:
- ASSUMPTIONS Q5 가 BACKLOG 로 이관되어 본 문서에 "AI 토론 점수체계 검증" 항목으로 등록.
- 와이프 UI 이해도 검증 항목이 BACKLOG 로 신규 등록 (PROJECT_ORIGIN_INTENT 의 장기 성공 기준은 보존).
- OPEN 6개 항목을 **Layer A / B / C 3단계로 분류** — Layer A 는 ASSUMPTIONS 활성 관리, Layer B 는 BACKLOG + 향후 코드 주석 대상, Layer C 는 ML 단계 보류.

각 항목은 다음 포맷을 따른다: 발생 맥락 / 현재 결정 / 재검토 예정 / 트리거.

---

## FDR + SQLite Market Data Foundation 후 신규 (2026-05-15)

B 방향 PC 작업 1~2단계 구현 (FinanceDataReader ETF universe + SQLite market_data 저장소)
완료 후 도출된 BACKLOG 항목.

### BACKLOG: 판단 근거 저장 (decision evidence)
- **사용자 요구 (유지)**: 향후 투자 결과를 판단한 근거를 저장해야 한다. 그래야 과거
  판단과 며칠 뒤 결과를 비교할 수 있다.
- **보류 사유**: 시장 데이터 저장소 안정화 전 판단 근거 저장까지 넣으면 범위가 커진다.
  본 STEP 에서는 etf_master / etf_daily_price / market_refresh_log 3 테이블만 도입.
  `decision_evidence` 테이블 / writer / AI 투자세션 대화 저장 / approval 상태 저장 /
  Telegram message 저장 / Run 상태 저장은 모두 **이번 STEP 에서 명시적 금지**.
- **보류된 위험**: 과거 판단과 이후 성과를 연결하지 못하면 AI 투자 시스템의 학습
  자산이 약해진다.
- **재검토 트리거**: PC ETF Universe TOP N 화면에서 사용자가 AI 투자세션에 1회 이상
  가져가고, 매수 / 매도 / 보류 중 하나의 판단을 남긴 시점.
- **연결**: 별도 STEP 으로 분리 — `decision_evidence` 테이블 스키마 + writer + 사용자
  판단 hook 지점 + 비교 리포트 도입은 본 STEP 종료 후 별도 설계.

### BACKLOG: FDR 외부 의존 약관 / 안정성 / 호출 빈도 제한 / 단일 호출 timeout 부재 검토
- **보류 사유**: FinanceDataReader 는 비공식 데이터 출처 (네이버/Investing 등 스크래핑
  추정) 기반. 본 STEP 에서는 가능성 확인 PASS 후 채택만 결정하고 약관 / 안정성 /
  호출 빈도 / 차단 위험 검토는 별도 진행.
- **보류된 위험 1 (출처 안정성)**: 출처 변경 / 차단 / 의존성 깨짐 시 운영 단절. 본 프로젝트는
  1차 데이터 소스를 FDR 에 두고 KRX OPEN API 를 fallback 으로 유지.
- **보류된 위험 2 (단일 호출 timeout 부재 — 검증자 B-6 NOTE)**: `app/market_data_fdr.py`
  의 `_default_price_fetcher` / `_default_universe_fetcher` 는 단일 호출 timeout 을
  강제하지 않는다. FDR 가 KRX/Naver 응답 hang 시 장시간 차단 가능성. 본 STEP 의
  per-ticker 실패 격리는 예외 catch 만 처리하며 타임아웃 자체는 외부 라이브러리에
  위임된 상태.
- **재검토 트리거**: FDR 호출이 운영 중 1회라도 실패하거나 KRX OPEN API 인증키 승인
  완료 시점 (월요일 이후 예상). 또는 운영 fetch 가 4분 이상 hang 되는 케이스 발생 시.
- **권장 후속 조치 (별도 STEP)**: per-ticker timeout wrapper (`concurrent.futures` /
  `signal.alarm` / `requests` timeout 직접 주입 등) + 운영 중 호출 시간 모니터링.

### BACKLOG: ETF Category 라벨 매핑
- **보류 사유**: `fdr.StockListing("ETF/KR")` 응답의 Category 컬럼은 정수 코드
  (예: 1, 2, 4). 라벨 매핑 (예: 1=국내주식, 4=해외주식 등) 은 별도 정의 필요.
- **연결**: B 방향 §3 의 섹터/테마 발굴 시 Category 활용 가능 — TOP N 화면 구현 STEP
  에서 함께 처리.

### BACKLOG: SQLite 영구 보존 운영 정책
- **보류 사유**: 본 STEP 의 `state/market/market_data.sqlite` 는 .gitignore 처리 (운영
  데이터 / 바이너리). PC 환경 간 동기화 / 백업 / OCI 배포 환경 SQLite 위치 / TTL 정책
  미정.
- **재검토 트리거**: OCI 일 3회 자동 PUSH 연결 STEP 또는 PC ↔ OCI 데이터 동기화 필요
  시점.

---

## STEP7C 완료 후 신규 (2026-05-12)

POC2-Step7C 완료 — 급락 ETF 주의 신호 (PUSH 3) 최소 구현 후 도출된 BACKLOG 항목.

### BACKLOG: 급락 임계값 검증
- **보류 사유**: Step7C 의 `FALLING_THRESHOLD_PCT = -10.0` 은 초기 운영값이며
  백테스트로 검증되지 않았다.
- **보류된 위험**: 너무 민감하면 알림 과다 (KS-5), 너무 둔하면 급락 신호가 늦게 나옴.
- **복귀 조건**: 급락 ETF 주의 신호가 2회 이상 발생하거나, 급락 후보가 전혀 나오지 않아
  기준 조정 필요성이 생길 때.
- **연결**: Layer B 의 "급락 임계값" 기존 항목과 통합 처리. Step7C 가 첫 구현이지만
  임계값은 여전히 미확정.

### BACKLOG: 급락 기준 기간 비교
- **보류 사유**: Step7C 는 1개월 수익률을 재사용한다.
- **보류된 위험**: 급락은 1개월보다 짧은 기간에서 더 잘 포착될 수 있다.
- **복귀 조건**: 사용자가 "이미 많이 빠진 뒤에야 신호가 나온다" 고 느끼는 경우.
- **연결**: ASSUMPTIONS Q4 Layer A "시간 측정 기간" 과 함께 검토 — 1일/1개월/60일/120일.

### BACKLOG: 급락 신호 UI 고도화
- **보류 사유**: Step7C 는 message_text 최소 신호 단계. UniverseRefreshPanel 의 ⚠ 1줄
  안내가 현재 UI 의 전부.
- **보류된 위험**: Telegram 만으로는 급락 근거를 충분히 보기 어려울 수 있다.
- **복귀 조건**: 사용자가 급락 후보의 가격 흐름을 UI 에서 더 보고 싶다고 명시할 때.

---

## STEP7B 완료 후 신규 (2026-05-12)

POC2-Step7B 완료 — 보유 종목 상태 브리핑 (PUSH 1) 최소 정리 후 도출된 BACKLOG 항목.

### BACKLOG: 보유 종목 상태 브리핑 상세 UI
- **보류 사유**: Step7B 는 Telegram/message_text 최소 정리 단계. 상세 근거 표시는
  별도 작업.
- **보류된 위험**: Telegram 요약 1줄만으로는 특정 보유 종목의 상태 근거 (어떤 비중,
  어떤 점검값) 를 보기 어려움.
- **복귀 조건**: 사용자가 특정 보유 종목의 상태 근거를 더 보고 싶다고 명시할 때.
- **참조**: docs/handoff/POC2_STEP7B_HOLDINGS_STATUS_BRIEFING_MINIMAL_PUSH.md §7.

### BACKLOG: 보유 점검 산식 개선
- **보류 사유**: 현재 holdings momentum 은 placeholder 성격의 점검값 (= pnl_rate).
  Step7B 는 사용자 노출 표현만 정정했지 산식 자체는 그대로.
- **보류된 위험**: 점검값이 실제 투자 판단 품질을 충분히 설명하지 못할 수 있음.
- **복귀 조건**: 보유 상태 브리핑 운영 후 점검값이 사용자 판단에 도움이 되지 않는다고
  사용자가 명시 확인할 때.
- **연결**: 기존 BACKLOG "무릎/머리/어깨 정량 기준" (Layer B) 항목과 함께 검토.

---

## STEP7 설계서 저장 후 신규 (2026-05-11)

POC2-Step7 (System Output 3-Push Realignment Design) 설계서 도출 항목. 본 STEP 에서
처리하지 않고 후속 구현 Step 또는 별도 작업으로 분리되는 항목들.

### BACKLOG: manual seed 입력 UX 개선 (seed 편집 UI)
- **보류 사유**: Step6 의 manual universe seed JSON 입력은 사용자 작성 부담이 큼.
  Step7A 에서 starter seed 가 도입되어 첫 진입 장벽은 해소되었으나, 사용자가 후보군을
  변경하려면 여전히 파일 직접 수정 또는 starter seed 삭제 후 재작성이 필요.
- **보류된 위험**: 후보군 변경 부담이 운영 사이클 지속성을 떨어뜨릴 가능성.
- **복귀 조건**: 사용자가 운영 중 후보군 직접 수정 필요 상황을 1회 이상 보고할 때 또는
  PUSH 2 두 번째 구현 라운드 진입 시.
- **자동 universe 수집과의 관계**: 자동 수집은 별도 BACKLOG 항목으로 분리. seed 편집
  UI 는 수동 후보군 관리 UX 만 다룬다.

### BACKLOG: 기본 ETF starter seed (Step7A 부분 도입 + 향후 확장)
- **현재 상태 (2026-05-11, Step7A)**: 최소 fallback 으로 starter seed 도입 완료
  (`app/universe_seed.py:STARTER_SEED_ITEMS`).
  · 후보 3개: KODEX 200 (069500) / KODEX 미국S&P500 (379800) / KODEX 미국나스닥100 (379810).
  · seed 파일 부재 시 `ensure_seed_file_exists()` 가 생성. 기존 사용자 seed 절대 덮어쓰지 않음.
  · API 응답에 `summary.source` 로 노출하여 UI 안내 가능.
- **보류된 확장 (향후 STEP 후보)**:
  · 후보 종목 확장 — 3개 → N개 (사용자 운영 결과 기반).
  · "예시 목록" 라벨링 — UI 에서 starter seed 가 매수 추천이 아님을 시각적으로 더
    명확히 (현재는 안내 문구로만).
- **보류된 위험**: starter seed 의 종목 선택이 장기 운영 후보군으로 굳어져 매수 추천처럼
  해석될 가능성 — 현재는 UI 안내 문구로 mitigation.
- **복귀 조건**: 신규 ETF 관찰 후보를 2회 이상 운영하면서 후보군 관리가 병목으로 재확인
  될 때 또는 사용자가 starter seed 종목 변경을 명시 요청할 때.

### RESOLVED: 급락 ETF 주의 신호 최소 구현 (PUSH 3 구현 Step) — Step7C 완료 (2026-05-12)
- **이전 보류 사유 (Step7 설계서 시점)**: PUSH 3 는 자리만 잡고 구현 없음. 급락 임계값
  확정 필요.
- **해결 (commit d7075bfd, Step7C)**: 기존 pykrx 1개월 수익률 (Step6) 재사용 +
  score_value <= -10.0 후보를 결정론적 tie-breaker (score ASC → ticker ASC →
  candidate_id ASC) 로 1건 선택 + 신호 없음 시 message_text bullet 미생성 (KS-5).
- **잔존 BACKLOG (Step7C 종결 시점)**:
  · 급락 임계값 검증 (-10.0% 확정값 아님) — 별도 항목으로 STEP7C 신규 섹션에 등록.
  · 급락 기준 기간 비교 (1개월 외 단기) — STEP7C 신규 섹션.
  · 급락 신호 UI 고도화 — STEP7C 신규 섹션.
- **참조**: docs/handoff/POC2_STEP7C_FALLING_ETF_CAUTION_SIGNAL_MINIMAL_PUSH.md.

### BACKLOG: 운영 빈도 문서 정합성 보정
- **보류 사유**: PROJECT_ORIGIN_INTENT §7 의 "1일 3회 PC 분석" 과 Step7 §7 의
  "K6/EOD 저빈도" 표현이 충돌 소지.
- **보류된 위험**: 두 표현이 공존하면 후속 STEP 설계에서 운영 빈도 결정이 흔들림
  (KS-11 의사결정 24시간 룰 가드 발동 가능).
- **복귀 조건**: PUSH 1 / 2 / 3 중 첫 구현 Step 진입 직전 문서 정합성 보정 작업 1회.

### BACKLOG 보강 — 기존 항목과의 관계 (중복 추가 회피)
- "무릎/머리/어깨 정량 기준" (Layer B 기존) → Step7 §9.4 와 동일 항목 — 본 STEP 에서
  중복 추가하지 않음. 복귀 조건만 보강: PUSH 1 구현 Step 진입 + 백테스트 또는 운영
  데이터 1개월 누적.
- "급락 임계값" (Layer B 기존) → 본 STEP "급락 ETF 주의 신호 최소 구현" 의 하위
  항목으로 간주. PUSH 3 구현 Step 진입 시 함께 처리.
- "시간 측정 기간" (Layer A 기존) → Step7 §9.5 "기간 비교 정책" 과 동일 항목 — 본
  STEP 에서 중복 추가하지 않음. ASSUMPTIONS Q4 활성 관리 그대로 유지.
- "RS / 거래량 / 정배열 등 복합 지표 기준값" (Layer C 기존) → Step7 §9.6 과 동일
  항목 — 본 STEP 에서 중복 추가하지 않음. ML 단계 보류 그대로 유지.

---

## STEP6 종료 후 신규 (2026-05-11)

### BACKLOG: AI 토론 점수체계 검증 (이전 ASSUMPTIONS Q5)
- **보류 사유**: 시스템 PUSH → AI 투자세션 → 사용자 결정 사이클이 아직 운영 데이터로 검증되지 않았다. 검증 트리거는 운영 시작 이후에야 도달한다.
- **보류된 위험**: AI 토론이 실제 의사결정 품질을 높이는지, 단순히 말만 늘리는지 판단할 수 없다.
- **복귀 조건**: 운영 시작 후 시스템 PUSH 를 받고, AI 투자세션을 거쳐 첫 매매 결정 또는 명시적 보류 결정 1회가 발생할 때.
- **자동 점검 시점**: Step 종료 시점 / 월간 ASSUMPTIONS 검토 / 첫 운영 월 종료 시점.
- **복귀 시 조치**: ASSUMPTIONS 활성 질문으로 재승격하고, Q5 또는 신규 번호로 재등록한다.
- **주의**: 시스템 본질 차별화 가설이라는 위상은 유지한다.
- **이력 보존 (Step6 첫 실전 검증 기록 — 2026-05-11)**:
  · 첫 실전 라운드 완료: GPT(설계자 역할) + Gemini(레드팀 역할) + Claude(조언자 역할) 토론으로 시스템 출력 정의 도출.
  · AI 투자세션을 별도 운영 채널로 확정 (PC 시스템과 분리). 사이클: 시스템 PUSH → AI 투자세션 토론 → 사용자 결정.
  · Step6 채택값: pykrx 기반 1개월 기간 수익률 (one_month_return_pct) — 단일 가격 기반 변수. 후보 비교 — 수동 seed recent_return_pct (보수적 → 기각) / 당일 등락률 (노이즈 → 보류) / manual_score (근거 약함 → 보류) / pykrx 기간 수익률 (채택).
  · 친구식 복합 점수체계 (MA / RSI / 고점 / 보너스) 가 아니라 사용자가 이해 가능한 단일 변수로 시작.
  · 검증 대상 명시: 사용자 본인. 와이프는 UI 가독성 검증 대상이며 본 항목의 검증 대상이 아니다.
- **참조**: docs/ASSUMPTIONS.md L-3 (포인터).

### BACKLOG: 와이프 UI 이해도 검증
- **보류 사유**: 1차 검증자는 사용자 본인이다. 사용자가 운영 흐름을 이해하지 못하면 와이프 UI 검증은 의미가 없다.
- **보류된 위험**: 장기 성공 기준인 "와이프가 이해할 수 있는 UI" 가 뒤로 밀리며 UI 가 사용자 전용으로 굳어질 수 있다.
- **복귀 조건**: 사용자 본인이 시스템 PUSH 수신 → AI 투자세션 → 매매 결정/보류 사이클을 반복 운영 가능하다고 판단한 시점.
- **자동 점검 시점**: 운영 첫 달 종료 시점 / 사용자가 "이제 운영은 된다" 고 명시한 시점.
- **복귀 시 조치**: 와이프 대상 UI 이해도 검증을 별도 Step 또는 체크리스트로 재개한다.
- **주의**: PROJECT_ORIGIN_INTENT.md 의 장기 성공 기준 "와이프가 이해할 수 있는 UI" 는 삭제하지 않는다. 본 항목은 검증 시점만 뒤로 미루는 결정이다.

---

## OPEN 항목 Layer 분류 (2026-05-11)

설계자 임의 확정 금지 6개 항목을 검증 트리거 위상별로 분류한다.

### Layer A — ASSUMPTIONS 활성 관리

운영 첫 달 데이터로 검증할 핵심 질문. ASSUMPTIONS Q4 에서 직접 관리.

- **발굴 단위 세부**
  - 현재 위치: ASSUMPTIONS Q4
  - 현재 초기값: 잘 오르는 ETF
  - 확정 여부: **확정 아님**
  - 복귀/검증 조건: 운영 첫 달 PUSH 결과가 실제 행동/보류 판단으로 연결되는지 확인.
- **시간 측정 기간**
  - 현재 위치: ASSUMPTIONS Q4 하위 관리
  - 현재 초기값: Step6 기준 pykrx 1개월 수익률
  - 확정 여부: **확정 아님**
  - 복귀/검증 조건: 1개월 외 기간 비교 필요성이 운영 중 발생하거나 백테스트 설계 시점 도래.

### Layer B — BACKLOG + 향후 코드 주석 대상

향후 코드 구현 시점에 진입하지만 임의 값으로 확정하지 말 것. 코드 도입 시 주석 표준 부착.

- **무릎/머리/어깨 정량 기준**
  - 보류 사유: 보유 종목 상태 브리핑 (PUSH 1) 을 더 정교하게 만들려면 필요하지만 아직
    백테스트/운영 데이터 없음. Step7B 는 "기준 도입" 이 아니라 "사용자 노출 명칭 정렬"
    단계였음.
  - 보류된 위험: 임의 기준을 쓰면 매수/매도 의견처럼 보이는 신호가 됨 (Step7 §3 투자
    행동 지시 금지 원칙 위반 위험).
  - 복귀 조건 (Step7B 종료 시점 보강 — 2026-05-12): 보유 상태 브리핑을 2회 이상 운영한
    뒤 사용자가 "그래서 현재 위치가 좋은지 나쁜지 모르겠다" 고 느끼는 경우.
  - **코드 주석 표준**: "확정값 아님 / 백테스트 검증 필요"
- **급락 임계값**
  - 보류 사유: 급락 ETF 경고 기준이지만 임계값 미검증.
  - 보류된 위험: 너무 민감하면 알림 과다, 너무 둔하면 경고 실패.
  - 복귀 조건: 급락 ETF 경고 설계 Step 진입 시.
  - **코드 주석 표준**: "확정값 아님 / 백테스트 검증 필요"
- **보유 점검과 외부 발굴 가중치**
  - 보류 사유: 보유 의견과 신규 ETF 추천의 상대 우선순위를 아직 운영으로 판단하지 못함.
  - 보류된 위험: 시스템 PUSH 우선순위가 사용자 의사결정 흐름과 어긋날 수 있음.
  - 복귀 조건: 3-PUSH 구조가 실제로 1회 이상 운영되고, 알림 우선순위 충돌이 발생할 때.
  - **코드 주석 표준**: "확정값 아님 / 운영 검증 필요"

### Layer C — ML 단계 보류

ML / 백테스트 인프라가 준비되기 전에는 진입 자체를 금지.

- **RS / 거래량 / 정배열 등 복합 지표 기준값**
  - 보류 사유: 친구식 복합 점수체계로 회귀할 위험이 있음.
  - 보류된 위험: 단순한 시스템을 만들기 전에 복합 지표가 들어오면 해석성과 운영성이 무너짐.
  - 복귀 조건: 단일 가격 기반 변수 운영 결과가 부족하다는 증거가 쌓이고, 백테스트 인프라가 준비된 뒤.
  - 자동 점검 시점: ML / 백테스트 Step 진입 전.
  - **주의**: 지금 Step7 또는 3-PUSH 재정렬 설계에서 확정하지 않는다.

---

## CLEANUP CANDIDATES (Step5D 이후 — 다음 Cleanup 또는 기능 STEP 진입 전 검토)

다음 Cleanup STEP 진입 시 우선 검토 항목 (Step5D 에서 처리하지 않은 KS-10 트리거 충족 / 근접 항목).

### CLEANUP NEXT: tests/test_holdings_draft_flow.py 추가 분리
- 트리거 충족 (Step5D 종료 시점, 2026-04-30): 1,982 라인. KS-10 트리거 1 (테스트 파일 1,500라인 초과 + 여러 STEP 의 테스트가 섞임) 충족.
- 분리 후보:
  · tests/test_holdings_input.py (Step1 holdings put/get/validation)
  · tests/test_market_naver_enrich.py (Step2 시세/enrich)
  · tests/test_draft_message_step2b.py (Step2B 메시지 요약/길이 방어)
  · tests/test_account_group.py (Step2C account_group)
  · tests/test_message_text_step2d.py (Step2D message_text 단일 소스)
- 처리 원칙: Step5D 와 동일 — 의미 / 검증 강도 / 동작 변경 0건, fixture / 헬퍼는 conftest.py / _helpers.py 활용.
- **RESOLVED (2026-05-08, Step5D-2 Cleanup)**: tests/test_holdings_draft_flow.py 가 244라인 (KS-10 트리거 1 미만)으로 축소됨. 분리 결과:
  · tests/test_holdings_draft_flow.py — holdings draft 핵심 happy path + 검증 (244라인)
  · tests/test_holdings_market_enrichment.py — market_cache + Naver fetch + enrich (504라인)
  · tests/test_holdings_message_text.py — Step2B/Step2D draft_message + handoff (924라인)
  · tests/test_holdings_account_group.py — Step2C account_group (334라인)
  pytest 119 passed 그대로 유지 — 의미 / 개수 / 검증 강도 변경 0건.

### CLEANUP NEXT: RunPanel.tsx 추가 분리 (EvidenceDetails)
- 트리거 충족 (Step5D 종료 시점, 2026-04-30): 905 라인. KS-10 트리거 3 (프론트 컴포넌트 900라인 초과) 충족.
- 분리 후보:
  · frontend/app/components/EvidenceDetails.tsx (현재 RunPanel.tsx 안의 EvidenceDetails + CompactHoldingsTableStandalone + 관련 helper)
- 처리 원칙: 렌더링 결과 / 문구 / 배치 / 동작 / message_text 동일.
- **RESOLVED (2026-05-08, Step5D-2 Cleanup)**: RunPanel.tsx 905 → 606라인 (KS-10 트리거 3 미만). 분리 결과:
  · frontend/app/components/EvidenceDetails.tsx — EvidenceDetails + CompactHoldingsTableStandalone + CompactHoldingsTable + CompactRow + DetailRowFields + AccountSummaryCards + KV + groupByAccount (343라인)
  · RunPanel.tsx 가 helper / type 14개를 named export 로 노출 (NormRec / Summary / AccountSummary / toFiniteNumber / fmtMoney / fmtSignedMoney / fmtPct / fmtSignedPct / pnlClass / normalizeRec / isPriced / isCalcAvailable / rowKey / computeSummaryFor / OverallSummaryCard) — EvidenceDetails 가 import.
  렌더링 / 문구 / 배치 / 동작 / message_text 모두 동일.

### CLEANUP NEXT: frontend/app/components/HoldingsClient.tsx 분리 — **KS-10 트리거 3 충족 (미해소)**
- **실측 (2026-05-08, Step5D-2 종료 시점 정정)**: 906 라인. KS-10 트리거 3 (프론트 컴포넌트 900라인 초과) **충족 상태**. 직전 보고서들의 "832 라인" 수치는 측정 없이 이전 STEP 의 추정값을 그대로 보고한 결과 — 정정.
- 변경 이력: git log 기준 마지막 변경은 commit 310bedc5 (Step2C, account_group 도입) — 이후 본 STEP 작업과 무관하게 906 라인 유지.
- Step5D-2 미처리 사유: 본 STEP §4.3 "관찰만 할 파일" 로 명시 분류되어 있었음. AC-19 "새 기능 / 분리 0건" 정책에 따라 추가 분리 안 함.
- 분리 후보 (잠정): EnrichedSection / OverallSummaryCard / AccountSummaryCards 를 RunPanel 의 동등 컴포넌트와 공용화 (BACKLOG "프론트 compact UI 공용 모듈 추출" 항목과 합쳐서 처리).
- **RESOLVED (2026-05-10, Step5D-2 Final Round)**: HoldingsClient.tsx 906 → 394라인. 분리 결과:
  · frontend/app/components/EnrichedHoldingsSection.tsx — EnrichedSection (default) + 8개 자식 컴포넌트 + 로컬 helpers (Summary/AccountSummary/isPriced/isCalcAvailable/computeSummaryFor/groupByAccount/rowKey, EnrichedHolding 기반) (515라인)
  · HoldingsClient.tsx 잔존 책임: 입력 폼 + 시세 갱신 / 저장 / 초안 생성 액션. fmt 5종 중복 제거 (lib 사용), DEFAULT_GROUP 도 lib 사용.
  렌더링 / 펼침 상태 유지 / [시세 갱신] 버튼 동작 / message_text 모두 동일. pytest 119 + frontend lint + build PASS.

### CLEANUP NEXT: app/draft_message.py 메시지 렌더링 책임 분리
- **실측 (2026-05-08)**: 600 라인. KS-10 트리거 4 (백엔드 핵심 모듈 650라인) 미달이나 근접. 직전 보고서의 "472 라인" 수치는 측정 없는 추정값으로 정정.
- _factor_bullet / _momentum_bullet / 길이 방어 / 요약 빌더 / 주목 종목 빌더가 한 모듈에 모임.
- 분리 후보 (잠정): app/draft_message/__init__.py + judgment.py + summary.py + focus.py + length_guard.py 식 패키지화.
- 처리 원칙: 출력 message_text 동일, [판단 사유] 헤더 1번 정책 유지.
- **PARTIAL RESOLVED (2026-05-10, Step5D-2 Final Round)**: draft_message.py 600 → 525라인 (트리거 4 미달 + 근접 50라인 이내 해소). 분리 결과:
  · app/message_helpers.py — leaf-level format / 항목 식별 helpers (_to_finite_float, _format_money/_format_pct/_format_signed_money/_format_signed_pct, _is_priced/_is_calc_available/_is_default_hold/_item_label, DEFAULT_HOLD_REASON) (124라인)
  · draft_message.py 잔존 책임: is_holdings_draft / compute_summary / select_focus_items / _factor_bullet / _momentum_bullet / _render_judgment_lines / _build_with_focus_limit / build_message_text + 정책 상수 (MAX_LENGTH_CHARS / TRUNCATION_NOTICE / TOP_N_*).
  공개 API (is_holdings_draft / compute_summary / build_message_text / DEFAULT_HOLD_REASON / MAX_LENGTH_CHARS) 동일 import 경로 유지 — 호출자 변경 0건.
  message_text 출력 / [판단 사유] 헤더 1번 정책 / 2 bullets 모두 동일. pytest 119 + black + flake8 PASS.
  추가 분리 (judgment / summary / focus / length_guard 패키지화) 는 KS-10 근접 해소 기준 충족됐으므로 본 라운드에서 더 진행하지 않음. 향후 Step 진입 시 책임 누적 재발 시 재검토.

### CLEANUP NEXT: app/api.py 라우터 분리
- **실측 (2026-05-08)**: 557 라인. KS-10 트리거 4 미달이나 근접. 직전 보고서의 "465 라인" 수치는 측정 없는 추정값으로 정정.
- runs / holdings / market / universe 라우터가 한 모듈에 모임.
- 분리 후보 (잠정): FastAPI APIRouter 패턴으로 app/api/__init__.py + runs.py + holdings.py + market.py + universe.py 분리.
- 처리 원칙: endpoint 경로 / 응답 스키마 동일, OCI handoff 경로 변경 0.
- **2026-05-10 (Step5D-2 Final Round) 재측정**: 557 라인 유지. KS-10 트리거 4 (650) 미달, 근접(>=600) 미달 — 본 라운드 처리 대상 외 (트리거 / 근접 모두 0건). 책임 누적 재발 시 재검토.

### CLEANUP NEXT: RunPanel.tsx ↔ EvidenceDetails.tsx 양방향 import 정돈
- 발생 맥락 (2026-05-08, Step5D-2): RunPanel.tsx 가 EvidenceDetails 의 default export 를 import 하고, EvidenceDetails.tsx 가 RunPanel 의 helper / type 14개를 named export 로 import. 빌드 / lint 통과 상태이며 JS/TS 의 named export 는 정적으로 해결되어 동작 위험은 없음.
- 다만 Cleanup 목적상 양방향 의존은 부채. 검증자 NOTES B-6.
- 분리 후보 (잠정): RunPanel 의 helper / type 을 별도 모듈 (`frontend/app/components/holdings_view_helpers.ts` 또는 `frontend/lib/holdings_view.ts`) 로 추출 → RunPanel + EvidenceDetails 모두 단방향 import.
- 처리 원칙: 추출 후 동작 / 렌더링 / message_text 동일 보장. import 경로만 변경.
- **RESOLVED (2026-05-10, Step5D-2 Final Round)**: frontend/lib/holdings_view.ts (186라인) 신규.
  · DEFAULT_GROUP, fmt 5종 (Money/SignedMoney/Pct/SignedPct/pnlClass), NormRec/Summary/AccountSummary 타입, normalizeRec/isPriced/isCalcAvailable/rowKey/computeSummaryFor.
  · RunPanel.tsx 가 named export 14개를 노출하던 본문 제거 → @/lib/holdings_view 에서 import. EvidenceDetails.tsx 도 동일 lib 에서 import. 양방향 import 해소 (RunPanel → EvidenceDetails 단방향만 잔존).
  RunPanel.tsx 606 → 444라인. 동작 / 렌더링 / message_text 동일. pytest 119 + frontend lint + build PASS.

---

## STEP 6 향후 검토 (Universe Momentum 발전 방향)

POC2-Step6 (Universe Momentum Formula Minimal Scoring) 에서 의도적으로 미도입한 항목.
사용자 운영 결과를 보며 필요성이 확인되면 별도 STEP 으로 진입한다.

### NEXT (Step6 미도입): 비동기 universe refresh
- 발생 맥락: Step6 의 POST /universe/momentum/refresh 는 동기 sync API. ticker 별 0.5초
  delay × 최대 20개 + 30초 budget 으로 HTTP 응답 시간 길어질 수 있음.
- 현재 결정: 동기 유지. 사용자 명시 갱신 1회만 호출하므로 운영 부담 작다고 판단.
- 재검토 트리거:
  - seed 후보군이 20개를 넘어야 할 강한 이유가 생길 때
  - 응답 시간 30초가 사용자 경험을 해친다는 명시 피드백 발생 시
  - 백그라운드 워커 도입이 필요한 다른 기능과 함께 진입 시
- 금지 (지금은): background worker / scheduler / async task queue / 자동 재시도.

### NEXT (Step6 미도입): pykrx 가격 히스토리 캐시
- 발생 맥락: Step6 는 매 refresh 마다 pykrx 호출. 같은 ticker 의 같은 기간 데이터를
  반복 호출할 수 있다 (특히 사용자가 짧은 시간 안에 여러 번 refresh 누르면).
- 현재 결정: 캐시 미도입. KS-9 (외부 의존 리스크) 와 KS-10 (단일 책임 누적) 위험 회피.
- 재검토 트리거:
  - 동일 ticker 의 동일 기간 호출이 분당 N회 이상 발생하는 운영 패턴이 확인될 때
  - pykrx 응답 시간이 사용자 경험을 명시적으로 해칠 때
- 금지 (지금은): pykrx 호출 결과 캐싱 / TTL 캐시 / 디스크 캐시.

### NEXT (Step6 미도입): universe 결과 history 저장
- 발생 맥락: Step6 는 latest 1건 덮어쓰기. 날짜별 누적 / Q5 검증용 변수 이력 / 성과
  비교 / AI 해석 로그 모두 미저장.
- 현재 결정: history 미도입. JSON SSOT 유지. DB 도입 금지.
- 재검토 트리거 (Step6 §15 명시):
  - universe momentum 결과를 날짜별로 누적해야 할 때
  - Q5 검증을 위해 변수 변경 이력과 성과를 비교해야 할 때
  - AI 해석 로그와 점수 결과를 연결해야 할 때
- 금지 (지금은): SQLite / PostgreSQL / MongoDB / 날짜별 history 파일.

### NEXT (Step6 미도입): ML dataset 저장 구조
- 발생 맥락: Q5 의 "AI 와 토론해 점수체계를 다듬는 사이클" 의 다음 단계는 ML 학습용
  dataset 일 수 있음. 그러나 Step6 시점에는 변수 1개 (one_month_return_pct) 만
  존재하므로 dataset 구조 선정 보류.
- 현재 결정: 미도입.
- 재검토 트리거: 변수가 3개 이상 안정 운영되고, 사용자가 ML 학습 진입 의지를 명시할 때.
- 금지 (지금은): ML feature store / training pipeline / 학습 데이터 누적.

### NEXT (Step6 미도입): pykrx 외 fallback 데이터 소스
- 발생 맥락: pykrx 단일 의존. pykrx 장애 / API 변경 시 universe refresh 전체 실패.
- 현재 결정: fallback 미도입. KS-9 (외부 의존 리스크) 가드는 candidate 단위 실패 격리 +
  refresh_status="failed" 정상 운영 경로 처리로 대응.
- 재검토 트리거:
  - pykrx 장애가 운영에 명시적 영향 (사용자 불만 발생) 을 줄 때
  - 다른 데이터 소스 (예: 직접 API / 다른 라이브러리) 가 안정성이 높음이 확인될 때
- 금지 (지금은): 다중 데이터 소스 / 자동 fallback / 데이터 소스 결정 트리.

---

## ACTIVE REVIEW BEFORE STEP5

Step5 (Momentum Engine 첫 구현 STEP) 진입 전에 반드시 검토할 5개 항목.
Step5 설계 지시문 작성 시 이 섹션을 1회 정독 후 반영한다.

### ACTIVE: 잘 올라가는 섹터 발굴 Factor
- 발생 맥락: POC2-Step3 첫 factor 후보 검토 중, 현재 후보군은 holdings 분석 factor 중심이며 사용자의 1년 목표인 "잘 올라가는 섹터 발굴"은 별도 축임을 확인. ASSUMPTIONS Q4 로 분리 관리.
- 현재 결정: Step3 에는 포함하지 않음. Step3 는 보유 현황 기반 factor 1개 통합만 수행.
- Step5 반영: Momentum Engine 은 holdings mode 와 universe mode 를 모두 수용할 수 있어야 한다. universe mode 는 보유 여부와 무관한 외부 ETF/섹터 후보 발굴 축이며, "잘 달리는 말 찾기" 는 이 축에서 다룬다.
- Step5 금지: 유니버스 종목 수, 데이터 소스, 산식은 확정하지 않는다.
- 재검토 예정: 현재 Factor 추가 작업 후, 다음 Factor 도입 검토 전.
- 트리거: 보유 종목과 무관한 시장/섹터 후보군 탐색 구조를 설계할 때.

### ACTIVE: Momentum score_result 계약
- 발생 맥락: Step5 가 도입할 Momentum Engine 의 출력 계약(score_result) 이 아직 결정되지 않았다. 점수 / 근거 / 라벨 / 신뢰구간 / 단위 등 필드 구성과 holdings mode / universe mode 의 공통/분기 구조를 미리 박지 않으면 첫 구현에서 다시 흔들릴 위험.
- 현재 결정: 미결. 구체 계약은 Step5 설계 지시문에서 새로 결정한다.
- Step5 반영: holdings mode 와 universe mode 가 같은 score_result 계약을 공유하되, 입력 데이터셋(holdings vs universe) 만 분기되는 형태로 시작 검토. 정확한 필드 / 단위 / 누락 fallback / message_text 반영 방식은 Step5 에서 결정.
- Step5 금지: score_result 의 threshold / 등급 라벨 / Top N / BUY·SELL 매핑 / ML 모델 종류 선확정 금지.
- 재검토 예정: Step5 설계 지시문 작성 시점.
- 트리거: Momentum Engine 첫 구현 진입 직전.

### ACTIVE: factor별 Top N / 랭킹 정책
- 발생 맥락: Step3 message_text 에 모든 종목 factor 사유를 넣으면 Telegram 요약형 정책과 충돌.
- 현재 결정: Step3 에서는 portfolio-level 판단 사유 1줄만 message_text 에 포함한다. 종목 기준 언급은 평가 계산 가능 row 중 max_weight_row 1개로 고정한다.
- Step5 반영: universe mode 는 후보 발굴 결과 자체가 "여러 row" 라 Top N 정책이 자연 발생한다. holdings mode 의 max_weight_row 1개 정책 ↔ universe mode 의 후보 N개 정책의 분기 기준을 Step5 에서 결정.
- Step5 금지: 사용자 노출용 Top N 설정 UI / 환경변수 노출 / 채널별 Top N 분리 — 코드 상수 우선.
- 재검토 예정: 사용자가 Telegram 에서 factor 기준 상위/하위 종목을 더 보고 싶다고 명시할 때.
- 트리거: factor 결과가 늘어나 UI 와 Telegram 표시 범위를 분리해야 할 때.

### ACTIVE: draft_payload.factor_signals 외 다른 메타 키 추가 금지
- 발생 맥락: POC2-Step3 — 설계자가 draft_payload.factor_signals 5번째 키를 Step3 한정 명시 승인. 일반 허용 아님.
- 현재 결정: factor_signals 외 추가 메타 flag(price_missing/calc_missing/risk_score 등) 추가 금지. Run top-level optional 필드 확장도 금지 (Step2D 의 message_text 로 그쳐야 함).
- Step5 반영: Momentum 결과는 기존 factor_signals 안에 새 scope (예: universe scope) 또는 새 factor_id 로 표현하는 방향을 우선 검토. 새 top-level draft_payload 키 / Run 필드 추가는 명시 승인 없이 금지.
- Step5 금지: draft_payload 의 6번째 키 신설 금지 (factor_signals 가 5번째 키이며, 그 안에서 표현).
- 재검토 예정: 새 factor 도입 시 또는 draft_payload 표현 한계가 명확해질 때.
- 트리거: factor_signals 1축으로는 표현이 불가능한 정책 결정이 들어올 때 (예: 실패 사유 분류, 알림 라우팅 메타).
- **Step6 Fix 라운드 확인 (2026-05-11)**: 가드 적용 사례 — Step6 1차 라운드에서 universe
  momentum 결과를 draft_payload.external_universe_check (7번째 키) 로 추가했으나
  검증자(Codex) REJECTED. 사용자(설계자) 결정으로 키 제거 + 기존 factor_signals 안의
  scope="universe" / factor_id="universe_one_month_return" signal 1건으로 재구성.
  Step5B 의 momentum_result 추가가 "명시 승인된 예외" 였다는 점 재확인 — 동일 패턴을
  명시 승인 없이 일반화하지 않는다는 가드의 적용 사례.
- **Step6 Fix 라운드 신규 API 가드 (2026-05-11)**: BACKLOG 본 항목의 정신을 endpoint
  영역으로도 확장. Step6 1차 라운드의 GET /universe/momentum/latest 추가가 검증자 REJECTED.
  Fix 라운드에서 endpoint 제거 + POST refresh 응답 필드 확장으로 UI 요구 충족. 신규
  endpoint 도입은 향후 STEP 지시문이 명시 승인할 때만.

### ACTIVE: ML 기반 초안 생성 / 분석 연결 (CONSOLIDATED)
- 통합 대상 (이전 4개 항목):
  · DEFERRED: ML 기반 초안 생성 연결 (POC1 시점)
  · DEFERRED: ML 기반 draft 생성기 교체 (Step 3 frontend 도입 시점 메모)
  · DEFERRED: ML 기반 실제 초안 생성기 연결 (Step 3 OCI 실연결 시점 재확인)
  · DEFERRED: ML/factor 기반 action/reason 고도화 (POC2 Step 2B 시점)
  · DEFERRED: ML 기반 draft 생성기 연결 (POC2 Step 1 재확인)
- 발생 맥락: draft.py / sample_draft.py 는 정적 stub 기반. backup/backtest/ml/predictive_risk_classifier.py 가 격리 보관 상태이며 POC 루프에 연결되지 않음.
- 현재 결정: ML 연결은 별도 STEP. Step5 (Momentum Engine 첫 구현) 에는 포함하지 않는다 — 정적 점수체계 + AI 토론 해석 사이클이 안정된 후 ML 연결.
- Step5 반영: ML 진입 시점 가드 — Momentum Engine 구조가 들어오는 첫 STEP 에서 ML 을 같이 끌어오지 않는다. 사이클 1회 운영 후 ASSUMPTIONS Q1 (factor 추가 10줄 이내 가능?) 검증 결과를 보고 별도 STEP 으로 진입.
- Step5 금지: Momentum Engine 첫 구현과 ML 학습/예측 동시 진입 금지.
- 재검토 예정: Momentum Engine 사이클 1회 운영 후 ASSUMPTIONS Q1 / Q5 검토 시점.
- 트리거: 사용자가 "추천 점수 / 위험도 / factor" 요구를 명시하고 정적 점수체계로 한계가 드러날 때.

---

## CONSOLIDATED DEFERRED

분류는 항목의 영역별. 한 항목이 여러 분류에 걸칠 경우 가장 본질적인 영역에 둔다.
이번 정돈에서 항목 삭제는 하지 않았으며, 통합 4건은 본 섹션 안에서 별도 표시.

### Momentum / Factor / ML

#### DEFERRED: 추천 로직 / 정렬 로직 / score 도입
- 발생 맥락: POC2 Step 1 — recommendations 의 action 은 모두 HOLD, score 필드 없음
- 현재 결정: 보유 현황 그대로 출력. 추천/정렬 안 함. 매수/매도 판단 안 함
- 재검토 예정: ML 연결 단계 또는 factor 추가 시점 (Step3 에서 첫 factor 통합 — 이후 STEP 에서 score 도입 검토)
- 트리거: 사용자가 "내 보유 종목 중 매도 후보를 표시해 달라" 같은 요구를 제기할 때

#### DEFERRED: 추천 판단 사유 / ML 사유를 메시지에 노출
- 발생 맥락: POC2 Step 1A — recommendations 의 reason 필드는 정적 stub. Step3 에서 portfolio-level factor reason 1줄을 message_text 에 추가했으나 holding_row 별 reason 은 메시지 미노출 정책.
- 현재 결정: action=HOLD 고정 + reason 정적 또는 portfolio-level 1줄. 종목별 추천 판단 로직 0
- 재검토 예정: ML 연결 단계 또는 새 factor 추가 시
- 트리거: reason 이 실제 판단 근거(예: "vol_20d 상승, drawdown_from_peak < -5%") 로 채워질 때

---

### Data Source / Market Cache

#### DEFERRED → 별도 STEP: POC2-Step2A — pykrx EOD fallback 추가
- 발생 맥락: POC2 Step 2 — Naver 1차 소스만 사용. pykrx / yfinance fallback 일체 금지 (설계자 결정 — 스코프 분리. 오늘은 1차 소스 안정성 검증, fallback 은 별도 단계)
- 현재 결정: Step 2 한정 pykrx 금지. 단일 종목 실패는 격리하고 그대로 표시 ("[시세 미확인]")
- 재검토 예정: POC2-Step2A 진입 시점
- 트리거 (모두 충족 시 Step2A 진입 검토):
  - Naver endpoint 가 일정 빈도 이상 timeout / 차단을 일으킬 때
  - 한국 종목 EOD 가 Naver 응답에 누락되는 케이스가 반복될 때
  - 사용자가 운영 중 "어제 종가가 안 나왔다" 류 피드백을 줄 때
- Step2A 채택 조건 (사전 결정):
  - pykrx 의존성 추가에 대한 별도 사용자 승인
  - 캐시/저장 위치 / TTL / 1차→2차 fallback 우선순위 결정
  - holdings 종목 중 일부만 한국 종목인 경우의 처리 정의

#### DEFERRED: Naver endpoint 변경 / 차단 대응
- 발생 맥락: POC2 Step 2 — Naver `m.stock.naver.com/api/stock/{ticker}/basic` 비공식 endpoint 사용
- 현재 결정: 변경 시 단일 종목 실패로 격리 (timeout/http_error/json_decode_error/missing_price 등 reason 캡슐화)
- 재검토 예정: Naver 응답 스키마 변경 / 차단 / 정책 변경 발생 시
- 트리거: refresh 호출 시 모든 종목이 동일 reason 으로 실패할 때

#### DEFERRED: market_cache TTL / 만료 정책
- 발생 맥락: POC2 Step 2 — "최근 조회값 재사용" 수준. TTL 미도입
- 현재 결정: 사용자가 [시세 갱신] 누를 때만 갱신. 캐시값에 만료 표시 없음.
- 재검토 예정: 시세 stale 노출이 사용자 혼란을 야기할 때
- 트리거: 어제 종가가 오늘 화면/메시지에 그대로 표시되어 의사결정에 문제가 될 때

#### DEFERRED: Naver fetch 동시성 / 배치 / rate limit
- 발생 맥락: POC2 Step 2 — fetch_many 는 단순 순차(직렬) 호출. 비공식 endpoint 보호 우선
- 현재 결정: 동시성 도입 안 함. 종목당 5초 timeout × 보유 종목 수 만큼 직렬 소요 가능
- 재검토 예정: 보유 종목 수 증가로 [시세 갱신] 체감 지연이 명확해질 때
- 트리거: 보유 종목 ≥ 10개 + refresh 시간 ≥ 30s 가 일상화될 때

#### DEFERRED: 비-한국 종목 / ETF / 해외 시세
- 발생 맥락: POC2 Step 2 — Naver 한국 시장 endpoint 만 사용. 미국/홍콩 등 미지원
- 현재 결정: 한국 종목 ticker (6자리 또는 ETF 영문 혼합) 만 지원. 해외 종목은 [시세 미확인]
- 재검토 예정: 사용자가 해외 종목 보유 입력 시
- 트리거: holdings 에 해외 종목 ticker 가 들어갔는데 모두 [시세 미확인] 으로 노출될 때

#### DEFERRED: Naver Finance 등 종목명 자동 조회
- 발생 맥락: POC2 Step 1 — 종목명은 사용자 직접 입력 (선택). 미입력 시 ticker 표시
- 현재 결정: 외부 API 호출 미도입. 사용자가 종목명을 알아서 채움
- 재검토 예정: 보유 종목 수가 늘어나 ticker 만으로 식별이 어려워질 때
- 트리거: 사용자가 "종목명 자동 채워줘" 요구 또는 ticker 오타로 인한 잘못된 보유 입력이 반복될 때

#### DEFERRED: 종목명 자동 보정 (사용자 입력 vs Naver 응답 충돌 처리)
- 발생 맥락: POC2 Step 2 — name 우선순위 = 사용자 입력 > Naver stockName > None
- 현재 결정: 사용자 입력이 항상 우선. Naver 응답명과 다르면 알림/경고 없음
- 재검토 예정: 사용자가 오타로 잘못된 종목명을 저장한 사례가 발견될 때
- 트리거: 사용자가 "내 입력명이 종목 실제 이름과 달라 보인다" 피드백 시

#### DEFERRED: holdings ticker 형식 검증 강화
- 발생 맥락: POC2 Step 2 — Naver endpoint 는 6자리 한국 종목 + 일부 ETF 영문혼합 ticker 만 200 응답
- 현재 결정: ticker 형식 사전 검증 없음. Naver 가 200 외 응답 시 [시세 미확인] 으로 표시
- 재검토 예정: 사용자가 ticker 형식 오류를 반복적으로 일으킬 때
- 트리거: refresh 결과 failure reason 이 항상 동일한 종목에서 동일하게 나올 때

#### DEFERRED: market_cache 영속화 위치 / 다중 환경 분리
- 발생 맥락: POC2 Step 2 — 단일 PC 단일 캐시 파일. 다중 환경(PC/NAS/OCI) 동기화 정책 없음
- 현재 결정: state/market_cache/ 는 .gitignore 처리. 환경 간 캐시 공유 안 함
- 재검토 예정: 운영 환경이 PC 외 추가될 때
- 트리거: 다중 환경에서 같은 holdings 에 다른 시세값이 보일 때

#### DEFERRED: refresh 실패 종목의 사용자 안내 / 재시도 UX
- 발생 맥락: POC2 Step 2 — failure list 는 helper 한 줄 텍스트로 노출
- 현재 결정: 종목별 재시도 버튼 / 실패 사유별 안내 / 자동 재시도 미도입
- 재검토 예정: refresh 실패 빈도가 사용자 체감 수준에 도달할 때
- 트리거: 동일 종목이 3회 이상 연속 실패하는 사례 발생 시

#### DEFERRED: Naver 응답 캐싱 헤더 / ETag 활용
- 발생 맥락: POC2 Step 2 — 매 refresh 마다 GET. 304 Not Modified / ETag / Last-Modified 미활용
- 현재 결정: 단순 GET 만 사용. 응답 헤더 무시
- 재검토 예정: refresh 호출 빈도가 늘어 Naver 부담이 우려될 때
- 트리거: refresh 호출 수가 1일 100건 이상 / Naver 응답 지연 발생 시

#### DEFERRED: 시세 표시 정밀도 / 통화 / 단위
- 발생 맥락: POC2 Step 2 — 모든 금액 "원" 고정. 천단위 콤마 + 소수 2자리 라운딩
- 현재 결정: KRW 단일 통화. 외화 / 단가 단위(주당/계약당) 구분 미도입
- 재검토 예정: 해외 종목 / 외화 ETF 보유가 일상화될 때
- 트리거: holdings 에 USD/JPY 등 외화 종목이 들어가면서 통화 혼동 발생 시

#### DEFERRED: enrich 결과를 OCI 측에서 재계산 / 검증
- 발생 맥락: POC2 Step 2 — enrich 책임은 100% 로컬 백엔드. OCI 는 message_text 발송만
- 현재 결정: OCI 가 시세를 재조회 / 검증하지 않음 (POC2 Step 1A 의 책임 분리 원칙 유지)
- 재검토 예정: OCI 와 로컬의 시세 stale 차이가 운영 이슈가 될 때
- 트리거: 사용자가 cron 발송 시각의 시세와 로컬 화면 시세가 다르다고 느낄 때

#### DEFERRED: market_cache 복수 소스 우선순위 / 메타데이터
- 발생 맥락: POC2 Step 2 — price_source="naver" 단일 값
- 현재 결정: 1차 소스 메타만 기록. 멀티 소스 우선순위 / 융합 / 충돌 해결 정책 없음
- 재검토 예정: POC2-Step2A 진입 시 (pykrx EOD fallback 추가 시)
- 트리거: pykrx fallback 도입 결정 시 동시에 결정 필요

#### DEFERRED: GET /holdings/enriched 응답 캐싱 / 조건부 응답
- 발생 맥락: POC2 Step 2 — 매 GET 마다 holdings 로드 + 캐시 결합 + JSON 직렬화
- 현재 결정: 응답 캐싱 / ETag / Last-Modified / If-Modified-Since 미적용
- 재검토 예정: holdings 종목 수가 100+ 로 늘어 GET 응답 시간이 체감 수준일 때
- 트리거: 프론트가 enriched 호출을 자주 트리거하면서 응답 지연이 보일 때

#### DEFERRED: enrichment 단계 로깅 / 감사 추적
- 발생 맥락: POC2 Step 2 — fetch_one / fetch_many 는 logger.warning 으로 실패만 기록
- 현재 결정: 성공 fetch / 캐시 hit-miss / refresh 호출 횟수 등 감사용 로그 없음
- 재검토 예정: 운영 안정화 단계 또는 Naver 차단 의심 시점
- 트리거: refresh 결과의 시간대별 성공/실패 패턴 분석이 필요할 때

#### DEFERRED: 가격 미확인 종목 반복 실패 관리
- 발생 맥락: POC2 Step 2B — 시세 미확인 종목은 [시세 미확인] 표기 + 주목 종목 카테고리에 포함
- 현재 결정: 종목별 누적 실패 카운트 / 자동 알림 / 자동 제외 정책 없음
- 재검토 예정: 동일 종목이 N일 연속 실패할 때 별도 안내가 필요해질 때
- 트리거: 동일 ticker 가 1주일 이상 [시세 미확인] 으로 표기될 때

---

### Holdings Input / Portfolio Structure

#### DEFERRED: holdings 스키마 확장 (평균단가 외 필드)
- 발생 맥락: POC2 Step 1 — 입력 필드를 ticker/quantity/avg_buy_price + name(선택) 으로 제한
- 현재 결정: 매입일자, 메모, 거래소 코드 등 추가 필드 미도입 (Step 2C 에서 account_group 만 추가됨)
- 재검토 예정: 운영 사용 중 동일 종목 여러 계좌 / 여러 매수 시점 분리가 필요해질 때
- 트리거: 사용자가 "같은 종목을 여러 행으로 나눠 입력하고 싶다" 는 요구를 제기할 때

#### DEFERRED: holdings 자동 불러오기 (브로커 API / CSV import)
- 발생 맥락: POC2 Step 1 — 사용자가 행 단위로 직접 입력
- 현재 결정: 자동 import 미구현. 직접 입력만 사용
- 재검토 예정: 보유 종목 수가 10개 이상 / 매일 갱신 부담이 사용자 체감으로 올 때
- 트리거: KIS API / 증권사 OpenAPI / CSV 업로드 요구가 명시될 때

#### DEFERRED: 운영용 holdings 편집 UX 개선
- 발생 맥락: POC2 Step 1 — 행 추가/삭제/저장만 단순 폼으로 제공
- 현재 결정: drag-drop 정렬, 일괄 가져오기, 일괄 삭제, undo 등 미도입
- 재검토 예정: 사용자가 holdings 편집 자주 한다고 보고할 때
- 트리거: 종목 수 증가 또는 사용자 UX 피드백

#### DEFERRED: 복수 포트폴리오 / 계좌 지원
- 발생 맥락: POC2 Step 1 — 단일 사용자 단일 포트폴리오 전제
- 현재 결정: 다중 계좌 / 다중 포트폴리오 미지원 (Step 2C 의 account_group 은 단일 포트폴리오 내 라벨링이며 별도 엔티티가 아님)
- 재검토 예정: 와이프/친구 공유 또는 ISA / 일반 / 연금 분리 운영 시점
- 트리거: 인증 / 사용자 구분 도입과 묶여서 다시 검토

#### DEFERRED: 계좌번호 / 증권사 구분 도입
- 발생 맥락: POC2 Step 2C — account_group 은 표시/그룹용 라벨로만 도입
- 현재 결정: 실제 계좌번호 / 증권사 식별자는 도입하지 않음. 라벨 자유 입력만 허용
- 재검토 예정: 사용자가 계좌별 손익 계산 / 증권사별 보고를 명시 요구할 때
- 트리거: "계좌번호 단위로 정확히 묶고 싶다" / "증권사별 합계가 필요하다" 류 요구

#### DEFERRED: 계좌별 세금 / 절세 판단
- 발생 맥락: POC2 Step 2C — account_group 은 세무 판정값 아님 (지시문 명시)
- 현재 결정: ISA 한도 / 연금 세액공제 / 양도세 계산 등 일체 미도입
- 재검토 예정: 사용자가 절세 판단을 화면에서 받고 싶다고 명시할 때
- 트리거: "ISA 만기까지 얼마 남았나" / "연금 한도 초과인가" 류 질문이 누적될 때

#### DEFERRED: 복수 포트폴리오 지원 (사용자별 / 가족별)
- 발생 맥락: POC2 Step 2C — holdings_latest.json 단일 SSOT. account_group 은 한 포트폴리오 내 라벨링
- 현재 결정: 사용자/포트폴리오 다중 엔티티 미도입
- 재검토 예정: 와이프와 본인 / 친구 / 가족 계정 분리가 필요한 시점
- 트리거: 인증 / 사용자 구분 도입과 묶여서 다시 검토

#### DEFERRED: account_group 라벨 병합 / 관리 UI
- 발생 맥락: POC2 Step 2C — 라벨은 자유 입력. "키움-일반" 과 "키움일반" 같은 변형이 누적될 수 있음
- 현재 결정: 자동 병합 / 라벨 일괄 변경 / 라벨 사용 통계 UI 없음
- 재검토 예정: 사용자가 라벨 파편화로 혼란을 겪을 때
- 트리거: 동일 의미 라벨이 5개 이상 파편화 발견 시

#### DEFERRED: 과거 draft_payload 영구 마이그레이션
- 발생 맥락: POC2 Step 2C — 과거 run 의 draft_payload 에 account_group 누락 가능. 렌더링 계층에서만 "일반" 으로 보정
- 현재 결정: 과거 run 의 store 파일을 강제 재작성하지 않음. 렌더링 호환만 보장
- 재검토 예정: 운영 중 과거 데이터 재현 / 비교가 필요해질 때
- 트리거: 사용자가 "어제 run 의 계좌별 합계가 보고 싶다" 같은 요구를 할 때

#### DEFERRED: stable holding_id 영구 저장 여부
- 발생 맥락: POC2 Step 2C — holding_id 도입 안 함. React key 는 source_index + ticker + account_group + avg_buy_price 조합
- 현재 결정: holdings_latest.json 스키마에 holding_id 추가하지 않음
- 재검토 예정: 사용자가 동일 종목 분할매수를 자주 편집하면서 행 순서가 흔들려 펼침 상태가 손실될 때
- 트리거: source_index 만으로 row 식별이 깨지는 사례 발생 시 (예: 행 삭제/재정렬 후 펼침 상태 미스매치)

#### DEFERRED: 인증 / 사용자 구분
- 발생 맥락: POC1 — 단일 사용자 전제 (혼자 쓰는 프로젝트, PROJECT_ORIGIN_INTENT)
- 현재 결정: 인증/세션/권한 체계 없음. CORS 도 개발용 origin 만 허용
- 재검토 예정: 와이프/친구에게 공유 시점 또는 여러 단말기에서 접속 필요 시점
- 트리거: "내 run 과 다른 사람 run 을 구분해야 한다" 가 명시 요구로 들어올 때

---

### UI / Message / Visualization

#### DEFERRED (CONSOLIDATED): 메시지 포맷 / 알림 채널 고도화
- 통합 대상 (이전 5개 항목):
  · DEFERRED: Telegram 메시지 디자인 고도화 (POC2 Step 1A)
  · DEFERRED: 전송 메시지 템플릿 고도화 (POC2 Step 2D)
  · DEFERRED: 알림 채널별 메시지 포맷 분리 (POC2 Step 1A)
  · DEFERRED: 메시지 채널별 포맷 분리 (POC2 Step 2B)
  · DEFERRED: Telegram 외 복수 알림 채널 (Step 3 OCI 실연결 시점)
- 발생 맥락: 메시지는 Telegram 단일 채널 + 평문(plain text) + Step 2B compaction 정책 + Step 2D preview 단일 소스. 마크다운 / HTML / parse_mode / 이모지 강조 / 색상 / 링크 / 이미지 / Slack·Discord·Email·SMS 채널별 포맷 함수 분리 모두 미도입.
- 현재 결정: 단일 채널 + 평문 + 길이 안전 한도(MAX_LENGTH_CHARS=3500) + 단일 message_text 소스 정책 그대로 유지. preview / OCI handoff / Telegram 발송이 같은 문자열 사용.
- 재검토 예정: Telegram 외 채널 도입 결정 시 또는 가독성 추가 요구 발생 시
- 트리거: 사용자가 "강조/색상/링크가 필요하다" 또는 "Telegram 외 채널 사용자에게 결과를 보내야 한다" 요구를 명시할 때

#### DEFERRED: Telegram 메시지 Top N 설정값 UI화
- 발생 맥락: POC2 Step 2B — TOP_N_PRICE_MISSING / TOP_N_BOTTOM_PNL_RATE / TOP_N_TOP_MARKET_WEIGHT / TOP_N_TOP_PNL_RATE 가 코드 내 상수
- 현재 결정: 기본값 3 으로 고정. 설정 파일 / 환경변수 / UI 설정으로 노출 안 함
- 재검토 예정: 사용자가 Top N 값 조정 요구를 반복 제기할 때
- 트리거: "더 많이 / 더 적게 보고 싶다" 가 명시 요구로 들어올 때

#### DEFERRED: Telegram 메시지 split 발송 검토
- 발생 맥락: POC2 Step 2B — 한 메시지로 발송하되 길이 안전 한도 초과 시 주목 종목 축소 + 잘림 안내
- 현재 결정: 메시지 분할(여러 개로 쪼개 발송) 도입 안 함. compaction 만으로 처리
- 재검토 예정: 한도 축소만으로는 정보 손실이 운영 이슈가 될 때
- 트리거: 잘림 안내가 일상화되면서 사용자가 "전체 정보를 봐야 한다" 요구할 때

#### DEFERRED: 계좌별 Telegram 요약
- 발생 맥락: POC2 Step 2B — 단일 계좌 전제. 계좌 필드 없으므로 계좌별 요약 불가
- 현재 결정: 계좌별 분리 요약 / 별도 발송 / 채널 분기 일체 안 함
- 재검토 예정: 계좌 구분 추가(POC2-Step2C 도입 완료) 후속으로 검토
- 트리거: 계좌 구분 도입 직후 — Step 2C 종료 시점에 한 번 검토 권장

#### DEFERRED: 계좌별 Telegram 요약 / 채널 분리
- 발생 맥락: POC2 Step 2C — Telegram message_text 는 Step 2B 정책 그대로 (전체 요약 + 주목 종목)
- 현재 결정: 계좌별 분리 발송 / 별도 메시지 / 채널 분기 일체 안 함
- 재검토 예정: 와이프와 본인이 다른 계좌만 보고 싶은 시점
- 트리거: 사용자가 계좌별 별도 알림을 명시 요구할 때

#### DEFERRED: 시세 확인 종목 기준 요약의 UX 고도화
- 발생 맥락: POC2 Step 2B — "시세 확인 N개 기준" 라벨 + 경고 문구로만 표시
- 현재 결정: 그래프 / 강조 색상 / 인포그래픽 미도입. 평문 텍스트만
- 재검토 예정: 시세 미확인 종목이 빈번히 발생하면서 사용자 혼란이 누적될 때
- 트리거: "전체 손익이 얼마인지 헷갈린다" 류 피드백

#### DEFERRED: 누락 데이터가 많은 포트폴리오의 별도 경고 정책
- 발생 맥락: POC2 Step 2B — 시세 미확인이 1개 이상이면 일반 경고 문구 1줄. 비율과 무관하게 동일
- 현재 결정: 시세 미확인 비율(예: 50% 이상) 에 따른 별도 경고 / FAILED 처리 등 차등 정책 없음
- 재검토 예정: 시세 미확인 비율이 높은 운영 사례 발생 시
- 트리거: 시세 미확인 종목이 전체의 절반을 넘는 사례가 반복될 때

#### DEFERRED: 시세 미확인 계좌 UX 고도화
- 발생 맥락: POC2 Step 2C — 시세 확인 0개 계좌는 "계산 불가" 한 줄 표시
- 현재 결정: 종목별 재시도 / 자동 알림 / 미확인 종목 강조 색상 등 미도입
- 재검토 예정: 시세 미확인이 일상적으로 한 계좌에 몰릴 때
- 트리거: 동일 계좌가 7일 이상 "계산 불가" 로 표시될 때

#### DEFERRED: PnL 산식 설명 고도화
- 발생 맥락: POC2 Step 2C — "(평가 계산 N개 기준)" 라벨 + 단일 경고 문구. 산식 자체는 화면에서 설명 안 함
- 현재 결정: 사용자가 산식을 직접 알고 있다고 가정. 툴팁 / 모달 / 도움말 미도입
- 재검토 예정: 사용자가 평가손익 계산 방식을 묻기 시작할 때
- 트리거: "왜 손익이 이렇게 나오나" 류 피드백이 1회라도 발생할 때

#### DEFERRED: 프론트 compact UI 공용 모듈 추출
- 발생 맥락: POC2 Step 2C — HoldingsClient.tsx (EnrichedSection) 와 RunPanel.tsx (HoldingsCompactView) 가 전체/계좌별 요약 계산 + compact table + 펼침 상태 유지 로직을 각각 보유. 외형은 유사하지만 데이터 소스 / 컬럼 의미 / 호환성 처리가 다름.
- 현재 결정: 두 컴포넌트의 책임이 단일이 아니므로 premature abstraction 회피. 공용 모듈(SummaryCards, CompactTable, useExpandedRows 등) 추출은 트리거 발생 후 별도 STEP.
- 재검토 예정: 동시 변경 사례 발생 시
- 트리거 (다음 중 하나라도 발생):
  · 한쪽 컴포넌트에 컬럼/요약 항목이 추가되면서 다른 쪽도 동일 변경이 필요한 일이 2회 이상 발생
  · 동일 계산 버그가 두 곳에서 같이 발견되어 두 곳에 같은 수정이 필요한 사례 발생
  · 컴포넌트 한 파일이 ~600 라인을 넘어 코드 리뷰 스캔이 어려워지는 시점
- **트리거 충족 (2026-04-30, Step5B 종료 시점)**: RunPanel.tsx 가 1,055라인으로 ~600 라인 트리거 초과. Step5B 에서 EvidenceDetails 안에 MomentumCandidatesSection 이 추가되어 책임이 더 늘어남. **다음 STEP 진입 전 우선 검토 필요**.
- **PARTIALLY RESOLVED (2026-04-30, Step5D Cleanup)**: RunPanel.tsx 의 표시 책임 일부를 분리 완료.
  · frontend/app/components/JudgmentReasonSection.tsx — 판단 사유 섹션 + pickPortfolioFactorSignal / pickMomentumBullet
  · frontend/app/components/MomentumCandidatesSection.tsx — 모멘텀 후보 상세 + pickMomentumCandidates
  RunPanel.tsx 1,055 → 905라인. 다만 KS-10 트리거(900라인) 와 EvidenceDetails 분리는 다음 Cleanup 후보로 잔존.

#### DEFERRED: 백엔드 테스트 파일 분리 (tests/test_poc1_loop.py)
- 발생 맥락: POC1 부터 단일 파일 tests/test_poc1_loop.py 에 모든 테스트 누적. Step1 ~ Step5B 까지 신규 케이스가 추가되며 단일 파일이 비대해짐.
- 현재 결정: 분리하지 않음. 단일 파일 + import 한 fixtures(`_isolated_store`, `_stub_oci_calls`, `_ORIGINAL_DELIVER`) 가 모든 통합 테스트에서 자동 적용되는 구조. 분리 시 fixture 공유 정책을 다시 정해야 함.
- 재검토 예정: 다음 STEP 진입 전 검토 권장 (검증자 NOTES B-3 누적 지적).
- 트리거 (다음 중 하나라도 발생):
  · 한 파일이 ~3,000 라인을 넘어 코드 리뷰 / IDE 검색이 느려지는 시점
  · 신규 STEP 의 테스트 추가 시 기존 무관한 테스트와의 충돌이 1회라도 발생
  · pytest collection 시간이 사용자 체감 수준에 도달
- **트리거 충족 (2026-04-30, Step5B 종료 시점)**: 3,158라인 — 3,000라인 트리거 초과. **다음 STEP 진입 전 우선 검토 권장** (분리 방향: tests/poc1/, tests/poc2_step2/, tests/poc2_step3/, tests/poc2_step5b/ 등 STEP 단위 또는 도메인 단위, conftest.py 로 공통 fixture 추출).
- **RESOLVED (2026-04-30, Step5D Cleanup)**: tests/test_poc1_loop.py 가 POC1 핵심(298라인)으로 축소됨. 분리 결과:
  · tests/conftest.py — 공통 fixture (autouse + 명시)
  · tests/_helpers.py — 헬퍼 함수 / 상수
  · tests/test_poc1_loop.py — POC1 승인 루프 핵심
  · tests/test_holdings_draft_flow.py — Step1/1A/2/2B/2C/2D
  · tests/test_factor_signals.py — Step3
  · tests/test_momentum_holdings.py — Step5B
  · tests/test_universe_seed.py — Step5C
  pytest 119 passed 그대로 유지. 단, test_holdings_draft_flow.py 가 1,982라인으로 KS-10 1차 트리거(테스트 1,500라인 + 여러 STEP 섞임) 충족 — 다음 Cleanup 후보로 별도 등재.

#### DEFERRED: 역할별 페이지 분리
- 발생 맥락: POC2 Step 2D — 한 화면(MainPanel)에 입력 폼, 시세 평가, 승인 초안 preview, 근거 데이터, 샘플 폼이 모두 들어감
- 현재 결정: 단일 화면 + 섹션 구분 + details 펼침으로 처리. 라우팅/메뉴 분리 도입 안 함
- 재검토 예정: 사용자가 입력과 승인을 분리된 동선으로 쓰고 싶다고 명시할 때
- 트리거: 동일 사용자가 한 세션에서 입력 → 승인 사이를 4회 이상 왕복하면서 화면 길이 부담을 보고할 때

#### DEFERRED: 근거 데이터 접힘 상태 영구 저장 (localStorage / URL Query)
- 발생 맥락: POC2 Step 2D — 승인 초안 영역의 근거 데이터 details 펼침 상태는 컴포넌트 메모리만 유지
- 현재 결정: 새 run 전환 / 페이지 reload 시 초기화. 최신 run 은 기본 접힘, 과거 run(message_text 없음)은 기본 펼침이라는 정책으로만 보정
- 재검토 예정: 사용자가 펼침 상태를 세션 간에도 유지하고 싶다고 명시할 때
- 트리거: F5 후 펼침 상태가 사라진다는 피드백이 1회라도 발생할 때

#### DEFERRED: message_text 와 Telegram 실제 렌더 차이 자동 검증
- 발생 맥락: POC2 Step 2D — preview 와 발송문은 같은 message_text 를 공유하지만, Telegram 클라이언트의 줄바꿈/공백/이모지/한글 폭 처리가 브라우저 pre-wrap 과 미세하게 다를 수 있음
- 현재 결정: 자동 비교 검증 도입 안 함. 사용자 디바이스에서 자연 검증
- 재검토 예정: preview 와 실제 Telegram 화면 차이가 의사결정에 영향을 줄 때
- 트리거: 사용자가 "preview 에서는 OK 였는데 Telegram 에서는 깨져 보인다" 류 피드백을 1회라도 보고할 때

#### DEFERRED: Next.js UI 세분화 / 컴포넌트 구조 정리
- 발생 맥락: Step 3 최소 구현 — 승인 루프를 단일 `ApprovalLoopClient.tsx` 로 처리
- 현재 결정: 입력 폼 / 상태 표시 / 초안 본문 / 다음 행동 섹션이 한 컴포넌트에 있음. 상수/유틸 최소 분리만 수행
- 재검토 예정: 화면 수 2개 이상으로 늘거나 같은 상태 표현이 여러 뷰에서 반복될 때
- 트리거: 주요 컴포넌트 한 파일이 ~400 라인을 넘고 코드 리뷰 스캔이 어려워지는 시점

#### DEFERRED: 전역 상태 관리 라이브러리 도입
- 발생 맥락: Step 3 — `useState` / `useRef` 만 사용, Redux/Zustand 미도입 (DEV_RULES 절대 금지 6번)
- 현재 결정: 단일 화면 + 단일 run 상태이므로 로컬 컴포넌트 상태로 충분
- 재검토 예정: 여러 화면에서 같은 run 을 공유해야 하거나 인증/권한 상태가 도입될 때
- 트리거: prop drilling 3 단계 이상이 상시화 되거나, 다중 run 동시 진행 화면이 생길 때

#### DEFERRED: 상세 에러 UX 개선
- 발생 맥락: Step 3 — 네트워크 실패/서버 오류는 단일 에러 배너에 raw detail 노출
- 현재 결정: 상태 구분은 최소 (loading / errorMsg / run.status). 과한 에러 분류 금지 (DEV_RULES D항)
- 재검토 예정: 사용자가 "어떤 오류인지 알 수 없다" 피드백을 낼 때
- 트리거: 동일 원인의 에러가 사용자 체험에 반복되는데 대처법이 다를 때 (예: 네트워크 vs 서버 500 vs 계약 오류)

#### DEFERRED: 수동 새로고침 시 run_id 유실 방지
- 발생 맥락: Step 3 레드팀 MINOR 지적 — `useState` 로만 run_id 를 보관하므로 브라우저 F5 시 현재 진행 중인 루프 화면이 소실됨
- 현재 결정: 이번 단계에서는 구현하지 않음. URL Query Parameter 또는 localStorage 중 어느 쪽을 쓸지 결정하지 않음
- 재검토 예정: Step 3 실사용 직후 (최우선 DEFERRED)
- 트리거: 사용자가 실제로 새로고침 후 "내 run 이 사라졌다" 를 1회라도 경험했을 때. 해결 방향: `/runs/{run_id}` URL 또는 `localStorage["last_run_id"]` 중 단순한 쪽 선택

#### DEFERRED: 운영용 화면 분리 (POC2 이후)
- 발생 맥락: POC1 은 단일 승인 루프 화면 하나로 정의됨
- 현재 결정: 대시보드 / run 목록 / 히스토리 / 설정 같은 별도 화면 만들지 않음
- 재검토 예정: POC2 단계 진입 시
- 트리거: 운영 중 "지난 run 들을 한 번에 보고 싶다" / "여러 사용자 구분이 필요하다" 등 요구가 누적될 때

#### DEFERRED: 스타일 시스템 / 컴포넌트 라이브러리 도입
- 발생 맥락: Step 3 — shadcn/ui / MUI / Tailwind 미도입 (DEV_RULES 절대 금지 7번)
- 현재 결정: `frontend/app/globals.css` 단일 CSS 파일로 최소 스타일 유지
- 재검토 예정: 화면이 복수 개가 되고 공용 컴포넌트 시각 통일이 필요해질 때
- 트리거: CSS 중복이 3곳 이상 발생하거나, 디자인 일관성 이슈가 사용자 피드백으로 올 때

#### DEFERRED: 시세 표시 timezone / 사람이 읽는 형식 정규화
- 발생 맥락: POC2 Step 2 — Naver `localTradedAt` (예: `2026-04-27T16:10:16+09:00`) 을 UI 에 그대로 표시
- 현재 결정: ISO 문자열 그대로 노출. KST 표기 변환 / "오늘 16:10" 같은 사람이 읽는 형식 미적용
- 재검토 예정: 사용자 가독성 피드백 시
- 트리거: "이게 한국 시간인가요" 류 질문이 반복될 때

#### DEFERRED: 모바일 최적화 (compact table 가로 스크롤 / 터치 UX)
- 발생 맥락: POC2 Step 2C — compact-table-wrapper 는 overflow-x: auto 만 적용. 폭 좁은 화면 대응은 최소
- 현재 결정: 데스크톱 우선. 모바일은 가로 스크롤로 감내
- 재검토 예정: 사용자가 모바일에서 정기적으로 확인하기 시작할 때
- 트리거: 와이프 / 친구 등 비-데스크톱 사용자 공유 시점

#### DEFERRED: 종목 상세 펼침 상태 장기 저장 (localStorage / URL Query)
- 발생 맥락: POC2 Step 2C — 펼침 상태는 컴포넌트 메모리(Set)로만 유지
- 현재 결정: 새 run 전환 / 페이지 reload 시 초기화. 항목 식별자 단위 polling 보존만 구현
- 재검토 예정: 사용자가 같은 펼침 상태를 세션 간에도 유지하고 싶다고 명시할 때
- 트리거: F5 후 펼침이 사라진다는 피드백 누적

#### DEFERRED: 샘플 입력 폼 완전 제거
- 발생 맥락: POC2 Step 1 — 샘플 입력은 접힘 섹션 + 고정 샘플 1버튼으로 격하했으나 유지
- 현재 결정: 개발/테스트 편의 위해 보존. 운영 입력 아래 접힘 섹션에 위치
- 재검토 예정: 운영 입력만으로 모든 검증 가능해진 후
- 트리거: 사용자가 "샘플 버튼이 더 이상 필요 없다" 명시할 때

#### DEFERRED: 샘플 초안 완전 제거 여부 (POC2 Step 1A 재확인)
- 발생 맥락: POC2 Step 1 / 1A — 샘플 입력 폼은 접힘 섹션 + 고정 샘플 1버튼으로 격하 후 보존
- 현재 결정: 운영 입력 보호 + 샘플 보존. raw JSON 표시는 Step 2D 에서 기본 접힘 details 안으로 이동됨
- 재검토 예정: 운영 입력만으로 모든 검증이 가능해진 후
- 트리거: 사용자가 "샘플 더 이상 필요 없다" 명시 또는 운영 입력 폼이 충분히 안정될 때

---

### OCI / Delivery / Operations

#### DEFERRED: 실패 상태 세분화 (DRAFT_FAILED / PUSH_FAILED / ALERT_FAILED)
- 발생 맥락: S1 설계 (이벤트/액션 설계) — FAILED 단일 상태로 출발
- 현재 결정: 지금은 FAILED 하나로 시작. 원인 구분은 로그로만 확인
- 재검토 예정: POC 완료 후 운영 중 복구 액션이 상황별로 달라져야 할 때
- 트리거: 실패 상황에서 사용자/시스템이 "어느 단계에서 실패했는가" 에 따라 다른 조치가 필요해질 때

#### DEFERRED: 부분 재시도 정책 (Retry Push / Retry Alert)
- 발생 맥락: POC 1단계 — 재시도 금지, 새 run_id 로만 새 초안 생성
- 현재 결정: 실패한 run 은 재사용하지 않고 GenerateDraft 를 다시 실행
- 재검토 예정: POC 완료 후 외부 전달 실패가 잦고 초안이 무거워 재생성 비용이 부담될 때
- 트리거: 외부 전달만 재시도하면 복구 가능한 일시적 장애 빈도가 일정 수준을 넘을 때

#### DEFERRED: 운영 필드 확장 (approved_at / rejected_at / error_code / error_message)
- 발생 맥락: 최소 데이터 계약을 run_id / asof / status / draft_payload 4개로 고정
- 현재 결정: 시각/에러 메시지는 서버 로그로만 남기고 데이터 모델에는 추가하지 않음
- 재검토 예정: 운영 리뷰/SLA 지표가 필요해졌을 때
- 트리거: "언제 승인됐고 왜 실패했는지" 를 UI/보고서에서 조회하는 요구가 반복해 발생할 때

#### DEFERRED: spike_watch / holding_watch 연계
- 발생 맥락: 다른 알림 파이프라인과의 통합은 POC 1기능 범위 밖
- 현재 결정: 단일 초안 승인 루프만 구현. 연동 지점 없음
- 재검토 예정: POC 1단계 승인 루프가 안정 동작 확인된 후
- 트리거: 복수 알림 경로에서 같은 승인 루프를 공통으로 써야 하는 순간

#### DEFERRED (CONSOLIDATED): DELIVERING polling / timeout / orphan 처리 고도화
- 통합 대상 (이전 4개 항목):
  · DEFERRED: DELIVERING 상태 타임아웃 / orphan 처리 (POC1)
  · DEFERRED: polling 제거 또는 대체 실시간 갱신 방식 재검토 (Step 3 frontend)
  · DEFERRED: polling 제거 또는 대체 실시간 갱신 방식 재검토 (Step 3 OCI 실연결 재확인)
  · DEFERRED: DELIVERING 느린 polling 고도화 (Step 3 OCI 실연결)
- 발생 맥락: DELIVERING 상태 타임아웃 / orphan 정리 / 12초 polling 6분 한도 / WebSocket·SSE 미도입 정책. 현재 폴링 빈도/총 감시 시간이 cron 처리 시간을 초과할 가능성.
- 현재 결정: 타임아웃/복구 로직 구현 안 함. 12초 × 30회 ≈ 6분 감시 후 자동 중단 + "상태 새로고침" 안내. WebSocket/SSE 도입 금지(DEV_RULES). 비정상 종료 시 수동 개입 가정.
- 재검토 예정: POC 완료 후 운영 안정화 단계
- 트리거: 외부 전달 중 서버 크래시/네트워크 단절로 DELIVERING 이 장시간 고정되는 사례, cron 평균 처리 시간이 polling 한도를 초과하거나 사용자 체감 지연이 보고될 때, DELIVERING 6분 자동 중단이 일상화될 때

#### DEFERRED: 실제 운영 배포 구조 통합
- 발생 맥락: Step 3 — dev 환경 분리 기동(3000 + 8000)만 구성
- 현재 결정: 리버스 프록시 / 단일 entry / 정적 빌드 호스팅 결정 보류. CORS 는 dev origin 만 허용
- 재검토 예정: shadow 또는 live-lite 리허설 단계
- 트리거: 배포 대상 환경(PC 상주 / 클라우드 / OCI) 이 확정될 때

#### DEFERRED: OCI handoff artifact 형식 고도화
- 발생 맥락: Step 3 실 OCI 전달 — 설계자 결정 기본 규약(run_id/asof/draft_payload/approved_at) 만 사용 (Step 2D 에서 message_text 포함 5필드로 확정)
- 현재 결정: 5 필드 고정. 스키마 버전 / 서명 / Idempotency 키 / 분류 메타 등 추가 안 함
- 재검토 예정: handoff 충돌·중복·재배포가 운영 중 1건이라도 발생할 때
- 트리거: OCI consumer 가 같은 run_id 를 두 번 처리하거나, 다양한 알림 종류를 구분해 라우팅 해야 할 때

#### DEFERRED: 알림 재시도 정책
- 발생 맥락: Step 3 — Telegram 발송 실패 시 OCI consumer 가 outbox 에 status=FAILED 로 한 번만 기록
- 현재 결정: 자동 재시도 없음. 새 run_id 로만 재시도 (POC1 부분 재시도 금지 정책 연장)
- 재검토 예정: Telegram 일시 장애로 인한 수동 재시도가 반복될 때
- 트리거: Telegram API 5xx / 429 빈도가 사용자 체감 수준에 도달할 때

#### DEFERRED: OCI 측 처리 timeout / orphan 대응
- 발생 맥락: Step 3 — daily_ops cron 은 09:05 KST 1회 + 사용자 1회 수동 실행 허용. inbox 의 orphan 파일 정리 로직 없음
- 현재 결정: inbox 에 들어간 artifact 는 다음 cron / 수동 실행 때 처리. 무기한 대기는 frontend polling 한도(약 6분) 가 사용자에게 안내
- 재검토 예정: cron 누락이나 OCI 다운으로 inbox 적체가 발생할 때
- 트리거: inbox/*.json 파일 수가 24시간 이상 N개 이상 잔존하는 사례

#### DEFERRED: 전달 결과 대시보드 분리
- 발생 맥락: Step 3 — 단일 승인 루프 화면에서 최종 status 만 노출
- 현재 결정: 별도 운영 대시보드(누적 처리량, 실패율, Telegram 응답 코드 등) 구축 안 함
- 재검토 예정: POC2 또는 운영 안정화 단계
- 트리거: "어제 몇 건 처리됐고 실패는 몇 건이냐" 가 정기 리뷰에 들어올 때

#### DEFERRED: OCI 측 메시지 렌더링 책임 재검토
- 발생 맥락: POC2 Step 1A — message_text 생성을 로컬 백엔드로 일원화하여 OCI bash 책임 최소화
- 현재 결정: OCI consumer 는 message_text 가 있으면 그대로 사용, holdings 에서 누락 시 FAILED. 비-holdings 면 raw fallback 으로 호환
- 재검토 예정: 운영 중 OCI 측 메시지 보강(예: 처리 시각/cron 컨텍스트 추가) 필요 시
- 트리거: OCI 측 처리 결과 메타데이터를 메시지에 함께 보내야 한다는 요구가 발생할 때

#### DEFERRED: 09:05 cron 자연 발생 검증 결과 반영
- 발생 맥락: POC1 Step 3 종료 시점 — 1회 수동 실행으로만 검증
- 현재 결정: 자연 cron 결과는 다음 09:05 KST 시점에 자연 발생
- 재검토 예정: 첫 자연 cron 실행 직후
- 트리거: cron 실행 후 inbox 적체 / Telegram 미발송 등 이슈 발견 시

---

### Snapshot / History / Audit

#### DEFERRED (CONSOLIDATED): 운영 결과 / 스냅샷 / 변화 감지 기록
- 통합 대상 (이전 5개 항목):
  · DEFERRED: 추적 필드 (holdings_snapshot_ref / market_data_snapshot_ref) (POC1)
  · DEFERRED: holdings 히스토리 / 스냅샷 관리 (POC2 Step 1)
  · DEFERRED: enrichment 결과의 draft_payload 외 영구 저장 (POC2 Step 2)
  · DEFERRED: snapshot/history 기반 변화 감지 (POC2 Step 2B)
  · DEFERRED: 전일 대비 변화 감지 (POC2 Step 2B)
- 발생 맥락: 재현성/감사 추적 / 시점별 holdings 스냅샷 / enrichment 결과의 시계열 저장 / "어제 대비 X% 변동" 류 변화 감지 / 일자별 비교 — 모두 POC 범위 밖이며 매번 덮어쓰는 단일 파일 SSOT 만 유지.
- 현재 결정: 시점별 스냅샷 / 변경 이력 / 별도 시계열 저장소 / snapshot 비교 / 전일 대비 비교 일체 미도입. 재현은 run 자체의 draft_payload 에만 의존.
- 재검토 예정: 추천 결과의 재현성 요구 / "어제는 어떤 보유 종목이었나" / 평가손익 시계열 차트 / "어제 대비 X% 변동" 알림 요구가 발생할 때
- 트리거: 사용자/감사 요구 또는 draft 재현성 요구 또는 일별 변화율/전일 대비 손익 알림 요구가 들어올 때

---

## CLOSED / RESOLVED

Step5 진입 전 정돈 시점에 완료 확인된 항목. 본문은 보존하고 종료 사유와 완료 Step 을 명시한다.

### RESOLVED: POC2-Step2C — Holdings UI 압축 (이전 표기: DEFERRED → 별도 STEP)
- 발생 맥락: POC2 Step 2B — Telegram 메시지만 요약형으로 전환. UI 카드 길이 / 펼침-접힘 / 요약 보기는 그대로
- 종료 사유: POC2-Step2C 에서 compact UI (전체 요약 + 계좌별 요약 + compact table + 상세 펼침 구조) 도입 완료.
- 완료 Step: POC2-Step2C
- 남은 후속: 모바일 최적화 / compact UI 공용 모듈 추출 / 상세 펼침 영구 저장 등 세부 항목은 UI / Message / Visualization 분류에 별도 DEFERRED 로 보존.

### RESOLVED: POC2-Step2C — 계좌 구분 추가 (이전 표기: DEFERRED → 별도 STEP)
- 발생 맥락: POC2 Step 2B — 단일 계좌 전제 유지. 보유 종목에 계좌 필드 없음
- 종료 사유: POC2-Step2C 에서 holdings.account_group 도입 + 단일 helper 정규화 + 중복 정책 완화 + UI 입력/표시 모두 완료.
- 완료 Step: POC2-Step2C
- 남은 후속: 계좌번호/증권사 구분, 계좌별 세금 판단, 라벨 병합/관리 UI, 계좌별 Telegram 요약 등은 Holdings Input / Portfolio Structure / UI 분류에 별도 DEFERRED 로 보존.

### RESOLVED: 현재가 / 평가금액 / 평가손익 / 수익률 / 현재가 기준 비중
- 발생 맥락: POC2 Step 1 — 매입금액과 매입금액 기준 비중까지만 계산
- 종료 사유: POC2-Step2 에서 Naver 시세 enrichment 도입으로 현재가 / 평가금액 / 평가손익 / 평가수익률 / 시장비중 모두 계산·표시 완료.
- 완료 Step: POC2-Step2
- 남은 후속: 비-한국 종목 / 외화 / TTL / 동시성 등 시세 데이터 소스 관련 세부 항목은 Data Source / Market Cache 분류에 별도 DEFERRED 로 보존.

### RESOLVED: 현재가 / 평가손익 / 수익률을 메시지에 포함
- 발생 맥락: POC2 Step 1A — 데이터 새로 만들지 않는 표현 보정 단계. 매입금액/매입비중까지만
- 종료 사유: POC2-Step2 enrichment + Step2B 의 message compaction 정책 안에서 평가지표가 message_text 의 전체 요약 / 주목 종목 카테고리에 포함되도록 완료.
- 완료 Step: POC2-Step2 + POC2-Step2B
- 남은 후속: 메시지 디자인 고도화 / 채널별 포맷 분리는 메시지 포맷 / 알림 채널 고도화(통합) 항목으로 보존.

### RESOLVED: ASSUMPTIONS.md Q2 closeout 이후 후속 질문 정리
- 발생 맥락: Q2 (OCI 푸쉬 파이프라인 동작 여부) — Step 3 실증으로 ANSWERED 가능 상태
- 종료 사유: POC2-Step3 종료 시점에 Q2 → A-4 (ANSWERED) 이동, POC2-Step4 시점에 Q3 → A-5 (ANSWERED) 이동 + Q4 OPEN 신규 + Q5 OPEN 신규. 활성 Open Questions = Q1 / Q4 / Q5 (3개) 로 정리 완료.
- 완료 Step: POC2-Step3 + POC2-Step4
- 남은 후속: Q1 OPEN 유지 권고는 다음 factor 추가 비용 측정 시점에 재검토. Q5 데드라인은 모멘텀 엔진 최소 운영 사이클 1회 완료 후.

### RESOLVED: handoff artifact 스키마 확장 (top-level message_text 추가)
- 발생 맥락: POC2 Step 1A — Telegram 메시지 문자열 책임을 로컬 백엔드로 이전. POC1 Step 3 의 4 키(run_id/asof/approved_at/draft_payload) 에 5번째 키 `message_text` 추가
- 종료 사유: POC2-Step1A 에서 5번째 키 도입 완료. POC2-Step2D 에서 Run 모델 자체에 message_text top-level optional 필드를 추가하고 generate 시점 빌드 + GET /runs/{id} 응답 + OCI handoff + Telegram 발송 모두 동일 단일 소스를 사용하도록 정리 완료.
- 완료 Step: POC2-Step1A + POC2-Step2D
- 남은 후속: ACTIVE REVIEW BEFORE STEP5 의 "draft_payload.factor_signals 외 다른 메타 키 추가 금지" 가드는 본 항목과 동일 정신 — Step5 에서 새 top-level 키 추가 금지로 연결.
