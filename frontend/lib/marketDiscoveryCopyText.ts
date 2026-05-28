// AI 투자세션 복사용 문구 생성 (POC2 — 2026-05-19 1차 + 2026-05-22 시장 판정 반영).
//
// 입력은 이미 조회된 MarketTopNResponse 의 일부 (asof / filters / candidates +
// market_context). 새 API 호출 / AI 직접 호출 / 자동 토론은 하지 않는다 — 사용자가
// 외부 AI 채널 (GPT / Gemini / Claude) 에 직접 복사·붙여넣는 입력문만 만든다.
//
// 2026-05-22 변경 (Market Regime & Benchmark Context 1차):
// - [시스템 시장 판정] 섹션 추가 (지시문 §11) — 시스템이 1차 산출한 KODEX200 기준
//   regime_label + KOSPI 보조 근거를 노출.
// - [시장 대비 후보 강도] 섹션 추가 — KODEX200 / KOSPI 대비 초과수익 표시.
// - [요청] 섹션 문구 변경 — AI 에게 장세 판정을 맡기지 않고 시스템 판정을 전제로
//   해석과 반론을 요청 (지시문 §11 / AC-19).

import type {
  ConstituentsAnalysisResponse,
  MarketCandidate,
  MarketContext,
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
  // 2026-05-22 — Market Regime & Benchmark Context. null/undefined 면 시장 판정
  // 섹션을 "판정불가 — 데이터 부족" 으로 노출.
  marketContext?: MarketContext | null;
  // 2026-05-27 — ETF Constituents & Overlap 1차 (지시문 §10). 분석 결과가 있으면
  // [구성종목 / 중복 노출] 섹션 + AI 요청 문구가 독립 테마 vs 반복 노출 해석을
  // 요구하는 형태로 강화.
  constituentsAnalysis?: ConstituentsAnalysisResponse | null;
}

function appendConstituentsSection(
  lines: string[],
  analysis: ConstituentsAnalysisResponse | null | undefined,
): void {
  if (!analysis) return;
  lines.push("[구성종목 / 중복 노출]");
  const cov = analysis.coverage;
  lines.push(
    `- 분석 대상: ${cov.requested_count}개 ETF (가용 ${cov.available_count} / 누락 ${cov.unavailable_count})`,
  );
  if (analysis.constituents.length > 0) {
    lines.push("- ETF별 상위 구성종목 (5):");
    analysis.constituents.forEach((c) => {
      if (c.status !== "ok") {
        lines.push(`  · ${c.etf_ticker} ${c.etf_name ?? "-"}: unavailable`);
        return;
      }
      const top5 = c.top_holdings
        .slice(0, 5)
        .map(
          (h) =>
            `${h.name ?? h.ticker ?? "-"} ${
              h.weight_pct !== null && h.weight_pct !== undefined
                ? `${h.weight_pct.toFixed(1)}%`
                : "-"
            }`,
        )
        .join(", ");
      const top3c = c.concentration.top3_weight_pct;
      const top5c = c.concentration.top5_weight_pct;
      lines.push(
        `  · ${c.etf_ticker} ${c.etf_name ?? "-"}: ${top5} (top3 ${
          top3c !== null && top3c !== undefined ? `${top3c.toFixed(1)}%` : "-"
        } / top5 ${
          top5c !== null && top5c !== undefined ? `${top5c.toFixed(1)}%` : "-"
        })`,
      );
    });
  }
  if (analysis.overlap_matrix.length > 0) {
    const top_pairs = [...analysis.overlap_matrix]
      .filter((p) => p.weighted_overlap_pct !== null && p.weighted_overlap_pct !== undefined)
      .sort(
        (a, b) =>
          (b.weighted_overlap_pct ?? 0) - (a.weighted_overlap_pct ?? 0),
      )
      .slice(0, 5);
    if (top_pairs.length > 0) {
      lines.push("- 중복률 상위 (top 5 쌍):");
      top_pairs.forEach((p) => {
        lines.push(
          `  · ${p.left_ticker} ↔ ${p.right_ticker}: 공통 ${p.common_count_top10}, 비중중복 ${
            p.weighted_overlap_pct !== null && p.weighted_overlap_pct !== undefined
              ? `${p.weighted_overlap_pct.toFixed(1)}%`
              : "-"
          }`,
        );
      });
    }
  }
  if (analysis.repeated_core_holdings.length > 0) {
    lines.push("- 반복 등장 핵심 종목:");
    analysis.repeated_core_holdings.slice(0, 10).forEach((r) => {
      lines.push(
        `  · ${r.name ?? r.ticker ?? "-"}: ${r.appears_in_etf_count}개 ETF`,
      );
    });
  }
}

