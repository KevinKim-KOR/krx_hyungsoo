// POC6-32 V2(PLAN §4-1 · §9 I-23) — 공통 시장 근거(`GET /market/evidence` · 저장값만 읽음 · 외부 조회 0 · 시장 DB
// 파일이 없으면 만들지 않고 unavailable · 있으면 서버의 기존 읽기 함수가 표 확인 — 서버 `app/market_evidence.py` 설명).
// 「오늘의 투자 점검」 [AI용 시장 정보 복사]는 누를 때마다 이 응답을 새로 읽어, 기준(시장 판정 · 코스피 · 수급 기준일)이
// 화면과 같을 때만 응답 글(`daily_text`)을 그대로 복사한다. 못 읽거나 글이 없으면 복사하지 않는다(대신할 글 없음).
// 이름: 같은 폴더 marketEvidence.ts(시장 판정 칸 타입) · DASH_KEY_EVIDENCE(보유 근거)와 겹치지 않게 'common' 을 붙였다.
import { request } from "./core";

// 서버 `app/market_evidence._basis` — 화면과 복사 근거 대조용(값이 없으면 null).
export interface MarketCommonBasis {
  regime_label: string | null; // 당일 판정 이름(판정이 확인됐을 때만)
  regime_price_date: string | null; // 당일 판정이 쓴 KODEX 200 가격 날짜
  regime_price_state: string | null; // 그 가격의 저장 상태(intraday · after_close · unknown)
  kospi_date: string | null; // 코스피 최신 저장 종가 날짜
  flow_date: string | null; // 수급 최신 날짜
  common_end_date: string | null; // 가격 · 수급 공통 비교 종료일
}

export interface MarketCommonEvidence {
  status: "ok" | "partial" | "unavailable";
  message: string | null; // unavailable 일 때 사유(한국어)
  generated_at: string;
  review_date: string;
  basis: MarketCommonBasis;
  fields: Record<string, unknown>;
  daily_text: string | null; // 일일 복사 글 · unavailable 이면 null
  evidence_items: { key: string; text: string }[];
  data_status: string[];
}

export const MARKET_COMMON_EVIDENCE_KEY = "market:common-evidence";

export function fetchMarketCommonEvidence(): Promise<MarketCommonEvidence> {
  return request<MarketCommonEvidence>("GET", "/market/evidence");
}

// 화면이 지금 보이는 기준. regimePriceState 는 화면이 판정 가격 행의 상태(장중 · 마감 뒤)를 보일 때만 준다
// (undefined = 화면에 그 값이 없음 → 대조하지 않음 · 시장 판정 응답으로 대신 보일 때).
export interface ScreenBasis {
  regimeLabel: string | null;
  regimePriceDate: string | null;
  regimePriceState?: string;
  kospiDate: string | null;
  flowDate: string | null;
}

const BASIS_ITEMS: [keyof ScreenBasis, keyof MarketCommonBasis, string][] = [
  ["regimeLabel", "regime_label", "시장 판정"],
  ["regimePriceDate", "regime_price_date", "시장 판정 가격 기준일"],
  ["regimePriceState", "regime_price_state", "시장 판정 가격 상태(장중 · 마감 뒤)"],
  ["kospiDate", "kospi_date", "코스피 기준일"],
  ["flowDate", "flow_date", "수급 기준일"],
];

// 화면과 다른 항목 이름(같으면 []). 없는 값은 null 로 맞춰 비교한다(화면 · 응답 모두 없으면 같음).
export function basisDiffs(server: Partial<MarketCommonBasis>, screen: ScreenBasis): string[] {
  return BASIS_ITEMS.filter(
    ([s, k]) => !(s === "regimePriceState" && screen.regimePriceState === undefined) && (screen[s] ?? null) !== (server[k] ?? null),
  ).map(([, , label]) => label);
}

export const COPY_READ_FAILED = "복사할 시장 근거를 읽지 못해 복사하지 않았습니다 — 잠시 뒤 다시 눌러 주세요.";
export const COPY_BASIS_DIFFERS = "화면과 복사 근거가 다릅니다 — [요약 다시 읽기] 뒤 다시 누르세요";

