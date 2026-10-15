// POC5-15 — 현재 시장 · 보유 상태 조합(설계 V1 §2~§4 · PLAN 판정 §2 · §5).
// 이미 받은 보유 · 근거 응답과 요청 성공 여부만 쓰는 순수 함수다. 새 조회 · 새 임계 · 가중치 없음.
// 「오늘의 투자 점검」 보유 띠와 「확인 근거」 요약이 같은 함수를 쓴다(같은 입력 → 같은 문구).
import type { EnrichedHoldingsResult, HoldingsMarketEvidenceResponse } from "@/lib/api";
import type { QueryState } from "@/lib/api/queryCache";
import { buildDeclineSummary, regimeText, type DeclineSummary } from "./declineSummary";
import { buildRiskEvidenceRows, type RiskEvidenceRow } from "./helpers";

export type MarketState = "down" | "not_down" | "unknown";
export type HoldingsState = "down_found" | "none_found" | "unknown" | "no_holdings";

// 시장 판정 함수(app/market_regime.py :: _label_from_score)의 유효 코드. 그 밖
// (unavailable · 없음 · 모르는 코드 · available=false)은 '미확인' — '하락 아님'으로 보지 않는다.
const DOWN_CODES = new Set(["bear"]);
const NOT_DOWN_CODES = new Set(["bull", "neutral"]);

export function marketStateOf(evidence: HoldingsMarketEvidenceResponse | null): MarketState {
  const mp = evidence?.judgment_summary?.market_position as
    | { available?: boolean; regime_code?: string | null }
    | null
    | undefined;
  if (!mp?.available || typeof mp.regime_code !== "string") return "unknown";
  if (DOWN_CODES.has(mp.regime_code)) return "down";
  if (NOT_DOWN_CODES.has(mp.regime_code)) return "not_down";
  return "unknown";
}

// s = 13 요약(두 응답 모두 받았을 때) · empty = 정상 보유 응답이 빈 목록.
export function holdingsStateOf(s: DeclineSummary | null, empty: boolean): HoldingsState {
  if (empty) return "no_holdings";
  if (!s) return "unknown";
  if (s.inBand > 0) return "down_found";
  if (s.total > 0 && s.judgeable === s.total) return "none_found";
  return "unknown";
}

// 설계 §4 표(판정 Q4 로 '하락 아님 · 하락 없음' 문구 교체).
const TEXT: Record<MarketState, Record<Exclude<HoldingsState, "no_holdings">, string>> = {
  down: {
    down_found: "시장·보유 동반 약세",
    none_found: "시장 하락 · 보유 하락 구간 미해당",
    unknown: "시장 하락 · 보유 판정 불완전",
  },
  not_down: {
    down_found: "보유 하락 구간 확인",
    none_found: "시장·보유 하락 구간 미해당",
    unknown: "자료 확인 필요",
  },
  unknown: {
    down_found: "보유 하락 구간 확인 · 시장 판정 불가",
    none_found: "보유 하락 구간 미해당 · 시장 판정 불가",
    unknown: "자료 확인 필요",
  },
};
export const NO_HOLDINGS_TEXT = "보유 판정 대상 없음";
export const PARTIAL_JUDGE_TEXT = "일부 종목 판정 불가";

export interface RiskCombination {
  market: MarketState;
  holdings: HoldingsState;
  text: string;
  // 판정 가능 a < 보유 b — 하락 있음이어도 · 미확인이어도 '일부 종목 판정 불가'를 함께 보인다.
  partial: boolean;
}

export function combineRiskState(
  market: MarketState,
  holdings: HoldingsState,
  s: DeclineSummary | null,
): RiskCombination {
  const text = holdings === "no_holdings" ? NO_HOLDINGS_TEXT : TEXT[market][holdings];
  const partial = !!s && s.total > 0 && s.judgeable < s.total;
  return { market, holdings, text, partial };
}

export type FailedQuery = "holdings" | "evidence" | "both" | null;
// 판정 §2 Q1 — 실제 실패한 조회만 한 문장으로(실패하지 않은 자료를 실패라 쓰지 않는다).
export const FAILURE_TEXT: Record<Exclude<FailedQuery, null>, string> = {
  holdings: "보유 자료를 불러오지 못했습니다.",
  evidence: "확인 근거를 불러오지 못했습니다.",
  both: "보유 자료와 확인 근거를 불러오지 못했습니다.",
};

export interface RiskStateView {
  combo: RiskCombination;
  summary: DeclineSummary | null;
  regime: string | null; // 시장 미확인이면 null(국면 이름을 붙이지 않음)
  failed: FailedQuery; // 빈 보유가 확인되면 null(대상 없음이 먼저)
}

