"use client";

export type RecentTickerSearchItem = {
  ticker: string;
  name: string;
  ticker_type: string;
  country_code: string;
  current_price: number | null;
  change_pct: number | null;
};

export const RECENT_TICKER_SEARCHES_KEY = "momentum-etf:recent-ticker-searches";
export const RECENT_TICKER_SEARCHES_LIMIT = 6;

export function loadRecentTickerSearches(): RecentTickerSearchItem[] {
  if (typeof window === "undefined") {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(RECENT_TICKER_SEARCHES_KEY);
    if (!raw) {
      return [];
    }
    const parsed = JSON.parse(raw) as RecentTickerSearchItem[];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed;
  } catch {
    return [];
  }
}

export function persistRecentTickerSearch(item: RecentTickerSearchItem): RecentTickerSearchItem[] {
  const nextItems = [
    item,
    ...loadRecentTickerSearches().filter(
      (entry) => !(entry.ticker === item.ticker && entry.ticker_type === item.ticker_type),
    ),
  ].slice(0, RECENT_TICKER_SEARCHES_LIMIT);

  if (typeof window !== "undefined") {
    window.localStorage.setItem(RECENT_TICKER_SEARCHES_KEY, JSON.stringify(nextItems));
  }
  return nextItems;
}
