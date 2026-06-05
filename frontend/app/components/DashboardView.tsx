"use client";

// POC2 Operational UI Cleanup 1차 — Dashboard (2026-06-06).
//
// 역할: 오늘의 판단 흐름 홈 화면.
// - 5-step 판단 흐름 카드로 운영 1회전 흐름을 시각화.
// - 각 step 카드에서 해당 화면으로 바로 이동 가능.
// - Market Discovery 데이터 상태를 1줄 요약으로 표시 (상세는 Market Discovery 화면).
// - 단순 바로가기 모음 → "오늘의 판단 흐름" 화면으로 정리.

import { useEffect, useState } from "react";
import {
  fetchMarketTopnLatest,
  type MarketTopNResponse,
} from "@/lib/api";
import type { MenuKey } from "./LeftSidebar";

interface Props {
  onNavigate: (key: MenuKey) => void;
}

type SummaryState =
  | { phase: "loading" }
  | { phase: "error" }
  | { phase: "ready"; data: MarketTopNResponse };

function describeMarketStatus(state: SummaryState): string {
  if (state.phase === "loading") return "Market Discovery 데이터 확인 중...";
  if (state.phase === "error") return "Market Discovery 데이터 확인 실패";
  const data = state.data;
  if (data.status === "ok") {
    return `데이터 있음 — 기준일 ${data.asof ?? "-"} / Universe ${data.universe_count ?? "-"}개`;
  }
  if (data.status === "missing") return "시장 데이터 없음 — 갱신 필요";
  return "데이터 오류 — Market Discovery 화면 확인 필요";
}

const STEPS: {
  num: number;
  title: string;
  desc: string;
  action: string;
  nav: MenuKey;
}[] = [
  {
    num: 1,
    title: "시장 데이터 갱신",
    desc: "Market Discovery 화면에서 '최신 시장 데이터 갱신'을 실행합니다. 수익률 기반 ETF 후보 목록이 SQLite에 저장됩니다.",
    action: "Market Discovery 열기 →",
    nav: "market_discovery",
  },
  {
    num: 2,
    title: "시장 후보 확인 + ETF 구성종목 분석",
    desc: "Market Discovery에서 TOP N 후보를 확인하고, ETF Exposure에서 구성종목 중복률을 점검합니다.",
    action: "ETF Exposure 열기 →",
    nav: "etf_exposure",
  },
  {
    num: 3,
    title: "내 보유 ETF와 비교",
    desc: "Holdings 화면에서 보유 ETF를 입력·저장하고, Evidence 조회로 현재 시장 후보와의 연결 상태를 확인합니다.",
    action: "Holdings 열기 →",
    nav: "holdings",
  },
  {
    num: 4,
    title: "판단 초안 생성",
    desc: "Holdings 화면의 '저장된 보유 종목으로 초안 만들기'를 실행합니다. 시장 국면 + 보유 Evidence가 메시지에 포함됩니다.",
    action: "Holdings 열기 →",
    nav: "holdings",
  },
  {
    num: 5,
    title: "승인 / Telegram 발송",
    desc: "Approval / Telegram 화면에서 초안 내용을 검토하고 승인합니다. 승인 시 Telegram 3-PUSH가 발송됩니다.",
    action: "Approval / Telegram 열기 →",
    nav: "approval",
  },
];

export default function DashboardView({ onNavigate }: Props) {
  const [state, setState] = useState<SummaryState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchMarketTopnLatest()
      .then((data) => {
        if (!cancelled) setState({ phase: "ready", data });
      })
      .catch(() => {
        if (!cancelled) setState({ phase: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const marketStatusLine = describeMarketStatus(state);

  return (
    <section aria-labelledby="dashboard-h">
      <h1 id="dashboard-h">Dashboard</h1>
      <p className="subtitle">
        오늘의 판단 흐름 — PC 투자 의사결정 1회전을 순서대로 진행합니다. 자동 매매 없음,
        인간 최종 승인 게이트 유지.
      </p>

      <div className="card" style={{ marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
          <span style={{ color: "var(--muted)" }}>시장 데이터 상태:</span>
          <span>{marketStatusLine}</span>
        </div>
      </div>

      <div className="dashboard-flow-grid">
        {STEPS.map((step) => (
          <div key={step.num} className="card dashboard-flow-card">
            <div className="dashboard-flow-step-num">STEP {step.num}</div>
            <h2 className="dashboard-flow-title">{step.title}</h2>
            <p className="dashboard-flow-desc">{step.desc}</p>
            <button
              type="button"
              className="dashboard-flow-btn"
              onClick={() => onNavigate(step.nav)}
            >
              {step.action}
            </button>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>시스템 구성</h2>
        <ul className="dashboard-status-list">
          <li>
            <strong>시장 데이터 기반</strong> — FinanceDataReader + SQLite
            (etf_master / etf_daily_price / market_refresh_log).
          </li>
          <li>
            <strong>운영 주기</strong> — 사용자 PC 수동 실행 (주 2회 예상).
            메뉴는 좌측에서 선택.
          </li>
          <li>
            <strong>보조 알림 배관</strong> — Telegram 3-PUSH (보유 종목 상태 /
            신규 ETF 관찰 후보 / 급락 ETF 주의). 자동 매매 없음.
          </li>
        </ul>
      </div>
    </section>
  );
}
