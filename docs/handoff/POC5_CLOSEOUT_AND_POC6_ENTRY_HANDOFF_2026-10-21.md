# POC5 종료 · POC6 진입 인계 (2026-10-21)

- **작성**: 개발자(VSCode Claude)
- **독자**: 다음 세션 개발자 · 총괄 설계자 — POC5 를 닫고 POC6(첫 작업 POC6-01 종료) 다음 차례 = ML 고도화 설계로 넘어가는 시점
- **정본 우선순위**: 지금 실제 동작 = `docs/PROGRAM_TRUTH.md` · 현재 상태 = `docs/STATE_LATEST.md` · 개발 규칙 = `CLAUDE.md`(= DEV_RULES). 이 문서는 요약 · 길잡이이며 충돌하면 정본이 이긴다.
- **입력**
  - POC5 진입 계약: `docs/handoff/POC5-00_INVESTMENT_MODEL_V2_MASTER_DESIGNER_HANDOFF_2026-10-03.md` · `docs/ai_design/POC5/POC5-00_OPERATIONAL_DECISION_LEDGER_MASTER_DESIGN_V1.md`
  - 단계별 설계 · PLAN · 결과서: `docs/ai_design/POC5/`(50) · `docs/ai_plan/POC5/`(32) · `docs/ai_result/POC5/`(결과서 32)
  - POC6: `docs/ai_design/POC6/POC6-01_MARKET_FLOW_INTEGRATION_SCOPE_AND_SOURCE_DECISION_2026-10-20.md` · 결과서 `docs/ai_result/POC6/POC6-01_MARKET_FLOW_INTEGRATION_RESULT.md`(§12 = 설계자 RESULT 판정 원문)
  - 백로그 `docs/backlog/BACKLOG.md` 머리 '현재 처리 요약'

```text
POC5         종료 — 결과서 32개 모두 종료 상태(IMPLEMENTED_VERIFIED_CLOSED · _DEPLOYED_CLOSED · _OPERATION_CONFIRMED · UI-01 = DONE_USER_CONFIRMED)
             POC5-28 = 미구현 이관(TRANSFERRED_TO_POC6_01 · 설계 · 조사만)
POC6-01      IMPLEMENTED_VERIFIED_CLOSED(2026-10-21) — 시장 흐름 통합(수급 · 환율 · 유가) · 이 인계와 같은 커밋
다음 차례    설계자 — ML 고도화의 목표 · 평가 · 채택 기준 설계(POC6-01 RESULT 판정 §5 · 단계 번호는 설계자가 정함)
남은 운영    2026-10-23(금) 08:10 · 09:20 배치 완료 뒤 공식 R0 1회(§4-1 · POC5-04 인계 §2)
ML 상태      ML_OPERATION_PROMOTION = NOT_APPROVED · CURRENT_DEPLOYABLE_ML_MODEL = none · Q6 운영 계약 OPEN
백로그       완료 7 · 대체 5 · 개발 대상 0 · ML 설계 통합 4 · 조건부 41 · 사용자 보류 5 = 62
```

---

## 1. POC5 가 한 일

**목적**(POC5-00 §8): 실제 운영 신호가 무엇이었고 그 뒤 어떤 결과가 나왔는지를 추적 가능한 증거로 쌓는다. POC5 자체는 ML 성공을 전제로 하지 않는다.
- 고정 계약: `OUTCOME_MODE = RAW_ONLY` · 성공/실패 라벨 없음 · 시장 방향 적중률 만들지 않음 · 과거 종목 신호 복원(backfill) 금지 · PRIMARY t0 = 메시지 조립에 실제 쓴 현재가.
- 실제 전달된 항목만 분석 표본이다. planned · failed · partial · skipped · gap 을 구분하고, 원장 기록 실패가 PUSH 발송을 막지 않는다.

진행은 원장 축(01A → OPS-04 → 01B → 02 → 03 → 04)을 먼저 세운 뒤, 사용자 실사용 의견에서 나온 PC 판단 근거 화면 · 기록 기능으로 넓혔다.

