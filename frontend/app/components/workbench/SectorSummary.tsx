"use client";

// POC6-28 — 「후보」 [섹터 요약](첫 화면 · PLAN §2-3 · 판정 §3 · §5 국면 순서).
// 카드: 내 보유와 겹친 항목 · 하위권 · 상위권(+ 보합장이면 상·하위에 함께 나온 업종).
// 첫 두 줄 = 공식 기초시장 · 자산 구성 · 사업군 분류 n/30. 반복된 업종 먼저 · 기초지수별 묶음은 접어 둔다.

import { createContext, useContext, useState } from "react";
import type { CompareGroup, CompareRow, CompareSummaryOk } from "@/lib/api/etfCompare";
import {
  BASIS_LABEL,
  commonText,
  countsText,
  kindLabel,
  md,
  mixText,
  pct,
  regimeView,
  sectorLine,
  type CardKey,
} from "@/lib/etfCompare";
import { directionColor } from "./helpers";
import EtfRowDetail from "./EtfRowDetail";
import CopyListButton from "./CopyListButton";
import type { MenuKey } from "../LeftSidebar";

const SHOW_FIRST = 5;

// POC6-29 — 행 상세의 [AI 세션에서 검토]가 메뉴를 옮길 수 있게(묶음 · 카드를 거치지 않고 ETF 줄까지).
const NavContext = createContext<((k: MenuKey) => void) | undefined>(undefined);

function EtfLine({
  row,
  s,
  side,
  open,
  onToggle,
}: {
  row: CompareRow;
  s: CompareSummaryOk;
  side: "top" | "bottom";
  open: boolean;
  onToggle: () => void;
}) {
  const nav = useContext(NavContext);
  const c = row.classification;
  const tags = [c.market === "국내" ? null : c.market, c.asset === "주식" ? null : c.asset, c.strategy ? "전략형" : null]
    .filter(Boolean)
    .join(" · ");
  return (
    <>
      <div
        className={`ec-etf${open ? " sel" : ""}`}
        role="button"
        tabIndex={0}
        aria-expanded={open}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onToggle();
          }
        }}
      >
        <span className="ec-etf-name">
          {row.name ?? row.ticker}
          {row.held && <span className="wb-hb hold">보유</span>}
          {s.in_both.includes(row.ticker) && <span className="ec-chip both">상·하위 공통</span>}
          {tags && <span className="ec-tag">{tags}</span>}
        </span>
        <span className="ec-etf-val" style={{ color: directionColor(row.basis_return.value) }}>
          {pct(row.basis_return.value)}
        </span>
      </div>
      {open && <EtfRowDetail row={row} s={s} side={side} screen="sector_summary" onNavigate={nav} />}
    </>
  );
}

function GroupBlock({
  g,
  rows,
  s,
  side,
  openTicker,
  setOpenTicker,
  defaultOpen,
  emphasizeDistinct,
}: {
  g: CompareGroup;
  rows: CompareRow[];
  s: CompareSummaryOk;
  side: "top" | "bottom";
  openTicker: string | null;
  setOpenTicker: (t: string | null) => void;
  defaultOpen: boolean;
  emphasizeDistinct: boolean;
}) {
  const [all, setAll] = useState(false);
  const members = g.tickers.map((t) => rows.find((r) => r.ticker === t)).filter((r): r is CompareRow => !!r);
  const shown = all ? members : members.slice(0, SHOW_FIRST);
  const range = g.etf_count === 1 ? pct(g.return_min) : `${pct(g.return_min)} ~ ${pct(g.return_max)}`;
  return (
    <details className="ec-group" open={defaultOpen} data-testid="ec-group">
      <summary>
        <span className="ec-group-name">{g.name ?? "미분류"}</span>
        <span className={`ec-kind ${g.kind}`}>{kindLabel(g)}</span>
        <span>
          ETF {g.etf_count}개
          {g.kind === "sector" && (
            <span className={emphasizeDistinct ? "ec-strong" : undefined}> · 서로 다른 지수 {g.distinct_index_count}종</span>
          )}
        </span>
        <span>{range}</span>
        {g.kind !== "sector" && members[0] && (
          <span className="ec-small">
            {members[0].name ?? members[0].ticker}
            {members.length > 1 ? ` 외 ${members.length - 1}` : ""}
          </span>
        )}
        <span className="ec-small">
          {countsText(g.markets)}
          {g.strategy_count ? ` · 전략형 ${g.strategy_count}` : ""}
          {g.held_count ? ` · 보유 ${g.held_count}` : ""}
        </span>
        {g.both_sides && <span className="ec-chip both">상·하위에 함께</span>}
      </summary>
      {shown.map((r) => (
        <EtfLine
          key={r.ticker}
          row={r}
          s={s}
          side={side}
          open={openTicker === `${side}:${r.ticker}`}
          onToggle={() => setOpenTicker(openTicker === `${side}:${r.ticker}` ? null : `${side}:${r.ticker}`)}
        />
      ))}
      {members.length > SHOW_FIRST && (
        <button type="button" className="wb-btn ec-more" onClick={() => setAll(!all)}>
          {all ? "접기" : `나머지 ${members.length - SHOW_FIRST}개 보기`}
        </button>
      )}
      <div className="ec-common" data-testid="ec-common">
        {g.constituents.status === "ok" && (
          <div>
            <b>공통 구성종목</b> {g.constituents.common.map((c) => `${c.name} ${c.etf_count}`).join(" · ")}
          </div>
        )}
        <div className="ec-small">{commonText(g)}</div>
      </div>
    </details>
  );
}

