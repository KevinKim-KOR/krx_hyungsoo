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
- 현재 결정: 타임아웃/복구 로직은 구현하지 않음. DELIVERING 은 단순 진행 상태로 두고 비정상 종료 시 수동 개입 가정. 프론트 polling 은 약 45초 후 자동 중단하며 "상태 새로고침" 안내만 노출
- 재검토 예정: POC 완료 후 운영 안정화 단계
- 트리거: 외부 전달 중 서버 크래시/네트워크 단절로 DELIVERING 이 장시간 고정되는 사례가 나올 때

---

# Step 3 — Next.js 프론트 도입 시 추가된 DEFERRED

## DEFERRED: Next.js UI 세분화 / 컴포넌트 구조 정리
- 발생 맥락: Step 3 최소 구현 — 승인 루프를 단일 `ApprovalLoopClient.tsx` 로 처리
- 현재 결정: 입력 폼 / 상태 표시 / 초안 본문 / 다음 행동 섹션이 한 컴포넌트에 있음. 상수/유틸 최소 분리만 수행
- 재검토 예정: 화면 수 2개 이상으로 늘거나 같은 상태 표현이 여러 뷰에서 반복될 때
- 트리거: 주요 컴포넌트 한 파일이 ~400 라인을 넘고 코드 리뷰 스캔이 어려워지는 시점

## DEFERRED: 전역 상태 관리 라이브러리 도입
- 발생 맥락: Step 3 — `useState` / `useRef` 만 사용, Redux/Zustand 미도입 (DEV_RULES 절대 금지 6번)
- 현재 결정: 단일 화면 + 단일 run 상태이므로 로컬 컴포넌트 상태로 충분
- 재검토 예정: 여러 화면에서 같은 run 을 공유해야 하거나 인증/권한 상태가 도입될 때
- 트리거: prop drilling 3 단계 이상이 상시화 되거나, 다중 run 동시 진행 화면이 생길 때

## DEFERRED: 상세 에러 UX 개선
- 발생 맥락: Step 3 — 네트워크 실패/서버 오류는 단일 에러 배너에 raw detail 노출
- 현재 결정: 상태 구분은 최소 (loading / errorMsg / run.status). 과한 에러 분류 금지 (DEV_RULES D항)
- 재검토 예정: 사용자가 "어떤 오류인지 알 수 없다" 피드백을 낼 때
- 트리거: 동일 원인의 에러가 사용자 체험에 반복되는데 대처법이 다를 때 (예: 네트워크 vs 서버 500 vs 계약 오류)

## DEFERRED: 수동 새로고침 시 run_id 유실 방지
- 발생 맥락: Step 3 레드팀 MINOR 지적 — `useState` 로만 run_id 를 보관하므로 브라우저 F5 시 현재 진행 중인 루프 화면이 소실됨
- 현재 결정: 이번 단계에서는 구현하지 않음. URL Query Parameter 또는 localStorage 중 어느 쪽을 쓸지 결정하지 않음
- 재검토 예정: Step 3 실사용 직후 (최우선 DEFERRED)
- 트리거: 사용자가 실제로 새로고침 후 "내 run 이 사라졌다" 를 1회라도 경험했을 때. 해결 방향: `/runs/{run_id}` URL 또는 `localStorage["last_run_id"]` 중 단순한 쪽 선택

## DEFERRED: 운영용 화면 분리 (POC2 이후)
- 발생 맥락: POC1 은 단일 승인 루프 화면 하나로 정의됨
- 현재 결정: 대시보드 / run 목록 / 히스토리 / 설정 같은 별도 화면 만들지 않음
- 재검토 예정: POC2 단계 진입 시
- 트리거: 운영 중 "지난 run 들을 한 번에 보고 싶다" / "여러 사용자 구분이 필요하다" 등 요구가 누적될 때

## DEFERRED: 인증 / 사용자 구분
- 발생 맥락: POC1 — 단일 사용자 전제 (혼자 쓰는 프로젝트, PROJECT_ORIGIN_INTENT)
- 현재 결정: 인증/세션/권한 체계 없음. CORS 도 개발용 origin 만 허용
- 재검토 예정: 와이프/친구에게 공유 시점 또는 여러 단말기에서 접속 필요 시점
- 트리거: "내 run 과 다른 사람 run 을 구분해야 한다" 가 명시 요구로 들어올 때

## DEFERRED: 스타일 시스템 / 컴포넌트 라이브러리 도입
- 발생 맥락: Step 3 — shadcn/ui / MUI / Tailwind 미도입 (DEV_RULES 절대 금지 7번)
- 현재 결정: `frontend/app/globals.css` 단일 CSS 파일로 최소 스타일 유지
- 재검토 예정: 화면이 복수 개가 되고 공용 컴포넌트 시각 통일이 필요해질 때
- 트리거: CSS 중복이 3곳 이상 발생하거나, 디자인 일관성 이슈가 사용자 피드백으로 올 때

## DEFERRED: 실제 운영 배포 구조 통합
- 발생 맥락: Step 3 — dev 환경 분리 기동(3000 + 8000)만 구성
- 현재 결정: 리버스 프록시 / 단일 entry / 정적 빌드 호스팅 결정 보류. CORS 는 dev origin 만 허용
- 재검토 예정: shadow 또는 live-lite 리허설 단계
- 트리거: 배포 대상 환경(PC 상주 / 클라우드 / OCI) 이 확정될 때

## DEFERRED: polling 제거 또는 대체 실시간 갱신 방식 재검토
- 발생 맥락: Step 3 DELIVERING 갱신용 1.5초 간격 polling, 최대 ~45초
- 현재 결정: WebSocket/SSE 도입 금지 (DEV_RULES 절대 금지 11번). 제한적 polling + 수동 새로고침 버튼 유지
- 재검토 예정: 외부 전달 시간이 자주 수 분 단위로 길어지거나 사용자가 polling 빈도 체감 이슈를 보고할 때
- 트리거: DELIVERING 평균 소요 시간이 polling 총 감시 시간을 초과하는 경우가 반복될 때

## DEFERRED: ML 기반 draft 생성기 교체 (중복 항목 통합)
- 이미 상단 "DEFERRED: ML 기반 초안 생성 연결" 에 포함됨. Step 3 에서도 동일 판단 유지 (sample_draft stub 그대로, 실제 ML 연결 안 함).
