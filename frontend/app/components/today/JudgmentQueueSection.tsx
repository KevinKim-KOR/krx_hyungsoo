"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. **JSX·문구·className·핸들러·호출 조건을 고치지 않았다** —
// 바뀐 것은 파일 배치와 import/export 줄뿐이다.

import type { QueryState } from "@/lib/api/queryCache";
import type {
  EnrichedHoldingsResult,
  HoldingsMarketEvidenceResponse,
  MarketTopNResponse,
} from "@/lib/api";
import type { MenuKey } from "../LeftSidebar";
import { fmtPct } from "./todayHelpers";
import { describeMismatched } from "@/lib/priceBasis";
import { aggregateHoldingsByTicker } from "../holdings_compare/helpers";

// ── §4.2 판단 큐 (오늘 내가 확인할 것) ───────────────────────────────────────
export default function JudgmentQueueSection({
  market,
  holdings,
  evidence,
  onNavigate,
}: {
  market: QueryState<MarketTopNResponse>;
  holdings: QueryState<EnrichedHoldingsResult>;
  evidence: QueryState<HoldingsMarketEvidenceResponse>;
  onNavigate: (key: MenuKey) => void;
}) {
  // 보유 종목 수(고유 ticker) 와 자료 확인 필요 건수 — 직접 동선 요약(§7·AC-13).
  // §6.4 조회 상태 구분: 보유 종목 수는 holdings 조회 성공만으로 확정 표시한다. evidence
  // 로딩·실패가 이미 확인된 보유 수를 "확인 불가"로 덮지 않는다.
  const holdCount =
    holdings.phase === "success"
      ? new Set(holdings.data.items.map((it) => it.ticker)).size
      : null;
  // POC3-06 §6.1 단일 계산 원칙 — Dashboard 는 backend 공통 요약(judgment_summary)을
  // **그대로 표시**한다. 프론트에서 재계산하지 않는다(§9.2 Dashboard/PUSH 별도 계산
  // 금지). 최대 3건·자료 확인 필요 건수 모두 evidence 응답의 judgment_summary 사용.
  const summary =
    evidence.phase === "success" ? evidence.data.judgment_summary ?? null : null;
  const needCheckCount = summary?.holdings?.coverage?.need_check ?? null;
  const topHoldings = summary?.holdings?.top_holdings ?? [];
  // POC5-09 — 최대 3개는 backend 가 PC 비교 기준일에 맞는 후보로 다시 고른 결과(app/pc_price_basis.py).
  // 기준일이 달라 뺀 종목은 자료 확인 사유로 따로 보인다(정상 · 안전 판정 아님 · 판정 §9-4-3).
  const basis =
    evidence.phase === "success" ? (evidence.data.price_basis ?? null) : null;
  const mismatched = basis?.date_mismatch ?? [];
  // POC5-09 설계 §10-2-2 — 최대 3개의 비중 · 손익은 「확인 근거」와 같은 종목 합산
  // (aggregateHoldingsByTicker · 전체 계좌 평가 합 ÷ 전체 보유 평가 합 · (평가 합 − 매입 합) ÷ 매입 합).
  // backend 요약의 비중 · 손익은 같은 종목의 첫 계좌 값이라 쓰지 않는다. 선정 · 순서 · 5일 · 20일 ·
  // KODEX200 대비는 backend 요약 그대로. 보유 조회 전 · 실패면 비중 · 손익을 보이지 않는다.
  const aggByTicker =
    holdings.phase === "success"
      ? new Map(aggregateHoldingsByTicker(holdings.data.items).map((a) => [a.ticker, a]))
      : null;
  const candCount =
    market.phase === "success" && market.data.status === "ok"
      ? market.data.candidates.length
      : null;

  return (
    <section className="tc-card" aria-label="오늘 내가 확인할 것">
      <h2 className="tc-h2">오늘 내가 확인할 것</h2>

      {/* 요즘 잘 오르는 ETF — 건수 + 진입 (상세 표는 대시보드에 두지 않음) */}
      <div className="tc-queue-item">
        <div className="tc-queue-head">
          요즘 잘 오르는 ETF{" "}
          {candCount != null ? (
            <strong>{candCount}개</strong>
          ) : market.phase === "loading" ? (
            <span className="tc-muted tc-small">불러오는 중...</span>
          ) : (
            <span className="tc-muted tc-small">확인 불가</span>
          )}
        </div>
        <p className="tc-muted tc-small">
          최근 시장보다 강한 흐름을 보이는 ETF를 확인합니다.
        </p>
        <button
          type="button"
          className="tc-btn"
          onClick={() => onNavigate("workbench")}
        >
          ETF 비교하기
        </button>
      </div>

      {/* 내가 가진 ETF — 평가·확인 근거 직접 동선 (POC3-05 DESIGN_V2 §7·AC-13). */}
      <div className="tc-queue-item tc-divider">
        <div className="tc-queue-head">
          내가 가진 ETF{" "}
          {holdCount != null ? (
            <strong>{holdCount}개</strong>
          ) : holdings.phase === "loading" ? (
            <span className="tc-muted tc-small">불러오는 중...</span>
          ) : (
            <span className="tc-muted tc-small">확인 불가</span>
          )}
          {needCheckCount != null && needCheckCount > 0 ? (
            <span className="tc-muted tc-small">
              {` · 자료 확인 필요 ${needCheckCount}건`}
            </span>
          ) : null}
        </div>
        <p className="tc-muted tc-small">
          보유 평가는 &lsquo;보유 현황&rsquo;, 보유 ETF의 수치와 확인 근거는 &lsquo;확인
          근거&rsquo;에서 확인합니다.
        </p>

        {/* POC3-06 §6.3·§7.1 — 오늘 먼저 볼 보유 ETF 최대 3건(공통 요약 · 최근 5거래일 변화 낮은 순 ·
            backend select_top_holdings). OCI 보유 브리핑은 20거래일 하락 구간과 자료 확인 불가
            (DATA_UNAVAILABLE_OR_STALE)로 고르므로(select_holdings) 기준이 다르다(POC5-UI-02 §2). */}
        {topHoldings.length > 0 ? (
          <p className="tc-muted tc-small">
            최근 5거래일 변화가 낮은 보유 ETF부터 최대 3개
            {basis?.reference_date ? ` · PC 저장 가격 기준일 ${basis.reference_date}` : ""}
          </p>
        ) : null}
        {topHoldings.length > 0 ? (
          <ul className="tc-today-holdings">
            {topHoldings.map((r) => {
              const agg = aggByTicker?.get(r.ticker) ?? null;
              return (
                <li key={r.ticker}>
                  <span className="tc-th-name">{r.name ?? r.ticker}</span>{" "}
                  <span className="tc-muted tc-small">
                    5일 {fmtPct(r.return_5d_pct)} · 20일 {fmtPct(r.return_20d_pct)} ·
                    KODEX200 대비 {fmtPct(r.excess_vs_kodex200_20d_pctp)}
                    {agg?.market_weight_pct != null
                      ? ` · 비중 ${agg.market_weight_pct.toFixed(1)}%`
                      : ""}
                    {agg?.pnl_rate_pct != null ? ` · 손익 ${fmtPct(agg.pnl_rate_pct)}` : ""}
                  </span>
                </li>
              );
            })}
          </ul>
        ) : holdCount != null && holdCount > 0 ? (
          <p className="tc-muted tc-small">
            5일 흐름을 계산할 수 있는 보유 ETF가 없어 먼저 볼 종목을 정할 수 없습니다.
            &lsquo;확인 근거&rsquo;에서 자료 상태를 확인하세요.
          </p>
        ) : null}
        {mismatched.length > 0 ? (
          <p className="tc-muted tc-small" data-testid="tc-price-mismatch">
            가격 기준일이 달라 이 비교에서 뺀 보유: {describeMismatched(mismatched)} — 자료
            확인 필요
          </p>
        ) : null}

        <div className="tc-btn-row">
          <button
            type="button"
            className="tc-btn"
            onClick={() => onNavigate("holdings")}
          >
            보유 현황
          </button>
          <button
            type="button"
            className="tc-btn"
            onClick={() => onNavigate("holdings_evidence")}
          >
            확인 근거
          </button>
        </div>
      </div>
    </section>
  );
}

// ⓘ 근거 마커 — hover 툴팁으로 "무엇과 무엇을 비교/확인해 최신이 아닌지" 표시.
// 근거 표준은 후속 설계 대상 (사용자 2026-07-30 확정) — 현재는 실제 값 기반 임시 문구.
