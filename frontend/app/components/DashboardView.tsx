"use client";

// POC3-01 UI-1 PC Status Dashboard — REMEDIATION (2026-07-26, base 596078f5).
//
// 역할: 첫 화면 = "오늘의 판단 상태". 1440×900 첫 viewport 에서 판단 요약·시장·
// 보유·예외·다음 행동을 30초 안에 파악.
//
// REMEDIATION 반영 (설계자 확정):
// - 시장 카드 lazy: 최초 진입/재진입에서 /market/topn/latest 자동 호출 안 함.
//   not_loaded 상태로 시작, 사용자가 "시장 상태 불러오기" 눌러야 1회 조회.
//   Dashboard 는 market_context / market_risk_reference / 기준일만 사용 (후보 건수·
//   목록 표시 안 함).
// - 조회 상태는 frontend 메모리(queryCache)에서 공유: 화면 왕복 시 재호출 X,
//   동일 진행 중 요청 dedup, 새로고침 시 재조회.
// - 결측 정직성: unavailable/부분결측/invalid 를 0/정상으로 위장하지 않음.
// - 중복 대형 카드 제거 (오늘의 데이터 상태 표 · 오늘 확인 대상 · 상세 화면 카드).
// - 예외별 직접 행동 버튼(기존 탭 이동 재사용).

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
import { useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import {
  DASH_KEY_MARKET,
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
  DASH_KEY_NAV,
} from "@/lib/api/dashboardKeys";
import type { MenuKey } from "./LeftSidebar";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

// ── 표시 규칙 (§4.2 · Dashboard 에만 적용) ──────────────────────────────────
function fmtPct(v: number | null | undefined): string {
  if (v == null) return "-";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}
function fmtIndex(v: number | null | undefined): string {
  if (v == null) return "-";
  return v.toLocaleString("ko-KR", { maximumFractionDigits: 2 });
}
// 금액: 읽기 쉬운 요약 단위 (억/만). 상세 화면의 정확 금액은 별도 유지.
function fmtAmountSummary(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)}억`;
  if (abs >= 1e4) return `${sign}${Math.round(abs / 1e4).toLocaleString("ko-KR")}만`;
  return v.toLocaleString("ko-KR");
}
// timestamp → 한국시간 가독 (의미 변경 없음).
// - 순수 날짜(YYYY-MM-DD)는 그대로 (KRX 거래일).
// - ISO datetime(2026-06-17T14:35:07+00:00 등)은 KST 로 변환해 가독 표시.
function fmtKstDate(s: string | null | undefined): string {
  if (!s) return "-";
  // 시각 성분이 없는 순수 날짜면 그대로.
  if (/^\d{4}-\d{2}-\d{2}$/.test(s)) return s;
  const d = new Date(s);
  // B-1: 파싱 불가 시 raw 문자열을 노출하지 않고 "확인 불가" 로 표시.
  if (isNaN(d.getTime())) return "확인 불가";
  // Asia/Seoul 기준 가독 형식 (YYYY-MM-DD HH:mm KST).
  const parts = new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(d);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")} ${get("hour")}:${get("minute")} KST`;
}

type BadgeKind = "ok" | "warn" | "danger" | "muted";
function badgeColor(k: BadgeKind): string {
  return k === "ok"
    ? "var(--ok)"
    : k === "warn"
      ? "var(--warn)"
      : k === "danger"
        ? "var(--danger)"
        : "var(--muted)";
}

// ── 예외 수집 (건수·원인·직접 행동) ────────────────────────────────────────
type Exception = { text: string; action: MenuKey; actionLabel: string };

