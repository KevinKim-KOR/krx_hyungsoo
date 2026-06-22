"use client";

// POC2 ETF Exposure Data Unfolding 1차 (2026-06-06) — Holdings Evidence State Bridge 카드.
//
// 책임 (지시문 §5.5 / §5.6 / AC-5 / AC-6):
// - ETF Exposure 화면 컨테이너가 전달한 evidence 데이터 (props) 만 렌더.
// - 본 컴포넌트는 직접 Holdings API 호출 X — 호출은 컨테이너 책임.
// - 상태 3종: not_loaded / ok / unavailable.
// - 사용자 명시 클릭으로만 데이터 로딩 (페이지 진입 시 자동 호출 X).
//
// 화면 표현:
// - not_loaded: "보유 겹침 정보: 불러오지 않음" + 명시 호출 버튼
// - ok: 보유 ETF별 후보군 반복 핵심 종목 겹침 표시
// - unavailable: 보유 데이터 없음 / API 실패 등

import type {
  HoldingsMarketEvidenceItem,
  HoldingsMarketEvidenceResponse,
} from "@/lib/api";

export type BridgeState = "not_loaded" | "loading" | "ok" | "unavailable";

interface Props {
  state: BridgeState;
  data: HoldingsMarketEvidenceResponse | null;
  errorMessage: string | null;
  candidateTickers: ReadonlyArray<string>;
  repeatedCoreTickers: ReadonlyArray<string>;
  onLoad: () => void;
}

function BridgeStatusBadge({ state }: { state: BridgeState }) {
  if (state === "ok") {
    return <span className="bridge-status-badge bridge-status-ok">ok</span>;
  }
  if (state === "unavailable") {
    return (
      <span className="bridge-status-badge bridge-status-unavailable">
        unavailable
      </span>
    );
  }
  if (state === "loading") {
    return (
      <span className="bridge-status-badge bridge-status-loading">loading</span>
    );
  }
  return (
    <span className="bridge-status-badge bridge-status-not-loaded">
      not_loaded
    </span>
  );
}

function HoldingsRow({
  h,
  candidateTickerSet,
  repeatedCoreTickerSet,
}: {
  h: HoldingsMarketEvidenceItem;
  candidateTickerSet: ReadonlySet<string>;
  repeatedCoreTickerSet: ReadonlySet<string>;
}) {
  const overlapItems = h.constituents_overlap.overlap_with_market_core;
  const overlapsWithCandidate = candidateTickerSet.has(h.ticker);
  return (
    <div className="evidence-holding-row">
      <div className="evidence-holding-header">
        <strong style={{ fontSize: "0.9rem" }}>{h.name}</strong>
        <span className="evidence-holding-ticker">{h.ticker}</span>
        {overlapsWithCandidate ? (
          <span className="evidence-topn-badge evidence-topn-matched">
            현재 ETF Exposure 후보군 포함
          </span>
        ) : (
          <span className="evidence-topn-badge evidence-topn-unknown">
            후보군 외
          </span>
        )}
      </div>
      <ul className="evidence-notes-list">
        <li>
          구성종목 겹침 상태: <strong>{h.constituents_overlap.status}</strong>
        </li>
        {overlapItems.length > 0 ? (
          overlapItems.slice(0, 5).map((item, i) => {
            const isRepeated = item.ticker
              ? repeatedCoreTickerSet.has(item.ticker)
              : false;
            return (
              <li key={`${h.ticker}-ov-${i}`}>
                {item.name ?? item.ticker ?? "-"}
                {item.ticker ? ` (${item.ticker})` : ""}
                {item.weight_pct != null
                  ? ` · 보유 ETF 내 비중 ${item.weight_pct.toFixed(2)}%`
                  : ""}
                {isRepeated ? " · 반복 핵심 종목" : ""}
              </li>
            );
          })
        ) : (
          <li style={{ color: "var(--muted)" }}>
            겹치는 구성종목 데이터 없음
          </li>
        )}
      </ul>
    </div>
  );
}

export default function HoldingsOverlapBridgeCard({
  state,
  data,
  errorMessage,
  candidateTickers,
  repeatedCoreTickers,
  onLoad,
}: Props) {
  const candidateTickerSet = new Set(candidateTickers);
  const repeatedCoreTickerSet = new Set(repeatedCoreTickers);

  return (
    <div className="card">
      <h2>
        보유 ETF 겹침 정보 <BridgeStatusBadge state={state} />
      </h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        본 카드는 ETF Exposure 화면 컨테이너가 명시 호출했을 때만 기존 read-only
        API <code>GET /holdings/market-evidence/latest</code> 를 호출합니다. 페이지
        진입 시 자동 호출 X, Holdings 화면과의 결합은 State Bridge 만으로 유지합니다.
      </p>

      {state === "not_loaded" && (
        <>
          <div className="message info" style={{ marginBottom: 8 }}>
            보유 겹침 정보: 불러오지 않음. 아래 버튼을 누르면 보유 ETF와 현재 후보
            ETF의 구성종목 겹침을 1회 조회합니다.
          </div>
          <div className="btn-row">
            <button type="button" onClick={onLoad}>
              보유 ETF 겹침 불러오기
            </button>
          </div>
        </>
      )}

      {state === "loading" && (
        <div className="message info">불러오는 중...</div>
      )}

      {state === "unavailable" && (
        <>
          <div className="message error" style={{ marginBottom: 8 }}>
            보유 겹침 정보를 표시할 수 없습니다.
            {errorMessage ? ` (${errorMessage})` : ""}
          </div>
          <div className="btn-row">
            <button type="button" onClick={onLoad}>
              다시 불러오기
            </button>
          </div>
        </>
      )}

      {state === "ok" && data && (
        <>
          {data.summary.total_holdings_count === 0 ? (
            <div className="message info">
              저장된 보유 종목이 없습니다. Holdings 화면에서 보유 ETF를 입력·저장한
              뒤 다시 시도하세요.
            </div>
          ) : (
            <>
              <p style={{ margin: "0.25rem 0", fontSize: "0.85rem" }}>
                보유 <strong>{data.summary.total_holdings_count}</strong>건 ·
                후보 일치 <strong>{data.summary.matched_topn_count}</strong>건 ·
                구성종목 비교 가능{" "}
                <strong>{data.summary.constituents_available_count}</strong>건 ·
                NAV 미연동{" "}
                <strong>{data.summary.nav_discount_unavailable_count}</strong>건.
              </p>
              <div style={{ marginTop: 6 }}>
                {data.holdings.map((h, idx) => (
                  <HoldingsRow
                    key={`${idx}|${h.ticker}|${h.account_group ?? ""}`}
                    h={h}
                    candidateTickerSet={candidateTickerSet}
                    repeatedCoreTickerSet={repeatedCoreTickerSet}
                  />
                ))}
              </div>
              <p
                className="helper"
                style={{ marginTop: 6, fontSize: "0.78rem" }}
              >
                evidence_source: <code>GET /holdings/market-evidence/latest</code>{" "}
                · market_asof {data.market_asof ?? "-"} · holdings_asof{" "}
                {data.holdings_asof ?? "-"}
              </p>
            </>
          )}
        </>
      )}
    </div>
  );
}
