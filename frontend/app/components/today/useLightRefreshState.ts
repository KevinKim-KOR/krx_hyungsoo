"use client";

// POC3-OPS-02B-2-KS10-TRIGGER-FILE-SPLIT (2026-09-13)
// `TodayInvestmentCheckView.tsx` 가 907줄로 KS-10 프론트 임계(>900)를 넘어
// 책임별로 분리했다. **JSX·문구·className·핸들러·호출 조건을 고치지 않았다** —
// 바뀐 것은 파일 배치와 import/export 줄뿐이다.

import { useEffect, useRef, useState } from "react";

// 경량 갱신 상태 훅. done/failed 는 잠깐 보여준 뒤 자동으로 idle 로 복귀
// (완료/실패 문구가 화면에 계속 남지 않게 · 2026-07-31 정정).
type RefreshPhase = "idle" | "running" | "done" | "failed";
const REFRESH_FEEDBACK_MS = 3000;
export function useLightRefreshState() {
  const [state, setState] = useState<RefreshPhase>("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const clear = () => {
    if (timer.current) {
      clearTimeout(timer.current);
      timer.current = null;
    }
  };
  const autoIdle = () => {
    clear();
    timer.current = setTimeout(() => setState("idle"), REFRESH_FEEDBACK_MS);
  };
  useEffect(() => clear, []);
  return {
    state,
    setRunning: () => {
      clear();
      setState("running");
    },
    setDone: () => {
      setState("done");
      autoIdle();
    },
    setFailed: () => {
      setState("failed");
      autoIdle();
    },
  };
}