function collectExceptions(
  market: QueryState<MarketTopNResponse>,
  evidence: QueryState<HoldingsMarketEvidenceResponse>,
  nav: QueryState<NavDiscountLatestResponse>,
): { list: Exception[]; anyUnavailable: boolean } {
  const list: Exception[] = [];
  let anyUnavailable = false;

  // 시장: 조회 완료(success)된 경우에만 판정. not_loaded(idle)/loading 은 예외
  // 아님 (§5 확정). A-1(2): 조회는 됐으나 data.status 가 ok 가 아니면(missing/
  // empty/invalid) 시장 카드에 "확인 불가" 가 뜨므로 예외 목록에도 반영한다
  // (요약에 "예외 없음" 과 동시 표시되지 않게).
  if (market.phase === "success") {
    if (market.data.status !== "ok") {
      list.push({
        text: `시장 데이터 확인 불가 (${market.data.status})`,
        action: "market_discovery",
        actionLabel: "Market Discovery 확인",
      });
      anyUnavailable = true;
    }
    const risk = market.data.market_risk_reference;
    const vix = risk?.vix;
    const kodex = risk?.kodex200;
    if (
      vix?.availability === "available" &&
      kodex?.availability === "available" &&
      vix.as_of_date &&
      kodex.as_of_date &&
      vix.as_of_date < kodex.as_of_date
    ) {
      list.push({
        text: `VIX stale — 기준일 ${vix.as_of_date} (시장 ${kodex.as_of_date}보다 이전)`,
        action: "diagnostics",
        actionLabel: "진단·상태 확인",
      });
    }
    if (vix?.availability === "unavailable") {
      list.push({
        text: "VIX unavailable",
        action: "diagnostics",
        actionLabel: "진단·상태 확인",
      });
      anyUnavailable = true;
    }
    for (const w of market.data.market_context?.warnings ?? []) {
      list.push({
        text: `시장 국면: ${w}`,
        action: "market_discovery",
        actionLabel: "Market Discovery 확인",
      });
    }
  }

  // Holdings Evidence (summary 건수 DIRECT).
  if (evidence.phase === "success") {
    const s = evidence.data.summary;
    if (s.evidence_unavailable_count > 0) {
      list.push({
        // 근거 확인은 "확인 근거" 화면으로 (§7·AC-13 — 평가 아닌 근거 연결).
        text: `보유 Evidence 확인 필요 ${s.evidence_unavailable_count}건`,
        action: "holdings_evidence",
        actionLabel: "해당 근거 확인",
      });
      anyUnavailable = true;
    }
    if (s.constituents_unavailable_count > 0) {
      list.push({
        text: `구성종목 비교 불가 ${s.constituents_unavailable_count}건`,
        action: "etf_exposure",
        actionLabel: "구성종목 확인",
      });
      anyUnavailable = true;
    }
    if (s.nav_discount_unavailable_count > 0) {
      list.push({
        text: `Evidence NAV 미연동 ${s.nav_discount_unavailable_count}건`,
        action: "diagnostics",
        actionLabel: "NAV 상태 확인",
      });
      anyUnavailable = true;
    }
  }

  // NAV.
  if (nav.phase === "success") {
    const s = nav.data.summary;
    const bad = (s.unavailable_count ?? 0) + (s.failed_count ?? 0);
    if (bad > 0) {
      list.push({
        text: `NAV 미연동/실패 ${bad}건`,
        action: "diagnostics",
        actionLabel: "NAV 상태 확인",
      });
      anyUnavailable = true;
    }
    if (nav.data.status === "empty") {
      list.push({
        text: "NAV 데이터 없음",
        action: "diagnostics",
        actionLabel: "NAV 상태 확인",
      });
      anyUnavailable = true;
    }
  }

  // A-1(4): 조회 실패(error)를 예외 목록에 추가한다. 기준일에 "확인 실패" 가
  // 뜨는데 예외 영역에 "확인된 예외 없음" 이 동시에 보이지 않도록.
  // market 의 idle(미조회)/loading 은 실패가 아니므로 예외로 넣지 않는다.
  if (market.phase === "error") {
    list.push({
      text: "시장 상태 조회 실패",
      action: "market_discovery",
      actionLabel: "Market Discovery 확인",
    });
    anyUnavailable = true;
  }
  if (evidence.phase === "error") {
    list.push({
      text: "보유 Evidence 조회 실패",
      action: "holdings_evidence",
      actionLabel: "확인 근거 열기",
    });
    anyUnavailable = true;
  }
  if (nav.phase === "error") {
    list.push({
      text: "NAV 조회 실패",
      action: "diagnostics",
      actionLabel: "진단·상태 확인",
    });
    anyUnavailable = true;
  }

  return { list, anyUnavailable };
}

