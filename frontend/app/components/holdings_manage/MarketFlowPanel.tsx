"use client";

// POC5-05 개정 2 §8 · §11-1 Q-B — 시장 흐름(PC 저장 종가 · 정형 값 · 사용자가 누를 때만).
// 마운트 때 GET /holdings/trade-history/market-flow 1회(부모가 [시장 흐름 보기]를 처음 누를 때만
// 마운트한다). 각 매매 = '기준일(판정 근거) 종가 → 마지막 저장일 종가' 변화와 같은 두 날짜의
// KOSPI 변화. '마지막 저장일'은 PC 에 저장된 마지막 날짜이며 오늘 시세가 아니므로 날짜를 늘 같이
// 보인다. 자료 없음 · 비교 불가는 사유 문구 그대로 · 출처가 다르면 '출처 다름' 표시. 판정 · 추천
// 문장 · ML 버튼은 없다(재진입 검토는 History 의 [재진입 검토] · POC5-06). 그리기는 `MarketFlowView`
// (재진입 검토 창이 이미 받은 시장 흐름을 같은 모양으로 그린다). POC5-07: 가격 비교 기준일이 있으면
// '가격 비교 기준일 이후 종가 변화'(기준일 → 마지막 저장일)를 맨 위에 · 종료 기간은 기준일 → 마지막
// 매도일 — 매수 · 손익이 아니라 종가 비교 출발점이다(실제 매수일 미상 표시는 그대로).

import { useEffect, useState } from "react";
import {
  fetchMarketFlow,
  type MarketFlowBasis,
  type MarketFlowEndpoint,
  type MarketFlowEvent,
  type MarketFlowPeriod,
  type MarketFlowReference,
  type MarketFlowResponse,
  type MarketFlowSeriesItem,
} from "@/lib/api";
import { apiErrorText, pnlClass } from "./format";
import { pct } from "./historyText";

interface Props {
  positionId: string;
  cycleId: string;
}

function src(p: MarketFlowEndpoint | null): string {
  return p?.source || "출처 미상";
}

function SeriesValue({ item }: { item: MarketFlowSeriesItem }) {
  if (item.status === "OK") {
    return (
      <>
        <b className={pnlClass(item.change_pct)}>{pct(item.change_pct)}</b>
        {item.source_differs ? (
          <>
            {" "}
            <span className="hmx-tag">
              출처 다름({src(item.start)} → {src(item.end)})
            </span>
          </>
        ) : item.start?.source ? (
          <span className="muted"> (출처 {item.start.source})</span>
        ) : null}
      </>
    );
  }
  const pair =
    item.status === "NOT_COMPARABLE" && item.start && item.end
      ? ` (${src(item.start)} → ${src(item.end)})`
      : "";
  return (
    <span className="muted">
      {item.reason ?? "자료 없음"}
      {pair}
    </span>
  );
}

function basisText(b: MarketFlowBasis): string {
  const moved = b.moved_to_next_trading_day ? ` · 거래일 ${b.trade_date}` : "";
  return `${b.basis_date ?? "—"}(${b.basis_note}${moved})`;
}

function EventLine({ ev }: { ev: MarketFlowEvent }) {
  const latest = ev.latest_stored_date
    ? `마지막 저장일 ${ev.latest_stored_date} 종가`
    : "마지막 저장일 없음";
  return (
    <li>
      {ev.kind === "SELL" ? (
        <>
          <strong>매도 뒤</strong>
          {" · "}
        </>
      ) : null}
      {ev.window_label}: {basisText(ev.basis)} 종가 → {latest}: <SeriesValue item={ev.ticker} />
      {" · 같은 날짜 KOSPI "}
      <SeriesValue item={ev.market} />
    </li>
  );
}

function ReferenceLine({ rf }: { rf: MarketFlowReference }) {
  const b = rf.basis;
  const moved = b.moved_to_next_trading_day ? ` · 설정한 기준일 ${b.trade_date}` : "";
  const latest = rf.latest_stored_date
    ? `마지막 저장일 ${rf.latest_stored_date} 종가`
    : "마지막 저장일 없음";
  return (
    <li>
      <strong>{rf.name}</strong>
      {" · "}
      {b.basis_date ?? "—"}({b.basis_note}
      {moved}) 종가 → {latest}: <SeriesValue item={rf.ticker} />
      {" · 같은 날짜 KOSPI "}
      <SeriesValue item={rf.market} />
    </li>
  );
}

