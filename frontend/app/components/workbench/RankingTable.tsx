"use client";

// POC6-29(PLAN §2-5 · 판정 Q4-1 · Q9) — 「후보리스트」 [표] 보기.
// 행을 펼치기 전에도 수치가 보이게, 지금 보는 쪽(상위 또는 하위)의 상세를 한 번에 묶어 읽는다(선정 순서 목록 =
// 같은 조회 키 · 정렬을 바꿔도 다시 읽지 않음). 칸 값 · 단위 · 날짜는 행 상세와 같은 응답이다.
// 날짜가 다른 값 · 값 없음은 칸에 짧게 적고, 행을 누르면 그 아래에 행 상세(실제 날짜 · 상태)가 열린다.

import { Fragment, useState } from "react";
import type { CompareRow, CompareSummaryOk } from "@/lib/api/etfCompare";
import type { DetailPeriod, EtfDetailItem } from "@/lib/api/etfDetail";
import { BASIS_LABEL, pct } from "@/lib/etfCompare";
import type { MenuKey } from "../LeftSidebar";
import { detailOf, detailStateText, useEtfDetail } from "./DetailNumbers";
import EtfRowDetail from "./EtfRowDetail";
import { directionColor } from "./helpers";

function cell(p: DetailPeriod | undefined) {
  if (!p) return <span className="ec-small">—</span>;
  if (p.status === "ok") return <span style={{ color: directionColor(p.value) }}>{pct(p.value)}</span>;
  return <span className="ec-small">{p.status === "period_differs" ? "기간 다름" : "값 없음"}</span>;
}

function won(v: number | null | undefined): string {
  return v == null ? "—" : Math.round(v).toLocaleString("ko-KR");
}

function navCells(it: EtfDetailItem | null) {
  if (!it) return [<td key="m">—</td>, <td key="n">—</td>, <td key="d">—</td>];
  const n = it.nav;
  if (n.status !== "ok") {
    const t = n.status === "not_applicable" ? "해당 없음" : "자료 없음";
    return [<td key="m" className="ec-small">{t}</td>, <td key="n" className="ec-small">{t}</td>, <td key="d" className="ec-small">{t}</td>];
  }
  return [
    <td key="m">{won(n.market_price)}</td>,
    <td key="n">{won(n.nav)}</td>,
    <td key="d" style={{ color: directionColor(n.discount_rate_pct) }}>
      {pct(n.discount_rate_pct)}
    </td>,
  ];
}

export default function RankingTable({
  s,
  side,
  rows,
  onNavigate,
}: {
  s: CompareSummaryOk;
  side: "top" | "bottom";
  rows: CompareRow[];
  onNavigate?: (key: MenuKey) => void;
}) {
  const base = side === "top" ? s.top : s.bottom;
  const detail = useEtfDetail(base.map((r) => r.ticker));
  const [open, setOpen] = useState<string | null>(null);
  const state = detailStateText(detail, base[0]?.ticker ?? "");
  const kodex = detail.phase === "success" && detail.data.status === "ok" ? detail.data.kodex200.window20 : null;
  return (
    <div className="ec-table-wrap" data-testid="ec-rank-table">
      {state && <div className="ec-small">{state}</div>}
      <table className="ec-table">
        <thead>
          <tr>
            <th>순위</th>
            <th>ETF</th>
            <th>선정({BASIS_LABEL[s.basis]})</th>
            <th>1개월</th>
            <th>3개월</th>
            <th>6개월</th>
            <th>12개월</th>
            <th>20구간 KODEX 200 차이</th>
            <th>시장가</th>
            <th>기준가(NAV)</th>
            <th>괴리율</th>
            <th>최근 고점 대비</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const it = detailOf(detail, r.ticker);
            const ex = it?.excess20;
            const isOpen = open === r.ticker;
            return (
              <Fragment key={r.ticker}>
                <tr
                  className={isOpen ? "sel" : undefined}
                  role="button"
                  tabIndex={0}
                  aria-expanded={isOpen}
                  data-testid="ec-table-row"
                  onClick={() => setOpen(isOpen ? null : r.ticker)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      setOpen(isOpen ? null : r.ticker);
                    }
                  }}
                >
                  <td>
                    {side === "top" ? "상위" : "하위"} {r.rank}
                  </td>
                  <td>{r.name ?? r.ticker}</td>
                  <td style={{ color: directionColor(r.basis_return.value), fontWeight: 600 }}>{pct(r.basis_return.value)}</td>
                  <td>{cell(it?.m1)}</td>
                  <td>{cell(it?.m3)}</td>
                  <td>{cell(it?.m6)}</td>
                  <td>{cell(it?.m12)}</td>
                  <td>
                    {!ex ? (
                      "—"
                    ) : ex.status === "ok" ? (
                      <span style={{ color: directionColor(ex.value_pctp) }}>{pct(ex.value_pctp, "%p")}</span>
                    ) : (
                      <span className="ec-small">{ex.status === "period_differs" ? "기간 다름" : "값 없음"}</span>
                    )}
                  </td>
                  {navCells(it)}
                  <td>{cell(it?.drawdown ? { ...it.drawdown, start_close: null, end_close: it.drawdown.close } : undefined)}</td>
                </tr>
                {isOpen && (
                  <tr>
                    <td colSpan={12}>
                      <EtfRowDetail row={r} s={s} side={side} screen="candidate_list" onNavigate={onNavigate} />
                    </td>
                  </tr>
                )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
      <div className="ec-small" data-testid="ec-table-dates">
        날짜: 각 칸은 같은 공통 끝일까지(1 · 3 · 6 · 12개월 = 끝일 30 · 90 · 180 · 365일 전 이후 첫 저장일부터) · 20구간 =
        저장 행 20구간{kodex?.start ? `(KODEX 200 ${kodex.start} → ${kodex.end})` : ""} · 시장가 · 기준가 · 괴리율 = 그 종목의 마지막
        기준가 자료일 · 날짜가 다른 값은 행을 눌러 실제 날짜와 상태를 확인하세요.
      </div>
    </div>
  );
}
