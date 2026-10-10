// POC5-06 — 재진입 검토 화면 test 자료 = 실제 백엔드 출력(tests/test_poc5_06_reentry_review.py 와 같은 tmp
// 자료로 GET 검토 · POST ML(계산 완료 · 자료 부족)을 실행해 그대로 옮김 · 산출물 경로만 일반화).
import type { ReentryMlResponse, ReentryReviewResponse } from "@/lib/api";

export const REVIEW: ReentryReviewResponse = {
  "schema": "reentry_review_v1",
  "read_only": true,
  "selection": {
    "position_id": "ab243b73-78e7-5524-9ce0-d9343eb14af0",
    "cycle_id": "349ff709-2f3f-5219-88e8-41c761f594b4",
    "ticker": "069500",
    "name": "KODEX 200",
    "account_group": "ISA"
  },
  "read_basis": {
    "holdings_status": "V1",
    "revision": 0,
    "doc_sha256": "6bf46519b7cb9aa22324036db013878d322dcf49dcbbe4c564c396d3c46b8ed0",
    "ledger_synced_at": "2025-07-01T10:00:00+09:00",
    "price_latest": "2025-06-27"
  },
  "my_trades": {
    "position": {
      "position_id": "ab243b73-78e7-5524-9ce0-d9343eb14af0",
      "ticker": "069500",
      "name": "KODEX 200",
      "account_group": "ISA",
      "is_open": true,
      "cycles": [
        {
          "cycle_id": "349ff709-2f3f-5219-88e8-41c761f594b4",
          "status": "OPEN",
          "opened_by": "BASELINE",
          "closed_by": null,
          "start_date": null,
          "end_date": null,
          "has_adjustment": false,
          "quantity": "10",
          "cost": "100000",
          "avg_buy_price": "10000",
          "realized_pnl": "0",
          "sold_cost": "0",
          "realized_rate": null,
          "events": [
            {
              "record_id": "644a2378-4d0a-52ac-baf8-a2708b90cfac",
              "kind": "BASELINE",
              "recorded_at": null,
              "supersedes_id": null,
              "payload": {
                "quantity": "10",
                "avg_buy_price": "10000"
              },
              "date": null,
              "cost_of_sold": null,
              "realized_pnl": null,
              "realized_rate": null,
              "q_after": "10",
              "c_after": "100000",
              "avg_after": "10000",
              "previous": []
            }
          ],
          "voided": []
        }
      ],
      "voided": []
    },
    "selected_cycle_id": "349ff709-2f3f-5219-88e8-41c761f594b4",
    "previous_cycle_ids": [],
    "summary": {
      "status": "OPEN",
      "opened_by": "BASELINE",
      "closed_by": null,
      "purchase_date_unknown": true,
      "closed_by_adjustment": false,
      "last_actual_sell_date": null,
      "has_adjustment": false
    },
    "notes": [
      "매수일 미상 — 기준잔고 · 잔고 등록으로 시작한 기간(입력 평단 기준)"
    ]
  },
  "stored_evidence": {
    "market_flow": {
      "schema": "holdings_market_flow_v1",
      "read_only": true,
      "ticker": "069500",
      "cycle_id": "349ff709-2f3f-5219-88e8-41c761f594b4",
      "opened_by": "BASELINE",
      "cycle_status": "OPEN",
      "purchase_date_unknown": true,
      "purchase_date_note": "매수일 미상 — 매수 전후 변화 계산 안 함",
      "db_present": true,
      "asset_kind": "ETF",
      "series": {
        "ticker": {
          "table": "etf_daily_price",
          "series_name": "ETF 저장 종가",
          "comparable_sources": [
            "FinanceDataReader",
            "NAVER_FDR"
          ]
        },
        "market": {
          "table": "market_benchmark_daily_price",
          "benchmark_id": "KOSPI",
          "series_name": "KOSPI 저장 종가",
          "comparable_sources": [
            "FinanceDataReader/KS11",
            "KRX_OPEN_API/idx_kospi_dd_trd",
            "NAVER_FDR"
          ]
        }
      },
      "latest_stored_date": "2025-06-27",
      "latest_stored_close": 15146.8,
      "latest_stored_source": "FinanceDataReader",
      "events": [],
      "holding_period": {
        "reason_code": "PURCHASE_DATE_UNKNOWN",
        "reason": "매수일 미상 — 매수 전후 변화 계산 안 함",
        "start_record_id": null,
        "end_record_id": null,
        "start_basis": null,
        "end_basis": null,
        "ticker": null,
        "market": null,
        "computed": false,
        "window_label": "첫 매수 기준일 → 마지막 매도 기준일"
      },
      "notes": [
        "저장 종가 비교값 — 체결단가로 계산한 개인 손익과 다르다.",
        "마지막 저장일은 PC 시세 DB 에 저장된 마지막 날짜이며 오늘 시세가 아니다.",
        "기준일 종가가 없으면 인접일 · 다른 계열로 메우지 않는다.",
        "정형 값만 제공 — 자유 생성 코멘트 · 모델 판단 없음."
      ],
      "free_commentary": null
    },
    "price_state": {
      "t": "2025-06-27",
      "latest_close": 15146.8,
      "latest_source": "FinanceDataReader",
      "expected_completed_date": "2025-07-14",
      "stale": true,
      "stale_note": "이 날짜 기준 검토",
      "price_basis_label": "저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정)",
      "partial_check_note": "change 가 없는 NAVER_FDR 구간은 가격 기준 변화(계단)를 감지할 수 없어 경계 검사가 부분적입니다 — 감지하지 못한 계단이 남을 수 있습니다.",
      "axis": {
        "label": "공식 휴장 목록이 아닌 KOSPI 저장일 보정 연구 축",
        "limit_note": "연도 파일이 없는 해는 KOSPI 저장일만 거래일로 셉니다 — 건너뛴 평일이 모두 확인된 휴장일은 아니며, KOSPI 저장이 빠진 실제 거래일도 축에서 빠질 수 있습니다.",
        "rule": "연도 파일 있는 해 = 파일 · 없는 해 = 평일 기본 ∩ KOSPI 저장일",
        "modes": {
          "2023": "KOSPI_CORRECTED",
          "2024": "KOSPI_CORRECTED",
          "2025": "KOSPI_CORRECTED"
        },
        "skipped_weekday_count": 0,
        "kospi_latest": "2025-06-27",
        "length": 646,
        "first": "2023-01-02",
        "last": "2025-06-27"
      },
      "features": {
        "chg5": -0.012754774485758236,
        "chg20": 0.03658019145540581,
        "chg60": 0.036171743954729774,
        "vol20": 0.011572844116401412,
        "from_high60": -0.020498222297523738
      },
      "status": "OK",
      "reason": null
    },
    "ledger": {
      "ticker": "069500",
      "synced_at": "2025-07-01T10:00:00+09:00",
      "items": [
        {
          "link_kind": "SUBJECT",
          "link_text": "이 종목 알림",
          "event_id": "ev1",
          "item_seq": 1,
          "push_kind": "holdings_briefing",
          "runtime_kst": "2025-06-26T09:15:00+09:00",
          "runtime_date_kst": "2025-06-26",
          "subject_kind": "ticker",
          "subject_id": "069500",
          "state": "D5_8",
          "state_label": "20거래일 하락 5~8%",
          "disposition": "sent",
          "delivery_status": "sent",
          "view": "DELIVERED",
          "view_text": "전달됨",
          "exposure": "PRIMARY",
          "cohort": "PRIMARY_LIVE",
          "off_schedule": 0,
          "contract_version": "holdings_briefing.v1",
          "outcome_target": true,
          "outcomes": [
            {
              "series_id": "krx_etf:069500",
              "horizon": 1,
              "status": "MATURED",
              "eval_date": null,
              "return_raw": null,
              "max_up_raw": null,
              "max_down_raw": null,
              "price_basis": "KRX_ETF_UNADJUSTED",
              "computed_at": "x"
            }
          ],
          "pending_horizons": [
            5,
            20
          ],
          "feedback": {
            "scope": "EVENT",
            "scope_text": "이 알림 전체에 대한 평가(종목별 평가 아님)",
            "count": 1,
            "latest": {
              "feedback_seq": 1,
              "helpfulness": "HELPFUL",
              "action": null,
              "memo": "메모 원문",
              "feedback_at": "x"
            }
          }
        },
        {
          "link_kind": "SECTOR_REPRESENTATIVE",
          "link_text": "연관 근거 — 사업군 신호의 대표 ETF 로 기록됨",
          "event_id": "ev2",
          "item_seq": 1,
          "push_kind": "holdings_briefing",
          "runtime_kst": "2025-06-26T09:15:00+09:00",
          "runtime_date_kst": "2025-06-26",
          "subject_kind": "sector",
          "subject_id": "semis",
          "state": "ENTRY_REVIEW",
          "state_label": "신규 진입 검토",
          "disposition": "sent",
          "delivery_status": "sent",
          "view": "DELIVERED",
          "view_text": "전달됨",
          "exposure": "PRIMARY",
          "cohort": "PRIMARY_LIVE",
          "off_schedule": 0,
          "contract_version": "holdings_briefing.v1",
          "outcome_target": true,
          "outcomes": [],
          "pending_horizons": [
            1,
            5,
            20
          ],
          "feedback": {
            "scope": "EVENT",
            "scope_text": "이 알림 전체에 대한 평가(종목별 평가 아님)",
            "count": 0,
            "latest": null
          }
        },
        {
          "link_kind": "INDEX_GROUP_MEMBER",
          "link_text": "연관 근거 — 기초지수 묶음 구성 ETF 로 기록됨",
          "event_id": "ev2",
          "item_seq": 3,
          "push_kind": "holdings_briefing",
          "runtime_kst": "2025-06-26T09:15:00+09:00",
          "runtime_date_kst": "2025-06-26",
          "subject_kind": "index_group",
          "subject_id": "k200",
          "state": "UP",
          "state_label": "UP",
          "disposition": "not_selected",
          "delivery_status": "sent",
          "view": "OBSERVED",
          "view_text": "관측만(본문에 안 실림)",
          "exposure": "NONE",
          "cohort": "PRIMARY_LIVE",
          "off_schedule": 0,
          "contract_version": "holdings_briefing.v1",
          "outcome_target": true,
          "outcomes": [
            {
              "series_id": "krx_etf:069500",
              "horizon": 5,
              "status": "PRICE_MISSING",
              "eval_date": null,
              "return_raw": null,
              "max_up_raw": null,
              "max_down_raw": null,
              "price_basis": "KRX_ETF_UNADJUSTED",
              "computed_at": "x"
            }
          ],
          "pending_horizons": [
            1,
            20
          ],
          "feedback": {
            "scope": "EVENT",
            "scope_text": "이 알림 전체에 대한 평가(종목별 평가 아님)",
            "count": 0,
            "latest": null
          }
        }
      ],
      "counts": {
        "SUBJECT": {
          "DELIVERED": 1
        },
        "SECTOR_REPRESENTATIVE": {
          "DELIVERED": 1
        },
        "INDEX_GROUP_MEMBER": {
          "OBSERVED": 1
        }
      },
      "status": "OK",
      "status_text": null
    }
  },
  "ml": {
    "available": true,
    "target_name": "이후 20거래일 최저 종가 변화(연구 추정)",
    "note": "연구 추정 · 투자 유효성 미확정"
  },
  "navigation": [
    {
      "menu": "market_discovery",
      "label": "요즘 잘 오르는 ETF — [최신 시장 데이터 갱신]",
      "note": "전체 ETF(약 1,200종목)의 최근 120일을 받습니다 · 약 1.5 ~ 2.5분 · 6시간 간격"
    },
    {
      "menu": "alert_records",
      "label": "받은 알림 기록 — [원장 새로고침]",
      "note": "OCI 원장 사본을 받습니다(시세는 갱신하지 않음)"
    }
  ],
  "notes": [
    "가격은 PC 에 저장된 종가입니다(현재 체결 가능 가격이 아님).",
    "D20 = 기준일 종가 대비 이후 20거래일 중 가장 낮았던 종가의 변화(모두 높으면 0) — 최대낙폭(MDD) · 장중 최대손실 · 손실 확률이 아닙니다.",
    "수수료 · 세금을 반영하지 않은 저장 종가 변화입니다 — 가격 의미는 '저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정)'입니다.",
    "겹치는 20일 창을 독립 표본으로 보지 않으므로 신뢰구간 · 성공률 · 확률을 표시하지 않습니다.",
    "이미 살펴본 과거 자료로 다시 계산한 연구이며 새로운 확증 시험이 아닙니다.",
    "알림이 도움이 됐는지 · 특정 거래가 적절했는지를 판정하지 않습니다.",
    "연구 추정 · 투자 유효성 미확정",
    "이 값은 매수/매도 지시가 아닙니다."
  ]
} as unknown as ReentryReviewResponse;

