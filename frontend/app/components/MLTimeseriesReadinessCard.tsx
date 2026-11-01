"use client";

// POC2 ML 최소 데이터 레인 (2026-06-08) — Readiness 카드 갱신.
//
// 이전 (2026-06-06): 정적 9축 표 (NAV/구성종목/거래량/시장지수/시장 폭/외국인·기관 수급/
//   변동성/Fear&Greed/CNN 등). 실제 적재 여부와 무관한 보수적 표기.
// 현재 (2026-06-08): GET /ml/readiness/latest 응답 기반 7축. 실제 etf_ml_feature_daily
//   / market_risk_feature_daily row 수 + latest asof 로 status 결정.
//
// 본 STEP 에서 표시하지 않는 (지시문 §6.6 '제외'):
//   - CNN Fear & Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장 폭 /
//     구성종목 가격 시계열. BACKLOG 후보로만 별도 관리.
//
// 2026-11-01 POC6-15(설계자 PLAN 판정 §3 · §4 · PLAN §8 · 사용자 확인 목업 3):
//   - 제목 '이전 학습용 값 — 쌓인 상태'. 순서 = 제목 → 결론 한 줄(항목 상태 요약 · 마지막 자료일 ·
//     건수) → 짧은 설명 → 항목 표 → 접힌 개발 정보. 버튼 없음.
//   - 화면 글자는 쉬운 한국어. 항목 이름 · 설명은 백엔드 고정 문장(app/api_ml_readiness.py)일 때만
//     쉬운 말로 바꾸고, 모르는 항목 · 문장 · 상태 값은 원래 값을 그대로 보인다.
//     표 이름 · 칼럼 이름 · 명령 · 응답 원문은 개발 정보 안으로.
//   - 'feature 생성은 CLI 로만' 문구는 지금 사실과 다름(「ML evidence 갱신」 작업 = app/ml_job_runner.py 가
//     같은 핵심 함수를 부름) → '다시 만들기는 「이전 자료와 실험 다시 만들기」에서'로 정정.
//   - 조회(마운트 때 GET 1회) · 응답 값 · 숫자는 그대로(건수에 쉼표만).

import { useEffect, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchMlReadinessLatest,
  type MlReadinessAxis,
  type MlReadinessResponse,
} from "@/lib/api";
import {
  CardConclusion,
  DevDetails,
  fmtCount,
  toneBadgeClass,
  type ConclusionTone,
} from "./MLCardParts";

// 불러오기 실패 — summary = 화면 결론 문장 · raw = 원문(개발 정보) · rawVisible = 모르는 실패라 원문도 본문에 보임.
type ErrorView = { summary: string; raw: string; rawVisible: boolean };

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; error: ErrorView }
  | { phase: "ready"; data: MlReadinessResponse };

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

// 항목 상태 값 → 쉬운 말. 모르는 값 = 원래 값 그대로(전과 같은 회색 배지).
// (백엔드 값 = available / partial / empty · 'missing' 도 '없음'으로 읽는다.)
type AxisKind = "have" | "part" | "none" | "unknown";
const AXIS_STATUS: Record<string, { kind: AxisKind; text: string; tone: ConclusionTone }> = {
  available: { kind: "have", text: "있음", tone: "ok" },
  partial: { kind: "part", text: "일부", tone: "warn" },
  empty: { kind: "none", text: "없음", tone: "muted" },
  missing: { kind: "none", text: "없음", tone: "muted" },
};

// 응답 문자열로 표를 찾을 때 'toString' · 'constructor' 같은 기본 속성 이름에 걸리지 않게 자기 키만 본다
// (걸리면 모르는 값이 원문 대신 빈칸으로 보임).
function own<T>(rec: Record<string, T>, key: string): T | undefined {
  return Object.prototype.hasOwnProperty.call(rec, key) ? rec[key] : undefined;
}

function axisStatus(status: string): { kind: AxisKind; text: string; tone: ConclusionTone } {
  return own(AXIS_STATUS, status) ?? { kind: "unknown", text: status, tone: "muted" };
}

// 백엔드 항목 이름(고정) → 쉬운 이름.
const AXIS_NAME: Record<string, string> = {
  "ETF 가격 시계열": "ETF 가격 흐름",
  "NAV / 괴리율 feature": "NAV · 괴리율",
  "거래량 / 유동성 feature": "거래량 · 유동성",
  "시장지수 feature": "시장지수",
  "ETF universe 시장 폭 feature": "ETF 시장 폭",
  "변동성 feature": "변동성",
  "조정장 전조 feature": "조정장 신호",
};