// ── 판단 요약 한 줄 (§4.1 · 기존 상태만) ────────────────────────────────────
function JudgmentSummary({
  market,
  exceptionCount,
}: {
  market: QueryState<MarketTopNResponse>;
  exceptionCount: number;
}) {
  let regime = "시장 상태 미조회";
  if (market.phase === "success") {
    regime = market.data.market_context?.regime_label ?? "시장 국면 확인 불가";
  } else if (market.phase === "loading") {
    regime = "시장 상태 확인 중";
  }
  const exceptionText =
    exceptionCount > 0
      ? `확인할 예외 ${exceptionCount}건`
      : "확인된 예외 없음";
  return (
    <div className="dashboard-summary-line">
      <span style={{ fontWeight: 700 }}>{regime}</span>
      <span style={{ color: "var(--muted)" }}> · </span>
      <span
        style={{
          color: exceptionCount > 0 ? "var(--warn)" : "var(--muted)",
          fontWeight: exceptionCount > 0 ? 600 : 400,
        }}
      >
        {exceptionText}
      </span>
    </div>
  );
}

// ── 시장 카드 (lazy) ───────────────────────────────────────────────────────
function MarketCard({
  market,
  onNavigate,
}: {
  market: QueryState<MarketTopNResponse> & { reload: () => void };
  onNavigate: (k: MenuKey) => void;
}) {
  return (
    <div className="card dashboard-col-card">
      <h2>시장 상태</h2>
      {market.phase === "idle" && (
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          시장 상태를 불러오면 시장 국면과 VIX를 확인할 수 있습니다.
          <br />
          <span style={{ color: "var(--muted)" }}>기준일: 미조회</span>
        </p>
      )}
      {market.phase === "loading" && (
        <p style={{ color: "var(--muted)" }}>시장 상태 불러오는 중...</p>
      )}
      {market.phase === "error" && (
        <p style={{ color: "var(--danger)" }}>시장 상태 확인 실패</p>
      )}
      {market.phase === "success" && (
        <MarketCardBody data={market.data} stale={market.stale} />
      )}

      <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className="dashboard-flow-btn"
          onClick={market.reload}
        >
          {market.phase === "idle"
            ? "시장 상태 불러오기"
            : "시장 상태 다시 불러오기"}
        </button>
        <button
          type="button"
          className="dashboard-flow-btn"
          onClick={() => onNavigate("market_discovery")}
        >
          Market Discovery 열기 →
        </button>
      </div>
    </div>
  );
}

