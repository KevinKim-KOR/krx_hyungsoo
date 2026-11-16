"use client";

// POC6-31 STEP 3(PLAN C17 · C18 · 판정 §2 첫째 · Q9 · Q10 · Q21) — 여러 지수 계열이 함께 담은 주식.
// - 「ETF 구성종목」 중복률 탭의 예전 '반복 핵심 종목' 자리(같은 화면에 기준이 다른 두 목록을 두지 않음).
// - 표 머리 = 확인 범위 · 비교 성립 여부(수치보다 먼저). 가장 최근 구성일의 ETF끼리 센다 · 이전 날짜는 참고.
// - 주식마다 ETF별 공식 지수명 · 전략형 · 비중 · 순위 · 1개월 수익률 · [후보로 고르기](고른 뒤 비교 이동은 화면 위쪽 줄).
// - 업종 해석은 가설(주식 업종 자료 없음 · ASSUMPTIONS Q4) — 「섹터요약」 공통 구성종목과 기준이 다르다(같은 묶음 안 비교).
import { useState } from "react";
import type { CrossFamilyGroup, CrossFamilyResponse, CrossFamilyStock } from "@/lib/api/constituentsStatus";
import { crossFamilyVerdict } from "@/lib/constituentsText";
import { md } from "@/lib/etfCompare";
import { directionColor } from "./workbench/helpers";

function pct(v: number | null | undefined): string {
  return v === null || v === undefined ? "-" : `${v.toFixed(2)}%`;
}

