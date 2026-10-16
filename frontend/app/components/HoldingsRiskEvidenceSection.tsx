"use client";

// POC3-05 보유 ETF 확인 근거 — 읽기 전용 확인 영역 (B구간).
//
// 기존 evidence 재사용만: enriched(평가·비중·손익) + market-evidence(5일·20일·KODEX200 대비).
// 입력·저장 기능처럼 보이지 않는다(수정 버튼·저장 없음). 위험 점수/등급/매도 문구 없음.
// 급락 신호는 자동 조회 GET 계약 부재로 이번 Step 제외(PLAN §1.3·§6).
// POC5-UI-02: 사용자 선택 정렬 네 가지(평가 비중 · 손익률 · 5일 변화(기본) · 20일 변화 — 화면 숫자 그대로 ·
// 순서만 바꿈 · 재조회 0) · 선택 상세 맨 위 '자료 확인 안내'(그 종목의 기존 사유) · 「데이터 상태」는
// '전체 ETF NAV·괴리율 보기' 보조 이동(설계 §11).
// POC5-09: 가격 흐름 기준 줄(PC 저장 가격 기준일) · 기준일이 다른 종목은 5일 · 20일 · KODEX200 대비 '—'
// (backend 응답 사본이 값을 비움) · 상세에 실제 날짜 사유 · 가격 흐름 기준 · 저장 거래량(판정 §9-4).
// POC5-15: 요약 맨 위 '현재 상태 + ?'(시장 · 보유 조합 · 오늘 띠와 같은 함수) · 긴 안내는 ? 도움말 ·
// 실패 · 빈 보유 안내 앞에 같은 상태 문구.
// POC5-13: 목록 위 요약(시장 국면 · PC 최근 20저장일 하락 구간 · 판정 범위) · 보기 '하락 구간' ·
// 이름 옆 구간 배지(파란 계열) · 상세 'PC 20저장일 하락 구간' 줄. 구간 판정은 backend 응답 사본이 한다.
// 조회는 Dashboard 와 같은 캐시 키(DASH_KEY_HOLDINGS/EVIDENCE)를 공유한다(Q6 · N+1 없음).

import { useMemo, useState } from "react";
import {
  fetchEnrichedHoldings,
  fetchHoldingsMarketEvidence,
  type EnrichedHoldingsResult,
  type HoldingsMarketEvidenceItem,
  type HoldingsMarketEvidenceResponse,
} from "@/lib/api";
import { useSharedQuery } from "@/lib/api/queryCache";
import { DASH_KEY_HOLDINGS, DASH_KEY_EVIDENCE } from "@/lib/api/dashboardKeys";
import {
  DEFAULT_EVIDENCE_SORT,
  EVIDENCE_SORT_OPTIONS,
  buildRiskEvidenceRows,
  evidenceGuidance,
  sortEvidenceRows,
  type EvidenceSortKey,
  type RiskEvidenceRow,
} from "./holdings_risk_evidence/helpers";
import { declineDetailText } from "./holdings_risk_evidence/declineSummary";
import DeclineSummaryBlock from "./holdings_risk_evidence/DeclineSummaryBlock";
import PriceVolatilityBlock from "./holdings_risk_evidence/PriceVolatilityBlock";
import {
  FAILURE_TEXT,
  riskStateFromQueries,
} from "./holdings_risk_evidence/riskCombination";
import PriceChart from "./workbench/PriceChart";
import StoredVolumeBlock from "./StoredVolumeBlock";
import { priceBasisLine, priceFlowLine } from "@/lib/priceBasis";
import { VOLUME_HELP } from "@/lib/storedVolume";
// 손익·수익률 방향 색은 ETF 비교하기와 같은 함수를 쓴다 — 국내 관례 전환 시
// 한 곳만 고치면 두 화면이 함께 바뀐다.
import { directionColor } from "./workbench/helpers";
import type { MenuKey } from "./LeftSidebar";

type QuickView = "all" | "decline" | "need_check";

function fmtPct(v: number | null): string {
  if (v === null) return "자료 확인 필요";
  const s = v >= 0 ? "+" : "";
  return `${s}${v.toFixed(2)}%`;
}
function fmtPctp(v: number | null): string {
  if (v === null) return "자료 확인 필요";
  const s = v >= 0 ? "+" : "";
  return `${s}${v.toFixed(2)}%p`;
}
// POC5-09 — 기준일이 PC 비교 기준일과 달라 현재 비교에서 뺀 행은 값 칸을 '—'로 둔다(판정 §9-4-2).
function stale(r: RiskEvidenceRow): boolean {
  return r.price_dates?.comparison === "date_mismatch";
}
function fmtMoney(v: number | null): string {
  if (v === null) return "자료 확인 필요";
  return v.toLocaleString("ko-KR") + "원";
}
function fmtKstDate(iso: string | null): string {
  if (!iso) return "자료 없음";
  return iso;
}

