"use client";

// POC6-28 — 「보유」 행 바로 아래 상세(PLAN §2-6 · §3-4 · §3-5 · 판정 §4).
// 한 줄씩 이름을 나눠 적는다: 최근 가격 변화 · 같은 기간 KODEX 200 · 후보 조회 기간 · 월간 수익률 · 약세 묶음 접점 ·
// 가격 기준일 · 현재가 · 평가액.
//
// 검증자 r2 F4: 가격 흐름 값 · 하락 판정 · 저장 상태(장중 · 마감 뒤)는 **비교 요약 한 응답**(`price_flow` · 같은 DB
// 읽기 · 보유 근거와 같은 기존 함수)에서만 읽는다. 다른 시점에 읽은 보유 근거 응답에 이 응답의 저장 상태를 붙이지
// 않는다. 비교 요약을 못 받았을 때만 보유 근거 값을 '저장 상태 확인 불가'와 함께 적는다.
// 검증자 r3 F5: 값이 없을 때는 이유를 출처별로 적는다(요약 없음 / 요약에 이 종목 없음 / 보유 근거 실패 · 확인 중 · 종목 없음).
// POC6-29(PLAN §2-3 · §2-7 · 판정 Q4-1) — 상세 수치(1 · 3 · 6 · 12개월 · 20구간 KODEX 200 차이 · 시장가 · NAV · 괴리율 등 ·
//   후보 화면과 같은 응답 · 같은 정의)를 넣고, 예전 '월간 수익률(보유 근거)' 줄은 뺐다(1개월이 정의가 다른 두 값으로
//   보이지 않게 · 설계 §4). 판단 근거 미리보기(보유) · [보유와 후보 비교에서 보기 →]를 둔다.

import type { HoldingsMarketEvidenceItem } from "@/lib/api";
import type { CompareSummaryOk, HoldingLink, PriceFlow } from "@/lib/api/etfCompare";
import { candidateLinkText, endPriceText, exposureText, md, pct, priceStateShort } from "@/lib/etfCompare";
import { fmtAmountSummary, fmtIndex } from "./helpers";
import PriceChart from "./PriceChart";
import DecisionDraftPreviewCard from "../holdings_compare/DecisionDraftPreviewCard";
import { DetailLines, detailOf, detailStateText, useEtfDetail } from "./DetailNumbers";
import { B_FLOW_PERIOD, holdingScopeQuery } from "./EtfRowDetail";
import { presetCompareHolding } from "./compareSelection";
import { ETF_COMPARE_DEFAULT, getScreenCondition } from "@/lib/etfCompareCondition";
import {
  PartialMark,
  evMissingText,
  hasFlowField,
  sumLinksOf,
  sumMissingText,
  type AggHolding,
  type EvPhase,
} from "./holdingParts";
import type { MenuKey } from "../LeftSidebar";

type Flow = Pick<
  PriceFlow,
  "end_date" | "start_date_5d" | "start_date_20d" | "comparison" | "status" | "return_5d_pct" | "return_20d_pct"
>;

function changeText(f: Flow): string {
  if (!f.end_date) return "가격 변화 없음(저장 가격 없음)";
  if (f.comparison === "date_mismatch") return `기준일이 PC 비교 기준일과 달라 비교하지 않음(이 종목 끝일 ${md(f.end_date)})`;
  if (f.status !== "ok") return "가격 변화 없음(20저장일 이력 부족)";
  const five =
    f.return_5d_pct != null && f.start_date_5d
      ? `5거래일 ${md(f.start_date_5d)} → ${md(f.end_date)} ${pct(f.return_5d_pct)}`
      : "5거래일 값 없음";
  const twenty =
    f.return_20d_pct != null && f.start_date_20d
      ? `20거래일 ${md(f.start_date_20d)} → ${md(f.end_date)} ${pct(f.return_20d_pct)}`
      : "20거래일 값 없음";
  return `${five} · ${twenty}`;
}

