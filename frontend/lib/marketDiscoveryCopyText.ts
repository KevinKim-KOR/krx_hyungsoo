// AI 투자세션 복사용 문구 생성 (2026-05-19 STEP — 지시문 §5 구조).
//
// 입력은 이미 조회된 MarketTopNResponse 의 일부 (asof / filters / candidates) 다.
// 새 API 호출 / AI 직접 호출 / 자동 토론은 하지 않는다 — 사용자가 외부 AI 채널
// (GPT / Gemini / Claude) 에 직접 복사·붙여넣는 1차 시장 해석 요청문만 만든다.
//
// AC-6: ETF 구성 종목과 구성 비중 정보가 아직 포함되지 않았다는 한계를 명시한다.
// AC-7: 요청 목적은 시장 테마 / 섹터 흐름 해석.
// AC-8: 매수 / 매도 추천을 요구하지 않는다.

import type {
  MarketCandidate,
  MarketProductTag,
  MarketTopNFilters,
} from "./api";

const TAG_LABEL_KO: Record<MarketProductTag, string> = {
  inverse: "인버스",
  leveraged: "레버리지",
  synthetic: "합성",
  futures: "선물형",
};

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function yesNo(v: boolean): string {
  return v ? "예" : "아니오";
}

function formatTags(tags: MarketProductTag[] | undefined): string {
  if (!tags || tags.length === 0) return "없음";
  return tags.map((t) => TAG_LABEL_KO[t] ?? t).join(", ");
}

export interface BuildCopyTextInput {
  asof: string;
  filters: MarketTopNFilters;
  candidates: MarketCandidate[];
}

// fail-loud 정책 (frontend/lib/api.ts 의 apiBase() 와 동일 패턴):
// asof / filters 는 백엔드 ok 응답에 항상 포함되므로 누락은 비정상 상태이다.
// "YYYY-MM-DD" 같은 placeholder 로 덮으면 사용자가 잘못된 기준일 문구를 AI 채널에
// 그대로 붙여넣을 수 있어 운영 위험이 된다. 호출자가 응답을 검증하지 않은 채로
// 본 함수를 호출했음을 명시적으로 드러낸다 (검증자 B-1 NOTE 반영).
export function buildMarketDiscoveryCopyText(input: BuildCopyTextInput): string {
  if (!input.asof || input.asof.length === 0) {
    throw new Error(
      "buildMarketDiscoveryCopyText: asof is required (no silent fallback).",
    );
  }
  const asof = input.asof;
  const lines: string[] = [];
  lines.push(`아래는 ${asof} 기준 한국 상장 ETF Market Discovery 결과입니다.`);
  lines.push("");
  lines.push("[데이터 기준]");
  lines.push(`- 데이터 기준일: ${asof}`);
  lines.push("- 데이터 출처: SQLite 저장 시장 데이터");
  lines.push("");
  lines.push("[필터 조건]");
  lines.push(`- 인버스 제외: ${yesNo(input.filters.exclude_inverse)}`);
  lines.push(`- 레버리지 제외: ${yesNo(input.filters.exclude_leveraged)}`);
  lines.push(`- 합성 제외: ${yesNo(input.filters.exclude_synthetic)}`);
  lines.push(`- 선물형 제외: ${yesNo(input.filters.exclude_futures)}`);
  lines.push("");
  lines.push("[주의]");
  lines.push("이 입력은 ETF명과 기간별 수익률 기반의 1차 시장 해석용입니다.");
  lines.push("ETF 구성 종목과 구성 비중 정보는 아직 포함되지 않았습니다.");
  lines.push(
    "따라서 최종 투자 판단이 아니라 시장 흐름 해석과 추가 확인 포인트 도출이 목적입니다.",
  );
  lines.push("");
  lines.push("[후보 ETF]");
  if (input.candidates.length === 0) {
    lines.push("(후보 없음)");
  } else {
    input.candidates.forEach((c, idx) => {
      const num = c.rank ?? idx + 1;
      const name = c.name ?? "-";
      const ticker = c.ticker ?? "-";
      lines.push(`${num}. ${name} (${ticker})`);
      lines.push(
        `   - 일간 수익률: ${formatPct(c.returns?.daily?.return_pct ?? null)}`,
      );
      lines.push(
        `   - 1개월 수익률: ${formatPct(c.returns?.one_month?.return_pct ?? null)}`,
      );
      lines.push(
        `   - 3개월 수익률: ${formatPct(c.returns?.three_month?.return_pct ?? null)}`,
      );
      lines.push(`   - 태그: ${formatTags(c.tags)}`);
    });
  }
  lines.push("");
  lines.push("[요청]");
  lines.push(
    "위 후보들이 어떤 시장 테마 또는 섹터 흐름을 시사하는지 해석해주세요.",
  );
  lines.push(
    "매수/매도 추천은 하지 말고, 추가로 확인해야 할 구성 종목, 업종, 리스크, 검증 포인트를 제시해주세요.",
  );
  return lines.join("\n");
}
