# THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md

# 3-PUSH Runtime Package Contract

## 0. 문서 목적

이 문서는 PC 테스트 환경과 OCI 런타임 환경이 공유할 `3-PUSH Runtime Package` 데이터 계약을 정의한다.

이 문서는 구현 지시서가 아니다.
이 문서는 schema 계약 문서다.

PC에서는 개발기간 동안 Approval/Telegram 화면을 OCI 발송 테스트 게이트처럼 사용한다.
OCI에서는 나중에 같은 데이터 구조를 받아 발송 시점의 runtime snapshot을 붙여 Telegram 발송에 사용한다.

---

## 1. 배경

현재 프로젝트의 PUSH/Telegram 흐름은 다음 구조를 갖는다.

```text
Run 생성
→ message_text 생성
→ PENDING_APPROVAL
→ 사용자 승인
→ DELIVERING
→ OCI handoff
→ OCI consumer
→ Telegram sendMessage
→ outbox 결과
→ COMPLETED / FAILED
```

개발기간 중에는 OCI에서 직접 테스트하기 어렵기 때문에, PC의 Approval/Telegram 화면을 OCI 발송 구조의 테스트 대역으로 사용한다.

단, 최종 목표는 PC가 완성된 메시지만 보내는 구조가 아니다.

목표 구조는 다음이다.

```text
PC
→ holdings / market / ML / universe evidence package 생성
→ PC에서 preview / approval로 검증
→ OCI로 package 전달

OCI
→ package 수신
→ 발송 시점 runtime data 조회
→ 3-PUSH message_text 생성
→ Telegram 발송
```

따라서 이 계약은 `message_text`보다 앞단의 판단 재료 구조를 정의한다.

---

## 2. 핵심 흐름

3-PUSH 생성 흐름은 아래 순서를 따른다.

```text
evidence package
→ runtime snapshot
→ push decision context
→ message_text
→ Telegram
```

### 2.1 evidence package

PC가 생성하는 사전 evidence 묶음이다.

예:

```text
- holdings snapshot
- market discovery snapshot
- ML baseline snapshot
- universe momentum snapshot
- NAV/괴리율 snapshot
- data quality snapshot
```

### 2.2 runtime snapshot

발송 시점에 확인하는 값이다.

PC 테스트에서는 실제 조회 또는 mock/manual 값으로 채울 수 있다.
OCI 런타임에서는 실제 조회값으로 채운다.

예:

```text
- 네이버 기준 국내 실시간 시세
- Nasdaq
- S&P 500
- Philadelphia Semiconductor Index
- 뉴스 snapshot
```

### 2.3 push decision context

evidence package와 runtime snapshot을 바탕으로 message_text 생성에 필요한 중간 관찰 구조다.

### 2.4 message_text

Telegram으로 실제 발송될 사람이 읽는 본문이다.

frontend가 조립하지 않는다.
backend 또는 OCI runtime builder가 생성한다.

---

## 3. PC / OCI 역할 구분

## 3.1 PC 역할

PC는 개발기간 중 다음 역할을 담당한다.

```text
- 기존 시스템 evidence 수집
- 3-PUSH runtime package 생성
- runtime snapshot 조회 가능 여부 테스트
- PC Approval/Telegram 화면에서 preview 검증
- raw JSON / 금지 문구 / 빈 placeholder 발송 방지
- OCI로 넘길 handoff 구조 검증
```

PC의 Approval은 실제 운영 승인 기능이 아니라 테스트 게이트다.

PC Approval의 목적은 다음이다.

```text
- 잘못된 message_text가 바로 Telegram으로 나가는 것 방지
- raw JSON 발송 방지
- 매수/매도/비중조절 문구 발송 방지
- 데이터가 비어 있는데 정상 메시지처럼 보이는 것 방지
```

## 3.2 OCI 역할

OCI는 최종 운영 시 다음 역할을 담당한다.

```text
- PC에서 넘긴 runtime package 수신
- 발송 시점 runtime snapshot 조회
- 3-PUSH message_text 생성
- Telegram 발송
- outbox 결과 기록
```

OCI에는 PC의 Approval UI가 없다.

운영 승인 방식, 스케줄 시간, 자동 발송 여부는 별도 Step에서 결정한다.

---

## 4. 최상위 schema

