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
//
// 2026-10-17 POC5-21 (설계자 PLAN 판정 Q1 · Q2 · Q3):
// - 수익률 줄마다 실제 사용 종가 날짜(시작 → 끝). 날짜가 없으면 '계산 기간 확인 불가'.
// - 머리말은 시장 저장 최신일을 따로 적는다(후보 끝일을 보증하는 날짜로 쓰지 않음).
// - KODEX200 대비 값은 두 수익률의 차이(%p) — 두 기간을 함께 적고, 다르면 '기간 다름'.
//   섹션 제목 [시장 대비 후보 강도] → [KODEX200 대비 수익률 차이].
// - 날짜 판정은 화면과 같은 lib/returnPeriod 를 쓴다.

import type {
  ConstituentsAnalysisResponse,
  MarketCandidate,
  MarketContext,
  MarketPeriodReturn,
  MarketProductTag,
  MarketTopNFilters,
} from "./api";
import { KOSPI_SOURCE_LINE, kospiStatusText, kospiValuesUsable } from "./kospiStatus";
import { cmpState, kodexRange, valuePeriod, type CmpKey } from "./returnPeriod";

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

// POC5-21 — 수익률 뒤 실제 계산 기간(화면과 같은 응답 값 · 같은 판정). 값이 없으면 붙이지 않는다.
function periodTail(r: MarketPeriodReturn | null | undefined, daily = false): string {
  const vp = valuePeriod(r);
  if (vp.kind === "none") return "";
  if (vp.kind === "unknown") return " (계산 기간 확인 불가)";
  return ` (${daily ? "직전 저장일 대비 · " : ""}사용 종가 ${vp.start} → ${vp.end})`;
}

// POC5-21 — KODEX200 대비 수익률 차이 뒤 두 기간(화면과 같은 판정 cmpState).
function rangeText(start: string | null | undefined, end: string | null | undefined): string {
  return start && end ? `${start} → ${end}` : "확인 불가";
}

function compareTail(
  candStart: string | null | undefined,
  candEnd: string | null | undefined,
  kStart: string | null | undefined,
  kEnd: string | null | undefined,
): string {
  const cand = rangeText(candStart, candEnd);
  const k = rangeText(kStart, kEnd);
  if (!(candStart && candEnd && kStart && kEnd)) {
    return ` (기간 확인 불가 — 후보 ${cand} · KODEX200 ${k})`;
  }
  return candStart === kStart && candEnd === kEnd
    ? ` (같은 기간 ${cand})`
    : ` (기간 다름 — 후보 ${cand} · KODEX200 ${k})`;
}

function candidateCompareTail(c: MarketCandidate, key: CmpKey, ctx: MarketContext | null | undefined): string {
  const kodex = ctx?.kodex200;
  if (cmpState(c, key, kodex) === "none") return "";
  const vp = valuePeriod(key === "1m" ? c.returns?.one_month : c.returns?.three_month);
  const kd = kodexRange(kodex, key);
  return compareTail(
    vp.kind === "dated" ? vp.start : null,
    vp.kind === "dated" ? vp.end : null,
    kd?.start,
    kd?.end,
  );
}

function datesTail(start: string | null | undefined, end: string | null | undefined, head = ""): string {
  return start && end ? ` (${head}사용 종가 ${start} → ${end})` : ` (${head}계산 기간 확인 불가)`;
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
  // POC3-02D-OPS-03 확정 계약 9 — 화면 KOSPI 카드와 같은 판정 · 같은 문구('N/A' 대신).
  // 값은 정상 · 휴장일(직전 거래일 자료가 최신)일 때만 싣는다.
  // 설계자 RESULT STEP 4-2 — KOSPI 값을 싣는 줄 끝에 공식 자료원을 붙인다(같은 줄 · ' · ').
  if (kospiValuesUsable(kp)) {
    lines.push(
      `- KOSPI 보조 기준: 20거래일 ${formatPct(kp.return_20d_pct)}, 60거래일 ${formatPct(kp.return_60d_pct)} · ${KOSPI_SOURCE_LINE}`,
    );
  } else {
    lines.push(`- KOSPI 보조 기준: ${kospiStatusText(kp)}`);
  }
}

