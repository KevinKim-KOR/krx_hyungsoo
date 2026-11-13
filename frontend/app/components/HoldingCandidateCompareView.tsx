"use client";

// POC6-29(PLAN §2-6 · 판정 Q1 · Q4-1 · Q4-2 · Q10 · 2026-11-12) — 「ETF보유 및 후보 선정 › 보유와 후보 비교」.
// C 「요즘 잘 오르는 ETF › 보유와 비교」 탭이 하던 일을 옮겼다:
// - 위에서 보유 하나(보유 · 비중 큰 순)와 후보 하나(이 화면 조건의 공통 기간 상 · 하위 30)를 고른다.
// - 선택한 쪽의 판단 근거 미리보기 → [AI 세션에서 검토](후보는 이 화면 목록에서 찾음 · 보유는 보유 종목으로).
// 보완 2차 S3(PLAN §10-6 · 목업 S3 · S 판정 Q-S6 · RESULT 재판정 V2 §4) — 기본 비교와 종목별 근거:
// - 고르기 두 칸 아래 기본 비교(표 하나 · 왼쪽 보유 · 오른쪽 후보): 1개월 · 3개월(같은 기간 KODEX 200 대비) ·
//   최근 5 · 20구간 · 고점 대비 — 항목마다 두 값(실제 기간) + 차이 또는 비교하지 않는 이유
//   (두 쪽 시작 · 끝일과 확인된 가격 상태가 같을 때만 차이).
// - 그 아래 종목별 근거(후보 · 보유 탭 하나): 시장가 · NAV · 괴리율 · 6 · 12개월 · 20구간 KODEX 200 차이 ·
//   하락 판정 · 구성종목 겹침 → 판단 근거 미리보기 → [AI 세션에서 검토](R3 의 접기 3개 · 미리보기 카드를 모음).
// - 상세 수치 = 행 상세와 같은 응답 · 같은 정의 · 같은 날짜(두 종목 한 번에 읽음). 가격 상태 = 그 응답의 끝일 가격.
// 읽기 전용 · 새 점수 · 등급 · 매매 신호 없음.

import { useState } from "react";
import { fetchEnrichedHoldings, type EnrichedHoldingsResult } from "@/lib/api";
import type { CompareRow } from "@/lib/api/etfCompare";
import { invalidateQueries, useSharedQuery } from "@/lib/api/queryCache";
import { ETF_DETAIL_KEY_PREFIX, WB_KEY_HOLD } from "@/lib/api/dashboardKeys";
import { BASIS_LABEL, exposureText, md, pct, weightText } from "@/lib/etfCompare";
import type { MenuKey } from "./LeftSidebar";
import DecisionDraftPreviewCard from "./holdings_compare/DecisionDraftPreviewCard";
import { BasisSaveRow, CompareLines, ConditionPanel, SummaryStatus, okSummary, useEtfCompareSummary } from "./workbench/CompareHead";
import { CompareBasic, CompareEvidence, type CompareHeadInfo } from "./workbench/CompareCards";
import { detailOf, detailStateText, useEtfDetail } from "./workbench/DetailNumbers";
import { B_FLOW_PERIOD, commonPeriodQuery, holdingScopeQuery } from "./workbench/EtfRowDetail";
import { takePresetHolding } from "./workbench/compareSelection";
import { aggregateHoldings, linkOf, type AggHolding } from "./workbench/holdingParts";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

type Pick = { side: "top" | "bottom"; ticker: string };

function byWeight(a: AggHolding, b: AggHolding): number {
  return (b.weight ?? -1) - (a.weight ?? -1) || a.ticker.localeCompare(b.ticker);
}

