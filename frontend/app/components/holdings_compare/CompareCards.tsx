"use client";

// 보유와 비교 — 카드 목록 (2026-08-16 사용자 실화면 직접 지시).
//
// 이 화면의 목적은 **내가 가진 것과 추천된 것의 비교**다. 그러려면 같은 기간의
// 수익률이 좌우 같은 자리에 있어야 하는데, 보유 쪽 evidence 에 1개월·3개월밖에
// 없어 견줄 수가 없었다. 백엔드에서 6개월·12개월을 채워(신규 계산 0건 — 후보
// returns 에 이미 있던 값을 옮기지 않던 것) 양쪽 모두 4개 기간을 나란히 놓는다.
//
// 카드 규칙은 다른 화면과 같다: 좌측 2단 + 우측 지표 + 정상이면 배지 숨김.
//   보유 : 큰 숫자 = 현재 손익률(사용자 지정) · 우측 1/3/6/12개월 + 20일 KODEX 초과
//   후보 : 큰 숫자 = 순위 기준 표기("1개월 1위") · 우측 동일 4칸 + 20일 KODEX 초과
//
// 참고점수는 카드에서 뺐다 — 이 맥 환경에서 항상 null 이고(ML 미실행),
// 사유(relative_upside_reasons)도 점수와 한 몸이라 함께 비어 있다. 대신 후보가
// **왜 이 목록에 있는지**를 응답의 basis+rank 로 그대로 적는다(새 판단 문구를
// 만들지 않는다 — 관찰값만 제공하는 원칙).

import type { MarketBasis, MarketCandidate } from "@/lib/api";
import type { HoldingsMarketEvidenceItem } from "@/lib/api";
import {
  type AggregatedHolding,
  type ExposureSummary,
  exposureLabel,
  exposureColor,
  candidateDataState,
  fmtPct,
  returnColor,
  DASH,
} from "./helpers";

// 순위 기준 표기 — 응답의 basis 를 사람이 읽는 말로. 값을 만들지 않고 이름만 붙인다.
const BASIS_LABEL: Record<MarketBasis, string> = {
  daily: "일간",
  one_month: "1개월",
  three_month: "3개월",
};

