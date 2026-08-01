"use client";

// OCI 적용·알림 화면 (기존 approval route key 유지).
//
// 2026-08-01 승인·알림 역할 분리 및 재배치 — A구간 (역할 정리·상단 재배치):
//   설계 정정(Q1-c): push_kind 3종은 모두 정보 PUSH. 현재 계약에 "투자 판단 초안"
//   식별 필드가 없으므로 판단 초안 영역·승인 대기 표현·빈 자리표시자를 만들지 않는다.
//   화면 명칭 = "OCI 적용·알림". 내부 approval route key·MainPanel 분기·draft→approval
//   자동 이동 경로는 불변.
//
//   상단 구조 (A구간):
//     1) OciAlertHeader — 화면 역할 안내 (OCI 적용 / 정보 PUSH 구분)
//     2) ThreePushParamCard — OCI 운영 기준 적용 (주 작업 · create→approve→sync→verify 불변)
//     3) InfoPushGuideCards — 정보 PUSH 운영 기준 안내 (승인 run 미포함 · 실측 상태 위장 없음)
//
//   하단(B·C구간에서 정식 정리 예정): ThreePushDraftCard·RunPanel(현재 run)·개발용은
//   기능 누락 방지를 위해 아래에 유지한다. B구간에서 "미리보기·수동 전달 점검" 으로
//   이동하고 문구를 정정한다. A구간에서는 상단 역할 분리만 확정한다.

import { useState } from "react";
import RunPanel from "./RunPanel";
import SampleDraftQuickButton from "./SampleDraftQuickButton";
import ThreePushDraftCard from "./ThreePushDraftCard";
import ThreePushParamCard from "./ThreePushParamCard";
import UniverseRefreshPanel from "./UniverseRefreshPanel";
import OciAlertHeader from "./approval/OciAlertHeader";
import InfoPushGuideCards from "./approval/InfoPushGuideCards";
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
      {/* A구간 1) 화면 역할 안내 */}
      <OciAlertHeader />

      {/* A구간 2) OCI 운영 기준 적용 — 주 작업 (계약 불변) */}
      <ThreePushParamCard />

      {/* A구간 3) 정보 PUSH 운영 기준 — 안내만 (승인 run 미포함) */}
      <InfoPushGuideCards />

      {/* ─── B·C구간에서 정식 정리 예정 (기능 누락 방지용 임시 유지) ─────────
          아래는 미리보기·수동 전달 점검 / 잘못 배치된 기능. B구간에서
          "미리보기·수동 전달 점검" 영역으로 이동하고 문구를 정정한다. */}
      <div className="pending-reorg-note card">
        아래 항목은 다음 단계(B·C)에서 <strong>미리보기·수동 전달 점검</strong>{" "}
        영역으로 정리됩니다. 현재는 기존 기능을 그대로 사용할 수 있습니다.
      </div>

      {/* 보조 출력 배관 — 신규 ETF 관찰 후보 (C구간에서 요즘 잘 오르는 ETF 로 이동) */}
      <UniverseRefreshPanel />

      {/* PUSH-1 / PUSH-3 수동 초안 생성 (B구간에서 미리보기·수동 점검으로 이동) */}
      <ThreePushDraftCard onDraftCreated={setRun} />

      {/* 현재 run 수동 처리 (B구간에서 "현재 미리보기·수동 처리 상태" 로 정리) */}
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