```json
{
  "schema_version": "three_push_runtime_package.v1",
  "package_id": "three-push-20260612-001",
  "created_at": "2026-06-12T21:30:00+09:00",
  "asof_date": "2026-06-12",
  "timezone": "Asia/Seoul",
  "source_mode": "pc_test",
  "push_kind": "market_briefing",
  "data_cutoff": {
    "kr_market_asof": "2026-06-12",
    "ml_feature_asof": "2026-06-12",
    "market_discovery_asof": "2026-06-12",
    "holdings_asof": "2026-06-12",
    "runtime_snapshot_at": null
  },
  "pc_evidence_snapshot": {},
  "runtime_snapshot": {},
  "push_context": {},
  "message_contract": {},
  "safety_guards": {},
  "generation_status": {}
}
```

---

## 5. 공통 필드

## 5.1 schema_version

```json
"schema_version": "three_push_runtime_package.v1"
```

PC와 OCI가 같은 데이터 계약을 보고 있는지 확인하기 위한 값이다.

schema가 변경되면 version을 올리고 변경 내용을 문서에 남긴다.

## 5.2 package_id

```json
"package_id": "three-push-20260612-001"
```

package 단위 식별자다.

Run ID와 동일할 필요는 없지만, Run과 연결 가능해야 한다.

## 5.3 source_mode

허용 값:

```text
pc_test
oci_runtime
```

의미:

```text
pc_test:
PC에서 preview / approval 테스트용으로 생성한 package

oci_runtime:
OCI에서 실제 발송 시점 runtime snapshot을 붙여 사용한 package
```

## 5.4 push_kind

허용 값:

```text
market_briefing
holdings_briefing
spike_or_falling_alert
```

의미:

```text
market_briefing:
어제까지의 장 흐름 + 가능한 runtime 시장 정보 기반 브리핑

holdings_briefing:
시장 판단을 바탕으로 holdings에 대한 관찰 / 리뷰 포인트 제공

spike_or_falling_alert:
현재 universe에서 잘 올라가거나 급등락이 큰 항목에 대한 관찰 알림
```

---

## 6. data_cutoff

각 evidence가 어느 기준일의 데이터인지 기록한다.

```json
"data_cutoff": {
  "kr_market_asof": "2026-06-12",
  "ml_feature_asof": "2026-06-12",
  "market_discovery_asof": "2026-06-12",
  "holdings_asof": "2026-06-12",
  "runtime_snapshot_at": null
}
```

원칙:

```text
- PC evidence 기준일과 runtime 조회 시점을 구분한다.
- runtime_snapshot_at은 OCI 또는 PC runtime 조회가 실제 수행된 시점에 채운다.
- 기준일이 불명확하면 정상 message_text처럼 보이면 안 된다.
```

---

## 7. pc_evidence_snapshot

PC가 생성해 OCI로 넘기는 사전 evidence 묶음이다.

```json
"pc_evidence_snapshot": {
  "holdings_snapshot": {},
  "market_discovery_snapshot": {},
  "ml_baseline_snapshot": {},
  "universe_momentum_snapshot": {},
  "nav_discount_snapshot": {},
  "data_quality_snapshot": {}
}
```

---

## 7.1 holdings_snapshot

```json
"holdings_snapshot": {
  "asof_date": "2026-06-12",
  "positions": [
    {
      "ticker": "069500",
      "name": "KODEX 200",
      "asset_type": "ETF",
      "quantity": 10,
      "avg_price": 35000,
      "current_price": 36000,
      "valuation_amount": 360000,
      "unrealized_return_pct": 2.85,
      "portfolio_weight_pct": 12.4,
      "data_status": "ok"
    }
  ],
  "portfolio_summary": {
    "total_valuation_amount": 10000000,
    "cash_amount": 500000,
    "cash_weight_pct": 5.0,
    "position_count": 8
  }
}
```

주의:

```text
- holdings_snapshot은 판단 재료다.
- 여기서 매수/매도/교체/비중 조절 결론을 만들지 않는다.
```

---

## 7.2 market_discovery_snapshot

