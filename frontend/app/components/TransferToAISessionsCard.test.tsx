// POC5-22 — 새로 만드는 AI 전달 자료의 candidate_snapshot 에 화면과 같은 동일 기간 KODEX200 객체(판정 §2).
// 질문 본문(복사문)과 구조화 자료의 날짜 · 수치가 같아야 한다. 응답에 없으면 null(기존 차이로 채우지 않음).
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import type { MarketCandidate, MarketContext } from "@/lib/api";
import { toDecisionCandidateSnapshot } from "@/lib/api/decisionSessions";
import { loadAISessionsDraft } from "@/lib/aiSessionsDraft";
import { buildETFExposureDraftFromMarketDiscovery } from "@/lib/etfExposureDraft";
import { sameCopyText, sameViewOf } from "@/lib/samePeriodKodex";
import TransferToAISessionsCard from "./TransferToAISessionsCard";

const FILTERS = {
  exclude_inverse: true,
  exclude_leveraged: true,
  exclude_synthetic: true,
  exclude_futures: true,
};

const SAME = {
  one_month: {
    status: "ok" as const,
    reason: null,
    start_date: "2026-09-14",
    end_date: "2026-10-14",
    candidate_return_pct: 22.2689,
    kodex200_return_pct: -9.8615,
    diff_pctp: 32.1304,
  },
  three_month: {
    status: "unavailable" as const,
    reason: "kodex200_end_price_missing",
    start_date: "2026-07-16",
    end_date: "2026-10-14",
    candidate_return_pct: 33.7931,
    kodex200_return_pct: null,
    diff_pctp: null,
  },
};

function cands(): MarketCandidate[] {
  return [
    {
      rank: 1,
      ticker: "0005D0",
      name: "SOL 전고체배터리&실리콘음극재",
      tags: [],
      returns: { one_month: { return_pct: 22.2689 } },
      excess_return: { vs_kodex200_1m_pctp: 37.33, vs_kodex200_3m_pctp: 47.02 },
      same_period_kodex200: SAME,
    },
    {
      rank: 2,
      ticker: "0209D0",
      name: "KODEX 전고체배터리ESS TOP2플러스",
      tags: [],
      returns: { one_month: { return_pct: 20.3 } },
      excess_return: { vs_kodex200_1m_pctp: 35.36, vs_kodex200_3m_pctp: 44.2 },
    },
  ] as MarketCandidate[];
}

const CTX = {
  status: "ok",
  regime_label: "하락장",
  regime_code: "bear",
  regime_reasons: [],
  kodex200: { status: "ok" },
  kospi: { status: "unavailable" },
  warnings: [],
} as unknown as MarketContext;

describe("AI 전달 자료 — candidate_snapshot.same_period_kodex200", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it("'AI Sessions로 넘기기' 초안 — 화면 응답과 같은 객체 · 질문 본문과 같은 수치 · 없으면 null", () => {
    render(
      <TransferToAISessionsCard
        asof="2026-10-14"
        filters={FILTERS}
        candidates={cands()}
        linkedMarketRefreshId={null}
        marketContext={CTX}
        compact
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "AI Sessions로 넘기기" }));
    const draft = loadAISessionsDraft();
    expect(draft).not.toBeNull();
    expect(draft!.candidate_snapshot[0].same_period_kodex200).toEqual(SAME);
    expect(draft!.candidate_snapshot[1].same_period_kodex200).toBeNull();
    // 구조화 자료로 만든 문구 = 질문 본문 줄.
    const fromSnapshot = sameCopyText(sameViewOf(draft!.candidate_snapshot[0].same_period_kodex200, "1m"));
    expect(draft!.question_text).toContain(`동일 기간 KODEX200 대비 1개월: ${fromSnapshot}`);
    expect(draft!.question_text).toContain(
      "동일 기간 KODEX200 대비 3개월: 계산 불가 — KODEX200 끝일 가격 없음 (후보 기간 2026-07-16 → 2026-10-14)",
    );
    // 기존 market_context_snapshot 의 기간 다른 차이는 그대로 보존(새 값의 입력 · 대체값 아님).
    const mcs = draft!.market_context_snapshot as { candidate_excess_returns: { vs_kodex200_1m_pctp: number }[] };
    expect(mcs.candidate_excess_returns[0].vs_kodex200_1m_pctp).toBe(37.33);
  });

  it("ETF 구성종목 초안 · 공용 변환 함수도 같은 객체", () => {
    const d = buildETFExposureDraftFromMarketDiscovery({
      asof: "2026-10-14",
      filters: FILTERS,
      candidates: cands(),
      marketContext: CTX,
      marketContextSnapshot: null,
    });
    expect(d.candidate_snapshot[0].same_period_kodex200).toEqual(SAME);
    expect(d.candidate_snapshot[1].same_period_kodex200).toBeNull();
    expect(toDecisionCandidateSnapshot(cands()[0]).same_period_kodex200).toEqual(SAME);
    expect(toDecisionCandidateSnapshot(cands()[1]).same_period_kodex200).toBeNull();
  });
});