// 복사 여부 판정(순서: 못 읽음 → 글 없음 → 기준 다름). ok 면 응답 글 그대로.
export function copyCheck(
  r: MarketCommonEvidence | null,
  screen: ScreenBasis,
): { ok: true; text: string } | { ok: false; message: string } {
  if (!r || typeof r !== "object" || !r.basis || typeof r.basis !== "object") return { ok: false, message: COPY_READ_FAILED };
  if (r.status === "unavailable" || typeof r.daily_text !== "string" || r.daily_text === "")
    return { ok: false, message: `복사할 시장 근거를 만들지 못해 복사하지 않았습니다 — ${r.message || "사유 확인 불가"}` };
  const diff = basisDiffs(r.basis, screen);
  if (diff.length > 0) return { ok: false, message: `${COPY_BASIS_DIFFERS}(다른 항목: ${diff.join(" · ")})` };
  return { ok: true, text: r.daily_text };
}

// ── 클립보드 쓰기(PLAN I-30 · 검토 F1) — 누른 순간(클릭 처리 안 · 읽기를 기다리기 전)에 쓰기를 시작한다 ──────────────
// 브라우저는 누른 동작 안에서 시작한 클립보드 쓰기만 허락할 수 있다. 공통 근거를 새로 읽고 대조한 뒤에 쓰면 그 밖이 된다.
// 그래서 글이 나중에 채워지는 클립보드 항목(ClipboardItem · 약속 값)을 누른 순간 넘기고, 읽기 · 대조가 끝나면
// - 복사함(write) = 그 글(text/plain) · 확인 창이 필요함(dialog) · 막힘(blocked) = 거절(CopySkipped) → 클립보드는 그대로.
// 확인 창은 [이 자료로 계속]을 누를 때(그 누름 안에서) writeText 로 쓴다. ClipboardItem · clipboard.write 가 없거나
// 약속 값 항목을 못 만드는 브라우저는 예전처럼 읽은 뒤 writeText(누른 동작 밖일 수 있음).
export type CopyDecision = { kind: "write"; text: string } | { kind: "dialog" } | { kind: "blocked" };

export const COPY_READING = "복사할 시장 근거를 새로 읽는 중...";
export const COPY_DONE = "AI용 시장 정보를 복사했습니다(고정 프롬프트 + 시장 근거).";
export const COPY_FAILED = "복사하지 못했습니다 — 아래 글을 직접 선택해 복사하세요.";
export const COPY_CANCELLED = "복사하지 않았습니다(취소) — 클립보드는 바뀌지 않았습니다";

// 쓰지 않기로 정한 이유 — 이 거절로 끝난 쓰기는 '복사하지 못했습니다'를 띄우지 않는다(안내는 부르는 쪽이 이미 띄움).
export class CopySkipped extends Error {
  constructor(readonly reason: "dialog" | "blocked") {
    super(reason === "dialog" ? "확인 창에서 고름" : "복사하지 않음");
  }
}

// writeText 로 쓰기(확인 창 [이 자료로 계속] · ClipboardItem 이 없는 브라우저) — done(성공 여부).
export function writeCopyText(text: string, done: (ok: boolean) => void): void {
  try {
    const p = typeof navigator !== "undefined" ? navigator.clipboard?.writeText(text) : undefined;
    if (!p) return done(false);
    p.then(
      () => done(true),
      () => done(false),
    );
  } catch {
    done(false);
  }
}

// 누른 순간에 부른다. decided = 읽기 · 대조 결과(복사 · 확인 창 · 막힘). done 은 '복사함'일 때만(성공 · 실패) 부른다.
export function startGestureCopy(decided: Promise<CopyDecision>, done: (ok: boolean, text: string) => void): void {
  const d0 = decided.catch((): CopyDecision => ({ kind: "blocked" }));
  const later = () => {
    d0.then((d) => {
      if (d.kind === "write") writeCopyText(d.text, (ok) => done(ok, d.text));
    });
  };
  const cb = typeof navigator !== "undefined" ? navigator.clipboard : undefined;
  const Item = typeof ClipboardItem === "function" ? ClipboardItem : undefined;
  if (!cb || typeof cb.write !== "function" || !Item) return later();
  const blob = d0.then((d) =>
    d.kind === "write" ? new Blob([d.text], { type: "text/plain" }) : Promise.reject(new CopySkipped(d.kind)),
  );
  blob.catch(() => undefined); // 거절 = 쓰지 않음(아래에서 결정으로 가림 · 처리 안 된 거절 경고 없음)
  let written: Promise<void>;
  try {
    written = cb.write([new Item({ "text/plain": blob })]);
  } catch {
    return later(); // 약속 값 클립보드 항목을 못 만드는 브라우저
  }
  written.then(
    () =>
      d0.then((d) => {
        if (d.kind === "write") done(true, d.text);
      }),
    (err: unknown) =>
      d0.then((d) => {
        if (d.kind === "write" && !(err instanceof CopySkipped)) done(false, d.text);
      }),
  );
}