function periodCells(
  values: [string, number | null][],
): React.ReactElement {
  return (
    <div className="wb-hm4">
      {values.map(([label, v]) => (
        <div className="wb-hm-cell" key={label}>
          <span className="k">{label}</span>
          <span className="v" style={{ color: returnColor(v) }}>
            {v == null ? DASH : `${v >= 0 ? "+" : ""}${v.toFixed(2)}`}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── 보유 ETF 카드 ──────────────────────────────────────────────────────────
export function HoldingCompareCards({
  rows,
  evidenceByTicker,
  selectedTicker,
  onSelect,
}: {
  rows: AggregatedHolding[];
  evidenceByTicker: Record<string, HoldingsMarketEvidenceItem | undefined>;
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
}) {
  if (rows.length === 0) {
    return <p className="wb-muted">보유 ETF 가 없습니다.</p>;
  }
  return (
    <div className="wb-hlist" data-testid="compare-holding-list">
      {rows.map((h) => {
        const ev = evidenceByTicker[h.ticker];
        const r = ev?.returns;
        const ok = r?.status === "ok";
        const ex20 = ev?.short_term_momentum?.excess_vs_kodex200_20d_pctp ?? null;
        const isSel = selectedTicker === h.ticker;
        return (
          <div
            key={h.ticker}
            className={`wb-hrow compact${isSel ? " sel" : ""}`}
            role="button"
            tabIndex={0}
            aria-pressed={isSel}
            aria-label={`${h.name ?? h.ticker} 상세 보기`}
            onClick={() => onSelect(h.ticker)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(h.ticker);
              }
            }}
          >
            <div className="wb-hcard">
              <div className="wb-hrow-top">
                <div className="wb-hrow-name">
                  {h.name ?? h.ticker}
                  {h.data_missing || h.eval_partial_unavail ? (
                    <span className="wb-hbadges">
                      <span className="wb-hb warn">자료 확인 필요</span>
                    </span>
                  ) : null}
                </div>
                <div className="wb-hrow-pnl">
                  <span
                    className="amt"
                    style={{ color: returnColor(h.pnl_rate_pct) }}
                  >
                    {fmtPct(h.pnl_rate_pct)}
                  </span>
                  <span className="rate wb-hmuted">손익률</span>
                </div>
              </div>
              <div className="wb-hrow-bot">
                <div className="wb-hrow-facts">
                  <span className="tk">{h.ticker}</span>
                  <span className="sep">/</span>
                  {h.market_weight_pct == null ? (
                    <span className="wb-hmuted">비중 자료 확인 필요</span>
                  ) : (
                    <span>
                      비중{" "}
                      <span className="wv">{fmtPct(h.market_weight_pct)}</span>
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="wb-hmetrics">
              {periodCells([
                ["1개월", ok ? r?.one_month_return_pct ?? null : null],
                ["3개월", ok ? r?.three_month_return_pct ?? null : null],
                ["6개월", ok ? r?.six_month_return_pct ?? null : null],
                ["12개월", ok ? r?.twelve_month_return_pct ?? null : null],
              ])}
              <div className="wb-hm-ex">
                <span className="k">20일 KODEX 초과</span>
                <span className="v" style={{ color: returnColor(ex20) }}>
                  {fmtPct(ex20)}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ── 후보 ETF 카드 ──────────────────────────────────────────────────────────
export function CandidateCompareCards({
  rows,
  basis,
  exposureByTicker,
  selectedTicker,
  onSelect,
}: {
  rows: MarketCandidate[];
  basis: MarketBasis;
  exposureByTicker: Record<string, ExposureSummary | undefined>;
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
}) {
  if (rows.length === 0) {
    return <p className="wb-muted">후보 ETF 가 없습니다.</p>;
  }
  return (
    <div className="wb-hlist" data-testid="compare-candidate-list">
      {rows.map((c, idx) => {
        const exposure = c.ticker ? exposureByTicker[c.ticker] : undefined;
        const ret = c.returns;
        const ex20 = c.excess_return?.vs_kodex200_1m_pctp ?? null;
        const dq = candidateDataState(c);
        const isSel = !!c.ticker && selectedTicker === c.ticker;
        return (
          <div
            key={`${c.ticker ?? "x"}-${idx}`}
            className={`wb-hrow compact${isSel ? " sel" : ""}`}
            role="button"
            tabIndex={0}
            aria-pressed={isSel}
            aria-label={`${c.name ?? c.ticker ?? "종목"} 상세 보기`}
            onClick={() => c.ticker && onSelect(c.ticker)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                if (c.ticker) onSelect(c.ticker);
              }
            }}
          >
            <div className="wb-hcard">
              <div className="wb-hrow-top">
                <div className="wb-hrow-name">
                  {c.name ?? c.ticker ?? DASH}
                  <span className="wb-hbadges">
                    {exposure ? (
                      <span
                        className="wb-hb"
                        style={{
                          color: exposureColor(exposure),
                          background: "rgba(107,114,128,0.10)",
                        }}
                      >
                        {exposureLabel(exposure)}
                      </span>
                    ) : null}
                    {/* 데이터 상태는 정상이면 띄우지 않는다 (다른 화면과 같은 규칙). */}
                    {dq && dq !== "ok" ? (
                      <span className="wb-hb warn">⚠ 데이터 {dq}</span>
                    ) : null}
                  </span>
                </div>
                <div className="wb-hrow-pnl">
                  {/* 참고점수 대신 "왜 이 목록에 있는지" — 응답의 basis + rank 그대로. */}
                  <span className="amt cand-basis-rank">
                    {c.rank != null
                      ? `${BASIS_LABEL[basis]} ${c.rank}위`
                      : BASIS_LABEL[basis]}
                  </span>
                </div>
              </div>
              <div className="wb-hrow-bot">
                <div className="wb-hrow-facts">
                  <span className="tk">{c.ticker ?? DASH}</span>
                </div>
              </div>
            </div>
            <div className="wb-hmetrics">
              {periodCells([
                ["1개월", ret?.one_month?.return_pct ?? null],
                ["3개월", ret?.three_month?.return_pct ?? null],
                ["6개월", ret?.six_month?.return_pct ?? null],
                ["12개월", ret?.twelve_month?.return_pct ?? null],
              ])}
              <div className="wb-hm-ex">
                <span className="k">20일 KODEX 초과</span>
                <span className="v" style={{ color: returnColor(ex20) }}>
                  {fmtPct(ex20)}
                </span>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
