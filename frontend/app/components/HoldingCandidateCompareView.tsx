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
// POC6-31 STEP 4 ~ 5(PLAN C21 ~ C25 · 판정 Q12 · Q13) — 「종목별 근거」의 '구성종목 겹침' 자리를 '구성종목 비교'(후보 주요 주식마다
// 후보 비중 · 고른 보유 비중 · 내 보유 전체의 확인된 노출 · 확인 범위 먼저)로 바꾸고, 후보 판단 근거 미리보기는 이 비교의 근거 지문과
// 같을 때만 만든다. 고른 후보 · 보유가 다시 불러온 목록에 없으면 다른 종목으로 바꾸지 않고 다시 고르라고 보인다.
// 읽기 전용 · 새 점수 · 등급 · 매매 신호 없음.

import { useState } from "react";
import { fetchEnrichedHoldings, type EnrichedHoldingsResult } from "@/lib/api";
import type { CompareCondition, CompareRow, CompareSummaryOk } from "@/lib/api/etfCompare";
import { invalidateQueries, useSharedQuery } from "@/lib/api/queryCache";
import { ETF_DETAIL_KEY_PREFIX, WB_KEY_HOLD } from "@/lib/api/dashboardKeys";
import { BASIS_LABEL, md, pct, weightText } from "@/lib/etfCompare";
import type { MenuKey } from "./LeftSidebar";
import DecisionDraftPreviewCard from "./holdings_compare/DecisionDraftPreviewCard";
import { BasisSaveRow, CompareLines, ConditionPanel, SummaryStatus, okSummary, useEtfCompareSummary } from "./workbench/CompareHead";
import { CompareBasic, CompareEvidence, type CompareHeadInfo } from "./workbench/CompareCards";
import { detailOf, detailStateText, useEtfDetail } from "./workbench/DetailNumbers";
import { B_FLOW_PERIOD, commonPeriodQuery, holdingScopeQuery } from "./workbench/EtfRowDetail";
import { takePresetCandidate, takePresetHolding, type PresetCandidate } from "./workbench/compareSelection";
import { takeOneTimeCondition } from "@/lib/etfCompareCondition";
import { aggregateHoldings, linkOf, type AggHolding } from "./workbench/holdingParts";
import PairExposureBlock, { usePairExposure } from "./workbench/PairExposureBlock";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

type Pick = { side: "top" | "bottom"; ticker: string };

function byWeight(a: AggHolding, b: AggHolding): number {
  return (b.weight ?? -1) - (a.weight ?? -1) || a.ticker.localeCompare(b.ticker);
}

