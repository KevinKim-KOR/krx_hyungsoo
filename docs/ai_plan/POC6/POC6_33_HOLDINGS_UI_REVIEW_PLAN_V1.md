# POC6-33 개발 PLAN V1 — 보유 현황 · 종목 관리 · 확인 근거 · 데이터 상태 화면 정리

V1 확정 — 설계자 PLAN 판정(2026-11-18 · 조건부 PASS) 반영 · 독립 사실 확인 1회 반영(2026-11-18) · 설계자 RESULT 판정(2026-11-19 · 조건부 PASS) 표시 보완 · 보유 집계 가림 반영(§9-2)

작성 2026-11-18 · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STATUS   = V1 확정(설계자 PLAN 판정 2026-11-18 조건부 PASS 반영) · 격리 구현 진행 · 코드 변경 없음(이 문서 기준)
DESIGN   = docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_DESIGN_2026-11-18.md
           (설계자 원본 파일명 HOLDINGS_UI_REVIEW_DEVELOPER_HANDOFF_2026-11-18.md · 본문 원문 그대로 · 1행 = 개발자 기록)
DECISION = docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_PLAN_DECISION_2026-11-18.md
           (설계자 PLAN 판정 · 조건부 PASS · 설계자 원본 파일명 POC6_33_DEVELOPER_HANDOFF_2026-11-18.md · Q0 ~ Q55 반영 기준)
MOCKUP   = docs/ai_plan/POC6/POC6_33_HOLDINGS_UI_REVIEW_MOCKUP.html
           (별도 파일 · 판정을 반영한 네 화면 · 범위 = §8 · 보유 이름 · 코드 · 수량 · 가격 · 금액 · 계좌 이름 ·
            보유별 수익률 · 괴리율 · 구성 행 수 없음 · 보유 집계는 N · M · ○)
RESULT   = docs/ai_result/POC6/POC6_33_HOLDINGS_UI_REVIEW_RESULT.md (작성됨 · 검증자 r2 VERIFIED · 설계자 RESULT 판정 2026-11-19 조건부 PASS)
RESULT 판정 = docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_RESULT_DECISION_2026-11-19.md (이 PLAN 에 반영한 표시 보완 = H1 · E7 · I-4 · §9-2)
단계 번호 = POC6-33 (설계자 판정 Q0 확정)
판정 반영 = §1 ~ §6 표 · §7 판정 표(Q0 ~ Q55 한 줄씩) · 판정 글이 열어 둔 구현 세부 = §9-1 개발자 적용 해석 I-1 ~ I-15
           (기존 계약을 지키는 가장 좁은 읽기 · 2026-11-19 RESULT 판정 §3 으로 확정 · 바뀐 표시 = §9-2)
조사 = 읽기 전용 4갈래(보유 현황 · 종목 관리 · 확인 근거 · 데이터 상태) · 2026-11-18 · 최신 main 작업 트리
       + 독립 사실 확인 1회(같은 날 · 틀린 문장 교체 · 빠진 사실 추가 · 줄 번호 다시 확인)
실측 = GET /holdings/enriched 1회(쓰기 없는 경로임을 코드로 확인한 뒤) · state/holdings/holdings_latest.json 건수만
       · 시장 DB mode=ro 직접 조회와 그 사본 · GET /market/nav-discount/latest 1회(집계만 · 이 경로의 표 만들기 문장은
         표가 이미 있으면 바뀌는 것 없음 · etf_nav_store.py:55-60 · 75-83) · 실행 시간은 환경마다 달라 범위로만 적음
보유 표기 = 실명 대신 '보유 A' · 보유 한 종목에 붙는 수익률 · KODEX 200 대비 · 괴리율 · 구성 행 수 · 상품 종류는 '○'
            (이 PLAN · 목업은 공개 저장소에 올라가므로 여러 값을 함께 적으면 공개 시세로 종목을 다시 알 수 있음)
            · 보유 집계(보유 종목 수 · 계좌별 보유 행 수 · 계좌 수 · 보유 ETF 수 · 개별 주식 수 · 상태별 보유 건수 ·
              상위 30 안 보유 건수 · 겹침 보유 건수 · 계산 가능 a/b · 구간별 보유 종목 수 · 보유 평가 비중 · 기록 건수)도
              실제 값을 적지 않음 → 종목 수 N · 행 수 M · 그 밖의 건수 ○ 또는 '합성 예시'라고 밝힌 값
              (2026-11-19 RESULT 판정 §4-1 · 처음 V1 은 건수를 그대로 적었음 → 이번에 가림)
            · 그대로 적는 것 = 모든 보유 ETF 에 같은 날짜(10/21 · 10/22 · 11/18)와 시장 전체 건수(ETF 전체 NAV 1,212행 ·
              주간 모집단 963 · 후보 목록 크기 등)와 규칙 수치(상위 30 · 상위 10 · 20저장일 · 3% · 5% · 200행 등)
