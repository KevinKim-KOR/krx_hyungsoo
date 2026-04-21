"use client";

import { useEffect, useState, useTransition } from "react";

import { AppModal } from "../components/AppModal";
import { useToast } from "../components/ToastProvider";

type BacktestTicker = {
  id: string;
  ticker: string;
  name: string;
  listingDate: string;
  status: "idle" | "checking" | "verified" | "error";
  message: string;
};

type BacktestGroup = {
  id: string;
  name: string;
  weight: number;
  tickers: BacktestTicker[];
};

type SavedBacktestItem = {
  config_id: string;
  name: string;
  period_months: number;
  slippage_pct: number;
  benchmark?: {
    ticker: string;
    name: string;
    listing_date: string;
  } | null;
  saved_at: string;
};

type BacktestRunResult = {
  initial_buy_date: string;
  latest_trading_day: string;
  cumulative_return_pct: number;
  cagr_pct: number;
  mdd_pct: number;
  benchmark?: {
    ticker: string;
    name: string;
    cumulative_return_pct: number;
    cagr_pct: number;
    mdd_pct: number;
  } | null;
  equity_curve: Array<{
    date: string;
    equity: number;
  }>;
};

const PERIOD_OPTIONS = Array.from({ length: 24 }, (_, index) => index + 1);
const MARKET_OPTIONS = [
  { value: "kor", label: "🇰🇷 한국" },
  { value: "au", label: "🇦🇺 호주" },
];

let groupCounter = 1;
let tickerCounter = 1;

function createTicker(ticker = ""): BacktestTicker {
  return {
    id: `ticker-${tickerCounter++}`,
    ticker,
    name: "",
    listingDate: "",
    status: "idle",
    message: "",
  };
}

function createGroup(): BacktestGroup {
  const nextNumber = groupCounter++;
  return {
    id: `group-${nextNumber}`,
    name: "",
    weight: 10,
    tickers: [createTicker()],
  };
}

function getTotalWeight(groups: BacktestGroup[]): number {
  return groups.reduce((sum, group) => sum + group.weight, 0);
}

function formatSavedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function BacktestBuilder({
  onHeaderSummaryChange,
}: {
  onHeaderSummaryChange?: (summary: {
    marketLabel: string;
    groupCount: number;
    totalWeight: number;
    resultLabel: string;
  }) => void;
}) {
  const toast = useToast();
  const [backtestName, setBacktestName] = useState("");
  const [countryCode, setCountryCode] = useState("kor");
  const [periodMonths, setPeriodMonths] = useState(12);
  const [slippagePct, setSlippagePct] = useState(0.5);
  const [rebalanceFreq, setRebalanceFreq] = useState("monthly");
  const [benchmarkTicker, setBenchmarkTicker] = useState<BacktestTicker>(createTicker());
  const [groups, setGroups] = useState<BacktestGroup[]>([createGroup()]);
  const [runResult, setRunResult] = useState<BacktestRunResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedConfigs, setSavedConfigs] = useState<SavedBacktestItem[]>([]);
  const [isLoadModalOpen, setIsLoadModalOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  function updateGroup(groupId: string, updater: (group: BacktestGroup) => BacktestGroup) {
    setGroups((current) => current.map((group) => (group.id === groupId ? updater(group) : group)));
  }

  function handleCountryChange(nextCountry: string) {
    setCountryCode(nextCountry);
    setError(null);
    setRunResult(null);
    setBenchmarkTicker(createTicker());
    setGroups((current) =>
      current.map((group) => ({
        ...group,
        tickers: group.tickers.map((ticker) => ({
          ...ticker,
          name: "",
          listingDate: "",
          status: "idle" as const,
          message: "",
        })),
      })),
    );
  }

  function handleAddGroup() {
    setError(null);
    setRunResult(null);
    setGroups((current) => [...current, createGroup()]);
  }

  function handleDeleteGroup(groupId: string) {
    setError(null);
    setRunResult(null);
    setGroups((current) => current.filter((group) => group.id !== groupId));
  }

  function handleAddTicker(groupId: string) {
    setError(null);
    setRunResult(null);
    updateGroup(groupId, (group) => ({
      ...group,
      tickers: [...group.tickers, createTicker()],
    }));
  }

  function handleDeleteTicker(groupId: string, tickerId: string) {
    setError(null);
    setRunResult(null);
    updateGroup(groupId, (group) => ({
      ...group,
      tickers: group.tickers.filter((ticker) => ticker.id !== tickerId),
    }));
  }

  function handleTickerChange(groupId: string, tickerId: string, tickerValue: string) {
    setError(null);
    setRunResult(null);
    updateGroup(groupId, (group) => ({
      ...group,
      tickers: group.tickers.map((ticker) =>
        ticker.id === tickerId
          ? {
              ...ticker,
              ticker: tickerValue.toUpperCase(),
              name: "",
              listingDate: "",
              status: "idle",
              message: "",
            }
          : ticker,
      ),
    }));
  }

  async function handleValidateTicker(groupId: string, tickerId: string) {
    setError(null);
    const currentGroup = groups.find((group) => group.id === groupId);
    const currentTicker = currentGroup?.tickers.find((ticker) => ticker.id === tickerId);
    const tickerValue = currentTicker?.ticker.trim().toUpperCase() ?? "";

    if (!tickerValue) {
      updateGroup(groupId, (group) => ({
        ...group,
        tickers: group.tickers.map((ticker) =>
          ticker.id === tickerId
            ? {
                ...ticker,
                status: "error",
                message: "티커를 입력하세요.",
              }
            : ticker,
        ),
      }));
      return;
    }

    updateGroup(groupId, (group) => ({
      ...group,
      tickers: group.tickers.map((ticker) =>
        ticker.id === tickerId
          ? {
              ...ticker,
              status: "checking",
              message: "",
            }
          : ticker,
      ),
    }));

    try {
      const response = await fetch("/api/backtest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "validate",
          ticker: tickerValue,
          country_code: countryCode,
        }),
      });
      const payload = (await response.json()) as {
        ticker?: string;
        name?: string;
        listing_date?: string;
        error?: string;
      };
      if (!response.ok) {
        throw new Error(payload.error ?? "티커 확인에 실패했습니다.");
      }

      updateGroup(groupId, (group) => ({
        ...group,
        tickers: group.tickers.map((ticker) =>
          ticker.id === tickerId
            ? {
                ...ticker,
                ticker: String(payload.ticker ?? tickerValue).toUpperCase(),
                name: String(payload.name ?? ""),
                listingDate: String(payload.listing_date ?? ""),
                status: "verified",
                message: payload.name
                  ? `${String(payload.name)}${payload.listing_date ? ` · 상장일 ${String(payload.listing_date)}` : ""}`
                  : "확인 완료",
              }
            : ticker,
        ),
      }));
    } catch (error) {
      updateGroup(groupId, (group) => ({
        ...group,
        tickers: group.tickers.map((ticker) =>
          ticker.id === tickerId
            ? {
                ...ticker,
                name: "",
                listingDate: "",
                status: "error",
                message: error instanceof Error ? error.message : "티커 확인에 실패했습니다.",
              }
            : ticker,
        ),
      }));
    }
  }

  function buildSaveGroups() {
    return groups.map((group) => {
      const groupName = group.name.trim();
      if (!groupName) {
        throw new Error("모든 그룹명은 필수입니다.");
      }
      if (!Number.isFinite(group.weight) || group.weight < 1 || group.weight > 100) {
        throw new Error("그룹 비중은 1에서 100 사이여야 합니다.");
      }

      const verifiedTickers = group.tickers.filter((ticker) => ticker.status === "verified");
      if (verifiedTickers.length === 0) {
        throw new Error(`${groupName}에는 확인된 티커가 최소 1개 필요합니다.`);
      }

      const hasUncheckedTicker = group.tickers.some(
        (ticker) => ticker.ticker.trim() && ticker.status !== "verified",
      );
      if (hasUncheckedTicker) {
        throw new Error(`${groupName}에 아직 확인되지 않은 티커가 있습니다.`);
      }

      return {
        group_id: group.id,
        name: groupName,
        weight: group.weight,
        tickers: verifiedTickers.map((ticker) => ({
          ticker: ticker.ticker,
          name: ticker.name,
          listing_date: ticker.listingDate,
        })),
      };
    });
  }

  function buildBenchmark() {
    const ticker = benchmarkTicker.ticker.trim();
    if (!ticker) {
      return null;
    }
    if (benchmarkTicker.status !== "verified") {
      throw new Error("벤치마크 종목을 확인하세요.");
    }
    return {
      ticker: benchmarkTicker.ticker,
      name: benchmarkTicker.name,
      listing_date: benchmarkTicker.listingDate,
    };
  }

  function applyLoadedConfig(payload: {
    name?: string;
    period_months?: number;
    slippage_pct?: number;
    rebalance_freq?: string;
    benchmark?: { ticker?: string; name?: string; listing_date?: string } | null;
    groups?: Array<{
      group_id?: string;
      name?: string;
      weight?: number;
      tickers?: Array<{ ticker?: string; name?: string; listing_date?: string }>;
    }>;
  }) {
    const nextGroups: BacktestGroup[] =
      payload.groups?.map((group, index) => ({
        id: String(group.group_id ?? `group-${index + 1}`),
        name: String(group.name ?? `그룹${index + 1}`),
        weight: Number(group.weight ?? 0),
        tickers:
          group.tickers?.map((ticker) => ({
            id: `ticker-${tickerCounter++}`,
            ticker: String(ticker.ticker ?? "").toUpperCase(),
            name: String(ticker.name ?? ""),
            listingDate: String(ticker.listing_date ?? ""),
            status: "verified" as const,
            message: ticker.name
              ? `${String(ticker.name ?? "")}${ticker.listing_date ? ` · 상장일 ${String(ticker.listing_date)}` : ""}`
              : "확인 완료",
          })) ?? [createTicker()],
      })) ?? [];

    setBacktestName(String(payload.name ?? ""));
    setPeriodMonths(Number(payload.period_months ?? 12));
    setSlippagePct(Number(payload.slippage_pct ?? 0.5));
    setRebalanceFreq(String(payload.rebalance_freq ?? "monthly"));
    setBenchmarkTicker(
      payload.benchmark?.ticker
        ? {
            id: `ticker-${tickerCounter++}`,
            ticker: String(payload.benchmark.ticker ?? "").toUpperCase(),
            name: String(payload.benchmark.name ?? ""),
            listingDate: String(payload.benchmark.listing_date ?? ""),
            status: "verified",
            message: payload.benchmark.name
              ? `${String(payload.benchmark.name ?? "")}${payload.benchmark.listing_date ? ` · 상장일 ${String(payload.benchmark.listing_date)}` : ""}`
              : "확인 완료",
          }
        : createTicker(),
    );
    setGroups(nextGroups.length > 0 ? nextGroups : [createGroup()]);
    groupCounter = Math.max(groupCounter, nextGroups.length + 1);
    setError(null);
    setRunResult(null);
  }

  function handleSaveConfig() {
    startTransition(async () => {
      try {
        setError(null);
        const title = backtestName.trim();
        if (!title) {
          throw new Error("백테스트 제목을 입력하세요.");
        }

        const normalizedGroups = buildSaveGroups();
        const benchmark = buildBenchmark();
        const response = await fetch("/api/backtest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "save",
            name: title,
            period_months: periodMonths,
            slippage_pct: slippagePct,
            rebalance_freq: rebalanceFreq,
            benchmark,
            groups: normalizedGroups,
          }),
        });
        const payload = (await response.json()) as {
          saved_at?: string;
          duplicated?: boolean;
          error?: string;
        };
        if (!response.ok) {
          throw new Error(payload.error ?? "백테스트 저장에 실패했습니다.");
        }

        if (payload.duplicated) {
          toast.warning(`[ETF-백테스트] 동일한 설정이 이미 저장되어 있어 저장을 건너뜁니다.`);
          return;
        }

        toast.success(`[ETF-백테스트] ${title} 저장 완료`);
      } catch (saveError) {
        const message = saveError instanceof Error ? saveError.message : "백테스트 저장에 실패했습니다.";
        setError(message);
        toast.error(`[ETF-백테스트] ${message}`);
      }
    });
  }

  function handleRunBacktest() {
    startTransition(async () => {
      try {
        setError(null);
        const normalizedGroups = buildSaveGroups();
        const benchmark = buildBenchmark();
        const response = await fetch("/api/backtest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            action: "run",
            period_months: periodMonths,
            slippage_pct: slippagePct,
            rebalance_freq: rebalanceFreq,
            benchmark,
            groups: normalizedGroups,
            country_code: countryCode,
          }),
        });
        const payload = (await response.json()) as BacktestRunResult & { error?: string };
        if (!response.ok) {
          throw new Error(payload.error ?? "백테스트 실행에 실패했습니다.");
        }
        setRunResult(payload);
        toast.success("[ETF-백테스트] 백테스트 실행 완료");
      } catch (runError) {
        setRunResult(null);
        const message = runError instanceof Error ? runError.message : "백테스트 실행에 실패했습니다.";
        setError(message);
        toast.error(`[ETF-백테스트] ${message}`);
      }
    });
  }

  function handleOpenLoadModal() {
    startTransition(async () => {
      try {
        setError(null);
        const response = await fetch("/api/backtest", { cache: "no-store" });
        const payload = (await response.json()) as { items?: SavedBacktestItem[]; error?: string };
        if (!response.ok) {
          throw new Error(payload.error ?? "저장된 백테스트를 불러오지 못했습니다.");
        }

        setSavedConfigs(payload.items ?? []);
        setIsLoadModalOpen(true);
      } catch (loadError) {
        const message = loadError instanceof Error ? loadError.message : "저장된 백테스트를 불러오지 못했습니다.";
        setError(message);
        toast.error(`[ETF-백테스트] ${message}`);
      }
    });
  }

  function handleLoadConfig(configId: string) {
    startTransition(async () => {
      try {
        setError(null);
        const response = await fetch(`/api/backtest?config_id=${encodeURIComponent(configId)}`, {
          cache: "no-store",
        });
        const payload = (await response.json()) as {
          name?: string;
          period_months?: number;
          slippage_pct?: number;
          rebalance_freq?: string;
          benchmark?: { ticker?: string; name?: string; listing_date?: string } | null;
          groups?: Array<{
            group_id?: string;
            name?: string;
            weight?: number;
            tickers?: Array<{ ticker?: string; name?: string; listing_date?: string }>;
          }>;
          saved_at?: string;
          error?: string;
        };
        if (!response.ok) {
          throw new Error(payload.error ?? "백테스트를 불러오지 못했습니다.");
        }

        applyLoadedConfig(payload);
        setIsLoadModalOpen(false);
        toast.success(
          `[ETF-백테스트] ${String(payload.name ?? "백테스트")} 불러오기 완료${payload.saved_at ? ` · ${formatSavedAt(String(payload.saved_at))}` : ""}`,
        );
      } catch (loadError) {
        const message = loadError instanceof Error ? loadError.message : "백테스트를 불러오지 못했습니다.";
        setError(message);
        toast.error(`[ETF-백테스트] ${message}`);
      }
    });
  }

  function handleDeleteSavedConfig(configId: string, name: string) {
    startTransition(async () => {
      try {
        setError(null);
        const response = await fetch("/api/backtest", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: "delete", config_id: configId }),
        });
        const payload = (await response.json()) as { error?: string };
        if (!response.ok) {
          throw new Error(payload.error ?? "백테스트 삭제에 실패했습니다.");
        }

        setSavedConfigs((current) => current.filter((item) => item.config_id !== configId));
        toast.success(`[ETF-백테스트] ${name} 삭제 완료`);
      } catch (deleteError) {
        const message = deleteError instanceof Error ? deleteError.message : "백테스트 삭제에 실패했습니다.";
        setError(message);
        toast.error(`[ETF-백테스트] ${message}`);
      }
    });
  }

  const totalWeight = getTotalWeight(groups);

  useEffect(() => {
    onHeaderSummaryChange?.({
      marketLabel: countryCode === "au" ? "호주" : "한국",
      groupCount: groups.length,
      totalWeight,
      resultLabel: runResult ? `완료 · ${runResult.latest_trading_day}` : "준비 중",
    });
  }, [countryCode, groups.length, onHeaderSummaryChange, runResult, totalWeight]);

  return (
    <div className="appPageStack">
      <div className="card appCard">
        <div className="card-body appCardBodyTight">
          <div className="backtestToolbar">
            <div className="backtestToolbarLeft">
              <div className="backtestSummaryText">
                그룹 {groups.length}개 · 총 비중 {totalWeight}%
              </div>
            </div>
            <div className="backtestToolbarActions">
              <button type="button" className="btn btn-outline-secondary" onClick={handleAddGroup}>
                그룹 추가
              </button>
              <button type="button" className="btn btn-outline-secondary" onClick={handleOpenLoadModal} disabled={isPending}>
                백테스트 불러오기
              </button>
              <button type="button" className="btn btn-success" onClick={handleSaveConfig} disabled={isPending}>
                {isPending ? "처리 중..." : "백테스트 저장"}
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="card appCard">
        <div className="card-body appCardBodyTight">
          <div className="backtestNameField">
            <div className="subheader mb-3">백테스트 정보</div>
            <div className="backtestInfoGrid">
              <label className="form-label mb-0">
                <span className="subheader">마켓</span>
                <select
                  className="form-select"
                  value={countryCode}
                  onChange={(event) => handleCountryChange(event.target.value)}
                >
                  {MARKET_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-label mb-0">
                <span className="subheader">백테스트 제목</span>
                <input
                  type="text"
                  className="form-control"
                  placeholder="예: 모멘텀 70/20/10 기본안"
                  value={backtestName}
                  onChange={(event) => {
                    setBacktestName(event.target.value);
                    setRunResult(null);
                  }}
                />
              </label>
              <label className="form-label mb-0">
                <span className="subheader">기간</span>
                <select
                  className="form-select"
                  value={periodMonths}
                  onChange={(event) => {
                    setPeriodMonths(Number(event.target.value));
                    setRunResult(null);
                  }}
                >
                  {PERIOD_OPTIONS.map((months) => (
                    <option key={months} value={months}>
                      최근 {months}달
                    </option>
                  ))}
                </select>
              </label>
              <label className="form-label mb-0">
                <span className="subheader">리밸런싱 주기</span>
                <select
                  className="form-select"
                  value={rebalanceFreq}
                  onChange={(event) => {
                    setRebalanceFreq(event.target.value);
                    setRunResult(null);
                  }}
                >
                  <option value="daily">매일</option>
                  <option value="weekly">매주</option>
                  <option value="monthly">매월</option>
                </select>
              </label>
              <label className="form-label mb-0">
                <span className="subheader">슬리피지(%)</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  step={0.1}
                  className="form-control"
                  value={slippagePct}
                  onChange={(event) => {
                    setSlippagePct(Number(event.target.value || 0));
                    setRunResult(null);
                  }}
                />
              </label>
              <div className="form-label mb-0">
                <span className="subheader">벤치마크 종목</span>
                <div className="backtestBenchmarkRow">
                  <input
                    type="text"
                    className="form-control"
                    placeholder="예: 0091P0, VHY"
                    value={benchmarkTicker.ticker}
                    onChange={(event) => {
                      setBenchmarkTicker({
                        ...benchmarkTicker,
                        ticker: event.target.value.toUpperCase(),
                        name: "",
                        listingDate: "",
                        status: "idle",
                        message: "",
                      });
                      setRunResult(null);
                    }}
                  />
                  <button
                    type="button"
                    className="btn btn-outline-secondary btn-sm"
                    onClick={async () => {
                      const tickerValue = benchmarkTicker.ticker.trim().toUpperCase();
                      if (!tickerValue) {
                        setBenchmarkTicker((current) => ({
                          ...current,
                          status: "error",
                          message: "티커를 입력하세요.",
                        }));
                        return;
                      }
                      setBenchmarkTicker((current) => ({ ...current, status: "checking", message: "" }));
                      try {
                        const response = await fetch("/api/backtest", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ action: "validate", ticker: tickerValue, country_code: countryCode }),
                        });
                        const payload = (await response.json()) as {
                          ticker?: string;
                          name?: string;
                          listing_date?: string;
                          error?: string;
                        };
                        if (!response.ok) {
                          throw new Error(payload.error ?? "티커 확인에 실패했습니다.");
                        }
                        setBenchmarkTicker((current) => ({
                          ...current,
                          ticker: String(payload.ticker ?? tickerValue).toUpperCase(),
                          name: String(payload.name ?? ""),
                          listingDate: String(payload.listing_date ?? ""),
                          status: "verified",
                          message: payload.name
                            ? `${String(payload.name)}${payload.listing_date ? ` · 상장일 ${String(payload.listing_date)}` : ""}`
                            : "확인 완료",
                        }));
                      } catch (validateError) {
                        setBenchmarkTicker((current) => ({
                          ...current,
                          name: "",
                          listingDate: "",
                          status: "error",
                          message: validateError instanceof Error ? validateError.message : "티커 확인에 실패했습니다.",
                        }));
                      }
                    }}
                    disabled={benchmarkTicker.status === "checking" || benchmarkTicker.status === "verified"}
                  >
                    {benchmarkTicker.status === "checking" ? (
                      <span className="d-inline-flex align-items-center gap-2">
                        <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                        확인 중...
                      </span>
                    ) : benchmarkTicker.status === "verified" ? (
                      "확인 완료"
                    ) : (
                      "확인"
                    )}
                  </button>
                </div>
                {benchmarkTicker.message ? (
                  <div
                    className={
                      benchmarkTicker.status === "error"
                        ? "backtestBenchmarkMessage backtestTickerMessageError"
                        : "backtestBenchmarkMessage"
                    }
                  >
                    {benchmarkTicker.message}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="backtestGroupGrid">
        {groups.map((group, index) => (
          <div key={group.id} className="card appCard backtestGroupCard">
            <div className="card-header appCardHeader">
              <div>
                <h3 className="card-title">그룹 {index + 1}</h3>
              </div>
              <button
                type="button"
                className="btn btn-outline-danger btn-sm"
                onClick={() => handleDeleteGroup(group.id)}
                disabled={groups.length === 1}
              >
                그룹 삭제
              </button>
            </div>
            <div className="card-body appCardBody backtestGroupBody">
              <div className="backtestFieldGrid">
                <label className="form-label mb-0">
                  <span className="subheader">그룹명</span>
                  <input
                    type="text"
                    className="form-control"
                    value={group.name}
                    onChange={(event) => {
                      setRunResult(null);
                      updateGroup(group.id, (currentGroup) => ({
                        ...currentGroup,
                        name: event.target.value,
                      }));
                    }}
                  />
                </label>
                <label className="form-label mb-0">
                  <span className="subheader">비중(%)</span>
                  <input
                    type="number"
                    min={1}
                    max={100}
                    className="form-control"
                    value={group.weight}
                    onChange={(event) =>
                      {
                        setRunResult(null);
                        updateGroup(group.id, (currentGroup) => ({
                          ...currentGroup,
                          weight: Number(event.target.value || 0),
                        }));
                      }
                    }
                  />
                </label>
              </div>

              <div className="backtestTickerSection">
                <div className="d-flex align-items-center justify-content-between">
                  <div className="subheader">ETF 티커</div>
                  <button type="button" className="btn btn-outline-secondary btn-sm" onClick={() => handleAddTicker(group.id)}>
                    종목 추가
                  </button>
                </div>
                <div className="backtestTickerList">
                  {group.tickers.map((ticker, tickerIndex) => (
                    <div key={ticker.id} className="backtestTickerItem">
                      <div className="backtestTickerRow">
                        <span className="tableMuted backtestTickerIndex">{tickerIndex + 1}</span>
                        <input
                          type="text"
                          className="form-control"
                          placeholder="예: 0091P0, VHY"
                          value={ticker.ticker}
                          onChange={(event) => handleTickerChange(group.id, ticker.id, event.target.value)}
                        />
                        <button
                          type="button"
                          className="btn btn-outline-secondary btn-sm"
                          onClick={() => void handleValidateTicker(group.id, ticker.id)}
                          disabled={ticker.status === "checking" || ticker.status === "verified"}
                        >
                          {ticker.status === "checking" ? (
                            <span className="d-inline-flex align-items-center gap-2">
                              <span className="spinner-border spinner-border-sm" aria-hidden="true" />
                              확인 중...
                            </span>
                          ) : ticker.status === "verified" ? (
                            "확인 완료"
                          ) : (
                            "확인"
                          )}
                        </button>
                        <button
                          type="button"
                          className="btn btn-outline-danger btn-sm"
                          onClick={() => handleDeleteTicker(group.id, ticker.id)}
                          disabled={ticker.status === "checking"}
                        >
                          삭제
                        </button>
                      </div>
                      {ticker.message ? (
                        <div
                          className={
                            ticker.status === "error" ? "backtestTickerMessage backtestTickerMessageError" : "backtestTickerMessage"
                          }
                        >
                          {ticker.message}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="card appCard">
        <div className="card-body appCardBodyTight">
          <button type="button" className="btn btn-primary w-100" onClick={handleRunBacktest} disabled={isPending}>
            {isPending ? "백테스트 실행 중..." : "백테스트 실행"}
          </button>
        </div>
      </div>

      <div className="card appCard">
        <div className="card-header appCardHeader">
          <h3 className="card-title">결과</h3>
        </div>
        <div className="card-body appCardBody">
          {runResult ? (
            <div className="backtestResultStack">
              <div className="backtestResultGrid">
                <div className="card appCard backtestResultCard">
                  <div className="card-body appCardBodyTight">
                    <div className="subheader">누적 수익률</div>
                    <div className={runResult.cumulative_return_pct >= 0 ? "metricPositive" : "metricNegative"}>
                      {runResult.cumulative_return_pct.toFixed(2)}%
                    </div>
                  </div>
                </div>
                <div className="card appCard backtestResultCard">
                  <div className="card-body appCardBodyTight">
                    <div className="subheader">CAGR</div>
                    <div className={runResult.cagr_pct >= 0 ? "metricPositive" : "metricNegative"}>
                      {runResult.cagr_pct.toFixed(2)}%
                    </div>
                  </div>
                </div>
                <div className="card appCard backtestResultCard">
                  <div className="card-body appCardBodyTight">
                    <div className="subheader">MDD</div>
                    <div className="metricNegative">{runResult.mdd_pct.toFixed(2)}%</div>
                  </div>
                </div>
              </div>
              <div className="tableMuted">
                시작 매수일 {runResult.initial_buy_date} · 최근 거래일 {runResult.latest_trading_day}
              </div>
              {runResult.benchmark ? (
                <div className="backtestResultStack">
                  <div className="subheader">벤치마크 비교 · {runResult.benchmark.name}</div>
                  <div className="backtestResultGrid">
                    <div className="card appCard backtestResultCard">
                      <div className="card-body appCardBodyTight">
                        <div className="subheader">누적 수익률</div>
                        <div className={runResult.benchmark.cumulative_return_pct >= 0 ? "metricPositive" : "metricNegative"}>
                          {runResult.benchmark.cumulative_return_pct.toFixed(2)}%
                        </div>
                      </div>
                    </div>
                    <div className="card appCard backtestResultCard">
                      <div className="card-body appCardBodyTight">
                        <div className="subheader">CAGR</div>
                        <div className={runResult.benchmark.cagr_pct >= 0 ? "metricPositive" : "metricNegative"}>
                          {runResult.benchmark.cagr_pct.toFixed(2)}%
                        </div>
                      </div>
                    </div>
                    <div className="card appCard backtestResultCard">
                      <div className="card-body appCardBodyTight">
                        <div className="subheader">MDD</div>
                        <div className="metricNegative">{runResult.benchmark.mdd_pct.toFixed(2)}%</div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="text-secondary" style={{ fontSize: "0.95rem" }}>
              설정을 마친 뒤 <strong>백테스트 실행</strong> 버튼을 눌러 결과를 확인한다.
            </div>
          )}
        </div>
      </div>

      <AppModal
        open={isLoadModalOpen}
        title="백테스트 불러오기"
        subtitle="저장된 백테스트 설정을 선택하면 현재 화면에 적용한다."
        size="xl"
        onClose={() => setIsLoadModalOpen(false)}
      >
        {savedConfigs.length > 0 ? (
          <div className="backtestLoadList">
            {savedConfigs.map((item) => (
              <div key={item.config_id} className="backtestLoadItem">
                <button
                  type="button"
                  className="backtestLoadItemBody"
                  onClick={() => void handleLoadConfig(item.config_id)}
                >
                  <span className="backtestLoadItemLine">
                    <span className="backtestLoadItemTitle">{item.name}</span>
                    <span className="backtestLoadItemMeta">
                      {` - 최근 ${item.period_months}달, 저장 ${formatSavedAt(item.saved_at)}`}
                    </span>
                  </span>
                </button>
                <button
                  type="button"
                  className="btn btn-outline-danger btn-sm"
                  onClick={() => void handleDeleteSavedConfig(item.config_id, item.name)}
                  disabled={isPending}
                >
                  삭제
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div className="tableMuted">저장된 백테스트가 없습니다.</div>
        )}
      </AppModal>
    </div>
  );
}
