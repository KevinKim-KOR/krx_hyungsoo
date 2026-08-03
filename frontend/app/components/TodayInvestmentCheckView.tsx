"use client";

// POC3-01 오늘의 투자 점검 (Today Investment Check) — 새 기본 진입 화면.
//
// 설계서 목표(§2): 새 대시보드만 보고 10초 안에 코스피 현재 위치 / 사용자가 생각할 일
// / 시스템이 처리할 일을 구분한다. 개별 ETF 최종 매수·매도 판단이나 신규 위험 산식은
// 이번 Step 범위가 아니다.
//
// 화면 계약:
// - §4.1 코스피는 지금 어디쯤인가: 코스피 차트(대표) + [별도 영역] 기존 시장 판정
//   (KODEX200 기준) + KODEX200 MA20/MA60 대비 거리. 두 기준을 하나로 묶어
//   "코스피 시장 상태" 라고 표기하지 않는다 (설계자 Q2/Q4 강제 분리 · FAIL 조건).
//   흐름 지속 거래일 수 / 최근 고점 대비 위치 / 거래량 = 개발 중 (Q3/Q5).
// - §4.2 오늘 내가 확인할 것 (판단 큐): 요즘 잘 오르는 ETF(건수+진입) / 내가 가진 ETF
//   중 확인할 종목(개발 중). 정비 항목은 여기에 절대 넣지 않는다 (AC-4/AC-5).
// - §4.3 자료 업데이트 필요 (정비 큐): 자료 최신성/미수집/실패 + 경량 갱신(Q7:
//   저장값 재조회 + holdings/market/refresh) + 항목별 대량 갱신 화면 이동(Q8).
// - §4.4 개발 중인 판단 기능: 미구현 기능을 숨기지 않고 정직하게 표시.
//
// 데이터: 모두 기존 경로 재사용 + POC3-01 KOSPI 시계열 read 확장. 신규 산식/소스 없음.
// Dashboard 와 같은 조회 조건은 같은 캐시 키 공유(화면 왕복 재조회 방지).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchMarketTopnLatest,
  type MarketTopNResponse,
  fetchEnrichedHoldings,
  type EnrichedHoldingsResult,
  fetchHoldingsMarketEvidence,
  type HoldingsMarketEvidenceResponse,
  fetchNavDiscountLatest,
  type NavDiscountLatestResponse,
  refreshMarket,
} from "@/lib/api";
import { useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import {
  DASH_KEY_MARKET,
  DASH_KEY_HOLDINGS,
  DASH_KEY_EVIDENCE,
  DASH_KEY_NAV,
} from "@/lib/api/dashboardKeys";
import type { MenuKey } from "./LeftSidebar";
import {
  buildRiskEvidenceRows,
  lowestFiveDayRows,
} from "./holdings_risk_evidence/helpers";
import KospiChart from "./today/KospiChart";
import {
  fmtKstDate,
  fmtPct,
  maDistanceText,
  regimeLabelKo,
} from "./today/todayHelpers";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

// ── §4.3 정비 큐 항목 (자료 상태) ────────────────────────────────────────────
// 판단 큐와 절대 섞이지 않도록 별도 타입/수집 함수로 분리.
// kind (§4.3): "light" = 대시보드에서 바로 "지금 다시 불러오기" 로 해소 가능(저장값
// 재조회). "heavy" = 전체 수집·재계산이 필요해 상세 화면에서 실행해야 함(Q8).
type MaintenanceItem = {
  text: string; // 사용자 언어 (내부 용어 비노출)
  kind: "light" | "heavy";
  target: MenuKey; // heavy 일 때 이동할 상세 화면 (Q8: 항목별 직접)
  actionLabel: string;
  // ⓘ 근거: 무엇과 무엇을 비교/확인해 최신이 아닌지 (실제 값 기반 · 임시 숫자 없음).
  // 정비 큐 판정 근거의 정식 표준은 후속 설계에서 확정 (임시 문구).
  reason?: string;
};

function collectMaintenance(
  holdings: QueryState<EnrichedHoldingsResult>,
  evidence: QueryState<HoldingsMarketEvidenceResponse>,
  nav: QueryState<NavDiscountLatestResponse>,
  market: QueryState<MarketTopNResponse>,
): MaintenanceItem[] {
  const list: MaintenanceItem[] = [];

  // light 는 "지금 다시 불러오기"(POST /holdings/market/refresh)로 실제 해소되는
  // 것만 — 이 API 는 보유 종목의 "현재가" 만 갱신한다. 현재가 결측 보유 종목이
  // 있으면 그 건수를 light 항목으로 노출 (갱신 후 실제로 사라짐 → 계약·동작 일치).
  if (holdings.phase === "success") {
    const missing = holdings.data.items.filter((h) => h.price_missing).length;
    if (missing > 0) {
      list.push({
        text: `보유 종목 현재가를 불러오지 못했습니다 (${missing}건)`,
        kind: "light",
        target: "holdings",
        actionLabel: "지금 다시 불러오기",
        reason:
          "보유 종목의 저장된 현재가(시세)를 불러오지 못한 상태입니다. '업데이트' 로 저장된 시세를 다시 불러옵니다.",
      });
    }
  }

  // VIX stale (시장 불안 지표가 오래됨) — 시장 응답의 risk reference 로 판정.
  if (market.phase === "success") {
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
      // 시장 불안 지표(VIX) 갱신은 전체 시장 자료 수집 필요 → heavy.
      list.push({
        text: `시장 불안 지표가 오래되었습니다 (기준일 ${vix.as_of_date})`,
        kind: "heavy",
        target: "market_discovery",
        actionLabel: "시장 자료 업데이트로",
        reason: `시장 불안 지표(VIX)의 기준일(${vix.as_of_date})이 시장 기준일(${kodex.as_of_date})보다 이전입니다. 두 기준일을 비교해 더 이전이면 오래된 것으로 봅니다.`,
      });
    }
    if (vix?.availability === "unavailable") {
      list.push({
        text: "시장 불안 지표 자료가 없습니다",
        kind: "heavy",
        target: "market_discovery",
        actionLabel: "시장 자료 업데이트로",
        reason: "시장 불안 지표(VIX) 자료가 아직 수집되지 않았습니다.",
      });
    }
  }

  // 보유 ETF 관련 자료 상태.
  if (evidence.phase === "success") {
    const s = evidence.data.summary;
    if (s.constituents_unavailable_count > 0) {
      // 구성종목 수집은 대량 작업 → heavy (상세 화면).
      list.push({
        text: `ETF가 담고 있는 종목 자료가 없습니다 (${s.constituents_unavailable_count}건)`,
        kind: "heavy",
        target: "etf_exposure",
        actionLabel: "구성종목 업데이트로",
        reason:
          "이 ETF가 담고 있는 종목·비중(구성종목) 자료가 아직 수집되지 않았습니다. 구성종목 화면에서 수집합니다.",
      });
    }
    if (s.evidence_unavailable_count > 0) {
      // 시장 비교 evidence 는 시장 자료 갱신이 필요 → 경량 갱신(현재가)으로 해소
      // 안 됨 → heavy (상세 화면). (2026-07-30 재분류: light→heavy)
      list.push({
        text: `내가 가진 ETF와 시장 비교 자료가 오래되었습니다 (${s.evidence_unavailable_count}건)`,
        kind: "heavy",
        target: "market_discovery",
        actionLabel: "시장 자료 업데이트로",
        reason:
          "보유 ETF가 현재 시장에서 어떤 위치인지(요즘 잘 오르는 ETF 목록에 드는지·KODEX200 대비 초과수익·단기 흐름) 비교한 자료가 최신 시장 기준으로 재계산되지 않았습니다.",
      });
    }
    if (s.nav_discount_unavailable_count > 0) {
      list.push({
        text: `ETF 기준가 비교 자료가 없습니다 (${s.nav_discount_unavailable_count}건)`,
        kind: "heavy",
        target: "etf_exposure",
        actionLabel: "구성종목 업데이트로",
        reason:
          "ETF의 순자산가치(NAV)와 시장가격을 비교한 괴리 자료가 없습니다. NAV보다 비싸게/싸게 거래되는지 확인하는 값입니다.",
      });
    }
  } else if (evidence.phase === "error") {
    list.push({
      text: "보유 ETF 비교 자료를 불러오지 못했습니다",
      kind: "heavy",
      target: "market_discovery",
      actionLabel: "시장 자료 업데이트로",
      reason: "보유 ETF의 시장 비교 자료를 조회하지 못했습니다.",
    });
  }

  // NAV 미연동/실패 — 기준가 자료는 구성종목/시장 갱신 필요 → heavy (재분류).
  if (nav.phase === "success") {
    const s = nav.data.summary;
    // B-1: 필수 집계 필드가 숫자가 아니면(손상 응답) 0 으로 위장하지 않고 "확인 불가".
    const uc = s?.unavailable_count;
    const fc = s?.failed_count;
    if (typeof uc !== "number" || typeof fc !== "number") {
      list.push({
        text: "ETF 기준가 자료 상태를 확인할 수 없습니다",
        kind: "heavy",
        target: "etf_exposure",
        actionLabel: "구성종목 업데이트로",
        reason:
          "ETF 기준가(NAV) 자료의 상태 집계가 응답에 없어 정상 여부를 확인할 수 없습니다.",
      });
    } else if (uc + fc > 0) {
      list.push({
        text: `ETF 기준가 자료가 일부 없습니다 (${uc + fc}건)`,
        kind: "heavy",
        target: "etf_exposure",
        actionLabel: "구성종목 업데이트로",
        reason:
          "일부 ETF의 순자산가치(NAV)·시장가격 괴리 자료가 없습니다. NAV 대비 현재 가격 수준을 확인하는 값입니다.",
      });
    }
  } else if (nav.phase === "error") {
    list.push({
      text: "ETF 기준가 자료를 불러오지 못했습니다",
      kind: "heavy",
      target: "etf_exposure",
      actionLabel: "구성종목 업데이트로",
      reason: "ETF 순자산가치(NAV) 자료를 조회하지 못했습니다.",
    });
  }

  return list;
}

