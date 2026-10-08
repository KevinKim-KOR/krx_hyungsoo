// POC5-05 개정 2 — History · 시장 흐름 · 과거 보유 테스트 자료(테스트 전용 · 화면 코드가 import 하지 않는다).
// 실제 백엔드 출력 그대로다: 격리된 임시 보유 파일 · 임시 시세 DB(scratchpad)에 app/holdings_history.apply_command ·
// holdings_edit.save_full_list 로 매매 · 정정 · 취소 · 입력 정정을 저장한 뒤 holdings_history_view.history() ·
// holdings_market_flow.build_market_flow() 결과를 JSON 으로 옮겼다(라이브 보유 · 시세 DB 미사용).

import type { MarketFlowResponse, TradeHistoryResponse } from "@/lib/api";

// 보유 중 KODEX 200 · ISA(지난 기간: 최초 매수 → 추가매수 → 분할매도(정정됨) → 전량매도 /
// 현재 기간: 재매수 → 분할매도 · 취소한 추가매수 1건) · 과거 보유 TIGER 2차전지테마 · 일반(잔고 등록 →
// 입력 정정(수량 · 종목명) → 입력 정정 종료) · 과거 보유 SK하이닉스 · 연금(잔고 등록 → 전량매도).

export const HISTORY: TradeHistoryResponse = {
  "status": "V2", "revision": 14,
  "positions": [
    {
      "position_id": "18fa64c5-a1f2-4d9c-93ae-aa48edcec61c", "ticker": "069500", "name": "KODEX 200", "account_group": "ISA", "is_open": true,
      "cycles": [
        {
          "cycle_id": "ab1c6b93-f476-4eca-a598-d2df9769b47a", "status": "CLOSED", "opened_by": "BUY", "closed_by": "SELL", "start_date": "2026-03-02",
          "end_date": "2026-05-20", "has_adjustment": false, "quantity": "0", "cost": "0", "avg_buy_price": null, "realized_pnl": "8000",
          "sold_cost": "160000", "realized_rate": "5",
          "events": [
            {
              "record_id": "06b8e992-7c10-4fed-8282-92b7ecd3a9d2", "kind": "BUY", "recorded_at": "2026-10-08T16:10:01+09:00", "supersedes_id": null,
              "payload": {"trade_date": "2026-03-02", "trade_time": "09:31", "price": "10000", "quantity": "10", "amount": "100000", "memo": "첫 매수", "seq": 0},
              "date": "2026-03-02", "cost_of_sold": null, "realized_pnl": null, "realized_rate": null, "q_after": "10", "c_after": "100000",
              "avg_after": "10000", "previous": []
            },
            {
              "record_id": "840bf9da-d205-4b5d-a10e-4b1dfdd30193", "kind": "BUY", "recorded_at": "2026-10-08T16:10:01+09:00", "supersedes_id": null,
              "payload": {"trade_date": "2026-04-15", "trade_time": null, "price": "12000", "quantity": "5", "amount": "60000", "memo": null, "seq": 0},
              "date": "2026-04-15", "cost_of_sold": null, "realized_pnl": null, "realized_rate": null, "q_after": "15", "c_after": "160000",
              "avg_after": "10666.66666666666666666666667", "previous": []
            },
            {
              "record_id": "833688d8-01dc-478a-bfd4-afe2c2525ca1", "kind": "SELL", "recorded_at": "2026-10-08T16:10:01+09:00",
              "supersedes_id": "3d4583b7-6a57-45d1-873b-3513d938fd6a",
              "payload": {"trade_date": "2026-05-06", "trade_time": null, "price": "13000", "quantity": "6", "amount": "78000", "memo": null, "seq": 0},
              "date": "2026-05-06", "cost_of_sold": "64000", "realized_pnl": "14000", "realized_rate": "21.875", "q_after": "9", "c_after": "96000",
              "avg_after": "10666.66666666666666666666667",
              "previous": [
                {
                  "record_id": "3d4583b7-6a57-45d1-873b-3513d938fd6a", "kind": "SELL", "recorded_at": "2026-10-08T16:10:01+09:00",
                  "supersedes_id": null,
                  "payload": {"trade_date": "2026-05-06", "trade_time": null, "price": "13000", "quantity": "7", "amount": "91000", "memo": null, "seq": 0}
                }
              ]
            },
            {
              "record_id": "287929dc-fb30-4c60-9b47-670a1749a25c", "kind": "SELL", "recorded_at": "2026-10-08T16:10:01+09:00", "supersedes_id": null,
              "payload": {"trade_date": "2026-05-20", "trade_time": null, "price": "10000", "quantity": "9", "amount": "90000", "memo": null, "seq": 0},
              "date": "2026-05-20", "cost_of_sold": "96000", "realized_pnl": "-6000", "realized_rate": "-6.25", "q_after": "0", "c_after": "0",
              "avg_after": null, "previous": []
            }
          ],
          "voided": []
        },
        {
          "cycle_id": "fa7de9dc-5ad7-4a51-98f2-96b05feb72b4", "status": "OPEN", "opened_by": "BUY", "closed_by": null, "start_date": "2026-09-24",
          "end_date": null, "has_adjustment": false, "quantity": "7", "cost": "70000", "avg_buy_price": "10000", "realized_pnl": "6000",
          "sold_cost": "30000", "realized_rate": "20",
          "events": [
            {
              "record_id": "7ea9caa0-46d7-401a-a557-d887f04aa4d7", "kind": "BUY", "recorded_at": "2026-10-08T16:10:01+09:00", "supersedes_id": null,
              "payload": {"trade_date": "2026-09-24", "trade_time": "10:42", "price": "10000", "quantity": "10", "amount": "100000", "memo": null, "seq": 0},
              "date": "2026-09-24", "cost_of_sold": null, "realized_pnl": null, "realized_rate": null, "q_after": "10", "c_after": "100000",
              "avg_after": "10000", "previous": []
            },
            {
              "record_id": "880accc4-7674-4e80-9282-d8efa4a5eafb", "kind": "SELL", "recorded_at": "2026-10-08T16:10:01+09:00", "supersedes_id": null,
              "payload": {"trade_date": "2026-09-30", "trade_time": null, "price": "12000", "quantity": "3", "amount": "36000", "memo": null, "seq": 0},
              "date": "2026-09-30", "cost_of_sold": "30000", "realized_pnl": "6000", "realized_rate": "20", "q_after": "7", "c_after": "70000",
              "avg_after": "10000", "previous": []
            }
          ],
          "voided": [
            {
              "record_id": "7517e701-57f5-49eb-8844-e3441354496a", "kind": "BUY", "recorded_at": "2026-10-08T16:10:01+09:00", "supersedes_id": null,
              "payload": {"trade_date": "2026-09-25", "trade_time": null, "price": "11000", "quantity": "2", "amount": "22000", "memo": null, "seq": 0},
              "voided_at": "2026-10-08T16:10:01+09:00"
            }
          ]
        }
      ]
    },
    {
      "position_id": "036301df-ecc9-41f2-9022-48804bb482a8", "ticker": "305540", "name": "TIGER 2차전지테마", "account_group": "일반", "is_open": false,
      "cycles": [
        {
          "cycle_id": "e1ae26b7-b86c-4275-8add-4bf6de0420b9", "status": "CLOSED", "opened_by": "REGISTER", "closed_by": "ADJUSTMENT",
          "start_date": null, "end_date": "2026-10-08", "has_adjustment": true, "quantity": "0", "cost": "0", "avg_buy_price": null,
          "realized_pnl": "0", "sold_cost": "0", "realized_rate": null,
          "events": [
            {
              "record_id": "d177e785-88b6-42d9-ba7e-79b2c97d8663", "kind": "REGISTER", "recorded_at": "2026-10-08T16:10:01+09:00",
              "supersedes_id": null, "payload": {"quantity": "100", "avg_buy_price": "10000"}, "date": null, "cost_of_sold": null,
              "realized_pnl": null, "realized_rate": null, "q_after": "100", "c_after": "1000000", "avg_after": "10000", "previous": []
            },
            {
              "record_id": "c353914b-3b30-4107-b583-1bd314a63ffd", "kind": "ADJUSTMENT", "recorded_at": "2026-10-08T16:10:01+09:00",
              "supersedes_id": null,
              "payload": {
                "effective_date": "2026-10-08", "seq": 0, "quantity": "80", "avg_buy_price": "10000", "name": "TIGER 2차전지테마",
                "before": {"quantity": "100", "avg_buy_price": "10000", "name": "TIGER 2차전지"}
              },
              "date": "2026-10-08", "cost_of_sold": null, "realized_pnl": null, "realized_rate": null, "q_after": "80", "c_after": "800000",
              "avg_after": "10000", "previous": []
            },
            {
              "record_id": "3a4fc1c6-12ad-452b-bd89-925658ad152b", "kind": "ADJUSTMENT", "recorded_at": "2026-10-08T16:10:01+09:00",
              "supersedes_id": null,
              "payload": {
                "effective_date": "2026-10-08", "seq": 1, "quantity": "0", "avg_buy_price": "10000",
                "before": {"quantity": "80", "avg_buy_price": "10000"}
              },
              "date": "2026-10-08", "cost_of_sold": null, "realized_pnl": null, "realized_rate": null, "q_after": "0", "c_after": "0",
              "avg_after": null, "previous": []
            }
          ],
          "voided": []
        }
      ]
    },
    {
      "position_id": "f993a164-18fe-4ea3-8414-1928c2be6b18", "ticker": "000660", "name": "SK하이닉스", "account_group": "연금", "is_open": false,
      "cycles": [
        {
          "cycle_id": "8a801a6c-aecf-4f7d-91e8-d2c22bf65d2f", "status": "CLOSED", "opened_by": "REGISTER", "closed_by": "SELL", "start_date": null,
          "end_date": "2026-09-30", "has_adjustment": false, "quantity": "0", "cost": "0", "avg_buy_price": null, "realized_pnl": "186000",
          "sold_cost": "1500000", "realized_rate": "12.4",
          "events": [
            {
              "record_id": "ccfa745d-e6bc-4f61-9c8a-3a3ab68a7a6a", "kind": "REGISTER", "recorded_at": "2026-10-08T16:10:01+09:00",
              "supersedes_id": null, "payload": {"quantity": "10", "avg_buy_price": "150000"}, "date": null, "cost_of_sold": null,
              "realized_pnl": null, "realized_rate": null, "q_after": "10", "c_after": "1500000", "avg_after": "150000", "previous": []
            },
            {
              "record_id": "bb5d40e7-cfbd-4b8b-a823-a393a4116ab5", "kind": "SELL", "recorded_at": "2026-10-08T16:10:01+09:00", "supersedes_id": null,
              "payload": {"trade_date": "2026-09-30", "trade_time": null, "price": "168600", "quantity": "10", "amount": "1686000", "memo": null, "seq": 0},
              "date": "2026-09-30", "cost_of_sold": "1500000", "realized_pnl": "186000", "realized_rate": "12.4", "q_after": "0", "c_after": "0",
              "avg_after": null, "previous": []
            }
          ],
          "voided": []
        }
      ]
    }
  ]
};