function appendCandidateStrengthSection(
  lines: string[],
  candidates: MarketCandidate[],
  ctx: MarketContext | null | undefined,
): void {
  lines.push("[KODEX200 대비 수익률 차이]");
  if (candidates.length === 0) {
    lines.push("(후보 없음)");
    return;
  }
  // POC5-21 — 화면 ? 와 같은 뜻(판정 Q1 · 기간이 다르면 초과수익 · 시장 우위로 설명하지 않음).
  lines.push(
    "- 수익률 차이 = 후보 수익률 − KODEX200 수익률(%p). 괄호의 두 기간이 다르면 같은 기간 초과수익이나 시장 대비 우위를 확인한 값이 아닙니다.",
  );
  candidates.forEach((c, idx) => {
    const num = c.rank ?? idx + 1;
    const name = c.name ?? "-";
    const ticker = c.ticker ?? "-";
    const oneM = formatPct(c.returns?.one_month?.return_pct ?? null);
    const exK1 = formatPctp(c.excess_return?.vs_kodex200_1m_pctp ?? null);
    const exK3 = formatPctp(c.excess_return?.vs_kodex200_3m_pctp ?? null);
    lines.push(`${num}. ${name} (${ticker})`);
    lines.push(`   - 1개월 수익률: ${oneM}${periodTail(c.returns?.one_month)}`);
    lines.push(`   - KODEX200 대비 1개월 수익률 차이: ${exK1}${candidateCompareTail(c, "1m", ctx)}`);
    lines.push(`   - KODEX200 대비 3개월 수익률 차이: ${exK3}${candidateCompareTail(c, "3m", ctx)}`);
  });
}

