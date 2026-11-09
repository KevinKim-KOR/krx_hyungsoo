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
// - 2026-11-02 POC6-16: 성공한 값과 그 값을 받은 시각(successAt · 이 탭 메모리)을 같이 둔다.
//   실패 · 캐시 재사용 · 다시 그리기 때는 시각을 바꾸지 않는다(판정 §4 — 이전 결과를 보일 때 그 시각).
// - 2026-11-09 POC6-27(검증자 r1 F1): 응답 순서 보호 — 키마다 쓰기 순번(seq)을 둔다. 조회는 시작할 때 순번을
//   받고, 끝났을 때 그 키의 순번이 그대로일 때만 쓴다. [이 자료로 계속] 반영(commitQuery)이나 같은 키의 새 조회가
//   순번을 바꾸면 그 전에 시작한 조회의 늦은 성공 · 실패는 버린다(새 값을 옛 응답이 덮지 않음). 무효화로 칸이
//   비었고 새 조회가 없으면 기존처럼 그 응답을 넣는다(비운 칸을 '불러오는 중'에 묶어 두지 않음).

import { useCallback, useEffect, useState } from "react";

type Entry<T> = {
  status: "success" | "loading" | "error";
  data?: T;
  // 진행 중 요청 dedup 용 promise.
  inflight?: Promise<T>;
  // 마지막 성공값 (재조회 실패 시 이전 성공값 구분용 · §4.4).
  lastSuccess?: T;
  // 마지막 성공값을 받은 시각(Date.now · POC6-16). 성공 때만 새로 쓴다.
  lastSuccessAt?: number;
  // 재조회 실패 여부. 캐시 엔트리에 저장하므로 화면 재진입해도 유지된다
  // (A-1(2): 이전 성공값이 재진입 후 정상값으로 위장되지 않게).
  refetchFailed?: boolean;
  // 쓰기 순번(POC6-27 · 위 계약). 조회 시작 · 반영 때 새로 받는다.
  seq?: number;
};

// 키 → 엔트리. 모듈 스코프라 앱 세션 동안만 유지 (새로고침 시 소멸).
const store = new Map<string, Entry<unknown>>();
// 키별 구독자 (해당 키 갱신 시 리렌더 트리거).
const subscribers = new Map<string, Set<() => void>>();
let seqCounter = 0;

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

  const mySeq = ++seqCounter;
  // 끝났을 때 이 조회가 아직 그 키의 마지막 쓰기인가(반영 · 새 조회가 있었으면 아님 · 무효화로 빈 칸이면 씀).
  const stillMine = () => {
    const cur = store.get(key);
    return cur === undefined || cur.seq === mySeq;
  };
  const inflight = fetcher()
    .then((data) => {
      if (!stillMine()) return data; // 늦은 옛 응답 — 캐시에 쓰지 않는다(F1)
      // 성공: refetchFailed 해제 (stale 경고 제거).
      store.set(key, {
        status: "success",
        data,
        lastSuccess: data,
        lastSuccessAt: Date.now(),
        refetchFailed: false,
        seq: mySeq,
      });
      notify(key);
      return data;
    })
    .catch((err) => {
      // 재조회 실패: 이전 성공값(lastSuccess)은 보존하되 refetchFailed 를 캐시
      // 엔트리에 저장한다 (A-1(2): 화면 재진입해도 stale 유지). 이전 성공값이
      // 없으면 error.
      if (!stillMine()) throw err; // 늦은 옛 실패 — 더 새 값에 '다시 읽기 실패'를 붙이지 않는다(F1)
      const prev = store.get(key) as Entry<T> | undefined;
      const hasPrev = prev?.lastSuccess !== undefined;
      store.set(key, {
        status: hasPrev ? "success" : "error",
        data: prev?.lastSuccess,
        lastSuccess: prev?.lastSuccess,
        lastSuccessAt: prev?.lastSuccessAt,
        refetchFailed: true,
        seq: mySeq,
      });
      notify(key);
      throw err;
    });

  store.set(key, {
    status: existing?.status === "success" ? "success" : "loading",
    data: existing?.data,
    lastSuccess: existing?.lastSuccess,
    lastSuccessAt: existing?.lastSuccessAt,
    refetchFailed: existing?.refetchFailed,
    inflight,
    seq: mySeq,
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

// POC6-27 — '받아 두고 고른 뒤 반영'([요약 다시 읽기] 확인 창). 받는 동안은 캐시를 건드리지 않고
// (호출부가 fetcher 를 직접 부름), 사용자가 [이 자료로 계속]을 고르면 그 결과를 아래 둘로 반영한다.
// [취소]면 아무것도 부르지 않는다 — 이전 값 · 성공 시각 · 실패 표시가 그대로 남는다.
// `at` = 실제로 받은 시각(창을 오래 열어 둬도 '읽은 시각'이 고른 시각으로 밀리지 않게 · 판정 Q8).
// 반영은 새 순번을 받는다 — 그 전에 시작한 조회(예: 화면을 열 때의 첫 조회)가 늦게 끝나도 이 값을 덮지 않는다(검증자 r1 F1).
export function commitQuery<T>(key: string, data: T, at: number = Date.now()): void {
  store.set(key, {
    status: "success",
    data,
    lastSuccess: data,
    lastSuccessAt: at,
    refetchFailed: false,
    seq: ++seqCounter,
  });
  notify(key);
}

// 받아 둔 조회가 실패했을 때 — fetchShared 실패 경로와 같은 표시(이전 값 · 그 시각 보존 · 다시 읽기 실패).
// 새 값을 쓰지 않으므로 진행 중인 조회의 순번은 그대로 둔다 — 그 조회가 나중에 성공하면 그 값이 들어온다.
// (표시는 지금 실패 그대로 — 이전 값이 없으면 오류 · 요청 공유는 끊는다)
export function markQueryFailed(key: string): void {
  const prev = store.get(key);
  const hasPrev = prev?.lastSuccess !== undefined;
  store.set(key, {
    status: hasPrev ? "success" : "error",
    data: prev?.lastSuccess,
    lastSuccess: prev?.lastSuccess,
    lastSuccessAt: prev?.lastSuccessAt,
    refetchFailed: true,
    seq: prev?.seq,
  });
  notify(key);
}

// 테스트/디버그용: 전체 캐시 초기화 (새로고침 상당).
export function __resetQueryCache(): void {
  store.clear();
  subscribers.clear();
}

export type QueryState<T> =
  | { phase: "idle" } // not_loaded — 아직 조회 안 함 (§ lazy 시장 카드)
  | { phase: "loading" }
  | { phase: "success"; data: T; stale: boolean; successAt?: number }
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
    state = {
      phase: "success",
      data: entry.data,
      stale: !!entry.refetchFailed,
      successAt: entry.lastSuccessAt,
    };
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
