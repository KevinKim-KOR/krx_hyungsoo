# POC5-07 인계 — 기존 보유의 가격 비교 기준일 (2026-10-11)

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(POC5-UI-01 버튼 크기 통일 → 10-12 POC5-02 · 03 확인 → 10-23 공식 R0 → 알림 ML 사후평가 설계 대응)
- **입력**
  - 설계서 `docs/ai_design/POC5/POC5-07_HOLDINGS_REFERENCE_DATE_DESIGN_V1.md` — V1 · §9 PLAN 판정 · §10 RESULT 판정(§10-3 = POC5-UI-01 지시) · 전달문 원문 3건
  - PLAN `docs/ai_plan/POC5/POC5-07_HOLDINGS_REFERENCE_DATE_PLAN_V1.md`
  - 결과서 `docs/ai_result/POC5/POC5-07_HOLDINGS_REFERENCE_DATE_RESULT.md` — §6-2 독립 검토 · §10 RESULT 전 실제 설정 · §11 배포 · 종료 기록
  - 직전 인계 `docs/handoff/POC5-06_MANUAL_REENTRY_REVIEW_AND_ML_EVIDENCE_HANDOFF_2026-10-10.md` · 정본 `docs/PROGRAM_TRUTH.md` · 상태 `docs/STATE_LATEST.md` · `docs/backlog/BACKLOG.md` §8 · §10

```text
POC5-07   IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED (2026-10-11)
          검증자 r1 VERIFIED(위험 NONE) · 설계자 RESULT PASS_TO_DEPLOY(지시문 외 변경 4 + 문서 정정 · RESULT 전 실제 설정 · 647줄 한계 수용)
          구현 커밋 89f90f0f · OCI pull 없음(OCI 실행 파일 변경 0) · PC 재기동 · 최종 화면 사용자 확인
          PC 보유 = V2 · revision 1 · 기준잔고 32 + 가격 비교 기준일 32(모두 2026-01-02 · 실제 매수일 미상)
다음 작업  POC5-UI-01 버튼 크기 통일(설계 POC5-07 §10-3 · 큰 48px 기본 · 중간 40px · 설계자 PLAN 왕복 없음)
남은 운영  10-12(월) 08:10 이후  POC5-02 첫 결과 행 · POC5-03 화면 가격 결과(POC5-01B 인계 §3)
          10-23(금) 배치 완료 뒤  공식 R0 1회(POC5-04 인계 §2)
다음 설계  알림의 ML 사후평가(평가 없는 알림도 객관적 가격 결과로 · 사용자 평가는 별도 근거 · 06 가격 연구와 다른 모델)
```

---

## 1. 만든 것

- **기록 종류 REFERENCE_DATE**(`app/holdings_book.py`): `personal_trade_history.records` 에 payload `{reference_date: 날짜 | null}` 한 칸 · 기준잔고 / 잔고 등록으로 시작한 기간만 · 날짜 ≤ 저장 시각의 KST 날짜(`kst_day`) · 정정 · 취소 대상 아님 · 같은 기간 유효 값 = 저장 순서 마지막 기록(null = 해제). 무결성 검사는 거치되 **기간 계산(replay)에서 제외** — 수량 · 평단 · 원가 · 손익 · 순서 · 기간 · `holdings` · OCI payload 무관.
- **저장**(`app/holdings_reference_date.py`): 기존 `PUT /holdings/trade-history` 의 `action: "reference_date"` — 요청 칸 5개 정확히(`reference_date` 빠지면 422 · 해제 = null 명시) · 대상 1 ~ 200 · request_id 재시도 확인 → revision 확인 → 전부 판정 뒤 한 번 교체 · 같은 값 / 미설정 해제 = 쓰기 0.
- **시장 흐름**(`app/holdings_market_flow.py`): `reference_flow` = '가격 비교 기준일 이후 종가 변화'(기준일 → 마지막 저장일 · 05 규칙 그대로) · 실제 매도로 끝난 기간은 보유 기간 항목 시작 = 기준일 · `reference_note`.
- **화면**: 보유 표 [가격 비교 기준일 설정](`ReferenceDateDialog` · 대상 목록과 같은 조회의 revision) · History 기간 머리 `ReferenceDateEditor`('실제 매수일: 미상' · '가격 비교 기준일' · [수정/해제] 같은 줄) · 기준일 있으면 매매 없는 기간에도 [시장 흐름 보기] · 시장 흐름 '실제 매수일: 미상' 줄 + 기준일 항목.

