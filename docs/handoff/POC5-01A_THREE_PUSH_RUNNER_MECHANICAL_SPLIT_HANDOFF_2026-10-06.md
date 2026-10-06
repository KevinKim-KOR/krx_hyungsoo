# POC5-01A 인계 — 세 PUSH 러너 기계 분리 (2026-10-06)

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자(`POC3-02D-OPS-04` 검증 대응 · 커밋 · 배포 → `POC5-01B` 운영 원장 PLAN)
- **입력**
  - 설계서 `docs/ai_design/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_DESIGN_V1.md` — 설계자 정정 원문 · PLAN 판정 2회 · RESULT 판정 원문(끝)
  - PLAN `docs/ai_plan/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_PLAN_V1.md` — §1-8 테스트가 러너에 바꿔 끼우는 이름 14개(런타임 전수 기록)
  - 결과서 `docs/ai_result/POC5/POC5-01A_THREE_PUSH_RUNNER_MECHANICAL_SPLIT_RESULT.md` — 이동표 · 동등성 · 파괴 시험 · 배포 · 첫 거래일(§11)
  - 지금 실제 동작 정본 `docs/PROGRAM_TRUTH.md`(§4 진입점 · 부록 A `_finish`) · 상태 `docs/STATE_LATEST.md`

```text
POC5-01A        IMPLEMENTED_VERIFIED_DEPLOYED_OPERATION_CONFIRMED (2026-10-06)
                설계자 PLAN PASS(2026-10-03) · RESULT PASS_TO_VERIFIER(2026-10-04)
                검증자 VERIFIED(재검증 2026-10-04 · r1 REJECTED — 고정 이름 13 → 14 · is_already_sent 누락)
배포            커밋 a0a2c514(선행 문서) · 87238e1e(구현) push 2026-10-04 · OCI pull 2026-10-04(사용자 · 휴장 중)
                cron · .env 변경 없음
운영 확인        2026-10-06 첫 거래일 통과(아래 §2)
다음            POC3-02D-OPS-04(로컬 구현 완료 · 검증자 r1 REJECTED 정정 중) → POC5-01B 운영 원장(OPS-04 배포 뒤)
```

---

## 1. POC5-01A 가 바꾼 것

- `scripts/run_three_push_runtime_oci.py` 646 → 517줄 — `run()` 안 네 블록을 문장 순서 그대로 새 모듈 3개로 옮겼다. 동작 · 본문 · 판정 · 상태 저장 순서 변경 0.
  - `app/three_push_runtime/runner_record.py` — 실행 기록 21키 시작 · 종료(`_finish` 본문 `finish_run`)
  - `app/three_push_runtime/runner_preflight.py` — PARAM · 비밀값 · slot · kind 활성 사전 검사
  - `app/three_push_runtime/runner_dispatch.py` — kind 조립(§3-c · 3-d · 3-e) · flag 뒤 판정(§6-c) · `KindAssembly`
- 테스트가 러너 모듈에 바꿔 끼우는 이름 14개는 러너에 남기거나(7) 호출 때 인자로 넘긴다(7). 새 모듈은 그 이름을 직접 import 하지 않는다.
- 운영 계약 차이 0 — 예외 문맥(`__context__`) 연결 차이 1건만 있다(PARAM 실패 + insert_status 실패가 겹친 경로 · 결과서 §6-1).
- 동등성 도구 `scripts/poc5_01a/runner_split_equivalence.py`(검증 전용 · OCI 실행 금지). **`POC3-02D-OPS-04` 이후 rc 2** — POC5-01A 가 '바뀌면 안 되는 기존 모듈' 로 고정한 20개 중 4개를 OPS-04 가 의도적으로 고쳤다(러너 시나리오 비교는 다름 0). POC5-01A 시점 검증에는 커밋 `87238e1e` 로 돌린다.

## 2. 첫 거래일 실측 (2026-10-06 · OCI 읽기 전용)

