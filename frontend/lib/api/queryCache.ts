// POC3-01 REMEDIATION — frontend in-memory 조회 상태 공유 (§4.5).
//
// 목적: 화면 왕복 시 성공한 조회 결과와 진행 중 요청을 브라우저 앱 세션 메모리에서
// 공유한다. 신규 API / DB / backend cache 아님 — 순수 frontend 상태.
//
// 계약:
// - 동일 키(endpoint + 요청 조건)의 성공 결과는 재사용 (화면 왕복 시 재호출 X).
// - 동일 키의 진행 중 요청은 dedup (동시 중복 실행 X).
// - endpoint / 요청 조건이 다르면 다른 키 (같은 키로 합치지 않음).
// - 브라우저 새로고침 시 모듈 메모리가 초기화되어 정상 재조회.
// - localStorage / sessionStorage / DB / 파일 저장 없음.
// - 무효화(invalidate)는 변경 성공 이벤트에서만 호출. 변경 실패 시 무효화 금지.

import { useCallback, useEffect, useState } from "react";

type Entry<T> = {
  status: "success" | "loading" | "error";
  data?: T;
  // 진행 중 요청 dedup 용 promise.
  inflight?: Promise<T>;
  // 마지막 성공값 (재조회 실패 시 이전 성공값 구분용 · §4.4).
  lastSuccess?: T;
  // 재조회 실패 여부. 캐시 엔트리에 저장하므로 화면 재진입해도 유지된다
  // (A-1(2): 이전 성공값이 재진입 후 정상값으로 위장되지 않게).
  refetchFailed?: boolean;
};

// 키 → 엔트리. 모듈 스코프라 앱 세션 동안만 유지 (새로고침 시 소멸).
const store = new Map<string, Entry<unknown>>();
// 키별 구독자 (해당 키 갱신 시 리렌더 트리거).
const subscribers = new Map<string, Set<() => void>>();

function notify(key: string) {
  const subs = subscribers.get(key);
  if (subs) for (const fn of subs) fn();
}

function subscribe(key: string, fn: () => void): () => void {
  let subs = subscribers.get(key);
  if (!subs) {
    subs = new Set();
    subscribers.set(key, subs);
  }
  subs.add(fn);
  return () => {
    subs?.delete(fn);
  };
}

/**
 * 키에 대한 조회를 실행하고 캐시한다. 이미 성공 결과가 있으면 그대로 반환하고
 * fetcher 를 호출하지 않는다. 진행 중 요청이 있으면 그 promise 를 공유한다.
 */
async function fetchShared<T>(
  key: string,
  fetcher: () => Promise<T>,
  opts: { force?: boolean } = {},
): Promise<T> {
  const existing = store.get(key) as Entry<T> | undefined;

  if (!opts.force && existing?.status === "success" && existing.data !== undefined) {
    return existing.data;
  }
  if (existing?.inflight) {
    // 동일 진행 중 요청 dedup.
    return existing.inflight;
  }

  const inflight = fetcher()
    .then((data) => {
      // 성공: refetchFailed 해제 (stale 경고 제거).
      store.set(key, {
        status: "success",
        data,
        lastSuccess: data,
        refetchFailed: false,
      });
      notify(key);
      return data;
    })
    .catch((err) => {
      // 재조회 실패: 이전 성공값(lastSuccess)은 보존하되 refetchFailed 를 캐시
      // 엔트리에 저장한다 (A-1(2): 화면 재진입해도 stale 유지). 이전 성공값이
      // 없으면 error.
      const prev = store.get(key) as Entry<T> | undefined;
      const hasPrev = prev?.lastSuccess !== undefined;
      store.set(key, {
        status: hasPrev ? "success" : "error",
        data: prev?.lastSuccess,
        lastSuccess: prev?.lastSuccess,
        refetchFailed: true,
      });
      notify(key);
      throw err;
    });

  store.set(key, {
    status: existing?.status === "success" ? "success" : "loading",
    data: existing?.data,
    lastSuccess: existing?.lastSuccess,
    refetchFailed: existing?.refetchFailed,
    inflight,
  });
  return inflight;
}