// 선택 상세의 NAV·괴리율·구성종목·중복률 (§4.4·Q2 통합). 기존 HoldingsMarketEvidenceCard
// 의 표시 의미를 그대로 재사용 — 신규 계산 없음. topn_match·급락은 사용하지 않는다.
function NavConstituentsDetail({
  item,
}: {
  item: HoldingsMarketEvidenceItem | null;
}) {
  if (!item) {
    return (
      <p className="helper">시장 evidence 자료가 없어 NAV·구성종목을 표시할 수 없습니다.</p>
    );
  }
  const nav = item.nav_discount;
  const overlap = item.constituents_overlap;
  // §6.4: not_loaded/partial/unavailable 을 구분한다. partial 은 값이 있으면 보여주되
  // "부분 자료" 상태를 숨기지 않는다. ok 만 완전 정상으로 표시한다.
  const navShowsValues = nav.status === "ok" || nav.status === "partial";
  const navText = nav.nav != null ? Math.round(nav.nav).toLocaleString("ko-KR") : "-";
  const priceText =
    nav.market_price != null
      ? Math.round(nav.market_price).toLocaleString("ko-KR")
      : "-";
  const discountText =
    nav.discount_rate_pct != null ? `${nav.discount_rate_pct.toFixed(2)}%` : "-";

  return (
    <div className="hre-detail-evidence">
      <div className="hre-detail-line">
        <span className="k">NAV · 괴리율</span>
        <span className="v">
          {navShowsValues ? (
            <>
              NAV {navText} · 시장가 {priceText} · 괴리율 {discountText}
              {nav.asof ? ` · asof ${nav.asof}` : ""}
              {nav.status === "partial" ? (
                <span className="hre-status-check"> · 부분 자료</span>
              ) : null}
            </>
          ) : (
            `NAV / 괴리율 확인 불가 (${nav.status})`
          )}
          {nav.message ? (
            <span className="hre-detail-note"> · {nav.message}</span>
          ) : null}
        </span>
      </div>
      <div className="hre-detail-line">
        <span className="k">구성종목 중복</span>
        <span className="v">
          {overlap.status !== "ok" ? (
            `구성종목 확인 불가 (${overlap.status})`
          ) : overlap.overlap_with_market_core.length === 0 ? (
            "시장 핵심과 중복 구성종목 없음"
          ) : (
            <ul className="hre-overlap-list">
              {overlap.overlap_with_market_core.map((o, i) => (
                <li key={`${o.ticker ?? "na"}-${i}`}>
                  {o.name ?? o.ticker ?? "-"}
                  {o.weight_pct != null ? ` · 비중 ${o.weight_pct.toFixed(2)}%` : ""}
                </li>
              ))}
            </ul>
          )}
        </span>
      </div>
    </div>
  );
}

interface Props {
  // 선택 상세의 unavailable 사유 → "데이터 상태" 이동 (§7). 없으면 이동 버튼 미표시.
  onNavigate?: (key: MenuKey) => void;
}

