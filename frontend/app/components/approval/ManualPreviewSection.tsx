"use client";

// OCI 적용·알림 — 미리보기·수동 전달 점검 영역 (B구간).
//
// 설계 정정(Q1-c·Q5-a): 여기 있는 것은 "투자 판단 초안" 이 아니라, PC 에서 사람이 수동으로
// 생성·전달 점검하는 기능이다. 자동 PUSH(OCI 발송)와는 다른 것으로 표시한다.
//  - ThreePushDraftCard: PUSH-1/PUSH-3 message_text 를 수동 생성해 미리보기.
//  - 현재 run 1건(RunPanel): MainPanel 메모리의 현재 run 을 "현재 미리보기·수동 처리 상태"
//    로 표시. push_kind 가 신뢰 가능한 정보 PUSH 종류일 때만 여기서 다룬다.
//    push_kind=null(종류 확인 불가) run 은 개발·호환 점검으로 보낸다(임의 분류 금지).
//
// RunPanel 의 승인/거절/발송 동작 계약은 변경하지 않는다 — 이 화면에서 사람이 수동으로
// 메시지 전달을 점검하는 기존 기능이다.

import { useState } from "react";
import RunPanel from "../RunPanel";
import ThreePushDraftCard from "../ThreePushDraftCard";
import { pushKindLabel, isKnownPushKind } from "./pushKindLabel";
import type { Run } from "@/lib/api";

interface Props {
  run: Run | null;
  setRun: (run: Run | null) => void;
}

export default function ManualPreviewSection({ run, setRun }: Props) {
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // 신뢰 가능한 정보 PUSH 종류의 run 만 이 영역에서 다룬다.
  const showCurrentRun = run !== null && isKnownPushKind(run.push_kind);

  return (
    <section aria-labelledby="manual-preview-h" className="manual-preview-section">
      <h2 id="manual-preview-h">미리보기·수동 전달 점검</h2>
      <p className="helper" style={{ marginBottom: 12 }}>
        아래는 자동 발송(OCI)이 아니라, PC 에서 <strong>사람이 수동으로</strong>{" "}
        메시지를 생성하고 전달을 점검하는 기능입니다. 정보 PUSH 자동 발송과는
        다릅니다.
      </p>

      {/* PUSH-1 / PUSH-3 수동 생성 (미리보기용) */}
      <ThreePushDraftCard onDraftCreated={setRun} />

      {/* 현재 메모리의 run 1건 — 현재 미리보기·수동 처리 상태 */}
      {showCurrentRun ? (
        <div className="current-manual-run">
          <div className="current-manual-run-head">
            <span className="current-manual-run-title">
              현재 미리보기·수동 처리 상태
            </span>
            <span className="current-manual-run-kind">
              {pushKindLabel(run!.push_kind)}
            </span>
          </div>
          <RunPanel
            run={run!}
            setRun={setRun}
            loading={loading}
            setLoading={setLoading}
            errorMsg={errorMsg}
            setErrorMsg={setErrorMsg}
          />
        </div>
      ) : null}
    </section>
  );
}