```json
"market_discovery_snapshot": {
  "asof_date": "2026-06-12",
  "benchmark": "KODEX200",
  "top_candidates": [
    {
      "ticker": "367760",
      "name": "RISE 네트워크인프라",
      "return_1d_pct": 1.46,
      "return_5d_pct": 5.1,
      "return_10d_pct": 8.2,
      "return_20d_pct": 15.3,
      "excess_return_5d_pct": 2.1,
      "excess_return_10d_pct": 3.4,
      "excess_return_20d_pct": 6.2,
      "data_quality_flags": []
    }
  ]
}
```

---

## 7.3 ml_baseline_snapshot

```json
"ml_baseline_snapshot": {
  "asof_date": "2026-06-12",
  "report_status": "ok",
  "feature_asof_start": "2026-03-11",
  "feature_asof_end": "2026-06-11",
  "evaluated_days": 43,
  "candidate_baseline": {
    "top_group_future_return_5d_pct": 3.0,
    "top_group_future_excess_5d_pct": -1.48,
    "hit_rate_excess_gt_0_5d": 0.432,
    "rank_correlation_5d": 0.198
  },
  "risk_baseline": {
    "high_risk_future_drawdown_5d_pct": -6.08,
    "low_risk_future_drawdown_5d_pct": -1.83
  },
  "limitations": [
    "과거 룩백 baseline이며 미래 예측 확정값이 아님"
  ]
}
```

주의:

```text
- ML baseline은 판단 보조 evidence다.
- 미래 수익률 예측 확정값으로 표현하지 않는다.
- 위험 threshold나 조정장 확정 문구로 변환하지 않는다.
```

---

## 7.4 universe_momentum_snapshot

```json
"universe_momentum_snapshot": {
  "asof_date": "2026-06-12",
  "items": [
    {
      "ticker": "123456",
      "name": "예시 ETF",
      "return_1d_pct": 4.2,
      "return_5d_pct": 9.8,
      "return_20d_pct": 18.1,
      "data_quality_flags": []
    }
  ]
}
```

---

## 7.5 nav_discount_snapshot

```json
"nav_discount_snapshot": {
  "asof_date": "2026-06-12",
  "items": [
    {
      "ticker": "069500",
      "nav": 35980,
      "market_price": 36000,
      "discount_premium_pct": 0.06,
      "data_status": "ok"
    }
  ]
}
```

---

## 7.6 data_quality_snapshot

```json
"data_quality_snapshot": {
  "asof_date": "2026-06-12",
  "warnings": [],
  "errors": [],
  "stale_sources": [],
  "unavailable_sources": []
}
```

주의:

```text
- data_quality는 message_text에 과도하게 노출하지 않는다.
- 오류가 message 생성 실패 사유라면 generation_status에 반영한다.
```

---

## 8. runtime_snapshot

발송 시점에 확인하는 runtime data다.

PC 테스트에서는 실제 조회, mock, manual 입력 중 하나로 채울 수 있다.
다만 PC에서 모두 테스트한다는 원칙에 따라 미국 지수 등 주요 runtime source는 PC에서 조회 가능 여부를 먼저 확인해야 한다.

```json
"runtime_snapshot": {
  "captured_at": null,
  "kr_realtime_price_snapshot": {},
  "overnight_us_market_snapshot": {},
  "news_snapshot": {}
}
```

---

## 8.1 kr_realtime_price_snapshot

```json
"kr_realtime_price_snapshot": {
  "captured_at": "2026-06-13T08:55:00+09:00",
  "source": "naver",
  "items": [
    {
      "ticker": "069500",
      "name": "KODEX 200",
      "price": 36000,
      "change_pct": 0.42,
      "volume": 123456,
      "data_status": "ok"
    }
  ],
  "status": "ok"
}
```

PC 테스트 원칙:

```text
- 네이버 시세 조회가 PC에서 먼저 검증되어야 한다.
- PC에서 실패하면 OCI로 넘기기 전에 failed 또는 partial 상태로 드러나야 한다.
- UI에 빈 placeholder처럼 노출하지 않는다.
```

---

## 8.2 overnight_us_market_snapshot

사용자가 요구한 밤사이 미국 시장 확인 영역이다.

대상은 최소 아래 세 가지다.

```text
- Nasdaq
- S&P 500
- Philadelphia Semiconductor Index
```

권장 구조:

