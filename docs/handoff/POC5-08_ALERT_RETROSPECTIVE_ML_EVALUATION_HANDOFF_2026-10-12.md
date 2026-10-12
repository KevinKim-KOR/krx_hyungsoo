# POC5-08 인계 — 알림의 ML 사후평가 (2026-10-12)

- **작성**: 개발자(VSCode Claude)
- **독자**: 다음 세션 개발자 — 10-23 공식 R0 → 설계자 다음 단계 지시 대응
- **입력**
  - 설계서 `docs/ai_design/POC5/POC5-08_ALERT_RETROSPECTIVE_ML_EVALUATION_DESIGN_V1.md` — V1 · §12 PLAN 판정 PASS(보충 A ~ C) · §13 RESULT 판정 PASS_TO_DEPLOY · 전달문 원문 3건
  - PLAN `docs/ai_plan/POC5/POC5-08_ALERT_RETROSPECTIVE_ML_EVALUATION_PLAN_V1.md`(판정 반영 = 본문 정정 + §7)
  - 결과서 `docs/ai_result/POC5/POC5-08_ALERT_RETROSPECTIVE_ML_EVALUATION_RESULT.md`
    - §6-2 독립 검토 반영 · §6-3 검증자 r1 수정 · §10 배포 · 종료 기록
  - 같이 종료한 운영 확인
    - `docs/ai_result/POC5/POC5-02_PRICE_OUTCOME_MATURITY_RESULT.md` §11
    - `docs/ai_result/POC5/POC5-03_PC_LEDGER_SYNC_AND_FEEDBACK_RESULT.md` §10
  - 직전 인계 `docs/handoff/POC5-07_HOLDINGS_REFERENCE_DATE_HANDOFF_2026-10-11.md` · 정본 `docs/PROGRAM_TRUTH.md` · 상태 `docs/STATE_LATEST.md`

```text
POC5-08   IMPLEMENTED_VERIFIED_DEPLOYED_CLOSED (2026-10-12)
          검증자 r1 REJECTED(시각 형식 · 실행 시각 자정 대체) → r2 VERIFIED(위험 NONE)
          설계자 RESULT PASS_TO_DEPLOY(결측 표시 열 0/1 비표준화 확정 · 지시문 외 변경 5건 수용)
          커밋 f1951812 push · OCI pull 없음 · PC 재기동 · 실화면 [사후평가 실행] 1회 사용자 확인
POC5-02   IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED (2026-10-12)
          첫 결과 행 = 휴장일인 10-09 08:10 배치 · +1 MATURED 458
POC5-03   IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED (2026-10-12)
          PC 사본 = OCI(실행 29 · 항목 767 · 결과 458) · 화면 +1 % 표시
남은 운영  10-23(금) 배치 완료 뒤 공식 R0 1회(POC5-04 인계 §2)
다음      설계자 다음 단계 지시 대기(설계서가 오면 바로 코딩하지 말고 PLAN 먼저)
```

---

## 1. 만든 것

- **실행**: 「받은 알림 기록」 머리 [원장 새로고침] 옆 큰 버튼 **[사후평가 실행]**.
  - `POST /decision-ledger/retrospective-evaluation` — 본문 `{}` 또는 `{end_date}`
  - PC 원장 사본을 04 `load_snapshot`(`mode=ro`)으로 1회 읽는다 → `app/alert_retro/`
- **가격 사후평가**: 저장된 +1 / +5 / +20 결과를 그대로 쓴다. 결과 없는 칸은 실행 때 고정한 **가격 관측 기준일**로 나눈다.
  - 평가일이 기준일보다 뒤 = 미도래 · 같거나 앞 = 도래 후 미기록
  - 가격 관측 기준일 = 획득 시각까지 종가가 끝난 마지막 거래일(15:30 기준)
- **ML**: +5 MATURED 라벨 · Ridge(alpha=1 · svd) vs 학습 가중 중앙값.
  - 가중치 w = 1/(신호일 계열 수 × 그 날 같은 계열 행 수)
  - 학습 구간만 전처리 — 숫자 2개 대입 · 표준화 · 결측 표시 0/1 그대로 · 범주 one-hot
  - 구간: 종료일 5거래일 전 anchor · 15거래일 = 5일 × 3
  - 학습 경계: 신호일 < 구간 첫날 · 평가일 15:30 < 시험 시작 · `computed_at` < 시험 시작
  - 판정: 날짜 평균 MAE(%p) · 세 구간이 모두 유효할 때만 '개선 / 차이 없음 / 악화'
