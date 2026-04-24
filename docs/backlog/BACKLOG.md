# BACKLOG

POC 1단계에서 의도적으로 뒤로 미룬 항목. 지금 구현하지 않음. 재검토 트리거가 발생했을 때만 꺼낸다.

각 항목은 다음 포맷을 따른다: 발생 맥락 / 현재 결정 / 재검토 예정 / 트리거.

---

## DEFERRED: 실패 상태 세분화 (DRAFT_FAILED / PUSH_FAILED / ALERT_FAILED)
- 발생 맥락: S1 설계 (이벤트/액션 설계) — FAILED 단일 상태로 출발
- 현재 결정: 지금은 FAILED 하나로 시작. 원인 구분은 로그로만 확인
- 재검토 예정: POC 완료 후 운영 중 복구 액션이 상황별로 달라져야 할 때
- 트리거: 실패 상황에서 사용자/시스템이 "어느 단계에서 실패했는가" 에 따라 다른 조치가 필요해질 때

## DEFERRED: 부분 재시도 정책 (Retry Push / Retry Alert)
- 발생 맥락: POC 1단계 — 재시도 금지, 새 run_id 로만 새 초안 생성
- 현재 결정: 실패한 run 은 재사용하지 않고 GenerateDraft 를 다시 실행
- 재검토 예정: POC 완료 후 외부 전달 실패가 잦고 초안이 무거워 재생성 비용이 부담될 때
- 트리거: 외부 전달만 재시도하면 복구 가능한 일시적 장애 빈도가 일정 수준을 넘을 때

## DEFERRED: 운영 필드 확장 (approved_at / rejected_at / error_code / error_message)
- 발생 맥락: 최소 데이터 계약을 run_id / asof / status / draft_payload 4개로 고정
- 현재 결정: 시각/에러 메시지는 서버 로그로만 남기고 데이터 모델에는 추가하지 않음
- 재검토 예정: 운영 리뷰/SLA 지표가 필요해졌을 때
- 트리거: "언제 승인됐고 왜 실패했는지" 를 UI/보고서에서 조회하는 요구가 반복해 발생할 때

## DEFERRED: 추적 필드 (holdings_snapshot_ref / market_data_snapshot_ref)
- 발생 맥락: 재현성/감사 추적이 POC 1단계 범위 밖
- 현재 결정: 스냅샷 참조를 따로 저장하지 않음. 재현은 run 자체의 draft_payload 에만 의존
- 재검토 예정: 추천 결과의 재현성 요구가 생겼을 때
- 트리거: "이 run 은 어떤 데이터로 만들었나" 를 사후 재현해야 하는 케이스가 나올 때

## DEFERRED: spike_watch / holding_watch 연계
- 발생 맥락: 다른 알림 파이프라인과의 통합은 POC 1기능 범위 밖
- 현재 결정: 단일 초안 승인 루프만 구현. 연동 지점 없음
- 재검토 예정: POC 1단계 승인 루프가 안정 동작 확인된 후
- 트리거: 복수 알림 경로에서 같은 승인 루프를 공통으로 써야 하는 순간

## DEFERRED: ML 기반 초안 생성 연결
- 발생 맥락: draft.py 는 현재 정적 stub payload 반환
- 현재 결정: backup/backtest/ml/predictive_risk_classifier.py 는 격리 보관. POC 루프에 연결하지 않음
- 재검토 예정: POC 1단계 루프가 완주 가능하다고 확인된 다음
- 트리거: 승인 루프 자체가 안정되고, 초안 내용 품질이 병목으로 드러날 때 (Q1: factor 추가 난이도 측정)

## DEFERRED: DELIVERING 상태 타임아웃 / orphan 처리
- 발생 맥락: POC 1단계 최소 상태 모델 — DELIVERING 은 Approve 요청과 동일 프로세스 안에서 종료 상태로 전이되도록 설계
- 현재 결정: 타임아웃/복구 로직은 구현하지 않음. DELIVERING 은 단순 진행 상태로 두고 비정상 종료 시 수동 개입 가정
- 재검토 예정: POC 완료 후 운영 안정화 단계
- 트리거: 외부 전달 중 서버 크래시/네트워크 단절로 DELIVERING 이 장시간 고정되는 사례가 나올 때
