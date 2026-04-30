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

---

# Step 3 (POC1 OCI 실연결) 시 추가된 DEFERRED

## DEFERRED: OCI handoff artifact 형식 고도화
- 발생 맥락: Step 3 실 OCI 전달 — 설계자 결정 기본 규약(run_id/asof/draft_payload/approved_at) 만 사용
- 현재 결정: 4 필드 고정. 스키마 버전 / 서명 / Idempotency 키 / 분류 메타 등 추가 안 함
- 재검토 예정: handoff 충돌·중복·재배포가 운영 중 1건이라도 발생할 때
- 트리거: OCI consumer 가 같은 run_id 를 두 번 처리하거나, 다양한 알림 종류를 구분해 라우팅 해야 할 때

## DEFERRED: 알림 재시도 정책
- 발생 맥락: Step 3 — Telegram 발송 실패 시 OCI consumer 가 outbox 에 status=FAILED 로 한 번만 기록
- 현재 결정: 자동 재시도 없음. 새 run_id 로만 재시도 (POC1 부분 재시도 금지 정책 연장)
- 재검토 예정: Telegram 일시 장애로 인한 수동 재시도가 반복될 때
- 트리거: Telegram API 5xx / 429 빈도가 사용자 체감 수준에 도달할 때

## DEFERRED: OCI 측 처리 timeout / orphan 대응
- 발생 맥락: Step 3 — daily_ops cron 은 09:05 KST 1회 + 사용자 1회 수동 실행 허용. inbox 의 orphan 파일 정리 로직 없음
- 현재 결정: inbox 에 들어간 artifact 는 다음 cron / 수동 실행 때 처리. 무기한 대기는 frontend polling 한도(약 6분) 가 사용자에게 안내
- 재검토 예정: cron 누락이나 OCI 다운으로 inbox 적체가 발생할 때
- 트리거: inbox/*.json 파일 수가 24시간 이상 N개 이상 잔존하는 사례

## DEFERRED: 전달 결과 대시보드 분리
- 발생 맥락: Step 3 — 단일 승인 루프 화면에서 최종 status 만 노출
- 현재 결정: 별도 운영 대시보드(누적 처리량, 실패율, Telegram 응답 코드 등) 구축 안 함
- 재검토 예정: POC2 또는 운영 안정화 단계
- 트리거: "어제 몇 건 처리됐고 실패는 몇 건이냐" 가 정기 리뷰에 들어올 때

## DEFERRED: Telegram 외 복수 알림 채널
- 발생 맥락: Step 3 — Telegram 단일 채널만 사용
- 현재 결정: Slack/Discord/Email 등 추가 채널 없음
- 재검토 예정: 와이프/친구 등 비-Telegram 사용자 공유 필요 시
- 트리거: Telegram 미사용자가 결과를 받아야 하는 요구가 발생할 때

## DEFERRED: ML 기반 실제 초안 생성기 연결 (Step 3 재확인)
- 발생 맥락: Step 3 — sample_draft.py 가 여전히 stub. 사용자 직접 입력만 사용
- 현재 결정: backup/backtest/ml/predictive_risk_classifier.py 를 POC1 루프에 연결하지 않음
- 재검토 예정: ASSUMPTIONS Q1 (factor 추가 10줄 이내 가능?) 검증 시점
- 트리거: 사용자가 매일 직접 입력하는 부담을 운영 중 호소할 때

## DEFERRED: polling 제거 또는 대체 실시간 갱신 방식 재검토 (Step 3 재확인)
- 발생 맥락: Step 3 OCI cron 비동기 소비 구조 — DELIVERING polling 1.5s → 12s 로 완화
- 현재 결정: 12초 × 30회 ≈ 6분 감시 후 자동 중단 + 수동 새로고침. WebSocket/SSE 미도입
- 재검토 예정: cron 평균 처리 시간이 polling 한도를 초과하거나 사용자 체감 지연이 보고될 때
- 트리거: DELIVERING 6분 자동 중단이 일상화될 때

## DEFERRED: DELIVERING 느린 polling 고도화
- 발생 맥락: Step3 실제 OCI 전달 검증
- 현재 결정: DELIVERING 상태에서는 10~15초 느린 polling + 수동 새로고침으로 단순 운영
- 재검토 예정: POC1 종료 후 운영 안정화 단계
- 트리거: cron 주기 증가, 대기 시간 증가, 불필요한 상태 조회 부하가 관찰될 때

---

# POC2 Step 1 (holdings 기반 draft 생성) 시 추가된 DEFERRED

## DEFERRED: holdings 스키마 확장 (평균단가 외 필드)
- 발생 맥락: POC2 Step 1 — 입력 필드를 ticker/quantity/avg_buy_price + name(선택) 으로 제한
- 현재 결정: 계좌 구분, 매입일자, 메모, 거래소 코드 등 추가 필드 미도입
- 재검토 예정: 운영 사용 중 동일 종목 여러 계좌 / 여러 매수 시점 분리가 필요해질 때
- 트리거: 사용자가 "같은 종목을 여러 행으로 나눠 입력하고 싶다" 는 요구를 제기할 때

## DEFERRED: holdings 자동 불러오기 (브로커 API / CSV import)
- 발생 맥락: POC2 Step 1 — 사용자가 행 단위로 직접 입력
- 현재 결정: 자동 import 미구현. 직접 입력만 사용
- 재검토 예정: 보유 종목 수가 10개 이상 / 매일 갱신 부담이 사용자 체감으로 올 때
- 트리거: KIS API / 증권사 OpenAPI / CSV 업로드 요구가 명시될 때

## DEFERRED: Naver Finance 등 종목명 자동 조회
- 발생 맥락: POC2 Step 1 — 종목명은 사용자 직접 입력 (선택). 미입력 시 ticker 표시
- 현재 결정: 외부 API 호출 미도입. 사용자가 종목명을 알아서 채움
- 재검토 예정: 보유 종목 수가 늘어나 ticker 만으로 식별이 어려워질 때
- 트리거: 사용자가 "종목명 자동 채워줘" 요구 또는 ticker 오타로 인한 잘못된 보유 입력이 반복될 때

## DEFERRED: 현재가 / 평가금액 / 평가손익 / 수익률 / 현재가 기준 비중
- 발생 맥락: POC2 Step 1 — 매입금액과 매입금액 기준 비중까지만 계산
- 현재 결정: 시세 데이터 연결 미도입. 평가지표 0건
- 재검토 예정: holdings 가 안정 운영되고 사용자가 "지금 평가금액 / 손익 보고 싶다" 가 명시될 때
- 트리거: 시세 데이터 소스 결정 (pykrx / KIS / Naver / yfinance 중 어떤 것을 쓸지)

## DEFERRED: 추천 로직 / 정렬 로직 / score 도입
- 발생 맥락: POC2 Step 1 — recommendations 의 action 은 모두 HOLD, score 필드 없음
- 현재 결정: 보유 현황 그대로 출력. 추천/정렬 안 함. 매수/매도 판단 안 함
- 재검토 예정: ML 연결 단계 또는 factor 추가 시점
- 트리거: 사용자가 "내 보유 종목 중 매도 후보를 표시해 달라" 같은 요구를 제기할 때

## DEFERRED: ML 기반 draft 생성기 연결 (POC2 Step 1 재확인)
- 발생 맥락: 상단 "ML 기반 초안 생성 연결" 과 동일. POC2 Step 1 에서도 보류
- 현재 결정: backup/backtest/ml/predictive_risk_classifier.py 연결 안 함. 단순 holdings stub 만 사용
- 재검토 예정: 보유 종목 기반 흐름이 안정화된 후 ASSUMPTIONS Q1 (factor 추가 10줄 이내) 검증 시점
- 트리거: 사용자가 "추천 점수 / 위험도 / factor" 요구를 제기할 때

## DEFERRED: 샘플 입력 폼 완전 제거
- 발생 맥락: POC2 Step 1 — 샘플 입력은 접힘 섹션 + 고정 샘플 1버튼으로 격하했으나 유지
- 현재 결정: 개발/테스트 편의 위해 보존. 운영 입력 아래 접힘 섹션에 위치
- 재검토 예정: 운영 입력만으로 모든 검증 가능해진 후
- 트리거: 사용자가 "샘플 버튼이 더 이상 필요 없다" 명시할 때

## DEFERRED: holdings 히스토리 / 스냅샷 관리
- 발생 맥락: POC2 Step 1 — state/holdings/holdings_latest.json 단일 파일만 유지
- 현재 결정: 시점별 스냅샷 / 변경 이력 미저장. 매번 덮어씀
- 재검토 예정: "어제는 어떤 보유 종목이었나" 가 필요해지는 운영 단계
- 트리거: 사용자/감사 요구 또는 draft 재현성 요구가 들어올 때

## DEFERRED: 운영용 holdings 편집 UX 개선
- 발생 맥락: POC2 Step 1 — 행 추가/삭제/저장만 단순 폼으로 제공
- 현재 결정: drag-drop 정렬, 일괄 가져오기, 일괄 삭제, undo 등 미도입
- 재검토 예정: 사용자가 holdings 편집 자주 한다고 보고할 때
- 트리거: 종목 수 증가 또는 사용자 UX 피드백

## DEFERRED: 복수 포트폴리오 / 계좌 지원
- 발생 맥락: POC2 Step 1 — 단일 사용자 단일 포트폴리오 전제
- 현재 결정: 다중 계좌 / 다중 포트폴리오 미지원
- 재검토 예정: 와이프/친구 공유 또는 ISA / 일반 / 연금 분리 운영 시점
- 트리거: 인증 / 사용자 구분 도입과 묶여서 다시 검토

## DEFERRED: 09:05 cron 자연 발생 검증 결과 반영
- 발생 맥락: POC1 Step 3 종료 시점 — 1회 수동 실행으로만 검증
- 현재 결정: 자연 cron 결과는 다음 09:05 KST 시점에 자연 발생
- 재검토 예정: 첫 자연 cron 실행 직후
- 트리거: cron 실행 후 inbox 적체 / Telegram 미발송 등 이슈 발견 시

## DEFERRED: ASSUMPTIONS.md Q2 closeout 이후 후속 질문 정리
- 발생 맥락: Q2 (OCI 푸쉬 파이프라인 동작 여부) — Step 3 실증으로 ANSWERED 가능 상태
- 현재 결정: ASSUMPTIONS 갱신 보류 (사용자 결정 대기)
- 재검토 예정: POC2 Step 1 종료 시점에 ASSUMPTIONS / Q1, Q3 와 함께 일괄 정리
- 트리거: 사용자 결정으로 ASSUMPTIONS 갱신 지시

---

# POC2 Step 1A (raw JSON 표시 제거 + holdings 초안 사람이 읽는 렌더링) 시 추가된 DEFERRED

## DEFERRED: handoff artifact 스키마 확장 (top-level message_text 추가) — 운영 메모
- 발생 맥락: POC2 Step 1A — Telegram 메시지 문자열 책임을 로컬 백엔드로 이전.
  POC1 Step 3 의 4 키(run_id/asof/approved_at/draft_payload) 에 5번째 키 `message_text` 추가
- 현재 결정: top-level 5번째 키로 분리 (draft_payload 와 책임 분리). holdings run 에서는
  필수, 비-holdings 에서는 선택. OCI consumer 가 message_text 우선 사용
- 재검토 예정: POC2 Step 2 진입 시 또는 다른 알림 채널 추가 시
- 트리거: 채널별 메시지 포맷이 갈라져야 할 때, 또는 message_text 외 별도 메타가 필요할 때

## DEFERRED: Telegram 메시지 디자인 고도화
- 발생 맥락: POC2 Step 1A — 사람이 읽는 줄 단위 목록까지만 도입. 마크다운 / 이모지 강조 / HTML
  parse_mode / 색상 / 링크 / 이미지 등 미사용
- 현재 결정: 평문(plain text) 만 사용. 운영 검증 우선
- 재검토 예정: Telegram 외 채널 추가 또는 사용자 가독성 추가 요구 시
- 트리거: 메시지 내 정보가 늘어나 평문으로 가독성이 떨어질 때

## DEFERRED: 현재가 / 평가손익 / 수익률을 메시지에 포함
- 발생 맥락: POC2 Step 1A — 데이터 새로 만들지 않는 표현 보정 단계. 매입금액/매입비중까지만
- 현재 결정: 시세 데이터 미연결. 평가지표 0건
- 재검토 예정: 시세 소스 결정 후 (BACKLOG "현재가/평가지표" 항목과 동시 진행)
- 트리거: pykrx/KIS/Naver/yfinance 중 시세 소스 확정 시

## DEFERRED: 추천 판단 사유 / ML 사유를 메시지에 노출
- 발생 맥락: POC2 Step 1A — recommendations 의 reason 필드는 현재 정적 stub("보유 종목 현황 ...")
- 현재 결정: action=HOLD 고정 + reason 정적 문구. 추천 판단 로직 0
- 재검토 예정: ML 연결 단계 또는 factor 추가 시
- 트리거: reason 이 실제 판단 근거(예: "vol_20d 상승, drawdown_from_peak < -5%") 로 채워질 때

## DEFERRED: 샘플 초안 완전 제거 여부 (POC2 Step 1A 재확인)
- 발생 맥락: POC2 Step 1 / 1A — 샘플 입력 폼은 접힘 섹션 + 고정 샘플 1버튼으로 격하 후 보존
- 현재 결정: 운영 입력 보호 + 샘플 보존. raw JSON 표시 그대로 유지 (개발/테스트 식별용)
- 재검토 예정: 운영 입력만으로 모든 검증이 가능해진 후
- 트리거: 사용자가 "샘플 더 이상 필요 없다" 명시 또는 운영 입력 폼이 충분히 안정될 때

## DEFERRED: 알림 채널별 메시지 포맷 분리
- 발생 맥락: POC2 Step 1A — Telegram 단일 채널만 사용. message_text 1개로 운영
- 현재 결정: Slack / Discord / Email 등 추가 채널 미도입. 채널별 메시지 포맷 함수 미분리
- 재검토 예정: 복수 채널 도입 결정 시
- 트리거: Telegram 외 채널 사용자 요구 발생 시

## DEFERRED: OCI 측 메시지 렌더링 책임 재검토
- 발생 맥락: POC2 Step 1A — message_text 생성을 로컬 백엔드로 일원화하여 OCI bash 책임 최소화
- 현재 결정: OCI consumer 는 message_text 가 있으면 그대로 사용, holdings 에서 누락 시 FAILED.
  비-holdings 면 raw fallback 으로 호환 (이전 POC1 메시지 형식)
- 재검토 예정: 운영 중 OCI 측 메시지 보강(예: 처리 시각/cron 컨텍스트 추가) 필요 시
- 트리거: OCI 측 처리 결과 메타데이터를 메시지에 함께 보내야 한다는 요구가 발생할 때

---

# POC2 Step 2 (holdings 시장데이터 enrichment) 시 추가된 DEFERRED

## DEFERRED → 별도 STEP: POC2-Step2A — pykrx EOD fallback 추가
- 발생 맥락: POC2 Step 2 — Naver 1차 소스만 사용. pykrx / yfinance fallback 일체 금지
  (설계자 결정 — 스코프 분리. 오늘은 1차 소스 안정성 검증, fallback 은 별도 단계)
- 현재 결정: Step 2 한정 pykrx 금지. 단일 종목 실패는 격리하고 그대로 표시 ("[시세 미확인]")
- 재검토 예정: POC2-Step2A 진입 시점
- 트리거 (모두 충족 시 Step2A 진입 검토):
  - Naver endpoint 가 일정 빈도 이상 timeout / 차단을 일으킬 때
  - 한국 종목 EOD 가 Naver 응답에 누락되는 케이스가 반복될 때
  - 사용자가 운영 중 "어제 종가가 안 나왔다" 류 피드백을 줄 때
- Step2A 채택 조건 (사전 결정):
  - pykrx 의존성 추가에 대한 별도 사용자 승인
  - 캐시/저장 위치 / TTL / 1차→2차 fallback 우선순위 결정
  - holdings 종목 중 일부만 한국 종목인 경우의 처리 정의

## DEFERRED: Naver endpoint 변경 / 차단 대응
- 발생 맥락: POC2 Step 2 — Naver `m.stock.naver.com/api/stock/{ticker}/basic` 비공식 endpoint 사용
- 현재 결정: 변경 시 단일 종목 실패로 격리 (timeout/http_error/json_decode_error/missing_price 등 reason 캡슐화)
- 재검토 예정: Naver 응답 스키마 변경 / 차단 / 정책 변경 발생 시
- 트리거: refresh 호출 시 모든 종목이 동일 reason 으로 실패할 때

## DEFERRED: market_cache TTL / 만료 정책
- 발생 맥락: POC2 Step 2 — "최근 조회값 재사용" 수준. TTL 미도입
- 현재 결정: 사용자가 [시세 갱신] 누를 때만 갱신. 캐시값에 만료 표시 없음.
- 재검토 예정: 시세 stale 노출이 사용자 혼란을 야기할 때
- 트리거: 어제 종가가 오늘 화면/메시지에 그대로 표시되어 의사결정에 문제가 될 때

## DEFERRED: Naver fetch 동시성 / 배치 / rate limit
- 발생 맥락: POC2 Step 2 — fetch_many 는 단순 순차(직렬) 호출. 비공식 endpoint 보호 우선
- 현재 결정: 동시성 도입 안 함. 종목당 5초 timeout × 보유 종목 수 만큼 직렬 소요 가능
- 재검토 예정: 보유 종목 수 증가로 [시세 갱신] 체감 지연이 명확해질 때
- 트리거: 보유 종목 ≥ 10개 + refresh 시간 ≥ 30s 가 일상화될 때

## DEFERRED: 시세 표시 timezone / 사람이 읽는 형식 정규화
- 발생 맥락: POC2 Step 2 — Naver `localTradedAt` (예: `2026-04-27T16:10:16+09:00`) 을 UI 에 그대로 표시
- 현재 결정: ISO 문자열 그대로 노출. KST 표기 변환 / "오늘 16:10" 같은 사람이 읽는 형식 미적용
- 재검토 예정: 사용자 가독성 피드백 시
- 트리거: "이게 한국 시간인가요" 류 질문이 반복될 때

## DEFERRED: 비-한국 종목 / ETF / 해외 시세
- 발생 맥락: POC2 Step 2 — Naver 한국 시장 endpoint 만 사용. 미국/홍콩 등 미지원
- 현재 결정: 한국 종목 ticker (6자리 또는 ETF 영문 혼합) 만 지원. 해외 종목은 [시세 미확인]
- 재검토 예정: 사용자가 해외 종목 보유 입력 시
- 트리거: holdings 에 해외 종목 ticker 가 들어갔는데 모두 [시세 미확인] 으로 노출될 때

## DEFERRED: enrichment 결과의 draft_payload 외 영구 저장
- 발생 맥락: POC2 Step 2 — enrich 결과는 매 generate-from-holdings 시 캐시에서 즉석 결합되어 draft_payload 에 들어감
- 현재 결정: enrichment 산출물(평가금액/손익) 의 별도 시계열/스냅샷 저장 없음
- 재검토 예정: 평가손익 시계열 차트 / 일자별 비교 요구 발생 시
- 트리거: "어제 평가손익이 얼마였나" 류 요구가 들어올 때

## DEFERRED: 종목명 자동 보정 (사용자 입력 vs Naver 응답 충돌 처리)
- 발생 맥락: POC2 Step 2 — name 우선순위 = 사용자 입력 > Naver stockName > None
- 현재 결정: 사용자 입력이 항상 우선. Naver 응답명과 다르면 알림/경고 없음
- 재검토 예정: 사용자가 오타로 잘못된 종목명을 저장한 사례가 발견될 때
- 트리거: 사용자가 "내 입력명이 종목 실제 이름과 달라 보인다" 피드백 시

## DEFERRED: holdings ticker 형식 검증 강화
- 발생 맥락: POC2 Step 2 — Naver endpoint 는 6자리 한국 종목 + 일부 ETF 영문혼합 ticker 만 200 응답
- 현재 결정: ticker 형식 사전 검증 없음. Naver 가 200 외 응답 시 [시세 미확인] 으로 표시
- 재검토 예정: 사용자가 ticker 형식 오류를 반복적으로 일으킬 때
- 트리거: refresh 결과 failure reason 이 항상 동일한 종목에서 동일하게 나올 때

## DEFERRED: market_cache 영속화 위치 / 다중 환경 분리
- 발생 맥락: POC2 Step 2 — 단일 PC 단일 캐시 파일. 다중 환경(PC/NAS/OCI) 동기화 정책 없음
- 현재 결정: state/market_cache/ 는 .gitignore 처리. 환경 간 캐시 공유 안 함
- 재검토 예정: 운영 환경이 PC 외 추가될 때
- 트리거: 다중 환경에서 같은 holdings 에 다른 시세값이 보일 때

## DEFERRED: refresh 실패 종목의 사용자 안내 / 재시도 UX
- 발생 맥락: POC2 Step 2 — failure list 는 helper 한 줄 텍스트로 노출
- 현재 결정: 종목별 재시도 버튼 / 실패 사유별 안내 / 자동 재시도 미도입
- 재검토 예정: refresh 실패 빈도가 사용자 체감 수준에 도달할 때
- 트리거: 동일 종목이 3회 이상 연속 실패하는 사례 발생 시

## DEFERRED: Naver 응답 캐싱 헤더 / ETag 활용
- 발생 맥락: POC2 Step 2 — 매 refresh 마다 GET. 304 Not Modified / ETag / Last-Modified 미활용
- 현재 결정: 단순 GET 만 사용. 응답 헤더 무시
- 재검토 예정: refresh 호출 빈도가 늘어 Naver 부담이 우려될 때
- 트리거: refresh 호출 수가 1일 100건 이상 / Naver 응답 지연 발생 시

## DEFERRED: 시세 표시 정밀도 / 통화 / 단위
- 발생 맥락: POC2 Step 2 — 모든 금액 "원" 고정. 천단위 콤마 + 소수 2자리 라운딩
- 현재 결정: KRW 단일 통화. 외화 / 단가 단위(주당/계약당) 구분 미도입
- 재검토 예정: 해외 종목 / 외화 ETF 보유가 일상화될 때
- 트리거: holdings 에 USD/JPY 등 외화 종목이 들어가면서 통화 혼동 발생 시

## DEFERRED: enrich 결과를 OCI 측에서 재계산 / 검증
- 발생 맥락: POC2 Step 2 — enrich 책임은 100% 로컬 백엔드. OCI 는 message_text 발송만
- 현재 결정: OCI 가 시세를 재조회 / 검증하지 않음 (POC2 Step 1A 의 책임 분리 원칙 유지)
- 재검토 예정: OCI 와 로컬의 시세 stale 차이가 운영 이슈가 될 때
- 트리거: 사용자가 cron 발송 시각의 시세와 로컬 화면 시세가 다르다고 느낄 때

## DEFERRED: market_cache 복수 소스 우선순위 / 메타데이터
- 발생 맥락: POC2 Step 2 — price_source="naver" 단일 값
- 현재 결정: 1차 소스 메타만 기록. 멀티 소스 우선순위 / 융합 / 충돌 해결 정책 없음
- 재검토 예정: POC2-Step2A 진입 시 (pykrx EOD fallback 추가 시)
- 트리거: pykrx fallback 도입 결정 시 동시에 결정 필요

## DEFERRED: GET /holdings/enriched 응답 캐싱 / 조건부 응답
- 발생 맥락: POC2 Step 2 — 매 GET 마다 holdings 로드 + 캐시 결합 + JSON 직렬화
- 현재 결정: 응답 캐싱 / ETag / Last-Modified / If-Modified-Since 미적용
- 재검토 예정: holdings 종목 수가 100+ 로 늘어 GET 응답 시간이 체감 수준일 때
- 트리거: 프론트가 enriched 호출을 자주 트리거하면서 응답 지연이 보일 때

## DEFERRED: enrichment 단계 로깅 / 감사 추적
- 발생 맥차: POC2 Step 2 — fetch_one / fetch_many 는 logger.warning 으로 실패만 기록
- 현재 결정: 성공 fetch / 캐시 hit-miss / refresh 호출 횟수 등 감사용 로그 없음
- 재검토 예정: 운영 안정화 단계 또는 Naver 차단 의심 시점
- 트리거: refresh 결과의 시간대별 성공/실패 패턴 분석이 필요할 때

---

# POC2 Step 2B (Telegram Message Compaction) 시 추가된 DEFERRED

## DEFERRED → 별도 STEP: POC2-Step2C — Holdings UI 압축
- 발생 맥락: POC2 Step 2B — Telegram 메시지만 요약형으로 전환. UI 카드 길이 / 펼침-접힘 / 요약 보기는 그대로
- 현재 결정: UI 압축 작업은 이번 단계 외. Telegram 메시지에 "전체 상세는 웹 화면에서 확인" 안내만 추가
- 재검토 예정: POC2-Step2C 진입 시점
- 트리거: 보유 종목 20+ 에서 UI 카드 리스트가 시각적으로 부담스러워질 때

## DEFERRED → 별도 STEP: POC2-Step2C — 계좌 구분 추가
- 발생 맥락: POC2 Step 2B — 단일 계좌 전제 유지. 보유 종목에 계좌 필드 없음
- 현재 결정: holdings 스키마 / draft_payload / Telegram 모두 계좌 구분 도입 안 함
- 재검토 예정: POC2-Step2C 또는 다중 사용자/계정 도입 시
- 트리거: ISA / 일반 / 연금 / 가족 계좌 분리 운영 요구 발생 시

## DEFERRED: Telegram 메시지 Top N 설정값 UI화
- 발생 맥락: POC2 Step 2B — TOP_N_PRICE_MISSING / TOP_N_BOTTOM_PNL_RATE / TOP_N_TOP_MARKET_WEIGHT / TOP_N_TOP_PNL_RATE 가 코드 내 상수
- 현재 결정: 기본값 3 으로 고정. 설정 파일 / 환경변수 / UI 설정으로 노출 안 함
- 재검토 예정: 사용자가 Top N 값 조정 요구를 반복 제기할 때
- 트리거: "더 많이 / 더 적게 보고 싶다" 가 명시 요구로 들어올 때

## DEFERRED: Telegram 메시지 split 발송 검토
- 발생 맥락: POC2 Step 2B — 한 메시지로 발송하되 길이 안전 한도 초과 시 주목 종목 축소 + 잘림 안내
- 현재 결정: 메시지 분할(여러 개로 쪼개 발송) 도입 안 함. compaction 만으로 처리
- 재검토 예정: 한도 축소만으로는 정보 손실이 운영 이슈가 될 때
- 트리거: 잘림 안내가 일상화되면서 사용자가 "전체 정보를 봐야 한다" 요구할 때

## DEFERRED: snapshot/history 기반 변화 감지
- 발생 맥락: POC2 Step 2B — "변화 없음" 은 이번 draft 안의 action=HOLD + 기본 reason 기준. 과거 run 비교 없음
- 현재 결정: snapshot/history 테이블 / 이전 run 비교 / 일자별 차이 일체 도입 안 함
- 재검토 예정: 운영 중 "어제 대비 X% 변동" 류 알림 요구 발생 시
- 트리거: 사용자가 "변화 감지" 알림이 별도 채널로 필요하다고 명시할 때

## DEFERRED: 전일 대비 변화 감지
- 발생 맥락: POC2 Step 2B — 매 run 은 독립적으로 처리. 전일 종가 / 전일 평가금액 비교 없음
- 현재 결정: 일자별 비교 데이터 보존 안 함
- 재검토 예정: snapshot/history 도입 시 동시에 검토
- 트리거: 일별 변화율 차트 / 전일 대비 손익 알림 요구

## DEFERRED: 계좌별 Telegram 요약
- 발생 맥락: POC2 Step 2B — 단일 계좌 전제. 계좌 필드 없으므로 계좌별 요약 불가
- 현재 결정: 계좌별 분리 요약 / 별도 발송 / 채널 분기 일체 안 함
- 재검토 예정: 계좌 구분 추가(POC2-Step2C 또는 이후) 와 함께
- 트리거: 계좌 구분 도입 직후

## DEFERRED: ML/factor 기반 action/reason 고도화
- 발생 맥락: POC2 Step 2B — action 은 전부 'HOLD' 고정, reason 은 정적 stub
- 현재 결정: ML 연결 / factor 점수 / 매수·매도 추천 미도입 (Phase 1 격리 유지)
- 재검토 예정: 보유 운영이 안정화된 후 ASSUMPTIONS Q1 (factor 추가 10줄 이내) 검증 시점
- 트리거: 사용자가 "추천 점수 / 위험도 / factor" 요구를 명시할 때

## DEFERRED: 가격 미확인 종목 반복 실패 관리
- 발생 맥락: POC2 Step 2B — 시세 미확인 종목은 [시세 미확인] 표기 + 주목 종목 카테고리에 포함
- 현재 결정: 종목별 누적 실패 카운트 / 자동 알림 / 자동 제외 정책 없음
- 재검토 예정: 동일 종목이 N일 연속 실패할 때 별도 안내가 필요해질 때
- 트리거: 동일 ticker 가 1주일 이상 [시세 미확인] 으로 표기될 때

## DEFERRED: 메시지 채널별 포맷 분리
- 발생 맥락: POC2 Step 2B — Telegram 단일 채널만 사용. message_text 1개로 발송
- 현재 결정: Slack / Discord / Email / SMS 등 추가 채널 미도입. 채널별 포맷 함수 분리 안 함
- 재검토 예정: 복수 채널 도입 결정 시
- 트리거: Telegram 외 채널 사용자 요구

## DEFERRED: 시세 확인 종목 기준 요약의 UX 고도화
- 발생 맥락: POC2 Step 2B — "시세 확인 N개 기준" 라벨 + 경고 문구로만 표시
- 현재 결정: 그래프 / 강조 색상 / 인포그래픽 미도입. 평문 텍스트만
- 재검토 예정: 시세 미확인 종목이 빈번히 발생하면서 사용자 혼란이 누적될 때
- 트리거: "전체 손익이 얼마인지 헷갈린다" 류 피드백

## DEFERRED: 누락 데이터가 많은 포트폴리오의 별도 경고 정책
- 발생 맥락: POC2 Step 2B — 시세 미확인이 1개 이상이면 일반 경고 문구 1줄. 비율과 무관하게 동일
- 현재 결정: 시세 미확인 비율(예: 50% 이상) 에 따른 별도 경고 / FAILED 처리 등 차등 정책 없음
- 재검토 예정: 시세 미확인 비율이 높은 운영 사례 발생 시
- 트리거: 시세 미확인 종목이 전체의 절반을 넘는 사례가 반복될 때

---

# POC2 Step 2C (Holdings UI 압축 + 계좌 구분) 시 추가된 DEFERRED

## DEFERRED: 계좌번호 / 증권사 구분 도입
- 발생 맥락: POC2 Step 2C — account_group 은 표시/그룹용 라벨로만 도입
- 현재 결정: 실제 계좌번호 / 증권사 식별자는 도입하지 않음. 라벨 자유 입력만 허용
- 재검토 예정: 사용자가 계좌별 손익 계산 / 증권사별 보고를 명시 요구할 때
- 트리거: "계좌번호 단위로 정확히 묶고 싶다" / "증권사별 합계가 필요하다" 류 요구

## DEFERRED: 계좌별 세금 / 절세 판단
- 발생 맥락: POC2 Step 2C — account_group 은 세무 판정값 아님 (지시문 명시)
- 현재 결정: ISA 한도 / 연금 세액공제 / 양도세 계산 등 일체 미도입
- 재검토 예정: 사용자가 절세 판단을 화면에서 받고 싶다고 명시할 때
- 트리거: "ISA 만기까지 얼마 남았나" / "연금 한도 초과인가" 류 질문이 누적될 때

## DEFERRED: 모바일 최적화 (compact table 가로 스크롤 / 터치 UX)
- 발생 맥락: POC2 Step 2C — compact-table-wrapper 는 overflow-x: auto 만 적용. 폭 좁은 화면 대응은 최소
- 현재 결정: 데스크톱 우선. 모바일은 가로 스크롤로 감내
- 재검토 예정: 사용자가 모바일에서 정기적으로 확인하기 시작할 때
- 트리거: 와이프 / 친구 등 비-데스크톱 사용자 공유 시점

## DEFERRED: 종목 상세 펼침 상태 장기 저장 (localStorage / URL Query)
- 발생 맥락: POC2 Step 2C — 펼침 상태는 컴포넌트 메모리(Set)로만 유지
- 현재 결정: 새 run 전환 / 페이지 reload 시 초기화. 항목 식별자 단위 polling 보존만 구현
- 재검토 예정: 사용자가 같은 펼침 상태를 세션 간에도 유지하고 싶다고 명시할 때
- 트리거: F5 후 펼침이 사라진다는 피드백 누적

## DEFERRED: 계좌별 Telegram 요약 / 채널 분리
- 발생 맥락: POC2 Step 2C — Telegram message_text 는 Step 2B 정책 그대로 (전체 요약 + 주목 종목)
- 현재 결정: 계좌별 분리 발송 / 별도 메시지 / 채널 분기 일체 안 함
- 재검토 예정: 와이프와 본인이 다른 계좌만 보고 싶은 시점
- 트리거: 사용자가 계좌별 별도 알림을 명시 요구할 때

## DEFERRED: 복수 포트폴리오 지원 (사용자별 / 가족별)
- 발생 맥락: POC2 Step 2C — holdings_latest.json 단일 SSOT. account_group 은 한 포트폴리오 내 라벨링
- 현재 결정: 사용자/포트폴리오 다중 엔티티 미도입
- 재검토 예정: 와이프와 본인 / 친구 / 가족 계정 분리가 필요한 시점
- 트리거: 인증 / 사용자 구분 도입과 묶여서 다시 검토

## DEFERRED: account_group 라벨 병합 / 관리 UI
- 발생 맥락: POC2 Step 2C — 라벨은 자유 입력. "키움-일반" 과 "키움일반" 같은 변형이 누적될 수 있음
- 현재 결정: 자동 병합 / 라벨 일괄 변경 / 라벨 사용 통계 UI 없음
- 재검토 예정: 사용자가 라벨 파편화로 혼란을 겪을 때
- 트리거: 동일 의미 라벨이 5개 이상 파편화 발견 시

## DEFERRED: 과거 draft_payload 영구 마이그레이션
- 발생 맥락: POC2 Step 2C — 과거 run 의 draft_payload 에 account_group 누락 가능. 렌더링 계층에서만 "일반" 으로 보정
- 현재 결정: 과거 run 의 store 파일을 강제 재작성하지 않음. 렌더링 호환만 보장
- 재검토 예정: 운영 중 과거 데이터 재현 / 비교가 필요해질 때
- 트리거: 사용자가 "어제 run 의 계좌별 합계가 보고 싶다" 같은 요구를 할 때

## DEFERRED: 시세 미확인 계좌 UX 고도화
- 발생 맥락: POC2 Step 2C — 시세 확인 0개 계좌는 "계산 불가" 한 줄 표시
- 현재 결정: 종목별 재시도 / 자동 알림 / 미확인 종목 강조 색상 등 미도입
- 재검토 예정: 시세 미확인이 일상적으로 한 계좌에 몰릴 때
- 트리거: 동일 계좌가 7일 이상 "계산 불가" 로 표시될 때

## DEFERRED: stable holding_id 영구 저장 여부
- 발생 맥락: POC2 Step 2C — holding_id 도입 안 함. React key 는 source_index + ticker + account_group + avg_buy_price 조합
- 현재 결정: holdings_latest.json 스키마에 holding_id 추가하지 않음
- 재검토 예정: 사용자가 동일 종목 분할매수를 자주 편집하면서 행 순서가 흔들려 펼침 상태가 sm 손실될 때
- 트리거: source_index 만으로 row 식별이 깨지는 사례 발생 시 (예: 행 삭제/재정렬 후 펼침 상태 미스매치)

## DEFERRED: PnL 산식 설명 고도화
- 발생 맥락: POC2 Step 2C — "(평가 계산 N개 기준)" 라벨 + 단일 경고 문구. 산식 자체는 화면에서 설명 안 함
- 현재 결정: 사용자가 산식을 직접 알고 있다고 가정. 툴팁 / 모달 / 도움말 미도입
- 재검토 예정: 사용자가 평가손익 계산 방식을 묻기 시작할 때
- 트리거: "왜 손익이 이렇게 나오나" 류 피드백이 1회라도 발생할 때

## DEFERRED: 프론트 compact UI 공용 모듈 추출
- 발생 맥락: POC2 Step 2C — HoldingsClient.tsx (EnrichedSection) 와 RunPanel.tsx (HoldingsCompactView) 가 전체/계좌별 요약 계산 + compact table + 펼침 상태 유지 로직을 각각 보유. 외형은 유사하지만 데이터 소스 / 컬럼 의미 / 호환성 처리가 다름.
- 현재 결정: 두 컴포넌트의 책임이 단일이 아니므로 premature abstraction 회피. 공용 모듈(SummaryCards, CompactTable, useExpandedRows 등) 추출은 트리거 발생 후 별도 STEP.
- 재검토 예정: 동시 변경 사례 발생 시
- 트리거 (다음 중 하나라도 발생):
  · 한쪽 컴포넌트에 컬럼/요약 항목이 추가되면서 다른 쪽도 동일 변경이 필요한 일이 2회 이상 발생
  · 동일 계산 버그가 두 곳에서 같이 발견되어 두 곳에 같은 수정이 필요한 사례 발생
  · 컴포넌트 한 파일이 ~600 라인을 넘어 코드 리뷰 스캔이 어려워지는 시점

---

# POC2 Step 2D (Approval Draft Preview Separation) 시 추가된 DEFERRED

## DEFERRED: 역할별 페이지 분리
- 발생 맥락: POC2 Step 2D — 한 화면(MainPanel)에 입력 폼, 시세 평가, 승인 초안 preview, 근거 데이터, 샘플 폼이 모두 들어감
- 현재 결정: 단일 화면 + 섹션 구분 + details 펼침으로 처리. 라우팅/메뉴 분리 도입 안 함
- 재검토 예정: 사용자가 입력과 승인을 분리된 동선으로 쓰고 싶다고 명시할 때
- 트리거: 동일 사용자가 한 세션에서 입력 → 승인 사이를 4회 이상 왕복하면서 화면 길이 부담을 보고할 때

## DEFERRED: 전송 메시지 템플릿 고도화
- 발생 맥락: POC2 Step 2D — message_text 는 Step 2B 의 build_message_text 가 만든 그대로. 마크다운/HTML/이모지 강조/링크 미사용
- 현재 결정: 평문 + 안전 한도(MAX_LENGTH_CHARS=3500) 정책 그대로. preview 도 동일 문자열 그대로 표시
- 재검토 예정: Telegram 외 채널 도입 또는 가독성 추가 요구 발생 시
- 트리거: 사용자가 "강조/색상/링크가 필요하다" 요구를 명시할 때

## DEFERRED: 근거 데이터 접힘 상태 영구 저장 (localStorage / URL Query)
- 발생 맥락: POC2 Step 2D — 승인 초안 영역의 근거 데이터 details 펼침 상태는 컴포넌트 메모리만 유지
- 현재 결정: 새 run 전환 / 페이지 reload 시 초기화. 최신 run 은 기본 접힘, 과거 run(message_text 없음)은 기본 펼침이라는 정책으로만 보정
- 재검토 예정: 사용자가 펼침 상태를 세션 간에도 유지하고 싶다고 명시할 때
- 트리거: F5 후 펼침 상태가 사라진다는 피드백이 1회라도 발생할 때

## DEFERRED: message_text 와 Telegram 실제 렌더 차이 자동 검증
- 발생 맥락: POC2 Step 2D — preview 와 발송문은 같은 message_text 를 공유하지만, Telegram 클라이언트의 줄바꿈/공백/이모지/한글 폭 처리가 브라우저 pre-wrap 과 미세하게 다를 수 있음
- 현재 결정: 자동 비교 검증 도입 안 함. 사용자 디바이스에서 자연 검증
- 재검토 예정: preview 와 실제 Telegram 화면 차이가 의사결정에 영향을 줄 때
- 트리거: 사용자가 "preview 에서는 OK 였는데 Telegram 에서는 깨져 보인다" 류 피드백을 1회라도 보고할 때
