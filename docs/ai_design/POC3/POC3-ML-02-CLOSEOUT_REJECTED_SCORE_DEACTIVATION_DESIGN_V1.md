# POC3-ML-02 REJECT Closeout — 개발플랜 작성 지시

- **작성**: 설계자
- **수신**: 개발자
- **수신일**: 2026-08-29
- **성격**: **설계자 지시문**(개발자 입력). §1 이하는 설계자 원문 그대로.
- **개발자 회신**: `docs/ai_plan/POC3/POC3-ML-02-CLOSEOUT_REJECTED_SCORE_DEACTIVATION_PLAN_V1.md`
- **선행**: `docs/ai_result/POC3/POC3-ML-02_RELATIVE_UPSIDE_SCORE_VALIDITY_GATE_RESULT.md`
  (Step `PASS` · 검증자 `VERIFIED` · 모델 `REJECT` 확정 · 커밋 `ad42bb88`)
- **게이트**: `next_gate = REJECTED_SCORE_DEACTIVATION`

---

## 0. 선행 판정 요약 (POC3-ML-02 종료 상태)

```text
step_status       = PASS
verification      = VERIFIED
model_verdict     = REJECT
model_scope       = relative_upside_v0
ui_action         = DEACTIVATE_AND_HIDE
oci_push_impact   = NONE
next_gate         = REJECTED_SCORE_DEACTIVATION
```

---

## 1. 설계자 지시문 (원문)

> 문서 3개의 커밋·푸시는 사용자 승인에 따라 진행한다.
>
> 다음 작업은 `relative_upside_v0`의 신규 개발이나 삭제가 아니라, REJECT 판정을 실제 판단 화면에 반영하는 UI closeout이다.
>
> ## 1. 확정 계약
>
> ### API
>
> * `GET /market/topn/latest`의 `relative_upside_score`와 `relative_upside_reasons` 필드는 유지한다.
> * API 스키마와 백엔드 모델 생성·저장 코드는 변경하지 않는다.
> * 필드는 연구 재현과 기존 계약 보존용이며 현재 판단 UI에서는 소비하지 않는다.
>
> ### 후보·판단 화면
>
> * `CandidateTable`과 `JudgmentWorkbench`에서 참고점수와 사유를 표시하지 않는다.
> * 참고점수를 이용한 재정렬을 완전히 제거한다.
> * 판단 워크벤치 정렬 드롭다운에서 `참고점수` 선택지를 제거한다.
> * 비활성 선택지, 0점, `사용 불가`, 경고 배지 등으로 대체하지 않는다.
> * API가 반환한 원래 후보 순서를 그대로 보존한다.
> * 점수 값의 존재·부재·크기가 화면 순서에 영향을 주지 않아야 한다.
>
> ### ML 화면
>
> * 좌측 ML 화면과 수동 실행 기능은 연구용 baseline으로 유지한다.
> * 해당 영역에 `relative_upside_v0`, `REJECT`, `연구용 baseline이며 투자 판단에 사용하지 않음`을 명시한다.
> * 자동 실행, 스케줄러, 후보 화면 연결은 추가하지 않는다.
> * 다른 운영 화면에는 이 상태 문구나 점수를 노출하지 않는다.
>
> ## 2. 변경 금지
>
> * OCI·PUSH·cron
> * API 응답 계약
> * DB 및 ML feature/model artifact
> * 모델 재학습·튜닝
> * 신규 대체 모델
> * `compute_topn(asof=...)` 결함 수정
> * 점수 평가 코드와 기존 증거 삭제
>
> ## 3. 개발플랜에 포함할 것
>
> * 현재 참고점수를 소비하는 프론트엔드 위치 전체
> * 제거되는 표시·정렬 로직
> * 유지되는 API·ML 연구 경로
> * 변경 예상 파일
> * 다음 계약을 고정하는 테스트
>
> 검증 계약:
>
> 1. 후보표와 판단 워크벤치에 점수·사유가 보이지 않는다.
> 2. `참고점수` 정렬 선택지가 존재하지 않는다.
> 3. 동일 후보 응답에서 점수만 변경하거나 제거해도 화면 순서가 같다.
> 4. 화면 순서는 API 후보 순서와 일치한다.
> 5. ML 연구 화면의 수동 실행은 유지되며 REJECT·연구용 표시가 보인다.
> 6. API·OCI·PUSH·cron 변경이 없다.
>
> ## 4. 진행 절차
>
> 이번에는 구현하지 말고 짧은 개발플랜만 제출한다.
>
> 개발플랜의 계약을 설계자와 레드팀이 확인한 뒤 구현한다. 구현 후에는 검증자 검증과 사용자 실제 화면 확인을 모두 통과해야 closeout을 종료한다.
>
> 이 closeout이 끝나기 전에는 신규 ML 모델이나 다음 기능 Step을 시작하지 않는다.