function appendMarketContextSection(
  lines: string[],
  ctx: MarketContext | null | undefined,
): void {
  lines.push("[시스템 시장 판정]");
  if (!ctx || ctx.status === "unavailable") {
    lines.push("- 시장 국면: 판정불가 (KODEX200 시계열 부족)");
    return;
  }
  lines.push(`- 시장 국면: ${ctx.regime_label}`);
  const k = ctx.kodex200;
  if (k.status === "ok") {
    const r20 = formatPct(k.return_20d_pct);
    const r60 = formatPct(k.return_60d_pct);
    lines.push(`- 기준: KODEX200 20거래일 ${r20}, 60거래일 ${r60}`);
    const ma20 = k.ma20_position === "above" ? "위" : "아래";
    const ma60 = k.ma60_position === "above" ? "위" : "아래";
    lines.push(`- KODEX200 현재가: 20일 이동평균 ${ma20} / 60일 이동평균 ${ma60}`);
  }
  const kp = ctx.kospi;
  if (kp.status === "ok") {
    lines.push(
      `- KOSPI 보조 기준: 20거래일 ${formatPct(kp.return_20d_pct)}, 60거래일 ${formatPct(kp.return_60d_pct)}`,
    );
  } else {
    lines.push("- KOSPI 보조 기준: 데이터 없음 (N/A)");
  }
}

function appendCandidateStrengthSection(
  lines: string[],
  candidates: MarketCandidate[],
): void {
  lines.push("[시장 대비 후보 강도]");
  if (candidates.length === 0) {
    lines.push("(후보 없음)");
    return;
  }
  candidates.forEach((c, idx) => {
    const num = c.rank ?? idx + 1;
    const name = c.name ?? "-";
    const ticker = c.ticker ?? "-";
    const oneM = formatPct(c.returns?.one_month?.return_pct ?? null);
    const exK1 = formatPctp(c.excess_return?.vs_kodex200_1m_pctp ?? null);
    const exK3 = formatPctp(c.excess_return?.vs_kodex200_3m_pctp ?? null);
    lines.push(`${num}. ${name} (${ticker})`);
    lines.push(`   - 1개월 수익률: ${oneM}`);
    lines.push(`   - KODEX200 대비 1개월 초과수익: ${exK1}`);
    lines.push(`   - KODEX200 대비 3개월 초과수익: ${exK3}`);
  });
}

function formatPctp(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%p`;
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
  if (input.constituentsAnalysis) {
    // 2026-05-27 FIX (검증자 A-3 NOTE 반영) — constituentsAnalysis 가 있을 때는
    // "구성 종목 정보가 아직 포함되지 않았다" 문구를 출력하지 않는다 (직전 STEP
    // 까지의 기본 문구와 본 STEP 의 [구성종목/중복 노출] 섹션이 자기모순).
    lines.push(
      "이 입력은 ETF명/수익률 + 시장 국면 + 후보 구성종목/중복률을 묶은 해석 요청문입니다.",
    );
    lines.push(
      "구성종목 데이터는 수집된 시점의 스냅샷이며 모든 후보가 포함되지 않을 수 있습니다.",
    );
    lines.push(
      "따라서 최종 투자 판단이 아니라 시장 흐름 해석과 독립 테마 vs 반복 노출 판단이 목적입니다.",
    );
  } else {
    lines.push("이 입력은 ETF명과 기간별 수익률 기반의 1차 시장 해석용입니다.");
    lines.push("ETF 구성 종목과 구성 비중 정보는 아직 포함되지 않았습니다.");
    lines.push(
      "따라서 최종 투자 판단이 아니라 시장 흐름 해석과 추가 확인 포인트 도출이 목적입니다.",
    );
  }
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
  appendMarketContextSection(lines, input.marketContext);
  lines.push("");
  appendCandidateStrengthSection(lines, input.candidates);
  // 2026-05-27 — 구성종목/중복률 섹션 (지시문 §10). analysis 가 있을 때만 노출.
  if (input.constituentsAnalysis) {
    lines.push("");
    appendConstituentsSection(lines, input.constituentsAnalysis);
  }
  lines.push("");
  lines.push("[요청]");
  if (input.constituentsAnalysis) {
    // 구성종목 정보가 있을 때 — 독립 테마 vs 반복 노출 해석 요청 (지시문 §10).
    lines.push(
      "시스템의 시장 국면 판정, KODEX200 대비 초과수익,",
    );
    lines.push(
      "그리고 ETF 구성종목/중복률을 전제로 해석해주세요.",
    );
    lines.push("");
    lines.push(
      "ETF명이 달라도 실제로 같은 종목 노출이 반복되는지,",
    );
    lines.push(
      "독립적인 테마로 볼 수 있는 후보가 무엇인지,",
    );
    lines.push(
      "구성종목 기준으로 반대 근거를 제시해주세요.",
    );
    lines.push("");
    lines.push("매수/매도 추천은 하지 마세요.");
  } else {
    lines.push(
      "시스템의 시장 국면 판정과 KODEX200/KOSPI 대비 초과수익을 전제로,",
    );
    lines.push(
      "이 후보들이 시장 전체 상승에 따라간 것인지, 독립적인 섹터/테마 강세인지 해석해주세요.",
    );
    lines.push("");
    lines.push("매수/매도 추천은 하지 말고,");
    lines.push(
      "시스템 판정이 틀릴 수 있는 반대 근거와 추가 확인 포인트를 제시해주세요.",
    );
  }
  return lines.join("\n");
}
