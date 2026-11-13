"use client";

// POC6-27 — 「지금 확인할 내용」의 보유 점검 · 잘 오르는 ETF 두 칸(설계 §4 · PLAN 판정 §4).
// POC6-29(설계 §2 · PLAN §2-2 · §3-2 · 판정 Q1 · Q2 · Q10 · Q13) — 두 칸을 각각 한 카드로 합쳤다(「보유 자세히」 ·
//   「잘 오르는 ETF 자세히」 없음).
// 보유 점검: [시장 배지] [보유 배지] → '보유 N종목 중 M종목 하락 · 판정 K종목' → 20구간 날짜 · 가격 상태 · 해당 비중.
//   판정 = 「보유」와 같은 요약 응답의 price_flow · 같은 함수(declineJudged · isDecline) · 종목 단위(계좌 합산).
//   판정 못 한 보유는 '하락 아님'으로 세지 않고 판정 수를 따로 적는다. 종목별 수치는 [보유 보기 →](「보유」).
// 잘 오르는 ETF: 이 카드 자체 기간(1일 · 1개월 · 3개월 · 기본 저장) · 제외 4종 고정으로 같은 요약(공통 기간 목록)을 읽어
//   선정 1 ~ 3위를 보인다. 「후보리스트」 조건과 따로이고, [후보리스트 보기 →]는 그 화면 조건으로 연다.
import type { EnrichedHoldingsResult, MarketTopNResponse } from "@/lib/api";
import type { CompareBasis, CompareSummary, CompareSummaryOk } from "@/lib/api/etfCompare";
import type { QueryState } from "@/lib/api/queryCache";
import { BASIS_LABEL, endPriceText, md, pct, weightText } from "@/lib/etfCompare";
import { setScreenCondition, ETF_COMPARE_DEFAULT } from "@/lib/etfCompareCondition";
import HelpPopover from "../holdings_risk_evidence/HelpPopover";
import type { MenuKey } from "../LeftSidebar";
import { BasisSaveRow } from "../workbench/CompareHead";
import { aggregateHoldings, declineJudged, isDecline, linkOf, type AggHolding } from "../workbench/holdingParts";
import { directionColor } from "../workbench/helpers";
import { joinStale, staleOf } from "./summaryLines";
import { regimeLabelKo } from "./todayHelpers";

type HoldingsState = "down_found" | "none_found" | "unknown" | "no_holdings";

const HOLDINGS_BADGE: Record<HoldingsState, string> = {
  down_found: "보유 약세",
  none_found: "보유 하락 구간 없음",
  unknown: "보유 판정 불완전",
  no_holdings: "보유 없음",
};

function marketBadge(market: QueryState<MarketTopNResponse>): string {
  if (market.phase === "loading" || market.phase === "idle") return "시장 판정 확인 중";
  const ctx = market.phase === "success" ? market.data.market_context : null;
  if (!ctx) return "시장 판정 확인 불가";
  if (ctx.regime_code === "bear") return "시장 약세";
  return `시장 ${regimeLabelKo(ctx.regime_code, ctx.regime_label)}`;
}

function okOf(q: QueryState<CompareSummary>): CompareSummaryOk | null {
  return q.phase === "success" && q.data.status === "ok" ? q.data : null;
}

// [요약 다시 읽기]에서 이 요약 원천을 부르는 이름(다시 읽기 실패 줄 · 일부 실패 표시와 같은 낱말).
export const SUMMARY_SOURCE_LABEL = "잘 오르는 ETF · 보유 하락 판정";

export interface HoldingsCount {
  total: number;
  judged: number;
  decline: AggHolding[];
  start20: string | null;
  endLine: string | null;
  bands: { label: string; count: number }[];
}

// 종목 단위 집계(「보유」와 같은 판정) — 요약을 못 받았으면 null(0종목으로 바꾸지 않음).
export function countHoldings(s: CompareSummaryOk | null, items: EnrichedHoldingsResult["items"] | null): HoldingsCount | null {
  if (!s || !items || s.holdings.status !== "ok") return null;
  const rows = aggregateHoldings(items);
  const judged = rows.filter((r) => declineJudged(linkOf(s, r.ticker), undefined));
  const decline = rows.filter((r) => isDecline(linkOf(s, r.ticker), undefined));
  const flows = rows.map((r) => linkOf(s, r.ticker)?.price_flow).filter((f): f is NonNullable<typeof f> => !!f);
  const ends = new Set(flows.map((f) => `${f.end_date}|${f.end_price?.state ?? ""}`));
  const f0 = flows[0];
  const bands = new Map<string, number>();
  for (const r of decline) {
    const label = linkOf(s, r.ticker)?.price_flow?.decline_band?.label ?? "하락";
    bands.set(label, (bands.get(label) ?? 0) + 1);
  }
  return {
    total: rows.length,
    judged: judged.length,
    decline,
    start20: f0?.start_date_20d ?? null,
    endLine:
      f0 && ends.size === 1 ? `${md(f0.end_date)} 가격 = ${endPriceText(f0.end_price)}` : f0 ? "가격 기준일이 종목마다 다름" : null,
    bands: [...bands.entries()].map(([label, count]) => ({ label, count })),
  };
}