### 1-1. 운영 원장 축 (OCI · PC 동기화)

| 단계 | 내용 | 상태 · 커밋 |
|---|---|---|
| POC5-00 | 운영 신호 · 판단 결과 원장 MASTER 설계 · PLAN | 확정 2026-09-26 · `3b6e3257` |
| POC5-01A | 세 PUSH 러너 기계 분리(646 → 517줄 · 동작 변경 0) | OPERATION_CONFIRMED · `87238e1e` · `19882ff3` |
| POC5-01B | 운영 의사결정 이벤트 원장(run · item · delivery · meta 4표 · 대조 CLI) · OCI `state/decision/decision_evidence.sqlite` | OPERATION_CONFIRMED(첫 활성 2026-10-08) · `9cbbd419` · `1d2fc929` |
| POC5-02 | 가격 결과 성숙(price_outcome 1 · 5 · 20거래일 · 배치 뒤 격리 실행) | OPERATION_CONFIRMED(첫 결과 행 2026-10-09) · `f0711340` |
| POC5-03 | 「받은 알림 기록」 — PC 원장 사본 · 버튼 동기화 · 선택 평가 | OPERATION_CONFIRMED(가격 결과 표시 2026-10-12) · `4e92d0c5` |
| POC5-04 | R0 수집 점검 · R1 원시 결과 리포트(PC 수동 읽기 전용 CLI) | CLOSED · `eb5d1ead` · 공식 R0 = 10-23 뒤(§4-1) |

### 1-2. 보유 · 매매 기록

| 단계 | 내용 | 상태 · 커밋 |
|---|---|---|
| POC5-05 | 보유 · 매매 이력 통합(매매 한 번 입력 = 보유 · 이력 같이 변경) | DEPLOYED_CLOSED · `33b002e4` · `ae5fa38c` |
| POC5-07 | 기존 보유의 가격 비교 기준일(REFERENCE_DATE · 2026-01-02 사용자 제안) | DEPLOYED_CLOSED · `89f90f0f` · `3996bb0b` |

### 1-3. 연구 · ML 근거 (PC 수동 · 운영 승격 아님)

| 단계 | 내용 | 상태 · 커밋 |
|---|---|---|
| POC5-06 | 수동 재진입 검토 · ETF 하나 D20 연구 추정(고정 Ridge · 2026-10-09 한정 연구 예외) | DEPLOYED_CLOSED · `21706285` · `ba7d55db` |
| POC5-08 | 알림의 ML 사후평가(원장 사본 · 확정 +5 가격 결과 · 고정 Ridge · 시간 분리 · 2026-10-11 연구 예외) | DEPLOYED_CLOSED · `f1951812` · `d7d365f4` |
| POC5-20 | 가격 · 거래량 · 변동성 근거 조합의 과거 사례 대조(PC 수동 CLI · 보유 ETF) | CLOSED · `704d84a1` |

### 1-4. PC 판단 근거 화면 · 시장 갱신