// 두 조회가 끝나기 전(받는 중)이면 null — 판정하지 않는다.
// 판정 순서: 정상 응답의 빈 보유 → 쓸 자료 없음(error) → 13 요약.
// 다시 읽기가 실패해도 받은 자료가 남아 있으면(success · stale) 그 자료로 판정한다(queryCache).
// rows: 「확인 근거」처럼 같은 행을 이미 만든 화면은 넘겨서 다시 만들지 않는다.
export function riskStateFromQueries(
  holdings: QueryState<EnrichedHoldingsResult>,
  evidence: QueryState<HoldingsMarketEvidenceResponse>,
  rows?: RiskEvidenceRow[],
): RiskStateView | null {
  const settled = (p: string) => p === "success" || p === "error";
  if (!settled(holdings.phase) || !settled(evidence.phase)) return null;
  const empty = holdings.phase === "success" && holdings.data.items.length === 0;
  const ev = evidence.phase === "success" ? evidence.data : null;
  const summary =
    !empty && holdings.phase === "success" && ev
      ? buildDeclineSummary(
          rows ?? buildRiskEvidenceRows(holdings.data.items, ev.holdings).rows,
          ev,
        )
      : null;
  const market = marketStateOf(ev);
  const hErr = holdings.phase === "error";
  const eErr = evidence.phase === "error";
  const failed: FailedQuery = empty
    ? null
    : hErr && eErr
      ? "both"
      : hErr
        ? "holdings"
        : eErr
          ? "evidence"
          : null;
  return {
    combo: combineRiskState(market, holdingsStateOf(summary, empty), summary),
    summary,
    regime: market !== "unknown" && ev ? regimeText(ev) : null,
    failed,
  };
}

// 판정 §5 — '?' 도움말: 지금 조합의 뜻 → 표시값의 기준 → 지금 해당하는 제한(해당하는 것만).
const MEANING: Record<string, string> = {
  "시장·보유 동반 약세":
    "기존 시장 국면이 하락장이고, 보유 종목 중 PC 20저장일 하락 구간에 든 종목이 있습니다. 시장 국면이 각 종목 하락의 원인이라는 뜻은 아닙니다.",
  "보유 하락 구간 확인":
    "시장 국면은 하락장이 아니지만, 보유 종목 중 PC 20저장일 하락 구간에 든 종목이 있습니다.",
  "시장 하락 · 보유 하락 구간 미해당":
    "시장 국면은 하락장이고, 보유 종목 중 PC 20저장일 하락 구간에 든 종목은 없습니다. ‘미해당’은 지금 기준에 해당하지 않았다는 뜻입니다.",
  "시장·보유 하락 구간 미해당":
    "시장 국면이 하락장이 아니고, 보유 종목 중 PC 20저장일 하락 구간에 든 종목도 없습니다. ‘미해당’은 지금 기준에 해당하지 않았다는 뜻입니다.",
  "보유 하락 구간 확인 · 시장 판정 불가":
    "보유 종목 중 PC 20저장일 하락 구간에 든 종목이 있습니다. 시장 국면은 판정할 자료가 없습니다.",
  "보유 하락 구간 미해당 · 시장 판정 불가":
    "보유 종목 중 PC 20저장일 하락 구간에 든 종목은 없습니다. 시장 국면은 판정할 자료가 없습니다. ‘미해당’은 지금 기준에 해당하지 않았다는 뜻입니다.",
  "시장 하락 · 보유 판정 불완전":
    "시장 국면은 하락장입니다. 보유 종목의 하락 구간은 자료가 없거나 판정하지 못한 종목이 있어 다 확인하지 못했습니다.",
  "자료 확인 필요": "시장 국면이나 보유 하락 구간을 판정할 자료가 부족합니다.",
  "보유 판정 대상 없음": "보유 종목이 없어 하락 구간을 판정할 대상이 없습니다.",
};
export const HELP_BAND_BASIS =
  "하락 구간은 PC 저장 종가 21개로 얻은 20저장일 변화를 소수 첫째 자리로 반올림한 뒤 −5% · −8% · −10% 경계로 나눕니다(OCI 보유 알림과 같은 경계). PC 저장 종가 기준이라 OCI 알림과 값이 다를 수 있습니다.";
export const HELP_SHARE_BASIS = "보유 평가 비중은 보유 현황의 평가금액을 종목별로 합산해 계산합니다.";
export const HELP_MARKET_BASIS = "시장 국면은 KODEX200 기준 기존 시장 판정입니다.";
// 판정하지 않은 이유는 종목마다 다르다(기준일 다름 · 저장 종가 부족 · 값 확인 불가 · 계좌 간 흐름 값 다름 ·
// 근거 항목 없음) — 한 가지로 단정하지 않고 종목 상세로 보낸다.
export const HELP_PARTIAL_JUDGE =
  "일부 종목은 구간을 판정하지 않았습니다(가격 기준일이 다르거나 저장 종가가 부족한 경우 등). 종목별 이유는 「확인 근거」 종목 상세에서 볼 수 있습니다.";
export const HELP_PARTIAL_EVAL =
  "평가금액을 확인하지 못한 종목이 있어 비중은 확인된 평가금액만으로 계산했습니다.";
export const HELP_SHARE_UNAVAILABLE =
  "평가금액을 확인하지 못해 보유 평가 비중은 확인 불가입니다.";

export function riskHelpParagraphs(v: RiskStateView): string[] {
  const out: string[] = [MEANING[v.combo.text] ?? ""];
  if (v.summary) out.push(HELP_BAND_BASIS, HELP_SHARE_BASIS);
  if (v.combo.market !== "unknown") out.push(HELP_MARKET_BASIS);
  if (v.combo.partial) out.push(HELP_PARTIAL_JUDGE);
  // 기본 화면과 같은 조건: 비중이 '확인 불가'면 그 사실, 계산했으면 일부 미확인 문단(DeclineSummaryBlock · 오늘 띠).
  if (v.summary && v.summary.inBandShare === null) out.push(HELP_SHARE_UNAVAILABLE);
  else if (v.summary?.evalPartial) out.push(HELP_PARTIAL_EVAL);
  return out.filter(Boolean);
}
