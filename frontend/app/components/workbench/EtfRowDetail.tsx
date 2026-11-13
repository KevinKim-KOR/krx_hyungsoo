"use client";

// POC6-28 — 「후보」 ETF 행 바로 아래 상세(섹터 요약 · ETF 순위 공통 · PLAN §2-5 · 판정 §5).
// 기존 가격 차트를 그대로 쓰고(저장 건수 · 전체 저장 기간 줄만 뺌), 행에서 본 값을 박스로 다시 보이지 않는다.
// POC6-29(PLAN §2-5 · §2-7 · §3-3 · §3-4 · 판정 Q4-1 · Q4-2) — 「섹터요약」 · 「후보리스트」 공통 행 상세:
//   조회 기간 · 상세 수치(1 · 3 · 6 · 12개월 · 20구간 KODEX 200 차이 · 시장가 · NAV · 괴리율 등 · 펼칠 때 그 종목만 읽음) ·
//   분류 · 보유 → 판단 근거 미리보기(이 화면의 공통 기간 목록에서 찾음) → [AI 세션에서 검토].

import type { CompareCondition, CompareRow, CompareSummaryOk } from "@/lib/api/etfCompare";
import type { DecisionDraftScreen } from "@/lib/api/decisionDraftPreview";
import { BASIS_LABEL, bothRanks, endPriceText, md } from "@/lib/etfCompare";
import type { MenuKey } from "../LeftSidebar";
import DecisionDraftPreviewCard from "../holdings_compare/DecisionDraftPreviewCard";
import { DetailLines, detailOf, detailStateText, useEtfDetail } from "./DetailNumbers";
import PriceChart from "./PriceChart";

function won(v: number | null | undefined): string {
  return v == null ? "—" : `${v.toLocaleString("ko-KR")}원`;
}

// B 화면 판단 근거의 시장 흐름 기간(판정 Q8 · 「오늘의 투자 점검」 시장 근거에서 고른 기간과 무관).
export const B_FLOW_PERIOD = "6M";

// 판단 근거 미리보기 요청 — 이 화면의 공통 기간 목록 · 화면이 본 쪽 · 순위 · 날짜 · 가격 시점(서버가 대조).
export function commonPeriodQuery(s: CompareSummaryOk, row: CompareRow, side: "top" | "bottom", screen: DecisionDraftScreen) {
  return {
    list_source: "common_period" as const,
    screen,
    basis: s.basis,
    ...s.filters,
    side,
    rank: row.rank,
    start_date: row.basis_return.start,
    end_date: row.basis_return.end,
    end_price_state: row.end_price.state,
    basis_value: row.basis_return.value,
  };
}

// 보유 판단 근거 요청 — 이 화면 조건만(서버가 그 조건의 공통 기간 목록으로 후보 관계를 확인 · 판정 Q4-2 둘째 항목).
export function holdingScopeQuery(screen: DecisionDraftScreen, cond: CompareCondition) {
  return { list_source: "common_period" as const, screen, basis: cond.basis, ...cond.filters };
}

export default function EtfRowDetail({
  row,
  s,
  side,
  screen,
  onNavigate,
}: {
  row: CompareRow;
  s: CompareSummaryOk;
  side: "top" | "bottom";
  screen: DecisionDraftScreen;
  onNavigate?: (key: MenuKey) => void;
}) {
  const detail = useEtfDetail([row.ticker]);
  const item = detailOf(detail, row.ticker);
  const stateText = detailStateText(detail, row.ticker);
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
        {item ? (
          <DetailLines it={item} />
        ) : (
          <>
            <dt>상세 수치</dt>
            <dd data-testid="ec-detail-state">{stateText}</dd>
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
      <DecisionDraftPreviewCard
        targetKind="candidate"
        ticker={row.ticker}
        displayName={row.name ?? row.ticker}
        listQuery={commonPeriodQuery(s, row, side, screen)}
        screenFilters={s.filters}
        rank={row.rank}
        onNavigate={onNavigate}
        flowPeriod={B_FLOW_PERIOD}
      />
    </div>
  );
}
