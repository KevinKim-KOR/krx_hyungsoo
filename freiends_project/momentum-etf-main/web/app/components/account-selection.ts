const MOMENTUM_ETF_ACCOUNT_KEY = "momentum-etf:selected-account-id";
const MOMENTUM_ETF_TICKER_TYPE_KEY = "momentum-etf:selected-ticker-type";

export function readRememberedMomentumEtfAccountId(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const value = window.localStorage.getItem(MOMENTUM_ETF_ACCOUNT_KEY);
  return value && value.trim() ? value : null;
}

export function writeRememberedMomentumEtfAccountId(accountId: string | null | undefined) {
  if (typeof window === "undefined") {
    return;
  }

  if (!accountId || !accountId.trim()) {
    window.localStorage.removeItem(MOMENTUM_ETF_ACCOUNT_KEY);
    return;
  }

  window.localStorage.setItem(MOMENTUM_ETF_ACCOUNT_KEY, accountId.trim());
}

export function readRememberedTickerType(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const value = window.localStorage.getItem(MOMENTUM_ETF_TICKER_TYPE_KEY);
  return value && value.trim() ? value : null;
}

export function writeRememberedTickerType(tickerType: string | null | undefined) {
  if (typeof window === "undefined") {
    return;
  }

  if (!tickerType || !tickerType.trim()) {
    window.localStorage.removeItem(MOMENTUM_ETF_TICKER_TYPE_KEY);
    return;
  }

  window.localStorage.setItem(MOMENTUM_ETF_TICKER_TYPE_KEY, tickerType.trim());
}
