"use client";

// 「비교·판단 › ETF 비교하기 › 보유」(POC6-28 · PLAN §2-6 · 판정 §4 · Q6).
//
// 읽는 것: 보유(공유 키) · 보유 근거(공유 키) · 「ETF 비교하기」 요약(같은 조건 · 「후보」와 같은 응답).
// 기본 행 = 종목명 · 보유 내 비중 · 매입 대비 손익. 행을 누르면 그 행 바로 아래 상세.
// 시장 국면은 표시 순서만 바꾼다(하락장 = 기존 하락 판정 보유 먼저). 읽기 전용 · 새 경고 기준 없음.

import { useState } from "react";
import {
  fetchEnrichedHoldings,
  fetchHoldingsMarketEvidence,
  type EnrichedHoldingsResult,
  type HoldingsMarketEvidenceResponse,
} from "@/lib/api";
import { invalidateQueries, useSharedQuery } from "@/lib/api/queryCache";
import { PRICE_SERIES_KEY_PREFIX, WB_KEY_EVID, WB_KEY_HOLD } from "@/lib/api/dashboardKeys";
import { regimeView, weightText } from "@/lib/etfCompare";
import type { MenuKey } from "./LeftSidebar";
import {
  CompareLines,
  ConditionPanel,
  SummaryStatus,
  okSummary,
  useEtfCompareSummary,
} from "./workbench/CompareHead";
import { HoldingTable, type HoldFilter } from "./workbench/HoldingTable";
import {
  aggregateHoldings,
  type AggHolding,
  type EvPhase,
  declineJudged,
  evidenceNotice,
  hasFlowField,
  sumLinksOf,
  sumMissingText,
  isDecline,
  isWeakContact,
  lacksCompareData,
  linkOf,
} from "./workbench/holdingParts";
import { evidenceByTicker } from "./workbench/helpers";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

// 하락장 머리말의 하락 보유 수 · 비중 — 비중은 모든 계좌 값이 확인된 종목만 더하고, 일부만 확인되면 그 범위를 적는다.
// unjudged = 하락 판정을 못 한 보유 수(판정 자료 없음 · 이력 부족 · 기준일 다름 등) — '하락 아님'으로 세지 않았음을 적는다.
export function declineWeightLine(declineRows: AggHolding[] | null, unjudged = 0): string {
  if (declineRows === null) return "보유 · 가격 흐름 자료를 읽지 못해 하락 판정 수와 비중을 셀 수 없습니다";
  const n = declineRows.length;
  const tail = unjudged > 0 ? ` · 하락 판정을 못 한 보유 ${unjudged}종목은 세지 않음` : "";
  if (n === 0) return `기존 하락 판정 0종목${tail}`;
  const known = declineRows.filter((r) => r.weight != null && r.weightOk === r.count);
  const sum = known.reduce((acc, r) => acc + (r.weight as number), 0);
  if (known.length === 0) return `기존 하락 판정 ${n}종목 · 보유 비중 확인 불가${tail}`;
  if (known.length < n)
    return `기존 하락 판정 ${n}종목 · 보유 비중 ${weightText(sum)}(${n}종목 중 ${known.length}종목만 확인)${tail}`;
  return `기존 하락 판정 ${n}종목 · 보유 비중 ${weightText(sum)}${tail}`;
}

