"use client";

// POC2 — Holdings × Market Discovery Evidence 1차 (2026-06-03).
//
// 지시문 §5.12 — Holdings 화면의 최소 표시. UI 전면 개편 X. 카드 1개.
// 페이지 로드 / polling 으로 자동 호출하지 않고 사용자가 [Evidence 조회] 버튼을
// 누를 때만 GET /holdings/market-evidence/latest 호출. read-only API.
//
// 표시 정책 (지시문 §5.10 금지 표현 회피):
// - 매수 / 매도 / 교체 / 진입 / 비중 확대·축소 / 탈락 / 대표 ETF 어휘 사용 X.
// - 데이터 상태 (matched / not_in_current_topn / unavailable / constituents_unavailable
//   / nav_discount.unavailable) 자체만 표시.
// - 첫 holding 의 evidence_notes 만 노출 — 종목별 리스트 전면 표시는 다음 STEP.

import { useCallback, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchHoldingsMarketEvidence,
  type HoldingsMarketEvidenceResponse,
} from "@/lib/api";

export default function HoldingsMarketEvidenceCard() {
  const [data, setData] = useState<HoldingsMarketEvidenceResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchHoldingsMarketEvidence();
      setData(res);
    } catch (e) {
      if (e instanceof ApiConfigError) {
        setError(e.message);
      } else if (e instanceof ApiRequestError) {
        setError(`API 요청 실패 (HTTP ${e.httpStatus}): ${e.message}`);
      } else {
        setError(`알 수 없는 오류: ${(e as Error).message}`);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <section
      style={{
        border: "1px solid #ccc",
        padding: "1rem",
        borderRadius: "0.5rem",
        marginTop: "1rem",
      }}
    >
      <h3 style={{ margin: "0 0 0.5rem 0", fontSize: "1rem" }}>
        보유 vs 시장 Evidence (1차)
      </h3>
      <p style={{ margin: "0 0 0.75rem 0", fontSize: "0.85rem", color: "#555" }}>
        Read-only. 외부 fetch 없음. 보유 ETF 가 현재 Market Discovery 후보 /
        시장 국면 / 단기 흐름 / 구성종목 중복 / NAV 상태와 어떻게 연결되는지
        확인용 evidence. 매수·매도·교체 판단 아님.
      </p>
      <button
        type="button"
        onClick={handleFetch}
        disabled={loading}
        style={{ padding: "0.4rem 0.8rem", marginBottom: "0.75rem" }}
      >
        {loading ? "조회 중..." : "Evidence 조회"}
      </button>
      {error && (
        <p style={{ color: "#c00", fontSize: "0.85rem", margin: "0.5rem 0" }}>
          {error}
        </p>
      )}
      {data && <EvidenceBody data={data} />}
    </section>
  );
}

function EvidenceBody({ data }: { data: HoldingsMarketEvidenceResponse }) {
  const { summary, market_context, holdings, warnings, market_asof, holdings_asof } =
    data;

  if (summary.total_holdings_count === 0) {
    return (
      <p style={{ fontSize: "0.85rem", margin: "0.5rem 0" }}>
        저장된 holdings 가 없습니다. 보유 종목을 입력하고 저장한 뒤 다시 조회해
        주세요.
      </p>
    );
  }

  return (
    <div style={{ fontSize: "0.85rem" }}>
      <SummaryRow summary={summary} />
      {market_context && <MarketContextRow context={market_context} />}
      <p style={{ margin: "0.25rem 0", color: "#666" }}>
        {market_asof && <>market_asof: {market_asof} </>}
        {holdings_asof && <>· holdings_asof: {holdings_asof}</>}
      </p>
      {warnings.length > 0 && (
        <ul style={{ margin: "0.25rem 0 0.5rem 1rem", color: "#a60" }}>
          {warnings.map((w, i) => (
            <li key={`w-${i}`}>{w}</li>
          ))}
        </ul>
      )}
      <HoldingsList holdings={holdings} />
    </div>
  );
}

function SummaryRow({
  summary,
}: {
  summary: HoldingsMarketEvidenceResponse["summary"];
}) {
  return (
    <p style={{ margin: "0.25rem 0" }}>
      <strong>보유 {summary.total_holdings_count}건</strong> 중 일치{" "}
      {summary.matched_topn_count}건 / TOP N 외{" "}
      {summary.not_in_current_topn_count}건 / 시장 비교 미가용{" "}
      {summary.evidence_unavailable_count}건. 구성종목 비교 가능{" "}
      {summary.constituents_available_count}건. NAV 미연동{" "}
      {summary.nav_discount_unavailable_count}건.
    </p>
  );
}

function MarketContextRow({
  context,
}: {
  context: NonNullable<HoldingsMarketEvidenceResponse["market_context"]>;
}) {
  return (
    <p style={{ margin: "0.25rem 0" }}>
      현재 시장 국면: <strong>{context.regime_label}</strong> ({context.regime_code})
    </p>
  );
}

function HoldingsList({
  holdings,
}: {
  holdings: HoldingsMarketEvidenceResponse["holdings"];
}) {
  if (holdings.length === 0) return null;
  return (
    <ul style={{ margin: "0.5rem 0 0 0", paddingLeft: "1.25rem" }}>
      {holdings.map((h) => (
        <li key={h.ticker} style={{ marginBottom: "0.4rem" }}>
          <strong>{h.name}</strong> ({h.ticker}) — {labelOfTopnStatus(h.topn_match.status)}
          {h.topn_match.status === "matched_topn_candidate" && h.topn_match.rank && (
            <> · rank {h.topn_match.rank}</>
          )}
          {h.evidence_notes.length > 0 && (
            <ul style={{ margin: "0.15rem 0 0 0.75rem", color: "#444" }}>
              {h.evidence_notes.map((note, i) => (
                <li key={`${h.ticker}-n-${i}`}>{note}</li>
              ))}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

function labelOfTopnStatus(status: string): string {
  switch (status) {
    case "matched_topn_candidate":
      return "Market Discovery 후보 일치";
    case "not_in_current_topn":
      return "TOP N 후보 외";
    case "unavailable":
    default:
      return "확인 불가";
  }
}