| 시각 | 실행 | 결과 |
|---|---|---|
| 08:10 | 시장 데이터 배치 | `success` · KRX `already_loaded`(10-02 · 휴일 10-05 08:10 에 적재) · 대표 27/27 |
| 08:30 | 시장 브리핑 | sent · 본문 261자 |
| 09:15 · 12:30 · 15:40 | 보유 브리핑 | sent · 175 · 175 · 215자 |
| 09:20 | KRX 보강 | `ok` · `already_loaded` |
| 09:30 · 10:30 · 11:30 · 12:30 | 장중 위험 | sent |
| 13:30 · 14:30 · 15:20 | 장중 위험 | skipped `intraday_daily_cap_reached`(기존 일일 상한) |

- 실행 11회 = 10-02 와 같다. 실행 기록 키 수가 10-02 와 같다(시장 40 · 보유 37 · 장중 sent 55 · 15:40 보유 38).
- 일일 상한 skip 기록은 46키다. 10-01(41키)보다 5개 많은데, 모두 OPS-03 기능 키다(`intraday_entry_omitted` · `intraday_entry_omitted_reason` · `intraday_representatives` · `intraday_trend_basis` · `risk_price_basis` — 10-01 15:20 기록은 OPS-03 OCI 반영 16:32 전). POC5-01A 때문에 생긴 차이가 아니다.
- `logs/low_freq_push_cron.log` · `logs/oci_market_data_batch.log` Traceback 0.

## 3. OCI 읽기 전용 확인 방법

```bash
ssh oci-krx 'cd /home/ubuntu/krx_hyungsoo && venv/bin/python - <<"PY"
import json
from pathlib import Path
rows=[json.loads(l) for l in Path("state/three_push/oci_runtime_history.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
for r in rows:
    if str(r.get("runtime_kst","")).startswith("2026-10-06"):
        print(r.get("runtime_kst","")[11:16], r.get("push_kind"), r.get("status"), r.get("reason"), r.get("message_text_length"), len(r))
PY'
```

본문 · 가격 · 키 값은 출력하지 않는다. 쓰기 · 발송 · 재시작 · pull · cron 변경은 사용자 몫이다.

## 4. 다음 단계 진입 정보

1. **`POC3-02D-OPS-04`**(남은 운영 정정 6건) — 로컬 구현 완료 · 사용자 확인 완료(2026-10-06) · **검증자 r1 REJECTED → 정정 중**(수동 `--krx-only` 보강 제외 · `RemoteProtocolError` 제외 · 줄 수 오보). 결과서 `docs/ai_result/POC3/POC3-02D-OPS-04_REMAINING_OPERATIONAL_CORRECTIONS_RESULT.md`. 커밋 · push · OCI pull 은 검증자 VERIFIED 뒤 별도 승인.
2. **`POC5-01B`** 운영 원장 — 설계서 `docs/ai_design/POC5/POC5-01B_OPERATIONAL_DECISION_EVENT_LEDGER_DESIGN_V1.md` · PLAN 아직 없음 · OPS-04 배포 뒤 착수(표본 섞임 방지 · 설계자 정정 2026-10-02). 원장 DB = `state/decision/decision_evidence.sqlite`. 주입 지점은 POC5-01A PLAN §1-12(`KindAssembly` additive 필드 · `finish_run`).
3. 설계자 확인 요청으로 남은 것: OPS-04 `RemoteProtocolError` 중 연결이 끊긴 경우를 일시 오류에 넣을지(지금은 뺀 상태).

## 5. 교훈

- **'전수 N개' 인벤토리는 런타임 기록으로 센다** — AST 변수명 스캔은 `rig["runner"]` 같은 형태를 놓친다(검증자 r1 반려 원인 · 메모리 `feedback_runtime_inventory_over_static_scan`).
- **결과서 절대 표현 금지** — "코드 동작 차이 0" 대신 "운영 계약 차이 0 · 예외 문맥 차이 1건"처럼 실측 범위만 적는다(설계자 RESULT 지시).
- **휴장 연휴 뒤 첫 거래일은 실행 기록 키 수 비교가 가장 빠른 동등성 확인**이다 — 단 비교 기준 날짜가 다른 단계(OPS-03 등) 배포 전후인지 먼저 확인한다.
- 맥북을 덮거나 오래 비우면 긴 회귀가 멈춘다 — `caffeinate -i` 는 덮개 닫힘 잠자기를 막지 못한다(전체 회귀 1회 30분 제한에 걸려 중단 · 2026-10-06).