- **조회**: `GET …/latest`(선택 `event_id`) — 완성된 최신 폴더만 읽는다. 원래 보고의 종료일 · 기준일로 입력 digest 를 다시 재서 '입력이 변경됨 · 재실행 필요'를 띄운다. 확인할 수 없으면 노란 줄을 띄운다.
- **손상 = CHECK_REQUIRED**(산출물 없음 · 대체 시각 없음)
  - 필수 표 · 참조 · 중복 키(실행 · 항목 · 결과) · values_json
  - 실행 날짜 · 예정 시각 HH:MM · 실행 시각(시간대 있는 ISO · KST 날짜 일치)
  - 결과 행 형식(계산 시각 포함)
- **산출물**: `state/ml/research/poc5_08/<YYYYmmddTHHMMSSffffff>_<8hex>/report.json · input_snapshot.json`
  - 임시 폴더에 다 쓴 뒤 이름을 바꾼다. 실패하면 500 이고 이전 산출물을 보존한다.

## 2. 운영 · 사용 메모

1. 첫 실제 실행: 2026-10-12 13:27 · 10-08 하루분(항목 482). ML 은 '자료 부족'이 정상이다.
   - 세 구간 전체 비교는 조건부로 가장 이르면 12-09 종료일 보고부터다. 날짜로 막지 않고 실행마다 실제 표본으로 판단한다.
2. 최신 결과를 보려면 사용자가 [원장 새로고침] → [사후평가 실행] 순서로 누른다. 자동 · 정기 실행은 없다.
3. 사용자 평가는 표본 · 라벨 · 입력에 쓰지 않는다. 평가만 바뀌어도 digest 가 바뀌어 '입력 변경'이 뜨지만 모델 수치는 같다.
4. 이것은 연구 예외다(2026-10-11 POC5-08 연구 예외 · 기반 문서 6곳). 운영 · 추천 모델이 아니며 `CURRENT_DEPLOYABLE_ML_MODEL=none` 을 유지한다.
5. 라이브 원장 · 연구 폴더에 시험 기록을 넣지 않는다. 시험은 tmp 사본과 `report.RESEARCH_ROOT` / `_now` 바꿔 끼우기를 쓴다.

## 3. 다음 개발자 주의 (이번 단계 교훈)

1. **형식 검사는 '문자열인가'가 아니라 실제로 읽히는가**(r1 반려).
   - 판단에 쓰는 칸마다 소비 지점을 먼저 열거하고 그 형식대로 파싱한다.
   - 실패하면 값을 만들지 말고 손상으로 처리한다.
   - 손상 시험은 '타입은 맞고 내용이 틀림'(`invalid-time` · `25:00` · 시간대 없음 · 날짜 불일치)까지 넣는다.
2. **설계의 '표시한다' 문장은 화면까지 대조한다** — 목업 확인만으로 놓친 항목 4개를 독립 검토가 찾았다(설계자 수용).
3. **변이 시험은 생존 변이에서 시험 공백을 찾는 데 쓴다.** 처음 4개가 생존했고(2자리 판정 · price_basis 정확 비교 · 계약 버전 · 시험 행 평가일 ≤ 종료일), 숫자 전처리 누출은 검토자가 별도 변이로 찾았다.
4. **보고 숫자는 실측 그대로** — r1 수정 보고에서 시험 건수를 '손상 10 · 정상 2'로 잘못 적어 검증자가 '9 · 1'로 정정했다.
5. report.json 은 item 마다 슬롯 3개를 담는다. 자료가 쌓이면 커지므로, 느려지면 그 근거로 설계자에게 올린다(지금 페이지 처리 · 캐시 추가 금지 · 설계 §13-4).
6. `git add -A docs/` 금지 — 사용자 소유 untracked `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`.

## 4. 다음 단계

- **10-23(금) 배치 완료 뒤**: 공식 R0 1회(POC5-04 인계 §2 · 별도 운영 점검).
- **설계자**: 다음 단계 지시 대기 — 설계서가 오면 PLAN 먼저(`docs/ai_plan/POC5/`).
- 10-08 15:40 사건의 +1(평가일 10-12)은 10-13 08:10 배치에서 성숙 예정이다. 확인은 의무가 아니다(설계서 §13-5).