function weightLine(c: HoldingsCount): string {
  // 하나도 판정하지 못했으면 '0%'가 아니라 셀 수 없음(「보유」의 '—'와 같은 뜻 · 검토 지적).
  if (c.judged === 0) return "해당 보유 비중 셀 수 없음";
  if (c.decline.length === 0) return "해당 보유 비중 0%";
  const known = c.decline.filter((r) => r.weight != null && r.weightOk === r.count);
  if (known.length === 0) return "해당 보유 비중 확인 불가";
  const sum = known.reduce((a, r) => a + (r.weight as number), 0);
  return `해당 보유 비중 ${weightText(sum)}(현금 제외 · 같은 종목 계좌 합산${known.length < c.decline.length ? ` · ${c.decline.length}종목 중 ${known.length}종목만 확인` : ""})`;
}

export function HoldingsCheckCard({
  market,
  summary,
  holdings,
  onNavigate,
}: {
  market: QueryState<MarketTopNResponse>;
  summary: QueryState<CompareSummary>;
  holdings: QueryState<EnrichedHoldingsResult>;
  onNavigate: (key: MenuKey) => void;
}) {
  const s = okOf(summary);
  const items = holdings.phase === "success" ? holdings.data.items : null;
  const c = countHoldings(s, items);
  // 다시 읽기에 실패한 원천은 이전 값과 그 시각을 적는다(완료로 위장 안 함 · 기존 계약).
  const stale = joinStale(staleOf("보유", holdings), staleOf(SUMMARY_SOURCE_LABEL, summary));
  const state: HoldingsState | null = !c
    ? null
    : c.total === 0
      ? "no_holdings"
      : c.decline.length > 0
        ? "down_found"
        : c.judged === c.total
          ? "none_found"
          : "unknown";
  const loading =
    summary.phase === "loading" || summary.phase === "idle" || holdings.phase === "loading" || holdings.phase === "idle";
  const failText =
    holdings.phase === "error"
      ? "보유 자료를 불러오지 못했습니다."
      : summary.phase === "error" || (summary.phase === "success" && summary.data.status !== "ok")
        ? "보유 하락 판정 자료를 불러오지 못했습니다."
        : s && s.holdings.status !== "ok"
          ? "보유 하락 판정 자료가 보유를 읽지 못했습니다."
          : null;
  const help = c
    ? [
        "판정 = 「보유」 화면과 같은 응답 · 같은 기존 20구간 하락 판정(PC 저장 종가 · 약 5% 이상 하락) · 종목 단위(같은 종목 여러 계좌 = 하나).",
        `구간 판정 가능 ${c.judged}/${c.total}종목 · ` + (c.bands.length ? c.bands.map((b) => `${b.label} ${b.count}종목`).join(" · ") : "하락 구간 0종목"),
        "판정하지 못한 보유(가격 자료 없음 · 이력 부족 · 기준일 다름)는 하락 수에 넣지 않습니다.",
      ]
    : [];
  return (
    <section className="tc-card tc-check" aria-label="보유 점검" data-testid="tc-risk-strip">
      <div className="tc-check-head">
        <h3 className="tc-h3">보유 점검</h3>
        {c ? <HelpPopover label="보유 점검" paragraphs={help} /> : null}
      </div>
      <div className="tc-check-badges">
        <span className="tc-sum-badge tc-sum-info">{marketBadge(market)}</span>{" "}
        {state ? <span className="tc-sum-badge tc-sum-info">{HOLDINGS_BADGE[state]}</span> : null}
      </div>
      {failText ? (
        <div className="tc-check-main" data-testid="tc-risk-failed">
          {failText}
        </div>
      ) : !c ? (
        <div className="tc-muted">{loading ? "보유 · 하락 판정 자료를 불러오는 중입니다" : "하락 판정 요약을 만들 수 없습니다"}</div>
      ) : c.total === 0 ? (
        <div className="tc-check-main">판정할 보유 종목이 없습니다</div>
      ) : (
        <>
          <div className="tc-check-main">
            <strong className="tc-risk-num" data-testid="tc-hold-count">
              {c.judged === 0
                ? `보유 ${c.total}종목 · 하락 판정을 하지 못했습니다(판정 0종목)`
                : `보유 ${c.total}종목 중 ${c.decline.length}종목 하락 · 판정 ${c.judged}종목`}
            </strong>
          </div>
          <div className="tc-muted tc-small" data-testid="tc-hold-basis">
            최근 20저장 구간{c.start20 ? ` ${md(c.start20)} → ` : " "}
            {c.endLine ?? "가격 기준일 확인 불가"} · {weightLine(c)}
            {c.judged < c.total ? ` · 판정 못 한 보유 ${c.total - c.judged}종목은 세지 않음` : ""}
          </div>
        </>
      )}
      {stale ? <div className="tc-sum-stale">{stale}</div> : null}
      <div className="tc-btn-row">
        <button type="button" className="tc-btn tc-btn-link" onClick={() => onNavigate("workbench_holdings")}>
          보유 보기 →
        </button>
      </div>
    </section>
  );
}

