"use client";

import { useMemo, useState } from "react";

import { PageFrame } from "../components/PageFrame";
import { AssetsManager } from "./AssetsManager";

type AssetsHeaderSummary = {
  totalAssets: number;
  totalValuation: number;
  totalCash: number;
  accountCount: number;
};

const DEFAULT_SUMMARY: AssetsHeaderSummary = {
  totalAssets: 0,
  totalValuation: 0,
  totalCash: 0,
  accountCount: 0,
};

function formatKrw(value: number): string {
  return `${new Intl.NumberFormat("ko-KR").format(Math.round(value))}원`;
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat("ko-KR").format(value);
}

function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function AssetsPageClient() {
  const [summary, setSummary] = useState<AssetsHeaderSummary>(DEFAULT_SUMMARY);
  const cashRatio = useMemo(
    () => (summary.totalAssets > 0 ? (summary.totalCash / summary.totalAssets) * 100 : 0),
    [summary.totalAssets, summary.totalCash],
  );

  const titleRight = useMemo(
    () => (
      <div className="appHeaderMetrics rankToolbarMeta">
        <div className="appHeaderMetric">
          <span>총 자산:</span>
          <span className="appHeaderMetricValue is-primary">{formatKrw(summary.totalAssets)}</span>
        </div>
        <div className="appHeaderMetric">
          <span>평가액:</span>
          <span className="appHeaderMetricValue">{formatKrw(summary.totalValuation)}</span>
        </div>
        <div className="appHeaderMetric">
          <span>현금:</span>
          <span className="appHeaderMetricValue">
            {formatKrw(summary.totalCash)}({formatPercent(cashRatio)})
          </span>
        </div>
        <div className="appHeaderMetric">
          <span>계좌수:</span>
          <span className="appHeaderMetricValue">{formatNumber(summary.accountCount)}</span>
        </div>
      </div>
    ),
    [cashRatio, summary],
  );

  return (
    <PageFrame title="자산 관리" fullHeight fullWidth titleRight={titleRight}>
      <AssetsManager onHeaderSummaryChange={setSummary} />
    </PageFrame>
  );
}