// ── §4.1 코스피 대표 (헤드라인) — 첫 화면 필수 요소만 compact ────────────────
// 코스피 차트 + [별도] 기존 시장 판정(KODEX200 기준) + KODEX200 MA 거리.
// 코스피와 KODEX200 을 하나로 묶지 않는다 (§3.1 강제 분리 · FAIL 조건).
function KospiHeadline({ market }: { market: QueryState<MarketTopNResponse> }) {
  const ctx =
    market.phase === "success" ? market.data.market_context ?? null : null;
  const kodex = ctx?.kodex200;
  const kospi = ctx?.kospi;
  const asof = ctx?.asof ?? (market.phase === "success" ? market.data.asof : null);

  return (
    <section className="tc-card tc-headline" aria-label="KOSPI 현재 위치">
      {/* 사용자 요청: 대표 제목은 "KOSPI". 코스피 가격 = 대표, KODEX200 판정은 별도. */}
      <h2 className="tc-h2">KOSPI</h2>

      {/* 코스피 차트(좌·넓게) + 시장 판정/기준선 패널(우). 전체 폭 대표 영역. */}
      <div className="tc-headline-grid">
        <div className="tc-headline-chart">
          <div className="tc-label">코스피 가격 흐름</div>
          <KospiChart />
        </div>

        <div className="tc-headline-stats">
          {/* 코스피 수익률·위치 (저장 KOSPI 시계열 기반 · POC3-06 §6.2 실제값).
              일간·1년·최근 1년 고점 대비를 실제 저장값으로 표시(개발 중 자리표시 제거). */}
          <div className="tc-stat-block">
            <div className="tc-label">코스피 수익률·위치</div>
            {kospi && kospi.status === "ok" ? (
              <ul className="tc-list-plain">
                <li>
                  일간{" "}
                  {kospi.daily_return_pct != null
                    ? fmtPct(kospi.daily_return_pct)
                    : "자료 없음"}
                </li>
                <li>1개월 {fmtPct(kospi.return_1m_pct)}</li>
                <li>3개월 {fmtPct(kospi.return_3m_pct)}</li>
                <li>
                  1년{" "}
                  {kospi.return_1y_pct != null
                    ? fmtPct(kospi.return_1y_pct)
                    : "자료 없음"}
                </li>
                <li>
                  최근 1년 고점 대비{" "}
                  {kospi.high_52w_gap_pct != null
                    ? fmtPct(kospi.high_52w_gap_pct)
                    : "자료 없음"}
                </li>
              </ul>
            ) : (
              <span className="tc-muted">수익률·위치 자료 없음</span>
            )}
          </div>

          {/* 기존 시장 판정 — KODEX200 기준임을 명시. 코스피와 합치지 않음(§3.1). */}
          <div className="tc-stat-block tc-divider">
            <div className="tc-label">
              기존 시장 판정 참고{" "}
              <span className="tc-muted tc-small">· KODEX200 기준</span>
            </div>
            {ctx ? (
              <div>
                <span className="tc-regime">
                  {regimeLabelKo(ctx.regime_code, ctx.regime_label)}
                </span>
                {/* POC3-06 §6.2 — 현재 국면 지속 거래일 수(실제값, 개발 중 제거). */}
                {ctx.regime_streak && ctx.regime_streak.streak_days != null ? (
                  <span className="tc-muted tc-small">
                    {" "}
                    · {ctx.regime_streak.streak_days}거래일째
                    {ctx.regime_streak.at_least ? " 이상" : ""}
                  </span>
                ) : (
                  <span className="tc-muted tc-small"> · 지속일 자료 없음</span>
                )}
                {ctx.asof && (
                  <span className="tc-muted tc-small"> · 기준일 {fmtKstDate(ctx.asof)}</span>
                )}
                <p className="tc-muted tc-small" style={{ marginTop: 4 }}>
                  코스피 가격 흐름과 별개로, 시스템의 기존 시장 판정은 KODEX200
                  지표로 계산됩니다.
                </p>
              </div>
            ) : (
              <span className="tc-muted">시장 판정 확인 불가</span>
            )}
          </div>

          {/* KODEX200 기준선 대비 위치 — MA20·MA60 각각 명시 (단일 표기 금지). */}
          <div className="tc-stat-block tc-divider">
            <div className="tc-label">KODEX200 기준선 대비 위치</div>
            {kodex && kodex.status === "ok" ? (
              <ul className="tc-list-plain">
                <li>{maDistanceText("MA20", kodex.ma20_distance_pct, kodex.ma20_position)}</li>
                <li>{maDistanceText("MA60", kodex.ma60_distance_pct, kodex.ma60_position)}</li>
              </ul>
            ) : (
              <span className="tc-muted">기준선 자료 확인 불가</span>
            )}
            {/* AC-11: 한계 설명은 hover 툴팁(ⓘ). 항상 노출 문단 아님. */}
            <span
              className="tc-info"
              tabIndex={0}
              role="note"
              aria-label="현재 시장 판정에 쓰는 이동평균 기준선까지의 거리입니다. 급격한 하락이나 반등에는 늦게 반응할 수 있으며, 미래의 추세 전환을 예측하는 값은 아닙니다."
              title="현재 시장 판정에 쓰는 이동평균 기준선까지의 거리입니다. 급격한 하락이나 반등에는 늦게 반응할 수 있으며, 미래의 추세 전환을 예측하는 값은 아닙니다."
            >
              ⓘ 이 값의 한계
            </span>
          </div>

          <div className="tc-muted tc-small tc-divider" style={{ paddingTop: 12 }}>
            마지막 자료 기준일 {fmtKstDate(asof)}
          </div>
        </div>
      </div>
    </section>
  );
}

