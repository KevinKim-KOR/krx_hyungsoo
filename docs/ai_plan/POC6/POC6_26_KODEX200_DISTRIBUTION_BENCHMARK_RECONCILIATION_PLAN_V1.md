# POC6-26 개발 PLAN V1 — KODEX200 분배금 포함 보유 기준선 검산(공개본)

작성 2026-11-07 · 갱신 2026-11-08(재개 판정 V1.2 반영) · 작성자: 개발자(VSCode Claude) · 수신: 설계자

```text
STATUS = PLAN 판정 완료 · 정정 반영 → 사용자 실행 승인(2026-11-08 · §5 네 항목) → 구현 · 실행
         → 본계산 1회 SAMPLE_RECONCILED → 검증자 r1 VERIFIED → 설계자 최종 RESULT PASS(2026-11-08 · docs/ai_design/POC6/POC6_26_KODEX200_DISTRIBUTION_BENCHMARK_RECONCILIATION_RESULT_DECISION_2026-11-08.md)
         → 종료 커밋 · push 진행(승인 ④ · CLOSED 는 push 성공 뒤 기록)
         (PLAN 제출 → 판정 V1.1 HOLD_SOURCE_CONFIRMATION → 사용자 Q1 (a) 결정(2026-11-07)
          → 재개 판정 V1.2 PASS_WITH_REQUIRED_CORRECTIONS · 대기 해제 → PLAN 정정 당시 계산 · 연구 사본 기록 · 공식 자료 기록 0)
         현재 = 본계산 1회 SAMPLE_RECONCILED · 검증자 r1 VERIFIED(2026-11-08 · 결과서 §10) · 공식 자료 요청 개발자 2 + 검증자 1 = 3/5회 · 설계자 RESULT 대기
PLAN 판정 = docs/ai_design/POC6/POC6_26_KODEX200_DISTRIBUTION_BENCHMARK_RECONCILIATION_PLAN_DECISION_V1_2_2026-11-07.md(우선)
          · docs/ai_design/POC6/POC6_26_KODEX200_DISTRIBUTION_BENCHMARK_RECONCILIATION_PLAN_DECISION_2026-11-07.md(V1.1 · 이용 조건 · 재개 절차는 V1.2 가 우선)
DESIGN = docs/ai_design/POC6/POC6_26_KODEX200_DISTRIBUTION_BENCHMARK_RECONCILIATION_DESIGN_V1.md
공개본 = 공식 분배 자료의 관측 수치(날짜 · 금액)는 이 문서에 적지 않는다(출처 · 방법 · 건수 · 판정 · 한계만 · 판정 V1.2 §1).
         관측 수치표가 든 제출 원본 = git 제외 로컬 검토 원본(state/ml/research/poc6_26/plan_review_original/).
```

## 1. 확인한 사실과 자료 경로

### 1-1. 봉인 가격판(`state/ml/research/krx_etf_universe.sqlite` · `krx_etf_universe_v1` · reader `app/krx_sealed_reader.py`)

| 항목 | 사실 |
|---|---|
| 달력 | member 3,122일(2014-01-02 ~ 2026-09-21) · **2025 거래일 242일 · D0 = 2025-01-02 · D1 = 2025-12-30** |
| 069500 행 | 2025 거래일 242일 모두 있음 · `ISU_CD` 069500 · `ISU_NM` 'KODEX 200' 하나 |
| 무조정 종가 | `TDD_CLSPRC`(원/주 · reader `CodeSeries.close`) · D0 · D1 행 있음 |
| 연결 종가 | reader `PRICE_BASIS = KRX_BASEPRICE_CHAIN` = 앞 값 × (1 + `CMPPREVDD_PRC` ÷ (`TDD_CLSPRC` − `CMPPREVDD_PRC`)) · 관계가 `FLUC_RT` 와 허용 오차 밖이면 구간을 끊음 · **2025 관계 불일치 0행 → D0 ~ D1 한 구간** |
| 기준가 차이 후보 | '전일 종가 ≠ 그날 기준가(종가 − 대비)'인 날 2025 = 4일(01-24 · 04-29 · 07-30 · 10-30) · 분배락일 · 조정 원인은 확인된 근거 범위로만 기록(판정 V1.2 §2) |
| 1주 단위 보조 근거 | `LIST_SHRS` · 위 후보일 — 설명되지 않는 단위 변경은 자료 미충족 |

### 1-2. 공식 지급현황 — 다운로드 경로(판정 V1.2 §1 · 사용자 Q1 (a))