```

## 0. 요약

### 0-1. 설계 요지(설계 §1 ~ §5)

| 화면 | 설계가 바라는 것 |
|---|---|
| 「보유 현황」 | 요약 행 = 수량 · 매입단가 · 현재가 · 손익 / 펼친 상세 = 매입금액 · 평가금액 · 매입 기준 비중 · 가격 기준과 출처를 먼저 · 반복 줄임 / '보유 내 비중(평가 기준)' · '매입 기준 비중' 명시 / 기준시각 · 출처 = '2026-11-18 15:54:12 KST · 네이버' / 자금 기준: 미입력은 한 번만 안내 + 보유 평가액 · 가격 기준일 · [입력] · 입력 상태는 현금 · 한도 · 현금 확인일 · 0원과 미입력 구별 |
| 「종목 관리」 | 상단 [가격 비교 기준일 설정] 일괄 버튼 제거 · 상단 = [새 보유 추가] · [입력 정정] · 기준일은 [History] 에서 '비교 시작일'로 읽고 개별 수정 · 해제(설계 §2 의 '그래프의 시작점' 설명은 사실과 달라 판정 Q19 로 정정 → §2) |
| 「확인 근거」 | 상단 = 점검 상태 · 하락 구간 건수와 평가 비중 · 자료 확인 필요 건수 · 가격 기준일 · 시각마다 이름과 뜻 · 한국 시각 / 행 = 종목 · 평가 비중 · 계좌 합산 손익률 · 5 · 20 저장일 흐름 · KODEX 200 대비 · 확인 사유 · 단위 / 상세 = 클릭한 행 바로 아래 · 방향과 시장 대비 먼저 · 같은 설명 한 번 · 주간 순위는 「주간 ETF 점검」과 같은 조회 결과 · 겹침 비교 범위 · 시장가 · NAV · 괴리율 · 기준일 · [전체 ETF NAV·괴리율 보기] 제거 |
| 「데이터 상태」 | 수집 상태와 괴리율 표시를 각각 읽게 · 'ok' → '수집됨' · 괴리율 표시 = 기존 조건 · asof · source · 출처 값 한국어 |

### 0-2. 설계자가 확인을 맡긴 사실(최신 main · 2026-11-18)

| # | 확인 요청 | 결과 | 근거 |
|---|---|---|---|
| F1 | 20일 수익률 10/21 ~ 11/18 · 차트 10/22 ~ 11/18 | **둘 다 맞음 · 역할이 다름.** 10/21 = 20일 수익률의 시작 종가 날짜(최신순 21번째 행 · 변화 20구간 · 종가 21개). 10/22 = [세부 흐름 보기] 창 차트의 첫 표시일(최근 20행). 같은 창의 거래량 평균 구간 = 10/21 ~ 11/17 · 가격 흔들림 최근 구간 = 10/21 ~ 11/18. 운영 DB 에서 KODEX 200 과 모든 보유 ETF 가 같은 날짜. 화면에는 범위의 역할이 적혀 있지 않음 | short_term_momentum.py:65-73 · :82 · pc_price_basis.py:91-97 · 246-251 · stored_volume_evidence.py:77 · 102-104 · 115 · 130-144 · DetailFlowsBody.tsx:94-96 · volumeTrend.ts:10-11 |
| F2 | 상세 'Market Discovery TOP 10' 의 출처 | 근거 API 가 compute_topn(n=10 · 1개월 · 제외 4종)을 부르고, 공유 builder 가 notes 첫 줄 '현재 Market Discovery TOP 10 후보에 포함되어 있지 않습니다.'를 만든다 → 화면 '자료 확인 안내'에 그대로 붙음. 같은 문장을 PUSH · 초안 · 런타임 근거가 같이 씀. 이 1개월 = 전체 MAX(date) − 30달력일 이후 첫 저장일 → 마지막 저장일 · 공통 기간 조건 없음 | api_holdings_market_evidence.py:268-275 · holdings_market_evidence.py:57-89 · 359-369 · helpers.ts:331 · HoldingsRiskEvidenceSection.tsx:450-464 · market_topn_helpers.py:143-188 · pc_price_basis.py:148-149 |
| F3 | 주간 순위 재사용 근거 | 「주간 ETF 점검」 = build_summary(1개월 · 제외 4종 · 상위 30 · 공통 기간 밖은 모집단에서 뺌). 그 결과 holdings.items[] 에 in_population · out_reason(stock · filter_excluded · no_price · period_differs) · side · top_rank(상위 30 안일 때만) · price_flow 가 이미 있음. **GET /weekly/etf-check 응답에는 이 칸이 빠짐**(assemble). 같은 함수 · 같은 인자를 GET /market/etf-compare/summary 기본 조건이 그대로 돌려줌(mode=ro). 화면 함수 · 문구(fetchEtfCompareSummary · outReasonText · candidateLinkText)도 있음 | api_weekly_review.py:56-145 · 192-205 · weekly_review.py:30-38 · pc_etf_compare_summary.py:65(LIST_N = 30) · 236-252 · 405-461 · api_etf_compare.py:77-104 · lib/api/etfCompare.ts:167-190 · 281-287 · lib/etfCompare.ts:385-427 |
| F4 | 실데이터 대조 | 보유 M행 · ○계좌 · 서로 다른 종목 N(ETF ○ · 개별 주식 ○ · 여러 계좌에 있는 종목이 있어 N < M). 주간 조건(공통 기간 10/19 → 11/18 · 모집단 963): **상위 30 안 · 순위권 밖 · 규칙상 제외 · 개별 주식 · 가격 없음 · 기간 다름 = 각 ○건**(상태별 보유 건수 · 공개 문서 가림 · 2026-11-19 RESULT 판정 §4-1). 옛 상위 10 = 주간 상위 30 의 앞 10 과 같은 순서 · 보유 포함 ○. 설계 캡처의 보유(보유 A)는 20저장일 수익률 · KODEX 200 대비 · 괴리율이 캡처 값과 같음(값은 '○' · 머리 '보유 표기') | 조사 실측(사본 DB 와 운영 DB mode=ro · 같은 인자 · 실행 시간 build_summary 약 0.5 ~ 0.9초(2회 · 0.47 · 0.87) · compute_topn 약 1.1초(1회) · 환경마다 다름) |
| F5 | '시장 핵심과 중복 구성종목 없음' 의 범위 | compute_topn 1개월 상위 10개 각 ETF 의 상위 10행에서 2개 이상 ETF 에 나온 종목(실측 20개)과 보유 ETF 최신 구성 상위 10행을 비교. 구성 없는 후보는 조용히 건너뜀. 응답 = status + 겹침 목록뿐(비교한 후보 수 · 기준일 · 행 수 없음). 실측: 후보 10개 모두 구성 있음(기준일 11/16 · 저장 4 ~ 30행) · 보유 ETF 모두 status ok(겹침 0건 보유 ○ · 1건 보유 ○ · 구성 기준일 모두 11/18) · 개별 주식 = constituents_unavailable · **저장 구성이 비교 상한 10행보다 적은 보유 ETF 도 '중복 없음'으로만 보임**(행 수 '○'). 겹침의 보유 쪽 구성 = 저장 MAX(asof)(latest_constituent_asof · etf_constituents_store.py:412-424 → holdings_market_evidence.py:227 · 285) · 후보 · 보유마다 연결을 따로 엶(etf_constituents_store.py:160-167) | holdings_market_evidence.py:205-232 · :294 · :310-313(반환 = status + 겹침 목록) · etf_constituents_analysis.py:135-174 · HoldingsRiskEvidenceSection.tsx:123-141 |
| F6 | 일괄 버튼 · 저장값 | 기록 ○건(기준잔고 · 기준일 · 정정 · 매수 · 종류별 건수 가림). 보유 기간 모두 기준잔고로 시작 · 기준일 2026-01-02 저장(2026-10-11 한 번의 일괄 실행). **지금 일괄 창 대상 ○건**(기준일 없는 기간이 없으면 누를 때 '설정할 보유가 없습니다' 안내만). 일괄 창 · History 편집기 모두 같은 PUT /holdings/trade-history(action reference_date) → 버튼을 없애도 백엔드 · 저장 문서 · 저장된 날짜는 그대로 | HoldingsBookSection.tsx:208-215 · ReferenceDateDialog.tsx:29-44 · 62-68 · 99-102 · ReferenceDateEditor.tsx:37-43 · holdings_reference_date.py:40 · 102 · holdings_book.py:21-24 · 480-497 |
| F7 | 기준일 = '그래프 시작점'(설계 §2) | **이 날짜를 쓰는 그래프는 없음**(holdings_manage/*.tsx 에 svg · 차트 0건). 쓰는 곳 = History [시장 흐름 보기]의 종가 변화 글 줄('가격 비교 기준일 이후 종가 변화' · 끝난 기간 '… → 마지막 매도일 종가 변화')과, 같은 글을 그대로 보이는 재진입 검토 창. 「확인 근거」 · 「보유 현황」 차트는 이 날짜를 읽지 않음. POC5-07 정의 = '종가 비교의 출발점' → **판정 Q19: 설계 §2 의 '그래프 시작점' 설명을 PLAN · 목업에서 정정**(§2 '그래프 시작점 정정') | MarketFlowPanel.tsx:89-105 · 107-128 · ReentryEvidence.tsx:25 · 202 · POC5-07 DESIGN_V1.md:23 |
| F8 | 「데이터 상태」 기계값 · 기존 문구 | 수집 상태 status = ok · partial · unavailable(저장값). 괴리율 표시 flag = 3% 이상 5% 미만 discount_check_needed · 5% 이상 discount_warning(읽을 때 계산 · status 와 따로) → 'ok + 괴리율 경고'가 실제로 함께 나옴. 운영: 최신 1,212행 모두 ok · 출처 naver_etf_item_list · 확인 필요 2 · 경고 2(4행 모두 ok) · 22행은 옛 기준일(06-23 ~ 11-10)인데 ok. **괴리율 문구 세 벌**: 설계 예시 '괴리율 주의' · '괴리율 확인 필요' / 프론트 '괴리 확인 필요(3% 이상)' · '괴리 주의(5% 이상)' / 백엔드 AI 글 '괴리율 절대값 3% 이상 · 확인 필요' · '… 5% 이상 · 경고'. '수집됨'은 앱에 없는 새 낱말 | etf_nav_service.py:365-401 · etf_nav_fetcher.py:21-22 · 70-79 · api_nav_discount.py:102 · DataStatusView.tsx:230-232 · 259-262 · 302-311 · 329-343 · DetailNumbers.tsx:67-70 · decision_preview_lines.py:60-63 |
| F9 | '보유 기준일'(holdings_asof) | 실제 뜻 = **보유 파일 수정 시각(mtime · UTC ISO)**. 지금 값 11/06 · 시장 기준일 11/18 → 이름과 뜻이 맞지 않음. 화면 안 fmtKstDate 가 변환을 하지 않아 원문 그대로 보임. 이 값과 market_asof 는 판단 요약 evidence_asof 로 PUSH 에도 넘어감 → 값은 그대로 두고 표시만 바꿈 | holdings_market_evidence.py:443-446 · 610-620 · api_holdings_market_evidence.py:259 · HoldingsRiskEvidenceSection.tsx:72-75 |

### 0-3. 기반 문서 대조
- 성공 기준 3(전문 용어 없이 읽히는 화면): 네 화면의 영어 · 기계 글자를 쉬운 한국어로 바꾼다.
- KS-2(정의 = '백엔드에 기능은 있는데 화면에 없거나 접근 불가' · KILL_SWITCHES.md:16-18): 일괄 버튼을 빼면 여러 기간(1 ~ 200)을 한 번에 저장하는 백엔드 경로를 화면에서 더 이상 쓰지 않는다(putReferenceDate 호출 = ReferenceDateDialog.tsx:62 여러 건 · ReferenceDateEditor.tsx:37-43 1건 고정 두 곳뿐 · holdings_reference_date.py:40 MAX_TARGETS = 200 · :102). **판정 Q46: 상단 일괄 버튼을 빼고 이 결정을 docs/KILL_SWITCHES.md KS-2 아래 판정 기록으로 남긴다(M6).** 백엔드 다건 경로 · 저장된 날짜는 그대로 · 화면은 History 에서 기간마다 1건 · 지금 일괄 대상 ○건(가림) · 다건 저장 계약은 기존 백엔드 시험이 확인. [전체 ETF NAV·괴리율 보기 →] 는 메뉴 「진단·상태 › 데이터 상태」와 「오늘의 투자 점검」의 같은 버튼(maintenanceQueue.ts:55-56)이 남아 접근 경로가 유지된다.
- KS-10: §6.
- 새 의존성 · 외부 조회 · DB 표 변경 · OCI · PUSH 변경: 판정 기준 0. 공유 builder(`holdings_market_evidence.py` 620줄)는 고치지 않는다(판정 Q26 = 응답에 없는 비교 범위는 '비교 범위 확인 불가'로 안내).
- 확인 주체: 화면만 바뀌는 항목 = 사용자 실화면(격리 화면) · 백엔드가 바뀌는 항목 = M4 주석 한 줄(동작 무변경)만 검증자 대상 · 문서 M5 · M6 = 검증자 대상.
- 실측값의 시점: 이 PLAN 의 운영 실측(날짜 · 건수 · 보유 A 값)은 2026-11-18 자료 기준이다. 다음 거래일 갱신 뒤에는 바뀌므로 실화면을 볼 때 그 자리에서 다시 잰다(§5).

## 1. 「보유 현황」(holdings)

경로: MainPanel.tsx:82-84 → HoldingsView.tsx → EnrichedHoldingsSection.tsx + holdings/CapitalContextPanel.tsx · 자료 = GET /holdings/enriched 하나(app/api.py:399-441). API · 계산 · 정렬 · 펼침 키 무변경. 같은 응답을 쓰는 다른 화면 7곳은 영향 없음. `_orphaned/HoldingsClient.tsx:34 · 405` 가 EnrichedSection 을 items 만으로 써서 tsc 대상이므로 props 는 바꾸지 않는다.

| ID | 바꿀 것(판정 반영) | 파일 · 줄 | 닿는 계약 | 고칠 시험 | 구분 | Q |
|---|---|---|---|---|---|---|
| H1 | 펼친 상세 = 매입금액 → 평가금액 → 매입 기준 비중 → 가격 기준시각 · 출처(한 줄 · H4). **수량 · 평균 매입단가 · 현재가는 상세에서 뺀다**(요약 행에 이미 있음 · 요약 행은 그대로). **2026-11-19 형수님 결정(격리 화면 확인):** 처음 V1 의 상세 '현재가'(값 없음 '미확인') 항목은 요약 행 '매입 X → 현재 Y'(값 없음 '현재 미확인')와 반복이라 뺌 → 설계자 RESULT 판정 §2-0 수용. 상세 = 매입금액 · 평가금액 · 매입 기준 비중 · 가격 기준시각과 출처 네 항목 · 1440px 에서 한 줄(가격 기준시각 = 두 칸 폭) · 좁은 화면은 읽을 수 있게 줄바꿈 · 시세 없음 = 요약 '현재 미확인' · 상세 평가금액 '평가 불가' · 매입 비중 없음 = '비중 계산 불가'(H3) | EnrichedHoldingsSection.tsx:710-735(DetailRowFields) | POC6-25 B-3 · AC2(현재가 '미확인' 항목을 숨기지 않음 · 유지) | eval.test.tsx:137('평균 매입단가' 단정 → '상세에 수량 · 평균 매입단가 없음' 단정) · 순서 단정 1개 추가(:115-127 은 항목 이름으로 찾음 · 그대로) | 화면 | Q5 · Q1 |
| H2 | 행 '보유 내 비중' → '보유 내 비중(평가 기준)'(계좌별 평가 비중) · 상세 '매입비중' → '매입 기준 비중' · 자금 카드 부분 평가 문구 속 같은 이름도 맞춤 · 계산 · 필드 그대로 | EnrichedHoldingsSection.tsx:672-678 · 718-719 · CapitalContextPanel.tsx:323-328 | POC6-24 B-3 · B-4(행 첫 줄 '보유 내' · 둘째 줄 '입력 현금 포함') · PROGRAM_TRUTH.md:304 | CapitalContextPanel.test.tsx:413 · 부분 평가 문구 단정(구현 때 grep) | 화면 | Q6 · Q7 |
| H3 | 매입 기준 비중이 null 이면 '0%' 대신 기존 '비중 계산 불가'(EnrichedHoldingsSection.tsx:677 낱말) | EnrichedHoldingsSection.tsx:718-719 · holdings_view.ts:12-15 · 30-34 | POC6-25 A-3(그때 범위 밖) | eval.test 에 null 사례 추가 | 화면 | Q9 |
| H4 | 상세 한 줄 '가격 기준시각 2026-11-18 15:54:12 KST · 네이버'(초까지 한국 시각) · '데이터 출처' 줄은 합침 · 날짜만 저장된 값 → 날짜만 · 해석 실패 → '확인 불가' · 둘 다 없으면 줄 없음(지금과 같음) · 출처 사전 naver → '네이버' · 사전 밖 → '기타 출처'(I-11) | EnrichedHoldingsSection.tsx:723-724 · 형식 함수 = lib/holdings_view.ts(기존 엄격 해석 parseIsoInstant lib/todayMarketLines.ts:31-42 재사용) | POC6-25 B-3 '분기는 형식화 전 값 없음 여부' | 지금 단정 0건 → ISO · 날짜만('2026-08-11' 고정 자료) · 사전 밖 출처('TEST' 고정 자료) · null 사례 추가 | 화면 | Q4 · Q11 · Q3 |
| H5 | 미확인 문구 그대로(배지 '시세 미확인' · 행 '현재 미확인' · 평가금액 '평가 불가' · 상세 현재가 '미확인'은 11/19 H1 결정으로 상세에서 현재가 항목을 빼 화면에 없음) | EnrichedHoldingsSection.tsx:645 · 692 · 721 · 722 | POC6-25 B-3 | 없음 | 변경 없음 | Q10 |
| H6 | 전 계좌의 보유 행 수(items.length · EnrichedHoldingsSection.tsx:137 · holdings_capital.py:268 holdings_rows = len(rows))를 '종목'으로 적은 곳 정정: ① 배너 '보유 종목 N개' → '종목 N개 · 보유 행 M개' ② 부분 평가 배너 'a/b종목 기준'(:392 · partial 일 때만 :403-404 에 보임) ③ :394 'b종목 전체'(만들지만 지금은 그리지 않음 · 같이 맞춤) ④ 부분 평가 경고 'n종목은 시세 미확인 … a/b종목만의 부분 합계'(:446-447) ⑤ 자금 카드 'a/b종목'(CapitalContextPanel.tsx:277-279) ⑥ 자금 카드 부분 결론 '보유 a/b종목만 시세 확인'(:325) → ② ~ ⑥ 은 '행' · 계좌 머리(:550) · 계좌 소계(:585) · AI 원문(holdings_capital.py:336-338)은 그대로 | EnrichedHoldingsSection.tsx:392 · 394 · 431-432 · 446-447 · CapitalContextPanel.tsx:277-279 · 325 | POC6-24 B-3(집계 단위 명시) | eval.test.tsx:91('1/2종목 기준') · 나머지 글자 단정(구현 때 grep) | 화면 | Q8 · Q7 |
| H7 | 자금 카드 미입력 = 안내 한 줄(기존 결론 문장 '현금 미입력 — …') + [입력] + '보유 평가액 · 가격 기준일' 칸 · 현금 · 한도 · 확인일 세 칸과 머리 태그 '아직 입력하지 않음'은 뺌 · [비우기] 뒤도 같은 미입력 모양(따로 '비움' 표시 없음) · 배너 총 평가금액과 같은 숫자여도 카드 칸 그대로 · 입력됨 · 0원 · 부분 평가 · 읽기 실패 보기는 그대로 | CapitalContextPanel.tsx:287-291 · 329-333 · 335-374 | POC6-24 B-4(기본 노출 · 미입력을 각각 표시) 미입력 부분 대체(판정 Q13) | CapitalContextPanel.test.tsx:73-82 | 화면 | Q13 · Q16 · Q1 |
| H8 | 입력됨 칸 이름 그대로('검토에 포함할 현금' · '이번 검토의 추가 투입 한도' · '현금 · 한도 확인일' · '보유 평가액 · 가격 기준일') · 입력 현금 포함 비중은 기존 표시 조건 그대로 · 직접 입력한 0원은 금액 '0원'(지금과 같음) · **계좌별 비중 계산 설명(계좌 행 비중 안내 :393-398)은 [자세히] 안 맨 앞으로**(모든 상태 · I-13) · 직접 입력 확인일 문장(:387-392)은 기본 화면 그대로 | CapitalContextPanel.tsx:387-405 | POC6-24 B-2('직접 입력 확인일 화면에 표시' · 유지) · B-3(집계 단위 안내 · 자리만 [자세히] 안으로) | CapitalContextPanel.test.tsx:200-213('기본 화면에 적음' → '[자세히] 안에 적음') | 화면 | Q14 · Q15 · Q16 |
| H9 | 'Naver' → '네이버' 네 곳(버튼 '시세 갱신 (Naver)' :125 · title :123 · 갱신 결과 줄 'Naver 시세 갱신 완료 — 성공 N건 …' :97 · 목록 위 '캐시된 Naver 시세 기준 평가 …' :315) + 기술 낱말 '캐시'(title '캐시에 반영' :123 · 목록 위 '캐시된' :315 · '아직 시세가 캐시되지 않았습니다' :316) → '저장'(예: '저장된 네이버 시세 기준 평가') · 갱신 실패 사유 코드는 그대로 | HoldingsView.tsx:96-100 · 119-126 · EnrichedHoldingsSection.tsx:313-317 | 사용자 결정 '화면 글자는 쉬운 한국어' | 없음(HoldingsView 시험 파일 없음) | 화면 | Q12 |

- 실측 상태: 자금 파일 없음 → NOT_ENTERED · 모든 보유 행 시세 있음 · price_asof 서로 다른 값 ○개(15:30 ~ 15:54 KST) · 출처 전부 naver. 그래서 실화면에서는 미입력 · 정상 행만 보인다. 0원 · 입력 · 부분 · 미확인은 렌더 시험(고정 자료)으로 본다.
- 0원 ↔ 미입력 구별은 이미 된다(cash_krw null ↔ 0 · CapitalContextPanel.tsx:343 '직접 입력한 0원').

## 2. 「종목 관리」(holdings_manage)

| ID | 바꿀 것(판정 반영) | 파일 · 줄 | 닿는 계약 | 고칠 시험 | 구분 | Q |
|---|---|---|---|---|---|---|
| M1 | 상단 [가격 비교 기준일 설정] 버튼 · 창 그리기 · 열림 종류 "reference" · import · historyRevision 상태 · 머리 주석(:9) 제거 → 상단 = [새 보유 추가] · [입력 정정]. fetchTradeHistory 는 남김(과거 보유 · 계좌 목록 · 전량매도 잔량 · 정정에 씀) | HoldingsBookSection.tsx:9 · 31 · 70 · 96-97 · 106 · 111 · 208-215 · 353-360(남김: 131-193 · 202-207) | POC5-07 §1 · §2 일괄 설정 문장(DESIGN_V1.md:18 · 30)을 이 설계가 화면 쪽에서 대체 · 백엔드 계약(대상 1 ~ 200 · 한 번 저장)은 그대로 | ReferenceDate.test.tsx 일괄 창 it 3개(:79 · :112 · :122) → '상단에 일괄 버튼 없음 · [새 보유 추가] · [입력 정정] 있음' it 1개 · describe(:78) 이름 | 화면 | Q46 |
| M2 | ReferenceDateDialog.tsx(창 + 창 전용 대상 선택 함수 referenceTargets · 146줄)를 **함께** `frontend/app/components/_orphaned/` 로 옮겨 보관(삭제 없음 · 새 파일 없음) · README 보관 사유 표에 한 줄(POC6-33 판정 Q17 · 상단 일괄 버튼 제거 · 다건 저장 백엔드 경로는 그대로) · 옮긴 파일의 상대 import(`./Dialog` · `./format` · :11-12)를 `../holdings_manage/…` 로 정정(tsc 대상) | ReferenceDateDialog.tsx → _orphaned/ReferenceDateDialog.tsx · _orphaned/README.md | _orphaned/README.md:3 정의('더 이상 어디서도 import 되지 않는' 파일) 유지 · 사용자 방침(삭제는 사용자 판단 · README:4) · CLAUDE.md §7(파일 삭제 승인) | ReferenceDate.test.tsx import(:26) · referenceTargets 단위 it(:103-110) 제거(I-1) · 다건 저장 계약 = tests/test_poc5_07_reference_date.py:157 · 224 · 379 그대로 · 기간별 설정 · 수정 · 해제 = 같은 파일 History it(:153 · :174 · :186 · :202) | 화면 | Q17 |
| M3 | History 기간 머리 줄 '가격 비교 기준일: 날짜/없음' → **'비교 시작일: 날짜/없음'**(ReferenceDateEditor.tsx:58) · 개별 편집 라벨 → '비교 시작일'(:75) · 같은 파일 머리 주석의 화면 글 인용(:3-4) · [수정/해제] · 저장 · 해제 동작 · 값 그대로 · 저장된 값은 History 를 열어 읽음 · 기준일 없는 새 잔고 등록 기간도 같은 줄('비교 시작일: 없음' · [수정/해제])에서 개별 설정(지금 동작 · 따로 안내 없음) · [시장 흐름 보기] 글 줄(백엔드 항목 이름 · 안내 글 · MarketFlowPanel.tsx:122)은 그대로(I-2 · 11/19 RESULT 판정 §2-2 로 바뀜 → §9-2) | ReferenceDateEditor.tsx:3-4 · 58 · 75 · (읽기만) HistoryCycle.tsx:108-124 · MarketFlowPanel.tsx:89-128 | POC5-07 §2(DESIGN_V1.md:34-35 · 값 · 저장 계약 그대로 · 화면 낱말만) | ReferenceDate.test.tsx:157 · 161 · 177 · 191(낱말) | 화면 | Q18 · Q19 · Q20 |
| M4 | 이번 변경으로 낡는 백엔드 주석 정정(화면 진입 설명: '일괄 설정의 … 화면이 기준일 없는 기간만 보내' → 지금 화면은 History 의 1건만 보냄 · 다건 경로는 백엔드 계약으로 남음) · 동작 무변경 · api_nav_discount.py:143('가장 흔한 값' ↔ 코드 = 최댓값)은 이번 변경과 무관 → 결과서 기록만 | app/holdings_reference_date.py:17-19 | — | 없음(기존 tests/test_poc5_07_reference_date.py 통과 확인) | 백엔드(주석) | Q21 |
| M5 | PROGRAM_TRUTH :303 일괄 버튼 문장 → History 기간별 '비교 시작일' 설정 · 수정 · 해제 · :1175 파일 목록 · 맨 위 변경 이력 · :60 · :327 은 그대로 · POC6-32 '반영 대기' 정정분(Q55)은 이 단계와 따로 커밋 | docs/PROGRAM_TRUTH.md | 기능 변경 시 PROGRAM_TRUTH 갱신 | — | 문서 | Q55 |
| M6 | KS-2 판정 기록: docs/KILL_SWITCHES.md KS-2(:16-18) 아래 '#### KS-2 판정 기록 (2026-11-18, POC6-33 일괄 기준일 화면 경로)' — KS-2 자체는 변경 · 약화하지 않음 · 내용 = 상단 일괄 버튼 제거 · 백엔드 다건 경로(PUT action reference_date · 대상 1 ~ 200)와 저장된 날짜는 그대로 · 화면 = History 기간마다 1건 · 지금 대상 ○건(가림) · 다건 저장 계약은 기존 백엔드 시험 · 출처 = 판정 문서 §2 · 기록 형식 = 같은 문서 KS-11 변경 근거 기록 선례 | docs/KILL_SWITCHES.md | KS-2 · 판정 Q46 | — | 문서 | Q46 |

- **'그래프 시작점' 정정(판정 Q19):** 설계 §2 의 '이미 저장한 날짜는 해당 종목 그래프의 시작점으로 읽는다 · 이 값은 기존 설계상 그래프를 그릴 때 사용하는 기준이다'는 사실과 다르다. 이 날짜를 쓰는 그래프는 없다(holdings_manage/*.tsx 에 svg · 차트 0건 · F7). 실제 용도는 ① History [시장 흐름 보기]의 종가 변화 설명 — '가격 비교 기준일 이후 종가 변화'(이 날짜 종가 → 마지막 저장일 종가 · MarketFlowPanel.tsx:89-105) · 끝난 기간 '가격 비교 기준일 … → 마지막 매도일 종가 변화'(:107-128)의 출발일 ② 같은 글을 그대로 보이는 재진입 검토 창(MarketFlowView · ReentryEvidence.tsx:25 · 202)의 비교 출발일이다. POC5-07 정의 = '종가 비교의 출발점'. 「확인 근거」 · 「보유 현황」 차트는 이 날짜를 읽지 않는다. 목업도 이 설명으로 고쳤다.
- 무관 확인: HoldingsManageView.behavior.test.tsx:72 · 224-225 · NewHoldingDialog.test.tsx:137 · ReentryReviewDialog.test.tsx:212 · 241 · HistoryDialog.test.tsx:163 · 295 는 일괄 버튼을 찾지 않는다(HistoryDialog.test.tsx:162 · 294 는 주석에 '가격 비교 기준일' 낱말만). 백엔드 시험 tests/test_poc5_07_reference_date.py:224 · 261 · 379 는 API 를 그대로 두므로 계속 통과한다.
- 실데이터: History 를 열면 모든 기간(M개)에 머리 줄(구현 뒤 '비교 시작일: 2026-01-02')과 [수정/해제]가 보인다(끝난 기간 ○).

## 3. 「확인 근거」(holdings_evidence)

화면 본체 = HoldingsRiskEvidenceSection.tsx(490줄) · 행 N개(종목 단위 · 개별 주식 포함 · enriched 기준). 같은 근거 응답을 「오늘의 투자 점검」 · Dashboard · WorkbenchHoldingsView · ETFExposureView 도 쓰므로 응답 값 · 공유 함수는 바꾸지 않고 그리기만 바꾼다(판정 Q26 으로 백엔드 변경 없음).

**상세 순서(판정 Q1):** ① 가격 방향 · 시장 대비(E4 첫 줄) → ② 주간 후보 여부 · 순위(E5) → ③ 필요한 자료 안내(E6 · 거른 뒤 남는 문장이 있을 때만) → ④ 가격 · 거래량 · 흔들림 요약(E4 세 묶음 + E9 날짜 역할) → ⑤ 가격 차트(기존 그대로) → ⑥ 구성(E8 주요 편입 → E7 구성종목 중복) → ⑦ NAV(E10). 개별 주식은 ⑥ · ⑦ 대신 'NAV·ETF 구성종목 해당 없음(개별 주식)' 한 줄(E12). 지금 화면(NAV → 구성 · HoldingsRiskEvidenceSection.tsx:104-141)과 순서가 반대인 ⑥ · ⑦ 도 이 순서로.

| ID | 바꿀 것(판정 반영) | 파일 · 줄 | 닿는 계약 | 고칠 시험 | 구분 | Q |
|---|---|---|---|---|---|---|
| E1 | 상단 = ① 현재 보유 점검 상태(기존 조합 문구 + ?) ② 하락 구간 N종목 · 평가 비중 x% ③ 자료 확인 필요 n ④ 가격 기준일 D(한 번) / 보조 한 줄 = 보유 저장 시각(분 단위 한국 시각) · 시장 기준일(D 와 다를 때만 이름 붙여) · 계산 가능 a/b / 구간 정의 · 출처 · 집계는 기존 ? 도움말. 지금 두 번 나오는 D('PC 저장 가격 기준일' · 'PC 가격 흐름 기준일')는 '가격 기준일' 하나 · 그 밖의 'PC' 글자(DeclineSummaryBlock.tsx:21 · :43)는 그대로 · PC 저장 종가의 뜻은 기존 ? 도움말(riskCombination.ts:150-151 HELP_BAND_BASIS)에 둠(I-15) | HoldingsRiskEvidenceSection.tsx:72-75(가짜 fmtKstDate 제거 → today/todayHelpers.ts:38-55 재사용) · 248-270 · lib/priceBasis.ts:22-33 · DeclineSummaryBlock.tsx:14-45 | riskStateFromQueries · buildDeclineSummary · combineRiskState 는 오늘 점검과 공유 → 함수 무변경 · holdings_asof · market_asof 값 무변경(PUSH evidence_asof) | HoldingsRiskEvidenceDecline.test.tsx:154 · 189 · 293 · 321 · 332 · priceBasis.test.ts:32 · HoldingsRiskEvidenceSection.test.tsx:518 | 화면 | Q31 · Q32 · Q4 · Q48 |
| E2 | 행 라벨에 단위 · 기간: '최근 5저장일' · '20저장일' · '같은 기간 KODEX 200 대비(%p)' · '평가 비중(계좌 합산)' · '손익률(계좌 합산)' · 확인 사유 한 줄(기존 하락 구간 · 자료 확인 필요 배지를 문장으로 · 판정 무변경) · 정렬 힌트에 '보유 목록 정렬 = 저장일 변화 기준' · 화면의 '5일 · 20일' 글자를 '저장일'로(아래 '저장일 통일 범위' 목록 전부 · Q47) · KODEX 200 대비는 20저장일만(Q29) | HoldingsRiskEvidenceSection.tsx:314-316 · 325-430(행 칸 이름 :398 '5일' · :407 '20일' · :417 'KODEX200 대비 20일') · holdings_risk_evidence/helpers.ts:180-205 · 253-258 | RiskEvidenceRow · need_check(helpers.ts:129-151)는 오늘 점검과 공유 → 판정 무변경 | Section.test:88 · 92 · 172 · 192 · 295 · 299 · 301 · 307-308 · 317 · 336 · 430 · 533 · Decline.test:199 · 220 · 258 · helpers.test.ts | 화면 | Q28 · Q29 · Q7 · Q47 |
| E3 | 상세를 클릭한 행 바로 아래로(ETF 비교하기 HoldingTable.tsx:76-160 묶음 방식) · 제목 = 이름 · 코드 · 같은 행을 다시 누르면 닫힘 · aria-expanded · 새 묶음 클래스(공유 .wb-hlist · .wb-hrow 는 그대로) · 목록 밖 옛 상세 자리와 '표에서 ETF 를 선택하면 …' 안내 정리 · **위쪽 행 상세가 열린 채 아래 행을 누르면 위 상세가 닫혀 행이 밀려도 누른 행의 화면 위치를 유지**(바뀌기 전 행 위치를 재고 그린 뒤 그 차이만큼 스크롤 · 새 방식) · 빠른 보기로 선택 행이 숨으면 상세도 숨김(선택은 유지) | HoldingsRiskEvidenceSection.tsx:211-214 · 337-343 · 435-480 · globals.css:2519 · 2531-2538 · 3117 | 공유 CSS(OverlapTab · HoldingTable) · PriceChart 조회 수 같음(한 번에 한 종목) · 스크롤 처리 선례: HoldingTable 0건 · scrollIntoView = TodayInvestmentCheckView.tsx:137 · AISessionsListTab.tsx:379 | Section.test:426(제목 'C1 상세') · 행 접근 이름 :185 · 264 · 279 · 505 유지 · Decline.test:142 · 395 · 417 · 551 · 위치 유지는 jsdom 이 배치를 계산하지 않아 렌더 시험으로 못 잡음 → 격리 실화면 확인 | 화면 | Q30 |
| E4 | 상세 첫 줄 = 방향과 시장 대비('최근 20저장일 −○○.○○%(내렸음) · 같은 기간 KODEX 200 대비 −○○.○○%p' · 값 · 부호 + 방향 낱말 '올랐음' · '내렸음' · 표시 값 0.00% = '변화 없음' · I-14) · 거래량 묶음 첫 칸 = 평균 대비 · 가격 흔들림 첫 칸 = 직전 대비(새 칸 이름 · 값은 기존 '직전보다 커짐 · 작아짐 · 같음' priceVolatility.ts:9-13) · 펼침 세 묶음(가격 · 거래량 · 가격 흔들림)을 값 · 기준일의 한 곳으로 · 세 묶음 칸 이름 · 도움말의 '5일 · 20일'도 '저장일'로(Q47) · [세부 흐름 보기] 창 = 차트 · 고른 날 수치 · 날짜 범위(역할) · 창 첫 줄(evidenceStrip)은 뺌 · KODEX 200 대비 값 = 근거 응답 값(Q50) | EvidenceGroups.tsx:17(PRICE_HELP_MEANING) · 36-114(:46 · 50 · 54 · :75-80) · DetailFlowsBody.tsx:76-151 · evidenceStrip.ts:31-72(:41-43) | volumeCells 는 오늘 화면 등과 공유(lib/storedVolume.ts) → 부르는 쪽 순서만 · PROGRAM_TRUTH.md:241 POC5-19('창 = 세 근거 기준일') 변경 | Decline.test:382 · 497 · 533 · 573 · 595 · 609 · 626 · 642 · 673 · Section.test:543 · 568 · 588 · 방향 낱말 세 경우 + 0.00 경계 시험 추가 | 화면 | Q34 · Q37 · Q47 · Q50 |
| E5 | 주간 순위 줄: 화면 들어올 때 GET /market/etf-compare/summary 를 「주간 ETF 점검」과 같은 기본 인자(1개월 · 제외 4종 · 상위 30)로 1회 → 상위 30 안 = '주간 ETF 점검 기준 · 1개월 상위 30 중 n위 · 시작 → 끝 · 인버스 · 레버리지 · 합성 · 선물 제외' / 모집단 안 · 상위 30 밖(하위 30 포함 · Q24) = '순위권 밖 · 1개월 상위 30 밖 · 시작 → 끝 · 같은 제외 조건' / **이 두 줄은 끝 가격 상태를 함께**: intraday → ' · 장중 저장값 기준' · unknown → ' · 마감값 확인 필요'(기존 낱말 lib/etfCompare.ts:82 · 409) · after_close 는 붙이지 않음(Q49 · I-7) / filter_excluded = '규칙상 제외 — 인버스 · 레버리지 · 합성 · 선물 제외 조건'(가격 · 손익 근거는 그대로) / no_price = '자료 확인 불가 — 저장 가격 없음' · period_differs = '자료 확인 불가 — 같은 기간 수익률을 구하지 못함' · 조회 실패 = '자료 확인 불가 — 주간 순위 조회 실패'(이때도 이 종목의 보유 · 가격 · 거래량 · NAV · 구성 근거는 그대로 읽힘 · Q52 · I-8) / stock = 'ETF 순위 대상 아님(개별 주식)'(Q33 · I-12). 공용 outReasonText(ETF 비교하기 · lib/etfCompare.ts:385-396)는 고치지 않고 이 화면 글을 씀. 같은 응답의 보유 exposure(하위 30 겹침 · Q51) · price_flow.kodex200_return_20d_pct(Q50)는 이 화면에 쓰지 않음 | HoldingsRiskEvidenceSection.tsx · holdings_risk_evidence/helpers.ts · lib/api/etfCompare.ts:167-190 · 281-287 · lib/etfCompare.ts:385-427 | 같은 함수 · 인자지만 요청이 따로 = 다른 순간의 DB → 응답의 조건 · 기간을 그대로 표시 · etfCompareKey 캐시를 ETF 비교하기(CompareHead.tsx:35-41) · 오늘 점검(TodayInvestmentCheckView.tsx:430-434)과 공유 · 상태 값 = pc_etf_compare_periods.py:37-39 · 44-69 | Section.test:115('N+1 없음: 목록 조회 2종' → 3종 · mock 추가) · **HoldingsRiskEvidenceDecline.test.tsx:13-26 도 API 4개만 mock → fetchEtfCompareSummary mock 추가**(안 하면 실제 요청이 나감) · 다섯 상태 + 조회 실패 + 끝 가격 상태(순위 · 순위권 밖 × intraday · unknown · after_close) 고정 자료 시험 추가 | 화면 | Q22 · Q24 · Q49 · Q50 · Q51 · Q52 |
| E6 | PC 상세 '필요한 자료 안내'(지금 이름 '자료 확인 안내')에서 builder notes 를 판정 세 갈래로 거름(프론트): 옛 Market Discovery 네 문장 · 상세 수치의 반복 안내 · 범위 없는 구성 중복 문구 · **자료 부족 안내는 남김** — 문장별 분류 = I-3(남는 목록 문장 = '단기 흐름은 데이터 부족으로 확인할 수 없습니다'(:383) · 기술 낱말이 든 자료 부족 문장 셋은 같은 상세의 구성 줄 · NAV 묶음이 같은 사실을 쉬운 한국어로 보임) · 거른 뒤 남는 문장이 없으면 줄 없음 · 공유 builder · PUSH · 초안 무변경 | holdings_risk_evidence/helpers.ts:331(evidenceGuidance) | builder notes 순서 전제(pc_price_basis.py:148-149) 그대로 · 문장이 바뀌면 거르기가 풀림 → 문장 상수 시험으로 고정 | helpers.test.ts:357(문장 상수 · 거르는 문장 모두로 늘림) · 370 · 393 · 412 · Section.test:346 · 408 · 418 | 화면 | Q23 |
| E7 | '구성종목 중복' 줄(2026-11-19 RESULT 판정 §2-1 수용 규칙) = **'비교 범위 확인 불가'를 먼저** + 비교 목록 '1개월 상위 10개 후보 · 시작 → 끝 · 인버스 · 레버리지 · 합성 · 선물 제외'(주간 순위의 상위 30 과 따로 고른 목록 · topn_basis · topnBasisText · 이미 받은 값 · POC6-32 I-22 선례 · 기간 · 제외 조건 = 이 후보 목록의 기준) + 실제 비교 규칙 '후보 둘 이상의 구성 상위 10행에 함께 나온 종목 ↔ 선택한 보유 ETF 구성 상위 10행 · 상위 10행 = 비교 상한'(builder compute_repeated_core_holdings min_appears=2 · 후보 한 곳에만 있는 종목은 비교 대상 아님). 실제 비교에 쓴 구성 기준일 · 행 수가 응답에 없어(반환 = status + 겹침 목록 · holdings_market_evidence.py:310-313) **'중복 없음' · 겹침 건수 · 비율은 표시하지 않음** · 찾은 종목이 있으면 '확인된 겹침'에 이름 · 비중은 응답으로 가리키는 대상을 확인할 수 있을 때만 '이 ETF 편입 비중 ○.○○%'처럼 뜻을 붙여 표시(건수 숫자 없음 · I-4) · '주요 편입'(E8)의 날짜 · 범위는 그 자료에 붙임 · status 가 ok 가 아니면 '구성종목 확인 불가 — 이 ETF 의 저장 구성 자료 없음'(constituents_unavailable) · '구성종목 확인 불가 — 비교 후보의 구성 자료 없음'(market_core_unavailable) · 원문 코드는 보이지 않음(I-3) · 겹침 목록은 지금처럼 1개월 상위 10개(순위 줄 상위 30 과 이름으로 구별 · Q25) | HoldingsRiskEvidenceSection.tsx:123-141 · HoldingsOverlapBridgeCard.tsx:73(topnBasisText 는 이미 export · 고침 없음 · import 만) | 겹침 계산 · 결과는 builder 값 그대로 · holdings_market_evidence.py(620) 무변경 · HoldingLink.exposure(compared_etf_count 등 · lib/api/etfCompare.ts:180-188)는 하위 30 목록과의 겹침(pc_etf_compare_summary.py:457)이라 뜻이 달라 쓰지 않음(Q51) | 범위 글 · 겹침 없음 / 있음 / 확인 불가 두 갈래 렌더 시험 추가 · ETFExposureView.test.tsx:397(topnBasisText) 그대로 통과 | 화면 | Q25 · Q26 · Q51 |
| E8 | 선택 ETF 주요 편입 · 구성 기준일 · 상태 = 상세 열 때 GET /market/constituents/summary?ticker= 1회(기존 읽기 API · 한 읽기 mode=ro · 수집 없음) · 그 자료의 기준일을 붙임 · 상태는 기존 글자 그대로(state_label = '미수집' · '원천 기준일 미확인' · '상위 N행만 확인' · '전체 확인' · '구성 자료를 읽지 못함' · weekly_candidate_review.py:107-114). 이 응답은 원천일이 확인된 구성을 먼저 고르고 없을 때만 저장 최신 구성(weekly_candidate_reads.py:7-8 · weekly_candidate_review.py:80-96 · api_weekly_review.py:263)이라 저장 MAX(asof)를 쓰는 겹침 builder(E7)와 같은 ETF 에서 구성 기준일이 다를 수 있음 → E8 줄은 자기 기준일을 붙이고 E7 과 묶지 않음 | lib/api/etfExposure.ts:205-208 · api_weekly_review.py:260-285 | mode=ro | 상세 시험 추가 · Section.test · **Decline.test:13-26 에 fetchConstituentsSummary mock 추가** | 화면 | Q27 |
| E9 | 날짜 역할 표시(세 묶음 바로 아래): 20저장일 수익률 = '시작 종가 10/21 → 끝 종가 11/18' · 창 차트 = '표시 기간 10/22 ~ 11/18 · 최근 20개 저장일' · 거래량 평균 = '비교 구간 10/21 ~ 11/17' · 날짜는 백엔드 값만 씀 · 백엔드 무변경 | DetailFlowsBody.tsx:94-96 · 143 · declineSummary.ts:90-91 · volumeTrend.ts:10-11 · lib/priceBasis.ts(머리말 '날짜를 코드에 두지 않는다') | volume_trend 20점(PROGRAM_TRUTH POC5-19 · tests/test_pc_volume_trend.py:45) 그대로 | Section.test:559 · 580 · Decline.test:229 · 258 · 497 · priceBasis.test.ts:48 | 화면 | Q35 |
| E10 | NAV 묶음(이름 '순자산가치(NAV) · 괴리율' = 이 화면 첫 표기 · I-10) 한 묶음에서 **시장가 · NAV · 괴리율(+부호) · 기준일 · 출처 · 수집 상태**를 늘 읽음: 괴리율 절대값 3% · 5% 이상이면 '괴리 확인 필요(3% 이상)' · '괴리 주의(5% 이상)'(기존 기준 · 색) · 기준일 = 'asof' 대신 '기준일' · 이전 목록 재사용 행은 '재저장일'(I-9) · 출처 = 사전('네이버' · 사전 밖 '기타 출처') · 수집 상태 = 사전('수집됨' · '이전 목록 재사용' · '확인 불가' · 사전 밖 '상태 확인 필요') · ? 도움말 = 괴리율 뜻(양수 = 그 기준 시점의 시장가가 NAV 보다 높았다는 뜻) · NAV = 순자산가치 · 3% · 5% 기준 · 접힌 [자세히] = 받은 안내 원문(message) · 사전 밖 원문(Q36 · I-11) · 근거 항목이 없을 때 글 '시장 evidence 자료가 없어 …'(:86) → '시장 근거 자료가 없어 …' | HoldingsRiskEvidenceSection.tsx:84-122 | 값 = 근거 응답 nav_discount(추가 조회 없음 · 같은 store · 같은 flag 함수 · source 칸 이미 있음 lib/api/holdings.ts:245-254 · holdings_market_evidence.py:316-341) · 부호 (시장가 − NAV)/NAV × 100(etf_nav_fetcher.py:61-67) · **POC2 표시 계약**(Holdings Evidence 의 NAV · 시장가격 · 괴리율 · asof · source · status 를 모두 줄에 · POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md:74-81)을 판정 Q54 로 지킴 | Section.test:138-161(partial '부분 자료' → '이전 목록 재사용' · message 는 [자세히] 안) · 543 · 565 · 588 · 591('NAV · 괴리율' → '순자산가치(NAV) · 괴리율') · 출처 · 수집 상태 · 재저장일 · 사전 밖 · 3 · 5 경계 · 음수 사례 추가 | 화면 | Q3 · Q36 · Q38 · Q39 · Q40 · Q53 · Q54 |
| E11 | [전체 ETF NAV·괴리율 보기 →] 제거(전체 표는 「데이터 상태」에서 조회) · onNavigate prop 정리 · 「오늘의 투자 점검」 같은 버튼은 남김 · 그 주석('기존 버튼 낱말(HoldingsRiskEvidenceSection)을 그대로')이 낡아 고침 · 화면 머리 주석 'unavailable 사유 확인은 "데이터 상태"로 이동(§7)'도 낡음 → 고침 | HoldingsRiskEvidenceSection.tsx:471-479 · HoldingsEvidenceView.tsx:8-9 · 18-27 · MainPanel.tsx:88-90 · today/maintenanceQueue.ts:52-53 | KS-2(접근 경로 = 메뉴 · 오늘 점검 버튼 유지) · PROGRAM_TRUTH.md:241 | Section.test:442 → '버튼 없음' 단정 · TodayInvestmentCheckView.test.tsx:548-563 그대로 | 화면 | Q54 |
| E12 | 개별 주식(○종목 · 요약 응답 is_stock · out_reason 'stock' 으로 확인될 때 · I-12) 상세: 순위 줄 'ETF 순위 대상 아님(개별 주식)' · 구성 · NAV 두 묶음 대신 'NAV·ETF 구성종목 해당 없음(개별 주식)' 한 줄 · 영어 message('NAV / discount source not integrated' · holdings_market_evidence.py:331) · '(constituents_unavailable)' 원문 · '필요한 자료 안내'의 '캐시' · 'source' 문장(:394 · :399)은 보이지 않음 | HoldingsRiskEvidenceSection.tsx:89-141 · holdings_risk_evidence/helpers.ts:331 | ETF 비교하기 선례: 보유 상세 '개별 주식 — NAV · ETF 구성종목 해당 없음'(HoldingRowDetail.tsx:160 · HoldingTable.tsx:9 판정 Q6) · 행 상세 '기준가(NAV) · 괴리율: 해당 없음(개별 주식)'(DetailNumbers.tsx:74) | 사례 시험 추가(확인됨 · 요약 조회 실패 두 경우) | 화면 | Q33 · Q53 |

- E4 예시(보유 A · 값은 '○'): '최근 20저장일 −○○.○○%(내렸음) · 같은 기간 KODEX 200 대비 −○○.○○%p'. 값 = row.return_20d_pct · excess_vs_kodex200_20d_pctp(근거 응답). E5 가 새로 받는 요약 응답의 price_flow.kodex200_return_20d_pct(pc_etf_compare_holdings.py:67 · 72-75 · pc_etf_compare_summary.py:423-424)는 근거 응답과 다른 순간에 읽은 값이라 쓰지 않는다(판정 Q50).
- **저장일 통일 범위**(지금 행 '5일 · 20일' · 요약 '20저장일' · notes '20거래일'이 섞여 있음 → 화면은 '저장일'로 · grep 실측 · 「확인 근거」 안만 · lib/priceBasis.ts 는 이 화면만 씀 · 판정 Q47 = 전부):
  - 행 칸 이름 HoldingsRiskEvidenceSection.tsx:398 · 407 · 417 · 섹션 소개 글 :224-228('최근 5일·20일 흐름과 KODEX200 대비 위치')
  - 정렬 이름 '5일 변화' · '20일 변화'(holdings_risk_evidence/helpers.ts:253-258) → '5저장일 변화' · '20저장일 변화' — 이 글자로 버튼을 찾는 시험 Section.test:299 · 301 · 307-308 · 430 · 533
  - 세 묶음 칸 이름 · 도움말(EvidenceGroups.tsx:17 · 46 · 50 · 54) · 창 첫 줄(evidenceStrip.ts:41-43 · E4 에서 뺌)
  - 목록 위 기준 줄 '가격 흐름(5일 · 20일 · KODEX200 대비)' · 'KODEX200 20일 비교 기간'(lib/priceBasis.ts:24 · 26) · 상세 기준 줄(:61) — 시험 priceBasis.test.ts:34 · 41 · 44 · 56 · 60 · Section.test:521 · 559 · 580
  - 계좌별 값 불일치 문장 '(상태 · 5일 · 20일 · KODEX200 대비)'(helpers.ts:321) — 시험 Section.test:403
  - notes '20거래일 …' 은 E6 에서 거름
  - 'PC' 글자(DeclineSummaryBlock.tsx:21 · 43)는 저장일 낱말과 따로 · 그대로(Q48 · I-15)

## 4. 「데이터 상태」(data_status)

화면 = DataStatusView.tsx(357줄) · API = GET /market/nav-discount/latest(app/api_nav_discount.py:113-160 · items 는 전체 행 · 화면이 상위 200건만 그림 :296). 원값은 API 계약 그대로 두고 화면 글자만 바꾼다. 지금 화면 시험 파일 없음 → 화면만 바꾸면 깨지는 기존 시험 0(백엔드 tests/test_api_nav_discount.py 등은 원값 고정 · 그대로 통과).

| ID | 바꿀 것(판정 반영) | 파일 · 줄 | 닿는 계약 | 고칠 시험 | 구분 | Q |
|---|---|---|---|---|---|---|
| D1 | 수집 상태 사전: ok → '수집됨' · partial → '이전 목록 재사용' · unavailable → '확인 불가' · 사전 밖 → '상태 확인 필요'(원문 = [자세히] · I-11) · 배지 · 필터 선택지 · 요약 줄 글자 · **요약 줄의 수집됨 · 확인 불가 · 기타 건수는 화면이 같은 응답 items 전체에서 필터와 같은 판정 함수 하나로 셈**(기타 = ok · unavailable 이 아닌 값 · partial 포함 → 요약 '기타' = 필터 '기타' 결과 · I-6) · 필터 값(ok · unavailable · other) · 배지 색 그대로 | DataStatusView.tsx:62-71 · 91-108 · 228-233 · 259-262 · 343 | 백엔드 summary(failed_count = partial 제외 · api_nav_discount.py:139-141)와 API 계약 무변경(오늘 점검 · 대시보드가 쓰는 summary 숫자 · maintenanceQueue.ts:205-236 등) | 없음 → D7 | 화면 | Q39 · Q43 |
| D2 | 괴리율 표시 사전: discount_check_needed → '괴리 확인 필요(3% 이상)' · discount_warning → '괴리 주의(5% 이상)'(기존 DetailNumbers 글자) · 절대값 기준(3 · 5) · 산식 · 숫자 색(5% 이상 --danger · 3% 이상 --warn) · 표시 글자 색(--warn) 그대로 | DataStatusView.tsx:54-60 · 329-336 · DetailNumbers.tsx:67-70 · 78 | etf_nav_fetcher.py:13('데이터 품질 확인용 · 매수/매도 판단 X') | 백엔드 tests/test_etf_nav.py:56 등 그대로 | 화면 | Q38 · Q44 |
| D3 | 영어 · 기계 글자 → 한국어(이 화면 안 전부 · I-5): 제목 'Data Status' → '데이터 상태' · 부제의 첫 NAV → '순자산가치(NAV)'(Q53 · I-10) · 안내 띠(표 이름 `etf_nav_daily` · 'SQLite' · 'Naver ETF universe' 빼고 쉬운 글) · 머리 ticker → '코드' · asof → '기준일' · source → '출처' · status → '수집 상태' · 고르기 라벨 '상태' → '수집 상태' · 정렬 선택지 '괴리율 \|abs\|' → '괴리율 절대값' · 'ticker' → '코드' · 검색 안내 'ticker / ETF명' → '코드 / ETF명' · 요약 'asof' → '가장 최근 기준일'(값 = 행 기준일 최댓값 · api_nav_discount.py:144-145) · 각 행 = 그 행 날짜 · 이전 목록 재사용 행 날짜 = '재저장일 YYYY-MM-DD'(Q40 · I-9) · 빈 · 오류 카드 문구 | DataStatusView.tsx:131-139 · 175 · 230-232 · 249 · 254 · 261 · 271-273 · 302-311 | POC2 표시 계약(asof · source · status 각각 별도 열 · POC2_NAV_DISCOUNT_DISPLAY_FIX_CONCLUSION.md:22-25 · 79-81) → 열 유지 · 글자만 | 없음 → D7 | 화면 | Q40 · Q41 · Q53 |
| D4 | 출처 사전: naver_etf_item_list → '네이버' · 사전 밖 → '기타 출처'(원문 = [자세히] · I-11) · 행 칸 · 요약 줄 · 응답 source null(출처가 둘 이상이거나 없음) → 지금처럼 '-' | DataStatusView.tsx:224 · 232 · 339-341 | — | 없음 → D7 | 화면 | Q3 |
| D5 | 표 위 뜻 두 줄: ① 수집 상태 = 그 기준일에 NAV · 시장가 · 괴리율을 받았는지 ② 괴리율 표시 = 받은 값의 괴리율 절대값이 3% · 5% 이상인지(데이터 확인용 · 매수 · 매도 판단 아님) · 괴리율 양수 = 시장가가 NAV 보다 높음 · 기존 문장(maintenanceQueue.ts:190) 낱말 재사용 | DataStatusView.tsx:132-140 | 설계 §4 '뜻을 각각 읽을 수 있다' | D7 | 화면 | Q2 |
| D6 | 사용자용 한국어 표기(수집 상태 · 괴리율 표시 · 출처 사전 · '재저장일' 판정 · 사전 밖 글)를 프론트 공용 새 파일 하나에 두고 「데이터 상태」 · 확인 근거 NAV 묶음 · ETF 비교하기(DetailNumbers 괴리 표시 · 글자 같음)가 같이 씀 · 백엔드 · API 무변경 | 새 frontend/lib/navLabels.ts(이름 확정 전) · DetailNumbers.tsx:67-70 | — | — | 화면 | Q42 |
| D7 | 화면 시험 새 파일: status ok · partial · unavailable · 사전 밖 / flag 없음 · 3 · 5 경계(2.99 · 3 · 4.99 · 5) · 음수(−3 · −5) / 출처 사전 안 · 밖 · null / **partial 포함 고정 자료로 요약 '기타' 건수 = 필터 '기타' 결과 건수** · 전체 · 수집됨 · 확인 불가 건수 / 재저장일 · 가장 최근 기준일 | 새 frontend/app/components/DataStatusView.test.tsx | vitest mock 관례(DashboardView.test.tsx:11-17 · 107-111) | 새로 | 화면 | Q45 |

- 같은 원문이 남는 다른 곳(이번에는 고치지 않음 · 결과서에 목록 · Q41 · I-5): NavDiscountPlaceholderCard.tsx:62-63 · 82 · 94-96 · 113-126 · marketDiscoveryCopyText.ts:349-358(AI 복사 글) · _orphaned/HoldingsMarketEvidenceCard.tsx:237-261.

## 5. 반영 확인(설계 §5 · 판정 §5) · 확인 방법

판정 §5: 이 표로 검증한다. 격리 화면에서 ① 보유 행을 펼치고 ② 이력(History)에서 비교 시작일을 읽고 ③ 「확인 근거」 상세를 위 행에서 아래 행으로 바꿔 연다. 주간 순위는 같은 조건 · 같은 자료로 대조한다. 문서 · 목업 · 결과서는 공개 저장소의 보유 정보 가림 기준(머리 '보유 표기')을 지킨다.

| 설계 §5 동선 | 확인할 결과 | 이 PLAN 항목 | 확인 방법 | 확인 주체 |
|---|---|---|---|---|
| 보유 현황의 요약과 행 펼침 | 평가 비중 · 매입 비중 · 시세 기준을 읽음 · 상세에 수량 · 평균 매입단가 · 현재가 없음(현재가 = 11/19 H1 결정) · 미입력 · 0원 · 입력 구별 · 계좌별 비중 설명은 [자세히] | H1 ~ H9 | 렌더 시험(미입력 · 0원 · 입력 · 부분 · 읽기 실패 · 시각 형식 네 가지 · 매입 비중 null · 사전 밖 출처) · 격리 실화면(보유 행 하나 펼침 · 운영 = 미입력 · 모든 행 시세 있음) | 사용자 실화면 |
| 종목 관리와 기존 보유 이력 | 상단 두 버튼 · History '비교 시작일' · 개별 수정 · 해제 | M1 ~ M3 | 대체 단정 시험 · HistoryDialog.test 그대로 · 격리 실화면(모든 기간 '비교 시작일: 2026-01-02' · [수정/해제] 보임 · **저장은 누르지 않음** · 쓰기 경로는 기존 고정 자료 시험) | 사용자 실화면 |
| 확인 근거에서 보유 ETF 선택 | 상세가 그 행 아래 · 판정 순서(방향 → 순위 → 자료 안내 → 요약 → 차트 → 구성 → NAV) · 같은 ETF 의 가격 · 거래량 · NAV 근거 · 수익률 기간과 차트 기간 | E3 · E4 · E9 · E10 · E12 | 렌더 시험 · 격리 실화면(보유 ETF 하나: '시작 종가 10/21' · '표시 기간 10/22 ~ 11/18' · NAV 묶음 여섯 칸 · 위쪽 행 상세가 열린 채 아래 행을 눌러도 누른 행 위치 유지) | 사용자 실화면 |
| 후보 기준 · 자료 예외 | 같은 자료로 주간 결과 대조 · 포함 / 순위권 밖 / 규칙상 제외 / 자료 확인 불가 · 끝 가격 상태 · 비교 사유 · 겹침 '비교 범위 확인 불가' | E5 · E6 · E7 · E8 | 고정 자료 시험(네 상태 + 개별 주식 + 조회 실패 + 끝 가격 상태) · 실데이터(상태별 보유 건수 ○ · 실데이터에 없는 상태(예: 상위 30 안 보유가 없으면 '포함')는 고정 자료로만) · 같은 시각 「주간 ETF 점검」 화면과 대조 | 사용자 실화면 |
| 데이터 상태 | 수집 상태 · 괴리율 경고의 뜻을 각각 읽음 · '기타' 요약 = 필터 결과 · 종목별 확인의 시작과 끝은 그 종목 상세 | D1 ~ D7 · E10 · E11 | 새 화면 시험(partial 포함 고정 자료 건수 대조) · 격리 실화면('수집됨' + 괴리율 표시 4행) | 사용자 실화면 |
| 문서 · 기록 | KS-2 판정 기록 · PROGRAM_TRUTH 갱신 · 보관 폴더 README · 백엔드 주석 | M2 · M4 · M5 · M6 | grep 대조(낡은 낱말 · 줄) | 검증자 |

- 검사(완료 때 한 번): `npx tsc --noEmit` · `npm run lint` · `npx vitest run` 전체. dev 서버가 켜진 동안 `npm run build` 는 하지 않는다.
- 백엔드(M4 주석 한 줄 · 동작 무변경): `black --check` · `flake8` · `py_compile` · tests/test_poc5_07_reference_date.py · 커밋 전 전체 pytest 1회 · 새 시험은 tmp DB · 고정 자료(라이브 DB · 보유 파일을 열지 않음).
- 결과서에는 보유 이름 · 코드 · 수량 · 가격 · 금액 · 계좌 이름을 쓰지 않는다. 보유 한 종목의 수익률 · KODEX 200 대비 · 괴리율 · 구성 행 수 · 상품 종류를 함께 적지 않는다. 보유 집계(종목 수 · 행 수 · 계좌 수 · 상태별 건수 등)는 N · M · ○ 로 적는다(머리 '보유 표기').
- 위 실화면 값(10/21 · 10/22 · 모집단 963 · 1,212행 · 괴리율 표시 4행 등 · 보유 상태별 건수는 가림)은 2026-11-18 자료 기준이다. 다음 거래일 갱신 뒤에는 바뀌므로 실화면을 볼 때 같은 방법(mode=ro 조회 · 같은 인자의 build_summary · 「주간 ETF 점검」 화면)으로 그 자리에서 다시 재고 그 값으로 대조한다.

## 6. 파일(예상) · 줄 수(2026-11-18 wc -l 실측)

| 구분 | 파일 | 지금 줄 수 | 항목 |
|---|---|---|---|
| 화면 고침 | frontend/app/components/EnrichedHoldingsSection.tsx | 735 | H1 · H2 · H3 · H4 · H6 · H9 |
| 화면 고침 | frontend/app/components/holdings/CapitalContextPanel.tsx | 408 | H2 · H6 · H7 · H8 |
| 화면 고침 | frontend/app/components/HoldingsView.tsx | 166 | H9 |
| 화면 고침 | frontend/lib/holdings_view.ts | 186 | H4 형식 함수 |
| 화면 고침 | frontend/app/components/holdings_manage/HoldingsBookSection.tsx | 376(약 20줄 감소 예상) | M1 |
| 화면 이동 | frontend/app/components/holdings_manage/ReferenceDateDialog.tsx → frontend/app/components/_orphaned/ReferenceDateDialog.tsx | 146 | M2(창 · 함수 함께 · 상대 import 경로만 정정) |
| 화면 고침 | frontend/app/components/_orphaned/README.md | 16 | M2 |
| 화면 고침 | frontend/app/components/holdings_manage/ReferenceDateEditor.tsx | 109 | M3 |
| 화면 고침 | frontend/app/components/HoldingsRiskEvidenceSection.tsx | 490 | E1 ~ E12 |
| 화면 고침 | holdings_risk_evidence/ helpers.ts 333 · EvidenceGroups.tsx 116 · DetailFlowsBody.tsx 154 · DeclineSummaryBlock.tsx 47 · volumeTrend.ts 26 | 표기 | E1 · E2 · E4 · E5 · E6 · E9 |
| 화면 고침 | frontend/lib/priceBasis.ts | 62 | E1 · E2(저장일 · Q47) |
| 화면 고침 | HoldingsEvidenceView.tsx(주석 :8-9 포함) · MainPanel.tsx · today/maintenanceQueue.ts | 30 · 191 · 243 | E11 |
| 고침 없음(import 만) | HoldingsOverlapBridgeCard.tsx(topnBasisText 는 :73 에서 이미 export) | 245 | E7 |
| 화면 고침 | frontend/app/components/DataStatusView.tsx · workbench/DetailNumbers.tsx | 357 · 155 | D1 ~ D6 |
| 화면 고침 | frontend/app/globals.css | 4356 | E3 · E10 새 묶음 클래스 |
| 화면 새 파일 | frontend/lib/navLabels.ts(이름 확정 전) · frontend/app/components/DataStatusView.test.tsx | — | D6 · D7 |
| 화면 시험 고침 | EnrichedHoldingsSection.eval.test.tsx 165 · CapitalContextPanel.test.tsx 449 · ReferenceDate.test.tsx 241 · HoldingsRiskEvidenceSection.test.tsx 599 · HoldingsRiskEvidenceDecline.test.tsx 699(API mock 2개 추가 · E5 · E8) · holdings_risk_evidence/helpers.test.ts 428 · lib/priceBasis.test.ts 63 | 표기 | 각 표 |
| 백엔드 고침(주석) | app/holdings_reference_date.py | 160 | M4(Q21) |
| 문서 | docs/PROGRAM_TRUTH.md(:241 확인 근거 · :243 데이터 상태 · :303 종목 관리 · :304 · :338 · :1134 · :1175 · 맨 위 이력) | 1293 | M5 |
| 문서 | docs/KILL_SWITCHES.md(KS-2 :16-18 아래 판정 기록) | 214 | M6 |
| 문서 | 결과서 docs/ai_result/POC6/POC6_33_HOLDINGS_UI_REVIEW_RESULT.md | — | 전체 |

- **KS-10:** 화면 컴포넌트 최대 735(EnrichedHoldingsSection) · 근접 850 미만 유지. `HoldingsRiskEvidenceSection.tsx`(490)는 상세를 행 안으로 옮기고 순서 · NAV 묶음이 늘어도 근접선 밖 예상 · 넘을 기미면 상세 묶음을 holdings_risk_evidence/ 아래 새 파일로 분리(결과서에 실측). 백엔드 `holdings_market_evidence.py` 620(근접선 넘음) · `app/api.py` 595 · `pc_etf_compare_summary.py` 529 · `holdings_capital.py` 425 무변경. 시험 `tests/test_poc6_32_weekly_review.py` 1406(근접 1450) 무변경. globals.css 는 컴포넌트 기준 밖.
- **무변경 확인 대상:** app/holdings_market_evidence.py · app/pc_price_basis.py · app/market_topn.py · app/api_weekly_review.py · app/stored_volume_evidence.py · app/holdings_capital.py · app/api_nav_discount.py · app/holdings_market_flow.py · AI 원문(holdings_capital.preview_lines · decision_preview_lines.py).
- 파일 이동(M2)은 Dockerfile · 배포 스크립트 영향을 구현 때 grep 으로 확인한다(DEV_RULES 2.3).
- Q55(PROGRAM_TRUTH 의 POC6-32 반영 상태 정정 · 2026-11-18 정정 완료)는 이 단계 변경과 섞지 않고 그 한 파일만 따로 커밋한다(§7 Q55).

## 7. 설계자 판정 반영(Q0 ~ Q55)

판정 문서(머리 DECISION) 기준 · 한 질문 한 줄. '적용 해석' 칸의 I-n 은 판정 글이 열어 둔 구현 세부를 개발자가 가장 좁게 읽은 것(§9-1 · 2026-11-19 RESULT 판정 §3 으로 확정 · §9-2).

| Q | 화면 | 판정 반영 내용 | PLAN 항목 | 적용 해석 |
|---|---|---|---|---|
| Q0 | 공통 | 단계 번호 POC6-33 확정 · 설계 · PLAN · 목업 · 결과서에 같은 번호 | 머리 | — |
| Q1 | 공통 | 목업의 요약 · 행 아래 상세 배치 적용 · 「확인 근거」 상세 순서 = 가격 방향 → 순위 → 필요한 자료 안내 → 가격 · 거래량 · 흔들림 요약 → 차트 → 구성 → NAV | §3 상세 순서 · E3 · H1 · H7 | — |
| Q2 | 공통 | 사용자 문구에 판정 표기를 적용(원안 새 낱말 + '비교 시작일' · '순자산가치(NAV)' · '재저장일' · '가장 최근 기준일' · '기타 출처' · '상태 확인 필요' · '비교 범위 확인 불가' · '변화 없음') · 목업의 부제 · 안내 띠 · 뜻 두 줄 · 도움말 글 | 전체 · D5 | — |
| Q3 | 데이터 상태 · 확인 근거 · 보유 현황 | 사전 밖 출처 = '기타 출처' · 확인되지 않은 수집 상태 = '상태 확인 필요' · 원문은 필요하면 [자세히] | D1 · D4 · E10 · H4 | I-11 |
| Q4 | 보유 현황 · 확인 근거 | 「보유 현황」 가격 기준시각 = 초까지 한국 시각 · 「확인 근거」 보유 저장 시각 = 분 단위 한국 시각(fmtKstDate 재사용) | H4 · E1 | — |
| Q5 | 보유 현황 | 펼친 상세에서 요약과 반복되는 수량 · 평균 매입단가를 뺌 · 상세 = 매입금액 · 평가금액 · 매입 기준 비중 · 시세 정보와 현재가(현재가는 11/19 형수님 결정으로 뺌 · RESULT 판정 §2-0 수용 · H1) | H1 | — |
| Q6 | 보유 현황 | 요약 행 '보유 내 비중(평가 기준)' = 계좌별 평가 비중 · 상세 '매입 기준 비중' | H2 | — |
| Q7 | 보유 현황 · 확인 근거 | 「보유 현황」 = 계좌별 평가 비중 · 「확인 근거」 = '평가 비중(계좌 합산)' · '손익률(계좌 합산)' · 「보유 현황」에 종목 합산 비중 추가 없음 | H2 · E2 | — |
| Q8 | 보유 현황 | 종목 수와 계좌별 보유 행 수를 구별(배너 둘 다 · 행 수를 '종목'으로 적은 다섯 곳 '행') | H6 | — |
| Q9 | 보유 현황 | 매입 기준 비중 값 없음 = '비중 계산 불가' | H3 | — |
| Q10 | 보유 현황 | 현재가 '미확인' · 평가금액 '평가 불가'(기존 글 그대로 · 현재가는 요약 행 '현재 미확인'에서 읽음 · 11/19 H1) | H5 | — |
| Q11 | 보유 현황 | 기준시각 · 출처 같은 줄 · 날짜만 저장된 값은 날짜만 | H4 | — |
| Q12 | 보유 현황 | 화면 용어 '네이버' · '저장' · 실패 사유 코드는 그대로 | H9 | — |
| Q13 | 보유 현황 | 현금 미입력 = 안내 한 줄 · 보유 평가액 · 가격 기준일 · [입력] | H7 | — |
| Q14 | 보유 현황 | '현금 · 한도 확인일' · 입력 현금 포함 비중은 기존 표시 조건대로 · 직접 입력한 0원 = 금액 | H8 | — |
| Q15 | 보유 현황 | 계좌별 비중 계산 설명은 [자세히] 안 | H8 | I-13 |
| Q16 | 보유 현황 | [비우기] 뒤 = 미입력 표시 · 배너 총 평가금액과 카드 보유 평가액은 둘 다 둠 | H7 | — |
| Q17 | 종목 관리 | ReferenceDateDialog 와 창 전용 대상 선택 함수를 함께 보관(`_orphaned/`) · README 에 사유 · 기간별 설정 · 수정 · 해제는 [History]에서 확인 · 다건 저장 API 계약은 기존 시험 | M2 | I-1 |
| Q18 | 종목 관리 | [History] 표시와 개별 편집 라벨 = '비교 시작일' | M3 | I-2 |
| Q19 | 종목 관리 | 실제 용도 = [시장 흐름 보기] 종가 변화 설명 · 재진입 검토의 비교 출발일 · 설계의 '그래프 시작점' 설명을 PLAN · 목업에서 정정 | §2 정정 · F7 · 목업 | — |
| Q20 | 종목 관리 | 저장된 값을 History 에서 열어 봄 · 기준일 없는 새 잔고 등록도 History 에서 개별 설정(따로 안내 없음) | M3 | — |
| Q21 | 종목 관리 | 화면 진입을 설명하는 기준일 백엔드 주석 정정 · api_nav_discount.py:143 은 결과서 기록만 | M4 | — |
| Q22 | 확인 근거 | 화면 진입 때 기존 GET /market/etf-compare/summary 를 주간 점검과 같은 기본 인자로 한 번 · 1개월 상위 30 · 제외 4종 | E5 | — |
| Q23 | 확인 근거 | PC 화면에서 옛 MD TOP 10 · 상세 수치의 반복 안내 · 범위 없는 구성 중복 문구를 거름 · 자료 부족 안내는 남김 · 기존 하락 구간 · 자료 확인 사유는 행에 | E6 | I-3 |
| Q24 | 확인 근거 | 모집단 안 하위 30 = '순위권 밖' | E5 | — |
| Q25 | 확인 근거 | 겹침 = 1개월 상위 10개 후보 목록 유지 · 목록 범위와 실제 비교 범위 구별 · 상위 10행 = 비교 상한 | E7 | I-4 |
| Q26 | 확인 근거 | 응답에 실제 비교 구성 기준일 · 행 수가 없음 → '비교 범위 확인 불가' · '중복 없음' · 겹침 건수는 같은 계산의 범위를 확인할 때만 · 백엔드 무변경 | E7 | I-4 |
| Q27 | 확인 근거 | 선택 ETF 주요 편입 · 상태 = 상세 열 때 기존 구성 요약에서 읽고 그 자료의 기준일을 붙임 | E8 | — |
| Q28 | 확인 근거 | 기존 하락 구간 · 자료 확인 사유를 행에 표시(판정 무변경) | E2 | — |
| Q29 | 확인 근거 | KODEX 200 대비 = 20저장일만 · 그 값은 근거 응답에서 계산된 값 | E2 · E4 | — |
| Q30 | 확인 근거 | 클릭 행 바로 아래 펼침 · 같은 행 다시 누르면 닫힘 · 위 상세가 닫혀 아래 행이 밀려도 클릭 행 화면 위치 유지 | E3 | — |
| Q31 | 확인 근거 | 중복된 PC 가격 흐름 기준일을 '가격 기준일'로 한 번 · 시장 기준일이 따로 필요하면 이름을 붙임 | E1 | — |
| Q32 | 확인 근거 | '보유 저장 시각' · 분 단위 한국 시각 · 값 무변경 | E1 | — |
| Q33 | 확인 근거 | 개별 주식이 확인되면 'ETF 순위 대상 아님' · 'NAV·ETF 구성종목 해당 없음' | E5 · E12 | I-12 |
| Q34 | 확인 근거 | 펼침 = 등락 · 시장 대비 · 가격 · 거래량 · 가격 흔들림 / 세부 창 = 차트와 선택한 날의 수치 | E4 | — |
| Q35 | 확인 근거 | 10/21 = 수익률 시작 종가 · 10/22 = 20개 가격 차트 첫날 → 실제 자료 날짜를 역할로 표시 · 백엔드 무변경 | E9 | — |
| Q36 | 확인 근거 | NAV 원문 안내(message)는 [자세히] | E10 | — |
| Q37 | 확인 근거 | 방향 줄 = 값 · 부호 + 방향 낱말 · 0.00% = '변화 없음' | E4 | I-14 |
| Q38 | 데이터 상태 · 확인 근거 | 기존 '괴리 확인 필요(3% 이상)' · '괴리 주의(5% 이상)' · 절대값 기준 · 색 | D2 · E10 | — |
| Q39 | 데이터 상태 · 확인 근거 | 수집 상태 = '수집됨' · '이전 목록 재사용' · '확인 불가' | D1 · E10 | — |
| Q40 | 데이터 상태 · 확인 근거 | 요약 '가장 최근 기준일' · 각 행 그 날짜 · 이전 목록 재사용으로 날짜가 재설정된 행 = '재저장일' | D3 · E10 | I-9 |
| Q41 | 데이터 상태 | 한국어 변환 범위(판정 글에 명시 없음) | D3 | I-5 |
| Q42 | 공통 | 사용자용 한국어 표기는 프론트 공용 사전을 재사용 · 백엔드 · API 무변경 | D6 | — |
| Q43 | 데이터 상태 | '기타' 요약 건수와 필터 결과를 같은 전체 조회 결과 · 같은 조건으로 맞춤 | D1 · D7 | I-6 |
| Q44 | 데이터 상태 | 괴리율 표시 · 숫자 색 그대로 | D2 | — |
| Q45 | 데이터 상태 | 화면 시험 새 파일 · partial 포함 고정 자료로 건수 대조 · 수집 상태 · 출처 · 괴리율 경계 · 음수 | D7 | — |
| Q46 | 종목 관리 | 상단 일괄 버튼 제거 · 일괄 화면 경로를 내리는 결정을 KS-2 기록에 | M1 · M6 | — |
| Q47 | 확인 근거 | 5 · 20 '저장일' 단위 — §3 '저장일 통일 범위' 전부 | E2 · E4 | — |
| Q48 | 확인 근거 | PC 저장 종가의 의미 = 도움말 | E1 | I-15 |
| Q49 | 확인 근거 | 순위는 그 조회의 실제 기간 · 끝 가격 상태로 · 순위 또는 순위권 밖 결과에 장중 · 마감 미확인 상태가 있으면 함께 | E5 | I-7 |
| Q50 | 확인 근거 | 20저장일 KODEX 200 대비 = 근거 응답 값 · 요약 응답의 KODEX 200 값은 안 씀 | E4 · E5 | — |
| Q51 | 확인 근거 | 요약 응답의 보유 exposure(하위 30 겹침)는 이 화면에서 안 씀 | E5 · E7 | — |
| Q52 | 확인 근거 | 확인 불가 = 확인된 사유('저장 가격 없음' · '같은 기간 수익률을 구하지 못함') · 순위 조회 실패에도 보유 · 가격 근거를 읽음 | E5 | I-8 |
| Q53 | 확인 근거 · 데이터 상태 | 두 화면의 첫 표기 = '순자산가치(NAV)' | E10 · D3 | I-10 |
| Q54 | 확인 근거 | 선택 상세 한 묶음 = 시장가 · NAV · 괴리율 · 기준일 · 출처 · 수집 상태 · 괴리율 뜻 = 도움말 · 전체 ETF 표 이동 버튼 제거(전체 표는 「데이터 상태」) | E10 · E11 | — |
| Q55 | 문서 | docs/PROGRAM_TRUTH.md 의 POC6-32 반영 상태 정정만 별도 커밋 · push 가능 · 커밋 대상과 실제 커밋 파일 목록이 그 한 파일인지 대조(`git show --stat`) · 커밋 · push 실행은 사용자 승인 뒤 | M5 · §6 | — |

## 8. 목업 범위(별도 파일 = 머리 MOCKUP · 판정 반영)

- 「보유 현황」: 요약 행 두 개(보유 A · 보유 B · 값은 '○' · 날짜만) · 한 행 펼친 상세(H1 순서 · 수량 · 평균 매입단가 · 현재가 없음(현재가 = 11/19 형수님 결정) · 네 항목 한 줄 · H4 두 칸 폭) · 자금 카드 세 상태(미입력 = 안내 한 줄 + 보유 평가액 · 가격 기준일 + [입력] · 0원 · 입력됨 · 계좌별 비중 설명은 [자세히] 안) · 배너 수(H6 · '종목 N개 · 보유 행 M개').
- 「종목 관리」: 상단 [새 보유 추가] · [입력 정정] 한 줄 · History 기간 머리 '비교 시작일: 2026-01-02' · [수정/해제] · 편집 라벨 '비교 시작일' · '그래프 시작점' 정정 설명.
- 「확인 근거」: 상단(E1) · 행(E2 · 저장일 이름 · 정렬 이름) · 클릭한 행 바로 아래 상세(E3) — 판정 순서: 방향 줄 → 순위 줄(E5 상태 목록 · 보유 A 값은 '○') → 필요한 자료 안내(E6) → 세 묶음 + 날짜 역할(E4 · E9) → 차트(그대로) → 주요 편입(E8) → 구성종목 중복(E7 · '비교 범위 확인 불가') → NAV 묶음(E10 · 여섯 칸 · 괴리율 '○') · [전체 ETF NAV·괴리율 보기] 없음 · 개별 주식 상세(E12).
- 「데이터 상태」: 한국어 제목 · 부제 첫 '순자산가치(NAV)' · 머리 · 뜻 두 줄(D5) · 요약 '가장 최근 기준일' · '수집됨' + '괴리 주의(5% 이상)' 행 · 출처 '네이버' · 예시 행(이전 목록 재사용 · 재저장일 / 확인 불가 / 기타 출처 · 상태 확인 필요).
- 보유 이름 · 코드 · 수량 · 가격 · 금액 · 계좌 이름은 그리지 않는다(가림 또는 '보유 A'). 보유 한 종목의 수익률 · KODEX 200 대비 · 괴리율 · 구성 행 수 · 하락 구간 · 상품 종류도 '○'. 보유 집계(종목 수 · 행 수 · 계좌 수 · 상태별 건수 · 계산 가능 a/b 등)는 N · M · ○ 또는 '합성 예시'로 밝힌 값(머리 '보유 표기' · 11/19 RESULT 판정 §4-1).

## 9. 하지 않는 것

- 공유 builder(`holdings_market_evidence.py`) · PUSH · 초안 문장 · AI 원문(holdings_capital.preview_lines · decision_preview_lines.py) 변경.
- 계산 · API 원값 · DB 표 · 저장 형식 · 백엔드 일괄 기준일 API(대상 1 ~ 200) · 백엔드 시장 흐름 글(holdings_market_flow.py) 변경.
- 새 그래프 · 새 메뉴 · 새 판정 · 새 점수. 「오늘의 투자 점검」의 [전체 ETF NAV·괴리율 보기 →] 제거.
- 새 의존성 · 외부 조회 · OCI · 라이브 보유 파일 쓰기. 파일 삭제(Q17 = 보관 · 삭제는 사용자 판단).
- 커밋 · push 는 사용자 승인 뒤(Q55 의 PROGRAM_TRUTH 단독 커밋 포함).

### 9-1. 개발자 적용 해석(판정 글이 열어 둔 구현 세부 · 2026-11-19 RESULT 판정 §3 으로 확정 · 바뀐 표시 = §9-2)

기준 = 판정 글의 낱말을 넘지 않고 기존 계약(공유 builder · API · PUSH · 시험 관례 · 사용자 화면 규칙)을 지키는 가장 좁은 읽기. 설계자가 다르게 정하면 그 I-n 에 적힌 파일 · 시험만 같이 바꾼다.

- **I-1(Q17 · M2) 기준일 창 시험.** 판정 = 창과 창 전용 대상 선택 함수를 함께 보관. 보관 폴더 정의(_orphaned/README.md:3 '더 이상 어디서도 import 되지 않는' 파일)를 지키려면 시험이 그 파일을 import 할 수 없다 → ReferenceDate.test.tsx 의 import(:26)와 referenceTargets 단위 it(:103-110)를 지우고, 일괄 창 it 3개(:79 · :112 · :122)는 '상단에 일괄 버튼 없음 · [새 보유 추가] · [입력 정정] 있음' it 1개로 바꾼다. 운영에서 쓰지 않는 대상 고르기 규칙은 시험 대상에서 빠지고, 다건 저장 계약은 백엔드 시험(tests/test_poc5_07_reference_date.py:157 여러 대상 첫 설정 · :224 한 번 쓰기 · 재시도 · 충돌 · :379 201건 거절)이, 기간별 설정 · 수정 · 해제는 같은 파일 History it(:153 · :174 · :186 · :202)이 계속 확인한다. 옮긴 파일은 상대 import 경로만 고쳐 tsc 를 통과시킨다(삭제 없음 · 다시 쓰면 그때 시험을 되살림).
- **I-2(Q18 · M3) '비교 시작일' 범위.** 바꿈 = History 기간 머리 줄 표시(ReferenceDateEditor.tsx:58) · 개별 편집 라벨(:75) · 그 파일 머리 주석의 화면 글 인용(:3-4) · 시험 낱말(ReferenceDate.test.tsx:157 · 161 · 177 · 191). 바꾸지 않음 = [시장 흐름 보기] 글 줄 — 항목 이름 '가격 비교 기준일 이후 종가 변화' · 안내 글 '가격 비교 기준일은 종가 비교의 출발점이다 …' · 구간 이름(백엔드 상수 holdings_market_flow.py:114-115 · 482 · 505)과 끝난 기간 줄 '가격 비교 기준일 … → 마지막 매도일'(MarketFlowPanel.tsx:122 · 재진입 검토 창과 공유). 바꾸면 백엔드 응답 글자 · 시험 · fixture(referenceFixtures.ts)가 함께 바뀌어 검증 대상이 된다. 그래서 같은 History 창에 머리 줄 '비교 시작일'과 흐름 줄 '가격 비교 기준일'이 함께 보인다 → 흐름 줄까지 맞출지 확인 요청. (11/19 RESULT 판정 §2-2 · §3 I-2 로 정해짐 → §9-2)
- **I-3(Q23 · E6 · E7 · E12) 안내 문장 분류.** builder 문장(holdings_market_evidence.py:358-401)별 이 화면 처리(builder · PUSH · 초안 무변경):

  | 문장 | 판정 갈래 | 이 화면 |
  |---|---|---|
  | '현재 Market Discovery …' 네 문장(:359-369) | 옛 MD TOP 10 | 거름 |
  | '20거래일 KODEX200 대비 단기 흐름 차이 …'(:371-381) | 상세 수치의 반복 안내(방향 줄 · 세 묶음) | 거름 |
  | 'NAV / 괴리율 확인이 필요합니다.'(:401) | 상세 수치의 반복 안내(NAV 묶음의 괴리 표시) | 거름 |
  | '… 일부 겹칩니다.'(:388) · '… 겹치는 항목이 없습니다.'(:389-391) | 범위 없는 구성 중복 문구 | 거름 |
  | '단기 흐름은 데이터 부족으로 확인할 수 없습니다.'(:383) | 자료 부족 안내 | 목록에 남김 |
  | '구성종목 데이터가 캐시에 없어 비교할 수 없습니다.'(:394) · '현재 후보군의 구성종목 데이터를 확인할 수 없습니다.'(:396) · 'NAV / 괴리율은 source 미연동으로 확인할 수 없습니다.'(:399) | 자료 부족 안내(기술 낱말 '캐시' · 'source' 포함) | 같은 사실을 같은 상세의 자기 줄이 쉬운 한국어로 보이므로 목록 문장은 거르고 그 줄로 남김: 구성 줄 '구성종목 확인 불가 — 이 ETF 의 저장 구성 자료 없음' · '구성종목 확인 불가 — 비교 후보의 구성 자료 없음' · NAV 묶음 '수집 상태 확인 불가' · 개별 주식이 확인되면 'NAV·ETF 구성종목 해당 없음' |

  목록 문장을 그대로 남기면 '캐시' · 'source'가 화면에 남는다(사용자 결정 '화면 글자는 쉬운 한국어'). 구성 줄의 두 사유 글은 새 낱말.
- **I-4(Q25 · Q26 · E7) 구성종목 중복 줄 모양 — 2026-11-19 RESULT 판정 §2-1 로 확정(수용).** 머리 = '비교 범위 확인 불가'(먼저) · 아래 '비교 목록: 1개월 상위 10개 후보 · 시작 → 끝 · 인버스 · 레버리지 · 합성 · 선물 제외'(주간 순위 상위 30 과 따로 고른 목록 · 이미 받은 topn_basis · 기간 · 제외 조건 = 이 후보 목록의 기준) · 실제 비교 규칙 = '후보 둘 이상의 구성 상위 10행에 함께 나온 종목 ↔ 선택한 보유 ETF 구성 상위 10행 · 상위 10행 = 비교 상한 · 실제 비교에 쓴 구성 기준일 · 행 수는 이 응답에 없음'(처음 V1 글 '각 ETF 구성 상위 10행까지 비교'는 후보 둘 이상 조건이 빠져 실제 규칙과 달랐음 · 결과서 EV-1 로 바꾼 글을 판정이 수용). 실제 비교의 구성 기준일 · 행 수가 미확인이라 '중복 없음' · 전체 겹침 건수 · 비율은 표시하지 않는다. 겹침 목록이 있으면 찾은 종목은 그 자체로 확인된 사실이라 '확인된 겹침'에 이름을 쓰고, 비중은 응답으로 가리키는 대상을 확인할 수 있을 때 '이 ETF 편입 비중 ○.○○%'처럼 뜻을 붙여 표시한다(건수 숫자 없음). 겹침 목록이 비면 결과 문장 없이 '비교 범위 확인 불가'와 비교 규칙만. '주요 편입'(E8)의 날짜 · 범위는 그 자료에 붙인다.
- **I-5(Q41 · D3) 한국어 변환 범위.** 「데이터 상태」 화면 안 영어 · 기계 글자 전부(제목 · 부제 · 안내 띠의 표 이름 · 'SQLite' · 'universe' · 요약 줄 · 고르기 라벨 · 선택지 · 정렬 선택지 · 검색 안내 · 표 머리 · 칸 값 · 빈 · 오류 카드 문구) + 같은 사전을 쓰는 「확인 근거」 NAV 묶음. 같은 원문이 남는 다른 곳(§4 끝 목록)은 바꾸지 않고 결과서에 목록.
- **I-6(Q43 · D1) '기타' 계산.** 요약 줄의 수집됨 · 확인 불가 · 기타 건수를 화면이 같은 응답 items 전체에서 필터와 같은 판정 함수 하나로 센다(기타 = ok · unavailable 이 아닌 값 · partial 포함 · 지금 필터 규칙 DataStatusView.tsx:102-107) → 요약 '기타' = 검색어 없이 필터 '기타'를 고른 결과 건수 · 전체 = items 개수(= summary.total_count). 백엔드 summary.failed_count(partial 제외 · api_nav_discount.py:139-141)와 API 계약은 그대로(다른 화면이 summary 를 씀). '기타' 낱말은 그대로.
- **I-7(Q49 · Q24 · E5) 끝 가격 상태를 붙이는 줄.** '1개월 상위 30 중 n위' · '순위권 밖' 두 줄만(판정 '순위 또는 순위권 밖 결과') · 규칙상 제외 · 자료 확인 불가 · ETF 순위 대상 아님에는 붙이지 않음. 값 = 요약 응답 보유 항목 end_price.state(그 보유의 마지막 저장 행 · pc_etf_compare_summary.py:425) · intraday → ' · 장중 저장값 기준' · unknown → ' · 마감값 확인 필요' · after_close 또는 end_price 없음 → 붙이지 않음.
- **I-8(Q52 · E5) 확인 불가 사유 글.** 응답이 알려 준 사유만: no_price '자료 확인 불가 — 저장 가격 없음' · period_differs '자료 확인 불가 — 같은 기간 수익률을 구하지 못함'(V1 원안의 괄호 '(이력이 짧거나 시작 · 끝 날짜가 다름)'은 응답이 둘을 나누지 않아 뺌 · pc_etf_compare_summary.py:447-452) · 조회 실패 '자료 확인 불가 — 주간 순위 조회 실패'(순위 줄만 · 다른 근거는 그대로 보임).
- **I-9(Q40 · D3 · E10) '재저장일' 표시.** 수집 상태가 partial(이전 목록 재사용 · naver_etf_universe_fetcher.py:249-258)인 행은 「데이터 상태」 기준일 칸에 '재저장일 2026-11-18'처럼 낱말을 날짜 앞에(열 이름 '기준일' · 정렬 · 값 그대로) · 「확인 근거」 NAV 묶음도 '기준일' 자리에 '재저장일 …'. 요약 '가장 최근 기준일'은 응답 asof(모든 행 최댓값 · api_nav_discount.py:144-145) 그대로 — 재저장 행의 날짜가 최댓값이면 그 날짜가 된다(지금 partial 0행).
- **I-10(Q53) '첫 표기' 자리.** 「확인 근거」 = 상세 NAV 묶음 이름 '순자산가치(NAV) · 괴리율'(상세는 한 번에 하나만 열림 · 묶음 안 칸은 'NAV') · 「데이터 상태」 = 부제의 첫 NAV '전체 ETF의 순자산가치(NAV) · 시장가 · 괴리율 조회' · 표 머리 · 뜻 줄 · 요약은 'NAV'. 개별 주식 줄은 판정 Q33 글 'NAV·ETF 구성종목 해당 없음' 그대로. 「오늘의 투자 점검」 · ETF 비교하기('기준가(NAV)')는 범위 밖.
- **I-11(Q3) 사전 밖 값의 범위 · 원문 자리.** ① 「보유 현황」 가격 출처도 같은 규칙(naver → '네이버' · 사전 밖 → '기타 출처') — 이 상세에는 [자세히]가 없어 원문은 보이지 않음(지금 모든 행 naver) ② 「데이터 상태」 표 칸 = '기타 출처' · '상태 확인 필요' · 원문은 표 아래 접힌 [자세히] 한 곳(사전 밖 값이 있을 때만 · 원문 값 · 건수) ③ 「확인 근거」 NAV 묶음 = 묶음 안 접힌 [자세히](받은 안내 원문 message · 사전 밖 원문) ④ NAV 저장 행이 없는 ETF(builder 표지 source 'not_integrated' · status unavailable · 값 없음 · holdings_market_evidence.py:322-331)는 출처가 아니라 '행 없음' 표지라 출처 칸 '-'(「데이터 상태」 null 출처와 같은 표기) · 수집 상태 '확인 불가' — 지금 보유 ETF 는 모두 NAV 행이 있어 해당 없음(이 표지는 개별 주식에만 · 그쪽은 Q33 '해당 없음') ⑤ 「데이터 상태」 요약 줄 출처 null(출처가 둘 이상이거나 없음 · api_nav_discount.py:146-147)은 지금처럼 '-'.
- **I-12(Q33 · E5 · E12) 개별 주식 판정 · 글.** 판정 = 요약 응답 보유 항목 is_stock · out_reason 'stock'(ETF 목록 etf_master 에 없는 종목 · pc_etf_compare_summary.py:88 · 408 · 430). 요약 조회가 실패하면 '확인'되지 않은 것으로 보고 순위 줄 '자료 확인 불가 — 주간 순위 조회 실패' · 구성 · NAV 줄은 근거 응답대로(수집 상태 '확인 불가' · 영어 원문은 [자세히]). 글 = 판정 낱말 + 이유 괄호 'ETF 순위 대상 아님(개별 주식)' · 'NAV·ETF 구성종목 해당 없음(개별 주식)'(V1 원안 괄호 유지).
- **I-13(Q15 · H8) [자세히]로 옮기는 범위.** 계좌 행 비중 안내 한 문장(CapitalContextPanel.tsx:393-398 · 보유가 있는 모든 상태)만 [자세히] 안 맨 앞으로 · 직접 입력 확인일 문장(:387-392 · POC6-24 B-2 '화면에 표시')과 부분 평가 · 기준일 다름 경고는 기본 화면 그대로. 시험 CapitalContextPanel.test.tsx:200-213 → '[자세히] 안에 있음'.
- **I-14(Q37 · E4) '변화 없음' 기준.** 방향 줄에 보이는 값(소수 둘째 자리)이 0.00 이면 '0.00%(변화 없음)' · 부호 없음(−0.004 도 '0.00%(변화 없음)') · 0.01 이상 '올랐음' · −0.01 이하 '내렸음' · 값 없음 → 기존 '자료 확인 필요'. 행 칸 · 세 묶음 · 정렬 값 표기는 그대로(방향 낱말 없음).
- **I-15(Q48 · E1) 'PC' 낱말.** 'PC 최근 20저장일 하락 구간'(DeclineSummaryBlock.tsx:21) · 'PC 저장 종가 기준'(:43)은 그대로 · E1 에서 '가격 기준일' 하나로 합치는 두 이름(:41 'PC 가격 흐름 기준일' · lib/priceBasis.ts:24 'PC 저장 가격 기준일')만 바뀜 · 'PC 저장 종가'의 뜻(OCI 보유 알림과 값이 다를 수 있음)은 기존 ? 도움말(riskCombination.ts:150-151 HELP_BAND_BASIS)에 이미 있어 새 도움말 글 없음.

### 9-2. RESULT 판정 표시 보완(2026-11-19 · 설계자 RESULT 판정 조건부 PASS)

판정 문서 = `docs/ai_design/POC6/POC6_33_HOLDINGS_UI_REVIEW_RESULT_DECISION_2026-11-19.md`. 이 PLAN 안에서 직접 고친 곳 = H1(상세 현재가 뺌 · §2-0) · E7 · I-4(구성종목 중복 규칙 · §2-1) · 머리 '보유 표기'와 보유 집계 가림(§4-1). 그 밖에 판정이 정한 화면 표시 변경(값 · 계산 · API · 서버 원문 그대로 · 화면 글자만):

- 「확인 근거」 순위 줄 = '1개월 수익률 상위 30 중 n위' · 순위권 밖 = '순위권 밖 · 1개월 수익률 상위 30 밖'(§1 · 실제 비교 기간 · 제외 조건 · 끝 가격 상태는 같은 조회 결과에서).
- History = 기간 머리 · 편집 라벨 · [시장 흐름 보기] 모두 같은 이름 '비교 시작일' → 흐름 줄 '비교 시작일부터 종가 변화'(§2-2 · I-2 가 남겼던 '가격 비교 기준일' 흐름 줄도 화면 표시에서 맞춤 · 날짜 · 비교 수치 · 저장 계약 · 서버 원문 그대로).
- 「종목 관리」 표 아래 계좌별 행 수 = '보유 행 M개'(§2-3 · H-1 · 「보유 현황」 배너 '종목 N개 · 보유 행 M개'와 같은 단위).
- [세부 흐름 보기] = 저장 거래량의 비교 구간 · 유효 자료 수를 읽게 하고 제공처 원문 `FinanceDataReader` 는 이 화면의 기존 도움말로(§2-4 · EV-3).
- 「확인 근거」 낱말 = 가격 기준일을 가리키는 낱말은 '가격 기준일' · 저장일을 세는 지표 · 차트 도움말은 '저장일' · 사용자 문구는 'KODEX 200' · 상단 market_asof 를 보일 때 이름 = '기존 후보 목록 기준일'(종목 가격 · 주간 순위 기준일과 구별)(§2-6).
- 「데이터 상태」 요약 날짜 = 최댓값 날짜에 재저장일이 들어 있으면 '가장 최근 목록 날짜(재저장일 포함)' · 일반 기준일만이면 '가장 최근 기준일'(§3 I-9 · 기존 응답값 사용).
- 나머지 I-1 · I-3 · I-5 ~ I-8 · I-10 ~ I-15 = 판정 §3 대로 수용(I-15 는 §2-6 날짜 · 단위 표기 적용).