/**
 * 키(또는 prefix)에 해당하는 캐시를 무효화한다. 변경 성공 이벤트에서만 호출.
 * prefix 매칭으로 관련 읽기만 무효화한다 (§4.5: 관련 읽기만 무효화).
 */
export function invalidateQueries(keyPrefix: string): void {
  const toDelete: string[] = [];
  for (const k of store.keys()) {
    if (k === keyPrefix || k.startsWith(keyPrefix)) toDelete.push(k);
  }
  for (const k of toDelete) {
    store.delete(k);
    notify(k);
  }
}

// 테스트/디버그용: 전체 캐시 초기화 (새로고침 상당).
export function __resetQueryCache(): void {
  store.clear();
  subscribers.clear();
}

export type QueryState<T> =
  | { phase: "idle" } // not_loaded — 아직 조회 안 함 (§ lazy 시장 카드)
  | { phase: "loading" }
  | { phase: "success"; data: T; stale: boolean }
  | { phase: "error"; lastData?: T };

/**
 * 자동 조회 hook. lazy=false(기본) 이면 마운트 시 1회 조회. lazy=true 이면
 * idle 상태로 시작하고 reload() 호출 시에만 조회 (§ 시장 카드).
 *
 * key 는 endpoint + 요청 조건을 유일하게 식별해야 한다.
 */
export function useSharedQuery<T>(
  key: string,
  fetcher: () => Promise<T>,
  opts: { lazy?: boolean } = {},
): QueryState<T> & { reload: () => void; reloadAsync: () => Promise<T> } {
  const lazy = opts.lazy ?? false;
  const [, forceRender] = useState(0);
  const rerender = useCallback(() => forceRender((n) => n + 1), []);

  // 키 갱신 구독.
  useEffect(() => subscribe(key, rerender), [key, rerender]);

  // 결과(성공/실패)를 알아야 하는 호출부는 runAsync 를 await 한다.
  const runAsync = useCallback(
    (force: boolean) => fetchShared(key, fetcher, { force }),
    // fetcher 는 호출부에서 안정적으로 전달해야 한다 (모듈 함수 래핑).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [key],
  );

  const run = useCallback(
    (force: boolean) => {
      // 실패 상태(refetchFailed)는 캐시 엔트리에 저장되므로 로컬 state 불필요.
      runAsync(force).catch(() => {
        // 에러는 fetchShared 가 엔트리에 refetchFailed 로 기록 후 rethrow.
      });
    },
    [runAsync],
  );

  // 비-lazy: 마운트 시 캐시에 성공값 없으면 1회 조회. 있으면 재사용 (재호출 X).
  useEffect(() => {
    if (lazy) return;
    const e = store.get(key) as Entry<T> | undefined;
    if (e?.status === "success" && e.data !== undefined) return;
    if (e?.inflight) return;
    run(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const reload = useCallback(() => run(true), [run]);
  const reloadAsync = useCallback(() => runAsync(true), [runAsync]);

  // 상태는 전적으로 캐시 엔트리에서 파생 → 화면 재진입해도 refetchFailed(stale)
  // 가 유지된다 (A-1(2)).
  const entry = store.get(key) as Entry<T> | undefined;
  let state: QueryState<T>;
  if (entry?.status === "success" && entry.data !== undefined) {
    // 이전 성공값 존재. refetchFailed 면 stale=true (재조회 실패 · 최신 아님).
    state = { phase: "success", data: entry.data, stale: !!entry.refetchFailed };
  } else if (entry?.inflight) {
    state = { phase: "loading" };
  } else if (entry?.status === "error") {
    // 이전 성공값 없이 실패.
    state = { phase: "error" };
  } else if (lazy) {
    state = { phase: "idle" };
  } else {
    state = { phase: "loading" };
  }

  return { ...state, reload, reloadAsync };
}
