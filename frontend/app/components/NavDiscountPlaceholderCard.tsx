"use client";

// POC2 NAV/괴리율 카드 (2026-06-08 — Naver ETF Universe NAV Integration).
//
// 이전 정책 (2026-06-06): NAV / 괴리율 source 미연동 — unavailable 고정 표시.
// 현재 정책 (2026-06-08): Naver `etfItemList.nhn` universe 1회 호출로 NAV /
//   시장가격 / 괴리율을 store(etf_nav_daily) 에 저장. ETF Exposure draft 안의
//   data_quality.nav_discount 가 ok / partial 이면 값 표시. unavailable 이 많으면
//   여전히 안내 배지 노출.

import type { MarketCandidate } from "@/lib/api";

interface Props {
  candidates?: ReadonlyArray<MarketCandidate>;
}

function _fmtNum(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return Math.round(value).toLocaleString();
}

function _fmtPctp(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value.toFixed(2)}%`;
}

export default function NavDiscountPlaceholderCard({ candidates = [] }: Props) {
  const stats = (() => {
    let ok = 0;
    let unavailable = 0;
    for (const c of candidates) {
      const status = c.data_quality?.nav_discount?.status;
      if (status === "ok" || status === "partial") ok += 1;
      else unavailable += 1;
    }
    return { ok, unavailable, total: candidates.length };
  })();

  const okItems = candidates
    .filter(
      (c) =>
        c.data_quality?.nav_discount?.status === "ok" ||
        c.data_quality?.nav_discount?.status === "partial",
    )
    .slice(0, 5);

  if (candidates.length === 0 || stats.ok === 0) {
    return (
      <div className="card">
        <h2>NAV / 괴리율 상태</h2>
        <div className="nav-unavailable-note" style={{ display: "block" }}>
          NAV / 괴리율: <strong>{candidates.length === 0 ? "후보 ETF 없음" : "표시 가능한 데이터 없음"}</strong>
          <br />
          {candidates.length > 0 && stats.unavailable > 0 && (
            <>
              후보 {stats.total}개 중 NAV ok {stats.ok}건 / unavailable{" "}
              {stats.unavailable}건. Market Discovery 갱신을 다시 실행하면 Naver
              universe NAV 가 재수집됩니다.
            </>
          )}
          {candidates.length === 0 && (
            <>
              ETF Exposure 화면 진입 후 후보 ETF 가 연결되면 NAV / 괴리율이
              표시됩니다.
            </>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <h2>NAV / 괴리율 상태</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        Naver ETF universe (`etfItemList.nhn`) 1회 호출 결과 — Market Discovery
        갱신 시점에 등록된 NAV / 시장가 / 괴리율. 후보 {stats.total}개 중 NAV ok{" "}
        <strong>{stats.ok}</strong>건 / 미수집{" "}
        <strong>{stats.unavailable}</strong>건. 매수/매도 판단 아님.
      </p>
      <table className="market-topn-table">
        <thead>
          <tr>
            <th>ETF</th>
            <th style={{ textAlign: "right" }}>NAV</th>
            <th style={{ textAlign: "right" }}>시장가</th>
            <th style={{ textAlign: "right", width: 100 }}>괴리율</th>
            <th style={{ width: 100 }}>asof</th>
            <th style={{ width: 160 }}>source</th>
            <th style={{ width: 90 }}>status</th>
          </tr>
        </thead>
        <tbody>
          {okItems.map((c) => {
            const nav = c.data_quality?.nav_discount;
            return (
              <tr key={c.ticker ?? c.name}>
                <td>
                  <code>{c.ticker ?? "-"}</code> {c.name ?? ""}
                </td>
                <td style={{ textAlign: "right" }}>{_fmtNum(nav?.nav)}</td>
                <td style={{ textAlign: "right" }}>
                  {_fmtNum(nav?.market_price)}
                </td>
                <td style={{ textAlign: "right" }}>
                  {_fmtPctp(nav?.discount_rate_pct)}
                  {nav?.flag ? (
                    <>
                      {" "}
                      <span style={{ fontSize: "0.75rem", color: "var(--warn)" }}>
                        {nav.flag}
                      </span>
                    </>
                  ) : null}
                </td>
                <td>{nav?.asof ?? "-"}</td>
                <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
                  {nav?.source ?? "-"}
                </td>
                <td>{nav?.status ?? "-"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {stats.ok > okItems.length && (
        <p
          className="helper"
          style={{ marginTop: 4, fontSize: "0.78rem" }}
        >
          상위 {okItems.length}개만 표시. 전체 {stats.ok}건은 후보 테이블에서 확인.
        </p>
      )}
      {stats.unavailable > 0 && (
        <p
          className="helper"
          style={{ marginTop: 4, fontSize: "0.78rem", color: "var(--muted)" }}
        >
          unavailable {stats.unavailable}건은 Naver 응답에서 누락된 종목입니다.
        </p>
      )}
    </div>
  );
}
