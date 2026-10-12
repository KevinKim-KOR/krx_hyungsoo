"use client";

// POC5-08 — 알림 상세 안 「사후평가 — 가격 결과 · 과거 검증(+5)」(설계 §8 · 사용자 확인 목업 2026-10-11).
//
// 최신 산출물에서 이 알림의 항목 · 계열 결과만 읽는다(GET · 학습 0). 항목 · 계열마다 한 줄 —
// 여러 항목인 알림에 '알림 전체 점수'를 만들지 않는다. 내 평가는 기존 「내 평가」 칸에 따로 둔다.

import { useEffect, useState } from "react";
import {
  fetchRetrospectiveLatest,
  type LedgerItem,
  type LedgerOutcomeRow,
  type RetroItem,
  type RetroResult,
  type RetroSlot,
} from "@/lib/api";
import { fmtPp } from "./RetroSummary";
import { HORIZONS, fmtPrice, fmtReturn, subjectName } from "./format";

interface Row {
  key: string;
  label: string;
  cells: (RetroSlot | null)[]; // +1 · +5 · +20
}

// 결과 행이 있는 계열마다 한 줄 · 결과가 아직 없는 칸(계열 미기록)은 앞 줄부터 채운다.
export function buildRetroRows(
  items: RetroItem[],
  names: LedgerItem[],
  outcomes: LedgerOutcomeRow[],
): Row[] {
  const seriesName = new Map(outcomes.map((o) => [o.series_id, o.series_name]));
  const rows: Row[] = [];
  for (const it of items) {
    const known = names.find((x) => x.item_seq === it.item_seq);
    const base = subjectName(known ?? { ...it, name: null });
    const queue = HORIZONS.map((h) => it.slots.filter((s) => !s.series_id && s.horizon === h));
    const take = (i: number) => queue[i].shift() ?? null;
    const series = Array.from(
      new Set(it.slots.filter((s) => s.series_id).map((s) => s.series_id as string)),
    );
    for (const sid of series) {
      const code = sid.slice(sid.indexOf(":") + 1);
      rows.push({
        key: `${it.item_seq}:${sid}`,
        label: code === it.subject_id ? base : `${base} · ${seriesName.get(sid) ?? code}`,
        cells: HORIZONS.map(
          (h, i) => it.slots.find((s) => s.series_id === sid && s.horizon === h) ?? take(i),
        ),
      });
    }
    const left = Math.max(...queue.map((q) => q.length));
    for (let k = 0; k < left; k += 1) {
      const label =
        series.length > 0 ? `${base} · 결과 미기록 계열` : left > 1 ? `${base} · 계열 ${k + 1}` : base;
      rows.push({ key: `${it.item_seq}:p${k}`, label, cells: HORIZONS.map((_, i) => take(i)) });
    }
  }
  return rows;
}

const fmtPct = (v: number | undefined) =>
  v === undefined ? "—" : `${v >= 0 ? "+" : "-"}${Math.abs(v).toFixed(2)}%`;

// 계산 시각(02 = UTC 기록) → KST "MM-DD HH:MM".
export function fmtKst(iso: string | null): string {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const d = new Date(t + 9 * 3600 * 1000).toISOString();
  return `${d.slice(5, 10)} ${d.slice(11, 16)}`;
}

export function priceCell(s: RetroSlot | null): string {
  if (!s) return "—";
  const tail = s.partial_path ? " · 일부 종가 경로" : "";
  if (s.status === "MATURED") return (s.sign_text ?? fmtReturn(s.return_raw)) + tail;
  if (s.status === "PENDING_NOT_DUE") {
    return s.expected_eval_date ? `미도래 (${s.expected_eval_date.slice(5)})` : "미도래";
  }
  return s.status_text + tail;
}

interface Props {
  eventId: string;
  items: LedgerItem[]; // 03 상세 — 항목 이름
  outcomes: LedgerOutcomeRow[]; // 03 상세 — 계열 이름
  // 원장 새로고침 · 평가 저장 · 사후평가 실행마다 바뀐다 — 다시 읽는다.
  refreshKey: string;
}

