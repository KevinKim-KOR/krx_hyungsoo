"use client";

// OCI 적용·알림 — 미리보기·수동 전달 점검 영역 (B구간).
//
// 설계 정정(Q1-c·Q5-a): 여기 있는 것은 "투자 판단 초안" 이 아니라, PC 에서 사람이 수동으로
// 생성·전달 점검하는 기능이다. 자동 PUSH(OCI 발송)와는 다른 것으로 표시한다.
//  - ThreePushDraftCard: PUSH-1/PUSH-3 message_text 를 수동 생성해 미리보기.
//  - HoldingsDraftButton: PUSH-2 보유 관찰 브리핑(저장된 보유 종목 기반) 수동 생성.
//    2026-08-02 POC3-05 DESIGN_V2 §4.6·A-Q5 — 기존 Holdings 화면의 "저장된 보유
//    종목으로 초안 만들기" 를 여기로 이동. 실행 계약(generateDraftFromHoldings→setRun)은
//    그대로. 신규 run 종류·승인 계약 없음.
//  - 현재 run 1건(RunPanel): MainPanel 메모리의 현재 run 을 "현재 미리보기·수동 처리 상태"
//    로 표시. push_kind 가 신뢰 가능한 정보 PUSH 종류일 때만 여기서 다룬다.
//    push_kind=null(종류 확인 불가) run 은 개발·호환 점검으로 보낸다(임의 분류 금지).
//
// RunPanel 의 승인/거절/발송 동작 계약은 변경하지 않는다 — 이 화면에서 사람이 수동으로
// 메시지 전달을 점검하는 기존 기능이다.

import { useCallback, useState } from "react";
import RunPanel from "../RunPanel";
import ThreePushDraftCard from "../ThreePushDraftCard";
import { pushKindLabel, isKnownPushKind } from "./pushKindLabel";
import {
  ApiConfigError,
  ApiRequestError,
  generateDraftFromHoldings,
  type Run,
} from "@/lib/api";

interface Props {
  run: Run | null;
  setRun: (run: Run | null) => void;
}

// PUSH-2 보유 관찰 브리핑 초안 생성 (§4.6 이동). 기존 실행 계약 그대로 재사용.
function HoldingsDraftButton({
  onDraftCreated,
}: {
  onDraftCreated: (run: Run) => void;
}) {
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const onGenerate = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const run = await generateDraftFromHoldings();
      onDraftCreated(run);
    } catch (e) {
      if (e instanceof ApiConfigError) setErrorMsg(`구성 오류: ${e.message}`);
      else if (e instanceof ApiRequestError)
        setErrorMsg(`요청 실패(HTTP ${e.httpStatus}): ${e.message}`);
      else setErrorMsg(`알 수 없는 오류: ${(e as Error).message}`);
    } finally {
      setLoading(false);
    }
  }, [onDraftCreated]);

  return (
    <div className="card">
      <h2>PUSH-2 보유 관찰 브리핑 초안 생성</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        저장된 보유 종목을 기반으로 PUSH-2 보유 관찰 브리핑 초안을 생성합니다. 보유
        종목 입력·저장은 &lsquo;보유·자료 관리 &gt; 종목 관리&rsquo; 화면에서 합니다.
        본 버튼은 backend 가 빌드한 초안을 받아 아래 승인 게이트로 넘기며, 사람이
        승인하기 전에는 Telegram 으로 발송되지 않습니다.
      </p>
      <button type="button" onClick={onGenerate} disabled={loading}>
        {loading ? "생성 중..." : "저장된 보유 종목으로 초안 만들기"}
      </button>
      {errorMsg ? (
        <div className="message error" style={{ marginTop: 8 }}>
          {errorMsg}
        </div>
      ) : null}
    </div>
  );
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

      {/* PUSH-2 보유 관찰 브리핑 수동 생성 (§4.6 Holdings 에서 이동) */}
      <HoldingsDraftButton onDraftCreated={setRun} />

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
