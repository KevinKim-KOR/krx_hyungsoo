"use client";

// POC2 PC UI Shell 1차 — Approval / Telegram view.
//
// 지시문 §3.5 — 승인 전/후 용어 분리:
//   승인 전 산출물 라벨: "승인 대기 메시지 초안" (이전 표현 사용 금지)
//   승인 후 결과 라벨: "Telegram 발송 결과" / "발송 완료 메시지"
//   거절 / 실패 결과 라벨: "거절 / 실패된 메시지 초안" (Telegram 미발송)
//
// 기존 흐름 유지:
// - HoldingsClient 가 생성한 run 을 RunPanel 이 호스팅 (status / Approve / Reject).
// - UniverseRefreshPanel (PUSH 2 신규 ETF 관찰 후보) 은 보조 출력 배관으로 본 view 에 잔존.
// - SampleDraftQuickButton 은 개발/테스트용으로 접힘 details 안에만 잔존.

import { useState } from "react";
import RunPanel from "./RunPanel";
import SampleDraftQuickButton from "./SampleDraftQuickButton";
import ThreePushDraftCard from "./ThreePushDraftCard";
import UniverseRefreshPanel from "./UniverseRefreshPanel";
import type { Run } from "@/lib/api";

interface Props {
  run: Run | null;
  setRun: (run: Run | null) => void;
}

export default function ApprovalTelegramView({ run, setRun }: Props) {
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  return (
    <section aria-labelledby="approval-h">
      <h1 id="approval-h">Approval / Telegram</h1>
      <p className="subtitle">
        승인 전 단계는 <strong>승인 대기 메시지 초안</strong> 으로, 승인 후
        단계는 <strong>Telegram 발송 결과</strong> 로 표시됩니다. 인간 최종
        승인 게이트를 유지합니다.
      </p>
      <div className="role-banner">
        <strong>[판단 흐름 STEP 5]</strong> Holdings 화면에서 생성된 초안을 검토하고
        승인 또는 거절합니다. 승인 시 Telegram 3-PUSH(보유 종목 상태 / 신규 ETF 관찰
        후보 / 급락 ETF 주의)가 발송됩니다. 거절 시 Telegram은 발송되지 않습니다.
      </div>

      {/* 보조 출력 배관 — PUSH 2 신규 ETF 관찰 후보 */}
      <UniverseRefreshPanel />

      {/* POC2 3-PUSH Message Contract 정렬 (2026-06-11) — PUSH-1 / PUSH-3 의
          초안 생성 진입점. 발송 시간 / UX 는 별도 STEP. 본 카드는 계약 확인용
          진입점이며 인간 승인 게이트는 그대로 유지된다 (AC-7). */}
      <ThreePushDraftCard onDraftCreated={setRun} />

      {/* 메인 흐름 — 현재 run (있을 때만) */}
      {run ? (
        <RunPanel
          run={run}
          setRun={setRun}
          loading={loading}
          setLoading={setLoading}
          errorMsg={errorMsg}
          setErrorMsg={setErrorMsg}
        />
      ) : (
        <div className="card">
          <h2>현재 승인 대기 메시지 초안</h2>
          <div className="message info">
            아직 생성된 초안이 없습니다. Holdings 메뉴에서 보유 종목 기반
            초안을 만든 뒤 본 화면에서 승인 여부를 결정합니다.
          </div>
        </div>
      )}

      {/* 개발/테스트용 — 접힘. 운영 입력 아님. */}
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
    </section>
  );
}