// 미제공 지표 1건 — 이름 + 상태 + 사유(hover 툴팁). 임시 숫자 없이 정직 표시.
type BlockedMetric = { name: string; badge: string; reason: string };

// 이번 Step 에서 코스피 영역에 "안 되는 것" 을 모두 기록 (사용자 지시 2026-07-29).
// 두 부류로 구분: (A) 기능 개발 중 (향후 저장값 파생) (B) 이번 단계 미도입
// (설계서 §11 금지 · 신규 산식/수집 필요 → 후속 Step). 숨기지 않고 board 로 노출.
// 2026-08-03 POC3-06 §3.2 — 흐름 지속 거래일 수·최근 고점 대비 위치·일간 등락률·
// 1년 수익률은 실제값으로 교체 완료(위 KospiHeadline). 개발 중 board 에서 제거.
const KOSPI_IN_DEV: BlockedMetric[] = [];

const KOSPI_NOT_IN_STEP: BlockedMetric[] = [
  {
    name: "거래량 흐름",
    badge: "이번 단계 미도입",
    reason: "현재 거래량 자료를 저장하지 않아 표시할 수 없습니다. 신규 수집이 필요해 이번 단계에서는 넣지 않습니다.",
  },
  {
    name: "공격·방어 비중",
    badge: "이번 단계 미도입",
    reason: "공격·방어 비중은 이번 화면 개편 단계의 범위가 아닙니다 (매매 비중 판단 표시 안 함).",
  },
  {
    name: "추세 전환선 (SuperTrend)",
    badge: "이번 단계 미도입",
    reason: "SuperTrend 등 신규 추세 전환 지표는 이번 단계에 도입하지 않습니다. 후속 위험 신호 단계에서 검토합니다.",
  },
];

