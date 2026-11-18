"use client";

// POC6-32 V2(PLAN 판정 V2 Q1 (a) · PLAN §2 S1 · S3 · §9 I-5) — 「오늘 확인 › 주간 ETF 점검」 화면.
// - 메뉴로 열 때마다 새로 그려진다(MainPanel) → 담은 주간 카드가 그려질 때 전에 받아 둔 응답을 비우고 새로 읽는다
//   (GET /weekly/etf-check · 한 응답 = 한 검토 건).
// - 이 화면에서 상세(「보유와 후보 비교」 · 「ETF 구성종목」)를 열었다가 [← 보낸 화면으로]로 돌아오면 이 화면은 숨겨 둔
//   그대로다 — 고른 ETF · 같은 검토 건(응답)이 그대로 보이고 다시 읽지 않는다(MainPanel 보낸 화면 기록).
// - 머리 [다시 읽기] = 받아 둔 응답을 비우고 지금 고른 ETF 로 다시 읽는다(주간 카드의 다시 읽기 차례 `gen` 을 올림).
// - 이 화면의 글자에는 '후보'를 쓸 수 있다(판정 V2 Q1 · 메뉴 이름 · 힌트는 제외).
// - 본문 = today/WeeklyReviewCard(① 시장 → ② ETF 흐름 → ③ 선택한 후보 검토 → ④ AI 의견 요약 → ⑤ 최근 검토 기록 · 제목은 이 화면 h1 하나).

import { useState } from "react";
import type { MenuKey } from "./LeftSidebar";
import WeeklyReviewCard from "./today/WeeklyReviewCard";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

export default function WeeklyEtfCheckView({ onNavigate }: Props) {
  const [gen, setGen] = useState(0);
  return (
    <section aria-labelledby="wk-h" className="ec-root wk-root">
      <div className="ec-head">
        <h1 id="wk-h">주간 ETF 점검</h1>
        <button type="button" className="wb-btn btn-md" onClick={() => setGen((g) => g + 1)}>
          다시 읽기
        </button>
      </div>
      <WeeklyReviewCard onNavigate={onNavigate} gen={gen} />
    </section>
  );
}