## 2. 운영 · 사용 메모

1. 지금 PC 보유 파일은 V2(revision 1)다. 해제는 비교 설정만 지우는 동작이고 V1 복구가 아니다. 배포 전 V1 백업 `state/holdings/backup/holdings_latest_pre_POC5-05_20261009.json` 은 그대로 둔다(덮어쓰면 기준일 · 이후 매매 기록이 사라진다).
2. 기준일만 바꾸면 OCI 적용 payload · hash · `pending_apply` 는 그대로다(OCI 카드 '미적용' 안 생김). 실제 매매를 넣으면 기존대로 OCI 미적용 표시.
3. 재매수로 생긴 새 기간(BUY 시작)은 기준일을 복사하지 않고 둘 수도 없다(422) — 실제 거래일을 쓴다.
4. 라이브 보유에 시험 기록을 넣지 않는다(시험 = tmp + `tests/_live_guard.py`). 실화면 확인은 입력 화면을 열고 [취소]로 닫는다.

## 3. 다음 개발자 주의 (이번 단계 교훈)

1. **계산 경로에 들어가는 기록 종류를 늘릴 때는 replay 정렬 · '보유 0 뒤 기록' 검사부터 본다** — 메타데이터 기록은 계산 전에 빼고 따로 읽어야 종료 기간에도 설정할 수 있다.
2. **화면이 쓰는 revision 은 화면이 본 목록과 같은 조회에서** — 부모의 다른 조회 revision 을 쓰면 짧은 틈에 덮어쓰기 보장이 깨진다(독립 검토 지적).
3. **'기간' 같은 단어도 계약 문장과 대조** — 기준일 구간을 '보유 기간'이라 부르면 '그날 보유했다는 증거 아님'과 어긋난다.
4. 변이 시험에서 안 잡힌 변이는 시험 자료가 그 분기를 안 지나는지 먼저 본다(이번: 끝난 기간에 추가매수가 없어 '시작 = 첫 매수' 변이가 같은 결과).
5. `app/holdings_market_flow.py` 647줄 — 다음에 기능을 더할 때 `REASONS` · `PERIOD_REASONS` · `NOTES` · 기준일 문구 등 상수를 먼저 분리(KS-10 650).
6. 사용자에게 보이는 모든 문장은 한국어(영어 검토 보고를 받은 직후 특히 주의 · 2026-10-11 지적).
7. `git add -A docs/` 금지 — 사용자 소유 untracked `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`.

## 4. 다음 단계

- **POC5-UI-01 버튼 크기 통일**(설계 POC5-07 §10-3 · 설계자 PLAN 왕복 없음): 큰 버튼(기본) 높이 48px · 글자 16px · 좌우 16px — 실행 · 저장 · 적용 · 새로고침 · 추가 · 분석 · 대화창 하단 / 중간 버튼 40px · 14px · 좌우 12px — 행 안 History · 수정 · 해제 · 펼치기 · 날짜 이동. 메뉴 · 탭 · 링크 제외 · 공통 스타일 2개 · 기존 색 · 위험 · 비활성 · 포커스 유지 · 좁은 폭 줄바꿈. 사용처 → 두 크기 매핑 · 변경 파일을 짧게 기록 · 화면 회귀 · tsc · eslint · 대표 실화면(보유 행 · 대화창 · 새로고침 · 좁은 폭). 별도 커밋. 실측 출발점 = BACKLOG §10(7가지 크기).
- **10-12(월) 08:10 이후**: POC5-02 첫 결과 행(OCI 읽기 전용) · POC5-03 화면 가격 결과 표시 확인 → 02 · 03 종료.
- **10-23(금) 배치 완료 뒤**: 공식 R0 1회(POC5-04 인계 §2).
- **설계자**: 알림의 ML 사후평가 설계 — 설계서가 오면 바로 코딩하지 말고 PLAN 먼저(`docs/ai_plan/POC5/`).
