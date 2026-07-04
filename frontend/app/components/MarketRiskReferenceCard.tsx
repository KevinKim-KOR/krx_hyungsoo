"use client";

// Market Risk Reference v1 카드 (2026-07-03).
//
// 책임:
// - 시장 위험 참고 카드 — 첫 화면 KODEX200 + VIX 일별 맥락.
// - KODEX200: 기준일 / 종가 / 전일 대비.
// - VIX: 기준일 / 종가 / 전일 대비 / 5거래일 변화.
// - 기준일이 다르면 안내 문구 표시 (숨기지 않음).
// - 상세 펼치기: KODEX200 / VIX 최근 20거래일 미니 추이 (두 시계열은 별도).
//
// 지시문 §9 준수: 판단 라벨 / 위험 점수 / 시장 국면 라벨 추가 없음.

import { useState } from "react";

import type {
  MarketRiskKodex200,
  MarketRiskReference,
  MarketRiskRecentPoint,
  MarketRiskVix,
} from "@/lib/api";

const DASH = "-";

function fmtNum(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return value.toLocaleString("ko-KR", { maximumFractionDigits: digits });
}

function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

// 미니 sparkline — 외부 차트 라이브러리 없이 SVG polyline 만 사용.
function MiniSeries({ points }: { points: MarketRiskRecentPoint[] }) {
  if (!points.length) return <div className="helper">최근 관측값이 없습니다.</div>;
  const values = points.map((p) => p.close);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const width = 200;
  const height = 40;
  const step = points.length > 1 ? width / (points.length - 1) : 0;
  const coords = points
    .map((p, i) => {
      const x = i * step;
      const y = height - ((p.close - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <div className="market-risk-mini">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label="최근 20거래일 종가 미니 추이"
      >
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          points={coords}
        />
      </svg>
      <div className="helper" style={{ fontSize: "0.75rem" }}>
        {points[0].date} ~ {points[points.length - 1].date}
      </div>
    </div>
  );
}

function KodexPanel({ card }: { card: MarketRiskKodex200 }) {
  if (card.availability !== "available") {
    return (
      <div>
        <div className="market-risk-panel-title">KODEX200 (국내 기준선)</div>
        <div className="helper">시계열 최신화가 완료되지 않았습니다.</div>
      </div>
    );
  }
  return (
    <div>
      <div className="market-risk-panel-title">KODEX200 (국내 기준선)</div>
      <ul className="dashboard-status-list">
        <li>
          기준일: <strong>{card.as_of_date ?? DASH}</strong>
        </li>
        <li>
          종가: <strong>{fmtNum(card.close)}</strong>
        </li>
        <li>
          전일 대비: <strong>{fmtPct(card.change_1d_pct)}</strong>
        </li>
      </ul>
    </div>
  );
}

function VixPanel({ card }: { card: MarketRiskVix }) {
  if (card.availability !== "available") {
    return (
      <div>
        <div className="market-risk-panel-title">VIX (미국 변동성 참고)</div>
        <div className="helper">VIX 데이터가 아직 확인되지 않았습니다.</div>
      </div>
    );
  }
  return (
    <div>
      <div className="market-risk-panel-title">VIX (미국 변동성 참고)</div>
      <ul className="dashboard-status-list">
        <li>
          기준일: <strong>{card.as_of_date ?? DASH}</strong>
        </li>
        <li>
          종가: <strong>{fmtNum(card.close)}</strong>
        </li>
        <li>
          전일 대비: <strong>{fmtPct(card.change_1d_pct)}</strong>
        </li>
        <li>
          5거래일 변화: <strong>{fmtPct(card.change_5d_pct)}</strong>
        </li>
      </ul>
    </div>
  );
}

interface Props {
  reference: MarketRiskReference | null | undefined;
}

export default function MarketRiskReferenceCard({ reference }: Props) {
  const [expanded, setExpanded] = useState(false);
  if (!reference) {
    return (
      <div className="card market-risk-reference-card">
        <div className="card-title">시장 위험 참고</div>
        <div className="helper">시장 위험 참고 데이터가 아직 준비되지 않았습니다.</div>
      </div>
    );
  }
  const { kodex200, vix } = reference;
  const bothAvailable =
    kodex200.availability === "available" && vix.availability === "available";
  const asofDiffers =
    bothAvailable && kodex200.as_of_date !== vix.as_of_date;
  return (
    <div className="card market-risk-reference-card">
      <div className="card-title">시장 위험 참고</div>
      <div className="market-risk-body">
        <KodexPanel card={kodex200} />
        <VixPanel card={vix} />
      </div>
      {asofDiffers ? (
        <div className="helper" style={{ marginTop: 6 }}>
          국내·미국 시장의 마지막 확인 거래일은 다를 수 있습니다. 각 시장의 실제
          기준일을 표시합니다.
        </div>
      ) : null}
      <button
        type="button"
        className="link-button"
        onClick={() => setExpanded((prev) => !prev)}
        style={{ marginTop: 8 }}
      >
        {expanded ? "상세 접기" : "상세 펼치기"}
      </button>
      {expanded ? (
        <div className="market-risk-detail" style={{ marginTop: 8 }}>
          <div>
            <div className="market-risk-panel-title">
              KODEX200 최근 20거래일 추이
            </div>
            <MiniSeries points={kodex200.recent_20d_series ?? []} />
            <div className="helper" style={{ fontSize: "0.75rem" }}>
              전체 관측 범위: {kodex200.series_first_date ?? DASH} ~{" "}
              {kodex200.series_last_date ?? DASH}
            </div>
          </div>
          <div style={{ marginTop: 8 }}>
            <div className="market-risk-panel-title">
              VIX 최근 20거래일 추이
            </div>
            <MiniSeries points={vix.recent_20d_series ?? []} />
            <div className="helper" style={{ fontSize: "0.75rem" }}>
              전체 관측 범위: {vix.series_first_date ?? DASH} ~{" "}
              {vix.series_last_date ?? DASH}
            </div>
          </div>
          <div className="helper" style={{ marginTop: 6, fontSize: "0.75rem" }}>
            두 시계열은 별도 축으로 표시됩니다. 동일 축 겹치기 금지.
          </div>
        </div>
      ) : null}
    </div>
  );
}
