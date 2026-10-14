"use client";

// POC5-12 — 「요즘 잘 오르는 ETF」 시장 TOP N 조회(설계 §4 · PLAN §3 보완 1 · 3 · 판정 §4).
//
// - 입력(필터 · 정렬 기준 · 방향)이 바뀌면 다시 읽는다(useEffect 하나가 조회 트리거 · B-6 NOTE).
// - 순번: 늦게 온 이전 요청 응답은 무시한다(떠난 화면의 갱신은 React 가 버린다).
// - 같은 입력 재조회가 실패하면 받은 자료를 두고 오류 한 줄(reloadError)만 보인다. 입력을 바꾼 뒤
//   실패하면 오류 카드(이전 조건 자료를 새 결과처럼 보이지 않음).
// - reloadLatest: 갱신 · 'VIX 다시 받기'가 끝난 뒤 다시 읽기. 그 전에 보낸 요청에 붙지 않고 새로
//   보내며, 상태 확인 반복(setInterval)이 클릭 때 함수를 쥐고 있어도 늘 지금 입력으로 읽는다
//   (갱신 중 필터를 바꾼 경우).
// 화면 컴포넌트(MarketDiscoveryView)의 새 책임을 줄이려고 따로 둔다(KS-10).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchMarketTopnLatest,
  forgetMarketTopnInflight,
  type MarketBasis,
  type MarketOrder,
  type MarketTopNFilterOptions,
  type MarketTopNResponse,
} from "@/lib/api";

export type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string }
  | { phase: "ready"; data: MarketTopNResponse };

export function useMarketTopnLoad(
  filters: MarketTopNFilterOptions,
  basis: MarketBasis,
  order: MarketOrder,
  describeError: (e: unknown) => string,
) {
  const [state, setState] = useState<LoadState>({ phase: "loading" });
  const [reloadError, setReloadError] = useState<string | null>(null);
  const seqRef = useRef(0);
  const lastReadyRef = useRef<{ key: string; data: MarketTopNResponse } | null>(null);

  const loadTopn = useCallback(() => {
    const seq = ++seqRef.current;
    const options = {
      excludeInverse: filters.excludeInverse,
      excludeLeveraged: filters.excludeLeveraged,
      excludeSynthetic: filters.excludeSynthetic,
      excludeFutures: filters.excludeFutures,
    };
    const key = JSON.stringify([options, basis, order]);
    setState({ phase: "loading" });
    setReloadError(null);
    fetchMarketTopnLatest(10, { ...options, basis, order })
      .then((data) => {
        if (seq !== seqRef.current) return;
        lastReadyRef.current = { key, data };
        setState({ phase: "ready", data });
      })
      .catch((e) => {
        if (seq !== seqRef.current) return;
        const prev = lastReadyRef.current;
        if (prev && prev.key === key) {
          setState({ phase: "ready", data: prev.data });
          setReloadError(describeError(e));
        } else {
          setState({ phase: "error", message: describeError(e) });
        }
      });
  }, [filters, basis, order, describeError]);

  const latestRef = useRef(loadTopn);
  useEffect(() => {
    latestRef.current = loadTopn;
    loadTopn();
  }, [loadTopn]);

  const reloadLatest = useCallback(() => {
    forgetMarketTopnInflight();
    latestRef.current();
  }, []);

  return { state, reloadError, reloadLatest };
}
