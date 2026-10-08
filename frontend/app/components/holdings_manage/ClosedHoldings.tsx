"use client";

// POC5-05 개정 2 §2 · PLAN §2-8 — 「종목 관리」 아래 접힌 '과거 보유'(전량매도 · 입력 정정으로 끝난 종목 · 계좌).
// 줄마다 마지막 보유 기간(시작 또는 매수일 미상 ~ 종료) · 그 기간의 실현손익 · 수익률 ·
// [History] · [재매수](선택한 줄의 새 보유 기간). 과거 보유는 정기 시세 수집 · 알림 대상이 아니며,
// 이 목록은 조회를 하지 않는다(부모가 넘긴 History 조회 결과만 그린다). 0건이면 그리지 않는다.

import type { PositionHistory } from "@/lib/api";
import { pnlClass } from "./format";
import { pct, periodText, signedNum } from "./historyText";

interface Props {
  positions: PositionHistory[]; // is_open=false 만
  onHistory: (positionId: string) => void;
  onRebuy: (position: PositionHistory) => void;
}

export default function ClosedHoldings({ positions, onHistory, onRebuy }: Props) {
  if (positions.length === 0) return null;
  return (
    <details className="card hmx-closed">
      <summary>과거 보유 ({positions.length}) — 보유가 끝난 종목</summary>
      <div className="hmx-tbl-wrap">
        <table className="hmx-tbl">
          <thead>
            <tr>
              <th>종목</th>
              <th>계좌</th>
              <th>보유 기간</th>
              <th className="hmx-r">실현손익</th>
              <th className="hmx-r">수익률</th>
              <th aria-label="동작" />
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const last = p.cycles.length > 0 ? p.cycles[p.cycles.length - 1] : null;
              const label = `${p.name || p.ticker} · ${p.account_group}`;
              return (
                <tr key={p.position_id}>
                  <td>
                    {p.name || p.ticker}
                    {p.name ? <span className="muted hmx-small"> {p.ticker}</span> : null}
                  </td>
                  <td>{p.account_group}</td>
                  <td>
                    {last ? periodText(last) : "—"}
                    {last?.closed_by === "ADJUSTMENT" ? (
                      <span className="hmx-tag" style={{ marginLeft: 6 }}>
                        입력 정정으로 종료
                      </span>
                    ) : null}
                  </td>
                  <td className={`hmx-r ${last ? pnlClass(last.realized_pnl) : ""}`}>
                    {last ? signedNum(last.realized_pnl) : "—"}
                  </td>
                  <td className={`hmx-r ${last ? pnlClass(last.realized_rate) : ""}`}>
                    {last ? pct(last.realized_rate) : "—"}
                  </td>
                  <td>
                    <div className="hmx-row-actions">
                      <button
                        type="button"
                        className="hmx-btn-sm hmx-ghost"
                        aria-label={`${label} History`}
                        onClick={() => onHistory(p.position_id)}
                      >
                        History
                      </button>
                      <button
                        type="button"
                        className="hmx-btn-sm hmx-ghost"
                        aria-label={`${label} 재매수`}
                        onClick={() => onRebuy(p)}
                      >
                        재매수
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="muted hmx-small" style={{ margin: "8px 0 0" }}>
        과거 보유는 정기 시세 수집 · 알림 대상에 넣지 않습니다. 시장 흐름은 History 에서 직접 누를 때만
        계산합니다.
      </p>
    </details>
  );
}