// 요약에서 가격 흐름을 못 읽은 이유 — 이 종목 연결은 있는데 가격 흐름 칸이 없는 경우를 따로 적는다.
function flowMissingText(link: HoldingLink | undefined, s: CompareSummaryOk | null): string {
  return link ? "비교 요약에 가격 흐름 없음" : sumMissingText(sumLinksOf(s));
}

// 보유 근거 값에 붙이는 출처 표시 — 이전 조회값이면 그것도 적는다.
function evTag(evPhase: EvPhase): string {
  return evPhase === "stale" ? "보유 근거 이전 조회값 · 저장 상태 확인 불가" : "보유 근거 · 저장 상태 확인 불가";
}

function recentChange(
  link: HoldingLink | undefined,
  ev: HoldingsMarketEvidenceItem | undefined,
  s: CompareSummaryOk | null,
  evPhase: EvPhase,
): string {
  if (hasFlowField(link)) return link.price_flow ? changeText(link.price_flow) : "가격 변화 없음(저장 가격 없음)";
  const m = ev?.short_term_momentum;
  const pd = ev?.price_dates;
  const sm = flowMissingText(link, s);
  if (!ev) return `가격 변화 없음(${sm} · ${evMissingText(evPhase)})`;
  if (!m || !pd) return `가격 변화 없음(${sm} · 보유 근거에 가격 변화 없음)`;
  return `${changeText({ ...pd, status: m.status, return_5d_pct: m.return_5d_pct, return_20d_pct: m.return_20d_pct })}(${evTag(evPhase)})`;
}

// 세 숫자(이 종목 · KODEX 200 · 차이)는 같은 응답 · 같은 저장 행에서 — 차이에서 KODEX 200 을 되돌려 만들지 않는다.
function sameKodex(link: HoldingLink | undefined, s: CompareSummaryOk | null): string {
  const f = link?.price_flow;
  if (!hasFlowField(link)) return `${flowMissingText(link, s)} — 보이지 않음`;
  if (!f) return "같은 기간 비교 자료 없음(저장 가격 없음)";
  if (f.excess_vs_kodex200_20d_pctp == null || f.return_20d_pct == null || f.kodex200_return_20d_pct == null) {
    if (f.comparison === "window_mismatch") return "KODEX 200 비교 기간이 달라 비교하지 않음";
    if (f.comparison === "date_mismatch") return "기준일이 PC 비교 기준일과 달라 비교하지 않음";
    return "같은 기간 비교 자료 없음";
  }
  return (
    `${md(f.start_date_20d)} → ${md(f.end_date)} · 이 종목 ${pct(f.return_20d_pct)} · ` +
    `KODEX 200 ${pct(f.kodex200_return_20d_pct)} · 차이 ${pct(f.excess_vs_kodex200_20d_pctp, "%p")}`
  );
}

function datesLine(
  link: HoldingLink | undefined,
  ev: HoldingsMarketEvidenceItem | undefined,
  s: CompareSummaryOk | null,
  evPhase: EvPhase,
): string {
  const f = link?.price_flow;
  if (!s || !hasFlowField(link)) {
    const sm = flowMissingText(link, s);
    const end = ev?.price_dates?.end_date;
    if (!end) return `가격 기준일 확인 불가(${sm} · ${ev ? "보유 근거에 날짜 없음" : evMissingText(evPhase)})`;
    return `${evPhase === "stale" ? "보유 근거(이전 조회값)" : "보유 근거"} ${md(end)} 가격 = 저장 상태 확인 불가(${sm})`;
  }
  if (!f) return `후보 근거 ${md(s.period.end)} 가격 = ${priceStateShort(s.price_state)} · 이 종목 저장 가격 없음`;
  const mine = `${md(f.end_date)} 가격 = ${endPriceText(f.end_price)}`;
  if (f.end_date === s.period.end) return `후보 · 보유 가격 흐름 모두 ${mine}`;
  return (
    `후보 근거 ${md(s.period.end)} 가격 = ${priceStateShort(s.price_state)} · ` +
    `보유 가격 흐름 ${mine} — 기준일이 달라 두 근거를 따로 봅니다`
  );
}

