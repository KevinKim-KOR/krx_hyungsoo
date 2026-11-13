"use client";

// POC3-01 오늘의 투자 점검 — 코스피 가격 흐름 차트 (설계서 §4.1).
//
// 저장된 KOSPI close 시계열(market_benchmark_daily_price)만 SVG 선으로 그린다.
// - NO_DATA/UNAVAILABLE 은 빈 정상 차트로 위장하지 않고 사유 표시.
// - BUY/SELL 마커·예측선·목표가 없음. KOSPI 지수 거래량은 미저장이라 이 차트에 없음(§4.1 Q5) ·
//   KODEX200 거래량은 KospiHeadline 의 'KODEX200 거래량' 칸(POC5-09).
// - 최상단 대표 정보 — 장식 배경이 아니라 흐름을 읽을 수 있는 크기(§4.1 차트 구성).
// - POC3-02D-OPS-03 확정 계약 9 ⑥ — 차트도 KOSPI 카드와 **같은 판정**을 쓴다(PLAN STEP 5-5). 판정은 부모가
//   이미 받은 `/market/topn/latest` 의 KOSPI 필드(`display_state`)다 — 차트가 따로 조회 · 계산하지 않는다(KS-1).
//   정상이 아니면 선을 경고색으로 그려 낡은 값을 정상처럼 보이지 않게 한다. 같은 배지 · 기준 줄은 차트 아래에
//   두지 않는다 — 이 차트는 코스피 공식 종가 구역(KospiCloseBlock) 머리 줄 바로 아래에만 쓰이고, 머리 줄이 기준일 ·
//   배지를 이미 보인다(형수님 결정 2026-11-14 · POC6-29-1 결과서 §4-1).

import { useSharedQuery } from "@/lib/api/queryCache";
import {
  fetchBenchmarkSeries,
  type MarketContextKospi,
  type PriceSeriesResponse,
} from "@/lib/api";
import { kospiStatusView, type KospiQueryPhase } from "@/lib/kospiStatus";
import ReadableLineChart from "../charts/ReadableLineChart";

export const KOSPI_SERIES_KEY = "today:price-series?benchmark=KOSPI";

// 최근 N개 저장값만 표시 (전체 12년 시계열은 대표 차트에서 흐름 판독을 흐린다).
// 기간은 차트 날짜 눈금 · 고른 날 줄로 읽는다(아래 설명 줄은 2026-11-14 형수님 결정으로 뺌).
const RECENT_DAYS = 120;

export default function KospiChart({
  kospi,
  phase,
}: {
  kospi?: MarketContextKospi | null;
  phase?: KospiQueryPhase;
} = {}) {
  const q = useSharedQuery<PriceSeriesResponse>(KOSPI_SERIES_KEY, () =>
    fetchBenchmarkSeries("KOSPI"),
  );
  // 부모가 KOSPI 판정을 넘기지 않으면(옛 호출) 상태 표시 없이 예전처럼 그린다.
  const status = phase === undefined ? null : kospiStatusView(kospi, phase);
  const flagged =
    status !== null && !status.loading && status.state !== "ok" && status.state !== "holiday";

  if (q.phase === "loading") {
    return <p className="tc-muted tc-small">코스피 가격 흐름 불러오는 중...</p>;
  }
  if (q.phase === "error") {
    return <p className="tc-danger tc-small">코스피 가격 흐름 확인 불가 (조회 실패)</p>;
  }
  if (q.phase === "idle") {
    return null;
  }

  const data = q.data;
  if (data.availability !== "AVAILABLE" || data.series.length === 0) {
    const label =
      data.availability === "NO_DATA"
        ? "저장된 코스피 가격 자료 없음"
        : "코스피 가격 확인 불가";
    return (
      <div className="tc-small">
        <span className="tc-warn" style={{ fontWeight: 600 }}>
          {label}
        </span>
      </div>
    );
  }

  const recent = data.series.slice(-RECENT_DAYS);

  return (
    <div>
      {/* POC5-19 개정(차트 읽기 · 2026-10-17) — 날짜 · pt 눈금 · 가로선 · 고른 날의 코스피 값 줄. */}
      <ReadableLineChart
        points={recent}
        unit="pt"
        valueLabel="코스피"
        label="코스피 일별 가격 흐름"
        height={220}
        warn={q.stale || flagged}
        testId="kospi-chart"
      />
      {/* 형수님 결정(2026-11-14 · POC6-29 운영 화면 · POC6-29-1 결과서 §4-1): 그래프 아래 두 줄(기간 · 저장일 수 · 최종값 /
          상태 배지 · 기준일 · N거래일 지연)은 바로 위 코스피 공식 종가 머리 줄(큰 숫자 · 기준일 · 배지)과 겹쳐 뺐다.
          지연 · 수집 사유는 자료 상태(아침 요약 [자료 상태 보기] · 「자료 최신화 필요」)에서 본다(설계자 지시 2026-11-14 ·
          POC6-29-1 결과서 §5). 다시 읽기 실패로 이전 값을
          그릴 때만 아래 경고 한 줄을 둔다(낡은 차트를 새 값처럼 보이지 않게). */}
      {q.stale ? (
        <div className="tc-small tc-warn" style={{ marginTop: 6 }} data-testid="kospi-chart-stale">
          ⚠ 이전 조회값 (재조회 실패)
        </div>
      ) : null}
    </div>
  );
}