```json
"overnight_us_market_snapshot": {
  "captured_at": "2026-06-13T08:55:00+09:00",
  "indices": [
    {
      "symbol": "NASDAQ",
      "name": "Nasdaq Composite",
      "change_pct": 0.85,
      "close": 18000.12,
      "status": "ok"
    },
    {
      "symbol": "SPX",
      "name": "S&P 500",
      "change_pct": 0.41,
      "close": 5400.33,
      "status": "ok"
    },
    {
      "symbol": "SOX",
      "name": "Philadelphia Semiconductor Index",
      "change_pct": 1.25,
      "close": 5200.45,
      "status": "ok"
    }
  ],
  "status": "ok"
}
```

PC 테스트 원칙:

```text
- 미국 지수 source는 OCI 구현 전 PC에서 먼저 조회 가능해야 한다.
- 최소 Nasdaq / S&P 500 / Philadelphia Semiconductor Index 3종의 최신값 또는 전일 종가 기준 등락률을 PC에서 확인한다.
- source가 불안정하면 message_text에 억지로 표시하지 않는다.
- 조회 실패가 반복되면 runtime_snapshot.status 또는 generation_status.warnings에 남긴다.
- UI에는 "미국지수 unavailable" 같은 빈 placeholder를 반복 노출하지 않는다.
```

주의:

```text
- 이 계약 문서에서는 실제 source를 확정하지 않는다.
- source 선정과 구현은 별도 Step에서 다룬다.
```

---

## 8.3 news_snapshot

뉴스는 선택 데이터다.

```json
"news_snapshot": {
  "captured_at": "2026-06-13T08:55:00+09:00",
  "status": "unavailable",
  "items": []
}
```

본문 생성 원칙:

```text
- status=unavailable이면 Telegram 본문에서 뉴스 섹션을 생략한다.
- "뉴스 수집 실패", "뉴스 unavailable" 문구를 반복 노출하지 않는다.
- 뉴스 source 도입은 별도 Step이다.
```

---

## 9. push_context

message_text 생성을 위한 중간 관찰 구조다.

```json
"push_context": {
  "market_view": {},
  "holdings_view": {},
  "spike_view": {}
}
```

---

## 9.1 market_view

PUSH-1용이다.

```json
"market_view": {
  "push_kind": "market_briefing",
  "summary_inputs": {
    "kr_market_trend_basis": "previous_close",
    "us_overnight_basis": "latest_available",
    "risk_evidence_basis": "ml_baseline_snapshot"
  },
  "observations": [
    {
      "type": "market_trend",
      "text": "전일 기준 국내 시장은 일부 테마 중심 강세가 관찰됨",
      "evidence_refs": [
        "pc_evidence_snapshot.market_discovery_snapshot.top_candidates"
      ]
    },
    {
      "type": "overnight_us",
      "text": "밤사이 미국 반도체 지수 강세가 확인되면 국내 반도체/성장 테마 해석에 참고 가능",
      "evidence_refs": [
        "runtime_snapshot.overnight_us_market_snapshot.indices.SOX"
      ]
    }
  ],
  "limitations": [
    "실시간 장중 판단이 아니라 발송 시점 snapshot 기준"
  ]
}
```

---

## 9.2 holdings_view

PUSH-2용이다.

```json
"holdings_view": {
  "push_kind": "holdings_briefing",
  "depends_on": "market_view",
  "observations": [
    {
      "ticker": "069500",
      "name": "KODEX 200",
      "text": "시장 기준선 역할을 하는 보유 항목으로, 전일 국내 지수 흐름과 함께 비교 필요",
      "evidence_refs": [
        "pc_evidence_snapshot.holdings_snapshot.positions.069500",
        "runtime_snapshot.kr_realtime_price_snapshot.069500"
      ]
    }
  ],
  "review_points": [
    "미국 지수와 국내 보유 ETF의 방향이 엇갈리는지 확인",
    "보유 종목이 당일 급등락 후보와 겹치는지 확인"
  ]
}
```

금지:

```text
- 매수 추천
- 매도 추천
- 교체 추천
- 비중 조절 지시
- 지금 행동 필요
```

허용:

```text
- 관찰 필요
- 확인 필요
- 리뷰 후보
- 판단 보조 근거
```

---

## 9.3 spike_view

PUSH-3용이다.

