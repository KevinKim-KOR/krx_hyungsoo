"use client";

// POC3-02D-OPS-02 3-4 — KOSPI 최신성 상태 표시 (설계자 확정 2026-09-28 · 사용자 전달).
//
// 「오늘의 투자 점검」 KOSPI 카드와 「요즘 잘 오르는 ETF」 시장 배경 카드가 **같은**
// 판정·문구를 쓴다(설계자: "두 화면은 같은 상태 판정·문구 생성기를 공유").
// 판정(`display_state`)과 거래일 지연(`trading_day_lag`)은 백엔드가 준다 — C7 공용
// 거래일 계산(`app/trading_day_lag.py`). 화면은 지연을 계산하지 않는다(설계자 Q6).
// 기술 토큰(`source_stale` 등)·예외 원문은 화면에 내지 않는다.

import type { MarketContextKospi, KospiDisplayState } from "@/lib/api";

type QueryPhase = "idle" | "loading" | "success" | "error";

type NonOk = Exclude<KospiDisplayState, "ok">;

// 설계자 확정 배지 문구 (Q5 · 2026-09-28).
const BADGE: Record<NonOk, string> = {
  stale: "기준일 지연",
  source_failed: "자료원 확인 실패",
  no_result: "수집 결과 없음",
  not_evaluated: "아직 평가되지 않음",
  holiday: "휴장일",
};

// 설계자 확정 사유 문장 — 정상일에는 숨기고 그 밖의 상태에서만 한 줄.
const REASON: Record<NonOk, string> = {
  stale: "KOSPI 원자료가 최근 거래일까지 갱신되지 않았습니다.",
  source_failed: "KOSPI 원자료를 불러오지 못했습니다.",
  no_result: "저장된 KOSPI 자료가 없습니다.",
  not_evaluated: "KOSPI 최신성 판정이 아직 실행되지 않았습니다.",
  holiday: "오늘은 국내 증시 휴장일입니다.",
};

// 설계자 RESULT M1 (2026-09-28) — 같은 `수집 결과 없음` 배지에서 사유를 나눈다.
//   KOSPI 행 자체가 없음(기준일 없음)       → REASON.no_result
//   기준일은 있으나 수익률 산출값이 없음     → 아래 문장
// `no_result` 에서 기준일이 있으면 수익률 값은 늘 없다 — 백엔드는 운영 판정이 `ok` 일
// 때만 값을 주고, 기준일이 있는 `no_result` 는 그 판정이 `ok` 가 아닌 경우다(이력 부족 등).
const NO_RESULT_WITH_AS_OF = "KOSPI 수익률을 계산할 자료가 충분하지 않습니다.";

// 지연 거래일 수를 붙이는 상태 — 정상 · 휴장일 자료는 지연으로 경고하지 않는다.
const SHOWS_LAG: ReadonlySet<KospiDisplayState> = new Set(["stale", "source_failed"]);

export type KospiBadge = { text: string; tone: "warn" | "neutral" };

export type KospiStatusView =
  | { loading: true }
  | {
      loading: false;
      state: KospiDisplayState;
      badges: KospiBadge[];
      basisLine: string | null;
      reason: string | null;
    };

// 백엔드가 `display_state` 를 주지 않은 응답(이 변경 전 서버)은 기존 `status` 로만
// 고른다. 지연 거래일 수는 만들지 않는다(화면 계산 금지).
function fallbackState(kospi: MarketContextKospi): KospiDisplayState {
  if (kospi.status === "ok") return "ok";
  if (kospi.status === "stale") return "stale";
  return "no_result";
}

/** 두 화면 공용 — 상태 · 배지 · 기준 줄 · 사유 줄. */
export function kospiStatusView(
  kospi: MarketContextKospi | null | undefined,
  phase: QueryPhase = "success",
): KospiStatusView {
  // 화면 요청 진행 중은 배지가 아니라 로딩 표시다('아직 평가되지 않음'과 합치지 않는다).
  if (phase === "loading" || phase === "idle") return { loading: true };
  if (phase === "error" || !kospi) {
    return {
      loading: false,
      state: "source_failed",
      badges: [{ text: BADGE.source_failed, tone: "warn" }],
      basisLine: null,
      reason: REASON.source_failed,
    };
  }
  const state = kospi.display_state ?? fallbackState(kospi);
  const badges: KospiBadge[] = [];
  if (state === "holiday") {
    badges.push({ text: BADGE.holiday, tone: "neutral" });
  } else if (state !== "ok") {
    badges.push({ text: BADGE[state], tone: "warn" });
    // 휴장일에 다른 상태가 겹치면 중립 '휴장일' 배지를 함께 단다.
    if (kospi.today_is_trading_day === false) {
      badges.push({ text: BADGE.holiday, tone: "neutral" });
    }
  }
  const asOf = kospi.as_of_date ?? null;
  const lag = kospi.trading_day_lag;
  let basisLine: string | null = null;
  if (asOf) {
    basisLine = `KOSPI 기준일 ${asOf}`;
    if (SHOWS_LAG.has(state) && typeof lag === "number" && lag > 0) {
      basisLine += ` · ${lag}거래일 지연`;
    }
  }
  return {
    loading: false,
    state,
    badges,
    basisLine,
    reason:
      state === "ok"
        ? null
        : state === "no_result" && asOf
          ? NO_RESULT_WITH_AS_OF
          : REASON[state],
  };
}

/** 제목 옆 배지. 정상 · 로딩이면 아무것도 그리지 않는다. */
export function KospiStatusBadges({
  kospi,
  phase,
}: {
  kospi: MarketContextKospi | null | undefined;
  phase?: QueryPhase;
}) {
  const v = kospiStatusView(kospi, phase);
  if (v.loading || v.badges.length === 0) return null;
  return (
    <>
      {v.badges.map((b) => (
        <span key={b.text} className={`kospi-badge ${b.tone}`}>
          {b.text}
        </span>
      ))}
    </>
  );
}

/** 기준 줄 + 사유 줄. 로딩이면 '확인 중'. */
export function KospiStatusLines({
  kospi,
  phase,
}: {
  kospi: MarketContextKospi | null | undefined;
  phase?: QueryPhase;
}) {
  const v = kospiStatusView(kospi, phase);
  if (v.loading) return <div className="kospi-status-loading">확인 중</div>;
  if (!v.basisLine && !v.reason) return null;
  return (
    <div className="kospi-status" data-kospi-state={v.state}>
      {v.basisLine ? <div className="kospi-status-basis">{v.basisLine}</div> : null}
      {v.reason ? <div className="kospi-status-reason">{v.reason}</div> : null}
    </div>
  );
}