export function signed(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  return `${v > 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function scopeText(cf: CrossFamilyResponse): string {
  const s = cf.scope;
  const parts = [
    `구성 자료 ${s.with_data}/${s.requested}(원천 구성일 확인된 것)`,
    s.latest_date ? `최신 구성일 ${md(s.latest_date)} ${s.same_date}개` : null,
    s.family_count !== undefined ? `확인된 계열 ${s.family_count}개` : null,
    s.unconfirmed_family_etfs ? `계열 미확인 ETF ${s.unconfirmed_family_etfs}` : null,
    s.unknown_rows ? `종류 미확인 행 ${s.unknown_rows}(가림)` : null,
  ];
  return parts.filter(Boolean).join(" · ");
}

function verdictText(g: Pick<CrossFamilyGroup, "status" | "stocks" | "evidence_count">): string {
  return crossFamilyVerdict({ status: g.status, stockCount: g.stocks.length, evidenceCount: g.evidence_count });
}

export default function CrossFamilyCard({
  cf,
  error,
  returnByTicker,
  onPick,
  picked,
}: {
  cf: CrossFamilyResponse | null;
  error: string | null;
  returnByTicker: Record<string, number | null | undefined>;
  onPick: (ticker: string, name: string | null) => void;
  // 고른 후보(행에 '고름' 표시) — 고른 후보 줄 · [보유와 후보 비교에서 보기 →]는 화면 위쪽(ETFExposureView · 2026-11-16 사용자 지시)
  picked: { ticker: string; name: string | null } | null;
}) {
  const [openKeys, setOpenKeys] = useState<Set<string>>(() => new Set());
  const [showAll, setShowAll] = useState(false);
  if (error) {
    return (
      <div className="card" data-testid="cf-card">
        <h2>여러 지수 계열이 함께 담은 주식</h2>
        <div className="message error">읽지 못했습니다 — {error}</div>
      </div>
    );
  }
  if (!cf) return null;
  const shown = showAll ? cf.stocks : cf.stocks.slice(0, 20);
  return (
    <div className="card" data-testid="cf-card">
      <h2>여러 지수 계열이 함께 담은 주식</h2>
      <p className="helper" data-testid="cf-scope">
        확인 범위: {scopeText(cf)} · ETF마다 원본 비중 1 ~ 10행 중 식별 가능한 주식 행만(현금 · 채권 · 파생 · ETF ·
        종류 미확인 가림) · 계열 = 공식 지수명이 같거나 판정으로 확인된 같은 기초지수
      </p>
      <p className={cf.status === "ok" ? "helper" : "message info"} data-testid="cf-verdict">
        {verdictText({ status: cf.status, stocks: cf.stocks, evidence_count: cf.scope.evidence_count ?? 0 })}
      </p>
      {cf.stocks.length > 0 ? (
        // POC6-31(형수님 화면 의견 · 목업 확인 2026-11-16) — 화면 폭 전체 표 대신 왼쪽부터 한 줄 요약 목록 · 줄을 눌러 펼침 ·
        // 펼친 ETF 줄을 눌러 고름(고른 ETF = 파란 테두리 · 채운 동그라미 · '✓ 고른 후보' · 같은 ETF 는 어느 주식 아래든 같이).
        <div className="cf-list" data-testid="cf-table">
          {shown.map((s: CrossFamilyStock) => (
            <StockItem
              key={s.key}
              s={s}
              open={openKeys.has(s.key)}
              onToggle={() => {
                const next = new Set(openKeys);
                if (next.has(s.key)) next.delete(s.key);
                else next.add(s.key);
                setOpenKeys(next);
              }}
              returnByTicker={returnByTicker}
              onPick={onPick}
              picked={picked}
            />
          ))}
        </div>
      ) : null}
      {cf.stocks.length > 20 ? (
        <button type="button" className="wb-btn btn-md" onClick={() => setShowAll(!showAll)} data-testid="cf-more">
          {showAll ? "20종목만 보기" : `${cf.stocks.length - 20}종목 더 보기`}
        </button>
      ) : null}
      <p className="helper">
        정렬 = 계열 수 → ETF 수 → 가장 큰 비중. 주식 자체의 업종 자료는 없어, 업종은 「섹터요약」 · 수익률과 함께 읽는
        가설입니다. 「섹터요약」의 공통 구성종목(같은 묶음 안 비교)과는 기준이 다릅니다.
      </p>
      {cf.reference.length > 0 ? (
        <details data-testid="cf-reference">
          <summary>이전 구성일 참고 {cf.reference.length}개 날짜</summary>
          <ul className="dashboard-status-list">
            {cf.reference.map((r) => (
              <li key={r.date}>
                {md(r.date)} 구성 ETF {r.etf_count}개 — {verdictText(r)}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function StockItem({
  s,
  open,
  onToggle,
  returnByTicker,
  onPick,
  picked,
}: {
  s: CrossFamilyStock;
  open: boolean;
  onToggle: () => void;
  returnByTicker: Record<string, number | null | undefined>;
  onPick: (ticker: string, name: string | null) => void;
  picked: { ticker: string } | null;
}) {
  const hasPicked = !!picked && s.entries.some((e) => e.etf === picked.ticker);
  return (
    <div className="cf-stock">
      <button type="button" className="cf-srow" aria-expanded={open} onClick={onToggle} data-testid="cf-stock-row">
        <span className="cf-chev" aria-hidden="true">
          {open ? "▼" : "▶"}
        </span>
        <span className="cf-sname">{s.name}</span>
        <span className="cf-facts">
          <span className="cf-pill">
            계열 {s.family_count}
            {s.strategy_count ? ` · 전략형 ${s.strategy_count}` : ""}
          </span>
          <span className="cf-pill">ETF {s.etf_count}</span>
          <span>
            가장 큰 비중{" "}
            <b>
              {pct(s.max_weight_pct)} · {s.max_entry.etf_name ?? s.max_entry.etf} {s.max_entry.rank}위
            </b>
          </span>
          {hasPicked ? <span className="cf-pill cf-pill-on">고른 후보 포함</span> : null}
        </span>
      </button>
      {open ? (
        <div className="cf-etfs" data-testid="cf-entries">
          <div className="cf-ehead" aria-hidden="true">
            <span />
            <span>ETF · 공식 지수명</span>
            <span className="cf-num">비중 · 순위 · 구성일</span>
            <span className="cf-num">1개월</span>
            <span />
          </div>
          {s.entries.map((e) => {
            const on = picked?.ticker === e.etf;
            return (
              <button
                type="button"
                key={e.etf}
                className={on ? "cf-etf cf-etf-on" : "cf-etf"}
                aria-pressed={on}
                onClick={() => onPick(e.etf, e.etf_name)}
                data-testid="cf-etf"
              >
                <span className="cf-radio" aria-hidden="true" />
                <span className="cf-ename-box">
                  <span className="cf-ename">{e.etf_name ?? e.etf}</span>
                  <span className="cf-idx">
                    {e.index_name ?? "계열 미확인"}
                    {e.strategy ? " · 전략형" : ""}
                  </span>
                </span>
                <span className="cf-num">
                  {pct(e.weight_pct)} · {e.rank}위 · {md(e.asof)} 구성
                </span>
                <span className="cf-num" style={{ color: directionColor(returnByTicker[e.etf]) }}>
                  {signed(returnByTicker[e.etf])}
                </span>
                <span className="cf-badge">{on ? "✓ 고른 후보" : ""}</span>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
