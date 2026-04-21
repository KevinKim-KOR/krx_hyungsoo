"use client";

import { useEffect, useRef, useState } from "react";
import { Area, AreaChart, Cell, Pie, PieChart, Tooltip } from "recharts";

import { BUCKET_COLORS } from "@/lib/bucket-theme";
import { AppLoadingState } from "../components/AppLoadingState";

type DashboardMetricItem = {
  label: string;
  value: number;
  kind: "money" | "percent";
  sub_value?: number;
  sub_kind?: "money" | "percent";
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
  daily_profit: number;
  weekly_profit: number;
};

type DashboardBucketItem = {
  label: string;
  weight_pct: number;
};

type DashboardData = {
  metrics_row1?: DashboardMetricItem[];
  metrics_row2?: DashboardMetricItem[];
  accounts?: DashboardAccountSummaryItem[];
  buckets?: DashboardBucketItem[];
  account_buckets?: Record<string, DashboardBucketItem[]>;
  sparklines?: Record<string, Array<{ date: string; value: number }>>;
  latest_snapshot_date?: string | null;
  weekly_date?: string | null;
  updated_at?: string | null;
  error?: string;
};

function formatMoney(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1_0000_0000) {
    const eok = Math.floor(abs / 1_0000_0000);
    const man = Math.round((abs % 1_0000_0000) / 1_0000);
    return man > 0 ? `${sign}${eok}억 ${new Intl.NumberFormat("ko-KR").format(man)}만원` : `${sign}${eok}억원`;
  }
  if (abs >= 1_0000) {
    const man = Math.round(abs / 1_0000);
    return `${sign}${new Intl.NumberFormat("ko-KR").format(man)}만원`;
  }
  return `${new Intl.NumberFormat("ko-KR").format(Math.round(value))}원`;
}

function formatPercent(value: number): string {
  return `${value.toFixed(2)}%`;
}

function formatMetricValue(value: number, kind: "money" | "percent" | "count"): string {
  if (kind === "money") return formatMoney(value);
  if (kind === "percent") return formatPercent(value);
  return new Intl.NumberFormat("ko-KR").format(value);
}

function formatUpdatedAt(value: string | null | undefined): string {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function getSignedClass(value: number): string {
  if (value > 0) return "text-success";
  if (value < 0) return "text-danger";
  return "";
}

function shouldHighlight(label: string): boolean {
  return label.includes("손익") || label.includes("수익률");
}

function renderAccountNameCell(account: DashboardAccountSummaryItem) {
  if (!account.account_url) {
    return <span className="fw-medium">{account.account_name}</span>;
  }

  return (
    <a
      href={account.account_url}
      target="_blank"
      rel="noreferrer"
      className="fw-medium"
      style={{ textDecoration: "underline" }}
    >
      {account.account_name}
    </a>
  );
}

type SparklinePoint = { date: string; value: number };

function SparklineTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: SparklinePoint }> }) {
  if (!active || !payload?.[0]) return null;
  const point = payload[0].payload;
  return (
    <div
      style={{
        background: "#1e293b",
        color: "#fff",
        padding: "4px 8px",
        borderRadius: 4,
        fontSize: "0.72rem",
        lineHeight: 1.4,
        whiteSpace: "nowrap",
      }}
    >
      <div style={{ fontWeight: 600 }}>{point.date}</div>
      <div>{new Intl.NumberFormat("ko-KR").format(Math.round(point.value))}</div>
    </div>
  );
}

let sparklineCounter = 0;

function Sparkline({ data, color = "#206bc4" }: { data: SparklinePoint[]; color?: string }) {
  const [id] = useState(() => `spark-${++sparklineCounter}`);
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      const nextWidth = Math.floor(rect?.width ?? 0);
      const nextHeight = Math.floor(rect?.height ?? 0);
      if (nextWidth > 0 && nextHeight > 0) {
        setSize({ width: nextWidth, height: nextHeight });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  if (data.length < 2) return null;
  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", minHeight: 96, minWidth: 0 }}>
      {size.width > 0 && size.height > 0 ? (
        <AreaChart
          data={data}
          width={size.width}
          height={size.height}
          margin={{ top: 0, right: 0, bottom: 0, left: 0 }}
        >
          <defs>
            <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.2} />
              <stop offset="100%" stopColor={color} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <Area
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={1.5}
            fill={`url(#${id})`}
            dot={false}
            isAnimationActive={false}
          />
          <Tooltip content={<SparklineTooltip />} cursor={{ stroke: color, strokeWidth: 1, strokeDasharray: "3 3" }} />
        </AreaChart>
      ) : null}
    </div>
  );
}

