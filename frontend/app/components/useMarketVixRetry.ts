"use client";

// POC5-12 — 「요즘 잘 오르는 ETF」 갱신 버튼의 'VIX 다시 받기'(설계 §3 · PLAN §2 · 판정 Q2 · §3).
//
// - 전체 갱신 6시간 대기 중이고, 가장 최근 전체 갱신에서 VIX 만 실패한 표식(`vix_retry.needed`)이
//   있으면 같은 버튼의 글자를 'VIX 다시 받기'로 바꾸고 `POST /market/refresh?scope=vix` 를 보낸다.
// - 결과는 POST 가 준 재시도 id 와 상태 응답의 `vix_retry.refresh_id` 가 같고 끝난 상태인지로
//   읽는다(첫 상태 조회 전에 끝나도 결과가 보인다).
// - 성공해도 '갱신 완료'(전체)로 부르지 않는다. 자동 반복 · 횟수 제한 없음.
// 화면 컴포넌트(MarketDiscoveryView)가 900줄 기준을 넘지 않도록 따로 둔다.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchMarketRefreshStatus,
  postMarketRefresh,
  type MarketRefreshStartResponse,
  type MarketRefreshStatusResponse,
  type MarketRefreshVixRetry,
} from "@/lib/api";

export const VIX_RETRY_FAILED_TEXT = "시장 불안 지표(VIX)를 갱신하지 못했습니다";

// 같은 갱신 버튼에 붙는 글자 · 진행 줄. label · line 이 null 이면 원래 전체 갱신 그대로.
export interface VixButton {
  label: string | null;
  line: { text: string; error: boolean } | null;
}

export type VixRetryUi =
  | { kind: "idle" }
  | { kind: "running" }
  | { kind: "completed"; asOf: string | null }
  | { kind: "failed"; message: string }
  | { kind: "info"; message: string };

const POLL_INTERVAL_MS = 4000;
const POLL_MAX_TICKS = 120; // 전체 갱신 polling 과 같은 안전 상한

function isFinished(
  r: MarketRefreshVixRetry | null | undefined,
  id: string,
): r is MarketRefreshVixRetry {
  return (
    !!r && r.refresh_id === id && (r.status === "completed" || r.status === "failed")
  );
}

