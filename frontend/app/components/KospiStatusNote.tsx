"use client";

// POC3-02D-OPS-02 3-4 — KOSPI 최신성 상태 표시 (설계자 확정 2026-09-28).
//
// 「오늘의 투자 점검」 KOSPI 카드와 「요즘 잘 오르는 ETF」 시장 배경 카드가 **같은**
// 판정·문구를 쓴다(설계자: "두 화면은 같은 상태 판정·문구 생성기를 공유").
// POC3-02D-OPS-03 설계자 RESULT STEP 5 — 판정 · 문구 생성기는 `lib/kospiStatus.ts` 에
// 있다. 이 파일은 그 결과를 그리는 React 컴포넌트만 둔다(lib → 컴포넌트 방향 금지).

import type { MarketContextKospi } from "@/lib/api";
import { kospiStatusView, type KospiQueryPhase } from "@/lib/kospiStatus";

/** 제목 옆 배지. 정상 · 로딩이면 아무것도 그리지 않는다. */
export function KospiStatusBadges({
  kospi,
  phase,
}: {
  kospi: MarketContextKospi | null | undefined;
  phase?: KospiQueryPhase;
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
  phase?: KospiQueryPhase;
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
