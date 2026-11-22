"""POC7-01 — 주간 ETF 신규 후보의 즉시 참여와 한 주 보류 비교(PC 회고 연구 · 규칙 하나 · 수동 CLI).

설계 `docs/ai_design/POC7/POC7_MASTER_DESIGN_V1_2026-11-20.md` · PLAN
`docs/ai_plan/POC7/POC7_01_WEEKLY_ENTRY_TIMING_BREADTH_PLAN_V1.md` · 판정
`docs/ai_design/POC7/POC7_01_WEEKLY_ENTRY_TIMING_BREADTH_PLAN_DECISION_2026-11-22.md`
(PLAN PASS · 우선).

가격의 의미: 봉인 KRX `KRX_BASEPRICE_CHAIN` 합성 가격지수의 모의 비교다. 분배금 포함 총수익 · 실제 계좌 ·
운영 채택이 아니다. 결론의 적용 범위는 분류할 수 있었던 과거 후보와 지수다(판정 §2).

```text
protocol  고정 입력(봉인 판 · 기본정보 CSV 해시) · 설정 · 잠금 기대값(PLAN §1-4) · 파일 도구
classify  국내 주식형 세 갈래(공식 기본정보 일치 · 명칭으로 추정 · 미확인) — 이름만 · 가격 미사용
data      봉인 확인(전후) · 공용 reader 연결 종가 · 원시 OHLCV · 그날 지수명 · 합성 시가 · 체결 가능
weekly    신호 주 · 운영 1개월 상위 30 복원 · 후보 · 상승 확산 분모 · 결정 · 짝(체결 가능 여부)
study     경로별 주 수익 · 차이 · 달력 자리 유지 블록 부트스트랩 · 1주 노출 경로 낙폭 · 판정 순서
report    결과 글(report.md) · 주별 기록 칸(판정 §2 이용 가능 시각 문구)
flow      prepare(잠금 · 성과 계산 0) · run(공식 1회 · 예산 판정은 쓰기 직전 한 곳)
verify    독립 재계산(원 reader 계열 · POC6 build_panel 칸 대조 · 지표 · 판정)
```

공용 reader · 운영 코드 · UI · API · OCI · PUSH 변경 없음. LightGBM · torch 를 올리는 POC6 패키지는
verify 의 칸 대조에서만 불러온다. 산출물은 `state/ml/research/poc7_01/` 에 추가만 한다(PC_ONLY).
"""
