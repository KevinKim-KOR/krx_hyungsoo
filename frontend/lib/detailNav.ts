// POC6-32 V2(PLAN §2 S4 · S6 · §4-4 · §9 I-1 ~ I-5) — 상세 화면 이동 장치.
//
// 1) 보낸 화면 기록(trail · 이 탭 메모리만 · 새로 고치면 없어짐)
//    - 화면 안에서 상세(메뉴에 없는 화면)를 열면 지금 화면을 기록 끝에 넣는다. 그 화면은 내리지 않고 숨겨 두므로
//      [← 보낸 화면으로]로 돌아가면 고른 것 · 조건 · 열린 행 · 받아 둔 응답이 그대로다(I-1 · I-5).
//    - [← 보낸 화면으로]는 한 단계씩 돌아간다(상세 → 상세도 한 단계씩 · I-2).
//    - 메뉴를 누르면 기록을 버리고 그 화면을 처음부터 그린다(지금처럼). 기록이 없을 때 지금 화면 메뉴를 다시 누르면 그대로.
//    - 화면 안에서 상세가 아닌 화면으로 가면 기록을 버린다(지금처럼 그 화면을 처음부터).
//    - 메뉴 강조 = 처음 보낸 화면(기록 첫 칸 · I-4).
//    - 화면 key 의 종류는 이 모듈이 모른다(lib 는 화면 모듈을 가져오지 않음 · 의존 방향 시험) — 부르는 쪽이 상세 여부를 넘긴다.
// 2) 한 번 넘김(같은 탭 · 모듈 메모리 · 한 번 읽으면 비움 · 저장 없음 · compareSelection 과 같은 방식)
//    - 「ETF 구성종목」 한 ETF(S6) · 「AI 투자 세션」 기록 열기(§4-4).

export interface NavEntry<K extends string> {
  key: K;
  // 화면을 새로 그릴 때마다 새 번호(같은 key 라도 번호가 다르면 다른 화면 · 처음부터 그림)
  id: number;
}

export interface NavState<K extends string> {
  // 숨겨 둔 보낸 화면(앞 = 처음 보낸 화면)
  trail: NavEntry<K>[];
  active: NavEntry<K>;
  nextId: number;
}

export function navStart<K extends string>(key: K): NavState<K> {
  return { trail: [], active: { key, id: 0 }, nextId: 1 };
}

// 메뉴 클릭 — 기록을 버리고 처음부터. 기록이 없고 지금 화면과 같은 메뉴면 그대로(같은 메뉴 다시 누름 = 변화 없음).
export function navSelect<K extends string>(s: NavState<K>, key: K): NavState<K> {
  if (s.trail.length === 0 && s.active.key === key) return s;
  return { trail: [], active: { key, id: s.nextId }, nextId: s.nextId + 1 };
}

// 화면 안 이동 — fromId = 이동을 부른 화면. 숨겨 둔 화면(보이는 화면이 아님)이 부른 이동과 지금 화면으로의 이동은 무시한다.
// 상세로 가면 지금 화면을 기록 끝에 넣고, 상세가 아니면 기록을 버린다.
export function navGo<K extends string>(s: NavState<K>, fromId: number, key: K, toDetail: boolean): NavState<K> {
  if (fromId !== s.active.id || key === s.active.key) return s;
  return {
    trail: toDetail ? [...s.trail, s.active] : [],
    active: { key, id: s.nextId },
    nextId: s.nextId + 1,
  };
}

// [← 보낸 화면으로] — 기록 끝 화면(숨겨 둔 그 화면 그대로)으로 한 단계.
export function navBack<K extends string>(s: NavState<K>): NavState<K> {
  if (s.trail.length === 0) return s;
  return { trail: s.trail.slice(0, -1), active: s.trail[s.trail.length - 1], nextId: s.nextId };
}

// 메뉴 강조 — 처음 보낸 화면(기록이 없으면 지금 화면).
export function navHighlight<K extends string>(s: NavState<K>): K {
  return s.trail.length > 0 ? s.trail[0].key : s.active.key;
}

// 돌아갈 화면(기록 끝 · 없으면 null).
export function navSender<K extends string>(s: NavState<K>): NavEntry<K> | null {
  return s.trail.length > 0 ? s.trail[s.trail.length - 1] : null;
}

// 그릴 화면 전부(숨겨 둔 보낸 화면 → 지금 화면).
export function navStack<K extends string>(s: NavState<K>): NavEntry<K>[] {
  return [...s.trail, s.active];
}

// ── 「ETF 구성종목」 한 ETF(PLAN S6) ─────────────────────────────────────────────
export interface ExposureSinglePreset {
  ticker: string;
  name: string;
  // 보낸 화면 이름(예: 「주간 ETF 점검」)
  from: string;
  // 보낸 화면의 목록 조건(받는 화면이 해석)
  condition?: unknown;
}

let pendingExposure: ExposureSinglePreset | null = null;

export function presetExposureSingle(p: ExposureSinglePreset): void {
  pendingExposure = { ...p };
}

export function takeExposureSingle(): ExposureSinglePreset | null {
  const p = pendingExposure;
  pendingExposure = null;
  return p;
}

// ── 「AI 투자 세션」 기록 열기(PLAN §4-4) ────────────────────────────────────────
let pendingRecord: string | null = null;

export function presetOpenRecord(id: string): void {
  pendingRecord = id;
}

export function takeOpenRecord(): string | null {
  const id = pendingRecord;
  pendingRecord = null;
  return id;
}
