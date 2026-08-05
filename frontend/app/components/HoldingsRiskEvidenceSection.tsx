"use client";

// POC3-05 보유 ETF 확인 근거 — 읽기 전용 확인 영역 (B구간).
//
// 기존 evidence 재사용만: enriched(평가·비중·손익) + market-evidence(5일·20일·KODEX200 대비).
// 입력·저장 기능처럼 보이지 않는다(수정 버튼·저장 없음). 위험 점수/등급/매도 문구 없음.
// 급락 신호는 자동 조회 GET 계약 부재로 이번 Step 제외(PLAN §1.3·§6).
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
  buildRiskEvidenceRows,
  type RiskEvidenceRow,
} from "./holdings_risk_evidence/helpers";
import PriceChart from "./workbench/PriceChart";
import type { MenuKey } from "./LeftSidebar";

type QuickView = "all" | "need_check";

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
    if (quickView === "need_check") return built.rows.filter((r) => r.need_check);
    return built.rows;
  }, [built, quickView]);

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
      ) : failed ? (
        <div className="message info">
          보유 확인 근거 자료를 불러오지 못했습니다. 자료 확인이 필요합니다.
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

          {/* 빠른 보기 — 전체 / 자료 확인 필요 (급락 신호 빠른보기 없음) */}
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
              className={quickView === "need_check" ? "active" : ""}
              onClick={() => setQuickView("need_check")}
            >
              자료 확인 필요 ({built.coverage.need_check})
            </button>
          </div>

          {/* 고밀도 표 (ticker 통합 · 한 줄) */}
          <div className="hre-table-wrap">
            <table className="hre-table">
              <thead>
                <tr>
                  <th>ETF</th>
                  <th>평가금액</th>
                  <th>평가 비중</th>
                  <th>손익률</th>
                  <th>5일</th>
                  <th>20일</th>
                  <th>KODEX200 대비 20일</th>
                  <th>데이터 상태</th>
                </tr>
              </thead>
              <tbody>
                {shownRows.map((r) => (
                  <tr
                    key={r.ticker}
                    className={selected === r.ticker ? "selected" : ""}
                    onClick={() => setSelected(r.ticker)}
                  >
                    <td>
                      <span className="hre-name">{r.name ?? r.ticker}</span>
                      <span className="hre-ticker">{r.ticker}</span>
                    </td>
                    <td>{fmtMoney(r.eval_amount)}</td>
                    <td>{r.market_weight_pct === null ? "자료 확인 필요" : `${r.market_weight_pct.toFixed(1)}%`}</td>
                    <td>{fmtPct(r.pnl_rate_pct)}</td>
                    <td>{fmtPct(r.return_5d_pct)}</td>
                    <td>{fmtPct(r.return_20d_pct)}</td>
                    <td>{fmtPctp(r.excess_vs_kodex200_20d_pctp)}</td>
                    <td>
                      <span
                        className={
                          r.need_check ? "hre-status-check" : "hre-status-ok"
                        }
                      >
                        {r.need_check ? "자료 확인 필요" : "확인됨"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 선택 상세 — 가격 차트(lazy) + NAV·괴리율·구성종목·중복률(§4.4·Q2 통합).
              이 정보의 unavailable 은 선택 상세에서만 표시하며 목록 전체의 자료 확인
              필요 판정에는 넣지 않는다(§6.2). */}
          {selected ? (
            <div className="hre-detail">
              <h3>{selected} 상세</h3>
              <PriceChart ticker={selected} />
              <NavConstituentsDetail item={selectedEvidence} />
              {onNavigate ? (
                <button
                  type="button"
                  style={{ marginTop: 8 }}
                  onClick={() => onNavigate("diagnostics")}
                >
                  진단·상태에서 원인 확인 →
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