function DashboardDonutChart({ buckets }: { buckets: DashboardBucketItem[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0]?.contentRect;
      const nextWidth = Math.floor(rect?.width ?? 0);
      const nextHeight = Math.floor(rect?.height ?? 0);
      if (nextWidth > 0 && nextHeight > 0) {
        setSize({ width: nextWidth, height: nextHeight });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const chartSize = size.width > 0 && size.height > 0 ? Math.min(size.width, size.height, 300) : 0;

  return (
    <div ref={containerRef} style={{ width: "100%", height: "100%", minWidth: 0, minHeight: 120 }}>
      {chartSize > 0 ? (
        <PieChart width={chartSize} height={chartSize} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
          <Pie
            data={buckets}
            dataKey="weight_pct"
            nameKey="label"
            cx="50%"
            cy="50%"
            innerRadius={chartSize * 0.26}
            outerRadius={chartSize * 0.46}
            paddingAngle={2}
            strokeWidth={0}
          >
            {buckets.map((_, i) => (
              <Cell key={i} fill={BUCKET_COLORS[i % BUCKET_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value) => `${Number(value).toFixed(2)}%`}
            contentStyle={{ fontSize: "0.82rem", borderRadius: 6 }}
          />
        </PieChart>
      ) : null}
    </div>
  );
}

function DashboardBucketLegend({ buckets }: { buckets: DashboardBucketItem[] }) {
  return (
    <div className="row g-1">
      {buckets.map((bucket, index) => (
        <div key={bucket.label} className="col-6">
          <div className="d-flex align-items-center gap-1" style={{ minWidth: 0 }}>
            <span
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                backgroundColor: BUCKET_COLORS[index % BUCKET_COLORS.length],
                flex: "0 0 auto",
              }}
            />
            <span
              className="text-secondary"
              style={{
                fontSize: "0.72rem",
                minWidth: 0,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {bucket.label.replace(/^\d+\.\s*/, "")} {bucket.weight_pct.toFixed(1)}%
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}

const PERIOD_OPTIONS = [
  { label: "1달", months: 1 },
  { label: "3달", months: 3 },
  { label: "6달", months: 6 },
  { label: "12달", months: 12 },
];

function calcChangePct(sparkData: SparklinePoint[] | undefined, months: number): number | null {
  if (!sparkData || sparkData.length < 2) return null;
  const weeksBack = Math.round(months * 4.33);
  const baseIndex = Math.max(0, sparkData.length - 1 - weeksBack);
  const baseValue = sparkData[baseIndex].value;
  const currentValue = sparkData[sparkData.length - 1].value;
  if (baseValue === 0) return null;
  return ((currentValue - baseValue) / Math.abs(baseValue)) * 100;
}

type DashboardRenderableMetricItem = {
  label: string;
  value: number;
  kind: "money" | "percent" | "count";
  sub_value?: number;
  sub_kind?: "money" | "percent" | "count";
};

const DASHBOARD_ROW1_LABELS = ["총 자산", "투자 원금", "금일 손익", "금주 손익"] as const;
const DASHBOARD_ROW2_LABELS = ["누적 손익", "현금 잔고", "금일 손익", "금주 손익"] as const;
const DASHBOARD_LEFT_LABELS = ["총 자산", "투자 원금", "누적 손익", "현금 잔고", "금일 손익", "금주 손익"] as const;

const DASHBOARD_ACCOUNT_WEIGHTS: { account_id: string; icon: string; label: string }[] = [
  { account_id: "kor_account", icon: "🇰🇷", label: "국내 계좌" },
  { account_id: "isa_account", icon: "🇰🇷", label: "ISA 계좌" },
  { account_id: "pension_account", icon: "🇰🇷", label: "연금저축 계좌" },
  { account_id: "core_account", icon: "💼", label: "장기보유 계좌" },
  { account_id: "aus_account", icon: "🇦🇺", label: "호주 계좌" },
];

function orderMetricItems(
  items: DashboardRenderableMetricItem[],
  labels: readonly string[],
): DashboardRenderableMetricItem[] {
  const itemMap = new Map(items.map((item) => [item.label, item]));
  return labels
    .map((label) => itemMap.get(label))
    .filter((item): item is DashboardRenderableMetricItem => item !== undefined);
}

function DashboardMetricCard({
  item,
  hideMoney,
  periodMonths,
  sparklines,
}: {
  item: DashboardRenderableMetricItem;
  hideMoney: boolean;
  periodMonths: number;
  sparklines: Record<string, SparklinePoint[]>;
}) {
  const highlighted = shouldHighlight(item.label);
  const signClass = highlighted ? getSignedClass(item.value) : "";
  const sparkData = sparklines[item.label];
  const sparkColor = highlighted ? (item.value >= 0 ? "#2fb344" : "#d63939") : "#206bc4";
  const changePct = calcChangePct(sparkData, periodMonths);

  function mask(value: number, kind: "money" | "percent" | "count" = "money"): string {
    if (hideMoney && kind === "money") return "••••••";
    return formatMetricValue(value, kind);
  }

  return (
    <div className="card card-sm dashboardMetricCard">
      <div
        className={`card-body ${sparkData ? "dashboardMetricCardBody" : "dashboardMetricCardBody dashboardMetricCardBodyTextOnly"}`}
        style={{ overflow: "hidden", paddingTop: "0.85rem", paddingBottom: "0.85rem" }}
      >
        <div className="d-flex align-items-center justify-content-between">
          <div className="subheader">{item.label}</div>
          {changePct !== null ? (
            <span
              className={changePct >= 0 ? "text-success" : "text-danger"}
              style={{ fontSize: "0.75rem", fontWeight: 600, whiteSpace: "nowrap" }}
            >
              {changePct >= 0 ? "+" : ""}
              {changePct.toFixed(1)}%
              {changePct >= 0 ? " \u2197" : " \u2198"}
            </span>
          ) : null}
        </div>
        {item.sub_value !== undefined && item.sub_kind === "count" ? (
          <div className="d-flex align-items-baseline gap-1" style={{ whiteSpace: "nowrap" }}>
            <span className="h1 mb-0 text-success" style={{ fontSize: "1.1rem" }}>
              {formatMetricValue(item.value, item.kind)}
            </span>
            <span className="text-secondary" style={{ fontSize: "1rem", fontWeight: 600 }}>
              /
            </span>
            <span className="h1 mb-0 text-danger" style={{ fontSize: "1.1rem" }}>
              {formatMetricValue(item.sub_value, item.sub_kind)}
            </span>
          </div>
        ) : (
          <div className="d-flex align-items-baseline gap-2">
            <div className={`h1 mb-0 ${signClass}`.trim()} style={{ fontSize: "1.32rem" }}>
              {mask(item.value, item.kind)}
            </div>
            {item.sub_value !== undefined && item.sub_kind ? (
              <span
                className={getSignedClass(item.sub_value)}
                style={{ fontSize: "0.94rem", fontWeight: 600, whiteSpace: "nowrap" }}
              >
                {formatMetricValue(item.sub_value, item.sub_kind)}
              </span>
            ) : null}
          </div>
        )}
        {sparkData ? (
          <div className="dashboardMetricCardSparkline">
            <Sparkline data={sparkData} color={sparkColor} />
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function DashboardManager() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hideMoney, setHideMoney] = useState(false);
  const [periodMonths, setPeriodMonths] = useState(12);

  function mask(value: number, kind: "money" | "percent" | "count" = "money"): string {
    if (hideMoney && kind === "money") return "••••••";
    return formatMetricValue(value, kind);
  }

  useEffect(() => {
    let alive = true;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const response = await fetch("/api/dashboard", { cache: "no-store" });
        const payload = (await response.json()) as DashboardData;
        if (!response.ok) {
          throw new Error(payload.error ?? "대시보드 데이터를 불러오지 못했습니다.");
        }
        if (alive) setData(payload);
      } catch (loadError) {
        if (alive) setError(loadError instanceof Error ? loadError.message : "대시보드 데이터를 불러오지 못했습니다.");
      } finally {
        if (alive) setLoading(false);
      }
    }

    load();
    return () => { alive = false; };
  }, []);

  if (loading) {
    return (
      <div className="appPageStack">
        <div className="appPageLoading">
          <AppLoadingState label="대시보드 데이터를 불러오는 중..." />
        </div>
      </div>
    );
  }

  const row1 = data?.metrics_row1 ?? [];
  const row2 = data?.metrics_row2 ?? [];
  const dashboardMetricItems = [...row1, ...row2].map((item) => ({
    ...item,
    kind: item.kind as "money" | "percent" | "count",
    sub_kind: item.sub_kind as "money" | "percent" | "count" | undefined,
  }));
  const leftMetricItems = orderMetricItems(dashboardMetricItems, DASHBOARD_LEFT_LABELS);
  const holdingsStatusMetric = dashboardMetricItems.find((item) => item.label === "수익/손실 종목 수");
  const buckets = data?.buckets ?? [];
  const accountBuckets = data?.account_buckets ?? {};
  const accounts = data?.accounts ?? [];
  const sparklines = data?.sparklines ?? {};

  return (
    <div className="appPageStack">
      {error ? (
        <div className="appBannerStack">
          <div className="alert alert-danger mb-0">{error}</div>
        </div>
      ) : null}

      {/* 헤더 + 기준일 */}
      <div className="d-flex align-items-center justify-content-between">
        <div className="text-secondary" style={{ fontSize: "0.82rem" }}>
          스냅샷 {data?.latest_snapshot_date ?? "-"} · 주별 {data?.weekly_date ?? "-"} · 갱신 {formatUpdatedAt(data?.updated_at)}
        </div>
        <div className="d-flex align-items-center gap-2">
          <select
            className="form-select form-select-sm"
            style={{ width: "auto" }}
            value={periodMonths}
            onChange={(e) => setPeriodMonths(Number(e.target.value))}
          >
            {PERIOD_OPTIONS.map((opt) => (
              <option key={opt.months} value={opt.months}>지난 {opt.label}</option>
            ))}
          </select>
          {holdingsStatusMetric && holdingsStatusMetric.sub_value !== undefined ? (
            <div
              className="text-secondary"
              style={{ fontSize: "0.85rem", fontWeight: 600, whiteSpace: "nowrap" }}
            >
              수익/손실 종목 수{" "}
              <span className="text-success">{formatMetricValue(holdingsStatusMetric.value, holdingsStatusMetric.kind)}</span>
              <span className="text-secondary">/</span>
              <span className="text-danger">
                {formatMetricValue(holdingsStatusMetric.sub_value, holdingsStatusMetric.sub_kind ?? "count")}
              </span>
            </div>
          ) : null}
          <button
            type="button"
            className={`btn btn-sm ${hideMoney ? "btn-primary" : "btn-outline-secondary"}`}
            onClick={() => setHideMoney((c) => !c)}
          >
            {hideMoney ? "금액 보이기" : "금액 가리기"}
          </button>
        </div>
      </div>

      <div className="dashboardOverviewGrid">
        <div className="dashboardOverviewLeft">
          {leftMetricItems.map((item) => (
            <div key={`left-${item.label}`} className="dashboardOverviewMetric">
              <DashboardMetricCard
                item={item}
                hideMoney={hideMoney}
                periodMonths={periodMonths}
                sparklines={sparklines}
              />
            </div>
          ))}
        </div>

        <div className="dashboardOverviewRight">
          <div className="card dashboardOverviewChartCard">
            <div className="card-header dashboardMiniChartHeader">
              <h3 className="card-title dashboardMiniChartTitle">전체 구성 비중</h3>
            </div>
            <div className="card-body dashboardMiniChartBody">
              <div className="dashboardMiniChartCanvas">
                <DashboardDonutChart buckets={buckets} />
              </div>
              <DashboardBucketLegend buckets={buckets} />
            </div>
          </div>

          {DASHBOARD_ACCOUNT_WEIGHTS.map((config) => {
            const acctBuckets = accountBuckets[config.account_id] ?? [];
            return (
              <div key={config.account_id} className="card dashboardOverviewChartCard">
                <div className="card-header dashboardMiniChartHeader">
                  <h3 className="card-title dashboardMiniChartTitle">{config.icon} {config.label}</h3>
                </div>
                <div className="card-body dashboardMiniChartBody">
                  <div className="dashboardMiniChartCanvas">
                    <DashboardDonutChart buckets={acctBuckets} />
                  </div>
                  <DashboardBucketLegend buckets={acctBuckets} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* 계좌별 요약 */}
      <div className="card">
        <div className="card-header">
          <h3 className="card-title">계좌별 요약</h3>
        </div>
        <div className="table-responsive">
          <table className="table table-vcenter card-table">
            <thead>
              <tr>
                <th>계좌</th>
                <th className="text-end">총 자산</th>
                <th className="text-end">총 원금</th>
                <th className="text-end">평가 금액</th>
                <th className="text-end">현금</th>
                <th className="text-end">현금 비중</th>
                <th className="text-end">계좌 손익</th>
                <th className="text-end">수익률</th>
                <th className="text-end">금일 손익</th>
                <th className="text-end">금주 손익</th>
              </tr>
            </thead>
            <tbody>
              {accounts.map((a) => (
                <tr key={a.account_id}>
                  <td>{renderAccountNameCell(a)}</td>
                  <td className="text-end">{mask(a.total_assets)}</td>
                  <td className="text-end">{mask(a.total_principal)}</td>
                  <td className="text-end">{mask(a.valuation_krw)}</td>
                  <td className="text-end">{mask(a.cash_balance)}</td>
                  <td className="text-end">{formatPercent(a.cash_ratio)}</td>
                  <td className={`text-end ${getSignedClass(a.net_profit)}`}>{mask(a.net_profit)}</td>
                  <td className={`text-end ${getSignedClass(a.net_profit_pct)}`}>{formatPercent(a.net_profit_pct)}</td>
                  <td className={`text-end ${getSignedClass(a.daily_profit)}`}>{mask(a.daily_profit)}</td>
                  <td className={`text-end ${getSignedClass(a.weekly_profit)}`}>{mask(a.weekly_profit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