function formatPctp(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%p`;
}


// 2026-06-01 Market Discovery Evidence Closeout 1차 — 지시문 §15 단기 흐름 섹션.
function appendShortTermMomentumSection(
  lines: string[],
  candidates: MarketCandidate[],
): void {
  const hasAny = candidates.some((c) => c.short_term_momentum);
  if (!hasAny) return;
  lines.push("");
  lines.push("[단기 흐름]");
  candidates.forEach((c, idx) => {
    const num = c.rank ?? idx + 1;
    const name = c.name ?? "-";
    const ticker = c.ticker ?? "-";
    const m = c.short_term_momentum;
    if (!m || m.status !== "ok") {
      lines.push(`${num}. ${name} (${ticker}) — 단기 흐름 데이터 부족`);
      return;
    }
    lines.push(`${num}. ${name} (${ticker})`);
    // POC5-21 — 구간마다 후보 · KODEX200 의 실제 시작 · 끝(응답의 행 날짜).
    const sd = m.start_dates;
    const kd = m.kodex200_start_dates;
    const wins = [
      { n: 5, ret: m.return_5d_pct, ex: m.excess_vs_kodex200_5d_pctp, s: sd?.five_d, ks: kd?.five_d },
      { n: 10, ret: m.return_10d_pct, ex: m.excess_vs_kodex200_10d_pctp, s: sd?.ten_d, ks: kd?.ten_d },
      { n: 20, ret: m.return_20d_pct, ex: m.excess_vs_kodex200_20d_pctp, s: sd?.twenty_d, ks: kd?.twenty_d },
    ];
    for (const w of wins) {
      const tail = w.ret == null ? "" : datesTail(w.s, m.end_date);
      lines.push(`   - ${w.n}거래일 수익률: ${formatPct(w.ret ?? null)}${tail}`);
    }
    for (const w of wins) {
      const tail = w.ex == null ? "" : compareTail(w.s, m.end_date, w.ks, m.kodex200_end_date);
      lines.push(`   - KODEX200 대비 ${w.n}거래일 수익률 차이: ${formatPctp(w.ex ?? null)}${tail}`);
    }
  });
}


// 2026-06-01 Market Discovery Evidence Closeout 1차 — 지시문 §15 데이터 품질 섹션.
function appendDataQualitySection(
  lines: string[],
  candidates: MarketCandidate[],
): void {
  const hasAny = candidates.some((c) => c.data_quality);
  if (!hasAny) return;
  lines.push("");
  lines.push("[데이터 품질]");
  candidates.forEach((c, idx) => {
    const num = c.rank ?? idx + 1;
    const name = c.name ?? "-";
    const ticker = c.ticker ?? "-";
    const dq = c.data_quality;
    if (!dq) {
      lines.push(`${num}. ${name} (${ticker}) — 품질 정보 없음`);
      return;
    }
    lines.push(`${num}. ${name} (${ticker})`);
    const drc = dq.daily_return_check;
    if (drc.status === "ok") {
      lines.push(
        `   - 일간 수익률: ${formatPct(drc.daily_return_pct ?? null)}${datesTail(drc.price_start_date, drc.price_end_date, "정상 · ")}`,
      );
    } else if (drc.status === "warning") {
      lines.push(
        `   - 일간 수익률: ${formatPct(drc.daily_return_pct ?? null)} — ${drc.flag ?? "확인 필요"}${datesTail(drc.price_start_date, drc.price_end_date)}`,
      );
    } else {
      lines.push("   - 일간 수익률: 데이터 부족");
    }
    const nd = dq.nav_discount;
    if (nd.status === "ok") {
      lines.push(
        `   - 괴리율: ${formatPct(nd.discount_rate_pct ?? null)} (source: ${nd.source ?? "-"})`,
      );
      if (nd.flag) {
        lines.push(`     · ${nd.flag}`);
      }
    } else {
      lines.push("   - 괴리율: source unavailable");
    }
  });
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
  lines.push("아래는 한국 상장 ETF Market Discovery 결과입니다.");
  lines.push("");
  lines.push("[데이터 기준]");
  lines.push(`- 시장 저장 최신일: ${asof} (저장된 전체 종목 가격 중 가장 늦은 저장일 — 후보별 수익률 계산 기간은 각 값 뒤 괄호)`);
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
        `   - 일간 수익률: ${formatPct(c.returns?.daily?.return_pct ?? null)}${periodTail(c.returns?.daily, true)}`,
      );
      lines.push(
        `   - 1개월 수익률: ${formatPct(c.returns?.one_month?.return_pct ?? null)}${periodTail(c.returns?.one_month)}`,
      );
      lines.push(
        `   - 3개월 수익률: ${formatPct(c.returns?.three_month?.return_pct ?? null)}${periodTail(c.returns?.three_month)}`,
      );
      lines.push(`   - 태그: ${formatTags(c.tags)}`);
    });
  }
  lines.push("");
  appendMarketContextSection(lines, input.marketContext);
  lines.push("");
  appendCandidateStrengthSection(lines, input.candidates, input.marketContext);
  // 2026-06-01 Market Discovery Evidence Closeout 1차 — 단기 흐름 + 데이터 품질
  // 섹션 (지시문 §15). candidates 에 응답 payload 가 들어있을 때만 노출.
  appendShortTermMomentumSection(lines, input.candidates);
  appendDataQualitySection(lines, input.candidates);
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
      "시스템의 시장 국면 판정, KODEX200 대비 수익률 차이(기간이 다르면 괄호에 두 기간),",
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
      "시스템의 시장 국면 판정, KODEX200 대비 수익률 차이(기간이 다르면 괄호에 두 기간),",
    );
    lines.push(
      "단기 흐름 (5/10/20거래일) 과 데이터 품질 체크 (일간 급등/급락 / 괴리율) 를 바탕으로",
    );
    lines.push(
      "이 후보들이 시장 전체 상승에 따라간 것인지, 같은 핵심 종목 반복 노출인지,",
    );
    lines.push(
      "최근 급등이 지속 흐름인지 단기 반응인지,",
    );
    lines.push(
      "데이터 품질상 확인이 필요한 후보가 있는지 해석해주세요.",
    );
    lines.push("");
    lines.push("매수/매도 추천은 하지 말고,");
    lines.push(
      "시스템 판정이 틀릴 수 있는 반대 근거와 추가 확인 포인트를 제시해주세요.",
    );
  }
  return lines.join("\n");
}
