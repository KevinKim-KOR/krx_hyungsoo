# POC3-02C-OPS-01 종료 · 다음 챕터 진입 — 2026-09-18

- **작성**: 개발자(VSCode Claude) · **독자**: 다음 세션 개발자
- **상태**: 검증자 VERIFIED(`685de1c4`) 후 운영 결함 2건 수정 · **OCI 배포·적용 완료**
- **최종 갱신**: 2026-09-19 (배포 후 실측으로 교체)

```text
로컬 / GitHub / OCI   2f341deb  (세 지점 동일)
OCI active            intraday-20260916T144047-642949 · 27개 사업군 · 기준일 2026-09-11
PC / OCI hash         76a7652c29edbdcc…  일치
sync                  deployed / verify ok · action_state = None
```

---

## 1. 이 챕터에서 만든 것

PC 가 사업군·대표 ETF 를 자동 산출 → 사용자가 버전 전체 승인 → OCI 전달.
**설정을 만들고 보내는 것까지**이고, 장중 알림 발송은 다음 단계(`OPS-02`)다.

```text
app/intraday_config/   schema · selector · store · generator · startup
app/api_intraday_config.py            state · approve-and-apply · reject
scripts/sync_intraday_config.py       PC→OCI 전달 사슬
scripts/apply_intraday_config_oci.py  원격 적용 (일시 업로드 후 삭제)
state/intraday_config/token_dictionary_v1.json   사업군 토큰 사전 (번들 데이터)
frontend/.../IntradayConfigCard.tsx   「장중 급등락 설정」 카드
```

함께 담은 것: **정기 PUSH 콘텐츠 동일 억제 해제**(`POC3-02B-OPS-03`).

---

## 2. 반드시 알아야 할 계약 5개

### 2-1. 조치 대상은 **최신 미기각 버전 하나뿐**

```sql
SELECT * FROM intraday_alert_config_version
 WHERE rejected_at IS NULL ORDER BY created_at DESC LIMIT 1
```

최신본이 active 면 `(None, None)` — 할 일 없음. "active 가 아닌 승인본" 을 물으면
v1 배포 후 v2 배포 시 **v1 이 재배포 대상으로 되살아난다**(검증자 r2).

### 2-2. 승인은 멱등 · 승인 API 는 최신본만 받는다

재시도도 `approve-and-apply` 를 쓴다. 무조건 `approve()` 하면 재시도마다
`approved_at` 이 새로 찍힌다. 그리고 요청 버전이 현재 조치 대상이 아니면 **409** —
화면을 오래 열어두면 옛 설정이 OCI 로 나간다(검증자 r3).

### 2-3. precheck 은 **원격에 쓰기 전에**

```text
승인확인 → ssh → precheck(_remote_active) → export → scp → mv → scp → apply
                 ↑ 여기서 실패하면 원격에 아무것도 안 쓴다
```

업로드 뒤 실패 경로는 전부 `fail_after_upload()` → `cleanup()` 을 거친다.
**맨 `fail()` 을 쓰면 안 된다** — 역검증 ㉖ 이 구간을 검사한다.

### 2-4. 원격 적용 결과 3종 (설계자 승인 2026-09-18)

```text
deployed              목표 version/hash 확인
remote_apply_failed   직전 version/hash 확인
deploy_unconfirmed    조회 3회(0s/2s/5s) 모두 실패 또는 예상 밖
```

`deploy_unconfirmed` 는 **완료도 실패도 아니다.** 화면은 「OCI 적용 여부 확인
필요」. 자동 재적용 금지(`AUTOMATIC_REAPPLY = FORBIDDEN`). UI 에서
`isUnconfirmed` 가 `isRetry` 보다 **우선**이다 — 둘 다 참이 될 수 있다.

### 2-5. 정기 PUSH 는 내용이 같아도 보낸다

```text
정기(시장 브리핑·보유 브리핑 3슬롯)  거래일·슬롯마다 발송
사건형(보유 급락 알림 7틱)           동일 위험 억제 유지
```

fingerprint 는 살아 있다 — 용도가 "발송 차단" 에서 "기록·비교" 로 바뀌었다.
중복 차단은 원래부터 `registry_key` 가 한다.

---

## 3. 지금 상태 · 다음에 할 일

### 3-1. OCI 배포 완료 (2026-09-18 · 사용자 실행)

```text
로컬 / GitHub / OCI   2f341deb
```

pull 로 발송 규칙이 바뀌었다 — **하루 고정 4건**(시장 브리핑 1 + 보유 브리핑 3).
이전에는 내용이 같으면 빠져 실측 약 44% 만 발송됐다.

### 3-2. 배포 직후 터진 결함 2건 (해소)

`git pull` 후 두 버튼이 모두 실패했다. 둘 다 **원격에서 실행해야만** 드러난다.

| 버튼 | 원인 | 수정 |
|---|---|---|
| 장중 급등락 설정 | 업로드 위치에서 `parents[1]` 이 루트가 아님 | `--project-root` 필수화 |
| 현재 운영 기준 | `verify` 복제 목록에 `holdings_risk_alert` 누락 (기존 결함, `5d2614d6` 부터) | 복제본 갱신 + 정본 일치 테스트 |

`3b0bee0d` 로 고쳐 재배포했고 **두 버튼 모두 성공**했다. 임시 스크립트도
정리됐다(`.apply_intraday_config_oci.py` 삭제 확인 — `cleanup()` 실동작).

**잔존 파일은 0건이다.** `latest_intraday_alert_config.json` 은 정상 배포된
전송 파일이지 잔존물이 아니다.

### 3-3. 다음 작업 = `POC3-02C-OPS-02`

설계서 §12-6 은 "정기 PUSH 억제 수정을 이어서" 라고 적었지만 **그건 이번
제출에 이미 포함돼 검증까지 끝났다**(결과서 §11). 실제 다음은 장중 급등락 알림
구현이다. 이 어긋남을 설계자에게 알려야 한다.

`intraday_alert_policy.enabled = false` 이고 임계·cooldown·상한이 비어 있다.
그 수치를 정하는 것이 `OPS-02` 다.

---

## 4. 검증 9라운드에서 나온 교훈

반려 사유가 매번 "고친 것 옆칸" 이었다. 자세한 분석은
`feedback_verify_contract_not_diff` 메모리에 남겼다. 요지만 적는다.

```text
상태 계약을 고치면   상태 × 전이 표를 그리고 빈 칸을 찾는다 (단일 사례 금지)
"X 안 한다" 주장은   실행 순서를 위에서 읽어 첫 X 지점을 찾는다
테스트는             diff 가 아니라 계약 문장에서 쓴다
가드는               무력화해 EXIT=1 이 나오는지 실증한다
수치는               새 절에 옮길 때 재측정한다
```

---

## 5. 재현 명령

```bash
.venv/bin/python -m pytest tests/ -q                      # 1,687 passed
.venv/bin/python scripts/ops02c/reverse_verify_guards.py  # 26가드 EXIT=0
cd frontend && npx vitest run                             # 18 files / 207 tests
```

결과서: `docs/ai_result/POC3/POC3-02C-OPS-01_PC_AUTO_PARAM_DELIVERY_RESULT.md`
설계서: `docs/ai_design/POC3/POC3-02C_INTRADAY_DECISION_BRIEFING_DESIGN_V1.md`
