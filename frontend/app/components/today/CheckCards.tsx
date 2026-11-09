"use client";

// POC6-27 — 「지금 확인할 내용」의 보유 점검 · 잘 오르는 ETF 두 칸(설계 §4 · PLAN 판정 §4).
//
// 보유 점검: [시장 배지] [보유 배지] → 'N종목 중 M종목 하락 구간' → 기준 · 해당 비중(현금 제외).
//   시장 배지 = §3 과 같은 KODEX 200 판정값(시장 판정 응답 · 하락장이면 '시장 약세'),
//   보유 배지 = 기존 보유 하락 구간 판정(riskStateFromQueries · 「확인 근거」와 같은 함수).
//   시장 국면 일수 · 구간 판정 가능 건수처럼 의미를 검산하는 내용은 [?] 안에.
// 잘 오르는 ETF: 실제 응답의 기간 · 방향 · 개수 · 기간 · 제외 조건 · 같은 목록의 앞 3개를 아래에 표시.
//   조건은 「요즘 잘 오르는 ETF」와 같은 탭 공유 조건(marketConditionStore).
import type {
  EnrichedHoldingsResult,
  HoldingsMarketEvidenceResponse,
  MarketTopNResponse,
} from "@/lib/api";
import type { QueryState } from "@/lib/api/queryCache";
import type { MarketCondition } from "@/lib/marketConditionStore";
import HelpPopover from "../holdings_risk_evidence/HelpPopover";
import { DECLINE_SHORT, PARTIAL_EVAL_TEXT, fmtShare } from "../holdings_risk_evidence/declineSummary";
import {
  FAILURE_TEXT,
  PARTIAL_JUDGE_TEXT,
  riskHelpParagraphs,
  riskStateFromQueries,
  type HoldingsState,
} from "../holdings_risk_evidence/riskCombination";
import type { MenuKey } from "../LeftSidebar";
import { candidateConditions, candidateLabel, candidatePeriod, joinStale, staleOf } from "./summaryLines";
import { regimeLabelKo } from "./todayHelpers";

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

export function HoldingsCheckCard({
  market,
  holdings,
  evidence,
  onNavigate,
  onDetail,
}: {
  market: QueryState<MarketTopNResponse>;
  holdings: QueryState<EnrichedHoldingsResult>;
  evidence: QueryState<HoldingsMarketEvidenceResponse>;
  onNavigate: (key: MenuKey) => void;
  onDetail: () => void;
}) {
  const risk = riskStateFromQueries(holdings, evidence);
  const d = risk?.summary ?? null;
  const stale = joinStale(staleOf("보유", holdings), staleOf("보유 근거", evidence));
  const help = risk
    ? [
        ...riskHelpParagraphs(risk),
        `지금 상태: ${risk.combo.text}`,
        `시장 국면(보유 근거 기준 · [요약 다시 읽기] 때 다시 계산): ${risk.regime ?? "확인 불가"}`,
        d
          ? `구간 판정 가능 ${d.judgeable}/${d.total}종목${risk.combo.partial ? ` · ${PARTIAL_JUDGE_TEXT}` : ""} · ` +
            d.bands.map((b) => `${DECLINE_SHORT[b.state]} ${b.count}종목`).join(" · ")
          : "하락 구간 요약을 만들 수 없습니다",
        `PC 저장 가격 기준일 ${d?.flowDate ?? "확인 불가"}`,
      ]
    : [];
  return (
    <section className="tc-card tc-check" aria-label="보유 점검" data-testid="tc-risk-strip">
      <div className="tc-check-head">
        <h3 className="tc-h3">보유 점검</h3>
        {risk ? <HelpPopover label="현재 상태" paragraphs={help} /> : null}
      </div>
      <div className="tc-check-badges">
        <span className="tc-sum-badge tc-sum-info">{marketBadge(market)}</span>{" "}
        {risk ? <span className="tc-sum-badge tc-sum-info">{HOLDINGS_BADGE[risk.combo.holdings]}</span> : null}
      </div>
      {!risk ? (
        <div className="tc-muted">보유 · 보유 근거를 불러오는 중입니다</div>
      ) : risk.combo.holdings === "no_holdings" ? (
        <div className="tc-check-main">판정할 보유 종목이 없습니다</div>
      ) : risk.failed ? (
        <div className="tc-check-main" data-testid="tc-risk-failed">
          {FAILURE_TEXT[risk.failed]}
        </div>
      ) : d ? (
        <>
          <div className="tc-check-main">
            <strong className="tc-risk-num">
              {d.total}종목 중 {d.inBand}종목 하락 구간
            </strong>
          </div>
          <div className="tc-muted tc-small">
            최근 20일 저장 종가 기준(약 5% 이상 하락) · 해당 보유 비중 {fmtShare(d.inBandShare)}(현금 제외 · 같은 종목 계좌 합산)
            {d.evalPartial && d.inBandShare !== null ? ` · ${PARTIAL_EVAL_TEXT}` : ""}
            {risk.combo.partial ? ` · ${PARTIAL_JUDGE_TEXT}` : ""}
          </div>
        </>
      ) : (
        <div className="tc-muted">하락 구간 요약을 만들 수 없습니다</div>
      )}
      {stale ? <div className="tc-sum-stale">{stale}</div> : null}
      <div className="tc-btn-row">
        <button type="button" className="tc-btn tc-btn-link" onClick={onDetail}>
          보유 자세히 ↓
        </button>
        <button type="button" className="tc-btn tc-btn-link" onClick={() => onNavigate("holdings_evidence")}>
          확인 근거 보기 →
        </button>
        <button type="button" className="tc-btn tc-btn-link" onClick={() => onNavigate("holdings")}>
          보유 현황 보기 →
        </button>
      </div>
    </section>
  );
}