function BlockedRow({ m }: { m: BlockedMetric }) {
  const dev = m.badge === "개발 중";
  return (
    <span>
      {m.name}{" "}
      <span className={dev ? "tc-badge tc-badge-dev" : "tc-badge tc-badge-off"}>
        {m.badge}
      </span>
      <span
        className="tc-info"
        tabIndex={0}
        role="note"
        aria-label={m.reason}
        title={m.reason}
      >
        {" "}
        ⓘ
      </span>
    </span>
  );
}

// ── §4.1 코스피 상세 — 이번 Step 에 아직/안 넣는 항목 board (정직 노출). ───────
function KospiDetailSection({
  market,
}: {
  market: QueryState<MarketTopNResponse>;
}) {
  void market; // 현재는 모두 미제공 — 향후 시계열 파생 시 market 사용.
  return (
    <section className="tc-card" aria-label="코스피 상세 (개발 중)">
      <h2 className="tc-h2">코스피 상세 지표</h2>
      <p className="tc-muted tc-small" style={{ marginBottom: 10 }}>
        아래 항목은 값이 없어 숨긴 것이 아니라, 아직 제공하지 않는 상태를 그대로
        표시한 것입니다.
      </p>
      <div className="tc-dev-row">
        {KOSPI_IN_DEV.map((m) => (
          <BlockedRow key={m.name} m={m} />
        ))}
        {KOSPI_NOT_IN_STEP.map((m) => (
          <BlockedRow key={m.name} m={m} />
        ))}
      </div>
    </section>
  );
}