const BASES: CompareBasis[] = ["daily", "one_month", "three_month"];

export function CandidatesCheckCard({
  summary,
  basis,
  onNavigate,
}: {
  summary: QueryState<CompareSummary>;
  basis: CompareBasis;
  onNavigate: (key: MenuKey) => void;
}) {
  const s = okOf(summary);
  const top = s ? s.top.slice(0, 3) : [];
  const stale = staleOf(SUMMARY_SOURCE_LABEL, summary);
  return (
    <section className="tc-card tc-check" aria-label="잘 오르는 ETF" data-testid="tc-cand-check">
      <h3 className="tc-h3">잘 오르는 ETF</h3>
      <div className="tc-check-badges">
        <span className="holdings-sort-seg" role="group" aria-label="잘 오르는 ETF 기간">
          {BASES.map((b) => (
            <button
              key={b}
              type="button"
              className={basis === b ? "on" : undefined}
              aria-pressed={basis === b}
              onClick={() => setScreenCondition("today", { basis: b, filters: ETF_COMPARE_DEFAULT.filters })}
            >
              {BASIS_LABEL[b]}
            </button>
          ))}
        </span>
        <span className="tc-muted tc-small">인버스 · 레버리지 · 합성 · 선물형 제외(고정)</span>
      </div>
      <BasisSaveRow screen="today" basis={basis} />
      {s ? (
        <>
          <div className="tc-muted tc-small" data-testid="tc-cand-line">
            {BASIS_LABEL[s.basis]} 수익률 상위 · {md(s.period.start)} → {md(s.period.end)} · {md(s.price_state.end_date)} 가격 ={" "}
            {s.price_state.intraday_count > 0 ? "장중 저장값 포함(잠정)" : s.price_state.after_close_count > 0 ? "마감 뒤 저장" : "마감값 확인 필요"} ·
            비교한 ETF {s.counts.population.toLocaleString("ko-KR")}개 · 기간이 달라 뺀 {s.counts.period_differs}개
          </div>
          <ol className="tc-cand-top" data-testid="tc-cand-top">
            {top.map((r) => (
              <li key={r.ticker}>
                <span className="tc-cand-rank">{r.rank}위</span>
                <span className="tc-cand-name">{r.name ?? r.ticker}</span>
                <span style={{ color: directionColor(r.basis_return.value), fontWeight: 600 }}>{pct(r.basis_return.value)}</span>
              </li>
            ))}
          </ol>
          <div className="tc-muted tc-small">이 카드의 조건으로 공통 기간 목록을 계산한 선정 1 ~ 3위 · 「후보리스트」 조건과 따로입니다</div>
        </>
      ) : summary.phase === "loading" || summary.phase === "idle" ? (
        <div className="tc-muted">목록을 불러오는 중입니다 · {BASIS_LABEL[basis]}</div>
      ) : summary.phase === "error" ? (
        <div className="tc-warn">목록을 불러오지 못했습니다 · [요약 다시 읽기]로 다시 시도하세요</div>
      ) : (
        <div className="tc-warn" data-testid="tc-cand-notok">
          {summary.data.message ?? "비교 목록을 만들 수 없습니다"}
        </div>
      )}
      {stale ? <div className="tc-sum-stale">{stale}</div> : null}
      <div className="tc-btn-row">
        <button type="button" className="tc-btn tc-btn-link" onClick={() => onNavigate("workbench")}>
          후보리스트 보기 →
        </button>
      </div>
    </section>
  );
}