function condText(c: MarketCondition): string {
  const basis = c.basis === "daily" ? "일간" : c.basis === "three_month" ? "3개월" : "1개월";
  const ex = [
    c.filters.exclude_inverse ? "인버스" : null,
    c.filters.exclude_leveraged ? "레버리지" : null,
    c.filters.exclude_synthetic ? "합성" : null,
    c.filters.exclude_futures ? "선물" : null,
  ].filter(Boolean);
  return `${basis} 수익률 ${c.order === "asc" ? "낮은 순" : "높은 순"} · ${ex.length ? `${ex.join(" · ")} 제외` : "제외 조건 없음"}`;
}

export function CandidatesCheckCard({
  market,
  condition,
  onNavigate,
  onDetail,
}: {
  market: QueryState<MarketTopNResponse>;
  condition: MarketCondition;
  onNavigate: (key: MenuKey) => void;
  onDetail: () => void;
}) {
  const data = market.phase === "success" && market.data.status === "ok" ? market.data : null;
  return (
    <section className="tc-card tc-check" aria-label="잘 오르는 ETF" data-testid="tc-cand-check">
      <h3 className="tc-h3">잘 오르는 ETF</h3>
      {data ? (
        <>
          <div className="tc-check-badges">
            <span className="tc-sum-badge tc-sum-info">{candidateLabel(data)}</span>
          </div>
          <div className="tc-check-main">
            <strong>조회한 ETF {data.candidates.length}개</strong>
          </div>
          <div className="tc-muted tc-small">
            {candidatePeriod(data.candidates)} · {candidateConditions(data)} · 같은 목록의 앞{" "}
            {Math.min(3, data.candidates.length)}개를 아래에 표시 · 「요즘 잘 오르는 ETF」와 같은 조건(이 탭)
          </div>
        </>
      ) : market.phase === "loading" || market.phase === "idle" ? (
        <div className="tc-muted">목록을 불러오는 중입니다 · 조건 {condText(condition)}</div>
      ) : (
        <div className="tc-warn">
          목록을 불러오지 못했습니다 · 요청한 조건 {condText(condition)} · 브라우저를 새로 고치거나 「요즘 잘 오르는
          ETF」에서 다시 읽어 주세요
        </div>
      )}
      <div className="tc-btn-row">
        <button type="button" className="tc-btn tc-btn-link" onClick={onDetail}>
          ETF 자세히 ↓
        </button>
        <button type="button" className="tc-btn tc-btn-link" onClick={() => onNavigate("market_discovery")}>
          요즘 잘 오르는 ETF →
        </button>
      </div>
    </section>
  );
}
