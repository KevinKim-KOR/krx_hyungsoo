"use client";
// POC5-19 개정(2026-10-17 §2 · §4) — 세부 흐름 창 본문.
// 1) 세 근거의 실제 기준일 + 핵심 값 한 줄씩 → 2) 같은 날짜로 맞춘 최근 저장일(거래량 흐름 날짜) 기간 · ? →
// 3) 고른 날짜의 종가 · 거래량 줄(차트 바로 위 고정) → 4) 가격 선(이미 받은 가격 시계열을 날짜로 찾음 · 배열 위치로
// 짝짓지 않음 · 그날 종가가 없으면 '가격 자료 없음' · 선을 끊음) → 5) 거래량 막대 → 6) 계산 기간 · 출처.
// 가격 시계열은 기본 화면 가격 차트와 같은 공유 조회 키를 '구독만' 한다(lazy · 창이 조회를 시작하지 않음 →
// 열고 닫아도 · 앞 조회가 실패했어도 새 GET 없음 · 요청 중이면 그 결과를 기다림).
import { useState } from "react";
import { fetchPriceSeries, type HoldingsMarketEvidenceItem, type PriceBasis, type PriceSeriesResponse } from "@/lib/api";
import { useSharedQuery } from "@/lib/api/queryCache";
import { fmtValue } from "@/lib/chartScale";
import { priceFlowLine } from "@/lib/priceBasis";
import { NO_VOLUME_TEXT, volumeSourceParts } from "@/lib/storedVolume";
import SeriesChart from "../charts/SeriesChart";
import { priceSeriesKey } from "../workbench/PriceChart";
import HelpPopover from "./HelpPopover";
import { declineDetailText } from "./declineSummary";
import { evidenceStrip } from "./evidenceStrip";
import type { RiskEvidenceRow } from "./helpers";
import { hidesValues, periodLine } from "./priceVolatility";
import VolumeBars from "./VolumeBars";
import { TREND_HELP_BASIS, TREND_HELP_PRICE_MATCH, missingNote, trendLimits } from "./volumeTrend";

export default function DetailFlowsBody({
  row,
  item,
  basis,
}: {
  row: RiskEvidenceRow;
  item: HoldingsMarketEvidenceItem | null;
  basis: PriceBasis | null;
}) {
  const vt = item?.volume_trend;
  const sv = item?.stored_volume;
  const pv = item?.price_volatility;
  const pd = row.price_dates;
  const name = row.name ?? row.ticker;
  const q = useSharedQuery<PriceSeriesResponse>(
    priceSeriesKey(row.ticker),
    () => fetchPriceSeries(row.ticker),
    { lazy: true },
  );
  const pts = vt?.points ?? [];
  const n = pts.length;
  const [sel, setSel] = useState<number | null>(null);
  const cur = Math.min(Math.max(sel ?? n - 1, 0), Math.max(n - 1, 0));

  const series = q.phase === "success" && q.data.availability === "AVAILABLE" ? q.data.series : null;
  const byDate = series ? new Map(series.map((p) => [p.date, p.price])) : null;
  const prices = pts.map((p) => byDate?.get(p.date) ?? null);
  const priceMissing = byDate ? prices.filter((v) => v === null).length : 0;

  // 가격 시계열을 쓸 수 없을 때의 문장은 기본 화면 가격 차트와 같은 구분(불러오는 중 · 조회 실패 · 저장 자료 없음 · 확인 불가).
  const priceUnavailable =
    q.phase === "loading" || q.phase === "idle"
      ? "가격 시계열 불러오는 중..."
      : q.phase === "error"
        ? "가격 시계열 확인 불가 (조회 실패)"
        : q.data.availability === "NO_DATA"
          ? "저장된 가격 데이터 없음"
          : "가격 확인 불가";
  const p = n > 0 ? pts[cur] : null;
  const curPrice = n > 0 ? prices[cur] : null;
  const priceText = !byDate
    ? q.phase === "loading" || q.phase === "idle"
      ? "불러오는 중"
      : "확인 불가"
    : curPrice !== null
      ? fmtValue(curPrice, "원")
      : "자료 없음";
  const volText = p ? (p.volume === null ? "값 없음" : fmtValue(p.volume, "주")) : "";
  const [src, win] = sv && sv.status !== "no_price_data" ? volumeSourceParts(sv) : ["", ""];
  const vnote = vt ? missingNote(vt) : null;

  return (
    <div className="dfw" data-testid="detail-flows-body">
      <div className="dfw-strip" data-testid="detail-flows-strip">
        {evidenceStrip(row, item, basis).map((l) => (
          <div key={l.key} className="dfw-strip-line">
            <span className="dfw-strip-k">
              {l.title} <span className="dfw-strip-date">기준일 {l.date}</span>
            </span>
            <span className="dfw-strip-v">{l.text}</span>
            {l.note ? <span className="dfw-strip-note hre-status-check">{l.note}</span> : null}
          </div>
        ))}
      </div>

      {n === 0 || !p ? (
        <p className="helper">{NO_VOLUME_TEXT}</p>
      ) : (
        <>
          <div className="dfw-period">
            <span data-testid="detail-flows-period">
              같은 날짜로 맞춘 최근 {n}개 저장일 · {pts[0].date} ~ {pts[n - 1].date}
            </span>
            <HelpPopover
              label="세부 흐름"
              paragraphs={[TREND_HELP_BASIS, TREND_HELP_PRICE_MATCH, ...trendLimits(vt)]}
            />
          </div>
          <div className="rc-readout" aria-live="polite" data-testid="detail-flows-readout">
            <span className="rc-readout-date">{p.date}</span> · 종가 <b>{priceText}</b> · 거래량{" "}
            <b>{volText}</b>
          </div>
          <div className="dfw-chart-title">종가(원)</div>
          {byDate ? (
            <SeriesChart
              dates={pts.map((x) => x.date)}
              values={prices}
              kind="line"
              unit="원"
              selected={cur}
              onSelect={setSel}
              label={`${name} 같은 날짜 종가`}
              height={150}
              warn={q.phase === "success" && q.stale}
              testId="detail-price"
            />
          ) : (
            <p className="helper dfw-chart-empty" data-testid="detail-price-unavailable">
              {priceUnavailable}
            </p>
          )}
          <div className="dfw-chart-title">거래량(주)</div>
          {vt ? (
            <VolumeBars ev={vt} selected={cur} onSelect={setSel} label={`${name} 같은 날짜 거래량`} />
          ) : null}
          {priceMissing || vnote ? (
            <div className="dfw-notes">
              {priceMissing ? (
                <div data-testid="detail-price-missing">
                  이 기간 중 가격 자료가 없는 날 {priceMissing}개는 선을 끊어 두었습니다(다른 날 값으로 채우지 않음).
                </div>
              ) : null}
              {vnote ? <div data-testid="volume-trend-note">{vnote}</div> : null}
            </div>
          ) : null}
        </>
      )}

      <div className="dfw-foot">
        {pd?.end_date ? <div>가격 흐름 · {priceFlowLine(pd.end_date, pd.start_date_5d, pd.start_date_20d)}</div> : null}
        <div data-testid="hre-decline-band">하락 구간 · {declineDetailText(row, basis)}</div>
        {src ? (
          <div>
            거래량 · {src} · {win}
          </div>
        ) : null}
        {pv && !hidesValues(pv) ? <div>가격 흔들림 · {periodLine(pv)}</div> : null}
      </div>
    </div>
  );
}