| 항목 | 계약 |
|---|---|
| 이용 근거 | 운용사 공개 다운로드 기능 · 개인 연구 · PC 내 비공개 보관 · 필요한 여섯 행 최소 기록 · 운용사 문의 없음(사용자 결정 2026-11-07 · 판정 V1.2) |
| 조회 경로 | 분배금 현황 `https://www.samsungfund.com/etf/product/distribution.do?tab=product` 에서 KODEX 200(069500 · 상품 id 2ETF01)의 **[분배금현황 다운로드]** 를 한 번 사용 — 버튼의 링크 = `https://www.samsungfund.com/excel-divid-list.do?id=2ETF01`(화면 코드 `<a href=… download>`) 와 같은 요청 1회 |
| 파일 읽기(기존 PC 뷰어 · 새 설치 0) | 먼저 파일 형식 확인(`file`) → ① xlsx(OOXML = zip 안 XML) · HTML 표 → Python 표준 라이브러리(`zipfile` · `xml.etree` · `html.parser`)로 행 읽기 ② 그 밖(옛 `.xls` 등) → macOS Quick Look(`qlmanage`)으로 그림을 만들어 육안 확인 · 옮겨 적기. 어느 쪽이든 종목 · 지급기준일 · 실지급일 · 세전 좌당 분배금이 확인된 행만 옮긴다 |
| 범위 | 2025 보유 기간 대상 회차(사전 확인 4건) · 양끝 인접 회차 2건 = 여섯 행 · 2025 지급 전체가 파일에 있는지 같이 확인 |
| 팩트시트 대조 | `https://m.samsungfund.com/sheet/20251107/2ETF01_20251031.pdf` 1회 → 개발자가 PDF 를 직접 읽어(기존 도구) 2025 네 건을 종목 · 기준일 · 금액으로 대조 · 출처 · 쪽 · 건수 · 일치 여부 기록 |
| 지속 보관(로컬 · git 제외) | `state/ml/research/poc6_26/<run_id>/official_rows.json` = 종목 식별 · 여섯 행(기준일 · 실지급일 · 금액) · 출처 주소 · 확인 시각 · 다운로드 파일 SHA-256 · HTTP 상태(확인된 경우) · 팩트시트 대조(출처 · 쪽 · 건수 · 일치) |
| 임시 원본 | 다운로드 파일 · 팩트시트 PDF · Quick Look 그림은 열람 · 대조 · 해시 기록이 끝나면 지운다(해시 = 그때 확인한 파일의 식별 정보) |
| 자료 미충족 | 종목 · 필수 칸 확인 불가 · 회차 범위 불일치 · 팩트시트 대조 불일치 → 계산하지 않고 확인된 항목 · 막힌 계산을 기록 |

### 1-3. 권리 경계(판정 V1.2 §2)

- 결제 = T+2(한국거래소 ETF 결제제도 · `https://regulation.krx.co.kr/contents/RGL/03/03060102/RGL03060102.jsp` · 본실행 추가 조회 없음). 매입 2025-01-02 · 결제일 **2025-01-06** · 첫 지급기준일 2025-01-31 — 매입일 기준 17거래일 · 결제일 기준 15거래일.
- 포함 조건 = **결제일 < 지급기준일**(같으면 '권리 경계 확인 필요') · 권리가 확인된 지급의 실지급일이 미확인이거나 D1 을 넘으면 기말 현금 장부 자료 미충족 · 양끝 인접 회차로 기간 경계를 대조.

## 2. 실행 방법(사용자 실행 승인 뒤 한 번)

