"use client";

// POC6-29(설계 §2 · PLAN §2-2 · §3-7 · 판정 Q8) — 「오늘의 투자 점검」 [시장 근거와 다른 변화 보기] · 처음엔 접힘.
// POC6-29 보완 2차(판정서 V2 §2 · S 판정 §1 · Q-S1 · PLAN §10-3) — 한 번 열면 바로 읽는다(안쪽 접기 없음):
//   ① 근거 표(수급 · VIX · 원/달러 · WTI · 단기 흐름 5거래일 · 5회) · 함께 읽기(1개월 해석 · 실제 기간) ·
//      시장 위험 참고(KODEX 200 · VIX 20거래일 차트 · 펼친 채)
//   ② 기간별 흐름 · 날짜별 사건(기존 시장 흐름 카드 그대로)
//   ③ (아침 요약 미완료일 때만) 전일 자료 미완료 — 못 채운 자료의 이전 문장 · 마지막 시도 사유
// 시장 판정 근거 표 · 코스피 공식 종가(차트 · 코스피 지표 포함)는 접기 밖 「오늘 시장 변화」 당일 판정 바로 아래
// (RegimeBasisTable · KospiCloseBlock · 형수님 결정 2026-11-13).
// 출처 · 받은 시각은 상태 옆 [?] 안에만(형수님 결정 2026-11-12). 새 계산 없음.
import type { MarketTopNResponse } from "@/lib/api";
import type { MarketFlowContext } from "@/lib/api/marketFlow";
import type { MorningBasisResponse } from "@/lib/api/morningBasis";
import type { QueryState } from "@/lib/api/queryCache";
import type { ShortFlowsResponse } from "@/lib/api/shortFlows";
import { flowsSentence } from "@/lib/marketNowText";
import { itemOf, readiness } from "@/lib/morningText";
import { kospiObs, md, num2, signedPct } from "@/lib/todayMarketLines";
import MarketRiskReferenceCard from "../MarketRiskReferenceCard";
import MarketFlowCard from "../marketflow/MarketFlowCard";
import type { VixButton } from "../useMarketVixRetry";
import MarketEvidenceTable from "./MarketEvidenceTable";

export default function MarketEvidenceFold({
  market,
  flow,
  morning,
  short,
  vix,
  onVixRetry,
  vixDisabled,
}: {
  market: QueryState<MarketTopNResponse>;
  flow: QueryState<MarketFlowContext>;
  morning: QueryState<MorningBasisResponse>;
  short: QueryState<ShortFlowsResponse>;
  vix: VixButton;
  onVixRetry: () => void;
  vixDisabled: boolean;
}) {
  const reference = market.phase === "success" ? (market.data.market_risk_reference ?? null) : null;
  const fd = flow.phase === "success" ? flow.data : null;
  const mb = morning.phase === "success" ? morning.data : null;
  const sf = short.phase === "success" ? short.data : null;
  const obs = kospiObs(fd);
  const kItem = itemOf(mb, "kospi");
  const interp = fd?.interpretation?.["1M"] ?? null;
  const p1 = fd?.periods?.["1M"] ?? null;
  const ready = readiness(mb);
  const oldFlows = itemOf(mb, "flows")?.met === false ? flowsSentence(fd) : null;
  return (
    <details className="tc-card tc-evidence-fold" data-testid="tc-evidence-fold">
      <summary className="tc-h2">시장 근거와 다른 변화 보기</summary>
      <div className="tc-evidence-body">
        <section className="tc-evidence-sec" aria-label="수급 · VIX · 원/달러 · WTI">
          <h3 className="tc-h3">① 수급 · VIX · 원/달러 · WTI</h3>
          <MarketEvidenceTable
            flow={fd}
            short={sf}
            morning={mb}
            vix={reference?.vix ?? null}
            vixAction={
              vix.label ? (
                <button type="button" className="btn-md tc-fold-btn" onClick={onVixRetry} disabled={vixDisabled}>
                  {vix.label}
                </button>
              ) : null
            }
          />
          {vix.line ? (
            <p className={vix.line.error ? "tc-warn tc-small" : "tc-muted tc-small"} data-testid="tc-vix-retry-line">
              {vix.line.text}
            </p>
          ) : null}
          {interp && (interp.rows.length > 0 || interp.notes.length > 0) ? (
            <div className="tc-small" data-testid="tc-ev-together">
              <strong>
                1개월 해석 · {p1?.start ? md(p1.start) : "?"} ~ {p1 ? md(p1.end) : "?"}
              </strong>
              {interp.rows.map((r) => (
                <div key={r.join("|")}>
                  {r[0]} → {r[1]}
                  {r[2] ? <span className="tc-muted"> · {r[2]}</span> : null}
                </div>
              ))}
              {interp.notes.map((n) => (
                <div className="tc-muted" key={n}>
                  {n}
                </div>
              ))}
            </div>
          ) : null}
          <MarketRiskReferenceCard reference={reference} startOpen />
        </section>

        <section className="tc-evidence-sec" aria-label="시장 흐름 상세">
          <h3 className="tc-h3">② 기간별 흐름 · 날짜별 사건</h3>
          <MarketFlowCard />
        </section>

        {ready.ok === false ? (
          <section className="tc-evidence-sec" aria-label="전일 자료 미완료" data-testid="tc-ev-incomplete">
            <h3 className="tc-h3">③ 전일 자료 미완료</h3>
            <div className="tc-small">{ready.head}</div>
            {ready.reasons.map((t) => (
              <div className="tc-muted tc-small" key={t}>
                {t}
              </div>
            ))}
            {kItem && !kItem.met && obs ? (
              <div className="tc-small">
                코스피 공식 종가 {md(obs.date)} {num2(obs.value)}
                {obs.d1 ? `(${md(obs.d1.from_date)} 대비 ${signedPct(obs.d1.pct)})` : ""} — 기준일 전 자료
              </div>
            ) : null}
            {oldFlows ? (
              <div className="tc-small">
                {oldFlows.text}
                {oldFlows.basis ? <span className="tc-muted"> {oldFlows.basis}</span> : null} — 기준일 전 자료
              </div>
            ) : null}
          </section>
        ) : null}
      </div>
    </details>
  );
}
