"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { IconSearch, IconX } from "@tabler/icons-react";
import { AppLoadingState } from "@/app/components/AppLoadingState";
import {
  loadRecentTickerSearches,
  persistRecentTickerSearch,
  RECENT_TICKER_SEARCHES_KEY,
  type RecentTickerSearchItem,
} from "@/lib/recent-ticker-searches";

type TickerSearchItem = RecentTickerSearchItem;

type TickerSearchPayload = {
  tickers: TickerSearchItem[];
  top_movers_by_type: Array<{
    ticker_type: string;
    label: string;
    items: TickerSearchItem[];
  }>;
  top_movers_updated_at?: string | null;
  top_movers_pre_open?: boolean;
};

function formatPrice(value: number | null, countryCode: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }

  if (countryCode === "au") {
    return `A$${new Intl.NumberFormat("en-AU", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value)}`;
  }

  return `${new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 0 }).format(value)}원`;
}

function formatChangePct(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "-";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function getChangeClass(value: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "";
  }
  return value > 0 ? "metricPositive" : "metricNegative";
}

function formatTopMoversUpdatedAt(value: string | null | undefined, preOpen: boolean): string {
  const raw = String(value ?? "").trim();
  if (!raw) {
    return preOpen ? "급상승(장개시 이전)" : "급상승";
  }

  const date = new Date(raw);
  if (Number.isNaN(date.getTime())) {
    return preOpen ? "급상승(장개시 이전)" : "급상승";
  }

  const weekday = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    weekday: "short",
  }).format(date);
  const datePart = new Intl.DateTimeFormat("sv-SE", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(date);
  const dayPeriod = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    hour: "numeric",
    hour12: true,
  })
    .formatToParts(date)
    .find((part) => part.type === "dayPeriod")?.value;
  const timePart = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })
    .format(date)
    .replace(`${dayPeriod ?? ""} `, "")
    .trim();

  const suffix = `${datePart}(${weekday}) ${dayPeriod ?? ""} ${timePart} 기준`.replace(/\s+/g, " ").trim();
  if (preOpen) {
    return `급상승(장개시 이전 - ${suffix})`;
  }
  return `급상승(${suffix})`;
}