```text
준비(개발자 · 공식 자료 요청 2회 · 자료 확인 합산 45분 안 · 간격 ≥ 1초 · 응답 실패 때만 예비 1회)
 a [분배금현황 다운로드] 1회 → 형식 확인 → §1-2 읽기 → 여섯 행 · 2025 지급 전체 확인
 b 팩트시트 PDF 1회 → 2025 네 건 대조
 c official_rows.json 기록 → 다운로드 파일 · PDF · 그림 SHA-256 기록 뒤 임시 원본 삭제

scripts/run_kodex200_distribution_check.py (신규 · 본계산 1회)
 1 official_rows.json 읽기(형식 · 필수 칸 · 여섯 행 · 팩트시트 일치 확인 · 어긋나면 자료 미충족으로 멈춤)
 2 봉인 판: verify_sealed_source(전) → load_panel → benchmark() 069500 → D0 · D1 의 close · chain · segment
           → 같은 구간 · 코드 · 원/주 · 1주 단위 보조 근거 → verify_sealed_source(후) · assert_same_source
 3 장부: E = D0 무조정 종가 × 1.002 · 수령 현금 = 결제일 < 지급기준일 · 실지급일 ≤ D1 인 행의 세전 좌당 금액 합(원 · 정수)
   정확 검산: A · B 공통 E 상쇄 → 기말 금액 차이 (D1 종가 + 현금) − D1 종가 == 원본 행을 독립적으로 다시 더한 현금 합(원 단위 정확 비교)
             → 그 뒤 A = D1 종가 ÷ E − 1 · B = (D1 종가 + 현금) ÷ E − 1 · C = (D1 연결 ÷ D0 연결) ÷ 1.002 − 1 · B−A · C−A · B−C(%p · 표시 때만 반올림)
 4 산출물(로컬 · git 제외 · .gitignore:236): state/ml/research/poc6_26/<run_id>/{run.json, official_rows.json, report.md, report.json}
   · 저장소 결과서에는 출처 · 방법 · 확인 건수 · 판정 · 한계만(여섯 행 · 금액 · 상세 계산표는 로컬)

검증자(같은 PC): 로컬 여섯 행 · 계산 독립 대조 + 공식 화면 원천 대조 1회(종목 · 회차 · 금액 · 지급 경계)
→ 공식 자료 요청 합계 = 개발자 2 + 검증자 1 = 3 · 상한 5(예비 2 = 응답 실패 때 재시도) · 자료 확인 합산 45분
```

- 시험: 작은 단위 시험 하나(가상 숫자) — 권리 경계(결제일 < · = · > 지급기준일) · 기말 분기(실지급일 ≤ D1 · > D1 · 미확인) · official_rows 형식 오류 · A · B · C · 원 단위 정확 검산. 라이브 DB · 네트워크 0.
- 기존 reader · 가격 정의 · 연구 코드 수정 0 · 운영 DB · API · 화면 · OCI 변경 0 · 새 패키지 0.

## 3. 판정 범위

자료 · 세 값이 확인되면 **'069500 · 2025년 1주 표본 검산 완료'**(판정 V1.2 §2). 가격 연결의 변화 원인은 확인된 사건 근거로만 적는다(C 전체를 분배 효과로 귀속하지 않음). 기존 연구(POC6-20 · 21 · 23) 결론을 바꾸지 않는다.

## 4. Q1 · Q2(확정)

- **Q1 = (a)** — 사용자 결정(2026-11-07) · 판정 V1.2 §1: 공개 다운로드 · 개인 연구 · 비공개 로컬 · 여섯 행 최소 기록 · 운용사 문의 없음. (V1.1 의 (c) 대기는 해제. 그때 확인한 KODEX 메인 하단 고지 = "본 웹사이트의 자료를 사전 허가없이 무단으로 사용하거나 데이터베이스화 할 경우…" · 이용약관 · 자료 이용 문의 링크 없음 · CS센터 전화만 — 사용 결정의 근거는 공개 제공 경로와 사용자 결정으로 기록한다.)
- **Q2 = (a)** — KRX ETF 결제제도 T+2(판정 V1.1 A-2 · V1.2 §2).

## 5. 승인 요청 범위(한 묶음 · 판정 V1.2 §3)

승인 기록: 2026-11-08 사용자 '한 묶음 모두 승인 (권장)' — 아래 1 ~ 4 전부.

1. 검산 스크립트 · 가상 자료 단위 시험 구현.
2. 공식 자료 확인: 개발자 [분배금현황 다운로드] 1회 · 팩트시트 PDF 1회 · 검증자 공식 화면 원천 대조 1회(합산 45분 · 공식 자료 요청 최대 5회 · 예비 = 응답 실패 재시도만).
3. 봉인 판 읽기 전용 · git 제외 연구 폴더 쓰기(여섯 행 최소 기록 · 해시) · 임시 원본 삭제 · 본계산 1회 · 검산 보고서 한 건.
4. 검증자 확인 · 설계자 최종 RESULT 뒤 종료 반영 · 커밋 · push(저장소 = 코드 · 시험 · 공개 문서만 · 연구 산출물 · 공식 자료 기록 · 검토 원본은 커밋하지 않음 · 사용자 handoff 제외).

## 6. 하지 않는 것

다른 종목 · 기간 · 분배금 재투자 · 세후 계산 · 현금 이자 · 기존 연구 재실행 · 비교 기준 교체 · 봉인 판 · reader 변경 · 새 패키지 설치 · 직접 JSON 조회(V1.2 로 다운로드 경로로 교체) · 대체 출처 탐색 · 운용사 연락 · 다운로드 원본 · PDF 장기 보관 · 공개 문서에 여섯 행 · 금액 기재 · 운영 DB · API · 화면 · OCI · PUSH · PARAM.