// ── §4.2 판단 큐 (오늘 내가 확인할 것) ───────────────────────────────────────
function JudgmentQueueSection({
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
  // POC3-06 §6.1·§6.3 — 두 조회 성공 시 공통 판단 요약을 1회 계산한다.
  // buildRiskEvidenceRows·lowestFiveDayRows 는 backend market_summary_composer 의
  // select_top_holdings 와 동일 규칙(전환 테스트로 고정) → Dashboard·PUSH 가 같은
  // 최대 3건·자료 확인 필요 건수를 표시한다(AC-2·6·7·14).
  const built =
    holdings.phase === "success" && evidence.phase === "success"
      ? buildRiskEvidenceRows(holdings.data.items, evidence.data.holdings)
      : null;
  const needCheckCount = built ? built.coverage.need_check : null;
  const topHoldings = built ? lowestFiveDayRows(built.rows, 3) : [];
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
function MaintInfo({ reason }: { reason?: string }) {
  if (!reason) return null;
  return (
    <span
      className="tc-info"
      tabIndex={0}
      role="note"
      aria-label={reason}
      title={reason}
    >
      {" "}
      ⓘ
    </span>
  );
}

// ── §4.3 정비 큐 (자료 업데이트 필요) ────────────────────────────────────────
function MaintenanceQueueSection({
  items,
  loading,
  refreshing,
  onLightRefresh,
  onNavigate,
}: {
  items: MaintenanceItem[];
  loading: boolean;
  refreshing: "idle" | "running" | "done" | "failed";
  onLightRefresh: () => void;
  onNavigate: (key: MenuKey) => void;
}) {
  const lightItems = items.filter((it) => it.kind === "light");
  const heavyItems = items.filter((it) => it.kind === "heavy");
  return (
    <section className="tc-card" aria-label="자료 최신화 필요">
      {/* 제목 + 건수. "최신" 배지는 아래 보유 현재가 행 문구 옆으로 이동(사용자 지시). */}
      <div className="tc-maint-title-row">
        <h2 className="tc-h2" style={{ marginBottom: 0 }}>
          자료 최신화 필요{" "}
          {!loading && (
            <span className="tc-count">
              {items.length > 0 ? `${items.length}건` : "0건"}
            </span>
          )}
        </h2>
      </div>

      {loading ? (
        <p className="tc-maint-asof tc-muted">자료 상태 확인 중...</p>
      ) : (
        // 모든 항목을 동일한 행 형태로 (그룹 라벨·상태줄 없음 · 사용자 지시 2026-07-30).
        // 각 행: [최신 배지?] 문구 ⓘ근거 ... [버튼]. light/heavy 형태 동일.
        <ul className="tc-maint-list">
          {/* 보유 현재가(light) 행 — 결측이 있으면 그 항목, 없으면 "최신" 배지 행. */}
          {lightItems.length > 0 ? (
            lightItems.map((it, i) => (
              <li key={`l${i}`} className="tc-maint-item">
                <span className="tc-maint-text">
                  {it.text}
                  <MaintInfo reason={it.reason} />
                  {refreshing === "done"
                    ? " · 완료"
                    : refreshing === "failed"
                      ? " · 실패"
                      : ""}
                </span>
                <button
                  type="button"
                  className="tc-btn tc-btn-link"
                  onClick={onLightRefresh}
                  disabled={refreshing === "running"}
                >
                  {refreshing === "running" ? "불러오는 중..." : "업데이트"}
                </button>
              </li>
            ))
          ) : (
            <li className="tc-maint-item">
              <span className="tc-maint-text">
                <span className="tc-fresh-badge">최신</span> 보유 종목 현재가는 최신
                상태입니다
                <MaintInfo reason="보유 종목의 저장된 현재가(시세)가 모두 있습니다. '업데이트' 로 저장된 시세를 다시 불러올 수 있습니다." />
                {refreshing === "done"
                  ? " · 완료"
                  : refreshing === "failed"
                    ? " · 실패"
                    : ""}
              </span>
              <button
                type="button"
                className="tc-btn tc-btn-link"
                onClick={onLightRefresh}
                disabled={refreshing === "running"}
              >
                {refreshing === "running" ? "불러오는 중..." : "업데이트"}
              </button>
            </li>
          )}
          {/* 상세 화면 갱신 대상(heavy) — 같은 행 형태 + ⓘ근거 + 이동 버튼. */}
          {heavyItems.map((it, i) => (
            <li key={`h${i}`} className="tc-maint-item">
              <span className="tc-maint-text">
                {it.text}
                <MaintInfo reason={it.reason} />
              </span>
              <button
                type="button"
                className="tc-btn tc-btn-link"
                onClick={() => onNavigate(it.target)}
              >
                {it.actionLabel}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// ── §4.4 개발 중인 판단 기능 — 빠진 기능 전체 board (사용자 지시 2026-07-29) ───
// 이번 화면에 넣기로 했으나 아직 없는 기능 + 이번 단계에 안 넣기로 한 기능을 모두
// 한곳에 기록해, 앞으로 무엇을 설계·개발해야 하는지 화면에서 직접 보이게 한다.
type DevItem = { name: string; badge: string; desc: string };

const DEV_IN_PROGRESS: DevItem[] = [
  {
    name: "내가 가진 ETF의 위험 신호",
    badge: "개발 중",
    desc: "보유 ETF 중 먼저 점검할 종목과 그 이유를 찾는 기능.",
  },
  {
    name: "시장 흐름 전환까지의 거리",
    badge: "개발 중",
    desc: "현재는 KODEX200 기준선 대비 위치만 참고로 제공합니다.",
  },
  // 2026-08-03 POC3-06: 흐름 지속 거래일 수·최근 고점 대비 위치·일간 등락률·
  // 1년 수익률은 실제값 제공 완료 → 개발 중 목록에서 제거.
];

const DEV_NOT_IN_STEP: DevItem[] = [
  {
    name: "거래량 흐름",
    badge: "이번 단계 미도입",
    desc: "거래량 자료 미저장 — 신규 수집 필요.",
  },
  {
    name: "공격·방어 비중",
    badge: "이번 단계 미도입",
    desc: "매매 비중 판단 표시는 이번 단계 범위 밖.",
  },
  {
    name: "추세 전환선 (SuperTrend)",
    badge: "이번 단계 미도입",
    desc: "신규 추세 전환 지표 — 후속 위험 신호 단계에서 검토.",
  },
];

function DevList({ items }: { items: DevItem[] }) {
  return (
    <ul className="tc-dev-list">
      {items.map((d) => (
        <li key={d.name}>
          {d.name}{" "}
          <span
            className={
              d.badge === "개발 중"
                ? "tc-badge tc-badge-dev"
                : "tc-badge tc-badge-off"
            }
          >
            {d.badge}
          </span>
          <p className="tc-muted tc-small">{d.desc}</p>
        </li>
      ))}
    </ul>
  );
}

function InDevelopmentSection() {
  return (
    <section className="tc-card" aria-label="개발 중인 판단 기능">
      <h2 className="tc-h2">개발 중인 판단 기능</h2>
      <p className="tc-muted tc-small" style={{ marginBottom: 12 }}>
        이번 화면에 넣기로 했으나 아직 없는 기능과, 이번 단계에서는 넣지 않기로 한
        기능을 모두 기록합니다. 값이 없어 숨긴 것이 아니라 앞으로 만들 목록입니다.
      </p>
      <div className="tc-label">준비 중 (앞으로 이 화면에 추가)</div>
      <DevList items={DEV_IN_PROGRESS} />
      <div className="tc-label tc-divider" style={{ paddingTop: 12 }}>
        이번 단계 미도입 (후속 단계·별도 설계)
      </div>
      <DevList items={DEV_NOT_IN_STEP} />
    </section>
  );
}

// ── 컨테이너 ─────────────────────────────────────────────────────────────────
export default function TodayInvestmentCheckView({ onNavigate }: Props) {
  // Dashboard 와 같은 조회 조건 → 같은 캐시 키 공유 (화면 왕복 재조회 방지).
  const market = useSharedQuery<MarketTopNResponse>(DASH_KEY_MARKET, () =>
    fetchMarketTopnLatest(10),
  );
  const holdings = useSharedQuery<EnrichedHoldingsResult>(DASH_KEY_HOLDINGS, () =>
    fetchEnrichedHoldings(),
  );
  const evidence = useSharedQuery<HoldingsMarketEvidenceResponse>(
    DASH_KEY_EVIDENCE,
    () => fetchHoldingsMarketEvidence(),
  );
  const nav = useSharedQuery<NavDiscountLatestResponse>(DASH_KEY_NAV, () =>
    fetchNavDiscountLatest(),
  );

  // 경량 갱신 상태 (Q7: 저장값 재조회 + holdings/market/refresh 까지만).
  const refreshing = useLightRefreshState();
  const onLightRefresh = useCallback(async () => {
    refreshing.setRunning();
    try {
      await refreshMarket(); // POST /holdings/market/refresh (Q7)
      // 완료 후 light 로 분류한 자료를 실제로 모두 재조회하고 그 결과를 기다린다
      // (r5 A-1 정정). Holdings·Evidence·NAV 세 소스 reloadAsync. 하나라도 실패하면
      // catch 로 "실패" · 모두 성공해야 "완료" (거짓 완료 금지 · B-1).
      await Promise.all([
        holdings.reloadAsync(),
        evidence.reloadAsync(),
        nav.reloadAsync(),
      ]);
      refreshing.setDone();
    } catch {
      refreshing.setFailed();
    }
  }, [refreshing, holdings, evidence, nav]);

  const maintLoading =
    holdings.phase === "loading" ||
    evidence.phase === "loading" ||
    nav.phase === "loading" ||
    market.phase === "loading";
  const maintenance = collectMaintenance(holdings, evidence, nav, market);

  return (
    <div className="tc-root">
      <header className="tc-header">
        <h1 className="tc-h1">오늘의 투자 점검</h1>
        {/* 부제 괄호 안내는 작은 글씨 (사용자 요청). */}
        <p className="tc-muted tc-subnote">
          코스피 현재 위치 · 오늘 내가 확인할 것 · 시스템이 처리할 자료를 한 화면에서
          구분합니다.
        </p>
      </header>

      {/* §4.1: 코스피 대표 영역은 최상단 전체 폭 (사용자 요청 "가로로 제일 길게").
          코스피 헤드라인 + 상세 지표를 위에 붙이고, 그 아래 판단 큐 + 정비 큐 2열. */}
      <KospiHeadline market={market} />
      <KospiDetailSection market={market} />

      <div className="tc-queue-grid">
        <JudgmentQueueSection
          market={market}
          holdings={holdings}
          evidence={evidence}
          onNavigate={onNavigate}
        />
        <MaintenanceQueueSection
          items={maintenance}
          loading={maintLoading}
          refreshing={refreshing.state}
          onLightRefresh={onLightRefresh}
          onNavigate={onNavigate}
        />
      </div>

      <InDevelopmentSection />
    </div>
  );
}

// 경량 갱신 상태 훅. done/failed 는 잠깐 보여준 뒤 자동으로 idle 로 복귀
// (완료/실패 문구가 화면에 계속 남지 않게 · 2026-07-31 정정).
type RefreshPhase = "idle" | "running" | "done" | "failed";
const REFRESH_FEEDBACK_MS = 3000;
function useLightRefreshState() {
  const [state, setState] = useState<RefreshPhase>("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clear = () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  };
  const autoIdle = () => {
    clear();
    timer.current = setTimeout(() => setState("idle"), REFRESH_FEEDBACK_MS);
  };
  useEffect(() => clear, []);
  return {
    state,
    setRunning: () => {
      clear();
      setState("running");
    },
    setDone: () => {
      setState("done");
      autoIdle();
    },
    setFailed: () => {
      setState("failed");
      autoIdle();
    },
  };
}
