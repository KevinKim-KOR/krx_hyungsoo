"use client";

// POC2 Step 1 — 메인 컨테이너.
//
// UI 정책 (지시문 D항):
// - 첫 번째 / 기본 노출 섹션 = HoldingsClient (운영 진입점)
// - run 이 만들어지면 RunPanel 로 status / Approve / Reject 노출
// - 샘플 입력은 가장 아래의 접힘 <details> 안. 라벨 "개발/테스트용 — 운영 입력 아님".
//   기본 닫힘. 운영 입력과 동급 탭 구조 금지.
//
// run state 는 이 컨테이너가 controlled 로 보유. HoldingsClient /
// SampleDraftQuickButton 모두 onDraftCreated(run) 으로 부모에 전달.

import { useState } from "react";
import HoldingsClient from "./HoldingsClient";
import RunPanel from "./RunPanel";
import SampleDraftQuickButton from "./SampleDraftQuickButton";
import type { Run } from "@/lib/api";

export default function MainPanel() {
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  return (
    <main>
      <h1>승인 루프</h1>
      <p className="subtitle">
        보유 종목을 입력하면 보유 현황 기반 초안이 생성되고, 승인 시 외부로 전달됩니다.
        (이번 단계는 ML 추천이 아닌 보유 현황 그대로의 초안입니다.)
      </p>

      {/* 1. 운영 진입점 — 보유 종목 입력 (최상단, 첫 번째 섹션) */}
      <HoldingsClient onDraftCreated={setRun} />

      {/* 2. 현재 run 표시 (run 있을 때만) */}
      {run ? (
        <RunPanel
          run={run}
          setRun={setRun}
          loading={loading}
          setLoading={setLoading}
          errorMsg={errorMsg}
          setErrorMsg={setErrorMsg}
        />
      ) : null}

      {/* 3. 샘플 입력 (개발/테스트용, 접힘) — 가장 아래 */}
      <details className="card" style={{ marginTop: 24 }}>
        <summary
          style={{
            cursor: "pointer",
            color: "var(--muted)",
            fontWeight: 600,
          }}
        >
          개발/테스트용 — 운영 입력 아님
        </summary>
        <div style={{ marginTop: 12 }}>
          <SampleDraftQuickButton onDraftCreated={setRun} />
        </div>
      </details>
    </main>
  );
}
