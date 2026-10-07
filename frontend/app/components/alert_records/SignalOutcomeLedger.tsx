"use client";

// POC5-03 — 접기 영역 `신호 결과 원장`. 펼쳤을 때만 목록에 보이는 알림의 상세를 읽어
// 평가 가능한(evaluable) item 의 당시 상태 · t0 · 처리와 +1/+5/+20 원시 결과를 보인다.
// 평가(feedback) 여부와 무관하게 결과를 보인다(설계 개정 2 §5 · 평가 조건 폐기).
// 접기 · 지연 조회는 가독성을 위한 것이며 조건이 아니다.

import { useEffect, useState } from "react";
import {
  fetchLedgerAlertDetail,
  type LedgerAlertCard,
  type LedgerAlertDetail,
} from "@/lib/api";
import {
  HORIZONS,
  NOT_TARGET,
  PENDING,
  PUSH_KIND_SHORT,
  dispositionLabel,
  fmtPrice,
  outcomeCell,
  subjectName,
} from "./format";

interface Row {
  key: string;
  time: string;
  kind: string;
  target: string;
  state: string;
  disposition: string;
  t0: string;
  cells: string[] | null; // null = 결과 대상 아님(세 칸 합침)
}

function buildRows(details: LedgerAlertDetail[]): Row[] {
  const rows: Row[] = [];
  for (const d of details) {
    for (const item of d.items.filter((i) => i.evaluable)) {
      const label = subjectName(item) + (d.off_schedule ? " (예정 외 실행)" : "");
      const base = {
        time: d.time_kst ?? "—",
        kind: PUSH_KIND_SHORT[d.push_kind] ?? d.push_kind,
        state: item.state_label ?? "—",
        disposition: dispositionLabel(item.disposition),
        t0: fmtPrice(item.t0_price),
      };
      const key = `${d.event_id}:${item.item_seq}`;
      if (!item.outcome_target) {
        rows.push({ ...base, key, target: label, cells: null });
        continue;
      }
      const outs = d.outcomes.filter((o) => o.item_seq === item.item_seq);
      const series = Array.from(new Set(outs.map((o) => o.series_id)));
      if (series.length === 0) {
        rows.push({ ...base, key, target: label, cells: HORIZONS.map(() => PENDING) });
        continue;
      }
      for (const s of series) {
        const own = outs.filter((o) => o.series_id === s);
        const code = s.slice(s.indexOf(":") + 1);
        const seriesName = own[0].series_name;
        const target = code === item.subject_id ? label : `${label} · ${seriesName}`;
        rows.push({
          ...base,
          key: `${key}:${s}`,
          target,
          cells: HORIZONS.map((h) => outcomeCell(own.find((o) => o.horizon === h))),
        });
      }
    }
  }
  return rows;
}

interface Props {
  alerts: LedgerAlertCard[];
  // 목록을 다시 읽을 때마다(원장 새로고침 · 평가 저장) 바뀐다 — 알림 ID · 평가 수가 같아도
  // 새로 성숙한 결과가 있을 수 있어 펼친 상태면 다시 읽는다.
  refreshKey: number;
}

export default function SignalOutcomeLedger({ alerts, refreshKey }: Props) {
  const [open, setOpen] = useState(false);
  const [details, setDetails] = useState<LedgerAlertDetail[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  // 목록(날짜 · 종류 · 평가 저장)이나 refreshKey 가 바뀌면 펼친 상태에서 다시 읽는다.
  const idsKey = alerts.map((a) => `${a.event_id}#${a.feedback_count}`).join(",");

  useEffect(() => {
    if (!open) return;
    let alive = true;
    const ids = idsKey ? idsKey.split(",").map((x) => x.split("#")[0]) : [];
    setDetails(null);
    setError(null);
    Promise.all(ids.map((id) => fetchLedgerAlertDetail(id)))
      .then((ds) => {
        if (alive) setDetails(ds);
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [open, idsKey, refreshKey]);

  const rows = details ? buildRows(details) : [];
  return (
    <details
      className="ar-ledger"
      onToggle={(e) => setOpen((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary>신호 결과 원장</summary>
      <p className="ar-note">
        이 날짜 · 종류 알림에서 평가 가능한 항목입니다. 수익률은 종가 원시값이며 성공 ·
        실패를 뜻하지 않습니다. 평가 여부와 관계없이 보입니다.
      </p>
      {error ? <div className="message error">결과를 불러오지 못했습니다 — {error}</div> : null}
      {open && !details && !error ? <div className="ar-note">불러오는 중...</div> : null}
      {details && rows.length === 0 ? (
        <div className="ar-note">이 날짜에 평가 가능한 항목이 없습니다</div>
      ) : null}
      {rows.length > 0 ? (
        <div className="ar-table-wrap">
          <table className="ar-table">
            <thead>
              <tr>
                <th>시각</th>
                <th>종류</th>
                <th>대상</th>
                <th>당시 상태</th>
                <th>처리</th>
                <th>t0</th>
                {HORIZONS.map((h) => (
                  <th key={h}>+{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.key}>
                  <td>{r.time}</td>
                  <td>{r.kind}</td>
                  <td>{r.target}</td>
                  <td>{r.state}</td>
                  <td>{r.disposition}</td>
                  <td className="ar-num">{r.t0}</td>
                  {r.cells === null ? (
                    <td className="ar-fact" colSpan={HORIZONS.length}>
                      {NOT_TARGET}
                    </td>
                  ) : (
                    r.cells.map((c, i) => (
                      <td key={i} className={c.endsWith("%") ? "ar-num" : "ar-fact"}>
                        {c}
                      </td>
                    ))
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </details>
  );
}