export default function RetroItemRows({ eventId, items, outcomes, refreshKey }: Props) {
  const [data, setData] = useState<RetroResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetchRetrospectiveLatest(eventId)
      .then((r) => {
        if (alive) {
          setData(r);
          setError(null);
        }
      })
      .catch((e: Error) => {
        if (alive) setError(e.message);
      });
    return () => {
      alive = false;
    };
  }, [eventId, refreshKey]);

  const ok = data?.status === "OK";
  const rows = ok ? buildRetroRows(data.event?.items ?? [], items, outcomes) : [];
  return (
    <>
      <div className="ar-sec-h">사후평가 — 가격 결과 · 과거 검증(+5)</div>
      {error ? (
        <div className="message error">사후평가 결과를 불러오지 못했습니다 — {error}</div>
      ) : null}
      {!data && !error ? <div className="ar-note">불러오는 중...</div> : null}
      {data && !ok ? (
        <div className="ar-note">
          {data.status === "NO_RESULT"
            ? "사후평가 결과가 없습니다 — 위 [사후평가 실행]으로 만듭니다"
            : data.status_text}
        </div>
      ) : null}
      {ok && rows.length === 0 ? (
        <div className="ar-note">
          이 알림은 최근 사후평가(신호 기간 끝 {data.end_date}) 대상에 없습니다
        </div>
      ) : null}
      {ok && data.input_changed ? (
        <div className="ar-retro-warn">입력이 변경됨 · 재실행 필요 — 아래는 기존 결과입니다</div>
      ) : null}
      {rows.length > 0 ? (
        <div className="ar-table-wrap">
          <table className="ar-table">
            <thead>
              <tr>
                <th>항목</th>
                {HORIZONS.map((h) => (
                  <th key={h}>+{h}</th>
                ))}
                <th className="ar-num">+5 실제</th>
                <th className="ar-num">과거 검증 추정</th>
                <th className="ar-num">단순 기준</th>
                <th className="ar-num">절대오차</th>
                <th>ML 사유</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const five = r.cells[1];
                const ml = five?.ml ?? null;
                const est = ml?.status === "ESTIMATED";
                return (
                  <tr key={r.key}>
                    <td>{r.label}</td>
                    {r.cells.map((c, i) => (
                      <td key={i}>{priceCell(c)}</td>
                    ))}
                    <td className="ar-num">
                      {est
                        ? fmtPct(ml.actual_pct)
                        : five?.status === "MATURED"
                          ? fmtReturn(five.return_raw)
                          : "—"}
                    </td>
                    <td className="ar-num">{est ? fmtPct(ml.estimate_pct) : "—"}</td>
                    <td className="ar-num">{est ? fmtPct(ml.baseline_pct) : "—"}</td>
                    <td className="ar-num">
                      {est && ml.abs_error_pp !== undefined ? fmtPp(ml.abs_error_pp) : "—"}
                    </td>
                    <td className="ar-dim">{est ? "—" : (ml?.reason_text ?? "—")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
      {rows.length > 0 ? <PriceFacts rows={rows} /> : null}
    </>
  );
}

// 기록된 결과 행의 세부(설계 §4 · §6 — 평가일 · 기준가 · 종가 · 경로 최고/최저 · 가격 기준 · 계산 시각).
function PriceFacts({ rows }: { rows: Row[] }) {
  const facts = rows.flatMap((r) =>
    r.cells
      .filter((c): c is RetroSlot => c !== null && c.series_id !== null)
      .map((c) => ({ key: `${r.key}:${c.horizon}`, label: r.label, c })),
  );
  if (facts.length === 0) return null;
  return (
    <details className="ar-ledger">
      <summary>가격 결과 세부</summary>
      <p className="ar-note">
        저장된 무조정 종가 원시값입니다. 계산 시각은 OCI 가 결과를 기록한 시각(KST)이며 그때 PC
        에서 읽었다는 뜻이 아닙니다.
      </p>
      <div className="ar-table-wrap">
        <table className="ar-table">
          <thead>
            <tr>
              <th>항목</th>
              <th>기간</th>
              <th>상태</th>
              <th>평가일</th>
              <th className="ar-num">기준가</th>
              <th className="ar-num">평가일 종가</th>
              <th className="ar-num">종가 변화</th>
              <th className="ar-num">경로 최고</th>
              <th className="ar-num">경로 최저</th>
              <th className="ar-num">경로 종가 수</th>
              <th>가격 기준</th>
              <th>계산 시각</th>
            </tr>
          </thead>
          <tbody>
            {facts.map(({ key, label, c }) => (
              <tr key={key}>
                <td>{label}</td>
                <td>+{c.horizon}</td>
                <td>{c.status_text}</td>
                <td>{c.eval_date ?? "—"}</td>
                <td className="ar-num">{fmtPrice(c.t0_price)}</td>
                <td className="ar-num">{fmtPrice(c.eval_price)}</td>
                <td className="ar-num">{fmtReturn(c.return_raw)}</td>
                <td className="ar-num">{fmtReturn(c.max_up_raw)}</td>
                <td className="ar-num">{fmtReturn(c.max_down_raw)}</td>
                <td className="ar-num">{c.path_points ?? "—"}</td>
                <td>{c.price_basis ?? "—"}</td>
                <td>{fmtKst(c.computed_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