// V1 파일(기록 시작 전 · 저장되지 않은 기준잔고) TIGER 미국S&P500 · 일반.
export const HISTORY_V1: TradeHistoryResponse = {
  "status": "V1", "revision": 0,
  "positions": [
    {
      "position_id": "9730953d-ce4a-5734-853b-7d13ce6856a3", "ticker": "360750", "name": "TIGER 미국S&P500", "account_group": "일반", "is_open": true,
      "cycles": [
        {
          "cycle_id": "a99791af-7d76-59ba-b26d-196a12addbcd", "status": "OPEN", "opened_by": "BASELINE", "closed_by": null, "start_date": null,
          "end_date": null, "has_adjustment": false, "quantity": "40", "cost": "855400", "avg_buy_price": "21385", "realized_pnl": "0",
          "sold_cost": "0", "realized_rate": null,
          "events": [
            {
              "record_id": "c77603f2-bf00-562e-b5ae-fdff118901d8", "kind": "BASELINE", "recorded_at": null, "supersedes_id": null,
              "payload": {"quantity": "40", "avg_buy_price": "21385"}, "date": null, "cost_of_sold": null, "realized_pnl": null, "realized_rate": null,
              "q_after": "40", "c_after": "855400", "avg_after": "21385", "previous": []
            }
          ],
          "voided": []
        }
      ]
    }
  ]
};