export default function HoldingsRiskEvidenceSection({ onNavigate }: Props = {}) {
  const holdings = useSharedQuery<EnrichedHoldingsResult>(
    DASH_KEY_HOLDINGS,
    () => fetchEnrichedHoldings(),
  );
  const evidence = useSharedQuery<HoldingsMarketEvidenceResponse>(
    DASH_KEY_EVIDENCE,
    () => fetchHoldingsMarketEvidence(),
  );

  const [quickView, setQuickView] = useState<QuickView>("all");
  const [sortKey, setSortKey] = useState<EvidenceSortKey>(DEFAULT_EVIDENCE_SORT);
  const [selected, setSelected] = useState<string | null>(null);

  // 선택 ticker 의 evidence item (NAV·구성종목 선택 상세용). 통합 전 원본 item 에서
  // 첫 항목을 사용 — 목록 표는 이미 ticker 통합(helpers)되어 있으나 NAV·구성종목은
  // 선택 상세에서만 원본 그대로 보여준다(§4.4·§6.2 목록 판정에는 미포함).
  const selectedEvidence: HoldingsMarketEvidenceItem | null = useMemo(() => {
    if (!selected || evidence.phase !== "success") return null;
    return (
      evidence.data.holdings.find((h) => h.ticker === selected) ?? null
    );
  }, [selected, evidence]);

  const built = useMemo(() => {
    if (holdings.phase !== "success" || evidence.phase !== "success") return null;
    return buildRiskEvidenceRows(
      holdings.data.items,
      evidence.data.holdings,
    );
  }, [holdings, evidence]);

  const loading = holdings.phase === "loading" || evidence.phase === "loading";
  const failed = holdings.phase === "error" || evidence.phase === "error";

  const shownRows: RiskEvidenceRow[] = useMemo(() => {
    if (!built) return [];
    // POC5-13 — '하락 구간' 보기 = PC 20저장일 하락 구간에 든 종목(받은 자료로 거름 · 정렬 유지).
    const rows =
      quickView === "need_check"
        ? built.rows.filter((r) => r.need_check)
        : quickView === "decline"
          ? built.rows.filter((r) => r.decline_band?.state)
          : built.rows;
    return sortEvidenceRows(rows, sortKey);
  }, [built, quickView, sortKey]);

  // POC5-13 · POC5-15 — 현재 상태 · 하락 구간 요약(오늘 화면 띠와 같은 공통 판정 함수 · 같은 입력 → 같은 문구).
  // 목록용으로 이미 만든 행을 넘겨 다시 만들지 않는다.
  const risk = useMemo(
    () => riskStateFromQueries(holdings, evidence, built?.rows),
    [holdings, evidence, built],
  );
  const declineSummary = risk?.summary ?? null;

  // POC5-09 — PC 비교 기준일 · 기준일이 달라 현재 비교에서 뺀 종목(응답 선택 필드).
  const basis =
    evidence.phase === "success" ? (evidence.data.price_basis ?? null) : null;

  // 선택 종목 행 — 정렬 · 빠른 보기와 무관하게 전체 행에서 찾는다(재조회 0).
  const selectedRow: RiskEvidenceRow | null = useMemo(
    () => built?.rows.find((r) => r.ticker === selected) ?? null,
    [built, selected],
  );
  // 선택 종목의 '자료 확인 안내'.
  const selectedGuidance: string[] = useMemo(
    () => (selectedRow ? evidenceGuidance(selectedRow, basis) : []),
    [selectedRow, basis],
  );
  const selectedFlowLine: string | null = selectedRow?.price_dates?.end_date
    ? priceFlowLine(
        selectedRow.price_dates.end_date,
        selectedRow.price_dates.start_date_5d,
        selectedRow.price_dates.start_date_20d,
      )
    : null;

  return (
    <section aria-labelledby="hre-h" className="hre-section card">
      <h2 id="hre-h">보유 ETF 확인 근거</h2>
      <p className="helper">
        보유 ETF 를 하나씩 이어서, 최근 5일·20일 흐름과 KODEX200 대비 위치, 평가
        정보를 한 화면에서 확인합니다. 값을 수정하거나 저장하지 않는 읽기 전용
        확인 영역입니다.
      </p>

      {loading ? (
        <div className="message info">불러오는 중...</div>
      ) : risk?.combo.holdings === "no_holdings" ? (
        // POC5-15 — 정상 응답의 빈 보유가 실패보다 먼저(PLAN 판정 Q1).
        <div className="message info" data-testid="hre-risk-state-empty">
          <strong>{risk.combo.text}</strong> — 표시할 보유 ETF 가 없습니다.
        </div>
      ) : failed ? (
        // POC5-15 — 오늘 띠와 같은 상태 문구 + 실제 실패한 조회 한 문장(PLAN 판정 Q1).
        <div className="message info" data-testid="hre-risk-state-failed">
          <strong>{risk?.combo.text ?? "자료 확인 필요"}</strong> —{" "}
          {risk?.failed ? FAILURE_TEXT[risk.failed] : "보유 확인 근거 자료를 불러오지 못했습니다."}
        </div>
      ) : !built || built.rows.length === 0 ? (
        <div className="message info">표시할 보유 ETF 가 없습니다.</div>
      ) : (
        <>
          {/* 요약 — 기준일 · coverage */}
          <div className="hre-summary">
            <span>
              보유 기준일{" "}
              {fmtKstDate(
                evidence.phase === "success" ? evidence.data.holdings_asof : null,
              )}
            </span>
            <span>
              시장 기준일{" "}
              {fmtKstDate(
                evidence.phase === "success" ? evidence.data.market_asof : null,
              )}
            </span>
            <span>
              계산 가능 {built.coverage.ok}/{built.coverage.total} · 자료 확인 필요{" "}
              {built.coverage.need_check}
            </span>
          </div>
          {basis ? (
            <p className="helper" data-testid="hre-price-basis">
              {priceBasisLine(basis)}
            </p>
          ) : null}
          {risk?.summary ? <DeclineSummaryBlock v={risk} /> : null}

          {/* 빠른 보기 — 전체 / 하락 구간 / 자료 확인 필요 (POC5-13 · 급락 신호 빠른보기 없음) */}
          <div className="hre-quickview">
            <button
              type="button"
              className={quickView === "all" ? "active" : ""}
              onClick={() => setQuickView("all")}
            >
              전체
            </button>
            <button
              type="button"
              className={quickView === "decline" ? "active" : ""}
              onClick={() => setQuickView("decline")}
            >
              하락 구간 ({declineSummary?.inBand ?? 0})
            </button>
            <button
              type="button"
              className={quickView === "need_check" ? "active" : ""}
              onClick={() => setQuickView("need_check")}
            >
              자료 확인 필요 ({built.coverage.need_check})
            </button>
          </div>

          {/* POC5-UI-02 — 「보유 현황」 정렬과 같은 양식(선택 묶음 · UI-01 크기 예외). */}
          <div className="holdings-sortbar">
            <span className="holdings-sortbar-label">정렬</span>
            <div className="holdings-sort-seg" role="group" aria-label="확인 근거 정렬 기준">
              {EVIDENCE_SORT_OPTIONS.map(([key, label]) => (
                <button
                  key={key}
                  type="button"
                  className={sortKey === key ? "on" : ""}
                  aria-pressed={sortKey === key}
                  onClick={() => setSortKey(key)}
                >
                  {label}
                </button>
              ))}
            </div>
            <span className="holdings-sortbar-hint">
              {sortKey === "weight" ? "큰 값부터" : "작은 값부터"} · 값이 없는 종목은 맨 뒤
            </span>
          </div>

          {/* 2026-08-15 사용자 실화면 직접 지시 — 8컬럼 표 → 하이브리드 행.
              ETF 비교하기(.wb-hrow)와 같은 규칙: 좌측 2단 카드 + 우측 지표 열.
              지표가 5일·20일 둘뿐이라 우측은 2칸 + 라벨이 긴 KODEX200 대비 20일은
              아랫줄. 데이터 상태는 "확인됨" 이면 배지를 띄우지 않고 "자료 확인 필요"
              일 때만 표시한다(ETF 비교하기 ok 배지와 동일 방침).
              값이 없는 칸을 임의로 채우지 않는 기존 계약(자료 확인 필요 / —)은 그대로. */}
          <div className="wb-hlist" data-testid="hre-evidence-list">
            {shownRows.map((r) => (
              <div
                key={r.ticker}
                className={`wb-hrow${selected === r.ticker ? " sel" : ""}`}
                role="button"
                tabIndex={0}
                aria-pressed={selected === r.ticker}
                /* 접근가능 이름을 종목으로 고정한다. 없으면 행 안의 "자료 확인 필요"
                   배지 문구까지 이름에 섞여, 같은 문구를 쓰는 빠른보기 버튼 조회와
                   충돌한다(getByRole 다중 매치). */
                aria-label={`${r.name ?? r.ticker} 상세 보기`}
                onClick={() => setSelected(r.ticker)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelected(r.ticker);
                  }
                }}
              >
                <div className="wb-hcard">
                  <div className="wb-hrow-top">
                    <div className="wb-hrow-name">
                      <span className="hre-name">{r.name ?? r.ticker}</span>
                      {r.decline_band?.label || r.need_check ? (
                        <span className="wb-hbadges">
                          {r.decline_band?.label ? (
                            <span className="wb-hb band">{r.decline_band.label}</span>
                          ) : null}
                          {r.need_check ? (
                            <span className="wb-hb warn">자료 확인 필요</span>
                          ) : null}
                        </span>
                      ) : null}
                    </div>
                    <div className="wb-hrow-pnl">
                      <span
                        className="amt"
                        style={{ color: directionColor(r.pnl_rate_pct) }}
                      >
                        {fmtPct(r.pnl_rate_pct)}
                      </span>
                      <span className="rate wb-hmuted">손익률</span>
                    </div>
                  </div>
                  <div className="wb-hrow-bot">
                    <div className="wb-hrow-facts">
                      <span className="tk hre-ticker">{r.ticker}</span>
                      <span className="sep">/</span>
                      {r.market_weight_pct === null ? (
                        <span className="wb-hmuted">비중 자료 확인 필요</span>
                      ) : (
                        <span>
                          비중{" "}
                          <span className="wv">
                            {r.market_weight_pct.toFixed(1)}%
                          </span>
                        </span>
                      )}
                      <span className="sep">/</span>
                      {r.eval_amount === null ? (
                        <span className="wb-hmuted">평가 자료 확인 필요</span>
                      ) : (
                        <span>
                          평가 <span className="wv">{fmtMoney(r.eval_amount)}</span>
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                <div className="wb-hmetrics">
                  <div className="wb-hm2">
                    <div className="wb-hm-cell">
                      <span className="k">5일</span>
                      <span
                        className="v"
                        style={{ color: directionColor(r.return_5d_pct) }}
                      >
                        {stale(r) ? "—" : fmtPct(r.return_5d_pct)}
                      </span>
                    </div>
                    <div className="wb-hm-cell">
                      <span className="k">20일</span>
                      <span
                        className="v"
                        style={{ color: directionColor(r.return_20d_pct) }}
                      >
                        {stale(r) ? "—" : fmtPct(r.return_20d_pct)}
                      </span>
                    </div>
                  </div>
                  <div className="wb-hm-ex">
                    <span className="k">KODEX200 대비 20일</span>
                    <span
                      className="v"
                      style={{
                        color: directionColor(r.excess_vs_kodex200_20d_pctp),
                      }}
                    >
                      {stale(r) ? "—" : fmtPctp(r.excess_vs_kodex200_20d_pctp)}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* 선택 상세 — 가격 차트(lazy) + NAV·괴리율·구성종목·중복률(§4.4·Q2 통합).
              이 정보의 unavailable 은 선택 상세에서만 표시하며 목록 전체의 자료 확인
              필요 판정에는 넣지 않는다(§6.2). */}
          {selected ? (
            <div className="hre-detail">
              <h3>{selected} 상세</h3>
              {selectedGuidance.length > 0 || selectedFlowLine || selectedRow ? (
                <div className="hre-detail-evidence">
                  {selectedGuidance.length > 0 ? (
                    <div className="hre-detail-line" data-testid="hre-guidance">
                      <span className="k">자료 확인 안내</span>
                      <span className="v">
                        {selectedGuidance.map((t) => (
                          <span key={t} className="hre-guidance-item">
                            {t}
                            <br />
                          </span>
                        ))}
                      </span>
                    </div>
                  ) : null}
                  {selectedRow ? (
                    <div className="hre-detail-line" data-testid="hre-decline-band">
                      <span className="k">PC 20저장일 하락 구간</span>
                      <span className="v">
                        {declineDetailText(selectedRow, basis)}
                      </span>
                    </div>
                  ) : null}
                  {selectedFlowLine ? (
                    <div className="hre-detail-line" data-testid="hre-price-flow">
                      <span className="k">가격 흐름 기준</span>
                      <span className="v">{selectedFlowLine}</span>
                    </div>
                  ) : null}
                </div>
              ) : null}
              <PriceChart ticker={selected} />
              <div className="hre-detail-evidence">
                <StoredVolumeBlock
                  title={`${selectedRow?.name ?? selected} 거래량`}
                  ev={selectedEvidence?.stored_volume}
                  help={VOLUME_HELP}
                  columns={4}
                  headClassName="svb-head"
                  referenceDate={basis?.reference_date}
                />
                {/* POC5-16 — 가격 흔들림(변동성) 접힌 구역 · 거래량 바로 아래 · 종목을 바꾸면 다시 접힘(key) */}
                <PriceVolatilityBlock
                  key={selected ?? ""}
                  ev={selectedEvidence?.price_volatility}
                  flowDate={basis?.reference_date ?? null}
                />
              </div>
              <NavConstituentsDetail item={selectedEvidence} />
              {onNavigate ? (
                <button
                  type="button"
                  style={{ marginTop: 8 }}
                  onClick={() => onNavigate("data_status")}
                >
                  전체 ETF NAV·괴리율 보기 →
                </button>
              ) : null}
            </div>
          ) : (
            <p className="helper hre-detail-hint">
              표에서 ETF 를 선택하면 가격 흐름·NAV·구성종목 상세를 볼 수 있습니다.
            </p>
          )}
        </>
      )}
    </section>
  );
}
