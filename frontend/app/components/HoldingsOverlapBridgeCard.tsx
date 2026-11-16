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

// POC6-31 사용자 지시(2026-11-16 · 화면 글자는 쉬운 한국어) — 서버 상태 코드를 그대로 보이지 않는다(모르는 값은 그대로).
const OVERLAP_STATUS_TEXT: Record<string, string> = {
  ok: "비교함",
  constituents_unavailable: "보유 ETF 구성 자료 없음",
  market_core_unavailable: "비교할 시장 기준 자료 없음",
  unavailable: "확인 못 함",
};

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
            이 목록에 있음
          </span>
        ) : (
          <span className="evidence-topn-badge evidence-topn-unknown">
            이 목록에 없음
          </span>
        )}
      </div>
      <ul className="evidence-notes-list">
        <li>
          구성종목 겹침 상태: <strong>{OVERLAP_STATUS_TEXT[h.constituents_overlap.status] ?? h.constituents_overlap.status}</strong>
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
      {/* POC6-31 사용자 지시(2026-11-16 · 화면 글자는 쉬운 한국어) — 개발 문구는 아래 '자세히' 안으로. */}
      <p className="helper" style={{ marginBottom: 8 }}>
        보유 ETF와 이 목록 ETF의 구성종목 겹침을 [보유 ETF 겹침 불러오기]를 누를 때 한 번 읽습니다(화면을 열 때 자동으로
        읽지 않음).
      </p>

      {state === "not_loaded" && (
        <>
          <div className="message info" style={{ marginBottom: 8 }}>
            보유 겹침 정보: 불러오지 않음. 아래 버튼을 누르면 보유 ETF와 현재 후보
            ETF의 구성종목 겹침을 1회 조회합니다.
          </div>
          <div className="btn-row">
            <button type="button" className="wb-btn btn-md" onClick={onLoad}>
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
            <button type="button" className="wb-btn btn-md" onClick={onLoad}>
              다시 불러오기
            </button>
          </div>
        </>
      )}

      {state === "ok" && data && (
        <>
          {data.summary.total_holdings_count === 0 ? (
            <div className="message info">
              저장된 보유 종목이 없습니다. 「종목 관리」에서 보유 ETF를 입력 · 저장한
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
              <details className="helper" style={{ marginTop: 6, fontSize: "0.78rem" }}>
                <summary>자세히</summary>
                읽은 곳: <code>GET /holdings/market-evidence/latest</code> · 시장 기준일 {data.market_asof ?? "-"} ·
                보유 기준일 {data.holdings_asof ?? "-"}
              </details>
            </>
          )}
        </>
      )}
    </div>
  );
}
