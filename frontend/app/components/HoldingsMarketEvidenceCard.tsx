"use client";

// POC2 Operational UI Cleanup 1차 — Holdings × Market Evidence 카드 (2026-06-06).
//
// 지시문 §5.12 — Holdings 화면의 최소 표시. UI 전면 개편 X.
// 표시 정책 (지시문 §5.10 금지 표현 회피):
// - 매수 / 매도 / 교체 / 진입 / 비중 확대·축소 / 탈락 / 대표 ETF 어휘 사용 X.
// - 데이터 상태 자체만 표시.
// AC-4: 요약 수치 그리드 + 종목별 배지 + NAV 미연동 안내.

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
        border: "1px solid var(--border)",
        background: "var(--card)",
        padding: "1rem",
        borderRadius: "0.5rem",
        marginTop: "1rem",
      }}
    >
      <h3 style={{ margin: "0 0 0.25rem 0", fontSize: "1rem" }}>
        보유 vs 시장 Evidence
      </h3>
      <p
        style={{
          margin: "0 0 0.5rem 0",
          fontSize: "0.8rem",
          color: "var(--muted)",
        }}
      >
        Read-only. 외부 fetch 없음. 보유 ETF가 현재 Market Discovery 후보 / 시장 국면 /
        단기 흐름 / 구성종목 중복 / NAV 상태와 어떻게 연결되는지 확인용 evidence.
        매수·매도·교체 판단 아님.
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
        <p
          style={{
            color: "var(--danger)",
            fontSize: "0.85rem",
            margin: "0.5rem 0",
          }}
        >
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
        저장된 holdings가 없습니다. 보유 종목을 입력하고 저장한 뒤 다시 조회해 주세요.
      </p>
    );
  }

  return (
    <div style={{ fontSize: "0.85rem" }}>
      {market_context && (
        <p style={{ margin: "0 0 0.5rem 0" }}>
          현재 시장 국면: <strong>{market_context.regime_label}</strong>{" "}
          <span style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
            ({market_context.regime_code})
          </span>
        </p>
      )}

      <div className="evidence-summary-grid">
        <SummaryItem label="보유 종목" value={String(summary.total_holdings_count)} />
        <SummaryItem
          label="후보 일치"
          value={String(summary.matched_topn_count)}
          highlight={summary.matched_topn_count > 0 ? "ok" : undefined}
        />
        <SummaryItem
          label="TOP N 외"
          value={String(summary.not_in_current_topn_count)}
          highlight={summary.not_in_current_topn_count > 0 ? "warn" : undefined}
        />
        <SummaryItem label="구성종목 비교 가능" value={String(summary.constituents_available_count)} />
        <SummaryItem
          label="NAV 미연동"
          value={String(summary.nav_discount_unavailable_count)}
          highlight={summary.nav_discount_unavailable_count > 0 ? "muted" : undefined}
        />
      </div>

      {summary.nav_discount_unavailable_count > 0 && (
        <span className="nav-unavailable-note">
          NAV/괴리율 데이터 소스 미연동 — {summary.nav_discount_unavailable_count}건 표시 불가
        </span>
      )}

      <p style={{ margin: "0.5rem 0 0.25rem 0", fontSize: "0.78rem", color: "var(--muted)" }}>
        {market_asof && <>market_asof: {market_asof}</>}
        {holdings_asof && <> · holdings_asof: {holdings_asof}</>}
      </p>

      {warnings.length > 0 && (
        <ul style={{ margin: "0.25rem 0 0.5rem 1rem", color: "var(--warn)", fontSize: "0.8rem" }}>
          {warnings.map((w, i) => (
            <li key={`w-${i}`}>{w}</li>
          ))}
        </ul>
      )}

      <HoldingsList holdings={holdings} />
    </div>
  );
}

function SummaryItem({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: "ok" | "warn" | "muted";
}) {
  const valueColor =
    highlight === "ok"
      ? "var(--ok)"
      : highlight === "warn"
        ? "var(--warn)"
        : highlight === "muted"
          ? "var(--muted)"
          : "var(--fg)";
  return (
    <div className="evidence-summary-item">
      <div className="evidence-summary-label">{label}</div>
      <div className="evidence-summary-value" style={{ color: valueColor }}>
        {value}
      </div>
    </div>
  );
}

function HoldingsList({
  holdings,
}: {
  holdings: HoldingsMarketEvidenceResponse["holdings"];
}) {
  if (holdings.length === 0) return null;
  return (
    <div style={{ marginTop: "0.75rem" }}>
      {holdings.map((h, idx) => {
        const badgeClass =
          h.topn_match.status === "matched_topn_candidate"
            ? "evidence-topn-badge evidence-topn-matched"
            : h.topn_match.status === "not_in_current_topn"
              ? "evidence-topn-badge evidence-topn-outside"
              : "evidence-topn-badge evidence-topn-unknown";

        return (
          <div
            key={`${idx}|${h.ticker}|${h.account_group ?? ""}`}
            className="evidence-holding-row"
          >
            <div className="evidence-holding-header">
              <strong style={{ fontSize: "0.9rem" }}>{h.name}</strong>
              <span className="evidence-holding-ticker">{h.ticker}</span>
              <span className={badgeClass}>
                {labelOfTopnStatus(h.topn_match.status)}
                {h.topn_match.status === "matched_topn_candidate" &&
                  h.topn_match.rank && <> · rank {h.topn_match.rank}</>}
              </span>
            </div>
            <NavDiscountLine nav={h.nav_discount} />
            {h.evidence_notes.length > 0 && (
              <ul className="evidence-notes-list">
                {h.evidence_notes.map((note, i) => (
                  <li key={`${h.ticker}-n-${i}`}>{note}</li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}

function NavDiscountLine({
  nav,
}: {
  nav: HoldingsMarketEvidenceResponse["holdings"][number]["nav_discount"];
}) {
  // 2026-06-08 Naver Universe NAV Integration — 종목별 NAV / 시장가격 / 괴리율
  // 표시 (status=ok/partial 일 때만 값. unavailable 은 'NAV 확인 불가' 텍스트만).
  if (nav.status !== "ok" && nav.status !== "partial") {
    return (
      <div
        style={{
          fontSize: "0.78rem",
          color: "var(--muted)",
          margin: "0.15rem 0 0 0",
        }}
      >
        NAV / 괴리율 확인 불가 ({nav.status})
      </div>
    );
  }
  const navText = nav.nav != null ? Math.round(nav.nav).toLocaleString() : "-";
  const priceText =
    nav.market_price != null
      ? Math.round(nav.market_price).toLocaleString()
      : "-";
  const discount =
    nav.discount_rate_pct != null ? nav.discount_rate_pct.toFixed(2) : "-";
  const flagText = nav.flag ? ` · ${nav.flag}` : "";
  // 2026-06-08 NAV / Discount Display FIX (검증자 매트릭스): asof 표시 추가.
  const asofText = nav.asof ? ` · asof ${nav.asof}` : "";
  const sourceText = nav.source ? ` · source: ${nav.source}` : "";
  const statusText = nav.status ? ` · status: ${nav.status}` : "";
  return (
    <div
      style={{
        fontSize: "0.78rem",
        color: "var(--muted)",
        margin: "0.15rem 0 0 0",
      }}
    >
      NAV {navText} · 시장가 {priceText} · 괴리율{" "}
      <strong style={{ color: "var(--fg)" }}>{discount}%</strong>
      {flagText}
      {asofText}
      {sourceText}
      {statusText}
    </div>
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