```json
"spike_view": {
  "push_kind": "spike_or_falling_alert",
  "universe_scope": "ETF",
  "ranking_basis": "absolute_return_desc",
  "items": [
    {
      "ticker": "123456",
      "name": "예시 ETF",
      "return_1d_pct": 5.4,
      "return_5d_pct": 12.1,
      "direction": "up",
      "reason_text": "단기 수익률 상위권으로 변동성 확대 관찰",
      "data_quality_flags": []
    }
  ],
  "limitations": [
    "개별 주식 전체 universe는 포함하지 않음"
  ]
}
```

주의:

```text
- ranking_basis는 표시 순서다.
- 위험 threshold나 매매 기준이 아니다.
```

---

## 10. message_contract

Telegram으로 보낼 본문의 안전 계약이다.

```json
"message_contract": {
  "max_length": 3500,
  "language": "ko",
  "sections": [
    "title",
    "summary",
    "key_observations",
    "review_points",
    "limitations"
  ],
  "forbidden_content": [
    "raw_json",
    "token",
    "chat_id",
    "buy_order",
    "sell_order",
    "cash_allocation_instruction",
    "regime_confirmation",
    "risk_threshold_confirmation"
  ],
  "message_text": ""
}
```

원칙:

```text
- message_text는 사람이 읽는 본문이다.
- raw JSON을 그대로 넣지 않는다.
- token / chat_id를 넣지 않는다.
- 매수/매도/비중조절/조정장 확정 문구를 넣지 않는다.
- 빈 runtime slot을 UI placeholder처럼 표시하지 않는다.
```

---

## 11. safety_guards

```json
"safety_guards": {
  "requires_pc_approval_for_test_send": true,
  "allow_unapproved_delivery": false,
  "frontend_may_build_message_text": false,
  "telegram_direct_call_from_pc": false,
  "oci_consumer_contract_required": true,
  "actual_send_allowed_in_tests": false
}
```

의미:

```text
requires_pc_approval_for_test_send:
PC 테스트에서는 Approval을 거친 뒤에만 handoff 가능

allow_unapproved_delivery:
승인 없는 전달 금지

frontend_may_build_message_text:
frontend message_text 조립 금지

telegram_direct_call_from_pc:
PC backend가 Telegram API를 직접 호출하지 않음

actual_send_allowed_in_tests:
테스트 중 실제 Telegram 발송 금지
```

---

## 12. generation_status

```json
"generation_status": {
  "status": "ok",
  "missing_sections": [],
  "warnings": [],
  "errors": []
}
```

허용 status:

```text
ok
partial
failed
```

의미:

```text
ok:
필수 데이터가 있고 message_text 생성 가능

partial:
일부 optional 데이터가 없지만 핵심 메시지 생성 가능
예: 뉴스 없음

failed:
필수 데이터가 없어 정상 message_text를 만들면 안 됨
예: holdings_snapshot 없음인데 holdings_briefing 생성 요청
```

원칙:

```text
- partial은 정상과 구분한다.
- failed인데 정상 message_text처럼 보이면 안 된다.
- optional 데이터 부재를 UI에 빈 placeholder로 반복 노출하지 않는다.
```

---

## 13. PUSH별 필수 / 선택 데이터

## 13.1 PUSH-1 market_briefing

필수:

```text
- market_discovery_snapshot 또는 동등한 시장 흐름 evidence
- data_quality_snapshot
```

선택:

```text
- overnight_us_market_snapshot
- news_snapshot
- ml_baseline_snapshot
```

PC 테스트 확인 필요:

```text
- Nasdaq 조회 가능 여부
- S&P 500 조회 가능 여부
- Philadelphia Semiconductor Index 조회 가능 여부
```

없으면 생략 가능:

```text
- news_snapshot
```

---

## 13.2 PUSH-2 holdings_briefing

필수:

```text
- holdings_snapshot
- market_view 또는 market_discovery_snapshot
```

선택:

```text
- kr_realtime_price_snapshot
- nav_discount_snapshot
- ml_baseline_snapshot
- overnight_us_market_snapshot
```

없으면 축소 가능한 것:

```text
- runtime realtime price
- overnight_us_market_snapshot
```

단, 축소 시에도 정상 메시지처럼 과장하면 안 된다.

---

## 13.3 PUSH-3 spike_or_falling_alert

필수:

