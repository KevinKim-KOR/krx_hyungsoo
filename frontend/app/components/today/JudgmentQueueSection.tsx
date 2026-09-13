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
          보유 평가는 &lsquo;보유 현황&rsquo;, 오늘 먼저 볼 ETF와 수치 근거는 &lsquo;확인
          근거&rsquo;에서 확인합니다.
        </p>

        {/* POC3-06 §6.3·§7.1 — 오늘 먼저 볼 보유 ETF 최대 3건 (공통 요약, 5일 낮은 순).
            backend PUSH 와 동일 규칙(lowestFiveDayRows = select_top_holdings). */}
        {topHoldings.length > 0 ? (
          <ul className="tc-today-holdings">
            {topHoldings.map((r) => (
              <li key={r.ticker}>
                <span className="tc-th-name">{r.name ?? r.ticker}</span>{" "}
                <span className="tc-muted tc-small">
                  5일 {fmtPct(r.return_5d_pct)} · 20일 {fmtPct(r.return_20d_pct)} ·
                  KODEX200 대비 {fmtPct(r.excess_vs_kodex200_20d_pctp)}
                  {r.market_weight_pct != null
                    ? ` · 비중 ${r.market_weight_pct.toFixed(1)}%`
                    : ""}
                  {r.pnl_rate_pct != null ? ` · 손익 ${fmtPct(r.pnl_rate_pct)}` : ""}
                </span>
              </li>
            ))}
          </ul>
        ) : holdCount != null && holdCount > 0 ? (
          <p className="tc-muted tc-small">
            5일 흐름을 계산할 수 있는 보유 ETF가 없어 먼저 볼 종목을 정할 수 없습니다.
            &lsquo;확인 근거&rsquo;에서 자료 상태를 확인하세요.
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