function MarketCardBody({
  data,
  stale,
}: {
  data: MarketTopNResponse;
  stale: boolean;
}) {
  const ctx = data.market_context;
  const risk = data.market_risk_reference;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13 }}>
      {stale && (
        <div style={{ color: "var(--warn)", fontSize: 12 }}>
          ⚠ 이전 조회값 (재조회 실패 — 최신 아님)
        </div>
      )}
      {/* 시장 국면 */}
      <div>
        <span style={{ color: "var(--muted)" }}>시장 국면: </span>
        <span style={{ fontWeight: 600 }}>
          {ctx?.regime_label ?? "확인 불가"}
        </span>
        {ctx?.asof && (
          <span style={{ color: "var(--muted)" }}> (기준일 {fmtKstDate(ctx.asof)})</span>
        )}
      </div>
      {/* KODEX200 */}
      {risk?.kodex200?.availability === "available" ? (
        <div>
          <span style={{ color: "var(--muted)" }}>KODEX200: </span>
          <span>{fmtIndex(risk.kodex200.close)}</span>
          {risk.kodex200.change_1d_pct != null && (
            <span
              style={{
                color:
                  risk.kodex200.change_1d_pct >= 0 ? "var(--ok)" : "var(--danger)",
              }}
            >
              {" "}
              {fmtPct(risk.kodex200.change_1d_pct)}
            </span>
          )}
          <span style={{ color: "var(--muted)" }}>
            {" "}
            (기준일 {fmtKstDate(risk.kodex200.as_of_date)})
          </span>
        </div>
      ) : (
        <div style={{ color: "var(--muted)" }}>KODEX200: 확인 불가</div>
      )}
      {/* VIX — 별도 기준일 + stale 분리 (§4.2) */}
      {risk?.vix?.availability === "available" ? (
        <VixLine
          vixClose={risk.vix.close ?? null}
          vixAsof={risk.vix.as_of_date ?? null}
          marketAsof={risk.kodex200?.as_of_date ?? null}
        />
      ) : (
        <div style={{ color: "var(--muted)" }}>VIX: 확인 불가</div>
      )}
    </div>
  );
}

function VixLine({
  vixClose,
  vixAsof,
  marketAsof,
}: {
  vixClose: number | null;
  vixAsof: string | null;
  marketAsof: string | null;
}) {
  const isStale = !!(vixAsof && marketAsof && vixAsof < marketAsof);
  return (
    <div>
      <span style={{ color: "var(--muted)" }}>VIX: </span>
      <span>{vixClose != null ? vixClose.toFixed(2) : "-"}</span>
      <span style={{ color: "var(--muted)" }}> (기준일 {fmtKstDate(vixAsof)})</span>
      {isStale && (
        <span style={{ color: "var(--warn)", fontWeight: 600, fontSize: 12 }}>
          {" "}
          ⚠ stale — 현재 시장값 아님
        </span>
      )}
    </div>
  );
}

