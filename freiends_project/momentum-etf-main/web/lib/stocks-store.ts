import { fetchFastApiJson } from "./internal-api";
import { BUCKET_NAME_MAP } from "./bucket-theme";

type StockMetaDoc = {
  ticker_type?: string;
  ticker?: string;
  name?: string;
  bucket?: number;
  added_date?: string;
  listing_date?: string;
  updated_at?: Date | string;
  ["1_week_avg_volume"]?: number;
  ["1_week_earn_rate"]?: number;
  ["2_week_earn_rate"]?: number;
  ["1_month_earn_rate"]?: number;
  ["3_month_earn_rate"]?: number;
  ["6_month_earn_rate"]?: number;
  ["12_month_earn_rate"]?: number;
};

type StocksAccountItem = {
  ticker_type: string;
  order: number;
  name: string;
  icon: string;
};

type StocksRowItem = {
  ticker: string;
  name: string;
  bucket_id: number;
  bucket_name: string;
  added_date: string;
  listing_date: string;
  week_volume: number | null;
  return_1d: number | null;
  return_1w: number | null;
  return_2w: number | null;
  return_1m: number | null;
  return_3m: number | null;
  return_6m: number | null;
  return_12m: number | null;
};

type StocksTableData = {
  ticker_types: StocksAccountItem[];
  rows: StocksRowItem[];
  ticker_type: string;
};

type StockValidationResult = {
  ticker: string;
  name: string;
  listing_date: string;
  status: "active" | "deleted" | "new";
  bucket_id: number;
  ticker_type: string;
  country_code: string;
};

type StockCreateResult = {
  ticker: string;
  name: string;
  listing_date: string;
  bucket_id: number;
  bucket_name: string;
  status: "active" | "deleted" | "new";
};

function normalizeNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function normalizeText(value: unknown, fallback = "-"): string {
  const text = String(value ?? "").trim();
  return text || fallback;
}

async function fetchClientJson<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  const payload = (await response.json().catch(() => ({}))) as { error?: string };
  if (!response.ok) {
    throw new Error(payload.error ?? `요청에 실패했습니다. (${response.status})`);
  }
  return payload as T;
}

export function getBucketOptions(): Array<{ id: number; name: string }> {
  return Object.entries(BUCKET_NAME_MAP)
    .filter(([id]) => Number(id) >= 1 && Number(id) <= 4)
    .map(([id, name]) => ({ id: Number(id), name }));
}

export async function loadStocksTable(tickerType?: string): Promise<StocksTableData> {
  if (typeof window !== "undefined") {
    return fetchClientJson<StocksTableData>(`/api/stocks${tickerType ? `?ticker_type=${encodeURIComponent(tickerType)}` : ""}`);
  }
  return fetchFastApiJson<StocksTableData>(
    `/internal/stocks${tickerType ? `?ticker_type=${encodeURIComponent(tickerType)}` : ""}`,
  );
}

export async function updateStockBucket(tickerType: string, ticker: string, bucketId: number): Promise<void> {
  if (typeof window !== "undefined") {
    await fetchClientJson("/api/stocks", {
      method: "PATCH",
      body: JSON.stringify({
        ticker_type: tickerType,
        ticker,
        bucket_id: bucketId,
      }),
    });
    return;
  }
  await fetchFastApiJson("/internal/stocks", {
    method: "PATCH",
    body: JSON.stringify({
      ticker_type: tickerType,
      ticker,
      bucket_id: bucketId,
    }),
  });
}

export async function deleteStock(tickerType: string, ticker: string): Promise<void> {
  if (typeof window !== "undefined") {
    await fetchClientJson("/api/stocks", {
      method: "DELETE",
      body: JSON.stringify({
        ticker_type: tickerType,
        ticker,
      }),
    });
    return;
  }
  await fetchFastApiJson("/internal/stocks", {
    method: "DELETE",
    body: JSON.stringify({
      ticker_type: tickerType,
      ticker,
    }),
  });
}

export async function validateStockCandidate(tickerType: string, ticker: string): Promise<StockValidationResult> {
  if (typeof window !== "undefined") {
    return fetchClientJson<StockValidationResult>("/api/stocks", {
      method: "POST",
      body: JSON.stringify({
        ticker_type: tickerType,
        ticker,
        action: "validate",
      }),
    });
  }
  return fetchFastApiJson<StockValidationResult>("/internal/stocks/validate", {
    method: "POST",
    body: JSON.stringify({
      ticker_type: tickerType,
      ticker,
    }),
  });
}

export async function addStockCandidate(tickerType: string, ticker: string, bucketId: number): Promise<StockCreateResult> {
  if (typeof window !== "undefined") {
    return fetchClientJson<StockCreateResult>("/api/stocks", {
      method: "POST",
      body: JSON.stringify({
        ticker_type: tickerType,
        ticker,
        bucket_id: bucketId,
        action: "create",
      }),
    });
  }
  return fetchFastApiJson<StockCreateResult>("/internal/stocks", {
    method: "POST",
    body: JSON.stringify({
      ticker_type: tickerType,
      ticker,
      bucket_id: bucketId,
    }),
  });
}

export async function refreshSingleStock(tickerType: string, ticker: string): Promise<{ ticker: string; ticker_type: string }> {
  if (typeof window !== "undefined") {
    return fetchClientJson<{ ticker: string; ticker_type: string }>("/api/stocks/refresh", {
      method: "POST",
      body: JSON.stringify({
        ticker_type: tickerType,
        ticker,
      }),
    });
  }
  return fetchFastApiJson<{ ticker: string; ticker_type: string }>("/internal/stocks/refresh", {
    method: "POST",
    body: JSON.stringify({
      ticker_type: tickerType,
      ticker,
    }),
  });
}

export type { StockCreateResult, StockValidationResult, StocksAccountItem, StocksRowItem, StocksTableData };
