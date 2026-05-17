"use client";

// POC2 PC UI Shell 1차 — Holdings view.
//
// 기존 holdings 기능을 그대로 래핑한다 (지시문 §3.4):
// - 평가금액 / 평가손익 / 비중 등 기존 표시 유지.
// - 기존 API 호출 유지.
// - 매수 / 매도 판단 화면으로 바꾸지 않음.
// - 새 기능을 추가하지 않음.
//
// HoldingsClient 의 onDraftCreated 콜백은 MainPanel 이 전달하는 setRun.
// draft 가 생성되면 MainPanel 이 active menu 를 "approval" 로 자동 전환한다.

import HoldingsClient from "./HoldingsClient";
import type { Run } from "@/lib/api";

interface Props {
  onDraftCreated: (run: Run | null) => void;
}

export default function HoldingsView({ onDraftCreated }: Props) {
  return (
    <section aria-labelledby="holdings-h">
      <h1 id="holdings-h">Holdings</h1>
      <p className="subtitle">
        보유 종목 입력 / 시세 갱신 / 평가 계산. 보유 종목 기반 초안 생성 후
        Approval / Telegram 메뉴에서 승인 여부를 판단합니다.
      </p>
      <HoldingsClient onDraftCreated={onDraftCreated} />
    </section>
  );
}
