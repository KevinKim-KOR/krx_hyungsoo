"use client";

// POC6-29(설계 §5 · PLAN §3-6 · 판정 Q7 기본안) — 「오늘의 투자 점검」 [최신 자료 갱신] 한 번.
//
// - PC 서버 묶음 작업(POST /refresh/all)이 보유 현재가 → 기존 시장 갱신 시작 순으로 잇는다. 화면은 상태
//   (GET /refresh/all/status)를 읽어 단계별 진행 · 결과를 보인다. 연타 · 다른 탭에서 같은 버튼을 눌러도 서버가 진행 중
//   작업(그 작업이 시작한 시장 갱신이 아직 도는 동안 포함)으로 연결한다(이 화면은 열릴 때 한 번 상태를 읽어 진행 중이면
//   이어서 따라간다). 「보유 현황」 [시세 갱신 (Naver)]은 묶음 작업을 만들지 않고, 겹치면 보유 현재가 조회만 서버에서
//   한 번으로 묶인다.
// - 시장 갱신 단계의 시작 응답은 기존 시장 갱신 hook 이 넘겨받아(adopt) 지금까지와 같이 진행 · 완료 · 대기(6시간 간격)를 따라간다.
// - [VIX 다시 받기](C 에서 옮김)는 기존 hook 그대로 — 시장 근거 상세 ①에서 누른다.
// - POC6-29 보완(보완 PLAN 판정 Q-R2) — 맨 앞 ⓪ 빠른 시세 단계가 끝나는 대로 먼저 알린다(onQuickDone · 6시간 대기와 무관).
// - POC6-29 보완 2차(S 판정 Q-S2) — ② 가 대기면 서버가 같은 작업에서 ③ 전일 자료 보충을 돈다. 끝나면 알린다(onPrevdayDone).
//   ③ 이 길 수 있어(수급 가져오기 상한 150초 + KRX · 해외 지표) 상태 확인 상한을 6분으로 둔다.
import { useCallback, useEffect, useRef, useState } from "react";
// 개별 모듈에서 읽는다(화면 시험이 `@/lib/api` 를 통째로 가짜로 바꾸는 방식과 겹치지 않게 · 기존 관례).
import type { MarketRefreshStartResponse, MarketRefreshStatusResponse } from "@/lib/api/market";
import {
  fetchRefreshAllStatus,
  postRefreshAll,
  type RefreshAllHoldingsStep,
  type RefreshAllPrevdayStep,
  type RefreshAllQuickStep,
  type RefreshAllStatus,
} from "@/lib/api/refreshAll";
import { useMarketRefresh, describeError } from "../useMarketRefresh";
import { useMarketVixRetry } from "../useMarketVixRetry";

export type AllPhase = "idle" | "starting" | "running" | "done" | "failed";

const POLL_MS = 1500;
const POLL_MAX = 240; // 1.5초 × 240 = 6분(③ 포함)

