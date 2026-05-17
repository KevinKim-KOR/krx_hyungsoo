"use client";

// POC2 PC UI Shell + Market Discovery 진입 — Dashboard view.
//
// 표시 정책 (지시문 §3.3 / §3.2):
// - 데이터 존재 여부 + Market Discovery 이동만 제공. TOP N 상세표 / 차트 /
//   시장 국면 / 매수·매도 판단 / AI 투자세션 버튼 모두 금지.
// - GET /market/topn/latest 응답의 status / asof / universe_count 만 요약 노출.

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

function describeStatus(state: SummaryState): {
  badge: string;
  detail: string;
} {
  if (state.phase === "loading") {
    return { badge: "확인 중", detail: "Market Discovery 데이터 상태 확인 중..." };
  }
  if (state.phase === "error") {
    return {
      badge: "확인 실패",
      detail: "Market Discovery 데이터 상태 확인에 실패했습니다.",
    };
  }
  const data = state.data;
  if (data.status === "ok") {
    return {
      badge: "데이터 있음",
      detail: `기준일 ${data.asof ?? "-"} / Universe ${
        data.universe_count ?? "-"
      }개 / 가격 수집 ${data.price_success_count ?? "-"}개`,
    };
  }
  if (data.status === "missing") {
    return {
      badge: "데이터 없음",
      detail: "시장 TOP N artifact 가 아직 생성되지 않았습니다.",
    };
  }
  return {
    badge: "데이터 오류",
    detail: data.error ?? "TOP N artifact 를 읽을 수 없습니다.",
  };
}

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

  const { badge, detail } = describeStatus(state);

  return (
    <section aria-labelledby="dashboard-h">
      <h1 id="dashboard-h">Dashboard</h1>
      <p className="subtitle">
        krx_alertor 운영 상태 요약과 메뉴 바로가기. 상세 화면은 좌측 메뉴에서 선택.
      </p>

      <div className="card">
        <h2>Market Discovery 데이터 상태</h2>
        <div className="status-row">
          <span className="status-badge">{badge}</span>
          <span className="kv">
            <span className="v">{detail}</span>
          </span>
        </div>
        <div className="btn-row" style={{ marginTop: 12 }}>
          <button
            type="button"
            onClick={() => onNavigate("market_discovery")}
          >
            Market Discovery 화면 열기 →
          </button>
        </div>
        <div className="helper" style={{ marginTop: 8 }}>
          상세 TOP N 표는 Market Discovery 메뉴에서만 확인합니다 (Dashboard
          에는 상세표를 두지 않습니다).
        </div>
      </div>

      <div className="card">
        <h2>시스템 상태</h2>
        <ul className="dashboard-status-list">
          <li>
            <strong>시장 데이터 기반 구축 완료</strong> — FinanceDataReader +
            SQLite (etf_master / etf_daily_price / market_refresh_log).
          </li>
          <li>
            <strong>운영 의사결정 입력</strong> — 사용자 PC 작업 (주 2회 예상).
            메인 메뉴는 좌측에서.
          </li>
          <li>
            <strong>보조 알림 배관</strong> — Telegram 3-PUSH (보유 종목 상태 /
            신규 ETF 관찰 후보 / 급락 ETF 주의). 자동 매매 없음, 인간 최종 승인 게이트 유지.
          </li>
        </ul>
      </div>

      <div className="card">
        <h2>바로가기</h2>
        <div className="btn-row dashboard-shortcut-row">
          <button
            type="button"
            onClick={() => onNavigate("market_discovery")}
          >
            Market Discovery →
          </button>
          <button
            type="button"
            onClick={() => onNavigate("holdings")}
          >
            Holdings →
          </button>
          <button
            type="button"
            onClick={() => onNavigate("approval")}
          >
            Approval / Telegram →
          </button>
          <button
            type="button"
            onClick={() => onNavigate("data_status")}
          >
            Data Status →
          </button>
        </div>
      </div>
    </section>
  );
}
