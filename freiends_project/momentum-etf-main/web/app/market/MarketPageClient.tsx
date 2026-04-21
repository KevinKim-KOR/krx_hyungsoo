"use client";

import { useMemo, useState } from "react";

import { PageFrame } from "../components/PageFrame";
import { MarketManager } from "./MarketManager";

type MarketHeaderSummary = {
  filteredCount: number;
  totalCount: number;
  updatedAt: string | null;
};

const DEFAULT_SUMMARY: MarketHeaderSummary = {
  filteredCount: 0,
  totalCount: 0,
  updatedAt: null,
};

function formatUpdatedAtWithElapsed(value: string | null | undefined): string {
  if (!value) {
    return "-";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const absolute = new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Seoul",
  }).format(date);

  const diffMs = Math.max(0, Date.now() - date.getTime());
  const totalMinutes = Math.floor(diffMs / 60000);
  const days = Math.floor(totalMinutes / (24 * 60));
  const hours = Math.floor((totalMinutes % (24 * 60)) / 60);
  const minutes = totalMinutes % 60;
  const elapsedParts: string[] = [];

  if (days > 0) {
    elapsedParts.push(`${days}일`);
  }
  if (hours > 0) {
    elapsedParts.push(`${hours}시간`);
  }
  if (minutes > 0 || elapsedParts.length === 0) {
    elapsedParts.push(`${minutes}분`);
  }

  return `${absolute}(${elapsedParts.join(" ")}전)`;
}

export function MarketPageClient() {
  const [summary, setSummary] = useState<MarketHeaderSummary>(DEFAULT_SUMMARY);

  const titleRight = useMemo(
    () => (
      <div className="appHeaderMetrics rankToolbarMeta">
        <div className="appHeaderMetric">
          <span>총:</span>
          <span className="appHeaderMetricValue">{new Intl.NumberFormat("ko-KR").format(summary.filteredCount)}개</span>
        </div>
        <div className="appHeaderMetric">
          <span>전체:</span>
          <span className="appHeaderMetricValue">{new Intl.NumberFormat("ko-KR").format(summary.totalCount)}개</span>
        </div>
        <div className="appHeaderMetric">
          <span>마지막 종목 리스트 갱신:</span>
          <span className="appHeaderMetricValue">{formatUpdatedAtWithElapsed(summary.updatedAt)}</span>
        </div>
      </div>
    ),
    [summary],
  );

  return (
    <PageFrame title="🇰🇷 ETF 마켓" fullHeight fullWidth titleRight={titleRight}>
      <MarketManager onHeaderSummaryChange={setSummary} />
    </PageFrame>
  );
}
