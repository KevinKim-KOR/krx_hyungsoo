# POC5-27 개발 PLAN V1 — PC 에서 OCI 운영 기준 실제 활성화

작성 2026-10-20 · 작성자: 개발자(VSCode Claude) · 수신: 설계자
근거: `docs/ai_design/POC5/POC5-27_PC_TO_OCI_RUNTIME_PARAM_ACTIVATION_DESIGN_V1.md`(V1 · 백로그 #50)

```text
STATUS   = PLAN 제출(2026-10-20) · 질문 4(Q1 = 기반 문서 해석 + 사용자 원격 쓰기 구현 승인) · 사용자 목업 확인(2026-10-20 · 그대로) · 사용자 원격 쓰기 승인(2026-10-20 · PLAN 권장 방식) → 설계자 PLAN PASS(2026-10-20 · Q1 ~ Q4 (a) + 보완 · §9) → 구현(2026-10-20) · 사용자 실화면 확인 완료(2026-10-20) · 검증자 r1 REJECTED(결과서 §10 · 코드 결함 2건) · 개발자 정정 → 검증자 r2 REJECTED(결과서 §11 · 첫 상태 조회 실패 뒤 적용 응답 단절 시 확인 불가 누락/P2) · 개발자 정정 → 검증자 r3 VERIFIED(2026-10-20 · 결과서 §12) → 설계자 RESULT PASS(2026-10-20 · 결과서 §13) → **IMPLEMENTED_VERIFIED_CLOSED**(종료 2026-10-20) · 설계자 RESULT 판정 대기
SCOPE    = 「OCI 운영·적용」 ② [현재 기준 OCI 적용] = OCI DB 활성 PARAM 을 PC 운영 기준 값으로 실제 활성화 + 다시 읽어 확인
           새 메뉴 · API 경로 · DB 표 · 큐 · 스케줄러 · .env 플래그 · 의존성 · 러너 변경 · PUSH 발송 0
MEASURED = 2026-10-20 · 코드 grep / read(HEAD 1fb287e0) · OCI 읽기 전용 2회(사용자 승인 · `mode=ro` · 쓰기 0)
```

## 1. 지금 호출 경계 (설계 §5-1)

- **버튼 → API**: 「현재 운영 기준」 카드 [현재 기준 OCI 전달](`ThreePushParamCard.tsx:216`)이 `POST /three-push/param/apply` 를 부른다(본문 무시 · 120초).
- **API 1단계** `_create_approved_manual_seed_param`(`app/api_three_push_param.py:256-288`):
  - `build_manual_seed_param()` 으로 **코드 기본값**(알림 종류 4 + 정책 10 = 14값)의 새 PARAM 을 만든다. 매번 새 `param_id` 다.
  - **PC DB** 에 새 버전 + 활성(`activated_by=api_param_apply`), PC JSON(latest · history)을 쓴다.
  - **사용자가 값을 고르는 화면은 없다.** 설계 '현행 허용 운영값'은 곧 PC 최신 운영 기준 JSON(코드 기본 14값)이다.
- **API 2단계** `_run_sync_to_oci`(`:291-333`)가 `scripts/sync_three_push_runtime_param.py` 를 하위 프로세스로 돈다.
  - ssh mkdir → scp `.tmp` → mv `latest_runtime_param.json` → 확인 스크립트를 OCI `/tmp` 에 올려 시스템 python3 로 **JSON 만** 검사 → PC 상태 파일 기록.
- **OCI DB 를 바꾸는 단계는 없다.** OCI 러너는 실행마다 시작 때 한 번 DB 활성값만 읽는다(`runner_preflight.py:30-36` → `read_active_param_dict` · JSON 대체 없음).
- **지금의 수동 활성화**(`scripts/create_three_push_runtime_param.py --approve`): OCI 에서 **코드 기본값으로 새 PARAM 을 만들어** 활성화한다. 전달받은 JSON 을 읽지 않는다.
- **이 경로에 있는 기존 결함**(이번에 함께 고칠 대상 · 지시문 외 변경으로 결과서에 기록):
  1. sync 가 **확인 전에 이름을 바꾼다** → 확인이 실패해도 OCI JSON 은 이미 교체돼 있다(API 설명문 :298-299 · :345-346 과 반대).
  2. 확인 스크립트 업로드가 실패하면 `verify=skipped` 인데도 sync 가 `success` 로 끝난다.
  3. 단계별 제한 시간 합(최대 180초)이 바깥 제한(120초)보다 길다. ssh 에 `BatchMode` · `ConnectTimeout` 이 없다.
  4. 서버 쪽 동시 실행 막음이 없다(화면 버튼만 막음).

## 2. OCI 저장 · 활성 · 복구 (설계 §5-2)

- **저장소**: OCI `state/runtime/runtime_state.sqlite`(상대 경로 · cron 은 저장소 루트에서 `venv/bin/python` 으로 실행 — OCI 확인).
  - 표 3개: `runtime_param_version` · `runtime_param_value` · `runtime_param_active`(범위당 1줄 · 이력 없음).
- **버전 만들기** `create_param_version`(`runtime_param_store.py:317-347`): 버전 줄 + 값 줄을 **한 트랜잭션**으로 쓴다. 실패하면 남는 것이 없다.
  - **같은 값 판정은 메타데이터까지 넣은 해시**(param_id · 시각 포함)라, 같은 값이어도 새 `param_id` 면 새 버전이 생긴다.
  - → 설계 '같은 유효값이면 새 버전 없음'은 **유효값 비교를 먼저 해야** 지킬 수 있다.
- **활성 전환** `activate_param_version`(`:350-366`): 한 문장 upsert(별도 트랜잭션). 대상 버전이 없으면 외래 키 오류로 포인터는 그대로다. **'활성 없음' 순간이 없다.**
  - 버전 만들기와 전환 사이에 실패하면 비활성 버전만 남고 포인터는 그대로다(운영 영향 없음).
- **승인 게이트 없음**: `approved_*` 는 만들 때 채워지고, 전환은 검사하지 않는다.
- **복구(이전 버전 다시 활성)**: 함수 `activate_param_version(옛 id)` 는 있지만 **실행 도구 · 문서화된 절차가 없다.** 버전은 지우지 않으므로(append-only) 옛 버전은 DB 에 남아 있다.
- **검증의 빈틈**: `validate_param_dict` 는 정책 dict 안의 키를 보지 않는다. 비어 있는 정책도 통과하지만, DB 로 다시 만들면 키가 빠져 러너가 `param_load_error` 로 멈춘다.
  - → 전환 전에 **DB 에서 다시 만든 후보가 러너 읽기 함수(`from_dict`)를 통과**하고 유효값이 요청과 같은지 확인한다.

## 3. 비교 · 표시 재사용 (설계 §5-3)

- **유효값 비교**: `oci_status_rows.param_active_job` · `_compare_values` 를 재사용한다.
  - 알림 종류는 집합(순서 무시), 나머지는 정확히 같아야 한다. 분모는 계산값(지금 14)이다.
  - **버전 ID 가 달라도 값이 같으면 '일치'**(OPS-04 Q7 b)를 그대로 지킨다. ID 는 화면 · 응답에 싣지 않는다.
- **OCI 활성값 읽기**: `oci_status_rows.param_values_block`(`mode=ro` heredoc · 버전 ID 를 읽지 않음)을 적용 전 읽기와 결과 다시 읽기에 재사용한다.
- **① '운영 기준 활성' 행**: 지금은 PC 백엔드 **기동 때 1번 읽은 캐시**로만 비교한다(POC3-07 Q2 · Q3 · OPS-04).
  - 적용 요청 안에서 읽은 OCI 활성값으로 이 캐시를 바꾸는 방법 → **Q3**.
- **문구 · 상태**: ① 행의 '일치 / 다름 / 확인 불가' 3분류를 그대로 쓴다. 꼬리말 '— 전달만 되고 활성화되지 않음'은 이제 쓸 일이 없어 뺀다.

## 4. 원격 실행 도구 · 배포 (설계 §5-4)

- **본보기 = 장중 설정 원격 적용**(`scripts/sync_intraday_config.py` + `scripts/apply_intraday_config_oci.py` · 2026-09 사용자 적용 운영 중):
  - 원격 쓰기 전에 활성값을 먼저 읽는다.
  - 도구를 임시로 올려 OCI venv python 과 `--project-root` 로 돈다.
  - **OCI 프로세스 안에서** 검증 → 기록 → 전환 → 다시 읽기를 하고, 불일치면 직전 값으로 되돌린다.
  - 결과가 애매하면 0 · 2 · 5초 **읽기만** 다시 해서 성공 / 실패 / 확인 불가로 정리하고, 임시 파일을 지운다.
- **새 OCI 쪽 도구** `scripts/apply_three_push_param_oci.py`(짧은 CLI · OCI 에 이미 있는 저장 함수만 import):
  1. `--json <전달 파일> --project-root <루트>`: 파일 검증(`read_param_file`) → 지금 활성값 읽기 → **유효값 같음 → 쓰기 없이 'SAME'**.
  2. 다름 → 버전 기록(`create_param_version` · PC 값 그대로) → 다시 만든 후보 검사(`from_dict` 통과 · 유효값 = 요청) → 직전 활성 id 기억 → 전환(`activate_param_version` · `activated_by=pc_param_apply`).
  3. 다시 읽기(`read_active_param_dict`) → 유효값 = 요청이면 'ACTIVATED', 아니면 직전 id 로 되돌리고 'FAILED readback'.
  4. `--list`(읽기만 · 버전 목록과 지금 활성값과의 차이 수) · `--activate-version <id>`(복구: 대상 버전 검사 → 전환 → 다시 읽기).
- **PC 쪽**: 새 모듈(예: `app/three_push_param_activation.py`)이 API 안에서 순서를 맡는다. `api_three_push_param.py`(389줄)는 부르기만 한다.
  1. PC 기준 만들기(지금 그대로).
  2. **적용 전 읽기**(`param_values_block`): 못 읽으면 원격 쓰기 없이 실패('기존 값 유지').
  3. 같으면 **원격 쓰기 없이** '일치 · 변경 없음'으로 끝낸다(새 OCI 버전 0).
  4. 다르면 JSON 전달(기존 sync · 1번 결함 고쳐 '확인 뒤 이름 바꾸기') → 도구 업로드 · 실행 → 결과 해석 → 임시 파일 정리 → 애매하면 읽기만 0 · 2 · 5초.
  5. 결과 = `active_same` · `activated` · `failed`(전환 전 실패 · 직전 값 유지) · `unconfirmed`(전환 뒤 확인 불가 · 단정하지 않음).
- **응답**: 기존 `ParamApplyResponse` 에 선택 필드만 더한다(결과 종류 · 비교 n/다른 수 · 확인 시각). **새 API 경로 없음.** 비밀 · SSH 대상 · 원격 경로 · `param_id` 를 싣지 않는다(지금 계약 그대로).
- **동시 실행**: 서버 쪽 잠금 하나(진행 중이면 '적용 진행 중' 응답). 시간 예산은 화면 120초 안(ssh `BatchMode` · `ConnectTimeout`).
- **배포**: PC 코드는 커밋 뒤 바로 쓰인다(개발 서버 · 백엔드 자동 재시작). OCI 는 적용에 pull 이 필요 없다(도구를 적용 때마다 올림 · 쓰는 저장 함수는 OCI 코드 `704d84a1` 에 있음 — §5). 다만 **복구 명령을 OCI 에서 쓰려면** 도구 파일이 OCI 에 있어야 하므로 사용자 pull(거래일 08:05 ~ 15:45 피함) → **Q4**.
- **복구 절차(새 화면 없음 · 판정 §4 보완 — OCI pull 을 기다리지 않는다)**: PC 저장소 루트에서 같은 검증 도구를 기존 SSH/SCP 경로로 임시 업로드해 쓴다.
  1. `scp -o BatchMode=yes scripts/apply_three_push_param_oci.py oci-krx:/home/ubuntu/krx_hyungsoo/state/three_push/params/.apply_three_push_param_oci.py`
  2. `ssh -o BatchMode=yes oci-krx 'cd /home/ubuntu/krx_hyungsoo && venv/bin/python state/three_push/params/.apply_three_push_param_oci.py --list --project-root /home/ubuntu/krx_hyungsoo'`(읽기만 · `*` = 지금 활성 · 버전마다 지금 활성값과 다른 값 수)
  3. 사용자가 고른 버전으로 `ssh -o BatchMode=yes oci-krx 'cd /home/ubuntu/krx_hyungsoo && venv/bin/python state/three_push/params/.apply_three_push_param_oci.py --activate-version <고른 버전 ID> --project-root /home/ubuntu/krx_hyungsoo'` — 검사 → 전환 → 다시 읽기, 마지막 줄 `RESULT {"result": "ACTIVATED" …}`.
  4. `ssh -o BatchMode=yes oci-krx 'rm -f /home/ubuntu/krx_hyungsoo/state/three_push/params/.apply_three_push_param_oci.py'`(정리).
  - OCI pull 뒤에는 상주 명령 `cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/apply_three_push_param_oci.py --list --project-root .` 도 쓸 수 있다.
  - '전환 실패의 DB 롤백'(도구 안 자동 · 이전 값 확인 시에만 FAILED)과 '성공 뒤 사용자가 정책을 되돌리기'(이 명령)를 구분한다. 복구 CLI 는 운영자가 고르도록 버전 ID 를 출력한다(웹 응답 · 화면 비노출은 그대로 · 판정 §4).

## 5. OCI 읽기 전용 확인 결과 (설계 §5-5 · 2026-10-20 · 사용자 승인 · 쓰기 0)

- OCI 코드 `704d84a1`(2026-10-17) · `venv/bin/python` 있음 · DB 파일 있음.
- 저장 함수 `create_param_version` · `activate_param_version` · `read_active_param_dict` · `get_active_pointer` · `flatten_param_dict` · `read_param_version` · `validate_param_dict` · `from_dict` · `read_param_file` 모두 있음.
- cron: `cd /home/ubuntu/krx_hyungsoo && venv/bin/python scripts/run_three_push_runtime_oci.py …`(시장 08:30 · 보유 09:15 / 12:30 / 15:40 · 보유 위험 알림 09:30 ~).
- **DB 활성 PARAM** = `param-20260907T152806-255383`(2026-09-07 · `create_script_approve` · manual_seed) · 버전 수 2 · 값 14개 = 코드 기본값.
- OCI JSON(마지막 전달본) = `param-20261004T020942-999570` = PC 운영 기준 JSON 과 같은 id. **PC 기준 14값 = OCI 활성 14값.**
- → 배포 뒤 첫 적용은 **'일치 · 변경 없음'(새 OCI 버전 0)**이 정상이다(설계 §6 '동일값 확인').

## 6. 격리 시험 방법 (설계 §5-6)

- **OCI 쪽을 PC 와 다른 임시 DB 로**(OPS-04 시험의 임시 home): 버전 A(기본값) 활성 · B(알림 종류 2개 다름).
- **가짜 SSH**: 명령별로 쓰기를 기록하는 라우터(장중 설정 시험 방식). 등록하지 않은 `subprocess.run` 은 실패시킨다(원장 시험 방식).
  - 원격 읽기 문자열은 로컬 bash 로 진짜 실행한다(OPS-04 방식).
  - 도구는 프로세스 안 실행과 `--project-root` 하위 프로세스 실행 둘 다 한다(원격 실행 계약 시험 방식).
- **사례**:
  1. 성공: 포인터 B · 다시 읽은 값 = B · 성공 판정은 다시 읽기로만(종료 코드 0 인데 A 그대로면 성공 아님).
  2. 같은 값: id 만 다른 같은 값 · 순서만 다른 알림 종류 → 버전 수 · 포인터 그대로 · 원격 쓰기 0 · '일치 · 변경 없음'.
  3. 전환 전 실패: 적용 전 읽기 실패 · 업로드 실패 · 검증 실패 · 전환 트랜잭션 실패 → 포인터 A 그대로 · 실패 · 임시 파일 정리.
  4. 전환 뒤 확인 불가: 실제 전환 뒤 응답 끊김 · 다시 읽기 실패 → '확인 불가' · 성공으로도 '기존 값 유지'로도 단정하지 않음 · 자동 되돌림 없음.
  5. 다시 적용: 4 뒤 다시 누르면 먼저 읽어 같으면 쓰기 0 · '일치'.
  6. 복구: `--activate-version A` → 포인터 A · 값 A · 버전 수 그대로.
- **공통 검사**:
  - 원격 명령에 러너 · cron · PUSH 없음.
  - 응답 · 화면에 버전 ID · 경로 · ssh 없음.
  - ① 행은 늘 200 이다.
  - 도구 상수와 정본 목록이 같은지 확인하는 계약 시험을 둔다.
- **화면 시험**: 버튼 이름 · 배지 6종 · 적용 중 버튼 막힘 · 결과 문구 · ① 행 갱신. 기존 시험의 '전달' 문구는 바꾼다. 'OCI 버튼 없음(①)'은 유지한다.
- **기존 검사**: 백엔드 관련 시험 + 전체 회귀 1회(백엔드 변경 있음) · black · flake8 · tsc · eslint · vitest · 변이(사본 폴더).

## 7. 질문

**Q1. 기반 문서와의 관계 + 원격 쓰기 구현 승인**

- **부딪히는 문장**:
  - `PROJECT_ORIGIN_INTENT`(2026-07-07 사용자 확정): "PC 는 … OCI 운영 DB 를 원격으로 직접 열거나 write 하지 않는다" · "PC 에서 계산·승인된 PARAM 은 DB 기반 발행 절차로 OCI 에 반영한다".
  - `ASSUMPTIONS` "OCI 계속 금지: … PARAM 생성/승격".
  - `KILL_SWITCHES` KS-11 "유지되는 금지: … PARAM 생성·승격".
- **선택지**:
  - **(a) 권장** — 설계 그대로 하되 '**PC(사용자)가 작성 · 승인한 PARAM 값을 OCI 쪽 짧은 도구가 그대로 DB 에 발행**'으로 읽는다.
    - PC 는 OCI DB 를 직접 열지 않는다.
    - OCI 는 값을 만들거나 고르지 않는다. 버튼을 누를 때만 기록 · 전환 · 확인한다.
    - 장중 설정(2026-09 사용자 적용 · OCI 쪽 도구가 OCI DB 를 씀)과 같은 해석이다.
    - 지금의 수동 활성화(OCI 가 코드 기본값으로 새 PARAM 생성)보다 'PC 승인값 발행'에 더 가깝다.
    - 기반 문서 문구는 바꾸지 않는다(필요하면 설계자 해석 주석).
  - **(b)** 기반 문서 문장을 먼저 개정해 명시적으로 허용한다(설계자 · 사용자 결정 후 진행).
- **사용자 승인 필요**: POC5-25 판정 §3 이 '개발 대상 선정'과 '원격 쓰기 구현 승인'을 나눴다. 'PC 버튼이 OCI 운영 DB 활성 PARAM 을 바꾸는 원격 쓰기 경로'를 이번에 만드는 것을 사용자가 승인해야 한다.
- **사용자 결정(2026-10-20)**: '승인 · PLAN 권장 방식' — 버튼을 누를 때만 먼저 OCI 실제값을 읽고 다를 때만 바꿔 다시 읽어 확인하며, PC 는 OCI DB 를 직접 열지 않는다. 기반 문서 해석((a) / (b))은 설계자 판단에 맡긴다.

**Q2. 중복 발송 키에 `param_id` 가 들어 있다**(`registry_key.py:14-31` · `push_kind::param_id::날짜(+칸)`)

- 값이 다른 기준을 낮에 활성화하면 새 `param_id` 가 되어, 그날 이미 보낸 칸의 키가 달라진다.
- **정상 일정(칸마다 하루 1번)에는 적용만으로 추가 발송이 생기지 않는다.** 같은 칸을 **손으로 다시 돌릴 때만** 중복을 막지 못한다.
- 같은 값이면 새 버전을 만들지 않으므로 키는 그대로다(지금 OCI = PC 14/14).
- **선택지**:
  - **(a) 권장** — 러너를 그대로 두고 결과서 한계로 기록한다.
  - **(b)** 러너 중복 키에서 `param_id` 를 뺀다. 러너 · 원장 키가 바뀌고 OCI pull 이 필요해 이번 범위 밖이므로 별도 설계가 필요하다.

**Q3. ① '운영 기준 활성' 행 갱신**

- 설계 §2 는 '응답 뒤 실제 활성값 확인 결과로 일치 / 다름 / 확인 불가 갱신'을 요구한다. 기존 POC3-07 Q2(OCI 조회 = 기동 때 1번만) · Q3(적용 결과는 그 요청 응답에만)와 맞춰야 한다.
- **선택지**:
  - **(a) 권장** — 적용 요청 **안에서** 읽은 OCI 활성값(적용 전 읽기 · 적용 뒤 다시 읽기)을 그 응답에 싣고, 같은 값으로 ① 행 캐시도 바꾼다.
    - 별도 OCI 재조회 · 폴링 · 새로고침 읽기는 없다.
    - 행 끝에 '기동 때 / 적용 때 확인 시각'을 붙이고, ① 아래 안내 한 줄을 고친다.
  - **(b)** ① 은 기동 때 값 그대로 두고, 결과는 ② 카드에만 보인다.

**Q4. OCI 쪽 도구 배치**

- **(a) 권장** — 적용 때마다 임시 업로드 · 실행 · 삭제한다(장중 설정과 같음 · 적용에 OCI pull 불필요).
  - 같은 파일을 저장소 `scripts/` 에도 둔다.
  - 복구 · 목록 명령은 사용자가 다음 OCI pull 뒤 OCI 에서 쓴다.
- **(b)** OCI 에 상시 배포한 도구만 쓴다(첫 적용 전에 OCI pull 필요).

## 8. 목업 (로컬 · 게시 안 함)

- 「OCI 운영·적용」 **전체 화면 1440 · 1000px**: 지금 / 바꾼 뒤.
- **6상태**:
  1. 일치 · 변경 없음
  2. 값 다름(적용 전)
  3. 적용 중
  4. 적용 완료
  5. 적용 실패
  6. 확인 불가
- 저장소 밖 사본 + 가짜 응답(사용자 백엔드 조회 응답을 읽기만 해 바탕으로 씀)으로 그렸다. 실제 OCI 활성값은 바꾸지 않았다.
- **카드 배치는 지금과 같다**(적용 기준 · 마지막 적용 · 결과 줄 + 버튼 하나).
  - 바뀌는 것: 버튼 '현재 기준 OCI 적용' · 배지 · 결과 문구 · 짧은 안내 한 줄('OCI 러너가 이후 실행에서 읽는 기준을 적용합니다. 이미 시작한 실행은 그때 읽은 기준으로 끝납니다.').
  - 차이는 ① 행(기존 비교 영역)에 '14개 중 n개 다름 · 묶음별 수'로 보인다.
- **예전 '전달' 기록**(10-04 11:09)은 '미적용'으로 단정하지 않고 **'이전 전달 기록 · 활성화 확인 없음'**(회색 배지)으로 보인다(판정 §5 정정 · 같은 자리 문구 · 목업 재확인 없음).

**사용자 목업 확인(2026-10-20)**: '확인함 · 그대로'.

## 9. 설계자 판정 반영 (2026-10-20 · 판정 원문 `docs/ai_design/POC5/POC5-27_PC_TO_OCI_RUNTIME_PARAM_ACTIVATION_PLAN_DECISION_2026-10-20.md`)

- **PASS · Q1 ~ Q4 모두 (a)** + 같은 구현의 보완. PLAN 재제출 · 목업 재확인 · 원격 쓰기 승인 재요청 없음.
- **Q1**: 'PC 승인값의 DB 발행'으로 한정한다. 기반 문서 3곳(PROJECT_ORIGIN_INTENT · ASSUMPTIONS · KILL_SWITCHES)의 금지 원문은 보존하고, 판정 원문의 2026-10-20 주석을 그 바로 아래에 붙였다(별도 개정 Step 없음).
- **Q2**: 러너 · 원장 · `registry_key` 는 바꾸지 않는다. 값이 다른 PARAM 으로 바꾼 날 같은 칸을 손으로 다시 돌릴 때의 중복 가능성은 결과서 · 복구/점검 절차에 남긴다. 적용 자체가 발송 · 러너 재실행을 하지 않는 경계를 시험한다. 같은 유효값이면 OCI 새 버전 · 포인터 변경이 없다(PC 의 기존 생성 · 이력은 그대로 쓴다).
- **Q3**: 적용 요청 안에서 얻은 실제 활성값 · 확인 시각을 응답과 ① '운영 기준 활성' 캐시에 함께 반영한다(그 행만). 확인 불가면 그 상태를 ① 에도 보인다. 읽지 않은 값 · 시각은 채우지 않는다. 200 과 '일치'는 다르다.
- **Q4**: 임시 업로드 방식이다. 복구는 다음 OCI pull 을 기다리지 않도록 §4 의 임시 업로드 명령으로 바꿨다(격리 루트에서 그대로 실행해 확인).
- **§5 보완(구현에 반영)**:
  - sync 결함 4건을 고쳤다: 확인 뒤 교체 · 확인 누락 = 실패 · 전체 예산 105초 < 120초 · 서버 적용 잠금 하나.
  - 후보는 DB 에서 다시 만들어 `from_dict` 와 요청 유효값 비교를 통과해야 전환한다. 빈 정책을 기본값으로 채우지 않는다.
  - 도구 실행을 시작한 뒤 결과를 모르면 기존 값 유지로 단정하지 않는다. 0 · 2 · 5초 읽기는 같은 예산 안에서만 하고, 요청값이 읽힐 때만 적용 완료로 본다. 자동 쓰기 재실행 · 역전환은 없다.
  - 정상적으로 읽은 값이 요청과 다르면 되돌리고, **이전 값까지 확인될 때만** FAILED 다. 되돌림 실패 · 미확인은 unconfirmed 다.
  - PC 코드 기본 14값 생성 방식은 유지한다.
  - 예전 전달 기록은 '이전 전달 기록 · 활성화 확인 없음'으로 보인다.
