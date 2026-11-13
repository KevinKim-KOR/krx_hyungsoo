"use client";

// 「ETF보유 및 후보 선정 › 후보리스트」(POC3-02 UI-2 Judgment Workbench → POC6-28 「ETF 비교하기 › 후보」 → POC6-29).
//
// POC6-29(PLAN §2-5 · 판정 Q1 · Q2 · Q4 · Q5 · Q9 · Q11 · 2026-11-12):
// - 이 화면의 조건(기간 · 제외)으로 GET /market/etf-compare/summary 를 읽는다. 다른 화면 조건과 따로이고, 기본 기간은
//   이 화면에 저장한다([이 기준을 기본으로]).
// - 목록 = 같은 조건 · 공통 기간 모집단의 상위 · 하위 최대 30. [목록 | 표] · 행 상세(상세 수치 · 판단 근거) ·
//   「이 목록으로 할 일」(AI 투자 세션 · ETF 구성종목 · 복사).
// - [섹터 요약]은 「섹터요약」 메뉴로 나갔다(SectorSummaryView · 판정 Q11).
// - 읽기 전용. 새 추천 · 위험 등급 · 매매 신호 없음.

import { useState } from "react";
import type { MenuKey } from "./LeftSidebar";
import {
  BasisSaveRow,
  CompareLines,
  ConditionPanel,
  SummaryStatus,
  okSummary,
  useEtfCompareSummary,
} from "./workbench/CompareHead";
import { invalidateQueries } from "@/lib/api/queryCache";
import { ETF_DETAIL_KEY_PREFIX, PRICE_SERIES_KEY_PREFIX } from "@/lib/api/dashboardKeys";
import RankingList from "./workbench/RankingList";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

export default function JudgmentWorkbenchView({ onNavigate }: Props) {
  const { cond, q } = useEtfCompareSummary("candidates");
  const [panel, setPanel] = useState(false);
  // [다시 불러오기] = 열린 행을 닫고(다시 그림) 차트 · 상세 수치 캐시를 지운다 — 다음에 행을 열 때 새 값을 읽게 한다.
  const [nonce, setNonce] = useState(0);
  const s = okSummary(q);
  const stale = q.phase === "success" && q.stale;

  return (
    <section aria-labelledby="wb-h" className="wb-root ec-root">
      <div className="ec-head">
        <h1 id="wb-h">후보리스트</h1>
        <button type="button" className="wb-btn btn-md" aria-expanded={panel} onClick={() => setPanel(!panel)}>
          조회 기준
        </button>
        <button
          type="button"
          className="wb-btn btn-md"
          onClick={() => {
            invalidateQueries(PRICE_SERIES_KEY_PREFIX);
            invalidateQueries(ETF_DETAIL_KEY_PREFIX);
            setNonce((n) => n + 1);
            q.reload();
          }}
        >
          다시 불러오기
        </button>
      </div>

      {panel && (
        <ConditionPanel
          screen="candidates"
          cond={cond}
          onClose={() => setPanel(false)}
          applies="「후보리스트」 상·하위 목록 · 표 · 목록 넘기기"
        />
      )}
      <BasisSaveRow screen="candidates" basis={cond.basis} />

      <SummaryStatus q={q} />
      {s && (
        <>
          <CompareLines s={s} stale={stale} />
          <RankingList key={`r${nonce}`} s={s} onNavigate={onNavigate} />
        </>
      )}
    </section>
  );
}