export default function WorkbenchHoldingsView({ onNavigate }: Props) {
  const { cond, q } = useEtfCompareSummary();
  const hold = useSharedQuery<EnrichedHoldingsResult>(WB_KEY_HOLD, () => fetchEnrichedHoldings());
  const evid = useSharedQuery<HoldingsMarketEvidenceResponse>(WB_KEY_EVID, () => fetchHoldingsMarketEvidence());
  const [panel, setPanel] = useState(false);
  const [filter, setFilter] = useState<HoldFilter>("all");
  const [selected, setSelected] = useState<string | null>(null);
  const s = okSummary(q);
  const evItems = evid.phase === "success" ? evid.data.holdings : undefined;
  const rows = hold.phase === "success" ? aggregateHoldings(hold.data.items) : [];
  const rv = s ? regimeView(s.regime, s.end_date, s.both_side_sectors) : null;
  const declineFirst = !!rv?.holdingsDeclineFirst;

  // 개수 · 비중은 확인한 자료로만 센다 — 조회 실패 · 결측을 0종목 · 0% 로 바꾸지 않는다(검증자 r1 F2).
  const holdOk = hold.phase === "success";
  const evOk = evid.phase === "success";
  const evPhase: EvPhase = evOk ? (evid.stale ? "stale" : "ok") : evid.phase === "error" ? "error" : "loading";
  // 요약의 보유 연결 = 요약이 있고 그 응답이 보유를 읽었을 때만(요약 없음 · 보유 못 읽음과 구분).
  const sl = sumLinksOf(s);
  const linksOk = sl === "ok";
  // 연결은 있는데 그 응답에 가격 흐름이 없는 보유 수(종목 없음 · 가격 흐름 칸 없음).
  const missingInSummary = holdOk && linksOk ? rows.filter((r) => !hasFlowField(linkOf(s, r.ticker))).length : 0;
  // 하락 판정 = 요약 price_flow(칸 있으면) · 없으면 보유 근거 — 실제로 판정한(judgeable) 보유만 센다.
  // 판정 못 한 보유는 '하락 아님'으로 세지 않고 따로 적는다 · 모두 판정 못 했으면 셀 수 없음('—')(검증자 F6).
  const unjudgedOf = (r: AggHolding) => !declineJudged(linkOf(s, r.ticker), evidenceByTicker(evItems, r.ticker));
  const anyJudged = rows.length === 0 || rows.some((r) => !unjudgedOf(r));
  const declineRows =
    holdOk && (linksOk || evOk) && anyJudged
      ? rows.filter((r) => isDecline(linkOf(s, r.ticker), evidenceByTicker(evItems, r.ticker)))
      : null;
  const unjudged = declineRows ? rows.filter(unjudgedOf).length : 0;
  // 약세 묶음 접점 · 비교 자료 부족은 요약 연결이 있어야 전부 셀 수 있다(없으면 '—' · 확인된 날짜 문제 배지만).
  const counts: Record<HoldFilter, number | null> = {
    all: holdOk ? rows.length : null,
    decline: declineRows ? declineRows.length : null,
    weak: holdOk && linksOk ? rows.filter((r) => isWeakContact(linkOf(s, r.ticker))).length : null,
    lack:
      holdOk && linksOk
        ? rows.filter((r) => lacksCompareData(linkOf(s, r.ticker), evidenceByTicker(evItems, r.ticker), true)).length
        : null,
  };
  const declineLine = declineWeightLine(declineRows, unjudged);
  const evNotice = evidenceNotice(evPhase, sl, missingInSummary, holdOk);
  const stocks = linksOk && s ? s.holdings.items.filter((h) => h.is_stock).length : 0;
  const reloadAll = () => {
    // 열린 행을 닫고 차트 캐시를 지운다 — 다음에 열 때 새 저장 가격을 읽는다(공유 조회는 지운 키를 스스로 다시 읽지 않음).
    setSelected(null);
    invalidateQueries(PRICE_SERIES_KEY_PREFIX);
    q.reload();
    hold.reload();
    evid.reload();
  };

  return (
    <section aria-labelledby="wbh-h" className="wb-root ec-root">
      <div className="ec-head">
        <h1 id="wbh-h">ETF 비교하기 · 보유</h1>
        <button type="button" className="wb-btn btn-md" aria-expanded={panel} onClick={() => setPanel(!panel)}>
          조회 기준
        </button>
        <button type="button" className="wb-btn btn-md" onClick={reloadAll}>
          다시 불러오기
        </button>
        <button type="button" className="wb-btn btn-md" onClick={() => onNavigate("holdings")}>
          보유 현황 보기 →
        </button>
      </div>
      {panel && <ConditionPanel cond={cond} onClose={() => setPanel(false)} />}

      <SummaryStatus q={q} />
      {s && <CompareLines s={s} stale={q.phase === "success" && q.stale} showRegime={false} />}
      {rv && (
        <div className={rv.ok ? "ec-regime" : "ec-regime check"} data-testid="ec-hold-regime">
          {rv.ok
            ? `${rv.line.split(" — ")[0]} — ${
                declineFirst ? `최근 하락한 보유부터 보여 줍니다 · ${declineLine}` : "비중 큰 순으로 보여 줍니다"
              }`
            : rv.line}
        </div>
      )}

      {hold.phase === "error" && <p className="wb-danger">보유 확인 실패</p>}
      {hold.phase === "success" && hold.stale && (
        <p className="wb-warn" data-testid="ec-hold-stale">
          보유 다시 조회 실패 — 아래 보유 목록 · 비중 · 손익은 이전 조회값입니다(최신 아님).
        </p>
      )}
      {evNotice && (
        <p className="wb-warn" data-testid="ec-ev-notice">
          {evNotice}
        </p>
      )}
      {hold.phase === "success" && (
        <>
          <div className="wb-filters" role="group" aria-label="보유 거르기">
            {(
              [
                ["all", "전체"],
                ["decline", "최근 하락"],
                ["weak", "약세 묶음 접점"],
                ["lack", "비교 자료 부족"],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                type="button"
                className={filter === k ? "wb-filter wb-filter-active" : "wb-filter"}
                aria-pressed={filter === k}
                onClick={() => {
                  setFilter(k);
                  setSelected(null);
                }}
              >
                {label} {counts[k] ?? "—"}
              </button>
            ))}
          </div>
          <div className="ec-small" data-testid="ec-hold-filter-note">
            최근 하락 = 기존 하락 판정(PC 20저장일) · 약세 묶음 접점 = 후보 하위권 직접 또는 구성종목 겹침 · 비교 자료 부족
            = 구성 자료 없는 ETF · 가격 비교 날짜 문제 · 비교 목록 밖{stocks ? ` · 개별 주식 ${stocks}종목은 해당 없음이라 넣지 않음` : ""}
            {!linksOk &&
              ` · ${sumMissingText(sl)} — 약세 묶음 접점 · 비교 자료 부족은 셀 수 없어 '—'(가격 비교 날짜 문제가 확인된 행만 배지)`}
          </div>
          {unjudged > 0 && (
            <div className="ec-small" data-testid="ec-hold-unjudged">
              하락 판정을 못 한 보유 {unjudged}종목 — 가격 자료 없음 · 이력 부족 · 기준일 다름 등으로 판정하지 않아 최근
              하락 숫자에 넣지 않았습니다.
            </div>
          )}
          <HoldingTable
            rows={rows}
            evidenceItems={evItems}
            evPhase={evPhase}
            s={s}
            filter={filter}
            declineFirst={declineFirst}
            selected={selected}
            onSelect={setSelected}
            onNavigate={onNavigate}
          />
        </>
      )}
      {hold.phase === "loading" && <p className="wb-muted">보유 확인 중...</p>}
    </section>
  );
}
