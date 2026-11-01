"use client";

// POC2 ML Baseline v0 룩백 검증 카드 (2026-06-11) — DataStatusView 하단 표시.
//
// 책임 (지시문 §12):
// - GET /ml/baseline-v0/latest 1회 조회 (외부 source 호출 X / 재계산 X).
// - 후보 발굴 baseline / 위험 패턴 baseline 의 룩백 검증 결과 요약.
// - 지시문 §12 금지 문구 (매수 후보 / 매도 후보 / 현금비중 확대 / 조정장 확정 /
//   위험 알림) 화면 표시 0건.
//
// 2026-11-01 POC6-15(설계자 PLAN 판정 §3 · §4 · PLAN §8 · 사용자 확인 목업 3):
//   - 제목 'Baseline 실험(v0) — 과거 자료로 되돌아본 검증'. 순서 = 제목 → 결론 한 줄(계산 상태 · 자료 기간 ·
//     평가 거래일 · 종목 수) → 경고 · 오류 → 짧은 설명 → 후보 고르기 · 위험 구간 표 → 접힌 '단순 기준과
//     비교 보기' → 접힌 개발 정보. 버튼 없음.
//   - 보고 ok 배지 = '보고 있음'(2026-11-02 RESULT 판정 §3 · 보고가 있다는 뜻 · 모든 점검 정상 · 추천 가능이 아님 · 설명에 적음). 'CLI 로만' 문구는 지금 사실과 다름
//     (「ML evidence 갱신」 작업 = app/ml_job_runner.py 가 같은 build_baseline_report 를 부르고 같은 파일에 씀)
//     → '다시 계산은 「이전 자료와 실험 다시 만들기」에서'로 정정.
//   - '이후 시장 drawdown' = KODEX 200 종가의 기준일(종가 포함)부터 n거래일 뒤까지 고점 대비 최대 하락
//     (app/ml_baseline_targets.py _kodex_future_drawdown · peak 시작 = 기준일 종가) → '이후 KODEX 200 고점 대비
//     최대 하락폭'. 20거래일 내 종가 하락폭(D20)과 다른 값.
//   - 보고 만든 시각(generated_at)은 본문 아래에도 보인다(판정 §2 '각 카드에 실행일' · 자료 점검 카드와 같은 자리).
//   - 백엔드 고정 경고 · 오류 문장만 쉬운 말로 바꾸고, 모르는 문장 · 상태 값은 원래 값을 본문에 그대로 보인다.
//     지표 원래 이름 · 누수 · 범위 검사 원문 · 경고 원문 · 명령 · 파일 경로는 개발 정보 안으로.
//   - 조회(마운트 때 GET 1회) · 응답 값 · 숫자 형식은 그대로(건수에 쉼표만).

import { useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchMlBaselineV0Latest,
  type MlBaselineV0Report,
  type MlBaselineV0Response,
} from "@/lib/api";
import { CardConclusion, DevDetails, fmtCount, kstText, type ConclusionTone } from "./MLCardParts";

// 불러오기 실패 — summary = 화면 결론 문장 · raw = 원문(개발 정보) · rawVisible = 모르는 실패라 원문도 본문에 보임.
type ErrorView = { summary: string; raw: string; rawVisible: boolean };

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; error: ErrorView }
  | { phase: "ready"; data: MlBaselineV0Response };

const DASH = "-";
const NUM = { textAlign: "right" as const };

function describeError(e: unknown): ErrorView {
  const raw = e instanceof Error ? e.message : String(e);
  if (e instanceof ApiConfigError) {
    return { summary: "화면 설정 오류 — 서버 주소 설정이 없습니다", raw: `구성 오류: ${raw}`, rawVisible: false };
  }
  if (e instanceof ApiRequestError) {
    const full = `요청 실패(HTTP ${e.httpStatus}): ${raw}`;
    if (e.httpStatus > 0) {
      return { summary: `서버가 오류로 응답했습니다(HTTP ${e.httpStatus})`, raw: full, rawVisible: false };
    }
    if (raw.startsWith("요청 시간 초과")) {
      return { summary: "서버 응답 시간이 지났습니다", raw: full, rawVisible: false };
    }
    if (raw.startsWith("네트워크 호출 실패")) {
      return { summary: "서버에 연결하지 못했습니다", raw: full, rawVisible: false };
    }
    return { summary: "요청 실패 — 원인 확인 필요", raw: full, rawVisible: true };
  }
  return { summary: "알 수 없는 오류 — 원인 확인 필요", raw: `알 수 없는 오류: ${raw}`, rawVisible: true };
}