```text
- universe_momentum_snapshot 또는 kr_realtime_price_snapshot 중 하나
```

선택:

```text
- data_quality_snapshot
- market_discovery_snapshot
```

이번 기준에서 범위 밖:

```text
- 개별 주식 전체 universe
```

---

## 14. UI 표시 원칙

runtime_snapshot의 빈 슬롯은 UI placeholder로 새면 안 된다.

금지 예:

```text
- 미국지수: unavailable
- 뉴스: unavailable
- 실시간 시세: unavailable
```

허용:

```text
- 해당 섹션 생략
- generation_status에 내부 warning 기록
- 상세 디버그/개발자용 영역에서만 확인
```

Telegram message_text에도 빈 섹션을 반복 노출하지 않는다.

---

## 15. 기존 기능 영향 경계

## 15.1 건드릴 수 있는 PUSH 영역

후속 구현에서 다음 영역은 변경 가능하다.

```text
- app/draft.py
- app/draft_three_push.py
- app/message_market_briefing.py
- app/message_spike_alert.py
- app/draft_message.py
- app/models.py
- Approval/Telegram preview 관련 frontend
```

이유:

```text
message_text 생성 전의 evidence package를 보존하고 preview해야 하기 때문이다.
```

## 15.2 읽기만 해야 하는 기존 기능

다음은 원칙적으로 읽기만 한다.

```text
- holdings 평가 계산
- Market Discovery 계산
- ML baseline 계산
- NAV/괴리율 계산
- universe momentum 계산
- data quality 계산
```

금지:

```text
- 기존 산식 변경
- baseline scoring 변경
- Market Discovery ranking 변경
- NAV/괴리율 계산 변경
- universe momentum 계산 변경
```

## 15.3 별도 Step이 필요한 영역

이 문서는 아래 작업을 구현하지 않는다.

```text
- OCI에서 네이버 실시간 시세 조회
- OCI에서 Nasdaq / S&P 500 / SOX 조회
- 뉴스 source 도입
- 하루 3회 scheduler
- 승인 없는 자동 발송
- 개별 주식 전체 universe 급등락 수집
```

단, PC 테스트 단계에서는 미국 지수와 네이버 시세의 조회 가능 여부를 먼저 확인해야 한다.

---

## 16. 성공 기준

이 계약은 다음을 만족해야 한다.

```text
1. PC에서 3종 PUSH를 테스트할 수 있다.
2. Approval/Telegram 화면에서 OCI 발송 전 preview 역할을 할 수 있다.
3. OCI로 넘겨도 message_text만이 아니라 판단 재료가 함께 남는다.
4. runtime_snapshot은 PC 테스트에서는 실제 조회 또는 mock/manual 값으로, OCI에서는 실제 조회값으로 채울 수 있다.
5. 미국 지수 runtime source는 OCI 구현 전 PC에서 조회 가능 여부가 확인된다.
6. 기존 PUSH delivery 계약은 깨지지 않는다.
7. PUSH 이전 Step에서 만든 계산 기능은 수정하지 않는다.
8. 빈 runtime slot이 UI placeholder로 노출되지 않는다.
9. PC에서 실제 3종 message_text가 생성된다.
```

---

## 17. Active Reference 등록 지침

이 문서는 후속 Step에서 active reference로 취급한다.

권장 등록 위치:

```text
docs/handoff/STATE_LATEST.md
docs/STATE_LATEST.md
docs/handoff/POC2_B_NEXT_ACTIONS.md
```

등록 문구 예:

```text
3-PUSH Runtime Package Contract:
docs/handoff/THREE_PUSH_RUNTIME_PACKAGE_CONTRACT.md

PC/OCI가 공유하는 three_push_runtime_package.v1 schema 계약.
PUSH 후속 Step에서는 이 문서를 기준으로 evidence package / runtime snapshot / message_text 생성을 설계한다.
```

---

## 18. 변경 이력

### v1

초기 계약.

핵심 내용:

```text
- evidence package 우선 구조 확정
- PC = 테스트/승인 게이트
- OCI = runtime snapshot + Telegram 발송 위치
- message_text는 최종 표현
- runtime_snapshot 빈 슬롯 UI placeholder 노출 금지
- PC에서 미국 지수 조회 가능 여부 확인 필요
```
