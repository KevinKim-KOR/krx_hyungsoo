"use client";

// POC5-05 개정 2 §2 · §3 · §8 — History 창의 보유 기간(cycle) 하나.
// 머리: 보유 중 · 시작 / 지난 보유 기간 · 시작 ~ 종료(매수일 미상 표시) · 기준잔고 · 잔고 등록 · 입력
// 정정 포함(참고 계산) 표시. 표: 기록 줄(HistoryEventRows). 요약: 보유 중 = 잔량 · 평단 · 남은 원가 ·
// 미실현(부모가 넘긴 「보유 현황」과 같은 /holdings/enriched 값 · 없으면 '—') · 누적 실현 /
// 종료 = 매도분 원가 합계 · 기간 실현손익 · 기간 수익률. [시장 흐름 보기]는 누를 때만 조회한다
// (한 번 펼친 뒤 접어도 다시 부르지 않는다).

import { useState } from "react";
import type { HoldingCycleView } from "@/lib/api";
import { fmtNum, fmtWon, pnlClass } from "./format";
import HistoryEventRows, { HISTORY_COLS, HistoryHeadRow, type RowActions } from "./HistoryEventRows";
import MarketFlowPanel from "./MarketFlowPanel";
import { dash, pct, savedAt, signedWon } from "./historyText";

export interface PriceInfo {
  current_price: number | null;
  pnl_amount: number | null;
  pnl_rate_pct: number | null;
}

interface Props {
  positionId: string;
  cycle: HoldingCycleView;
  priceInfo: PriceInfo | null; // 보유 중 기간에만 넘긴다
  actions: RowActions;
}

function Cell({ k, v, cls }: { k: string; v: string; cls?: string }) {
  return (
    <div>
      <span className="hmx-k">{k}</span>
      <span className={cls ? `hmx-v ${cls}` : "hmx-v"}>{v}</span>
    </div>
  );
}

function CycleTags({ cycle }: { cycle: HoldingCycleView }) {
  const anchor = cycle.events.find((e) => e.kind === "BASELINE" || e.kind === "REGISTER") ?? null;
  return (
    <span className="hmx-row-actions" style={{ flexWrap: "wrap" }}>
      {cycle.opened_by === "BASELINE" ? (
        <span className="hmx-tag">기준잔고 · 매수일 미상 · 입력 평단 기준</span>
      ) : null}
      {cycle.opened_by === "REGISTER" ? <span className="hmx-tag">잔고 등록 · 매수일 미상</span> : null}
      {anchor ? (
        <span className="hmx-tag">
          {anchor.recorded_at ? `${savedAt(anchor.recorded_at).slice(0, 10)} 기록 시작` : "기록 시작 전"}
        </span>
      ) : null}
      {cycle.has_adjustment ? (
        <span className="hmx-tag hmx-tag-warn">입력 정정 포함 · 참고 계산</span>
      ) : null}
    </span>
  );
}

function CycleSummary({ cycle, priceInfo }: { cycle: HoldingCycleView; priceInfo: PriceInfo | null }) {
  if (cycle.status === "OPEN") {
    const cur = priceInfo?.current_price ?? null;
    const pnl = priceInfo?.pnl_amount ?? null;
    const avg = cycle.avg_buy_price ? fmtWon(cycle.avg_buy_price) : "—";
    const rate = cycle.realized_rate !== null ? ` · ${pct(cycle.realized_rate)}` : "";
    return (
      <div className="hmx-sum">
        <Cell k="잔량 · 평단" v={`${dash(cycle.quantity, 6)}주 · ${avg}`} />
        <Cell k="남은 원가" v={fmtWon(cycle.cost)} />
        <Cell
          k={cur !== null ? `미실현 (현재가 ${fmtNum(cur)})` : "미실현"}
          v={pnl !== null ? `${signedWon(pnl)} · ${pct(priceInfo?.pnl_rate_pct)}` : "—"}
          cls={pnl !== null ? pnlClass(pnl) : undefined}
        />
        <Cell k="누적 실현" v={`${signedWon(cycle.realized_pnl)}${rate}`} cls={pnlClass(cycle.realized_pnl)} />
      </div>
    );
  }
  return (
    <div className="hmx-sum">
      <Cell k="매도분 원가 합계" v={fmtWon(cycle.sold_cost)} />
      <Cell k="기간 실현손익" v={signedWon(cycle.realized_pnl)} cls={pnlClass(cycle.realized_pnl)} />
      <Cell k="기간 수익률" v={pct(cycle.realized_rate)} cls={pnlClass(cycle.realized_rate)} />
      {cycle.closed_by === "ADJUSTMENT" ? <Cell k="종료" v="입력 정정으로 종료" /> : null}
    </div>
  );
}

export default function HistoryCycle({ positionId, cycle, priceInfo, actions }: Props) {
  const [flowShown, setFlowShown] = useState(false);
  const [flowLoaded, setFlowLoaded] = useState(false);
  const open = cycle.status === "OPEN";
  const start = cycle.start_date ?? "매수일 미상";
  const head = open ? `보유 중 · ${start}` : `지난 보유 기간 · ${start} ~ ${cycle.end_date ?? "—"}`;
  const hasTrades = cycle.events.some((e) => e.kind === "BUY" || e.kind === "SELL");
  return (
    <section className="hmx-cycle" aria-label={head}>
      <div className="hmx-cycle-head">
        <b>{head}</b>
        <CycleTags cycle={cycle} />
      </div>
      <div className="hmx-tbl-wrap">
        <table className="hmx-tbl">
          <thead>
            <HistoryHeadRow />
          </thead>
          <tbody>
            <HistoryEventRows cycle={cycle} actions={actions} />
            {open && !hasTrades ? (
              <tr>
                <td colSpan={HISTORY_COLS} className="muted hmx-small">
                  기록 시작 뒤 매매 없음 — [매매]로 입력하면 여기에 쌓입니다.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
      <CycleSummary cycle={cycle} priceInfo={priceInfo} />
      {hasTrades ? (
        <>
          <div className="hmx-row-actions" style={{ marginTop: 10 }}>
            <button
              type="button"
              className="hmx-btn-sm hmx-ghost"
              aria-expanded={flowShown}
              onClick={() => {
                setFlowShown((v) => !v);
                setFlowLoaded(true);
              }}
            >
              {flowShown ? "시장 흐름 접기" : "시장 흐름 보기"}
            </button>
          </div>
          {flowLoaded ? (
            <div hidden={!flowShown}>
              <MarketFlowPanel positionId={positionId} cycleId={cycle.cycle_id} />
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
