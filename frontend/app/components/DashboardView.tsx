"use client";

// POC3-01 UI-1 PC Status Dashboard 초안 (2026-07-26).
//
// 역할: 첫 화면을 "STEP 1~5 절차 안내" → "오늘의 판단 상태" Dashboard 로 전환.
// - 기존 데이터 경로가 확인된 시장 상태·보유 요약·최신성·예외만 사용.
// - 신규 API/집계/source 없음. 기존 응답 필드를 DIRECT 표시하거나 items 를
//   의미 변경 없이 COMPOSE(단순 합산)만 한다.
// - 서로 다른 기준일을 하나의 최신 시점으로 합치지 않는다.
// - unavailable 을 0/정상으로 치환하지 않는다. VIX 는 별도 기준일·stale 표시.
// - 후보 순위표·보유 위험 표·고밀도 표·차트는 만들지 않는다 (POC3-02/03 범위).
// - 초안 생성·승인·OCI·PUSH 버튼은 여기 모으지 않는다 (POC3-04 범위).
// - STEP 1~5 안내는 삭제하지 않고 "사용 흐름 도움말" 로 접어 기본 비노출.

import { useEffect, useState } from "react";
import {
  fetchMarketTopnLatest,
  type MarketTopNResponse,
  fetchEnrichedHoldings,
  type EnrichedHoldingsResult,
  fetchHoldingsMarketEvidence,
  type HoldingsMarketEvidenceResponse,
  fetchNavDiscountLatest,
  type NavDiscountLatestResponse,
} from "@/lib/api";
import type { MenuKey } from "./LeftSidebar";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

// 영역별 로딩/실패 격리 (§6.8: 일부 영역 실패해도 정상 영역 유지).
type Area<T> =
  | { phase: "loading" }
  | { phase: "error" }
  | { phase: "ready"; data: T };