export const ML_OK: ReentryMlResponse = {
  "schema": "reentry_review_v1",
  "status": "OK",
  "status_text": "계산 완료",
  "reason": null,
  "ticker": "069500",
  "target_name": "이후 20거래일 최저 종가 변화(연구 추정)",
  "t": "2025-06-27",
  "expected_completed_date": "2025-07-14",
  "stale": true,
  "stale_note": "이 날짜 기준 검토",
  "result": {
    "t": "2025-06-27",
    "recipe_version": "poc5_06.v1",
    "features_at_t": {
      "chg5": -0.012754774485758236,
      "chg20": 0.03658019145540581,
      "chg60": 0.036171743954729774,
      "vol20": 0.011572844116401412,
      "from_high60": -0.020498222297523738
    },
    "samples": {
      "valid_n": 566,
      "excluded_by_reason": {}
    },
    "blocks": [
      {
        "block": 1,
        "first_date": "2024-09-06",
        "last_date": "2024-12-03",
        "axis_dates": 63,
        "train_n": 357,
        "valid_n": 63,
        "excluded_n": 0,
        "status": "OK",
        "train_last_eval_end": "2024-09-05",
        "baseline_median_pct": -1.4075770517046338,
        "mae_model_pp": 3.4957656644743524,
        "mae_baseline_pp": 5.878661492185378
      },
      {
        "block": 2,
        "first_date": "2024-12-04",
        "last_date": "2025-03-03",
        "axis_dates": 63,
        "train_n": 420,
        "valid_n": 63,
        "excluded_n": 0,
        "status": "OK",
        "train_last_eval_end": "2024-12-03",
        "baseline_median_pct": -2.051601481827886,
        "mae_model_pp": 2.4402157851726263,
        "mae_baseline_pp": 1.6892292872342214
      },
      {
        "block": 3,
        "first_date": "2025-03-04",
        "last_date": "2025-05-30",
        "axis_dates": 63,
        "train_n": 483,
        "valid_n": 63,
        "excluded_n": 0,
        "status": "OK",
        "train_last_eval_end": "2025-03-03",
        "baseline_median_pct": -1.954247624123806,
        "mae_model_pp": 2.625208491493781,
        "mae_baseline_pp": 1.8178964431615516
      }
    ],
    "overall": {
      "n": 189,
      "mae_model_pp": 2.8537299803802534,
      "mae_baseline_pp": 3.1285957408603835,
      "verdict": "IMPROVED",
      "verdict_text": "단순 기준보다 검증 오차 작음"
    },
    "final": {
      "train_n": 566,
      "train_first": "2023-03-27",
      "train_last": "2025-05-30",
      "estimate_pct": -2.221204332528138,
      "baseline_median_pct": -1.9194272315299188
    },
    "status": "OK",
    "reason": null
  },
  "axis": {
    "label": "공식 휴장 목록이 아닌 KOSPI 저장일 보정 연구 축",
    "limit_note": "연도 파일이 없는 해는 KOSPI 저장일만 거래일로 셉니다 — 건너뛴 평일이 모두 확인된 휴장일은 아니며, KOSPI 저장이 빠진 실제 거래일도 축에서 빠질 수 있습니다.",
    "rule": "연도 파일 있는 해 = 파일 · 없는 해 = 평일 기본 ∩ KOSPI 저장일",
    "modes": {
      "2023": "KOSPI_CORRECTED",
      "2024": "KOSPI_CORRECTED",
      "2025": "KOSPI_CORRECTED"
    },
    "skipped_weekday_count": 0,
    "kospi_latest": "2025-06-27",
    "length": 646,
    "first": "2023-01-02",
    "last": "2025-06-27"
  },
  "price_basis_label": "저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정)",
  "partial_check_note": "change 가 없는 NAVER_FDR 구간은 가격 기준 변화(계단)를 감지할 수 없어 경계 검사가 부분적입니다 — 감지하지 못한 계단이 남을 수 있습니다.",
  "recipe": {
    "target": "D20(t) = min(0, min_{h=1..20} C(t+h)/C(t) - 1) · 연구 축 위치 기준",
    "features": [
      "C(t)/C(t-5)-1",
      "C(t)/C(t-20)-1",
      "C(t)/C(t-60)-1",
      "std(ddof=0) of last 20 daily log returns",
      "C(t)/max(C(t-59)..C(t))-1"
    ],
    "model": "StandardScaler -> Ridge(alpha=1.0, solver='svd', fit_intercept=True)",
    "clip": [
      -1.0,
      0.0
    ],
    "baseline": "median D20 of the training block",
    "validation": {
      "end": "axis t-20",
      "dates": 189,
      "blocks": 3,
      "block": 63
    },
    "min_train": 252,
    "mae_unit": "%p",
    "version": "poc5_06.v1"
  },
  "canonical_sha256": "e531e006703ff342dcd1c0094a52c993a3ae40ebf2b128a59552d38ddd481c81",
  "read_basis": {
    "holdings_status": "V1",
    "revision": 0,
    "doc_sha256": "6bf46519b7cb9aa22324036db013878d322dcf49dcbbe4c564c396d3c46b8ed0",
    "ledger_synced_at": "2025-07-01T10:00:00+09:00",
    "price_latest": "2025-06-27"
  },
  "libraries": {
    "scikit-learn": "1.9.0",
    "numpy": "2.4.6"
  },
  "notes": [
    "가격은 PC 에 저장된 종가입니다(현재 체결 가능 가격이 아님).",
    "D20 = 기준일 종가 대비 이후 20거래일 중 가장 낮았던 종가의 변화(모두 높으면 0) — 최대낙폭(MDD) · 장중 최대손실 · 손실 확률이 아닙니다.",
    "수수료 · 세금을 반영하지 않은 저장 종가 변화입니다 — 가격 의미는 '저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정)'입니다.",
    "겹치는 20일 창을 독립 표본으로 보지 않으므로 신뢰구간 · 성공률 · 확률을 표시하지 않습니다.",
    "이미 살펴본 과거 자료로 다시 계산한 연구이며 새로운 확증 시험이 아닙니다.",
    "알림이 도움이 됐는지 · 특정 거래가 적절했는지를 판정하지 않습니다.",
    "연구 추정 · 투자 유효성 미확정",
    "이 값은 매수/매도 지시가 아닙니다."
  ],
  "runtime_seconds": 1.092,
  "artifact": {
    "folder": "state/ml/research/poc5_06/20261010T170459_20dc88ef",
    "files": "review.json · input_snapshot.json"
  }
} as unknown as ReentryMlResponse;

