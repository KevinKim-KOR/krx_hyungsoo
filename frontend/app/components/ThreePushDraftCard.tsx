"use client";

// POC2 3-PUSH Message Contract 정렬 (2026-06-11) — PUSH-1 / PUSH-3 draft 생성 카드.
//
// 책임 (지시문 §4 / §10):
// - PUSH-1 (시장 흐름 브리핑) / PUSH-3 (급등락 관찰 신호) Run 생성 진입점.
//   PUSH-2 (보유 관찰 브리핑) 는 Holdings 화면의 "초안 생성" 버튼 (기존) 이 담당.
// - backend 가 message_text 까지 미리 빌드한 Run 을 받아 그대로 setRun 으로 넘긴다.
//   frontend 는 message_text 를 조립/파싱하지 않는다 (AC-2).
// - 생성된 Run 은 위의 RunPanel 에서 승인 게이트를 통과해야 OCI/Telegram 으로 간다.
//   본 카드 자체가 Telegram 발송을 트리거하지 않는다 (AC-7 승인 게이트 유지).
//
// 지시문 §13 에 따라 발송 시간 / UX 는 본 STEP 에서 확정하지 않는다 — 본 카드는
// 3종 message_text 계약 확인을 위한 임시 진입점이다.

import { useCallback, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  generateMarketBriefingDraft,
  generateSpikeAlertDraft,
  type Run,
} from "@/lib/api";

interface Props {
  onDraftCreated: (run: Run) => void;
}

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

export default function ThreePushDraftCard({ onDraftCreated }: Props) {
  const [loading, setLoading] = useState<"none" | "market" | "spike">("none");
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleMarket = useCallback(async () => {
    setLoading("market");
    setErrorMsg(null);
    try {
      const run = await generateMarketBriefingDraft();
      onDraftCreated(run);
    } catch (e) {
      setErrorMsg(describeError(e));
    } finally {
      setLoading("none");
    }
  }, [onDraftCreated]);

  const handleSpike = useCallback(async () => {
    setLoading("spike");
    setErrorMsg(null);
    try {
      const run = await generateSpikeAlertDraft();
      onDraftCreated(run);
    } catch (e) {
      setErrorMsg(describeError(e));
    } finally {
      setLoading("none");
    }
  }, [onDraftCreated]);

  return (
    <div className="card">
      <h2>3-PUSH 초안 생성 (PUSH-1 / PUSH-3)</h2>
      <p className="helper" style={{ marginBottom: 8 }}>
        하루 3종 PUSH 메시지 중 PUSH-1 시장 흐름 브리핑 / PUSH-3 급등락 관찰
        신호의 초안을 생성합니다. PUSH-2 보유 관찰 브리핑은 Holdings 화면의 &lsquo;초안
        생성&rsquo; 버튼이 담당합니다. 본 카드는 backend 가 빌드한 message_text 를
        그대로 받아 표시하며, 인간 승인 전에는 Telegram 으로 발송되지 않습니다.
      </p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={handleMarket}
          disabled={loading !== "none"}
        >
          PUSH-1 시장 흐름 브리핑 초안
        </button>
        <button
          type="button"
          onClick={handleSpike}
          disabled={loading !== "none"}
        >
          PUSH-3 급등락 관찰 신호 초안
        </button>
      </div>
      {errorMsg && (
        <div className="message error" style={{ marginTop: 8 }}>
          {errorMsg}
        </div>
      )}
      <div
        className="helper"
        style={{ marginTop: 8, fontSize: "0.8rem" }}
      >
        <strong>본 카드는 발송이 아니라 초안 생성입니다.</strong> 생성된 초안은
        위 RunPanel 의 승인 게이트를 통과해야 OCI/Telegram 으로 전달됩니다 (지시문
        §8 승인 게이트 유지). 매수·매도·교체·현금비중·조정장 확정 문구 0건.
      </div>
    </div>
  );
}