export function GlobalTickerSearch() {
  const router = useRouter();
  const pathname = usePathname();
  const [panelOpen, setPanelOpen] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [highlightIndex, setHighlightIndex] = useState(-1);
  const [allTickers, setAllTickers] = useState<TickerSearchItem[]>([]);
  const [topMoversByType, setTopMoversByType] = useState<TickerSearchPayload["top_movers_by_type"]>([]);
  const [topMoversUpdatedAt, setTopMoversUpdatedAt] = useState<string | null>(null);
  const [topMoversPreOpen, setTopMoversPreOpen] = useState(false);
  const [topMoversLoading, setTopMoversLoading] = useState(false);
  const [recentSearches, setRecentSearches] = useState<TickerSearchItem[]>([]);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLInputElement | null>(null);

  const fetchSearchData = useCallback(async (signal?: AbortSignal) => {
    setTopMoversLoading(true);
    try {
      const response = await fetch("/api/ticker-search-data", { cache: "no-store", signal });
      if (!response.ok) {
        return;
      }
      const payload = (await response.json()) as TickerSearchPayload;
      setAllTickers(Array.isArray(payload.tickers) ? payload.tickers : []);
      setTopMoversByType(Array.isArray(payload.top_movers_by_type) ? payload.top_movers_by_type : []);
      setTopMoversUpdatedAt(typeof payload.top_movers_updated_at === "string" ? payload.top_movers_updated_at : null);
      setTopMoversPreOpen(Boolean(payload.top_movers_pre_open));
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        return;
      }
      // 전역 검색은 실패 시 조용히 비활성화합니다.
    } finally {
      setTopMoversLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!panelOpen) {
      return;
    }

    const controller = new AbortController();
    void fetchSearchData(controller.signal);
    return () => controller.abort();
  }, [fetchSearchData, panelOpen]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      setRecentSearches(loadRecentTickerSearches());
    } catch {
      // localStorage 파싱 실패 시 무시합니다.
    }
  }, []);

  useEffect(() => {
    if (!panelOpen) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      inputRef.current?.focus();
    }, 60);

    return () => window.clearTimeout(timeoutId);
  }, [panelOpen]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) {
        setPanelOpen(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    setPanelOpen(false);
    setSearchInput("");
    setHighlightIndex(-1);
  }, [pathname]);

  const filteredTickers = useMemo(() => {
    const query = searchInput.trim().toLowerCase();
    if (!query) {
      return [];
    }

    return allTickers
      .filter((item) => item.ticker.toLowerCase().includes(query) || item.name.toLowerCase().includes(query))
      .slice(0, 20);
  }, [allTickers, searchInput]);

  function updateRecentSearches(item: TickerSearchItem) {
    setRecentSearches(persistRecentTickerSearch(item));
  }

  function navigateToTicker(item: TickerSearchItem) {
    updateRecentSearches(item);
    setSearchInput("");
    setHighlightIndex(-1);
    setPanelOpen(false);
    router.push(`/ticker?ticker=${encodeURIComponent(item.ticker)}`);
  }

  function removeRecentSearch(item: TickerSearchItem) {
    const nextItems = recentSearches.filter(
      (entry) => !(entry.ticker === item.ticker && entry.ticker_type === item.ticker_type),
    );
    setRecentSearches(nextItems);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(RECENT_TICKER_SEARCHES_KEY, JSON.stringify(nextItems));
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setHighlightIndex((prev) => Math.min(prev + 1, filteredTickers.length - 1));
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightIndex((prev) => Math.max(prev - 1, 0));
      return;
    }

    if (event.key === "Escape") {
      setPanelOpen(false);
      return;
    }

    if (event.key !== "Enter") {
      return;
    }

    event.preventDefault();
    if (highlightIndex >= 0 && highlightIndex < filteredTickers.length) {
      navigateToTicker(filteredTickers[highlightIndex]);
      return;
    }

    if (filteredTickers.length === 1) {
      navigateToTicker(filteredTickers[0]);
    }
  }

  return (
    <div ref={wrapRef} className={`globalTickerSearch ${panelOpen ? "is-open" : ""}`.trim()}>
      <button
        type="button"
        className="globalTickerSearchTrigger"
        onClick={() => setPanelOpen((prev) => !prev)}
        aria-expanded={panelOpen}
        aria-label="티커 또는 종목명 검색 열기"
      >
        <span className="globalTickerSearchTriggerText">티커/종목명</span>
      </button>

      {panelOpen ? (
        <div className="globalTickerSearchPanel">
          <div className="globalTickerSearchPanelInner">
            <div className="globalTickerSearchInputWrap">
              <IconSearch size={18} stroke={2} className="globalTickerSearchInputIcon" />
              <input
                ref={inputRef}
                className="globalTickerSearchInputField"
                type="text"
                value={searchInput}
                placeholder="검색어를 입력해주세요"
                onChange={(event) => {
                  setSearchInput(event.target.value);
                  setHighlightIndex(-1);
                }}
                onKeyDown={handleKeyDown}
              />
            </div>

            {searchInput.trim() ? (
              <div className="globalTickerSearchSection">
                <div className="globalTickerSearchSectionTitle">검색 결과</div>
                <div className="globalTickerSearchResults">
                  {filteredTickers.map((item, index) => (
                    <button
                      key={`${item.ticker_type}-${item.ticker}`}
                      type="button"
                      className={index === highlightIndex ? "globalTickerSearchResult is-active" : "globalTickerSearchResult"}
                      onMouseEnter={() => setHighlightIndex(index)}
                      onMouseDown={(event) => {
                        event.preventDefault();
                        navigateToTicker(item);
                      }}
                    >
                      <div className="globalTickerSearchResultMain">
                        <div className="globalTickerSearchResultName">{item.name}</div>
                        <div className="globalTickerSearchResultTicker">{item.ticker}</div>
                      </div>
                      <div className="globalTickerSearchResultMeta">
                        <div className="globalTickerSearchResultPrice">
                          {formatPrice(item.current_price, item.country_code)}
                        </div>
                        <div className={getChangeClass(item.change_pct)}>{formatChangePct(item.change_pct)}</div>
                      </div>
                    </button>
                  ))}
                  {filteredTickers.length === 0 ? (
                    <div className="globalTickerSearchEmpty">검색 결과가 없습니다.</div>
                  ) : null}
                </div>
              </div>
            ) : (
              <>
                <div className="globalTickerSearchSection">
                  <div className="globalTickerSearchSectionTitle">최근 검색</div>
                  <div className="globalTickerSearchChips">
                    {recentSearches.length > 0 ? (
                      recentSearches.map((item) => (
                        <div key={`${item.ticker_type}-${item.ticker}`} className="globalTickerSearchChip">
                          <button type="button" className="globalTickerSearchChipLabel" onClick={() => navigateToTicker(item)}>
                            {`${item.name}(${item.ticker})`}
                          </button>
                          <button
                            type="button"
                            className="globalTickerSearchChipRemove"
                            onClick={() => removeRecentSearch(item)}
                            aria-label={`${item.name} 최근 검색 제거`}
                          >
                            <IconX size={14} stroke={2.2} />
                          </button>
                        </div>
                      ))
                    ) : (
                      <div className="globalTickerSearchEmpty">최근 검색이 없습니다.</div>
                    )}
                  </div>
                </div>

                <div className="globalTickerSearchSection">
                  <div className="globalTickerSearchSectionHeader">
                    <div className="globalTickerSearchSectionTitle">
                      {formatTopMoversUpdatedAt(topMoversUpdatedAt, topMoversPreOpen)}
                    </div>
                  </div>
                  {topMoversLoading ? (
                    <AppLoadingState compact label="급상승 데이터를 불러오는 중..." />
                  ) : (
                    <div className="globalTickerSearchTopMoversGrid">
                      {topMoversByType.map((group) => (
                        <div key={group.ticker_type} className="globalTickerSearchTopMoversColumn">
                          <div className="globalTickerSearchTopMoversTitle">{group.label}</div>
                          <div className="globalTickerSearchResults">
                            {group.items.map((item, index) => (
                              <button
                                key={`${item.ticker_type}-${item.ticker}`}
                                type="button"
                                className="globalTickerSearchResult"
                                onClick={() => navigateToTicker(item)}
                              >
                                <div className="globalTickerSearchRank">{index + 1}</div>
                                <div className="globalTickerSearchResultMain">
                                  <div className="globalTickerSearchResultName">{item.name}</div>
                                  <div className="globalTickerSearchResultTicker">{item.ticker}</div>
                                </div>
                                <div className="globalTickerSearchResultMeta">
                                  <div className="globalTickerSearchResultPrice">
                                    {formatPrice(item.current_price, item.country_code)}
                                  </div>
                                  <div className={getChangeClass(item.change_pct)}>{formatChangePct(item.change_pct)}</div>
                                </div>
                              </button>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