// 보고 상태 값(app/ml_baseline_v0.py _aggregate_status = ok / warn / insufficient_history / error) → 쉬운 말.
// 모르는 값 = 원래 값 그대로(회색 배지).
function reportStatusView(status: unknown): { tone: ConclusionTone; label: string; known: boolean } {
  switch (status) {
    case "ok":
      return { tone: "ok", label: "보고 있음", known: true };
    case "warn":
      return { tone: "warn", label: "주의", known: true };
    case "insufficient_history":
      return { tone: "warn", label: "과거 자료 부족", known: true };
    case "error":
      return { tone: "bad", label: "계산 오류", known: true };
    default: {
      const raw = String(status);
      return { tone: "muted", label: raw === "" ? "(빈 상태 값)" : raw, known: false };
    }
  }
}

// 응답 메시지 — 백엔드 고정 문장(app/api_ml_baseline.py)으로 시작하면 쉬운 말 요약만 본문에, 원문은 개발 정보.
const CORRUPT_PREFIX = "baseline report 파일이 손상되어 읽을 수 없습니다";
const EMPTY_PREFIX = "ML baseline v0 룩백 report 미생성.";

function isKnownMessage(msg: string | null | undefined, prefix: string): boolean {
  return !msg || msg.startsWith(prefix);
}

// 경고 · 오류 — 백엔드가 같은 틀로 만드는 문장(app/ml_baseline_v0.py · ml_baseline_candidate.py ·
// ml_baseline_risk.py · ml_baseline_targets.py)만 쉬운 말로. 틀에 안 맞으면 null(호출하는 쪽이 원문을 보인다).
const NOTICE_EXACT = new Map<string, string>([
  [
    "etf_ml_feature_daily 가 비어있음 — feature 생성 CLI 먼저 실행 필요",
    "ETF 학습용 값이 비어 있습니다 — 학습용 값을 먼저 만들어야 합니다",
  ],
  [
    "market_risk_feature_daily 가 비어있음 — feature 생성 CLI 먼저 실행 필요",
    "시장 위험 값이 비어 있습니다 — 학습용 값을 먼저 만들어야 합니다",
  ],
  ["market_risk_feature_daily 가 비어있음", "시장 위험 값이 비어 있습니다"],
  [
    "평가 가능한 asof 0건 — feature 분포 / target join 확인 필요",
    "후보 고르기 기준: 평가할 수 있는 날이 0일입니다 — 학습용 값과 이후 수익률 자료 확인 필요",
  ],
  [
    "rank correlation 산출 불가 (target join 부족)",
    "후보 고르기 기준: 점수 순위와 이후 수익률의 순위 상관을 계산하지 못했습니다(이후 수익률 자료 부족)",
  ],
]);
const NOTICE_PATTERN: Array<[RegExp, (m: RegExpMatchArray) => string]> = [
  [
    /^candidate target 의 asof 수\((\d+)\)가 MAX_HORIZON\((\d+)\) 이하 — 평가 가능 거래일 0$/,
    (m) => `후보 고르기 기준: 자료가 ${m[1]}거래일로 ${m[2]}거래일 이하라 평가할 수 있는 날이 없습니다`,
  ],
  [
    /^risk target 의 asof 수\((\d+)\)가 MAX_HORIZON\((\d+)\) 이하 — 평가 가능 거래일 0$/,
    (m) => `위험 구간 기준: 자료가 ${m[1]}거래일로 ${m[2]}거래일 이하라 평가할 수 있는 날이 없습니다`,
  ],
  [
    /^composite_score 산출 가능 asof 가 (\d+)건 — tercile 분할 어려움$/,
    (m) => `위험 구간 기준: 위험 점수를 계산할 수 있는 날이 ${m[1]}일이라 1/3씩 나누기 어렵습니다`,
  ],
  [
    /^kodex200\((.+)\) close 시계열이 etf_ml_feature_daily 에 없음$/,
    (m) => `KODEX 200(${m[1]}) 종가 자료가 ETF 학습용 값에 없습니다`,
  ],
];

