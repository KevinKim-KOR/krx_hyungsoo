"use client";

// POC6-27 — [최신 시장 데이터 갱신] 공용 hook(「요즘 잘 오르는 ETF」 · 「오늘의 투자 점검」 · PLAN 판정 Q7 (a)).
//
// 시작 · 상태 확인 반복 · 완료 처리는 「요즘 잘 오르는 ETF」에 있던 코드를 그대로 옮겼다(POST /market/refresh →
// GET /market/refresh/status 4초 반복 · 8분 상한 · 상한에서 마지막 1회 확인 · 화면을 떠나면 반복 중단 ·
// 멈춘 뒤 온 응답 버림 · VIX 다시 받기 넘겨받기 · 성공 때만 시장 읽기 무효화).
// 더한 것은 하나다 — 이 탭에서 시작한(또는 시작 요청이 '이미 실행 중'으로 받은) 갱신 id 를 모듈 메모리에 두고,
// 화면에 다시 들어오면 그 id 의 상태를 1회 읽어 진행을 이어 본다(같은 작업을 새로 시작하지 않음 · 저장 없음).
// 끝난 것(완료 · 실패 · 대기 · 다른 갱신)을 읽으면 메모리를 지운다.
import { useCallback, useEffect, useRef, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchMarketRefreshStatus,
  postMarketRefresh,
  type MarketRefreshStartResponse,
  type MarketRefreshStatusResponse,
} from "@/lib/api";
import { invalidateQueries } from "@/lib/api/queryCache";
import { MARKET_INVALIDATION_KEYS } from "@/lib/api/dashboardKeys";
import { getStartedRefreshId, setStartedRefreshId } from "@/lib/marketRefreshMemory";

export type RefreshUiState =
  | { kind: "idle" }
  | { kind: "starting" }
  | { kind: "running"; refreshId: string | null }
  // POC5-10 — 완료여도 확인할 사유(예: 보유 개별주 가격 갱신 실패)가 있으면 note 로 보인다.
  | { kind: "completed"; refreshId: string | null; note: string | null }
  | { kind: "failed"; message: string }
  | { kind: "cooldown"; cooldownRemainingSeconds: number }
  // POC6-29 보완 2차 — ③ 전일 자료 보충이 도는 중이라 시작 거절(실패 아님 · 끝난 뒤 다시 누름).
  | { kind: "blocked"; message: string };

const POLL_INTERVAL_MS = 4000;
// 2026-05-22 — 운영 사고 1건 후 90 → 120 으로 상향. 1115 ETF 가격 수집이
// 약 6분 8초 (368s) 걸려 90 × 4s = 360s 상한을 8초 초과했고, 그 결과 frontend
// 가 fail 표시했지만 백엔드는 그 사이 정상 완료한 사례를 차단.
const POLL_MAX_TICKS = 120; // 8분 안전 상한

export function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