// 시장 흐름 — ETF 기간(실제 매수로 시작 · 종료): 출처 다름 OK · 비교 불가 · 자료 없음 · 같은 출처 OK ·
// 보유 기간 OK(출처 다름). 개별주(잔고 등록 · 종료): 개별주 미수집 · 매수일 미상.
// 응답에는 화면 타입에 없는 필드(schema · series · free_commentary 등)도 그대로 둔다.
export const FLOW_ETF = {
  "schema": "holdings_market_flow_v1", "read_only": true, "ticker": "069500", "cycle_id": "c-closed", "opened_by": "BUY", "cycle_status": "CLOSED",
  "purchase_date_unknown": false, "purchase_date_note": null, "db_present": true, "asset_kind": "ETF",
  "series": {
    "ticker": {"table": "etf_daily_price", "series_name": "ETF 저장 종가", "comparable_sources": ["FinanceDataReader", "NAVER_FDR"]},
    "market": {
      "table": "market_benchmark_daily_price", "benchmark_id": "KOSPI", "series_name": "KOSPI 저장 종가",
      "comparable_sources": ["FinanceDataReader/KS11", "KRX_OPEN_API/idx_kospi_dd_trd", "NAVER_FDR"]
    }
  },
  "latest_stored_date": "2026-10-02", "latest_stored_close": 11832.0, "latest_stored_source": "FinanceDataReader",
  "events": [
    {
      "record_id": "r1", "kind": "BUY", "trade_date": "2026-03-02",
      "basis": {
        "trade_date": "2026-03-02", "trade_date_is_trading_day": false, "trade_date_decided_by": "snapshot", "basis_date": "2026-03-03",
        "basis_date_decided_by": "snapshot", "moved_to_next_trading_day": true, "basis_note": "비거래일(연도 파일) → 다음 거래일(연도 파일)"
      },
      "window_label": "매수 기준일 → 마지막 저장일", "latest_stored_date": "2026-10-02",
      "ticker": {
        "series": "ETF", "series_name": "ETF 저장 종가", "table": "etf_daily_price", "status": "OK", "reason_code": null, "reason": null,
        "start_date": "2026-03-03", "end_date": "2026-10-02", "start": {"date": "2026-03-03", "close": 10000.0, "source": "NAVER_FDR"},
        "end": {"date": "2026-10-02", "close": 11832.0, "source": "FinanceDataReader"}, "change_pct": "18.32", "source_differs": true
      },
      "market": {
        "series": "KOSPI", "series_name": "KOSPI 저장 종가", "table": "market_benchmark_daily_price", "status": "OK", "reason_code": null, "reason": null,
        "start_date": "2026-03-03", "end_date": "2026-10-02", "start": {"date": "2026-03-03", "close": 6000.0, "source": "NAVER_FDR"},
        "end": {"date": "2026-10-02", "close": 6600.0, "source": "KRX_OPEN_API/idx_kospi_dd_trd"}, "change_pct": "10", "source_differs": true
      }
    },
    {
      "record_id": "r2", "kind": "BUY", "trade_date": "2026-04-15",
      "basis": {
        "trade_date": "2026-04-15", "trade_date_is_trading_day": true, "trade_date_decided_by": "snapshot", "basis_date": "2026-04-15",
        "basis_date_decided_by": "snapshot", "moved_to_next_trading_day": false, "basis_note": "거래일 그대로(연도 파일)"
      },
      "window_label": "매수 기준일 → 마지막 저장일", "latest_stored_date": "2026-10-02",
      "ticker": {
        "series": "ETF", "series_name": "ETF 저장 종가", "table": "etf_daily_price", "status": "NOT_COMPARABLE", "reason_code": "SOURCE_UNVERIFIED",
        "reason": "비교 불가(가격 기준 확인 안 됨)", "start_date": "2026-04-15", "end_date": "2026-10-02",
        "start": {"date": "2026-04-15", "close": 11800.0, "source": "KRX_UNADJ"},
        "end": {"date": "2026-10-02", "close": 11832.0, "source": "FinanceDataReader"}, "change_pct": null, "source_differs": true
      },
      "market": {
        "series": "KOSPI", "series_name": "KOSPI 저장 종가", "table": "market_benchmark_daily_price", "status": "OK", "reason_code": null, "reason": null,
        "start_date": "2026-04-15", "end_date": "2026-10-02", "start": {"date": "2026-04-15", "close": 6100.0, "source": "NAVER_FDR"},
        "end": {"date": "2026-10-02", "close": 6600.0, "source": "KRX_OPEN_API/idx_kospi_dd_trd"},
        "change_pct": "8.196721311475409836065573770491803278689", "source_differs": true
      }
    },
    {
      "record_id": "r3", "kind": "SELL", "trade_date": "2026-05-06",
      "basis": {
        "trade_date": "2026-05-06", "trade_date_is_trading_day": true, "trade_date_decided_by": "snapshot", "basis_date": "2026-05-06",
        "basis_date_decided_by": "snapshot", "moved_to_next_trading_day": false, "basis_note": "거래일 그대로(연도 파일)"
      },
      "window_label": "매도 기준일 → 마지막 저장일", "latest_stored_date": "2026-10-02",
      "ticker": {
        "series": "ETF", "series_name": "ETF 저장 종가", "table": "etf_daily_price", "status": "NO_DATA", "reason_code": "BASIS_ROW_MISSING",
        "reason": "자료 없음(기준일 종가 없음 · 인접일 대체 안 함)", "start_date": "2026-05-06", "end_date": "2026-10-02", "start": null,
        "end": {"date": "2026-10-02", "close": 11832.0, "source": "FinanceDataReader"}, "change_pct": null, "source_differs": false
      },
      "market": {
        "series": "KOSPI", "series_name": "KOSPI 저장 종가", "table": "market_benchmark_daily_price", "status": "NO_DATA",
        "reason_code": "BASIS_ROW_MISSING", "reason": "자료 없음(기준일 종가 없음 · 인접일 대체 안 함)", "start_date": "2026-05-06", "end_date": "2026-10-02",
        "start": null, "end": {"date": "2026-10-02", "close": 6600.0, "source": "KRX_OPEN_API/idx_kospi_dd_trd"}, "change_pct": null,
        "source_differs": false
      }
    },
    {
      "record_id": "r4", "kind": "SELL", "trade_date": "2026-05-20",
      "basis": {
        "trade_date": "2026-05-20", "trade_date_is_trading_day": true, "trade_date_decided_by": "snapshot", "basis_date": "2026-05-20",
        "basis_date_decided_by": "snapshot", "moved_to_next_trading_day": false, "basis_note": "거래일 그대로(연도 파일)"
      },
      "window_label": "매도 기준일 → 마지막 저장일", "latest_stored_date": "2026-10-02",
      "ticker": {
        "series": "ETF", "series_name": "ETF 저장 종가", "table": "etf_daily_price", "status": "OK", "reason_code": null, "reason": null,
        "start_date": "2026-05-20", "end_date": "2026-10-02", "start": {"date": "2026-05-20", "close": 10640.0, "source": "FinanceDataReader"},
        "end": {"date": "2026-10-02", "close": 11832.0, "source": "FinanceDataReader"}, "change_pct": "11.2030075187969924812030075187969924812",
        "source_differs": false
      },
      "market": {
        "series": "KOSPI", "series_name": "KOSPI 저장 종가", "table": "market_benchmark_daily_price", "status": "OK", "reason_code": null, "reason": null,
        "start_date": "2026-05-20", "end_date": "2026-10-02",
        "start": {"date": "2026-05-20", "close": 6246.0, "source": "KRX_OPEN_API/idx_kospi_dd_trd"},
        "end": {"date": "2026-10-02", "close": 6600.0, "source": "KRX_OPEN_API/idx_kospi_dd_trd"},
        "change_pct": "5.667627281460134486071085494716618635927", "source_differs": false
      }
    }
  ],
  "holding_period": {
    "reason_code": null, "reason": null, "start_record_id": "r1", "end_record_id": "r4",
    "start_basis": {
      "trade_date": "2026-03-02", "trade_date_is_trading_day": false, "trade_date_decided_by": "snapshot", "basis_date": "2026-03-03",
      "basis_date_decided_by": "snapshot", "moved_to_next_trading_day": true, "basis_note": "비거래일(연도 파일) → 다음 거래일(연도 파일)"
    },
    "end_basis": {
      "trade_date": "2026-05-20", "trade_date_is_trading_day": true, "trade_date_decided_by": "snapshot", "basis_date": "2026-05-20",
      "basis_date_decided_by": "snapshot", "moved_to_next_trading_day": false, "basis_note": "거래일 그대로(연도 파일)"
    },
    "ticker": {
      "series": "ETF", "series_name": "ETF 저장 종가", "table": "etf_daily_price", "status": "OK", "reason_code": null, "reason": null,
      "start_date": "2026-03-03", "end_date": "2026-05-20", "start": {"date": "2026-03-03", "close": 10000.0, "source": "NAVER_FDR"},
      "end": {"date": "2026-05-20", "close": 10640.0, "source": "FinanceDataReader"}, "change_pct": "6.4", "source_differs": true
    },
    "market": {
      "series": "KOSPI", "series_name": "KOSPI 저장 종가", "table": "market_benchmark_daily_price", "status": "OK", "reason_code": null, "reason": null,
      "start_date": "2026-03-03", "end_date": "2026-05-20", "start": {"date": "2026-03-03", "close": 6000.0, "source": "NAVER_FDR"},
      "end": {"date": "2026-05-20", "close": 6246.0, "source": "KRX_OPEN_API/idx_kospi_dd_trd"}, "change_pct": "4.1", "source_differs": true
    },
    "computed": true, "window_label": "첫 매수 기준일 → 마지막 매도 기준일"
  },
  "notes": [
    "저장 종가 비교값 — 체결단가로 계산한 개인 손익과 다르다.",
    "마지막 저장일은 PC 시세 DB 에 저장된 마지막 날짜이며 오늘 시세가 아니다.",
    "기준일 종가가 없으면 인접일 · 다른 계열로 메우지 않는다.",
    "정형 값만 제공 — 자유 생성 코멘트 · 모델 판단 없음."
  ],
  "free_commentary": null
} as unknown as MarketFlowResponse;

