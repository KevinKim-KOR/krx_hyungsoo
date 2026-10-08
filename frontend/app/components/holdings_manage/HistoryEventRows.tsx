"use client";

// POC5-05 개정 2 §3 · §6 — History 표의 기록 줄(보유 기간 하나).
// 매수 · 매도 줄: 체결단가 · 매매대금 · 매도분 원가 · 실현손익 · 수익률(서버 Decimal 계산값 표시만) ·
// [정정](부모 매매 창 정정 모드) · [취소](화면 안 확인 뒤 저장). 기준잔고 · 잔고 등록 줄은 입력 평단을
// '(평단)' 으로 보이고 매매대금 · 손익을 만들지 않는다. 입력 정정 줄은 정정 전 → 정정 후만 보인다
// (매매 · 손익 0원 거래가 아님). 정정 전 입력은 그 줄 아래 펼침으로 보인다.

import type { HoldingCycleView, TradeEventView } from "@/lib/api";
import { pnlClass } from "./format";
import {
  adjustmentText,
  dash,
  eventLabel,
  eventWhen,
  firstBuyId,
  pct,
  recordBrief,
  savedAt,
  signedNum,
} from "./historyText";

export const HISTORY_COLS = 11;

export interface RowActions {
  confirmId: string | null; // 취소 확인 중인 기록
  voiding: boolean;
  voidError: string | null;
  onCorrect: (ev: TradeEventView) => void;
  onAskVoid: (ev: TradeEventView) => void;
  onConfirmVoid: () => void;
  onCancelVoid: () => void;
}

export function HistoryHeadRow() {
  return (
    <tr>
      <th>날짜</th>
      <th>구분</th>
      <th className="hmx-r">수량</th>
      <th className="hmx-r">체결단가</th>
      <th className="hmx-r">매매대금</th>
      <th className="hmx-r">매도분 원가</th>
      <th className="hmx-r">실현손익</th>
      <th className="hmx-r">수익률</th>
      <th className="hmx-r">잔량 · 평단</th>
      <th>메모</th>
      <th aria-label="동작" />
    </tr>
  );
}

export default function HistoryEventRows({
  cycle,
  actions,
}: {
  cycle: HoldingCycleView;
  actions: RowActions;
}) {
  const first = firstBuyId(cycle);
  return (
    <>
      {cycle.events.map((ev) => (
        <EventRow key={ev.record_id} ev={ev} label={eventLabel(ev, first)} actions={actions} />
      ))}
    </>
  );
}

function EventRow({
  ev,
  label,
  actions,
}: {
  ev: TradeEventView;
  label: string;
  actions: RowActions;
}) {
  const p = ev.payload;
  const trade = ev.kind === "BUY" || ev.kind === "SELL";
  const anchor = ev.kind === "BASELINE" || ev.kind === "REGISTER";
  const when = eventWhen(ev);
  const memo = typeof p.memo === "string" && p.memo ? p.memo : null;
  const left = `${dash(ev.q_after, 6)}${ev.avg_after ? ` · ${dash(ev.avg_after)}` : ""}`;
  const busy = actions.voiding;
  return (
    <>
      <tr>
        <td className={anchor ? "muted" : undefined}>{when}</td>
        <td>{label}</td>
        {ev.kind === "ADJUSTMENT" ? (
          <td colSpan={6} className="hmx-small">
            {adjustmentText(p)}
          </td>
        ) : (
          <>
            <td className="hmx-r">{dash(p.quantity, 6)}</td>
            <td className={anchor ? "hmx-r muted" : "hmx-r"}>
              {anchor ? `${dash(p.avg_buy_price)} (평단)` : dash(p.price)}
            </td>
            <td className="hmx-r">{trade ? dash(p.amount) : "—"}</td>
            <td className="hmx-r">{dash(ev.cost_of_sold)}</td>
            <td className={`hmx-r ${pnlClass(ev.realized_pnl)}`}>{signedNum(ev.realized_pnl)}</td>
            <td className={`hmx-r ${pnlClass(ev.realized_rate)}`}>{pct(ev.realized_rate)}</td>
          </>
        )}
        <td className="hmx-r">{left}</td>
        <td
          title={memo ?? undefined}
          style={{ maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis" }}
        >
          {memo ?? ""}
        </td>
        <td>
          {trade ? (
            <div className="hmx-row-actions">
              <button
                type="button"
                className="hmx-btn-sm hmx-ghost"
                aria-label={`${when} ${label} 정정`}
                disabled={busy}
                onClick={() => actions.onCorrect(ev)}
              >
                정정
              </button>
              <button
                type="button"
                className="hmx-btn-sm hmx-ghost"
                aria-label={`${when} ${label} 취소`}
                disabled={busy}
                onClick={() => actions.onAskVoid(ev)}
              >
                취소
              </button>
            </div>
          ) : null}
        </td>
      </tr>
      {ev.previous.length > 0 ? (
        <tr>
          <td colSpan={HISTORY_COLS} style={{ whiteSpace: "normal" }}>
            <details>
              <summary className="hmx-small" style={{ color: "var(--accent)", cursor: "pointer" }}>
                정정 전 입력 {ev.previous.length}건
              </summary>
              <ul className="hmx-small muted" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {ev.previous.map((r) => (
                  <li key={r.record_id}>
                    이전 입력: {recordBrief(r)} · {savedAt(r.recorded_at)} 저장
                  </li>
                ))}
              </ul>
            </details>
          </td>
        </tr>
      ) : null}
      {actions.confirmId === ev.record_id ? (
        <tr>
          <td colSpan={HISTORY_COLS} style={{ whiteSpace: "normal" }}>
            <div className="hmx-row-actions" style={{ alignItems: "center", flexWrap: "wrap" }}>
              <span>이 기록을 취소할까요?</span>
              <button
                type="button"
                className="hmx-btn-sm"
                disabled={busy}
                onClick={actions.onConfirmVoid}
              >
                {busy ? "취소 저장 중…" : "취소 확정"}
              </button>
              <button
                type="button"
                className="hmx-btn-sm hmx-ghost"
                disabled={busy}
                onClick={actions.onCancelVoid}
              >
                그대로 두기
              </button>
            </div>
            {actions.voidError ? (
              <div className="hmx-error" role="alert">
                {actions.voidError}
              </div>
            ) : null}
          </td>
        </tr>
      ) : null}
    </>
  );
}