export const ML_SHORT: ReentryMlResponse = {
  "schema": "reentry_review_v1",
  "status": "DATA_SHORT",
  "status_text": "자료 부족 — 추정값을 만들지 않음",
  "reason": "세 검증 구간 중 학습 · 검증 자료가 부족한 구간이 있음",
  "ticker": "069500",
  "target_name": "이후 20거래일 최저 종가 변화(연구 추정)",
  "t": "2024-07-12",
  "expected_completed_date": "2025-07-14",
  "stale": true,
  "stale_note": "이 날짜 기준 검토",
  "result": {
    "t": "2024-07-12",
    "recipe_version": "poc5_06.v1",
    "features_at_t": {
      "chg5": -0.009712062959181367,
      "chg20": -0.05620039092050633,
      "chg60": -0.03211352402075529,
      "vol20": 0.012310986073550759,
      "from_high60": -0.09754653894481125
    },
    "samples": {
      "valid_n": 318,
      "excluded_by_reason": {}
    },
    "blocks": [
      {
        "block": 1,
        "first_date": "2023-09-25",
        "last_date": "2023-12-20",
        "axis_dates": 63,
        "train_n": 109,
        "valid_n": 63,
        "excluded_n": 0,
        "status": "DATA_SHORT"
      },
      {
        "block": 2,
        "first_date": "2023-12-21",
        "last_date": "2024-03-18",
        "axis_dates": 63,
        "train_n": 172,
        "valid_n": 63,
        "excluded_n": 0,
        "status": "DATA_SHORT"
      },
      {
        "block": 3,
        "first_date": "2024-03-19",
        "last_date": "2024-06-14",
        "axis_dates": 63,
        "train_n": 235,
        "valid_n": 63,
        "excluded_n": 0,
        "status": "DATA_SHORT"
      }
    ],
    "status": "DATA_SHORT",
    "reason": "세 검증 구간 중 학습 · 검증 자료가 부족한 구간이 있음"
  },
  "axis": {
    "label": "공식 휴장 목록이 아닌 KOSPI 저장일 보정 연구 축",
    "limit_note": "연도 파일이 없는 해는 KOSPI 저장일만 거래일로 셉니다 — 건너뛴 평일이 모두 확인된 휴장일은 아니며, KOSPI 저장이 빠진 실제 거래일도 축에서 빠질 수 있습니다.",
    "rule": "연도 파일 있는 해 = 파일 · 없는 해 = 평일 기본 ∩ KOSPI 저장일",
    "modes": {
      "2023": "KOSPI_CORRECTED",
      "2024": "KOSPI_CORRECTED"
    },
    "skipped_weekday_count": 0,
    "kospi_latest": "2024-07-12",
    "length": 398,
    "first": "2023-01-02",
    "last": "2024-07-12"
  },
  "price_basis_label": "저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정)",
  "partial_check_note": "change 가 없는 NAVER_FDR 구간은 가격 기준 변화(계단)를 감지할 수 없어 경계 검사가 부분적입니다 — 감지하지 못한 계단이 남을 수 있습니다.",
  "recipe": {
    "target": "D20(t) = min(0, min_{h=1..20} C(t+h)/C(t) - 1) · 연구 축 위치 기준",
    "features": [
      "C(t)/C(t-5)-1",
      "C(t)/C(t-20)-1",
      "C(t)/C(t-60)-1",
      "std(ddof=0) of last 20 daily log returns",
      "C(t)/max(C(t-59)..C(t))-1"
    ],
    "model": "StandardScaler -> Ridge(alpha=1.0, solver='svd', fit_intercept=True)",
    "clip": [
      -1.0,
      0.0
    ],
    "baseline": "median D20 of the training block",
    "validation": {
      "end": "axis t-20",
      "dates": 189,
      "blocks": 3,
      "block": 63
    },
    "min_train": 252,
    "mae_unit": "%p",
    "version": "poc5_06.v1"
  },
  "canonical_sha256": "9c58d435214ac6069761d985b55bbae70e7f351985a5b58dbf2c0c3a9d667363",
  "read_basis": {
    "holdings_status": "V1",
    "revision": 0,
    "doc_sha256": "6bf46519b7cb9aa22324036db013878d322dcf49dcbbe4c564c396d3c46b8ed0",
    "ledger_synced_at": "2025-07-01T10:00:00+09:00",
    "price_latest": "2024-07-12"
  },
  "libraries": {
    "scikit-learn": "1.9.0",
    "numpy": "2.4.6"
  },
  "notes": [
    "가격은 PC 에 저장된 종가입니다(현재 체결 가능 가격이 아님).",
    "D20 = 기준일 종가 대비 이후 20거래일 중 가장 낮았던 종가의 변화(모두 높으면 0) — 최대낙폭(MDD) · 장중 최대손실 · 손실 확률이 아닙니다.",
    "수수료 · 세금을 반영하지 않은 저장 종가 변화입니다 — 가격 의미는 '저장 종가(네이버 계열 · 분배락 조정 흔적 · 총수익 여부 미확정)'입니다.",
    "겹치는 20일 창을 독립 표본으로 보지 않으므로 신뢰구간 · 성공률 · 확률을 표시하지 않습니다.",
    "이미 살펴본 과거 자료로 다시 계산한 연구이며 새로운 확증 시험이 아닙니다.",
    "알림이 도움이 됐는지 · 특정 거래가 적절했는지를 판정하지 않습니다.",
    "연구 추정 · 투자 유효성 미확정",
    "이 값은 매수/매도 지시가 아닙니다."
  ],
  "runtime_seconds": 0.006,
  "artifact": {
    "folder": "state/ml/research/poc5_06/20261010T170501_638017bd",
    "files": "review.json · input_snapshot.json"
  }
} as unknown as ReentryMlResponse;