export const FLOW_STOCK = {
  "schema": "holdings_market_flow_v1", "read_only": true, "ticker": "000660", "cycle_id": "c-reg", "opened_by": "REGISTER", "cycle_status": "CLOSED",
  "purchase_date_unknown": true, "purchase_date_note": "매수일 미상 — 매수 전후 변화 계산 안 함", "db_present": true, "asset_kind": "STOCK",
  "series": {
    "ticker": {"table": "etf_daily_price", "series_name": "ETF 저장 종가", "comparable_sources": ["FinanceDataReader", "NAVER_FDR"]},
    "market": {
      "table": "market_benchmark_daily_price", "benchmark_id": "KOSPI", "series_name": "KOSPI 저장 종가",
      "comparable_sources": ["FinanceDataReader/KS11", "KRX_OPEN_API/idx_kospi_dd_trd", "NAVER_FDR"]
    }
  },
  "latest_stored_date": null, "latest_stored_close": null, "latest_stored_source": null,
  "events": [
    {
      "record_id": "r5", "kind": "SELL", "trade_date": "2026-09-30",
      "basis": {
        "trade_date": "2026-09-30", "trade_date_is_trading_day": true, "trade_date_decided_by": "snapshot", "basis_date": "2026-09-30",
        "basis_date_decided_by": "snapshot", "moved_to_next_trading_day": false, "basis_note": "거래일 그대로(연도 파일)"
      },
      "window_label": "매도 기준일 → 마지막 저장일", "latest_stored_date": null,
      "ticker": {
        "series": "ETF", "series_name": "ETF 저장 종가", "table": "etf_daily_price", "status": "NO_DATA", "reason_code": "STOCK_NOT_COLLECTED",
        "reason": "자료 없음(PC 개별주 일별 종가 미수집)", "start_date": "2026-09-30", "end_date": null, "start": null, "end": null, "change_pct": null,
        "source_differs": false
      },
      "market": {
        "series": "KOSPI", "series_name": "KOSPI 저장 종가", "table": "market_benchmark_daily_price", "status": "NO_DATA", "reason_code": "NO_WINDOW",
        "reason": "자료 없음(종목 비교 구간 없음)", "start_date": "2026-09-30", "end_date": null, "start": null, "end": null, "change_pct": null,
        "source_differs": false
      }
    }
  ],
  "holding_period": {
    "reason_code": "PURCHASE_DATE_UNKNOWN", "reason": "매수일 미상 — 매수 전후 변화 계산 안 함", "start_record_id": null, "end_record_id": null, "start_basis": null,
    "end_basis": null, "ticker": null, "market": null, "computed": false, "window_label": "첫 매수 기준일 → 마지막 매도 기준일"
  },
  "notes": [
    "저장 종가 비교값 — 체결단가로 계산한 개인 손익과 다르다.",
    "마지막 저장일은 PC 시세 DB 에 저장된 마지막 날짜이며 오늘 시세가 아니다.",
    "기준일 종가가 없으면 인접일 · 다른 계열로 메우지 않는다.",
    "정형 값만 제공 — 자유 생성 코멘트 · 모델 판단 없음."
  ],
  "free_commentary": null
} as unknown as MarketFlowResponse;