// 백엔드 설명(고정 문장) → 쉬운 말. 건수가 들어간 두 문장은 틀로 맞춘다(건수는 결론 줄 · 개발 정보에 있음).
const NOTE_EXACT: Record<string, string> = {
  "etf_ml_feature_daily.nav / nav_market_price / discount_rate_pct + nav_status 컬럼 — latest available ≤ asof 정책":
    "NAV, NAV 기준 시장가, 괴리율(그날 또는 그 전 최신 NAV만 씀)",
  "etf_ml_feature_daily.volume + volume_ratio_20d (20일 평균 대비)": "거래량, 20일 평균 대비 거래량",
  "etf_universe_up/down/flat_count + ratio + median_return_1d/5d":
    "오른 · 내린 · 보합 ETF 수와 비율, 1 · 5일 수익률 중앙값",
  "etf_ml_feature_daily.volatility_20d (일간 수익률 표준편차) + market_risk_feature_daily.volatility_20d_market_proxy / volatility_expansion_20d":
    "20일 일간 수익률 표준편차, 시장 변동성 대리값, 변동성 확대",
  "distance_from_20d_high + down_day_volume_ratio + large_negative_day_proxy + short_term_weakness_proxy + breadth_deterioration_proxy (proxy raw 값. label/threshold 미확정)":
    "20일 고점과의 거리, 하락일 거래량 비율, 큰 하락일, 단기 약세, 시장 폭 악화(기준 미정 · 원래 값)",
  "etf_ml_feature_daily 미적재": "ETF 값이 쌓여 있지 않음",
  "market_risk_feature_daily 미적재": "시장 값이 쌓여 있지 않음",
  미적재: "쌓여 있지 않음",
  "일부만 적재": "일부만 쌓여 있음",
};
const NOTE_PATTERN: Array<[RegExp, string]> = [
  [/^etf_ml_feature_daily \d+건 — return 5\/10\/20d \+ close\/volume 적재$/, "5 · 10 · 20일 수익률, 종가, 거래량"],
  [/^market_risk_feature_daily \d+건 — KODEX200 \/ KOSPI return 1\/5\/20d$/, "KODEX 200 · 코스피 1 · 5 · 20일 수익률"],
];

// 표 한 줄 — 아는 항목 이름일 때만 이름 · 설명을 쉬운 말로. 모르는 항목 = 이름 · 설명 원문 그대로.
function axisView(axis: MlReadinessAxis): { name: string; note: string } {
  const name = own(AXIS_NAME, axis.label);
  if (name === undefined) return { name: axis.label, note: axis.note };
  const exact = own(NOTE_EXACT, axis.note);
  if (exact !== undefined) return { name, note: exact };
  const pat = NOTE_PATTERN.find(([re]) => re.test(axis.note));
  return { name, note: pat ? pat[1] : axis.note };
}

// 결론 배지 — 응답의 항목 상태만 센다(새 판정 없음).
function axesSummary(axes: MlReadinessAxis[]): { tone: ConclusionTone; label: string } {
  const n = axes.length;
  if (n === 0) return { tone: "muted", label: "항목 정보 없음" };
  const c: Record<AxisKind, number> = { have: 0, part: 0, none: 0, unknown: 0 };
  for (const a of axes) c[axisStatus(a.status).kind] += 1;
  const { have, part, none, unknown } = c;
  if (have === n) return { tone: "ok", label: `${n}개 항목 모두 있음` };
  if (none === n) return { tone: "muted", label: `${n}개 항목 모두 없음` };
  if (part === n) return { tone: "warn", label: `${n}개 항목 모두 일부만 있음` };
  const parts = [
    have > 0 ? `있음 ${have}` : null,
    part > 0 ? `일부 ${part}` : null,
    none > 0 ? `없음 ${none}` : null,
    unknown > 0 ? `상태 확인 필요 ${unknown}` : null,
  ].filter((x): x is string => x !== null);
  return { tone: "warn", label: `${n}개 항목 중 ${parts.join(" · ")}` };
}

