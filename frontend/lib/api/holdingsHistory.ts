// POC5-05 개정 2 — 보유 · 매매 이력(PC 로컬 API).
//   GET  /holdings/trade-history              position 별 보유 기간 · 기록 · 계산값(쓰기 0)
//   PUT  /holdings/trade-history              매매 명령 한 번 → 현재 보유와 이력이 같이 바뀐다
//   GET  /holdings/trade-history/market-flow  사용자가 누를 때만 · PC 저장 종가 요약
// 숫자는 백엔드가 Decimal 로 계산한 십진 문자열이다(화면 반올림은 표시용으로만 쓴다).
// 오류 detail 은 문자열(422 입력 오류 · 409 충돌/새로고침 · 404 없음 · 500 파일/시세 DB).

import { request } from "./core";
import type { HoldingItem } from "./holdings";

export type TradeRecordKind =
  | "BASELINE"
  | "REGISTER"
  | "BUY"
  | "SELL"
  | "ADJUSTMENT"
  | "VOID";

export interface TradeRecordView {
  record_id: string;
  kind: TradeRecordKind;
  recorded_at: string | null; // null = 기록 시작 전(저장되지 않은 기준잔고)
  supersedes_id: string | null;
  payload: Record<string, unknown>;
}

export interface TradeEventView extends TradeRecordView {
  date: string | null;
  cost_of_sold: string | null;
  realized_pnl: string | null;
  realized_rate: string | null;
  q_after: string | null;
  c_after: string | null;
  avg_after: string | null;
  previous: TradeRecordView[];
}

export interface HoldingCycleView {
  cycle_id: string;
  status: "OPEN" | "CLOSED";
  opened_by: "BASELINE" | "REGISTER" | "BUY";
  closed_by: "SELL" | "ADJUSTMENT" | null;
  start_date: string | null; // null = 매수일 미상
  end_date: string | null;
  has_adjustment: boolean;
  quantity: string;
  cost: string;
  avg_buy_price: string | null;
  realized_pnl: string;
  sold_cost: string;
  realized_rate: string | null;
  events: TradeEventView[];
  voided: (TradeRecordView & { voided_at: string | null })[];
}

export interface PositionHistory {
  position_id: string;
  ticker: string;
  name: string | null;
  account_group: string;
  is_open: boolean;
  cycles: HoldingCycleView[];
  // 줄 단위 취소 기록(기간의 매매가 모두 취소돼 기간이 빠져도 남는다).
  voided?: (TradeRecordView & { voided_at: string | null })[];
}

export interface TradeHistoryResponse {
  status: "NO_FILE" | "V1" | "V2";
  revision: number;
  positions: PositionHistory[];
}

export function fetchTradeHistory(positionId?: string): Promise<TradeHistoryResponse> {
  const q = positionId ? `?position_id=${encodeURIComponent(positionId)}` : "";
  return request<TradeHistoryResponse>("GET", `/holdings/trade-history${q}`);
}

export type TradeAction =
  | "buy"
  | "sell"
  | "sell_all"
  | "new_position"
  | "register"
  | "correct"
  | "void";

export interface TradeInput {
  trade_date: string;
  trade_time?: string | null;
  price: string;
  quantity: string;
  memo?: string | null;
}

export interface TradeCommand {
  record_id: string; // 저장 동작마다 새 UUID · 같은 내용의 재시도에는 같은 값
  base_revision: number;
  action: TradeAction;
  position_id?: string | null;
  ticker?: string;
  account_group?: string | null;
  name?: string | null;
  trade?: TradeInput;
  holding?: { quantity: string; avg_buy_price: string };
  same_day?: "after" | "before";
  supersedes_id?: string;
}

export interface TradeCommandResult {
  record: TradeRecordView & { position_id: string; cycle_id: string };
  holdings: HoldingItem[];
  revision: number;
}

export function putTradeCommand(cmd: TradeCommand): Promise<TradeCommandResult> {
  return request<TradeCommandResult>("PUT", "/holdings/trade-history", cmd);
}

// ─── 시장 흐름(저장 종가 · 정형 값 · 누를 때만) ─────────────────────────

export interface MarketFlowEndpoint {
  date: string;
  close: number | string;
  source: string | null;
}

export interface MarketFlowSeriesItem {
  series: string;
  series_name: string;
  table: string;
  status: "OK" | "NO_DATA" | "NOT_COMPARABLE";
  reason_code: string | null;
  reason: string | null;
  start_date: string | null;
  end_date: string | null;
  start: MarketFlowEndpoint | null;
  end: MarketFlowEndpoint | null;
  change_pct: string | null;
  source_differs: boolean;
}

export interface MarketFlowBasis {
  trade_date: string;
  trade_date_is_trading_day: boolean;
  trade_date_decided_by: string;
  basis_date: string | null;
  basis_date_decided_by: string | null;
  moved_to_next_trading_day: boolean;
  basis_note: string;
}

export interface MarketFlowEvent {
  record_id: string;
  kind: "BUY" | "SELL";
  trade_date: string;
  basis: MarketFlowBasis;
  window_label: string;
  latest_stored_date: string | null;
  ticker: MarketFlowSeriesItem;
  market: MarketFlowSeriesItem;
}

export interface MarketFlowPeriod {
  reason_code: string | null; // PURCHASE_DATE_UNKNOWN · CYCLE_OPEN · NO_BUY · NO_SELL
  reason: string | null;
  start_basis?: MarketFlowBasis | null;
  end_basis?: MarketFlowBasis | null;
  ticker?: MarketFlowSeriesItem | null;
  market?: MarketFlowSeriesItem | null;
}

export interface MarketFlowResponse {
  ticker: string;
  cycle_id: string;
  opened_by: string;
  cycle_status: string;
  purchase_date_unknown: boolean;
  purchase_date_note: string | null;
  db_present: boolean;
  asset_kind: string;
  latest_stored_date: string | null;
  events: MarketFlowEvent[];
  holding_period: MarketFlowPeriod | null;
  notes: string[];
}

export function fetchMarketFlow(
  positionId: string,
  cycleId: string,
): Promise<MarketFlowResponse> {
  const q = `position_id=${encodeURIComponent(positionId)}&cycle_id=${encodeURIComponent(cycleId)}`;
  return request<MarketFlowResponse>("GET", `/holdings/trade-history/market-flow?${q}`);
}