export function useMarketVixRetry({
  fullRefreshBusy,
  onRetrySucceeded,
}: {
  fullRefreshBusy: boolean;
  onRetrySucceeded: () => void;
}) {
  const [status, setStatus] = useState<MarketRefreshStatusResponse | null>(null);
  const [ui, setUi] = useState<VixRetryUi>({ kind: "idle" });
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const aliveRef = useRef(true);
  const succeededRef = useRef(onRetrySucceeded);
  succeededRef.current = onRetrySucceeded;
  // 전체 갱신이 시작되면 이전 'VIX 다시 받기' 결과 줄을 비운다(전체 갱신 진행 줄을 가리지 않게).
  const [prevBusy, setPrevBusy] = useState(fullRefreshBusy);
  if (prevBusy !== fullRefreshBusy) {
    setPrevBusy(fullRefreshBusy);
    if (fullRefreshBusy) setUi({ kind: "idle" });
  }

  // 상태 확인 세대 — stop() 하면 올라간다. 그 전에 보낸 상태 요청의 응답(성공 · 오류)은 버린다:
  // 이전 재시도의 늦은 응답이 새 재시도의 진행 줄 · 버튼 잠금 · 타이머를 끝내지 않게(검증자 r1).
  const genRef = useRef(0);
  const stop = useCallback(() => {
    genRef.current += 1;
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // 6시간 대기 중인지(받은 상태의 남은 초 · 화면을 오래 열어 둬도 끝나는 순간 원래 버튼으로).
  const [cooling, setCooling] = useState(false);
  const coolTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // 상태 요청 순번 — 늦게 온 오래된 응답이 더 새 상태(버튼 글자 · 대기 시간)를 덮지 않게.
  const reqSeqRef = useRef(0);
  const appliedSeqRef = useRef(0);
  const applyStatusAt = useCallback((s: MarketRefreshStatusResponse, seq: number): boolean => {
    if (seq < appliedSeqRef.current) return false;
    appliedSeqRef.current = seq;
    setStatus(s);
    if (coolTimerRef.current !== null) clearTimeout(coolTimerRef.current);
    const secs = s.cooldown_remaining_seconds;
    setCooling(secs > 0);
    coolTimerRef.current = secs > 0 ? setTimeout(() => setCooling(false), secs * 1000) : null;
    return true;
  }, []);
  const readStatus = useCallback(async () => {
    const seq = ++reqSeqRef.current;
    return { s: await fetchMarketRefreshStatus(), seq };
  }, []);
  // 화면(전체 갱신 상태 확인)이 받은 상태 — 받은 순간을 순번으로 쓴다(그 사이 다시 받기 확인은 없음).
  const absorbStatus = useCallback(
    (s: MarketRefreshStatusResponse) => {
      applyStatusAt(s, ++reqSeqRef.current);
    },
    [applyStatusAt],
  );

  const settle = useCallback(
    (r: MarketRefreshVixRetry) => {
      stop();
      if (r.status === "completed") {
        setUi({ kind: "completed", asOf: r.vix_as_of_date ?? null });
        succeededRef.current();
      } else {
        setUi({ kind: "failed", message: r.error_summary || VIX_RETRY_FAILED_TEXT });
      }
    },
    [stop],
  );

  const follow = useCallback(
    (retryId: string) => {
      stop();
      const gen = genRef.current;
      setUi({ kind: "running" });
      let ticks = 0;
      const tick = async () => {
        ticks += 1;
        let got: { s: MarketRefreshStatusResponse; seq: number };
        try {
          got = await readStatus();
        } catch {
          if (gen !== genRef.current) return; // 멈춘 뒤(새 재시도 · 화면 떠남) 온 오류는 버림
          if (ticks >= POLL_MAX_TICKS) {
            stop();
            setUi({ kind: "failed", message: VIX_RETRY_FAILED_TEXT });
          }
          return;
        }
        if (gen !== genRef.current) return; // 멈춘 뒤 온 응답은 버림
        const s = got.s;
        applyStatusAt(s, got.seq);
        if (isFinished(s.vix_retry, retryId)) {
          settle(s.vix_retry);
        } else if (ticks >= POLL_MAX_TICKS) {
          stop();
          setUi({
            kind: "failed",
            message: "상태 확인 시간이 너무 길어졌습니다. 잠시 후 다시 시도하세요.",
          });
        }
      };
      timerRef.current = setInterval(tick, POLL_INTERVAL_MS);
    },
    [stop, settle, readStatus, applyStatusAt],
  );

  // 화면을 열 때 상태 1회(대기 시간 · 표식). 진행 중인 다시 받기가 있으면 이어서 본다.
  useEffect(() => {
    let alive = true;
    aliveRef.current = true;
    const gen = genRef.current;
    readStatus()
      .then(({ s, seq }) => {
        // 그 사이 더 새 상태를 받았거나 다른 확인이 시작됐으면 이 응답은 쓰지 않는다.
        if (!alive || !applyStatusAt(s, seq) || gen !== genRef.current) return;
        const r = s.vix_retry;
        if (r?.status === "running" && r.refresh_id) follow(r.refresh_id);
      })
      .catch(() => {
        // 상태를 못 읽으면 원래 버튼(전체 갱신) 그대로다.
      });
    return () => {
      alive = false;
      aliveRef.current = false;
      stop();
      if (coolTimerRef.current !== null) clearTimeout(coolTimerRef.current);
    };
  }, [follow, stop, readStatus, applyStatusAt]);

  const vixMode =
    !fullRefreshBusy &&
    status !== null &&
    status.status !== "running" &&
    cooling &&
    status.vix_retry?.needed === true;

  const start = useCallback(async () => {
    setUi({ kind: "running" });
    let started;
    try {
      started = await postMarketRefresh("vix");
    } catch {
      if (aliveRef.current) setUi({ kind: "failed", message: VIX_RETRY_FAILED_TEXT });
      return;
    }
    if (!aliveRef.current) return;
    // vix_retry_running(다른 창 등에서 이미 도는 다시 받기)도 그 id 로 결과까지 본다.
    if (
      (started.status === "accepted" || started.status === "vix_retry_running") &&
      started.refresh_id
    ) {
      follow(started.refresh_id);
      return;
    }
    setUi({ kind: "info", message: started.message });
    // not_needed · running(전체 갱신 중) — 표식을 다시 읽어 버튼 글자를 맞춘다(순번으로 더 새 상태 보호).
    readStatus()
      .then(({ s, seq }) => {
        if (aliveRef.current) applyStatusAt(s, seq);
      })
      .catch(() => undefined);
  }, [follow, readStatus, applyStatusAt]);

  // 전체 갱신 POST 가 'VIX 다시 받기 실행 중'으로 거절되면 그 다시 받기를 이어서 보인다
  // ('갱신 완료'(전체)로 보이지 않게). 넘겨받았으면 true.
  const takeOver = useCallback(
    (started: MarketRefreshStartResponse): boolean => {
      if (started.status !== "vix_retry_running" || !started.refresh_id) return false;
      follow(started.refresh_id);
      return true;
    },
    [follow],
  );

  const running = ui.kind === "running";
  const button: VixButton = {
    label: vixMode || running ? "VIX 다시 받기" : null,
    line: vixRetryLine(ui),
  };
  return {
    vixMode,
    running,
    ui,
    button,
    start,
    // 전체 갱신이 끝난 상태 응답을 받아 표식 · 대기 시간을 맞춘다(applyStatus 에서 부름).
    absorbStatus,
    takeOver,
  };
}

export function vixRetryLine(ui: VixRetryUi): { text: string; error: boolean } | null {
  switch (ui.kind) {
    case "running":
      return { text: "VIX 다시 받는 중…", error: false };
    case "completed":
      return {
        text: `VIX 다시 받기 완료(기준일 ${ui.asOf ?? "확인 불가"})`,
        error: false,
      };
    case "failed":
      return { text: `확인 필요: ${ui.message}`, error: true };
    case "info":
      return { text: ui.message, error: false };
    default:
      return null;
  }
}