export default function HoldingCandidateCompareView({ onNavigate }: Props) {
  const { cond, q } = useEtfCompareSummary("compare");
  const hold = useSharedQuery<EnrichedHoldingsResult>(WB_KEY_HOLD, () => fetchEnrichedHoldings());
  const [panel, setPanel] = useState(false);
  const [preset] = useState<string | null>(() => takePresetHolding());
  const [holdingPick, setHoldingPick] = useState<string | null>(preset);
  const [candPick, setCandPick] = useState<Pick | null>(null);
  const [focus, setFocus] = useState<"candidate" | "holding">(preset ? "holding" : "candidate");
  const s = okSummary(q);
  const holdings = hold.phase === "success" ? aggregateHoldings(hold.data.items).sort(byWeight) : [];
  const h = holdings.find((x) => x.ticker === holdingPick) ?? holdings[0] ?? null;
  const candList: { side: "top" | "bottom"; row: CompareRow }[] = s
    ? [...s.top.map((row) => ({ side: "top" as const, row })), ...s.bottom.map((row) => ({ side: "bottom" as const, row }))]
    : [];
  const c =
    candList.find((x) => candPick && x.side === candPick.side && x.row.ticker === candPick.ticker) ?? candList[0] ?? null;
  const tickers = [h?.ticker, c?.row.ticker].filter((t): t is string => !!t);
  const detail = useEtfDetail(tickers);
  const hd = h ? detailOf(detail, h.ticker) : null;
  const cd = c ? detailOf(detail, c.row.ticker) : null;
  const link = h ? linkOf(s, h.ticker) : undefined;
  const flow = link?.price_flow ?? null;
  const band = flow?.decline_band;
  const holdingNote = h
    ? detailStateText(detail, h.ticker)
    : hold.phase === "error"
      ? "보유 목록을 읽지 못해 고를 보유가 없습니다"
      : hold.phase === "success"
        ? "고를 보유가 없습니다"
        : "보유 목록 확인 중...";
  const candidateNote = c ? detailStateText(detail, c.row.ticker) : s ? "고를 후보가 없습니다" : "후보 목록 확인 중...";
  // 상세를 아직 못 읽었으면 차이 줄을 만들지 않고 그 사실만(읽는 중 · 실패 · 고른 종목 없음).
  const diffPending =
    tickers.length === 0
      ? "고른 종목이 없어 차이를 적지 않습니다"
      : detail.phase === "error"
        ? "상세 수치를 읽지 못해 차이를 적지 않습니다"
        : detail.phase !== "success"
          ? "상세 수치를 읽는 중이라 차이는 아직 적지 않습니다"
          : null;
  const holdingDecline = !h
    ? "—"
    : band?.judgeable
      ? band.state
        ? (band.label ?? "하락 구간")
        : "하락 구간 아님"
      : "판정 못 함(가격 자료 · 기준일 확인 필요)";
  const holdingExposure = !h
    ? "—"
    : link
      ? link.is_stock
        ? "개별 주식 — ETF 구성종목 해당 없음"
        : exposureText(link)
      : "비교 요약에 이 종목 없음";
  const candidateExposure = c
    ? c.row.constituents
      ? `구성 자료 ${md(c.row.constituents.asof)} · 상위 ${c.row.constituents.items.length}종목`
      : "구성 자료 없음"
    : "—";
  const holdHead: CompareHeadInfo = {
    name: h ? (h.name ?? h.ticker) : null,
    badge: h ? `보유 · 비중 ${weightText(h.weight)}${h.weightOk < h.count ? "(일부 계좌만)" : ""}` : null,
    note: holdingNote,
  };
  const candHead: CompareHeadInfo = {
    name: c ? (c.row.name ?? c.row.ticker) : null,
    badge: c ? `후보 · ${BASIS_LABEL[s?.basis ?? "one_month"]} ${c.side === "top" ? "상위" : "하위"} ${c.row.rank}위` : null,
    note: candidateNote,
  };

  return (
    <section aria-labelledby="hcc-h" className="wb-root ec-root">
      <div className="ec-head">
        <h1 id="hcc-h">보유와 후보 비교</h1>
        <button type="button" className="wb-btn btn-md" aria-expanded={panel} onClick={() => setPanel(!panel)}>
          조회 기준
        </button>
        <button
          type="button"
          className="wb-btn btn-md"
          onClick={() => {
            invalidateQueries(ETF_DETAIL_KEY_PREFIX);
            q.reload();
            hold.reload();
            // 지운 상세 칸은 같은 키로 스스로 다시 읽지 않는다 — 이 두 종목을 바로 다시 읽는다(검토 지적).
            if (tickers.length > 0) detail.reload();
          }}
        >
          다시 불러오기
        </button>
      </div>
      {panel && (
        <ConditionPanel
          screen="compare"
          cond={cond}
          onClose={() => setPanel(false)}
          applies="「보유와 후보 비교」 후보 고르기 목록(상·하위 30)"
        />
      )}
      <BasisSaveRow screen="compare" basis={cond.basis} />
      <SummaryStatus q={q} />
      {s && <CompareLines s={s} stale={q.phase === "success" && q.stale} showRegime={false} />}

      <div className="hcc-pick">
        <label className="hcc-box">
          <span className="ec-small">보유에서 고르기 · 비중 큰 순</span>
          <select
            value={h?.ticker ?? ""}
            onChange={(e) => {
              setHoldingPick(e.target.value);
              setFocus("holding");
            }}
            disabled={holdings.length === 0}
            data-testid="hcc-holding"
          >
            {holdings.map((x) => (
              <option key={x.ticker} value={x.ticker}>
                {x.name ?? x.ticker} · 비중 {weightText(x.weight)}
              </option>
            ))}
          </select>
          {hold.phase === "error" && <span className="wb-warn">보유를 불러오지 못했습니다</span>}
        </label>
        <label className="hcc-box">
          <span className="ec-small">후보에서 고르기 · 이 화면 조건의 상·하위 30</span>
          <select
            value={c ? `${c.side}:${c.row.ticker}` : ""}
            onChange={(e) => {
              const [side, ticker] = e.target.value.split(":");
              setCandPick({ side: side as "top" | "bottom", ticker });
              setFocus("candidate");
            }}
            disabled={candList.length === 0}
            data-testid="hcc-candidate"
          >
            {candList.map((x) => (
              <option key={`${x.side}:${x.row.ticker}`} value={`${x.side}:${x.row.ticker}`}>
                {x.side === "top" ? "상위" : "하위"} {x.row.rank}위 · {x.row.name ?? x.row.ticker} · {pct(x.row.basis_return.value)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <CompareBasic hold={hd} cand={cd} holdHead={holdHead} candHead={candHead} pending={diffPending} />

      <CompareEvidence
        focus={focus}
        onFocus={setFocus}
        hold={hd}
        cand={cd}
        holdHead={holdHead}
        candHead={candHead}
        holdingDecline={holdingDecline}
        holdingExposure={holdingExposure}
        candidateExposure={candidateExposure}
      >
        {focus === "candidate" && c && s ? (
          <DecisionDraftPreviewCard
            targetKind="candidate"
            ticker={c.row.ticker}
            displayName={c.row.name ?? c.row.ticker}
            listQuery={commonPeriodQuery(s, c.row, c.side, "holding_candidate_compare")}
            screenFilters={s.filters}
            rank={c.row.rank}
            onNavigate={onNavigate}
            flowPeriod={B_FLOW_PERIOD}
          />
        ) : focus === "holding" && h ? (
          <DecisionDraftPreviewCard
            targetKind="holding"
            ticker={h.ticker}
            displayName={h.name ?? h.ticker}
            screenFilters={cond.filters}
            listQuery={holdingScopeQuery("holding_candidate_compare", s ? { basis: s.basis, filters: s.filters } : cond)}
            onNavigate={onNavigate}
            flowPeriod={B_FLOW_PERIOD}
          />
        ) : (
          <div className="ec-small">고를 종목이 없습니다.</div>
        )}
      </CompareEvidence>
    </section>
  );
}
