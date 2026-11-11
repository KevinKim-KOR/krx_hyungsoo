"use client";

// POC6-28 — 「후보」 [ETF 순위](판정 Q9 (a) · §5 · PLAN §2-4 · §3-6).
// 목록 = 섹터 요약과 같은 응답의 상위 · 하위 최대 30. 정렬 버튼은 그 목록 안의 표시 순서만 바꾼다.
// 비교 가능 행을 값 순(동률 = 선정 순위)으로, 기간 다름 · 값 없음은 방향과 관계없이 그 뒤에 선정 순위로.
// 행 = 표시 순서 · ETF명 · 표시(보유 · 해외 · 전략형) · 선정 순위 · 선택 기준값(또는 사유).

import { useState } from "react";
import type { CompareSummaryOk } from "@/lib/api/etfCompare";
import {
  SORT_LABEL,
  comparable,
  criterionOf,
  kodexSameNote,
  pct,
  reasonText,
  sortLine,
  sortRows,
  type SortDir,
  type SortKey,
} from "@/lib/etfCompare";
import { directionColor } from "./helpers";
import EtfRowDetail from "./EtfRowDetail";

const KEYS: SortKey[] = ["sel", "one_month", "three_month", "same", "drawdown"];

export default function RankingList({ s }: { s: CompareSummaryOk }) {
  const [side, setSide] = useState<"top" | "bottom">("top");
  const [key, setKey] = useState<SortKey>("sel");
  const [dir, setDir] = useState<SortDir>("desc");
  const [open, setOpen] = useState<string | null>(null);
  const base = side === "top" ? s.top : s.bottom;
  const rows = sortRows(base, key, dir);
  const note = key === "same" ? kodexSameNote(s) : null;

  const pickSide = (next: "top" | "bottom") => {
    setSide(next);
    setKey("sel");
    setDir(next === "top" ? "desc" : "asc");
    setOpen(null);
  };
  const pickKey = (k: SortKey) => {
    if (k === "sel") setKey("sel");
    else if (k === key) setDir(dir === "desc" ? "asc" : "desc");
    else {
      setKey(k);
      setDir(side === "top" ? "desc" : "asc");
    }
    setOpen(null);
  };

  return (
    <div className="ec-rank" data-testid="ec-ranking">
      <div className="ec-rank-head">
        <span className="holdings-sort-seg" role="group" aria-label="상위 · 하위">
          {(["top", "bottom"] as const).map((sd) => (
            <button key={sd} type="button" className={side === sd ? "on" : undefined} aria-pressed={side === sd} onClick={() => pickSide(sd)}>
              {sd === "top" ? `상위 ${s.top.length}` : `하위 ${s.bottom.length}`}
            </button>
          ))}
        </span>
        <span className="ec-small">섹터 요약과 같은 목록 · 정렬은 이 목록 안의 표시 순서만 바꿉니다</span>
      </div>
      <div className="holdings-sortbar">
        <span className="holdings-sortbar-label">정렬</span>
        <span className="holdings-sort-seg">
          {KEYS.map((k) => (
            <button key={k} type="button" className={key === k ? "on" : undefined} aria-pressed={key === k} onClick={() => pickKey(k)}>
              {SORT_LABEL[k]}
              {key === k && k !== "sel" ? (dir === "desc" ? " ▼" : " ▲") : ""}
            </button>
          ))}
        </span>
        <span className="holdings-sortbar-hint">같은 항목을 다시 누르면 높은 순 ↔ 낮은 순</span>
      </div>
      <div className="ec-basis" data-testid="ec-sort-line">
        <div className="ec-basis-main">{sortLine(s, side, key, dir, base)}</div>
        {note && (
          <div className="ec-small" data-testid="ec-kodex-note">
            {note}
          </div>
        )}
      </div>
      <div className="ec-rank-list" data-testid="ec-rank-list">
        {rows.map((r, i) => {
          const v = criterionOf(r, key);
          const ok = comparable(v);
          const c = r.classification;
          const marks = [c.market && c.market !== "국내" ? c.market : null, c.strategy ? "전략형" : null].filter(Boolean);
          const isOpen = open === r.ticker;
          return (
            <div key={r.ticker} data-testid="ec-rank-row">
              <div
                className={`ec-rank-row${isOpen ? " sel" : ""}`}
                role="button"
                tabIndex={0}
                aria-expanded={isOpen}
                onClick={() => setOpen(isOpen ? null : r.ticker)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setOpen(isOpen ? null : r.ticker);
                  }
                }}
              >
                <span className="ec-rank-pos">{i + 1}</span>
                <span className="ec-etf-name">
                  {r.name ?? r.ticker}
                  {r.held && <span className="wb-hb hold">보유</span>}
                  {s.in_both.includes(r.ticker) && <span className="ec-chip both">상·하위 공통</span>}
                  {marks.length > 0 && <span className="ec-tag">{marks.join(" · ")}</span>}
                </span>
                <span className="ec-small">
                  {side === "top" ? "상위" : "하위"} {r.rank}위
                </span>
                <span className="ec-rank-val" data-testid="ec-rank-val" style={{ color: ok ? directionColor(v.value) : "var(--muted)" }}>
                  {ok ? pct(v.value, v.unit) : reasonText(v)}
                </span>
              </div>
              {isOpen && (
                <EtfRowDetail row={r} s={s} side={side} rowValueKey={key === "three_month" ? "three_month" : null} />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