export default function HoldingRowDetail({
  row,
  ev,
  evPhase,
  link,
  s,
  onNavigate,
}: {
  row: AggHolding;
  ev: HoldingsMarketEvidenceItem | undefined;
  evPhase: EvPhase;
  link: HoldingLink | undefined;
  s: CompareSummaryOk | null;
  onNavigate: (k: MenuKey) => void;
}) {
  const detail = useEtfDetail([row.ticker]);
  const item = detailOf(detail, row.ticker);
  const noLink = `후보 비교 자료 없음(${sumMissingText(sumLinksOf(s))})`;
  return (
    <div className="ec-detail" data-testid="ec-hold-detail">
      <dl className="ec-lines">
        <dt>최근 가격 변화</dt>
        <dd data-testid="ec-hold-recent">{recentChange(link, ev, s, evPhase)}</dd>
        <dt>같은 기간 KODEX 200</dt>
        <dd data-testid="ec-hold-kodex">{sameKodex(link, s)}</dd>
        <dt>후보 조회 기간</dt>
        <dd data-testid="ec-hold-candidate">{s && link ? candidateLinkText(link, s) : noLink}</dd>
        {item ? (
          <DetailLines it={item} omitWindows />
        ) : (
          <>
            <dt>상세 수치</dt>
            <dd data-testid="ec-detail-state">{detailStateText(detail, row.ticker)}</dd>
          </>
        )}
        <dt>약세 묶음 접점</dt>
        <dd data-testid="ec-hold-exposure">
          {!link ? (
            noLink
          ) : link.is_stock ? (
            <>
              개별 주식 — NAV · ETF 구성종목 해당 없음
              {link.exposure.status === "ok" ? ` · ${exposureText(link)}` : ""}
            </>
          ) : (
            <>
              {link.side === "bottom" ? `직접 — 후보 하위 ${link.side_rank}위 · ` : ""}
              {exposureText(link)}
              {link.exposure.status === "no_constituents" && (
                <button type="button" className="wb-btn ec-inline" onClick={() => onNavigate("etf_exposure")}>
                  ETF 구성종목에서 확인 →
                </button>
              )}
            </>
          )}
        </dd>
        <dt>가격 기준일</dt>
        <dd data-testid="ec-hold-dates">{datesLine(link, ev, s, evPhase)}</dd>
        <dt>현재가 · 평가액</dt>
        <dd>
          현재 {row.currentPrice == null ? "—" : fmtIndex(row.currentPrice)} · 평가액{" "}
          {row.evalOk === 0 ? "확인 불가" : fmtAmountSummary(row.evalAmount)}
          <PartialMark ok={row.evalOk} count={row.count} />
        </dd>
      </dl>
      <PriceChart ticker={row.ticker} valueLabel="저장 가격" compact />
      <div className="ec-btn-row">
        <button
          type="button"
          className="wb-btn btn-md"
          onClick={() => {
            presetCompareHolding(row.ticker);
            onNavigate("holding_candidate_compare");
          }}
        >
          보유와 후보 비교에서 보기 →
        </button>
        <button type="button" className="wb-btn btn-md" onClick={() => onNavigate("holdings")}>
          보유 현황 보기 →
        </button>
      </div>
      <DecisionDraftPreviewCard
        targetKind="holding"
        ticker={row.ticker}
        displayName={row.name ?? row.ticker}
        screenFilters={s?.filters ?? ETF_COMPARE_DEFAULT.filters}
        listQuery={holdingScopeQuery("holdings", s ? { basis: s.basis, filters: s.filters } : getScreenCondition("holdings"))}
        onNavigate={onNavigate}
        flowPeriod={B_FLOW_PERIOD}
      />
    </div>
  );
}
