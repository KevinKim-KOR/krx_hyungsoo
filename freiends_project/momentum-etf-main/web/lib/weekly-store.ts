import { fetchFastApiJson } from "./internal-api";

type WeeklyEditableField = {
  key: string;
  label: string;
  type: "int" | "float" | "text";
};

type WeeklyRow = {
  week_date: string;
  week_date_display: string;
  withdrawal_personal: number;
  withdrawal_mom: number;
  nh_principal_interest: number;
  total_expense: number;
  deposit_withdrawal: number;
  total_principal: number;
  total_assets: number;
  purchase_amount: number;
  valuation_amount: number;
  profit_loss: number;
  cumulative_profit: number;
  weekly_profit: number;
  weekly_return_pct: number;
  cumulative_return_pct: number;
  memo: string;
  exchange_rate: number;
  exchange_rate_change_pct: number;
  bucket_pct_momentum: number;
  bucket_pct_market: number;
  bucket_pct_dividend: number;
  bucket_pct_alternative: number;
  bucket_pct_cash: number;
  total_stocks: number;
  profit_count: number;
  loss_count: number;
  updated_at: string | null;
};

type WeeklyTableData = {
  active_week_date: string;
  rows: WeeklyRow[];
  editable_fields: WeeklyEditableField[];
  core_hidden_keys: string[];
};

export async function loadWeeklyTableData(): Promise<WeeklyTableData> {
  return fetchFastApiJson<WeeklyTableData>("/internal/weekly");
}

export async function aggregateActiveWeekData(): Promise<{ week_date: string }> {
  return fetchFastApiJson<{ week_date: string }>("/internal/weekly", {
    method: "POST",
  });
}

export async function updateWeeklyRow(
  weekDate: string,
  payload: Record<string, unknown>,
): Promise<{ week_date: string }> {
  return fetchFastApiJson<{ week_date: string }>("/internal/weekly", {
    method: "PATCH",
    body: JSON.stringify({
      ...payload,
      week_date: weekDate,
    }),
  });
}

export type { WeeklyEditableField, WeeklyRow, WeeklyTableData };