// ── 보유 카드 (Holdings items COMPOSE 합산 · 결측 정직성) ───────────────────
function HoldingsCard({
  holdings,
  evidence,
  onNavigate,
}: {
  holdings: QueryState<EnrichedHoldingsResult>;
  evidence: QueryState<HoldingsMarketEvidenceResponse>;
  onNavigate: (k: MenuKey) => void;
}) {
  return (
    <div className="card dashboard-col-card">
      <h2>보유 현황</h2>
      {holdings.phase === "loading" && (
        <p style={{ color: "var(--muted)" }}>보유 데이터 확인 중...</p>
      )}
      {holdings.phase === "error" && (
        <p style={{ color: "var(--danger)" }}>보유 데이터 확인 실패</p>
      )}
      {holdings.phase === "success" && (
        <HoldingsCardBody items={holdings.data.items} stale={holdings.stale} />
      )}
      {evidence.phase === "success" && (
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
      {/* §7·AC-13: 평가 연결 → 보유 현황, 확인 대상 연결 → 확인 근거. */}
      <div className="btn-row" style={{ marginTop: 8 }}>
        <button
          type="button"
          className="dashboard-flow-btn"
          onClick={() => onNavigate("holdings")}
        >
          보유 현황 열기 →
        </button>
        <button
          type="button"
          className="dashboard-flow-btn"
          onClick={() => onNavigate("holdings_evidence")}
        >
          확인 근거 →
        </button>
      </div>
    </div>
  );
}

function HoldingsCardBody({
  items,
  stale,
}: {
  items: EnrichedHoldingsResult["items"];
  stale: boolean;
}) {
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
      {stale && (
        <div style={{ color: "var(--warn)", fontSize: 12 }}>
          ⚠ 이전 조회값 (재조회 실패 — 최신 아님)
        </div>
      )}
      <div>
        <span style={{ color: "var(--muted)" }}>보유 종목 수: </span>
        <span style={{ fontWeight: 600 }}>{count}</span>
      </div>
      <div>
        <span style={{ color: "var(--muted)" }}>총 평가액: </span>
        {evalOk === 0 ? (
          <span style={{ color: "var(--warn)", fontWeight: 600 }}>확인 불가</span>
        ) : (
          <>
            <span style={{ fontWeight: 600 }}>{fmtAmountSummary(evalSum)}</span>
            {evalMissing > 0 && (
              <span style={{ color: "var(--warn)", fontSize: 12 }}>
                {" "}
                ({evalOk}/{count}건 기준 · 불가 {evalMissing}건 제외)
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
              {fmtAmountSummary(pnlSum)}
            </span>
            {pnlMissing > 0 && (
              <span style={{ color: "var(--warn)", fontSize: 12 }}>
                {" "}
                ({pnlOk}/{count}건 기준 · 불가 {pnlMissing}건 제외)
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ── 예외 목록 (원인·건수·직접 행동) ────────────────────────────────────────
function ExceptionList({
  exceptions,
  anyUnavailable,
  loading,
  onNavigate,
}: {
  exceptions: Exception[];
  anyUnavailable: boolean;
  loading: boolean;
  onNavigate: (k: MenuKey) => void;
}) {
  return (
    <div className="card">
      <h2>확인할 예외</h2>
      {exceptions.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>
          {loading ? "확인 중..." : "확인된 예외 없음"}
        </p>
      ) : (
        <ul className="dashboard-exception-list">
          {exceptions.map((ex, i) => (
            <li key={i}>
              <span style={{ color: "var(--warn)" }}>{ex.text}</span>
              <button
                type="button"
                className="dashboard-exception-btn"
                onClick={() => onNavigate(ex.action)}
              >
                {ex.actionLabel} →
              </button>
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

// ── 기준일 + 다시 불러오기 (§4.1) ──────────────────────────────────────────
function AsOfPanel({
  market,
  evidence,
  nav,
  onReloadAll,
}: {
  market: QueryState<MarketTopNResponse>;
  evidence: QueryState<HoldingsMarketEvidenceResponse>;
  nav: QueryState<NavDiscountLatestResponse>;
  onReloadAll: () => void;
}) {
  const rows: { area: string; asof: string; kind: BadgeKind }[] = [];
  rows.push({
    area: "시장",
    asof:
      market.phase === "success"
        ? fmtKstDate(market.data.asof)
        : market.phase === "idle"
          ? "미조회"
          : market.phase === "loading"
            ? "확인 중"
            : "확인 실패",
    kind: market.phase === "success" ? "muted" : "muted",
  });
  rows.push({
    area: "보유 Evidence",
    asof:
      evidence.phase === "success"
        ? fmtKstDate(evidence.data.holdings_asof)
        : evidence.phase === "loading"
          ? "확인 중"
          : "확인 실패",
    kind: "muted",
  });
  rows.push({
    area: "NAV",
    asof:
      nav.phase === "success"
        ? fmtKstDate(nav.data.asof)
        : nav.phase === "loading"
          ? "확인 중"
          : "확인 실패",
    kind: "muted",
  });

  return (
    <div className="card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>항목별 기준일</h2>
        <button type="button" className="dashboard-flow-btn" onClick={onReloadAll}>
          다시 불러오기
        </button>
      </div>
      <table className="dashboard-status-table" style={{ marginTop: 8 }}>
        <tbody>
          {rows.map((r) => (
            <tr key={r.area}>
              <td>{r.area}</td>
              <td style={{ color: badgeColor(r.kind) }}>기준일 {r.asof}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ color: "var(--muted)", fontSize: 12, marginTop: 4 }}>
        서로 다른 기준일은 합치지 않습니다.
      </p>
    </div>
  );
}

// ── 사용 흐름 도움말 (STEP 1~5 접힘) ───────────────────────────────────────
const HELP_STEPS: { title: string; desc: string }[] = [
  { title: "시장 데이터 갱신", desc: "Market Discovery 화면에서 '최신 시장 데이터 갱신'을 실행합니다." },
  { title: "시장 후보 확인 + ETF 구성종목 분석", desc: "Market Discovery TOP N 후보 확인, ETF Exposure 구성종목 중복률 점검." },
  { title: "보유 종목 입력 · 확인 근거", desc: "'종목 관리'에서 보유 ETF 입력·저장, '보유 현황'·'확인 근거'에서 평가와 수치 근거 확인." },
  { title: "판단 초안 생성", desc: "'OCI 적용·알림 > 미리보기·수동 전달 점검'에서 '저장된 보유 종목으로 초안 만들기'를 실행합니다." },
  { title: "승인 / Telegram 발송", desc: "Approval / Telegram 화면에서 초안을 검토·승인합니다." },
];

function HelpFlow() {
  return (
    <details className="card">
      <summary style={{ cursor: "pointer", fontWeight: 600 }}>
        사용 흐름 도움말 (STEP 1~5)
      </summary>
      <ol style={{ marginTop: 8, paddingLeft: 20, fontSize: 13 }}>
        {HELP_STEPS.map((s, i) => (
          <li key={i} style={{ marginBottom: 4 }}>
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
  // 시장은 lazy (최초 topn 자동 호출 안 함). 나머지는 마운트 시 캐시 통해 조회.
  const market = useSharedQuery<MarketTopNResponse>(
    DASH_KEY_MARKET,
    () => fetchMarketTopnLatest(),
    { lazy: true },
  );
  const holdings = useSharedQuery<EnrichedHoldingsResult>(
    DASH_KEY_HOLDINGS,
    () => fetchEnrichedHoldings(),
  );
  const evidence = useSharedQuery<HoldingsMarketEvidenceResponse>(
    DASH_KEY_EVIDENCE,
    () => fetchHoldingsMarketEvidence(),
  );
  const nav = useSharedQuery<NavDiscountLatestResponse>(
    DASH_KEY_NAV,
    () => fetchNavDiscountLatest(),
  );

  const { list: exceptions, anyUnavailable } = collectExceptions(
    market,
    evidence,
    nav,
  );

  const anyLoading =
    market.phase === "loading" ||
    holdings.phase === "loading" ||
    evidence.phase === "loading" ||
    nav.phase === "loading";

  // "다시 불러오기": Dashboard 관련 읽기만 재조회 (시장은 이미 조회된 경우에만).
  const reloadAll = () => {
    holdings.reload();
    evidence.reload();
    nav.reload();
    if (market.phase !== "idle") market.reload();
  };

  return (
    <section aria-labelledby="dashboard-h" className="dashboard-root">
      <h1 id="dashboard-h">오늘의 판단 상태</h1>

      {/* 판단 요약 한 줄 */}
      <JudgmentSummary market={market} exceptionCount={exceptions.length} />

      {/* 시장 | 보유 2열 */}
      <div className="dashboard-two-col">
        <MarketCard market={market} onNavigate={onNavigate} />
        <HoldingsCard
          holdings={holdings}
          evidence={evidence}
          onNavigate={onNavigate}
        />
      </div>

      {/* 예외 (행동 버튼) */}
      <ExceptionList
        exceptions={exceptions}
        anyUnavailable={anyUnavailable}
        loading={anyLoading}
        onNavigate={onNavigate}
      />

      {/* 항목별 기준일 + 다시 불러오기 */}
      <AsOfPanel
        market={market}
        evidence={evidence}
        nav={nav}
        onReloadAll={reloadAll}
      />

      {/* STEP 1~5 도움말 (접힘) */}
      <HelpFlow />
    </section>
  );
}