export function useMarketRefresh({
  onCompleted,
  onStatus,
  takeOver,
  probeOnMount = false,
}: {
  // 성공 완료 때(시장 읽기 무효화 뒤) 화면별 다시 읽기.
  onCompleted: () => void;
  // 받은 상태 응답(VIX 다시 받기 표식 · 대기 시간 맞춤).
  onStatus?: (s: MarketRefreshStatusResponse) => void;
  // 시작 요청이 'VIX 다시 받기 실행 중'으로 거절됐을 때 넘겨받기(넘겨받았으면 true).
  takeOver?: (started: MarketRefreshStartResponse) => boolean;
  // POC6-27 — 이 탭이 시작한 갱신이 없어도 들어올 때 상태를 1회 읽어, 진행 중인 갱신이면 이어 본다
  // (「요즘 잘 오르는 ETF」는 VIX 다시 받기 hook 이 들어올 때 이미 읽으므로 쓰지 않음).
  probeOnMount?: boolean;
}) {
  const [refreshUi, setRefreshUi] = useState<RefreshUiState>({ kind: "idle" });
  const pollTickRef = useRef<number>(0);
  const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const pollGenRef = useRef(0); // POC5-12 — 멈춘 뒤 온 이전 상태 응답은 버린다(새 갱신 확인을 끊지 않게)
  const completedRef = useRef(onCompleted);
  completedRef.current = onCompleted;
  const statusRef = useRef(onStatus);
  statusRef.current = onStatus;
  const takeOverRef = useRef(takeOver);
  takeOverRef.current = takeOver;

  const stopPolling = useCallback(() => {
    pollGenRef.current += 1;
    if (pollTimerRef.current !== null) {
      clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
    pollTickRef.current = 0;
  }, []);

  useEffect(() => {
    return () => stopPolling();
  }, [stopPolling]);

  const applyStatus = useCallback(
    (status: MarketRefreshStatusResponse) => {
      statusRef.current?.(status);
      if (status.status === "running") {
        setRefreshUi({ kind: "running", refreshId: status.refresh_id ?? null });
        return;
      }
      setStartedRefreshId(null);
      if (status.status === "completed") {
        stopPolling();
        setRefreshUi({
          kind: "completed",
          refreshId: status.refresh_id ?? null,
          note: status.error_summary ?? null,
        });
        // 갱신 성공 시에만 Dashboard 의 시장 읽기 무효화 (failed 분기는 무효화
        // 안 함 — §4.5 "변경 실패 시 무효화 금지").
        for (const k of MARKET_INVALIDATION_KEYS) invalidateQueries(k);
        completedRef.current();
        return;
      }
      if (status.status === "failed") {
        stopPolling();
        setRefreshUi({
          kind: "failed",
          message: status.error_summary ?? "원인 미상",
        });
        return;
      }
      if (status.status === "skipped_cooldown") {
        stopPolling();
        setRefreshUi({
          kind: "cooldown",
          cooldownRemainingSeconds: status.cooldown_remaining_seconds,
        });
        return;
      }
      // idle — 폴링 종료
      stopPolling();
      setRefreshUi({ kind: "idle" });
    },
    [stopPolling],
  );

  const startPolling = useCallback(() => {
    stopPolling();
    const gen = pollGenRef.current;
    pollTimerRef.current = setInterval(async () => {
      pollTickRef.current += 1;
      if (pollTickRef.current > POLL_MAX_TICKS) {
        // 2026-05-22 — 운영 사고 1건 후 polling 상한 진입 시점에 한 번 더 status
        // 명시 조회. 백엔드가 polling tick 사이의 짧은 틈에 완료했지만 frontend
        // 가 fail 표시로 가버리는 케이스 차단. applyStatus 가 completed / failed /
        // cooldown / idle 모두 처리하므로 결과를 그대로 신뢰한다.
        stopPolling();
        try {
          const finalStatus = await fetchMarketRefreshStatus();
          applyStatus(finalStatus);
          if (
            finalStatus.status === "completed" ||
            finalStatus.status === "failed" ||
            finalStatus.status === "skipped_cooldown" ||
            finalStatus.status === "idle"
          ) {
            return;
          }
        } catch {
          // 마지막 조회마저 실패하면 아래 fallback fail 표시.
        }
        setRefreshUi({
          kind: "failed",
          message: "상태 확인 시간이 너무 길어졌습니다. 잠시 후 다시 시도하세요.",
        });
        return;
      }
      try {
        const status = await fetchMarketRefreshStatus();
        if (gen !== pollGenRef.current) return;
        applyStatus(status);
      } catch (e) {
        if (gen !== pollGenRef.current) return;
        stopPolling();
        setRefreshUi({ kind: "failed", message: describeError(e) });
      }
    }, POLL_INTERVAL_MS);
  }, [stopPolling, applyStatus]);

  // POC6-27 — 이 탭에서 시작한 갱신이 아직 끝나지 않았으면(다른 화면에 다녀온 경우) 상태를 1회 읽어 이어 본다.
  useEffect(() => {
    const id = getStartedRefreshId();
    if (id === null && !probeOnMount) return;
    let alive = true;
    const gen = pollGenRef.current;
    if (id === null) {
      // 진행 중이면 같은 작업으로 이어 보고(새로 시작하지 않음) · 아니면 원래 버튼(지난 결과 · 대기 안내 없음).
      fetchMarketRefreshStatus()
        .then((s) => {
          if (!alive || gen !== pollGenRef.current) return;
          statusRef.current?.(s);
          if (s.status !== "running") return;
          applyStatus(s);
          startPolling();
        })
        .catch(() => undefined); // 확인 실패 = 원래 버튼(누르면 서버가 진행 · 대기 여부를 알려 줌)
      return () => {
        alive = false;
      };
    }
    setRefreshUi({ kind: "running", refreshId: id });
    fetchMarketRefreshStatus()
      .then((s) => {
        if (!alive || gen !== pollGenRef.current) return;
        if (s.refresh_id && s.refresh_id !== id) {
          // 그 사이 다른 갱신이 기록됐다 — 이 탭이 시작한 것의 결과는 알 수 없으므로 원래 버튼으로.
          setStartedRefreshId(null);
          setRefreshUi({ kind: "idle" });
          statusRef.current?.(s);
          return;
        }
        applyStatus(s);
        if (s.status === "running") startPolling();
      })
      .catch((e) => {
        if (!alive || gen !== pollGenRef.current) return;
        setRefreshUi({ kind: "failed", message: describeError(e) });
      });
    return () => {
      alive = false;
    };
    // 화면에 들어올 때 1회만(이어받기). 이후 진행은 startPolling 이 맡는다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // POC6-29 — 시작 응답을 받은 뒤의 처리(직접 시작 · [최신 자료 갱신] 묶음 작업이 시작한 응답 넘겨받기 공통).
  const handleStarted = useCallback(
    (started: MarketRefreshStartResponse, gen: number) => {
      // 화면을 떠났어도 시작된 갱신은 기억한다(돌아오면 이어 봄 · 상태 확인은 지금 새로 열지 않음).
      if (started.status === "accepted" || started.status === "running") {
        setStartedRefreshId(started.refresh_id ?? null);
      }
      if (gen !== pollGenRef.current) return;
      if (takeOverRef.current?.(started)) {
        setRefreshUi({ kind: "idle" }); // POC5-12 — 'VIX 다시 받기'가 도는 중이라 거절됨 → 그 진행을 보인다
        return;
      }
      if (started.status === "accepted" || started.status === "running") {
        setRefreshUi({ kind: "running", refreshId: started.refresh_id ?? null });
        startPolling();
        return;
      }
      if (started.status === "skipped_cooldown") {
        setRefreshUi({
          kind: "cooldown",
          cooldownRemainingSeconds: started.cooldown_remaining_seconds,
        });
        return;
      }
      if (started.status === "prevday_running") {
        setRefreshUi({ kind: "blocked", message: started.message });
        return;
      }
      setRefreshUi({ kind: "failed", message: started.message });
    },
    [startPolling],
  );

  const start = useCallback(async () => {
    setRefreshUi({ kind: "starting" });
    const gen = pollGenRef.current; // 화면을 떠나면 올라간다(POST 응답이 늦어도 상태 확인을 새로 열지 않음)
    let started: MarketRefreshStartResponse;
    try {
      started = await postMarketRefresh();
    } catch (e) {
      setRefreshUi({ kind: "failed", message: describeError(e) });
      return;
    }
    handleStarted(started, gen);
  }, [handleStarted]);

  // POC6-29 — PC 서버 묶음 작업이 시작한 시장 갱신(시작 응답과 같은 모양)을 넘겨받아 같은 방식으로 따라간다.
  const adopt = useCallback(
    (started: MarketRefreshStartResponse) => handleStarted(started, pollGenRef.current),
    [handleStarted],
  );

  const busy = refreshUi.kind === "starting" || refreshUi.kind === "running";
  return { refreshUi, start, adopt, busy };
}
