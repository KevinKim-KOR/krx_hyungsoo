import { fetchFastApiJson } from "./internal-api";

type SnapshotAccountItem = {
  account_id: string;
  account_name: string;
  order: number;
  total_assets: number;
  total_principal: number;
  cash_balance: number;
  valuation_krw: number;
};

type SnapshotListItem = {
  id: string;
  snapshot_date: string;
  total_assets: number;
  total_principal: number;
  cash_balance: number;
  valuation_krw: number;
  account_count: number;
  accounts: SnapshotAccountItem[];
};

export async function loadSnapshotList(): Promise<SnapshotListItem[]> {
  const payload = await fetchFastApiJson<{ snapshots: SnapshotListItem[] }>("/internal/snapshots");
  return payload.snapshots ?? [];
}

export type { SnapshotAccountItem, SnapshotListItem };
