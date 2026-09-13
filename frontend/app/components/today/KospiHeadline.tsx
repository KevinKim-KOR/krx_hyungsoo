"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. **JSX·문구·className·핸들러·호출 조건을 고치지 않았다** —
// 바뀐 것은 파일 배치와 import/export 줄뿐이다.

import type { QueryState } from "@/lib/api/queryCache";
import type { MarketTopNResponse } from "@/lib/api";
import KospiChart from "./KospiChart";
import {
  fmtKstDate,
  fmtPct,
  maDistanceText,
  regimeLabelKo,
} from "./todayHelpers";

// ── §4.1 코스피 대표 (헤드라인) — 첫 화면 필수 요소만 compact ────────────────
// 코스피 차트 + [별도] 기존 시장 판정(KODEX200 기준) + KODEX200 MA 거리.
// 코스피와 KODEX200 을 하나로 묶지 않는다 (§3.1 강제 분리 · FAIL 조건).
export default function KospiHeadline({ market }: { market: QueryState<MarketTopNResponse> }) {
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
