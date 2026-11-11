"use client";

// 「비교·판단 › ETF 비교하기 › 후보」(POC3-02 UI-2 Judgment Workbench → POC6-28 개편 · 2026-11-11).
//
// POC6-28(PLAN docs/ai_plan/POC6/POC6_28_ETF_COMPARISON_SECTOR_AND_HOLDINGS_PLAN_V1.md · 판정 2026-11-11):
// - 한 응답(GET /market/etf-compare/summary)으로 [섹터 요약](첫 화면) · [ETF 순위]를 함께 그린다(판정 Q9 (a)).
// - 같은 조건 · 공통 기간 모집단의 상위 · 하위 최대 30(판정 Q3 (a)) · 조회 기준은 「ETF 비교하기」 안에서만 공유(Q4 (b)).
// - 「확인 필요」 탭 · 빠른 필터 · 요약 칸은 없앴다(판정 Q6 · PLAN §4 — 각 행 사유 · 「보유」 · 「오늘의 투자 점검」 자료 확인).
// - 읽기 전용. 새 추천 · 위험 등급 · 매매 신호 없음.

import { useState } from "react";
import type { MenuKey } from "./LeftSidebar";
import {
  CompareLines,
  ConditionPanel,
  SummaryStatus,
  okSummary,
  useEtfCompareSummary,
} from "./workbench/CompareHead";
import SectorSummary from "./workbench/SectorSummary";
import { invalidateQueries } from "@/lib/api/queryCache";
import { PRICE_SERIES_KEY_PREFIX } from "@/lib/api/dashboardKeys";
import RankingList from "./workbench/RankingList";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

type CandTab = "summary" | "ranking";

export default function JudgmentWorkbenchView({ onNavigate }: Props) {
  const { cond, q } = useEtfCompareSummary();
  const [tab, setTab] = useState<CandTab>("summary");
  const [panel, setPanel] = useState(false);
  // [다시 불러오기] = 열린 행을 닫고(다시 그림) 차트 캐시를 지운다 — 공유 조회는 지워진 키를 스스로 다시
  // 읽지 않으므로, 다음에 행을 열 때 새 저장 가격을 읽게 한다(독립 검토 MEDIUM).
  const [nonce, setNonce] = useState(0);
  const s = okSummary(q);
  const stale = q.phase === "success" && q.stale;

  return (
    <section aria-labelledby="wb-h" className="wb-root ec-root">
      <div className="ec-head">
        <h1 id="wb-h">ETF 비교하기 · 후보</h1>
        <span className="holdings-sort-seg ec-tabs" role="tablist" aria-label="후보 보기">
          {(
            [
              ["summary", "섹터 요약"],
              ["ranking", "ETF 순위"],
            ] as const
          ).map(([k, label]) => (
            <button
              key={k}
              type="button"
              role="tab"
              aria-selected={tab === k}
              className={tab === k ? "on" : undefined}
              onClick={() => setTab(k)}
            >
              {label}
            </button>
          ))}
        </span>
        <button type="button" className="wb-btn btn-md" aria-expanded={panel} onClick={() => setPanel(!panel)}>
          조회 기준
        </button>
        <button
          type="button"
          className="wb-btn btn-md"
          onClick={() => {
            invalidateQueries(PRICE_SERIES_KEY_PREFIX);
            setNonce((n) => n + 1);
            q.reload();
          }}
        >
          다시 불러오기
        </button>
      </div>

      {panel && <ConditionPanel cond={cond} onClose={() => setPanel(false)} />}

      <SummaryStatus q={q} />
      {s && (
        <>
          <CompareLines s={s} stale={stale} showRegime={tab === "summary"} />
          {tab === "summary" ? (
            <SectorSummary key={`s${nonce}`} s={s} onNavigate={onNavigate} />
          ) : (
            <RankingList key={`r${nonce}`} s={s} />
          )}
        </>
      )}
    </section>
  );
}
