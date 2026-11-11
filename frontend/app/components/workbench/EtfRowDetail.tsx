"use client";

// POC6-28 — 「후보」 ETF 행 바로 아래 상세(섹터 요약 · ETF 순위 공통 · PLAN §2-5 · 판정 §5).
// 기존 가격 차트를 그대로 쓰고(저장 건수 · 전체 저장 기간 줄만 뺌), 행에서 본 값을 박스로 다시 보이지 않는다.
// 한 줄씩: 조회 기간 · 1개월 KODEX 200 대비 · 최근 고점 대비 · 3개월 · 분류 · 끝일 가격 상태.

import type { CompareRow, CompareSummaryOk } from "@/lib/api/etfCompare";
import { BASIS_LABEL, bothRanks, endPriceText, md, pct, reasonText } from "@/lib/etfCompare";
import PriceChart from "./PriceChart";

function won(v: number | null | undefined): string {
  return v == null ? "—" : `${v.toLocaleString("ko-KR")}원`;
}

export default function EtfRowDetail({
  row,
  s,
  side,
  rowValueKey = null,
}: {
  row: CompareRow;
  s: CompareSummaryOk;
  side: "top" | "bottom";
  // [ETF 순위]에서 행에 이미 보이는 기준(3개월)은 상세에서 날짜만 적는다(행 값 반복 없음 · 판정 §5).
  rowValueKey?: "three_month" | null;
}) {
  const c = row.criteria;
  const same = c.same_kodex_1m;
  const dd = c.drawdown;
  const three = c.three_month;
  const cls = row.classification;
  const br = row.basis_return;
  const both = bothRanks(s, row.ticker);
  const intradayNote =
    row.end_price.state === "intraday" ? `${md(row.end_price.date)} = ${endPriceText(row.end_price)}` : null;
  const kind =
    cls.kind === "sector" ? `업종 ${cls.sector}` : cls.kind === "index" ? "기초지수별 묶음" : "미분류";
  return (
    <div className="ec-detail" data-testid="ec-etf-detail">
      <PriceChart ticker={row.ticker} valueLabel="저장 가격" compact lastNote={intradayNote} />
      <dl className="ec-lines">
        <dt>조회 기간</dt>
        <dd>
          {BASIS_LABEL[s.basis]} {md(br.start)} {won(br.start_close)} → {md(br.end)} {won(br.end_close)} ·{" "}
          {both ? `상위 ${both.top}위 · 하위 ${both.bottom}위(상·하위 공통)` : `${side === "top" ? "상위" : "하위"} ${row.rank}위`} ·{" "}
          {md(row.end_price.date)} 가격 = {endPriceText(row.end_price)}
        </dd>
        <dt>1개월 KODEX 200 대비</dt>
        <dd data-testid="ec-detail-same">
          {same.status === "ok"
            ? `${md(same.start)} → ${md(same.end)} · 이 ETF ${pct(same.etf_return_pct)} · KODEX 200 ${pct(
                same.kodex200_return_pct,
              )} · 차이 ${pct(same.value, "%p")}`
            : reasonText({ ...same, unit: "%p" })}
        </dd>
        <dt>최근 고점 대비</dt>
        <dd data-testid="ec-detail-drawdown">
          {dd.status === "missing"
            ? reasonText({ ...dd, unit: "%" })
            : `20저장일 ${md(dd.start)} ~ ${md(dd.end)} · 고점 ${md(dd.peak_date)} ${won(dd.peak_close)} → ${md(
                dd.end,
              )} ${won(dd.close)} · ${pct(dd.value)}${dd.status === "period_differs" ? " · 기간 다름(KODEX 200 창과 다름)" : ""}`}
        </dd>
        {s.basis !== "three_month" && (
          <>
            <dt>3개월</dt>
            <dd data-testid="ec-detail-three">
              {three.status === "missing"
                ? reasonText({ ...three, unit: "%" })
                : `${md(three.start)} → ${md(three.end)}${rowValueKey === "three_month" ? "" : ` · ${pct(three.value)}`}${
                    three.status === "period_differs" ? " · 기간 다름(상장 뒤 구간 등)" : ""
                  }`}
            </dd>
          </>
        )}
        <dt>기초지수 · 분류</dt>
        <dd>
          {cls.index_name ?? "공식 기준정보 없음"}
          {cls.market ? ` · 지역 ${cls.market}` : ""}
          {cls.asset ? ` · 자산 ${cls.asset}` : ""}
          {cls.strategy ? " · 운용 전략 전략형(커버드콜 등)" : ""} · {kind}
          {cls.kind === "sector" ? " (공식 지수명의 낱말 = 기존 사업군 사전)" : ""}
        </dd>
        <dt>보유</dt>
        <dd>{row.held ? "보유 중" : "보유하지 않음"}</dd>
      </dl>
    </div>
  );
}