export default function HoldingCandidateCompareView({ onNavigate }: Props) {
  // POC6-31(판정 Q10) — 「ETF 구성종목」에서 넘긴 후보 · 그 목록 조건(이 화면이 떠 있는 동안만 · 화면 조건 · 저장된
  // 기본값은 그대로 · 사용자가 이 화면 조건을 정하면 그 값이 이긴다).
  const [presetCand] = useState(() => takePresetCandidate());
  const [once] = useState(() => takeOneTimeCondition("compare"));
  const { cond, q } = useEtfCompareSummary("compare", once);
  const hold = useSharedQuery<EnrichedHoldingsResult>(WB_KEY_HOLD, () => fetchEnrichedHoldings());
  const [panel, setPanel] = useState(false);
  const [preset] = useState<string | null>(() => takePresetHolding());
  const [holdingPick, setHoldingPick] = useState<string | null>(preset);
  const [candPick, setCandPick] = useState<Pick | null>(
    presetCand ? { side: presetCand.side, ticker: presetCand.ticker } : null,
  );
  const [focus, setFocus] = useState<"candidate" | "holding">(preset && !presetCand ? "holding" : "candidate");
  const s = okSummary(q);
  const holdings = hold.phase === "success" ? aggregateHoldings(hold.data.items).sort(byWeight) : [];
  const holdFound = holdings.find((x) => x.ticker === holdingPick) ?? null;
  // 고른(또는 넘겨받은) 보유가 다시 읽은 보유 목록에 없으면 첫 보유로 바꾸지 않는다(STEP 5 · 고른 종목 유지).
  const holdMissing = !!(hold.phase === "success" && holdingPick && !holdFound);
  const h = holdFound ?? (holdMissing ? null : (holdings[0] ?? null));
  const candList: { side: "top" | "bottom"; row: CompareRow }[] = s
    ? [...s.top.map((row) => ({ side: "top" as const, row })), ...s.bottom.map((row) => ({ side: "bottom" as const, row }))]
    : [];
  const found = candList.find((x) => candPick && x.side === candPick.side && x.row.ticker === candPick.ticker) ?? null;
  // 넘겨받은 후보가 이 조건 목록에 없으면 다른 종목으로 바꾸지 않는다(C23) — 사용자가 고를 때까지 비워 둔다.
  const presetMissing = !!(s && presetCand && candPick?.ticker === presetCand.ticker && !found);
  // 안내는 지금 고른 후보가 넘겨받은 그 후보일 때만(사용자가 다른 후보로 바꾸면 내린다).
  const presetSelected = !!(presetCand && candPick?.ticker === presetCand.ticker && candPick.side === presetCand.side);
  // 고른 후보가 지금 목록(다시 불러온 목록 · 바꾼 조회 기준의 목록)에 없으면 첫 후보로 조용히 바꾸지 않는다
  // (STEP 5 · 고른 종목 유지 · 조회 기준을 바꿔도 같은 규칙 — 결과서 §4).
  const pickMissing = !!(s && candPick && !found);
  const c = found ?? (presetMissing || pickMissing ? null : (candList[0] ?? null));
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
  // 구성종목 비교(C21 · C22) — 이 화면 조건 · 고른 후보 · 고른 보유로 읽는다(근거 지문 = 미리보기 대조용 · C25).
  const pair = usePairExposure(
    c && s
      ? {
          candidate: c.row.ticker,
          holding: h?.ticker ?? null,
          screen: "holding_candidate_compare",
          basis: s.basis,
          side: c.side,
          rank: c.row.rank,
          start_date: c.row.basis_return.start,
          end_date: c.row.basis_return.end,
          filters: { ...s.filters },
        }
      : null,
  );
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
            // 지금 보이는 후보 · 보유를 고른 것으로 고정한 뒤 다시 읽는다 — 고르지 않고 보던 첫 종목도 목록이 바뀌면
            // 다른 종목으로 조용히 넘어가지 않고 '다시 고르세요'(검토 지적 frontend#0 · 서버 안내 '고른 보유 · 후보는 그대로').
            if (c && !candPick) setCandPick({ side: c.side, ticker: c.row.ticker });
            if (h && !holdingPick) setHoldingPick(h.ticker);
            invalidateQueries(ETF_DETAIL_KEY_PREFIX);
            q.reload();
            hold.reload();
            // 지운 상세 칸은 같은 키로 스스로 다시 읽지 않는다 — 이 두 종목을 바로 다시 읽는다(검토 지적).
            if (tickers.length > 0) detail.reload();
            pair.reload();
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

      {presetCand && presetSelected ? (
        <PresetNotice p={presetCand} missing={presetMissing} onceActive={!!once && cond === once.cond} cond={cond} s={s} />
      ) : null}
      {holdMissing ? (
        <p className="wb-warn" data-testid="hcc-holding-missing">
          고른 보유가 지금 보유 목록에 없습니다 — 보유를 다시 고르세요(다른 종목으로 바꾸지 않았습니다)
        </p>
      ) : null}
      {pickMissing && !presetSelected ? (
        <p className="wb-warn" data-testid="hcc-pick-missing">
          고른 후보가 지금 이 조건 목록에 없습니다 — 후보를 다시 고르세요(다른 종목으로 바꾸지 않았습니다)
        </p>
      ) : null}
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
            {!h && holdings.length > 0 ? (
              <option value="" disabled>
                보유를 다시 고르세요
              </option>
            ) : null}
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
            {/* POC6-31(C23) — 넘겨받은 후보가 목록에 없으면 비운 채로 둔다(첫 후보가 고른 것처럼 보이지 않게). */}
            {!c && candList.length > 0 ? (
              <option value="" disabled>
                후보를 다시 고르세요
              </option>
            ) : null}
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
        cons={<PairExposureBlock q={pair} hasPick={!!c} />}
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
            pair={{
              holding: h?.ticker ?? null,
              fingerprint: pair.phase === "success" ? pair.data.fingerprint : null,
            }}
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

// POC6-31(판정 Q10 · PLAN C18 · C23) — 넘겨받은 후보 안내: 조건(이번 이동 · 넘긴 조건 없음 · 사용자가 바꿈)과 넘긴 목록의
// 시작일 · 끝일이 이 화면 목록과 같은지. 다르면 이유로 보인다(같은 것처럼 말하지 않음).
function PresetNotice({
  p,
  missing,
  onceActive,
  cond,
  s,
}: {
  p: PresetCandidate;
  missing: boolean;
  onceActive: boolean;
  cond: CompareCondition;
  s: CompareSummaryOk | null;
}) {
  const side = p.side === "top" ? "상위" : "하위";
  const condText = !p.condition
    ? `넘겨받은 조건 없음 — 이 화면 조건(${BASIS_LABEL[cond.basis]} ${side})으로 찾았습니다`
    : onceActive
      ? `이번 이동 조건 = ${BASIS_LABEL[cond.basis]} ${side}(넘긴 목록 조건 · 이 화면을 떠나면 원래 조건)`
      : `이 화면 조건(${BASIS_LABEL[cond.basis]})을 바꿔 넘긴 조건(${BASIS_LABEL[p.condition.basis]})과 다릅니다`;
  const dateDiff = !!(s && p.start && p.end && (p.start !== s.period.start || p.end !== s.end_date));
  const dateText =
    s && p.start && p.end
      ? dateDiff
        ? `넘긴 목록(${md(p.start)} → ${md(p.end)})과 이 화면 목록(${md(s.period.start)} → ${md(s.end_date)})의 날짜가 다릅니다 — 순위 · 수익률은 이 화면 목록 기준입니다`
        : `목록 날짜 ${md(p.start)} → ${md(p.end)} 같음`
      : null;
  const name = p.name ?? p.ticker;
  return (
    <p className={missing || dateDiff || (p.condition && !onceActive) ? "wb-warn" : "ec-small"} data-testid="hcc-preset-candidate">
      {missing
        ? `「ETF 구성종목」에서 고른 ${name}은(는) 이 조건 목록에 없습니다 — 목록을 다시 읽거나 후보를 다시 고르세요`
        : `「ETF 구성종목」에서 고른 후보로 열렸습니다`}
      {` · ${condText}`}
      {dateText ? ` · ${dateText}` : ""}
    </p>
  );
}