export function useTodayRefresh({
  onMarketCompleted,
  onHoldingsDone,
  onVixDone,
  onQuickDone,
  onPrevdayDone,
}: {
  onMarketCompleted: () => void;
  onHoldingsDone: (step: RefreshAllHoldingsStep) => void;
  onVixDone: () => void;
  onQuickDone?: (step: RefreshAllQuickStep) => void;
  onPrevdayDone?: (step: RefreshAllPrevdayStep) => void;
}) {
  const lastStatusRef = useRef<MarketRefreshStatusResponse | null>(null);
  // 화면을 떠난 뒤 도착한 응답은 버린다(묶음 작업 상태 · 시작 응답 — 검토 지적).
  const aliveRef = useRef(true);
  useEffect(() => {
    aliveRef.current = true;
    return () => {
      aliveRef.current = false;
    };
  }, []);
  const vixSinkRef = useRef<{
    absorb: (s: MarketRefreshStatusResponse) => void;
    takeOver: (s: MarketRefreshStartResponse) => boolean;
  } | null>(null);
  const marketRefresh = useMarketRefresh({
    probeOnMount: true,
    onStatus: (s) => {
      lastStatusRef.current = s;
      // 'VIX 다시 받기'가 도는 중이면 VIX hook 이 그 id 로 결과까지 따라간다(진행 표시 = 그 hook 의 상태).
      vixSinkRef.current?.absorb(s);
    },
    takeOver: (started) => vixSinkRef.current?.takeOver(started) ?? false,
    onCompleted: onMarketCompleted,
  });
  const vixRetry = useMarketVixRetry({ fullRefreshBusy: marketRefresh.busy, onRetrySucceeded: onVixDone });
  vixSinkRef.current = { absorb: vixRetry.absorbStatus, takeOver: vixRetry.takeOver };
  // 다시 받기가 끝나면(완료 · 실패) 곧바로 풀린다 — 별도 깃발을 두지 않는다(검토 지적: 깃발이 남아 버튼이 막힘).
  const vixRetryRunning = vixRetry.running;

  const [phase, setPhase] = useState<AllPhase>("idle");
  const [status, setStatus] = useState<RefreshAllStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const ticksRef = useRef(0);
  // 같은 작업의 단계 결과는 한 번만 넘긴다(상태를 여러 번 읽어도).
  const handledRef = useRef<{ job: string | null; quick: boolean; holdings: boolean; market: boolean; prevday: boolean }>({
    job: null,
    quick: false,
    holdings: false,
    market: false,
    prevday: false,
  });
  const holdingsRef = useRef(onHoldingsDone);
  holdingsRef.current = onHoldingsDone;
  const quickRef = useRef(onQuickDone);
  quickRef.current = onQuickDone;
  const prevdayRef = useRef(onPrevdayDone);
  prevdayRef.current = onPrevdayDone;
  const adoptRef = useRef(marketRefresh.adopt);
  adoptRef.current = marketRefresh.adopt;

  const stop = useCallback(() => {
    if (timerRef.current !== null) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    ticksRef.current = 0;
  }, []);
  useEffect(() => stop, [stop]);

  const apply = useCallback(
    (s: RefreshAllStatus) => {
      setStatus(s);
      const h = handledRef.current;
      if (h.job !== s.job_id) {
        handledRef.current = { job: s.job_id, quick: false, holdings: false, market: false, prevday: false };
      }
      const cur = handledRef.current;
      const qs = s.steps.quick;
      if (qs && !cur.quick && qs.status !== "pending" && qs.status !== "running") {
        cur.quick = true;
        quickRef.current?.(qs);
      }
      const hs = s.steps.holdings;
      if (hs && !cur.holdings && (hs.status === "done" || hs.status === "failed" || hs.status === "skipped")) {
        cur.holdings = true;
        holdingsRef.current(hs);
      }
      const ms = s.steps.market;
      if (ms && !cur.market && ms.status !== "pending") {
        cur.market = true;
        adoptRef.current({
          status: ms.status,
          refresh_id: ms.refresh_id ?? null,
          message: ms.message ?? "",
          cooldown_remaining_seconds: ms.cooldown_remaining_seconds ?? 0,
        });
      }
      const ps = s.steps.prevday;
      if (ps && !cur.prevday && ps.status !== "pending" && ps.status !== "running") {
        cur.prevday = true;
        prevdayRef.current?.(ps);
      }
      if (s.state === "running") setPhase("running");
      else if (s.state === "done") {
        setPhase("done");
        stop();
      } else {
        // 작업 기록이 없다(PC 서버가 다시 시작됨 등) — '갱신 중'을 계속 보이지 않고 멈춘다.
        stop();
        setPhase("failed");
        setError("자료 갱신 작업 상태를 찾지 못했습니다(PC 서버가 다시 시작됐을 수 있음). [요약 다시 읽기]로 확인하세요.");
      }
    },
    [stop],
  );

  const follow = useCallback(() => {
    stop();
    timerRef.current = setInterval(async () => {
      ticksRef.current += 1;
      if (ticksRef.current > POLL_MAX) {
        stop();
        setPhase("failed");
        setError("상태 확인 시간이 너무 길어졌습니다. 잠시 후 [요약 다시 읽기]로 확인하세요.");
        return;
      }
      let s: RefreshAllStatus;
      try {
        s = await fetchRefreshAllStatus();
      } catch (e) {
        if (!aliveRef.current) return;
        stop();
        setPhase("failed");
        setError(describeError(e));
        return;
      }
      if (!aliveRef.current) return;
      apply(s);
    }, POLL_MS);
  }, [apply, stop]);

  // 열릴 때 한 번 — 다른 탭에서 시작한 묶음 작업이 돌고 있으면 이어서 따라간다.
  useEffect(() => {
    let alive = true;
    fetchRefreshAllStatus()
      .then((s) => {
        if (!alive || s.state !== "running") return;
        apply(s);
        follow();
      })
      .catch(() => undefined);
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const startAll = useCallback(async () => {
    if (phase === "starting" || phase === "running") return;
    setPhase("starting");
    setError(null);
    let s: RefreshAllStatus;
    try {
      s = await postRefreshAll();
    } catch (e) {
      if (!aliveRef.current) return;
      setPhase("failed");
      setError(describeError(e));
      return;
    }
    if (!aliveRef.current) return;
    apply(s);
    if (s.state === "running") follow();
  }, [phase, apply, follow]);

  const busy = phase === "starting" || phase === "running";
  return { marketRefresh, vixRetry, vixRetryRunning, lastStatusRef, all: { phase, status, error, busy }, startAll };
}
