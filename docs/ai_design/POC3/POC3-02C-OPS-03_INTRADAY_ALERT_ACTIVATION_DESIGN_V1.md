# POC3-02C-OPS-03 — 장중 급등락 알림 활성화 (설계자 지시 보존본)

- **출처**: 설계자(웹 GPT) 채팅 지시 · 2026-09-21
- **성격**: 개발자 입력. 개발자가 내용을 바꾸지 않는다.

```text
OPS_02_IMPLEMENTATION       = VERIFIED
CURRENT_STEP                = POC3-02C-OPS-03
CURRENT_ACTION              = IMPLEMENT_AND_VERIFY
PLAN_RESUBMISSION_REQUIRED  = NO
POLICY_ENABLED              = false (구현 완료 전 유지)
LIVE_SEND                   = 0
COMMIT_PUSH_OCI_APPLY       = 검증자 통과 전 금지
```

## 선행 판정 2건

- **Naver 무조정 D-1 등락률 사용**: 승인 유지. 급락 판정 변화 0건까지
  검증됐으므로 되돌리지 않는다.
- **정책 비활성인데 `장중 점검 확인 불가` 가 붙는 현상**: 결함이 맞다.
  - 비활성: 요약 줄 자체를 표시하지 않음
  - 활성 + 정상 집계: 실제 요약 표시
  - 활성 + 집계 누락·손상: `장중 점검 확인 불가`

## 1. 15:40 비활성 요약 결함 수정

`DEF-INTRADAY-SUMMARY-WHEN-DISABLED` 를 이번 Step 에서 수정한다.

- 정책 비활성 또는 `NOT_CONFIGURED`: 장중 점검 문구를 아예 붙이지 않음
- 정책 활성 + 정상 집계: 장중 점검 결과 표시
- 정책 활성 + 집계 파일 누락·손상·읽기 실패: `장중 점검 확인 불가`
- 기존 15:40 보유 브리핑 본문과 발송 슬롯은 변경하지 않음

비활성·정상·누락·손상 네 경로의 관통 테스트를 추가한다.

## 2. 정책 생성·승인·전달 경로

사용자가 임계값이나 ETF 를 하나씩 입력하는 화면을 만들지 않는다.

기존 원칙을 유지한다.

- PC: 정책 후보 자동 산출
- 사용자: 산출된 버전 전체를 승인
- OCI: 승인된 번들을 읽어 판정·발송
- OCI 자체 학습·임계 재선정·전체 종목 탐색 금지

기존 「승인·적용 > 장중 급등락 설정」 카드에 다음을 읽기 전용으로 표시한다.

- 설정 버전과 산출 기준일
- 활성/비활성 상태
- 대표 사업군 수
- 12개 정책 키와 값
- 산출 출처와 checksum
- 다음 적용 시 장중 알림이 실제 운영된다는 경고

기존 `approve-and-apply` 가 사업군 목록뿐 아니라 같은 버전의
`intraday_alert_policy` 전체를 승인·전달하도록 완결한다. 별도 메뉴와 수동
임계값 편집 UI 는 만들지 않는다.

## 3. 최초 정책값

이미 확정된 값은 그대로 사용한다.

```text
enabled                     = true
cooldown_minutes            = 120
max_alerts_per_day          = 4
max_items_per_section       = 3
sector_entry_min_pct        = +1.5
sector_chase_pct            = +4.0
sector_avoid_drop_pct       = -1.5
sector_rank_top_pct         = 20
sector_min_coverage_pct     = 80
```

`REQUIRED_POLICY_KEYS` 12개 전부를 결과서 표에 열거한다. 위 목록에 없는
나머지 키는 검증된 설계서·스키마의 기존 확정값만 사용한다. 확정 근거가 없는
값이 있다면 임의 생성하지 말고 해당 키만 중단·보고한다.

정책값은 스키마 기본값으로 조용히 주입하지 말고 PC 가 생성하는 버전된 정책
데이터에 포함한다.

## 4. 활성화 안전선

기존 `holdings_risk_alert` cron 과 autosend flag 가 이미 운영 중이므로,
`enabled=true` 번들을 OCI active 로 바꾸는 순간 다음 cron 부터 실발송 대상이
된다. 따라서 순서를 고정한다.

```text
1  로컬 구현
2  정책 후보 생성
3  후보 payload 와 12개 키 검증
4  후보 기준 dry-run 및 목업 대조
5  전체 회귀·KS-10
6  검증자 검증
7  사용자 메시지 형식·최대 발송량 확인
8  사용자 승인 후 approve-and-apply
9  OCI checksum·active version read-back
10 다음 cron 운영 확인
```

검증자와 사용자 확인 전에는 `enabled=true` 버전을 OCI active 로 만들지 않는다.
실제 Telegram 시험 발송도 하지 않는다.

## 5. 발송 계약

- 고정 4건: 시장 브리핑 08:00 + 보유 브리핑 09:15·12:30·15:40
- 조건형: 기존 7틱에서 조건 충족 시 하루 최대 4건
- 하루 최대: 8건
- 조건형은 신호가 없으면 0건
- 15:40 장중 요약은 보유 브리핑 안의 한 줄이며 별도 발송 건수가 아님
- 기존 폐지된 `spike_or_falling_alert` 를 부활시키지 않음
- 신규 push kind 와 신규 cron 을 만들지 않음

## 6. 완료 기준

```text
SUMMARY_WHEN_DISABLED        = OMITTED
POLICY_KEYS                  = 12/12 VALID
USER_EDITABLE_THRESHOLDS     = 0
CANDIDATE_DRY_RUN            = PASS
FLOW_THROUGH_TESTS           = PASS
BACKEND_FULL_REGRESSION      = PASS
KS10_TRIGGER                 = 0
RUNNER_LINES                 <= 648
VERIFIER                     = VERIFIED
USER_MESSAGE_APPROVAL        = REQUIRED_BEFORE_ACTIVATION
OCI_ACTIVE_ENABLED           = false UNTIL FINAL_APPROVAL
TELEGRAM_SENDS               = 0 BEFORE ACTIVATION
```

`PROGRAM_TRUTH.md` 와 `STATE_LATEST.md` 갱신은 수용한다. 별도 OPS-02 종료
문서는 지금 만들지 말고, OPS-03 활성화 및 운영 확인까지 끝난 뒤 `POC3-02C`
통합 closeout 한 건으로 작성한다.