function SideCard({
  s,
  side,
  openTicker,
  setOpenTicker,
  emphasizeDistinct,
}: {
  s: CompareSummaryOk;
  side: "top" | "bottom";
  openTicker: string | null;
  setOpenTicker: (t: string | null) => void;
  emphasizeDistinct: boolean;
}) {
  const rows = side === "top" ? s.top : s.bottom;
  const groups = s.groups[side];
  const ov = s.overview[side];
  const sectors = groups.filter((g) => g.kind === "sector");
  const others = groups.filter((g) => g.kind !== "sector");
  const indexCount = others.filter((g) => g.kind === "index").length;
  const unclassified = others.filter((g) => g.kind === "unclassified").reduce((n, g) => n + g.etf_count, 0);
  const vals = rows.map((r) => r.basis_return.value);
  const [othersOpen, setOthersOpen] = useState(false);
  const title = side === "top" ? "상위권에 모인 업종 · 테마" : "하위권에 모인 업종 · 테마";
  return (
    <section className="card ec-card" data-testid={`ec-card-${side}`}>
      <h2>{title}</h2>
      <div className="ec-small">
        {BASIS_LABEL[s.basis]} {side === "top" ? "상위" : "하위"} {rows.length}개
        {vals.length ? ` · ${pct(Math.min(...vals))} ~ ${pct(Math.max(...vals))}` : ""}
      </div>
      <div className="ec-mix" data-testid={`ec-mix-${side}`}>
        {mixText(ov)}
      </div>
      <div className="ec-mix" data-testid={`ec-sector-line-${side}`}>
        {sectorLine(ov)}
      </div>
      {sectors.map((g) => (
        <GroupBlock
          key={`s:${g.name}`}
          g={g}
          rows={rows}
          s={s}
          side={side}
          openTicker={openTicker}
          setOpenTicker={setOpenTicker}
          defaultOpen={g === sectors[0] && g.etf_count >= 2}
          emphasizeDistinct={emphasizeDistinct}
        />
      ))}
      {others.length > 0 && (
        <div className="ec-others">
          <button type="button" className="wb-btn ec-more" aria-expanded={othersOpen} onClick={() => setOthersOpen(!othersOpen)}>
            {othersOpen ? "▾" : "▸"} 기초지수별 묶음 {indexCount}개 · 미분류 {unclassified}개
          </button>
          {othersOpen &&
            others.map((g) => (
              <GroupBlock
                key={`o:${g.kind}:${g.name}`}
                g={g}
                rows={rows}
                s={s}
                side={side}
                openTicker={openTicker}
                setOpenTicker={setOpenTicker}
                defaultOpen={false}
                emphasizeDistinct={false}
              />
            ))}
        </div>
      )}
      <CopyListButton s={s} side={side} />
    </section>
  );
}