export default function MLTimeseriesReadinessCard() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchMlReadinessLatest()
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

  return (
    <div className="card">
      <h2>이전 학습용 값 — 쌓인 상태</h2>
      {state.phase === "loading" && <CardConclusion tone="muted" label="불러오는 중" />}
      {state.phase === "error" && (
        <CardConclusion tone="bad" label="불러오지 못함">
          {state.error.summary}
          {state.error.rawVisible && <> · 원문: {state.error.raw}</>}
        </CardConclusion>
      )}
      {state.phase === "ready" && <ReadyConclusion data={state.data} />}
      <p className="helper" style={{ marginBottom: 8 }}>
        이전 실험(위험 구간 나누기 · 하락 예측 아님)을 위해 만든 값입니다. 현재 예측 비교는 이 값을 쓰지
        않습니다. 다시 만들기는 아래 「이전 자료와 실험 다시 만들기」에서 합니다.
      </p>
      {state.phase === "ready" && <ReadinessTable axes={state.data.axes} />}
      <DevDetails>
        <div>표 이름: etf_ml_feature_daily · market_risk_feature_daily (SQLite)</div>
        <div>
          칼럼 예: return_5d/10d/20d · nav · nav_market_price · nav_discount_rate_pct · nav_status ·
          volume_ratio_20d · volatility_20d · distance_from_20d_high …
        </div>
        <div>
          만드는 명령: scripts/generate_ml_features.py (화면의 「이전 자료와 실험 다시 만들기」 = ML evidence
          갱신 작업 app/ml_job_runner.py 도 같은 핵심 함수를 부름)
        </div>
        <div>
          이 자료에 없는 것(원래 이름): CNN Fear &amp; Greed / VKOSPI / 외국인·기관 수급 / KOSPI 전체 시장
          폭 / 구성종목 가격 시계열 — BACKLOG 후보
        </div>
        <div>조회: GET /ml/readiness/latest</div>
        {state.phase === "error" && <div>오류 원문: {state.error.raw}</div>}
        {state.phase === "ready" && (
          <>
            <div>응답 상태 값: {String(state.data.status)}</div>
            <div>
              etf_feature_row_count={state.data.etf_feature_row_count} · etf_distinct_asof_count=
              {state.data.etf_distinct_asof_count} · etf_latest_asof={state.data.etf_latest_asof ?? "null"}
            </div>
            <div>
              market_risk_row_count={state.data.market_risk_row_count} · market_risk_latest_asof=
              {state.data.market_risk_latest_asof ?? "null"}
            </div>
            <div>항목 원문(feature 축 | 상태 값 | 설명):</div>
            {state.data.axes.map((axis) => (
              <div key={axis.label}>
                {axis.label} | {axis.status} | {axis.note}
              </div>
            ))}
          </>
        )}
      </DevDetails>
    </div>
  );
}

function ReadyConclusion({ data }: { data: MlReadinessResponse }) {
  const sum = axesSummary(data.axes);
  const respStatus: string = data.status;
  const odd = respStatus !== "ok";
  const etfAsof = data.etf_latest_asof ?? "-";
  const mktAsof = data.market_risk_latest_asof ?? "-";
  return (
    <CardConclusion tone={odd && sum.tone === "ok" ? "warn" : sum.tone} label={sum.label}>
      {etfAsof === mktAsof ? (
        <>
          마지막 자료일 <strong>{etfAsof}</strong>
        </>
      ) : (
        <>
          마지막 자료일 ETF 값 <strong>{etfAsof}</strong> · 시장 값 <strong>{mktAsof}</strong>
        </>
      )}{" "}
      · ETF 값 <strong>{fmtCount(data.etf_feature_row_count)}</strong>건 ·{" "}
      <strong>{fmtCount(data.etf_distinct_asof_count)}</strong>거래일 · 시장 값{" "}
      <strong>{fmtCount(data.market_risk_row_count)}</strong>건
      {odd && <> · 응답 상태 값 &lsquo;{respStatus}&rsquo; — 원인 확인 필요</>}
    </CardConclusion>
  );
}

function ReadinessTable({ axes }: { axes: MlReadinessAxis[] }) {
  return (
    <>
      <table className="market-topn-table">
        <thead>
          <tr>
            <th>항목</th>
            <th style={{ width: 140 }}>상태</th>
            <th>담긴 값</th>
          </tr>
        </thead>
        <tbody>
          {axes.map((axis) => {
            const s = axisStatus(axis.status);
            const v = axisView(axis);
            return (
              <tr key={axis.label}>
                <td>{v.name}</td>
                <td>
                  <span className={toneBadgeClass(s.tone)}>{s.text}</span>
                </td>
                <td style={{ color: "var(--muted)" }}>{v.note}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="helper" style={{ marginTop: 8, fontSize: "0.78rem" }}>
        이 자료에 없는 것: 공포 · 탐욕 지수, 코스피 변동성 지수, 외국인 · 기관 수급, 코스피 전체 시장 폭,
        구성종목 가격(나중 후보).
      </p>
    </>
  );
}
