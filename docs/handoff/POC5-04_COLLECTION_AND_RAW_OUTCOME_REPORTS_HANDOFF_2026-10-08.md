# POC5-04 인계 — R0 수집 점검 · R1 원시 결과 리포트 (2026-10-08)

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(10-12 POC5-02 · 03 확인 → 10-23 공식 R0 → 후속 설계)
- **입력**
  - 설계서 `docs/ai_design/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_DESIGN_V1.md` — 개정 1 · 끝에 PLAN 판정 · RESULT 판정(PASS) · 전달문 원문
  - PLAN `docs/ai_plan/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_PLAN_V1.md` — §7 판정 정정 · §8 구현 중 확정 · §9 검증자 r1 정정
  - 결과서 `docs/ai_result/POC5/POC5-04_COLLECTION_AND_RAW_OUTCOME_REPORTS_RESULT.md`
  - 직전 인계 `docs/handoff/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_HANDOFF_2026-10-08.md`(01B 종료 · 02 · 03 남은 확인) · 정본 `docs/PROGRAM_TRUTH.md` · 상태 `docs/STATE_LATEST.md`

```text
POC5-04   IMPLEMENTED_VERIFIED_CLOSED (2026-10-08)
          검증자 r1 REJECTED(필수 사본 표 누락 · iterations 0) → r2 VERIFIED · 설계자 RESULT PASS(개발 종료 · 변경 5/5)
          PC 수동 도구 — OCI pull · cron · .env 변경 0
남은 운영  10-12(월) 08:10 이후  POC5-02 첫 결과 행 · POC5-03 화면 가격 결과(직전 인계 §3)
          10-23(금) 배치 완료 뒤  공식 R0 1회(아래 §2)
다음 설계  설계자 후보 = 보유 매수 · 매도 이력(BACKLOG §8) · ML 사후평가(무평가 알림도 사용 계약 유지)
```

---

## 1. 만든 것

- `scripts/run_ledger_report.py r0|r1` + `app/ledger_reports/`(source · dates · evidence · r0 · r1 · bootstrap · render).
- 입력 = PC 원장 사본(`state/decision/decision_evidence.sqlite` · 03 이 동기화 · `mode=ro`). 출력 = `state/ml/research/poc5_04/<r0|r1>_<종료일>_<생성시각>/report.md · report.json`(새 폴더만).
- 입력 사본 손상(필수 표 6개 중 누락 · 결과 표 생성 기록 뒤 결과 표 누락) → R0 `CHECK_REQUIRED` · R1 실행 실패(exit 3).
- R0 `CHECK_REQUIRED` 는 '점검하라' 는 뜻이다. 실행 failed · 전달 failed/partial 은 운영 점검 대상이며 원장 수집 결함 확정이 아니다(설계자). 정상 skipped · no_selection · 반복 억제 · 상한 제외는 실패가 아니다.

## 2. 공식 R0 실행 절차 (2026-10-23 · 개발자 1회)

D10 = 2026-10-22(운영 캘린더 실측). 10-22 종가는 10-23 08:10 배치가 적재하고 09:20 이 보강한다. **09:30 이라는 시각이 아니라 실제 배치 완료 근거가 조건이다.**

1. **배치 완료 확인(OCI 읽기 전용)** — `logs/oci_market_data_batch.log` 의 10-23 08:10 · 09:20 결과 줄(상태 · KRX 적재일 · 완료 시각) · 원장 오류(`grep "decision ledger" logs/three_push_runtime_cron.log logs/low_freq_push_cron.log`) · 10-08 ~ 10-22 PUSH 실패를 확인한다.
2. **대조 근거(OCI 읽기 전용 · 같은 SSH 명령에서 시각을 붙인다)**

   ```bash
   ssh oci-krx 'cd /home/ubuntu/krx_hyungsoo && echo "captured_at=$(date -Iseconds)" && venv/bin/python scripts/run_decision_ledger_reconcile.py' > <scratchpad>/reconcile_2026-10-23.txt
   ```

3. **운영 근거 파일**(개발자 작성 · scratchpad · 저장소에 두지 않는다)

   ```text
   price_batch_price_date=2026-10-22
   price_batch_status=success
   price_batch_completed_at=2026-10-23T09:20:xx+09:00   (1 의 실제 완료 시각)
   ops_error_count=0                                    (1 에서 확인한 배치 · 원장 · PUSH 오류 건수)
   메모: … (원인 · 영향 · 현재 조치 상태 — 비밀값은 쓰지 않는다)
   ```

4. **PC 동기화** — 사용자에게 「진단·상태 > 받은 알림 기록」 `원장 새로고침` 을 부탁한다(배치 완료 **뒤**). 리포트는 마지막 성공 동기화 시각 > 배치 완료 시각인지 본다.
5. **실행**

   ```bash
   .venv/bin/python scripts/run_ledger_report.py r0 --end 2026-10-22 \
       --reconcile-evidence <scratchpad>/reconcile_2026-10-23.txt --ops-evidence <scratchpad>/ops_2026-10-23.txt
   ```

6. **보고** — 판정 · `not_ready_reasons` · `problems` · 대조 기간 · 예정 실행 누락 · 가격 슬롯 · PENDING 을 설계자에게 보고한다. failed/partial 이 있으면 원인 · 영향 · 조치 상태를 함께 적는다. 과거 기록 삭제 · 재발송 · PRIMARY 시작일 재설정은 하지 않는다. 같은 기간을 COLLECTION_OK 로 만들려고 반복 점검하지 않는다.

R1 은 연구 · 검토가 필요할 때 `r1 --end <완료 거래일>` 로 수동 실행한다(+20 성숙 · 충분한 표본을 기다리지 않는다 · `INSUFFICIENT_SAMPLE` 은 사실대로).

## 3. 주의

1. **`git add -A docs/` 를 쓰지 않는다** — 사용자 소유 `docs/handoff/INVESTMENT_MODEL_V2_MASTER_HANDOFF_2026-07-26.md`(untracked)가 함께 올라간다(이번 단계에서 한 번 일어나 `git restore --staged` 로 내림). 경로를 하나씩 지정한다.
2. 결과서 수치는 그 자리에서 실측한 뒤 적는다(이번 단계에서 줄 수를 먼저 적었다가 바로 고친 일이 있다).
3. 리포트 출력 폴더는 `state/ml/research/` 아래라 라이브 해시 비교(전체 회귀 전후)에 들어간다 — 회귀 중에 리포트를 실행하지 않는다.
4. `--end` 는 오늘(KST) 이전 · 운영 거래일만 받는다. 개발 시험은 PC 사본 **복사본** · scratchpad 출력으로 한다.