function useArea<T>(fetcher: () => Promise<T>): Area<T> {
  const [state, setState] = useState<Area<T>>({ phase: "loading" });
  useEffect(() => {
    let cancelled = false;
    fetcher()
      .then((data) => {
        if (!cancelled) setState({ phase: "ready", data });
      })
      .catch(() => {
        if (!cancelled) setState({ phase: "error" });
      });
    return () => {
      cancelled = true;
    };
    // fetcher 는 모듈 함수 참조라 안정적. 최초 1회만 실행.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return state;
}

// 상태 배지 (§6.8: 사용 가능/stale/unavailable/warning 을 색으로 구분).
type Badge = "ok" | "stale" | "unavailable" | "warning" | "loading";

function StatusBadge({ kind, label }: { kind: Badge; label: string }) {
  const color =
    kind === "ok"
      ? "var(--ok)"
      : kind === "warning" || kind === "stale"
        ? "var(--warn)"
        : kind === "unavailable"
          ? "var(--danger)"
          : "var(--muted)";
  return (
    <span style={{ color, fontWeight: 600, fontSize: 12 }}>{label}</span>
  );
}

// ── 오늘의 데이터 상태 ──────────────────────────────────────────────────────
// 시장 / Holdings / NAV·구성종목 영역별 기준일 + 상태. 화면 조회 시각을
// 데이터 기준일처럼 표현하지 않는다 (§6.2).
function DataStatusSection({
  market,
  evidence,
  nav,
}: {
  market: Area<MarketTopNResponse>;
  evidence: Area<HoldingsMarketEvidenceResponse>;
  nav: Area<NavDiscountLatestResponse>;
}) {
  const rows: { area: string; asof: string; badge: Badge; note: string }[] = [];

  // 시장 (Market Discovery latest).
  if (market.phase === "loading") {
    rows.push({ area: "시장 데이터", asof: "확인 중", badge: "loading", note: "" });
  } else if (market.phase === "error") {
    rows.push({ area: "시장 데이터", asof: "-", badge: "unavailable", note: "확인 실패" });
  } else {
    const d = market.data;
    if (d.status === "ok") {
      rows.push({
        area: "시장 데이터",
        asof: d.asof ?? "-",
        badge: "ok",
        note: `Universe ${d.universe_count ?? "-"}개`,
      });
    } else {
      rows.push({
        area: "시장 데이터",
        asof: d.asof ?? "-",
        badge: "unavailable",
        note: d.status === "missing" ? "갱신 필요" : "데이터 오류",
      });
    }
  }

  // Holdings Evidence (기준일 분리: holdings_asof / market_asof).
  if (evidence.phase === "loading") {
    rows.push({ area: "보유 Evidence", asof: "확인 중", badge: "loading", note: "" });
  } else if (evidence.phase === "error") {
    rows.push({
      area: "보유 Evidence",
      asof: "-",
      badge: "unavailable",
      note: "확인 실패",
    });
  } else {
    const e = evidence.data;
    rows.push({
      area: "보유 Evidence",
      asof: e.holdings_asof ?? "-",
      badge: "ok",
      note: `시장 기준일 ${e.market_asof ?? "-"}`,
    });
  }

  // NAV / 구성종목.
  if (nav.phase === "loading") {
    rows.push({ area: "NAV·괴리율", asof: "확인 중", badge: "loading", note: "" });
  } else if (nav.phase === "error") {
    rows.push({ area: "NAV·괴리율", asof: "-", badge: "unavailable", note: "확인 실패" });
  } else {
    const n = nav.data;
    if (n.status === "ok") {
      const s = n.summary;
      const hasUnavail = (s.unavailable_count ?? 0) + (s.failed_count ?? 0) > 0;
      rows.push({
        area: "NAV·괴리율",
        asof: n.asof ?? "-",
        badge: hasUnavail ? "warning" : "ok",
        note: hasUnavail
          ? `미연동/실패 ${(s.unavailable_count ?? 0) + (s.failed_count ?? 0)}건`
          : `${s.ok_count ?? 0}건`,
      });
    } else {
      rows.push({
        area: "NAV·괴리율",
        asof: n.asof ?? "-",
        badge: "unavailable",
        note: "데이터 없음",
      });
    }
  }

  return (
    <div className="card">
      <h2>오늘의 데이터 상태</h2>
      <table className="dashboard-status-table">
        <tbody>
          {rows.map((r) => (
            <tr key={r.area}>
              <td>{r.area}</td>
              <td style={{ color: "var(--muted)" }}>기준일 {r.asof}</td>
              <td>
                <StatusBadge
                  kind={r.badge}
                  label={
                    r.badge === "ok"
                      ? "사용 가능"
                      : r.badge === "warning"
                        ? "warning"
                        : r.badge === "unavailable"
                          ? "unavailable"
                          : r.badge === "loading"
                            ? "확인 중"
                            : "stale"
                  }
                />
              </td>
              <td style={{ color: "var(--muted)", fontSize: 12 }}>{r.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── 시장 상태 (시장 국면 + KODEX200 + VIX 별도 기준일·stale) ───────────────
function MarketStatusSection({
  market,
  onNavigate,
}: {
  market: Area<MarketTopNResponse>;
  onNavigate: (k: MenuKey) => void;
}) {
  return (
    <div className="card">
      <h2>시장 상태</h2>
      {market.phase === "loading" && (
        <p style={{ color: "var(--muted)" }}>시장 데이터 확인 중...</p>
      )}
      {market.phase === "error" && (
        <p style={{ color: "var(--danger)" }}>시장 데이터 확인 실패</p>
      )}
      {market.phase === "ready" && <MarketStatusBody data={market.data} />}
      <button
        type="button"
        className="dashboard-flow-btn"
        onClick={() => onNavigate("market_discovery")}
        style={{ marginTop: 8 }}
      >
        Market Discovery 열기 →
      </button>
    </div>
  );
}

function MarketStatusBody({ data }: { data: MarketTopNResponse }) {
  const ctx = data.market_context;
  const risk = data.market_risk_reference;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {/* 시장 국면 (DIRECT). */}
      {ctx ? (
        <div>
          <span style={{ color: "var(--muted)" }}>시장 국면: </span>
          <span style={{ fontWeight: 600 }}>{ctx.regime_label}</span>
          {ctx.asof && (
            <span style={{ color: "var(--muted)", fontSize: 12 }}>
              {" "}
              (기준일 {ctx.asof})
            </span>
          )}
        </div>
      ) : (
        <div style={{ color: "var(--muted)" }}>시장 국면: unavailable</div>
      )}

      {/* KODEX200 (DIRECT). */}
      {risk?.kodex200?.availability === "available" ? (
        <div>
          <span style={{ color: "var(--muted)" }}>KODEX200: </span>
          <span>
            {risk.kodex200.close ?? "-"}
            {risk.kodex200.change_1d_pct != null && (
              <span
                style={{
                  color:
                    risk.kodex200.change_1d_pct >= 0
                      ? "var(--ok)"
                      : "var(--danger)",
                }}
              >
                {" "}
                {risk.kodex200.change_1d_pct >= 0 ? "+" : ""}
                {risk.kodex200.change_1d_pct.toFixed(2)}%
              </span>
            )}
          </span>
          <span style={{ color: "var(--muted)", fontSize: 12 }}>
            {" "}
            (기준일 {risk.kodex200.as_of_date ?? "-"})
          </span>
        </div>
      ) : (
        <div style={{ color: "var(--muted)" }}>KODEX200: unavailable</div>
      )}

      {/* VIX — 별도 기준일 + stale 판정 (§6.3). KODEX200 과 기준일이 다르면
          stale 경고. 날짜 하드코딩 없이 실제 응답 기준으로 비교. */}
      {risk?.vix?.availability === "available" ? (
        <VixLine
          vixAsof={risk.vix.as_of_date ?? null}
          vixClose={risk.vix.close ?? null}
          marketAsof={risk.kodex200?.as_of_date ?? null}
        />
      ) : (
        <div style={{ color: "var(--muted)" }}>VIX: unavailable</div>
      )}
    </div>
  );
}

function VixLine({
  vixAsof,
  vixClose,
  marketAsof,
}: {
  vixAsof: string | null;
  vixClose: number | null;
  marketAsof: string | null;
}) {
  // 실제 응답 기준으로 stale 판정 (하드코딩 금지). VIX 기준일이 시장 기준일보다
  // 이전이면 stale 경고 톤. 현재 시장값과 합치지 않는다.
  const isStale = !!(vixAsof && marketAsof && vixAsof < marketAsof);
  return (
    <div>
      <span style={{ color: "var(--muted)" }}>VIX: </span>
      <span>{vixClose ?? "-"}</span>
      <span style={{ color: "var(--muted)", fontSize: 12 }}>
        {" "}
        (기준일 {vixAsof ?? "-"})
      </span>
      {isStale && (
        <span
          style={{ color: "var(--warn)", fontWeight: 600, fontSize: 12 }}
        >
          {" "}
          ⚠ stale — 시장 기준일({marketAsof})보다 이전. 현재 시장값으로 보지 말 것.
        </span>
      )}
    </div>
  );
}

// ── 보유 현황 (Holdings 응답 items 를 단순 COMPOSE 합산) ────────────────────
function HoldingsSummarySection({
  holdings,
  evidence,
  onNavigate,
}: {
  holdings: Area<EnrichedHoldingsResult>;
  evidence: Area<HoldingsMarketEvidenceResponse>;
  onNavigate: (k: MenuKey) => void;
}) {
  return (
    <div className="card">
      <h2>보유 현황</h2>
      {holdings.phase === "loading" && (
        <p style={{ color: "var(--muted)" }}>보유 데이터 확인 중...</p>
      )}
      {holdings.phase === "error" && (
        <p style={{ color: "var(--danger)" }}>보유 데이터 확인 실패</p>
      )}
      {holdings.phase === "ready" && (
        <HoldingsSummaryBody items={holdings.data.items} />
      )}
      {/* 확인 필요 evidence 건수 (DIRECT summary). */}
      {evidence.phase === "ready" && (
        <div style={{ marginTop: 4, fontSize: 13 }}>
          <span style={{ color: "var(--muted)" }}>확인 필요 Evidence: </span>
          <span
            style={{
              color:
                evidence.data.summary.evidence_unavailable_count > 0
                  ? "var(--warn)"
                  : "var(--muted)",
              fontWeight: 600,
            }}
          >
            {evidence.data.summary.evidence_unavailable_count}건
          </span>
        </div>
      )}
      <button
        type="button"
        className="dashboard-flow-btn"
        onClick={() => onNavigate("holdings")}
        style={{ marginTop: 8 }}
      >
        Holdings 열기 →
      </button>
    </div>
  );
}

function HoldingsSummaryBody({
  items,
}: {
  items: EnrichedHoldingsResult["items"];
}) {
  // COMPOSE: 기존 items 의 eval_amount / pnl_amount 를 단순 합산 (의미 변경 없음).
  // 결측(null)은 0 으로 치환하지 않는다: 유효값이 하나도 없으면 "확인 불가",
  // 일부만 있으면 불완전 합계를 전체처럼 표시하지 않고 "N/M건 기준" 을 명시한다.
  const count = items.length;
  let evalSum = 0;
  let evalOk = 0;
  let pnlSum = 0;
  let pnlOk = 0;
  for (const it of items) {
    if (it.eval_amount != null) {
      evalSum += it.eval_amount;
      evalOk += 1;
    }
    if (it.pnl_amount != null) {
      pnlSum += it.pnl_amount;
      pnlOk += 1;
    }
  }
  const evalMissing = count - evalOk;
  const pnlMissing = count - pnlOk;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 13 }}>
      <div>
        <span style={{ color: "var(--muted)" }}>보유 종목 수: </span>
        <span style={{ fontWeight: 600 }}>{count}</span>
      </div>
      <div>
        <span style={{ color: "var(--muted)" }}>총 평가액: </span>
        {evalOk === 0 ? (
          // 유효 평가액이 하나도 없음 → 0 으로 표시하지 않는다.
          <span style={{ color: "var(--warn)", fontWeight: 600 }}>확인 불가</span>
        ) : (
          <>
            <span style={{ fontWeight: 600 }}>{evalSum.toLocaleString()}</span>
            {evalMissing > 0 && (
              <span style={{ color: "var(--warn)", fontSize: 12 }}>
                {" "}
                ({evalOk}/{count}건 기준 · 평가 불가 {evalMissing}건 제외)
              </span>
            )}
          </>
        )}
      </div>
      <div>
        <span style={{ color: "var(--muted)" }}>평가손익: </span>
        {pnlOk === 0 ? (
          <span style={{ color: "var(--warn)", fontWeight: 600 }}>확인 불가</span>
        ) : (
          <>
            <span
              style={{
                fontWeight: 600,
                color: pnlSum >= 0 ? "var(--ok)" : "var(--danger)",
              }}
            >
              {pnlSum >= 0 ? "+" : ""}
              {pnlSum.toLocaleString()}
            </span>
            {pnlMissing > 0 && (
              <span style={{ color: "var(--warn)", fontSize: 12 }}>
                {" "}
                ({pnlOk}/{count}건 기준 · 손익 불가 {pnlMissing}건 제외)
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── 확인할 예외 (정상보다 우선 · 건수/사유 요약) ────────────────────────────
function ExceptionsSection({
  market,
  evidence,
  nav,
}: {
  market: Area<MarketTopNResponse>;
  evidence: Area<HoldingsMarketEvidenceResponse>;
  nav: Area<NavDiscountLatestResponse>;
}) {
  const exceptions: string[] = [];
  let anyUnavailable = false;

  // 시장 국면 warnings + VIX stale.
  if (market.phase === "ready") {
    const d = market.data;
    if (d.market_context?.warnings?.length) {
      for (const w of d.market_context.warnings) exceptions.push(`시장 국면: ${w}`);
    }
    const vix = d.market_risk_reference?.vix;
    const kodex = d.market_risk_reference?.kodex200;
    if (
      vix?.availability === "available" &&
      kodex?.availability === "available" &&
      vix.as_of_date &&
      kodex.as_of_date &&
      vix.as_of_date < kodex.as_of_date
    ) {
      exceptions.push(
        `VIX stale — 기준일 ${vix.as_of_date} (시장 ${kodex.as_of_date}보다 이전)`,
      );
    }
    if (d.market_risk_reference?.vix?.availability === "unavailable") {
      exceptions.push("VIX unavailable");
      anyUnavailable = true;
    }
  } else if (market.phase === "error") {
    exceptions.push("시장 데이터 확인 실패");
  }

  // Holdings Evidence 예외 (DIRECT summary 건수).
  if (evidence.phase === "ready") {
    const s = evidence.data.summary;
    if (s.evidence_unavailable_count > 0) {
      exceptions.push(`보유 Evidence 확인 필요 ${s.evidence_unavailable_count}건`);
      anyUnavailable = true;
    }
    if (s.constituents_unavailable_count > 0) {
      exceptions.push(
        `구성종목 비교 불가 ${s.constituents_unavailable_count}건`,
      );
      anyUnavailable = true;
    }
    if (s.nav_discount_unavailable_count > 0) {
      exceptions.push(
        `Evidence NAV 미연동 ${s.nav_discount_unavailable_count}건`,
      );
      anyUnavailable = true;
    }
    if (evidence.data.warnings?.length) {
      for (const w of evidence.data.warnings) exceptions.push(`Evidence: ${w}`);
    }
  } else if (evidence.phase === "error") {
    exceptions.push("보유 Evidence 확인 실패");
  }

  // NAV 예외.
  if (nav.phase === "ready") {
    const s = nav.data.summary;
    const bad = (s.unavailable_count ?? 0) + (s.failed_count ?? 0);
    if (bad > 0) {
      exceptions.push(`NAV 미연동/실패 ${bad}건`);
      anyUnavailable = true;
    }
    if (nav.data.status === "empty") {
      exceptions.push("NAV 데이터 없음");
      anyUnavailable = true;
    }
  } else if (nav.phase === "error") {
    exceptions.push("NAV 확인 실패");
  }

  const stillLoading =
    market.phase === "loading" ||
    evidence.phase === "loading" ||
    nav.phase === "loading";

  return (
    <div className="card">
      <h2>확인할 예외</h2>
      {stillLoading && exceptions.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>확인 중...</p>
      ) : exceptions.length === 0 ? (
        // unavailable 이 하나도 없을 때만 "예외 없음". 로딩 중에는 단정하지 않음.
        <p style={{ color: "var(--muted)" }}>
          {stillLoading ? "확인 중..." : "확인된 예외 없음"}
        </p>
      ) : (
        <ul className="dashboard-exception-list">
          {exceptions.map((ex, i) => (
            <li key={i} style={{ color: "var(--warn)" }}>
              {ex}
            </li>
          ))}
        </ul>
      )}
      {anyUnavailable && (
        <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 4 }}>
          unavailable 항목은 0/정상으로 해석하지 않습니다.
        </p>
      )}
    </div>
  );
}

// ── 오늘 확인 대상 (기존 응답에서 바로 확인되는 건수만) ─────────────────────
function TodayReviewSection({
  market,
  evidence,
}: {
  market: Area<MarketTopNResponse>;
  evidence: Area<HoldingsMarketEvidenceResponse>;
}) {
  return (
    <div className="card">
      <h2>오늘 확인 대상</h2>
      <ul className="dashboard-status-list" style={{ fontSize: 13 }}>
        <li>
          <span style={{ color: "var(--muted)" }}>Market Discovery 후보: </span>
          {market.phase === "loading" ? (
            "확인 중..."
          ) : market.phase === "error" ? (
            <span style={{ color: "var(--danger)" }}>확인 실패</span>
          ) : market.data.status === "ok" ? (
            // status=ok 일 때만 실제 후보 건수 (candidates 는 non-null 배열 계약).
            `${market.data.candidates.length}건`
          ) : (
            // missing/empty/invalid 는 "데이터 없음" 이지 후보 0건이 아니다.
            <span style={{ color: "var(--warn)" }}>
              확인 불가 ({market.data.status})
            </span>
          )}
        </li>
        {evidence.phase === "ready" && (
          <>
            <li>
              <span style={{ color: "var(--muted)" }}>후보와 일치: </span>
              {evidence.data.summary.matched_topn_count}건
            </li>
            <li>
              <span style={{ color: "var(--muted)" }}>비교 가능(TOP N 외): </span>
              {evidence.data.summary.not_in_current_topn_count}건
            </li>
            <li>
              <span style={{ color: "var(--muted)" }}>확인 불가: </span>
              {evidence.data.summary.evidence_unavailable_count}건
            </li>
          </>
        )}
      </ul>
    </div>
  );
}

// ── 사용 흐름 도움말 (기존 STEP 1~5 를 접어 보존) ──────────────────────────
const HELP_STEPS: { num: number; title: string; desc: string }[] = [
  {
    num: 1,
    title: "시장 데이터 갱신",
    desc: "Market Discovery 화면에서 '최신 시장 데이터 갱신'을 실행합니다.",
  },
  {
    num: 2,
    title: "시장 후보 확인 + ETF 구성종목 분석",
    desc: "Market Discovery TOP N 후보 확인, ETF Exposure 구성종목 중복률 점검.",
  },
  {
    num: 3,
    title: "내 보유 ETF와 비교",
    desc: "Holdings 화면에서 보유 ETF 입력·저장, Evidence 조회로 후보와 연결 확인.",
  },
  {
    num: 4,
    title: "판단 초안 생성",
    desc: "Holdings 화면의 '저장된 보유 종목으로 초안 만들기'를 실행합니다.",
  },
  {
    num: 5,
    title: "승인 / Telegram 발송",
    desc: "Approval / Telegram 화면에서 초안을 검토·승인합니다.",
  },
];

function HelpFlow() {
  return (
    <details className="card">
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>
        사용 흐름 도움말 (STEP 1~5)
      </summary>
      <ol style={{ marginTop: 8, paddingLeft: 20, fontSize: 13 }}>
        {HELP_STEPS.map((s) => (
          <li key={s.num} style={{ marginBottom: 4 }}>
            <strong>{s.title}</strong>
            <span style={{ color: "var(--muted)" }}> — {s.desc}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

// ── Dashboard 본체 ─────────────────────────────────────────────────────────
export default function DashboardView({ onNavigate }: Props) {
  const market = useArea<MarketTopNResponse>(() => fetchMarketTopnLatest());
  const holdings = useArea<EnrichedHoldingsResult>(() => fetchEnrichedHoldings());
  const evidence = useArea<HoldingsMarketEvidenceResponse>(() =>
    fetchHoldingsMarketEvidence(),
  );
  const nav = useArea<NavDiscountLatestResponse>(() => fetchNavDiscountLatest());

  return (
    <section aria-labelledby="dashboard-h">
      <h1 id="dashboard-h">오늘의 판단 상태</h1>
      <p className="subtitle">
        오늘 시장·보유·데이터에 볼 것이 있는지 먼저 확인합니다. 자동 매매 없음,
        인간 최종 승인 게이트 유지. 서로 다른 기준일은 합치지 않습니다.
      </p>

      {/* 1. 오늘의 데이터 상태 */}
      <DataStatusSection market={market} evidence={evidence} nav={nav} />

      {/* 2. 시장 상태 */}
      <MarketStatusSection market={market} onNavigate={onNavigate} />

      {/* 3. 보유 현황 */}
      <HoldingsSummarySection
        holdings={holdings}
        evidence={evidence}
        onNavigate={onNavigate}
      />

      {/* 4. 확인할 예외 */}
      <ExceptionsSection market={market} evidence={evidence} nav={nav} />

      {/* 5. 오늘 확인 대상 */}
      <TodayReviewSection market={market} evidence={evidence} />

      {/* 6. 상세 화면 이동 버튼 (화면 이동만) */}
      <div className="card">
        <h2>상세 화면</h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button
            type="button"
            className="dashboard-flow-btn"
            onClick={() => onNavigate("market_discovery")}
          >
            Market Discovery 열기 →
          </button>
          <button
            type="button"
            className="dashboard-flow-btn"
            onClick={() => onNavigate("holdings")}
          >
            Holdings 열기 →
          </button>
          <button
            type="button"
            className="dashboard-flow-btn"
            onClick={() => onNavigate("data_status")}
          >
            Data Status 열기 →
          </button>
        </div>
      </div>

      {/* 사용 흐름 도움말 (STEP 1~5 접힘) */}
      <HelpFlow />
    </section>
  );
}