function plainNotice(raw: string): string | null {
  const exact = NOTICE_EXACT.get(raw);
  if (exact !== undefined) return exact;
  for (const [re, fn] of NOTICE_PATTERN) {
    const m = raw.match(re);
    if (m) return fn(m);
  }
  return null;
}

function fmtPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  const pct = value * 100;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(2)}%`;
}

function fmtFloat(value: number | null | undefined, digits = 3): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  return value.toFixed(digits);
}

// 상위 묶음 비율(top_group_quantile 0.2 → "20") — 기존 표시와 같은 toFixed(0).
function topPctText(q: number | null | undefined): string {
  if (q == null || !Number.isFinite(q)) return DASH;
  return (q * 100).toFixed(0);
}

function devValue(v: unknown): string {
  if (typeof v === "number") return fmtCount(v);
  if (v !== null && typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export default function MLBaselineV0Card() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchMlBaselineV0Latest()
      .then((data) => {
        if (!cancelled) setState({ phase: "ready", data });
      })
      .catch((e) => {
        if (!cancelled) setState({ phase: "error", error: describeError(e) });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const data = state.phase === "ready" ? state.data : null;
  // 기존 분기 그대로: error → 손상 · (empty 또는 report 없음) → 보고 없음 · 그 밖 = 보고 본문.
  const rpt =
    data && data.status !== "error" && data.status !== "empty" && data.report ? data.report : null;

  return (
    <div className="card">
      <h2>Baseline 실험(v0) — 과거 자료로 되돌아본 검증</h2>
      {state.phase === "loading" && <CardConclusion tone="muted" label="불러오는 중" />}
      {state.phase === "error" && (
        <CardConclusion tone="bad" label="불러오지 못함">
          {state.error.summary}
          {state.error.rawVisible && <> · 원문: {state.error.raw}</>}
        </CardConclusion>
      )}
      {data && <ResponseConclusion data={data} />}
      {data && rpt && <ReportNotices data={data} rpt={rpt} />}
      <p className="helper" style={{ marginBottom: 8 }}>
        이전 학습용 값으로 과거 구간을 되돌아보며 (1) 후보 고르기 기준과 (2) 위험 구간 기준이 의미가
        있었는지 확인한 결과입니다. ‘보고 있음’은 보고가 만들어졌다는 뜻이며 모든 점검이 정상이라거나 추천에 쓸 수
        있다는 뜻은 아닙니다. 점검 결과는 아래 경고·오류를 확인하세요. 다시 계산은 위 「이전 자료와 실험 다시 만들기」에서
        합니다.
      </p>
      {rpt && <ReportTables rpt={rpt} />}
      <DevDetails>
        <div>조회: GET /ml/baseline-v0/latest</div>
        <div>
          만드는 명령: python scripts/run_ml_baseline_v0.py (화면의 「이전 자료와 실험 다시 만들기」 = ML
          evidence 갱신 작업 app/ml_job_runner.py 도 같은 핵심 함수 build_baseline_report 를 부르고 같은
          파일에 씀)
        </div>
        {state.phase === "error" && <div>오류 원문: {state.error.raw}</div>}
        {data && (
          <>
            <div>
              응답 상태 값: {String(data.status)} · 보고 파일: {data.report_path}
            </div>
            {data.message ? <div>응답 메시지 원문: {data.message}</div> : null}
          </>
        )}
        {rpt && <ReportDevInfo rpt={rpt} />}
      </DevDetails>
    </div>
  );
}

function ResponseConclusion({ data }: { data: MlBaselineV0Response }) {
  if (data.status === "error") {
    const known = isKnownMessage(data.message, CORRUPT_PREFIX);
    return (
      <CardConclusion tone="bad" label="보고 파일 손상">
        저장된 Baseline 실험 보고 파일이 손상되어 읽을 수 없습니다
        {!known && <> · 원문: {data.message} · 원인 확인 필요</>}
      </CardConclusion>
    );
  }
  if (data.status === "empty") {
    const known = isKnownMessage(data.message, EMPTY_PREFIX);
    return (
      <CardConclusion tone="muted" label="보고 없음">
        Baseline 실험 보고가 아직 만들어지지 않았습니다 · 위 「이전 자료와 실험 다시 만들기」에서 만들 수
        있습니다
        {!known && <> · 원문: {data.message}</>}
      </CardConclusion>
    );
  }
  if (!data.report) {
    return (
      <CardConclusion tone="warn" label="보고 내용 없음">
        응답 상태 값 ‘{String(data.status)}’인데 보고 내용이 비어 있습니다 · 원인 확인 필요
        {data.message ? <> · 원문: {data.message}</> : null}
      </CardConclusion>
    );
  }
  return <ReportConclusion rpt={data.report} />;
}

function ReportConclusion({ rpt }: { rpt: MlBaselineV0Report }) {
  const s = reportStatusView(rpt.status);
  const fr = rpt.feature_asof_range;
  const nW = rpt.warnings?.length ?? 0;
  const nE = rpt.errors?.length ?? 0;
  return (
    <CardConclusion tone={s.tone} label={s.label}>
      자료 기간{" "}
      <strong>
        {fr.start ?? DASH} ~ {fr.end ?? DASH}
      </strong>
      ({fmtCount(fr.trading_days)}거래일) · 평가 <strong>{fmtCount(rpt.evaluated_asof_range.evaluated_days)}</strong>
      거래일 · {fmtCount(rpt.candidate_baseline.evaluated_ticker_count)}종목
      {nW > 0 && <> · 경고 {nW}건</>}
      {nE > 0 && <> · 오류 {nE}건</>}
      {!s.known && <> · 처음 보는 상태 값 — 확인 필요</>}
    </CardConclusion>
  );
}

// 결론 바로 아래 — 경고 · 오류 · 누수 검사 이상 · 처음 보는 응답 상태. 접힌 개발 정보에만 숨기지 않는다.
function ReportNotices({ data, rpt }: { data: MlBaselineV0Response; rpt: MlBaselineV0Report }) {
  const leak = rpt.leakage_checks;
  const leakLines: string[] = [];
  if (leak.feature_future_data_leakage_detected === true) {
    leakLines.push("미래 자료 섞임 의심 — 기준일 뒤의 자료가 계산에 들어갔을 수 있습니다 · 원인 확인 필요");
  }
  if (leak.target_horizon_short_tail_excluded === false) {
    // app/ml_baseline_targets.py evaluate_leakage — 마지막 구간 행에 future 값이 있으면 false.
    leakLines.push("결과 기간이 모자란 마지막 거래일에 이후 결과 값이 들어 있습니다(비어 있어야 함) · 원인 확인 필요");
  }
  if (leak.time_order_preserved === false) {
    leakLines.push("날짜 순서가 어긋난 자료가 있습니다 · 원인 확인 필요");
  }
  // 참 · 거짓이 아닌 값 = 통과로 치지 않고 원래 값을 보인다.
  const leakFlags: Array<[string, unknown]> = [
    ["미래 자료 섞임 검사", leak.feature_future_data_leakage_detected],
    ["마지막 구간 제외 검사", leak.target_horizon_short_tail_excluded],
    ["날짜 순서 검사", leak.time_order_preserved],
  ];
  for (const [name, v] of leakFlags) {
    if (typeof v !== "boolean") {
      leakLines.push(`${name} 값 ‘${String(v)}’ — 처음 보는 값입니다 · 원인 확인 필요`);
    }
  }
  const warnings = rpt.warnings ?? [];
  const errors = rpt.errors ?? [];
  const oddResp = data.status !== "ok";
  if (!oddResp && leakLines.length === 0 && warnings.length === 0 && errors.length === 0) return null;
  return (
    <>
      {oddResp && (
        <div className="message info">
          응답 상태 값 ‘{String(data.status)}’ — 처음 보는 값입니다 · 확인 필요
        </div>
      )}
      {(errors.length > 0 || leakLines.length > 0) && (
        <div className="message error" data-role="report-errors">
          {errors.length > 0 && (
            <>
              <strong>오류 {errors.length}건</strong>
              {errors.length > 30 && <> (앞 30건만 표시)</>}
              <ul style={{ margin: "4px 0 0" }}>
                {errors.slice(0, 30).map((t, i) => {
                  const p = plainNotice(t);
                  return <li key={i}>{p ?? <>{t} — 처음 보는 문장 · 원인 확인 필요</>}</li>;
                })}
              </ul>
            </>
          )}
          {leakLines.length > 0 && (
            <>
              <strong>누수 검사</strong>
              <ul style={{ margin: "4px 0 0" }}>
                {leakLines.map((t) => (
                  <li key={t}>{t}</li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="message info" data-role="report-warnings">
          <strong>경고 {warnings.length}건</strong>
          {warnings.length > 30 && <> (앞 30건만 표시)</>}
          <ul style={{ margin: "4px 0 0" }}>
            {warnings.slice(0, 30).map((t, i) => {
              const p = plainNotice(t);
              return <li key={i}>{p ?? <>{t} — 처음 보는 문장 · 확인 필요</>}</li>;
            })}
          </ul>
        </div>
      )}
    </>
  );
}

function PctRow({
  label,
  rec,
  keys,
  fmt,
}: {
  label: string;
  rec: Record<string, number | null> | undefined;
  keys: string[];
  fmt: (v: number | null | undefined) => string;
}) {
  return (
    <tr>
      <td>{label}</td>
      {keys.map((k) => (
        <td key={k} style={NUM}>
          {fmt(rec?.[k])}
        </td>
      ))}
    </tr>
  );
}

const CAND_KEYS = ["5d", "10d", "20d"];

// 단순 위험 기준 3가지(app/ml_baseline_risk.py SIMPLE_RISK_BASELINE_AXES) — 모두 기준일까지의 값.
const SIMPLE_RISK_AXES: Array<[string, string]> = [
  ["kodex200_return_5d", "지난 5일 KODEX 200 수익률(작을수록 위험)"],
  ["drawdown_20d_market_proxy", "지난 20일 고점 대비 KODEX 200 하락폭(작을수록 위험)"],
  ["etf_universe_down_ratio", "시장 폭 악화(그날 내린 ETF 비율이 클수록 위험)"],
];

function ReportTables({ rpt }: { rpt: MlBaselineV0Report }) {
  const cand = rpt.candidate_baseline;
  const risk = rpt.risk_baseline;
  const p = topPctText(cand.top_group_quantile);
  const simple = cand.simple_baselines;
  const kst = kstText(rpt.generated_at);
  return (
    <>
      <h3 style={{ marginTop: 12 }}>후보 고르기 기준</h3>
      <div style={{ overflowX: "auto" }}>
        <table className="market-topn-table" data-role="candidate-table">
          <thead>
            <tr>
              <th>지표</th>
              <th style={NUM}>5일</th>
              <th style={NUM}>10일</th>
              <th style={NUM}>20일</th>
            </tr>
          </thead>
          <tbody>
            <PctRow
              label={`종합 점수 상위 ${p}% — 이후 평균 수익률`}
              rec={cand.top_group_avg_future_return}
              keys={CAND_KEYS}
              fmt={fmtPct}
            />
            <PctRow
              label={`종합 점수 상위 ${p}% — KODEX 200 대비 평균 초과 수익`}
              rec={cand.top_group_avg_future_excess_return}
              keys={CAND_KEYS}
              fmt={fmtPct}
            />
            <PctRow
              label="전체 ETF — 이후 수익률 중앙값"
              rec={cand.universe_median_future_return}
              keys={CAND_KEYS}
              fmt={fmtPct}
            />
            <PctRow
              label={`종합 점수 상위 ${p}% 중 KODEX 200보다 나은 비율`}
              rec={cand.hit_rate}
              keys={CAND_KEYS}
              fmt={(v) => fmtFloat(v)}
            />
            <PctRow
              label="점수 순위와 이후 수익률의 순위 상관"
              rec={cand.rank_correlation}
              keys={CAND_KEYS}
              fmt={(v) => fmtFloat(v)}
            />
            <PctRow
              label={`단순 기준: 지난 20일 수익률 상위 ${p}% — 이후 평균 수익률`}
              rec={simple?.["simple_return_20d_top_quintile_avg_future_return"]}
              keys={CAND_KEYS}
              fmt={fmtPct}
            />
            <PctRow
              label={`단순 기준: 지난 20일 KODEX 200 대비 초과 수익 상위 ${p}% — 이후 평균 수익률`}
              rec={simple?.["simple_excess_20d_vs_kodex200_top_quintile_avg_future_return"]}
              keys={CAND_KEYS}
              fmt={fmtPct}
            />
          </tbody>
        </table>
      </div>
      <p className="helper" style={{ marginTop: 4 }}>
        종합 점수 상위 {p}% 묶음(사용자 결정) · 단순 기준 2가지 = 지난 20일 수익률 · 지난 20일 초과 수익
        상위 {p}% · 평가 {fmtCount(cand.evaluated_days)}거래일 · {fmtCount(cand.evaluated_ticker_count)}
        종목.
      </p>

      <h3 style={{ marginTop: 16 }}>위험 구간 기준</h3>
      <div style={{ overflowX: "auto" }}>
        <table className="market-topn-table" data-role="risk-table">
          <thead>
            <tr>
              <th>구간</th>
              <th style={NUM}>이후 KODEX 200 수익률 3일</th>
              <th style={NUM}>5일</th>
              <th style={NUM}>10일</th>
              <th style={NUM}>이후 KODEX 200 고점 대비 최대 하락폭 5일</th>
              <th style={NUM}>10일</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>위험 점수 상위 1/3</td>
              <td style={NUM}>{fmtPct(risk.high_risk_group_future_return?.["3d"])}</td>
              <td style={NUM}>{fmtPct(risk.high_risk_group_future_return?.["5d"])}</td>
              <td style={NUM}>{fmtPct(risk.high_risk_group_future_return?.["10d"])}</td>
              <td style={NUM}>{fmtPct(risk.high_risk_group_future_drawdown?.["5d"])}</td>
              <td style={NUM}>{fmtPct(risk.high_risk_group_future_drawdown?.["10d"])}</td>
            </tr>
            <tr>
              <td>위험 점수 하위 1/3</td>
              <td style={NUM}>{fmtPct(risk.low_risk_group_future_return?.["3d"])}</td>
              <td style={NUM}>{fmtPct(risk.low_risk_group_future_return?.["5d"])}</td>
              <td style={NUM}>{fmtPct(risk.low_risk_group_future_return?.["10d"])}</td>
              <td style={NUM}>{fmtPct(risk.low_risk_group_future_drawdown?.["5d"])}</td>
              <td style={NUM}>{fmtPct(risk.low_risk_group_future_drawdown?.["10d"])}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="helper" style={{ marginTop: 4 }}>
        위험 점수 상위 1/3 묶음의 이후 KODEX 200 하락폭이 하위 1/3보다 컸는지 확인합니다 · 최대 하락폭 =
        기준일 종가부터 그 기간 끝까지 KODEX 200 종가의 고점 대비 가장 큰 하락(20거래일 내 종가 하락폭과 다른
        값) · 평가{" "}
        {fmtCount(risk.evaluated_days)}거래일 · 이후 5일 동안 내린 ETF 비율(하루 평균): 상위{" "}
        {fmtFloat(risk.high_risk_group_future_down_ratio_5d)} · 하위{" "}
        {fmtFloat(risk.low_risk_group_future_down_ratio_5d)}.
      </p>

      <details style={{ marginTop: 12 }} data-role="simple-compare">
        <summary>단순 기준과 비교 보기</summary>
        <div style={{ overflowX: "auto" }}>
          <table className="market-topn-table">
            <thead>
              <tr>
                <th>단순 기준(상위 1/3 = 위험 묶음)</th>
                <th style={NUM}>위험 묶음 이후 10일 최대 하락폭</th>
                <th style={NUM}>안전 묶음 10일</th>
                <th style={NUM}>위험 묶음 이후 KODEX 200 수익률 5일</th>
                <th style={NUM}>안전 묶음 5일</th>
              </tr>
            </thead>
            <tbody>
              {SIMPLE_RISK_AXES.map(([axis, label]) => {
                const row = risk.simple_baselines?.[axis] as Record<string, number | null> | undefined;
                return (
                  <tr key={axis}>
                    <td>{label}</td>
                    <td style={NUM}>{fmtPct(row?.["high_risk_future_market_drawdown_10d"])}</td>
                    <td style={NUM}>{fmtPct(row?.["low_risk_future_market_drawdown_10d"])}</td>
                    <td style={NUM}>{fmtPct(row?.["high_risk_future_kodex200_return_5d"])}</td>
                    <td style={NUM}>{fmtPct(row?.["low_risk_future_kodex200_return_5d"])}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="helper" style={{ marginTop: 4 }}>
          종합 위험 점수와 따로, 기준 하나씩만으로 나눈 비교입니다 · 위험 묶음 = 그 기준에서 위험 쪽 1/3 ·
          안전 묶음 = 반대쪽 1/3(위험이 낮은 쪽이라는 뜻이며 손실이 없다는 뜻은 아님) · 최대 하락폭 = 이후
          KODEX 200 고점 대비 최대 하락폭(위 표와 같은 계산).
        </p>
      </details>

      <p className="helper" style={{ marginTop: 8 }} data-role="generated-at">
        보고 만든 시각 {kst ? `${kst}(한국 시각)` : String(rpt.generated_at ?? DASH)}
      </p>
    </>
  );
}

// 접힌 개발 정보 — 지표 원래 이름 · 누수 · 범위 검사 원문 · 경고 · 오류 원문.
function ReportDevInfo({ rpt }: { rpt: MlBaselineV0Report }) {
  const cand = rpt.candidate_baseline;
  const risk = rpt.risk_baseline;
  const leak = rpt.leakage_checks;
  const ev = rpt.evaluated_asof_range;
  const kst = kstText(rpt.generated_at);
  const warnings = rpt.warnings ?? [];
  const errors = rpt.errors ?? [];
  return (
    <>
      <div>
        보고 상태 값: {String(rpt.status)} · 보고 만든 시각: {String(rpt.generated_at)}
        {kst ? ` (한국 시각 ${kst})` : ""}
      </div>
      <div>
        평가 기간 원문(evaluated_asof_range): {ev.start ?? "null"} ~ {ev.end ?? "null"} · evaluated_days=
        {devValue(ev.evaluated_days)}
      </div>
      <div>
        종합 점수 = composite rank v0 · 상위 묶음 = top group(top_group_quantile={devValue(cand.top_group_quantile)}
        · top quintile) · 위험 점수 상위 · 하위 1/3 = composite tercile · 단순 기준 = simple baseline
      </div>
      <div>
        후보 지표 원래 이름: top group 평균 future return · top group 평균 future excess (vs KODEX200) ·
        universe median future return · {"hit rate (excess > 0)"} · rank correlation ·
        simple_return_20d_top_quintile_avg_future_return ·
        simple_excess_20d_vs_kodex200_top_quintile_avg_future_return
      </div>
      <div>
        위험 지표 원래 이름: high-risk group (상위 1/3 composite) · low-risk group (하위 1/3) · future
        KODEX200 return 3d/5d/10d · future market drawdown 5d/10d (_kodex_future_drawdown — 고점 대비 최대
        하락 · D20 과 다름) · universe down ratio 5d
      </div>
      <div>
        단순 위험 기준 원래 이름: {SIMPLE_RISK_AXES.map(([axis]) => axis).join(" · ")} — high/low_risk_future_market_drawdown_10d
        · high/low_risk_future_kodex200_return_5d · evaluated_asof_count=
        {SIMPLE_RISK_AXES.map(([axis]) => devValue(risk.simple_baselines?.[axis]?.["evaluated_asof_count"])).join(
          " / ",
        )}
      </div>
      <div>
        누수(leakage) 검사: future data leakage detected={String(leak.feature_future_data_leakage_detected)} ·
        horizon tail excluded={String(leak.target_horizon_short_tail_excluded)} · time order preserved=
        {String(leak.time_order_preserved)} · candidate tail asof count={devValue(leak.candidate_tail_asof_count)} ·
        risk tail asof count={devValue(leak.risk_tail_asof_count)}
      </div>
      {(leak.details?.length ?? 0) > 0 && (
        <div>
          누수 검사 세부 원문:
          <ul style={{ margin: "2px 0" }}>
            {leak.details.slice(0, 30).map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </div>
      )}
      <div>
        범위(coverage) 검사:{" "}
        {Object.entries(rpt.coverage_checks ?? {})
          .map(([k, v]) => `${k}=${devValue(v)}`)
          .join(" · ")}
      </div>
      {warnings.length > 0 && (
        <div>
          warnings 원문 ({warnings.length}):
          <ul style={{ margin: "2px 0" }}>
            {warnings.slice(0, 30).map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}
      {errors.length > 0 && (
        <div>
          errors 원문 ({errors.length}):
          <ul style={{ margin: "2px 0" }}>
            {errors.slice(0, 30).map((e, i) => (
              <li key={i}>{e}</li>
            ))}
          </ul>
        </div>
      )}
    </>
  );
}