function HoldingsCard({
  s,
  onNavigate,
  strong,
}: {
  s: CompareSummaryOk;
  onNavigate: (k: MenuKey) => void;
  strong: boolean;
}) {
  const items = s.holdings.items;
  const direct = items.filter((h) => h.side);
  const expo = items.filter((h) => h.exposure.status === "ok");
  return (
    <section className={`card ec-card${strong ? " strong" : ""}`} data-testid="ec-card-holdings">
      <h2>내 보유와 겹친 항목</h2>
      {s.holdings.status === "error" ? (
        <p className="wb-danger">보유 파일을 읽지 못해 겹침을 확인하지 못했습니다.</p>
      ) : (
        <div className="ec-small">
          이번 상·하위 {s.counts.shown_top + s.counts.shown_bottom - s.in_both.length}개 기준 · 직접 보유{" "}
          {direct.length}건 · 구성종목 겹침(노출 확인) {expo.length}종목
        </div>
      )}
      {direct.map((h) => {
        const row = (h.side === "top" ? s.top : s.bottom).find((r) => r.ticker === h.ticker);
        return (
          <div key={`d:${h.ticker}`} className="ec-hold-line">
            <span className="ec-etf-name">{row?.name ?? h.ticker}</span>
            <span>
              {h.side === "top" ? "상위" : "하위"} {h.side_rank}위
              {h.side === "bottom" && h.top_rank != null ? ` · 상위 ${h.top_rank}위(상·하위 공통)` : ""} ·{" "}
              {BASIS_LABEL[s.basis]}{" "}
              <span style={{ color: directionColor(h.basis_return?.value) }}>{pct(h.basis_return?.value)}</span> (
              {md(h.basis_return?.start)} → {md(h.basis_return?.end)})
            </span>
          </div>
        );
      })}
      {expo.length > 0 && (
        <div className="ec-hold-line">
          <span className="ec-chip expo">노출 확인</span>
          <span className="ec-small">
            보유 {expo.length}종목이 하위권 ETF 구성 상위 10과 겹칩니다 — 종목별 겹친 종목 · 구성 기준일은 「보유」에서
            봅니다.
          </span>
        </div>
      )}
      <div className="ec-btn-row">
        <button type="button" className="wb-btn btn-md" onClick={() => onNavigate("workbench_holdings")}>
          「보유」에서 보기 →
        </button>
      </div>
    </section>
  );
}

function BothCard({ s }: { s: CompareSummaryOk }) {
  return (
    <section className="card ec-card strong" data-testid="ec-card-both">
      <h2>상·하위에 함께 나온 업종</h2>
      <div className="ec-small">
        같은 기간 상위와 하위에 모두 들어 있는 업종입니다. 업종 안에서 ETF별 차이를 확인하세요.
      </div>
      {s.both_side_sectors.map((name) => {
        const t = s.groups.top.find((g) => g.kind === "sector" && g.name === name);
        const b = s.groups.bottom.find((g) => g.kind === "sector" && g.name === name);
        return (
          <div key={name} className="ec-hold-line">
            <span className="ec-etf-name">{name}</span>
            <span>
              상위 {t?.etf_count ?? 0}개({t ? pct(t.return_max) : "—"} ~) · 하위 {b?.etf_count ?? 0}개(~{" "}
              {b ? pct(b.return_min) : "—"})
            </span>
          </div>
        );
      })}
    </section>
  );
}

export default function SectorSummary({
  s,
  onNavigate,
}: {
  s: CompareSummaryOk;
  onNavigate: (k: MenuKey) => void;
}) {
  const [openTicker, setOpenTicker] = useState<string | null>(null);
  const rv = regimeView(s.regime, s.end_date, s.both_side_sectors);
  const card = (k: CardKey) => {
    if (k === "both") return <BothCard key="both" s={s} />;
    if (k === "holdings")
      return <HoldingsCard key="holdings" s={s} onNavigate={onNavigate} strong={rv.emphasis === "holdings"} />;
    return (
      <SideCard
        key={k}
        s={s}
        side={k}
        openTicker={openTicker}
        setOpenTicker={setOpenTicker}
        emphasizeDistinct={k === "top" && rv.emphasis === "distinct_index"}
      />
    );
  };
  return (
    <NavContext.Provider value={onNavigate}>
      <div className="ec-cards" data-testid="ec-sector-summary" data-order={rv.order.join(",")}>
        {rv.order.map(card)}
      </div>
    </NavContext.Provider>
  );
}
