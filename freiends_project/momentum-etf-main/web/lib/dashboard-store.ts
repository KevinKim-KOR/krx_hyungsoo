import { fetchFastApiJson } from "./internal-api";

type DashboardMetricItem = {
  label: string;
  value: number;
  kind: "money" | "percent";
};

type DashboardAccountSummaryItem = {
  account_id: string;
  account_name: string;
  account_url?: string | null;
  order: number;
  total_assets: number;
  total_principal: number;
  valuation_krw: number;
  cash_balance: number;
  cash_ratio: number;
  net_profit: number;
  net_profit_pct: number;
};

type DashboardBucketItem = {
  label: string;
  weight_pct: number;
};

type DashboardData = {
  metrics_row1: DashboardMetricItem[];
  metrics_row2: DashboardMetricItem[];
  accounts: DashboardAccountSummaryItem[];
  buckets: DashboardBucketItem[];
  sparklines: Record<string, Array<{ date: string; value: number }>>;
  latest_snapshot_date: string | null;
  weekly_date: string | null;
  updated_at: string | null;
};

export async function loadDashboardData(): Promise<DashboardData> {
  return fetchFastApiJson<DashboardData>("/internal/dashboard");
}

export type { DashboardData };