function PeriodLine({ period }: { period: MarketFlowPeriod }) {
  if (!period.reason_code && period.ticker && period.market) {
    const ref = Boolean(period.reference_date);
    const day = (b: MarketFlowBasis | null | undefined, first: boolean) =>
      b
        ? `${b.basis_date ?? "—"}${
            b.moved_to_next_trading_day
              ? `(${first && ref ? "설정한 기준일" : "거래일"} ${b.trade_date} → 다음 거래일)`
              : ""
          }`
        : "—";
    // 기준일 구간은 '보유 기간'이라 부르지 않는다(그날 보유했다는 증거가 아님 · 설계 §1).
    return (
      <li>
        {ref ? "가격 비교 기준일" : "보유 기간: 최초 매수일"} {day(period.start_basis, true)} → 마지막 매도일{" "}
        {day(period.end_basis, false)} 종가 변화{" "}
        <SeriesValue item={period.ticker} />
        {" · 같은 기간 KOSPI "}
        <SeriesValue item={period.market} />
      </li>
    );
  }
  return <li className="muted">보유 기간: {period.reason ?? "계산 안 함"}</li>;
}

function seriesNames(d: MarketFlowResponse): string {
  const items: MarketFlowSeriesItem[] = d.events.flatMap((e) => [e.ticker, e.market]);
  if (d.reference_flow) items.push(d.reference_flow.ticker, d.reference_flow.market);
  if (d.holding_period?.ticker) items.push(d.holding_period.ticker);
  if (d.holding_period?.market) items.push(d.holding_period.market);
  const names = Array.from(new Set(items.map((i) => i.series_name)));
  return names.length > 0 ? names.join(" · ") : "ETF 저장 종가 · KOSPI 저장 종가";
}

export function MarketFlowView({ data }: { data: MarketFlowResponse }) {
  return (
    <>
      <ul>
        {data.reference_flow && data.purchase_date_unknown ? (
          <li className="muted">실제 매수일: 미상 — 매수 전후 변화는 계산하지 않습니다(아래는 종가 비교).</li>
        ) : null}
        {data.reference_flow ? <ReferenceLine rf={data.reference_flow} /> : null}
        {data.events.map((ev) => (
          <EventLine key={ev.record_id} ev={ev} />
        ))}
        {data.holding_period ? <PeriodLine period={data.holding_period} /> : null}
      </ul>
      <div className="muted hmx-small" style={{ marginTop: 6 }}>
        계열: {seriesNames(data)} · 출처는 각 날짜 행에 저장된 출처입니다.
      </div>
      <ul className="muted hmx-small">
        {data.reference_note ? <li>{data.reference_note}</li> : null}
        {data.notes.map((n) => (
          <li key={n}>{n}</li>
        ))}
      </ul>
    </>
  );
}

export default function MarketFlowPanel({ positionId, cycleId }: Props) {
  const [data, setData] = useState<MarketFlowResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    fetchMarketFlow(positionId, cycleId).then(
      (res) => {
        if (live) setData(res);
      },
      (e: unknown) => {
        if (live) setError(apiErrorText(e));
      },
    );
    return () => {
      live = false;
    };
  }, [positionId, cycleId]);

  return (
    <div className="hmx-flow" aria-live="polite">
      <b>시장 흐름</b> <span className="muted">· PC 저장 종가 · 직접 누를 때만 계산</span>
      {!data && !error ? (
        <p className="muted hmx-small" style={{ margin: "6px 0 0" }}>
          시장 흐름을 불러오는 중…
        </p>
      ) : null}
      {error ? (
        <div className="hmx-error" role="alert">
          {error}
        </div>
      ) : null}
      {data ? <MarketFlowView data={data} /> : null}
      <div className="muted hmx-small" style={{ marginTop: 6 }}>
        재진입 판단을 돕는 근거 · ML 연구 추정은 이 기간의 [재진입 검토]에서 봅니다.
      </div>
    </div>
  );
}