| 단계 | 내용 | 상태 · 커밋 |
|---|---|---|
| POC5-UI-01 | 버튼 크기 통일(큰 48px · 중간 40px) | DONE_USER_CONFIRMED · `8ac6f41f` |
| POC5-UI-02 | 「확인 근거」 기존 점검 흐름 정정 · 정렬 · 자료 확인 안내 | CLOSED · `9cfb535f` · `c5613b6c` |
| POC5-09 | 저장 거래량 확인 근거 · PC 가격 흐름 기준일 정정 | CLOSED · `7f394deb` |
| POC5-10 | PC 갱신에 보유 개별주 가격 단계 | CLOSED · `2522a672` |
| POC5-UI-03 | 「오늘의 투자 점검」 정보 배치(기본 화면 축소 · 펼치기) | CLOSED · `ff4279e8` |
| POC5-11 | PC 시장 갱신에 VIX 단계 · 시장 판정 날짜 정정 | CLOSED · `f950ebfa` |
| POC5-12 | VIX 최신성(미국 장 마감 기준) · 'VIX 다시 받기' · 진행 중 요청 공유 | CLOSED · `12b988bb` |
| POC5-13 | 보유 · 시장 위험 근거 통합 1차(하락 구간) | CLOSED · `e87de6d8` · `e1bb9839` |
| POC5-14 | 같은 종목 · 여러 계좌 평가값 정정 | CLOSED · `01e54a50` |
| POC5-15 | 현재 시장 · 보유 상태 조합(두 화면 공통 판정) | CLOSED · `48cb3b8a` |
| POC5-16 | 저장 종가 가격 흔들림(변동성) 근거 | CLOSED · `76797b1f`(쓰지 않게 된 구역 삭제 `9df40437`) |
| POC5-17 | PC 수동 갱신 멈춤 보호(FDR 대기 20초 · 연속 5종목 시간 초과 중단) | CLOSED · `64749ad4` |
| POC5-18 | PC 갱신 예상 밖 오류 상태 정정 | CLOSED · `eea4ff4e` |
| POC5-19 | 저장 거래량 흐름 · 종목 상세 근거 묶음 · 차트 읽기 | CLOSED · `39549254` |
| POC5-UI-04 | 종목 가격 차트 기간 선택(3개월 기본 · 6개월 · 1년 · 전체) | CLOSED · `c5dd13e8` |
| POC5-21 | 「요즘 잘 오르는 ETF」 후보 수익률의 실제 계산 기간 | CLOSED · `05093286` |
| POC5-22 | 후보와 KODEX200 의 동일 기간 수익률 비교 | CLOSED · `25feee25` · `6cab3a18` |
| POC5-23 | 선택 ETF 판단 근거 미리보기(묶음 글 · 복사) | CLOSED · `089310e3` |
| POC5-24 | 선택 근거의 AI 투자세션 연결 | CLOSED · `87a29bf2` |
| POC5-25 | 현재 저장 종가의 고점 대비 근거 정정(폐기 스냅샷 → 저장 20행) | CLOSED · `e1e1d8ac` |
| POC5-26 | 「요즘 잘 오르는 ETF」 기본 조회 기준 설정(백로그 #19) | CLOSED · `1fb287e0` |

### 1-5. OCI 운영 기준 · 이관

| 단계 | 내용 | 상태 · 커밋 |
|---|---|---|
| POC5-27 | PC 에서 OCI 운영 기준(PARAM) 실제 활성화 — 「OCI 운영·적용」 ② [현재 기준 OCI 적용] = PC 승인값의 OCI DB 발행(백로그 #50) | CLOSED · `c15ef6b1` |
| POC5-28 | 시장 수급 · 환율 · 유가 흐름 통합 근거(백로그 #48) | 미구현 이관 → POC6-01 |

## 2. POC6-01 — 시장 흐름 통합 (종료 2026-10-21)

- 「최신 시장 데이터 갱신」 마지막 단계에서 다음을 받아 시장 DB 새 표 2개(`market_macro_daily` · `market_investor_flow_daily`)에 넣는다.
  - 원/달러 · WTI: Yahoo `KRW=X` · `CL=F` 완료 일봉.
  - 코스피 투자자별 순매수: 키움 REST `ka10051`(KRX 코스피 종합 행 · 억원 → 원).
- 읽기 API `GET /market/flow-context`(쓰기 0) 하나가 다음 네 곳에 같은 서버 글을 준다.
  - 「요즘 잘 오르는 ETF」 시장 흐름 카드.
  - 「오늘의 투자 점검」 코스피 카드 두 줄.
  - AI 복사문.
  - 판단 근거 미리보기(`flow_period`) · AI 세션 넘김.
- 확인할 수 없는 것(부분 집계 · 부분 기간 · 20일 비교 불가 · 비교 못 한 자료 · 확인 못 한 해석 조합)은 '없음 · 해당 없음'으로 쓰지 않는다(검증자 r1 정정).
- 운영 사실 · 한계(결과서 §5 · §7 · RESULT 판정 §3):
  - KRX 회원 웹 자동 수집은 이용약관(제10조 · 제12조) 때문에 중단했다. 수급은 키움 한 경로뿐이다(주문 · 잔고 · SDK 없음).
  - 키움은 등록 IP 인증이다. 집 · 회사 · 핫스팟은 공인 IP 가 달라 수급은 집(등록 IP)에서 갱신할 때만 받는다. 다른 곳에서는 수급만 실패하고 빠진 날은 다음 집 갱신에서 채운다.
  - `.env` 의 `KIWOOM_APP_KEY` · `KIWOOM_APP_SECRET` 은 사용자가 넣었다. 값을 출력 · 기록하지 않는다.
  - 순매수만 제공된다(매수 · 매도 NULL · 거래대금 비율 생략). 오늘(KST) 수급은 넣지 않고 최근 20거래일을 겹쳐 받아 정정한다.
  - 이 표는 최신 확보 자료이며 **PIT 가 아니다** — ML 과거 검증에서 당시 알았던 자료로 간주하지 않는다.
  - 'VIX 다시 받기' 조건 = 사용자 결정 (a): 시장 흐름 실패도 다른 단계 실패로 센다.
- 시장 흐름에 지표 · 자료원을 계속 보태는 것은 기본 후속이 아니다(판정 §5).

## 3. 다음 차례 — ML 고도화 설계 (설계자)

판정 §5: **ML 고도화의 목표 · 평가 · 채택 기준 설계.** 다음을 ML 설계에서 정한다.
- 과거 시점 정보 가용성.
- 대조 기준.
- 검증 구간.
- 실패 시 종료 기준.

원천별 PIT 이력 시스템 구축을 자동 선행 과제로 만들지 않는다. 기존 운영 점검 일정(R0)은 ML 설계 착수를 막지 않는다.

**ML 설계가 쓸 수 있는 자산(지금 있는 것)**

| 자산 | 위치 · 성격 |
|---|---|
| 운영 원장(실제 전달 신호) | OCI `state/decision/decision_evidence.sqlite`(POC5-01B) · PC 사본 = 「받은 알림 기록」(POC5-03) · RAW_ONLY |
| 가격 결과 1 · 5 · 20거래일 | 원장 price_outcome(POC5-02) · 성숙 전 PENDING |
| 사용자 선택 평가 | 「받은 알림 기록」 평가(POC5-03 · 선택) — **평가 없는 알림도 ML 이 그대로 쓴다**(평가 유무로 거르지 않음) |
| 알림 사후평가 | POC5-08(+5 고정 Ridge · 시간 분리 · 연구 예외 · 운영 승격 아님) |
| 재진입 검토 D20 | POC5-06(연구 예외 · ETF 하나) |
| 근거 조합 과거 사례 대조 | POC5-20 CLI(관측 대조 · 판정 아님) |
| R0 · R1 리포트 | POC5-04 CLI(R1 = 연구 · 검토 때 수동) |
| POC4 결론 | Track A(수익 예측) · Track B(하락 조기경보) 모두 REJECT — `docs/handoff/POC4-03_RF_VS_MOMENTUM_KILL_GATE_HANDOFF_2026-09-26.md` |
| 시장 흐름 표 | POC6-01(비PIT · 입력 여부는 별도 판단) |

**ML 설계 때 함께 결정하기로 미뤄 둔 것**(백로그)
- ML 설계 통합 4건(#3 · #55 · #57 · #62 · 별도 선행 기능 4개로 개발하지 않음).
- #59 관찰 후보군(seed) 편집 화면.
- PC seed 3 ↔ OCI 승인 20 차이(B-098). 관찰 후보군 = 사용자가 승인한 ETF 관찰 목록이며 보유 · 비보유를 포함할 수 있다('비보유만'이 아님).

**유지되는 계약(다시 결정 항목으로 올리지 않음)**
- `ML_OPERATION_PROMOTION = NOT_APPROVED` · `CURRENT_DEPLOYABLE_ML_MODEL = none` · Q6 운영 계약 OPEN.
- 운영 ML 자동 실행 · 추천 채택 · PUSH/PARAM 변경 · 주문은 없다.
- 한국 거래일 = 평일 fallback(2026-09-11 사용자 확정 · 연 2~3회 오판 허용).
- 원장 RAW_ONLY 계약(§1).

## 4. 남은 운영 일정 · 보류

### 4-1. 공식 R0 1회 — 2026-10-23(금) 배치 완료 뒤 (개발자)

절차 전문 = `docs/handoff/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_HANDOFF_2026-10-08.md` §2. 요약:
1. **조건**: 09:30 이라는 시각이 아니라 실제 배치 완료 근거다. OCI 읽기 전용으로 `logs/oci_market_data_batch.log` 의 10-23 08:10 · 09:20 결과 줄 · 원장 오류 · 10-08 ~ 10-22 PUSH 실패를 확인한다.
2. **대조 근거**: `ssh oci-krx '… scripts/run_decision_ledger_reconcile.py'` 결과를 scratchpad 에 저장한다. 시각을 같은 명령에서 붙인다.
3. **운영 근거 파일**: scratchpad · 저장소에 두지 않는다.
4. **PC 동기화**: 사용자에게 「받은 알림 기록」 원장 새로고침을 부탁한다(배치 완료 뒤).
5. **실행**: `.venv/bin/python scripts/run_ledger_report.py r0 --end 2026-10-22 --reconcile-evidence … --ops-evidence …`
6. **보고**: 판정 · 사유 · 대조 기간 · 누락 · PENDING 을 설계자에게 보고한다. 과거 기록 삭제 · 재발송 · PRIMARY 시작일 재설정은 하지 않는다.

OCI 는 읽기 전용이고 명령마다 사용자 승인을 받는다. 쓰기 · 발송 · 재시작은 하지 않는다.

### 4-2. 보류 · 조건부

- **사용자 보류 5**: #20 ETF Category 라벨 · #33 손익 산식 설명 · #40 · #60 · #59(ML 설계 때). 사용자가 명시하기 전에는 개발하지 않는다.
- **조건부 41**: 재개 신호가 실제로 생기면 다룬다. 임의로 개발을 제안하지 않는다.
- **차트 선택 한계**(POC6-01): 고른 날 좌우 화살표는 코스피 거래일만 옮긴다. 불편이 제기될 때 검토한다.
- **KS-10 근접**: `app/market_refresh_service.py` 616줄 · `frontend/app/components/MarketDiscoveryView.tsx` 871줄. 다음에 그 파일을 넓힐 때 구조 변경을 함께 판단한다(판정 §3 · 근접만으로 분리 단계 만들지 않음).

## 5. 운영 구조 요약 (자세히 = PROGRAM_TRUTH §9 · §10)

- **OCI(자동)**: crontab 이 다음을 돌린다.
  - 시장 데이터 배치 08:10 + KRX 보강 09:20.
  - 시장 브리핑 08:30.
  - Holdings 09:15 · 12:30 · 15:40.
  - `holdings_risk_alert` 7틱(09:30 ~ 15:20).
  - 원장 기록(`DECISION_LEDGER_ENABLED=true`).
  - 배치 뒤 가격 결과 성숙.

  러너 PARAM = OCI DB 활성값이다. PC 「OCI 운영·적용」 ② [현재 기준 OCI 적용]으로 PC 승인값을 발행한다(POC5-27 · 같으면 쓰기 0).
- **PC(수동)**:
  - 「최신 시장 데이터 갱신」: 단계 = ETF 목록 · 가격 → 보유 개별주 → KOSPI → VIX → NAV → 시장 흐름.
  - 「받은 알림 기록」: 원장 새로고침 · 사후평가.
  - 판단 근거 화면들(「오늘의 투자 점검」 · 「확인 근거」 · 「ETF 비교하기」 · 「요즘 잘 오르는 ETF」 · 「보유와 비교」) · AI 세션.
- **자료 최신성**: KRX 는 전일 자료를 익영업일 08:00 에 공개한다(그래서 08:10 배치). 맥북 밤샘 조회는 하지 않는다.

## 6. 다음 세션 개발자 — 작업 방식 · 환경

- **흐름**: 설계서 저장(원문) → 짧은 PLAN(`docs/ai_plan/` · 질문 · 화면이 바뀌면 전체 화면 목업을 로컬로 띄움) → 사용자 목업 확인 → 설계자 판정(원문 저장 · PLAN 반영) → 구현 → 독립 검토 1회(백그라운드) → RESULT(`docs/ai_result/` · 7섹션) → 사용자 실화면 → 검증자(staged 기준) → 설계자 RESULT 판정(원문을 결과서 끝에) → 종료 기록(RESULT · PLAN · STATE · PROGRAM_TRUTH · BACKLOG) → 커밋 · push(사용자 승인 · `git commit -F`).
- **넘길 곳은 한 번에 한 곳**(설계자 · 검증자 동시 안내 없음). 커밋은 작업 종료 때만.
- **환경**(맥북):
  - uv(Python 3.12) · nvm(Node 24).
  - 사용자 서버(uvicorn `--reload` :8000 · next dev :3000)는 건드리지 않는다. 코드를 바꾸면 자동으로 다시 읽는다.
  - 전체 pytest 약 7분: 백그라운드 + `caffeinate -i` · 덮개 열어 두기.
  - 프론트 검증 = `npx tsc --noEmit` · `npm run lint` · `npx vitest run`(dev 중 `npm run build` 금지).
  - 마지막 실측(2026-10-20 · POC6-01 r1 정정 뒤): 백엔드 4072 passed · 프론트 69파일 878 passed.
- **안전**:
  - 시험은 라이브 DB 를 열지 않는다(`tests/conftest.py` 가드 · tmp). 라이브 DB 읽기는 `mode=ro` 만.
  - 변이 시험은 저장소 밖 사본에서만 하고, 복원은 내용 쓰기 + 시각 되돌림.
  - OCI 는 읽기 전용 · 명령별 승인. 비밀값은 출력하지 않는다.
- **git**:
  - 경로를 하나씩 stage 한다(`git add -A` · 폴더 금지 · 훅이 막음).
  - 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(untracked)는 넣지 않는다.
  - 결과서 · STATE 에 현재 HEAD SHA 를 쓰지 않는다.
- **사용자에게 보이는 글은 모두 한국어**. 화면은 컴포넌트 이름이 아니라 메뉴 이름(「…」)으로 부른다.

## 7. POC5 에서 굳은 교훈 (반려 라운드에서 확정)

1. **확인 범위는 diff 가 아니라 계약 문장에서** 정한다. 고친 칸 옆의 상태 · 순서 · 경로(정정 · 재매수 · 화면 왕복 · 첫 조회 실패)를 표로 열거하고 parametrize 로 시험한다.
2. **'없음 · 해당 없음 · 정상' 문장은 비교를 마쳤을 때만** 쓴다. 확인 범위(못 한 자료 · 사유)를 같이 만들고, 요약 줄 · AI 글 · 응답 모델까지 같은 칸을 전달한다(POC6-01 r1).
3. **판정이 여러 갈래면 판정 순서도 상태 표에** 넣는다(POC5-09 r1). 보존 계약은 실행 순서가 아니라 조회 쪽 행 구분으로 지킨다(POC5-10 r1).
4. **인접 계약은 실제 소스로 확인**한다. 필드명 · 모든 return path · 응답 모델(빌더 칸이 응답에서 빠지는 것은 실제 GET 시험으로만 잡힘)이 대상이다.
5. **결과서 주장 = 코드 실제 동작 · 실측 인용**. 줄 수 · git 상태 · 시험 수는 그 자리에서 잰다.
6. **검증은 줄인 방식으로**: 독립 검토는 단계당 1회(백그라운드), 변이 시험으로 시험의 힘을 확인한다. 전체 회귀는 마지막 1회. 찾은 결함은 한계로 미루지 말고 고친다.
