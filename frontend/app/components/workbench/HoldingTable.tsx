"use client";

// 「비교·판단 › ETF 비교하기 › 보유」 목록(POC3-02 §7.6 보유 표 → POC6-28 개편 · PLAN §2-6 · 판정 §4).
//
// 기본 행 = 종목명 · 보유 내 비중 · 매입 대비 손익(같은 ticker 다계좌는 한 행 · 부분 집계 표기는 기존 그대로).
// 배지는 서로 다른 뜻을 섞지 않는다:
//   기존 하락 판정(`decline_band` · 기존 문구) / 점검 사유(직접 하위권 + 그 기간 수익률 음수) /
//   노출 확인(구성종목 겹침) / 비교 자료 부족(구성 자료 없는 ETF · 가격 비교 날짜 문제 · 비교 목록 밖).
// 개별 주식은 'NAV · ETF 구성종목 해당 없음'이라 조치 목록(비교 자료 부족)에 넣지 않는다(판정 Q6).
// 행을 누르면 그 행 바로 아래에 상세가 열린다(HoldingRowDetail).

import type { HoldingsMarketEvidenceItem } from "@/lib/api";
import type { CompareSummaryOk } from "@/lib/api/etfCompare";
import { pointReason, weightText } from "@/lib/etfCompare";
import {
  fmtAmountSummary,
  fmtSignedPct,
  directionColor,
  evidenceByTicker,
} from "./helpers";
import HoldingRowDetail from "./HoldingRowDetail";
import {
  PartialMark,
  isDecline,
  isWeakContact,
  lacksCompareData,
  linkOf,
  declineOf,
  sumLinksOf,
  type AggHolding,
  type EvPhase,
} from "./holdingParts";
import type { MenuKey } from "../LeftSidebar";

export type HoldFilter = "all" | "decline" | "weak" | "lack";

export function HoldingTable({
  rows,
  evidenceItems,
  evPhase,
  s,
  filter,
  declineFirst,
  selected,
  onSelect,
  onNavigate,
}: {
  rows: AggHolding[];
  evidenceItems: HoldingsMarketEvidenceItem[] | undefined;
  evPhase: EvPhase;
  s: CompareSummaryOk | null;
  filter: HoldFilter;
  declineFirst: boolean;
  selected: string | null;
  onSelect: (t: string | null) => void;
  onNavigate: (k: MenuKey) => void;
}) {
  const linksOk = sumLinksOf(s) === "ok";
  let list = rows.slice();
  if (filter === "decline")
    list = list.filter((r) => isDecline(linkOf(s, r.ticker), evidenceByTicker(evidenceItems, r.ticker)));
  if (filter === "weak") list = list.filter((r) => isWeakContact(linkOf(s, r.ticker)));
  if (filter === "lack")
    list = list.filter((r) => lacksCompareData(linkOf(s, r.ticker), evidenceByTicker(evidenceItems, r.ticker), linksOk));
  // 기본 = 비중 큰 순. 하락장이면 기존 하락 판정이 있는 보유를 먼저(표시 순서만 · 판정 §4 · PLAN §5).
  list.sort((a, b) => {
    if (declineFirst) {
      const da = isDecline(linkOf(s, a.ticker), evidenceByTicker(evidenceItems, a.ticker)) ? 0 : 1;
      const db = isDecline(linkOf(s, b.ticker), evidenceByTicker(evidenceItems, b.ticker)) ? 0 : 1;
      if (da !== db) return da - db;
    }
    return (b.weight ?? -1) - (a.weight ?? -1);
  });

  return (
    <div className="wb-hlist" data-testid="wb-holding-list">
      {list.map((r) => {
        const ev = evidenceByTicker(evidenceItems, r.ticker);
        const link = linkOf(s, r.ticker);
        const reason = s ? pointReason(link, s) : null;
        const isSel = selected === r.ticker;
        // 하락 배지와 그 저장 상태는 같은 응답에서 — 요약이 있으면 price_flow 와 그 끝일 행 상태,
        // 요약이 없으면 보유 근거 판정 + '저장 상태 확인 불가'(검증자 r2 F4).
        const dec = declineOf(link, ev);
        const decSuffix = !dec.state
          ? ""
          : dec.fromSummary
            ? link?.price_flow?.end_price.state === "intraday"
              ? " · 장중"
              : ""
            : " · 저장 상태 확인 불가";
        return (
          <div key={r.ticker} className="ec-hrow-wrap">
            <div
              className={`wb-hrow ec-hrow${isSel ? " sel" : ""}`}
              role="button"
              tabIndex={0}
              aria-expanded={isSel}
              data-testid="ec-hold-row"
              onClick={() => onSelect(isSel ? null : r.ticker)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(isSel ? null : r.ticker);
                }
              }}
            >
              <div className="ec-hrow-top">
                <span className="ec-etf-name">
                  {r.name ?? r.ticker}
                  {link?.is_stock && <span className="ec-tag">개별 주식</span>}
                  {r.count > 1 && <span className="wb-hb mute">{r.count}계좌 합산</span>}
                </span>
                <span className="ec-small">
                  비중{" "}
                  {r.weightOk === 0 ? (
                    "—"
                  ) : (
                    <>
                      <b>{weightText(r.weight)}</b>
                      <PartialMark ok={r.weightOk} count={r.count} />
                    </>
                  )}
                </span>
                <span className="ec-small">
                  매입 대비 손익{" "}
                  {r.pnlOk === 0 ? (
                    "확인 불가"
                  ) : (
                    <b style={{ color: directionColor(r.pnlAmount) }}>{fmtAmountSummary(r.pnlAmount)}</b>
                  )}
                  <PartialMark ok={r.pnlOk} count={r.count} />{" "}
                  {r.count > 1 ? (
                    <span className="wb-hmuted">계좌별 상이</span>
                  ) : (
                    <span style={{ color: directionColor(r.pnlRate) }}>{fmtSignedPct(r.pnlRate)}</span>
                  )}
                </span>
              </div>
              <div className="ec-badges">
                {dec.state && (
                  <span className="ec-chip decline">
                    {dec.label}
                    {decSuffix}
                  </span>
                )}
                {link?.exposure.status === "ok" && <span className="ec-chip expo">노출 확인</span>}
                {lacksCompareData(link, ev, linksOk) && <span className="ec-chip lack">비교 자료 부족</span>}
              </div>
              {reason && (
                <div className="ec-reason" data-testid="ec-point-reason">
                  점검 사유: {reason}
                </div>
              )}
            </div>
            {isSel && (
              <HoldingRowDetail row={r} ev={ev} evPhase={evPhase} link={link} s={s} onNavigate={onNavigate} />
            )}
          </div>
        );
      })}
      {list.length === 0 && <p className="wb-muted">조건에 맞는 보유 종목 없음</p>}
    </div>
  );
}
