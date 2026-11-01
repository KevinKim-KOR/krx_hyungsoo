"use client";

// POC2 ML Feature Sanity Check (2026-06-08) — ML 화면의 sanity 요약 카드.
//
// 책임 (지시문 §4.7):
// - GET /ml/feature-sanity/latest 1회 조회 (외부 source 호출 X / 재계산 X).
// - sanity_status / latest asof / checked ticker / warning/error 수 요약.
// - 샘플 ETF 5~10건의 return/excess/volatility/drawdown/NAV 괴리율 표시.
// - 본 카드는 데이터 품질 표시 영역. 매수·매도 / 위험 threshold / 조정장 판정 0건.
//
// 2026-11-01 POC6-15(설계자 PLAN 판정 §3 · §4 · PLAN §8): 제목 「이전 자료 점검」.
//   순서 = 제목 → 현재 결론 한 줄 → 설명 → 점검 표 · 오류 · 경고 · 견본 표 → 접힌 개발 정보.
//   화면 글자는 쉬운 한국어. 백엔드가 같은 틀로 만드는 경고 · 오류 문장은 쉬운 말로 요약하고
//   (틀에 안 맞으면 원문 그대로 · 오류는 '원인 확인 필요'), 원문 · 파일 경로 · 필드 이름 · 명령은
//   '자세한 정보(개발 정보)' 안. 조회(마운트 때 GET 1회) · 값 · 숫자 서식은 그대로(건수는 쉼표만).
//   옛 'CLI 로만 갱신' 문구는 사실과 달라(「이전 자료와 실험 다시 만들기」도 같은 핵심 함수를 부름) 고침.

import { useEffect, useState, type ReactNode } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchMlFeatureSanityLatest,
  type MlFeatureSanityResponse,
  type MlSanitySampleRow,
  type MlSanitySubChecks,
} from "@/lib/api";
import {
  CardConclusion,
  DevDetails,
  fmtCount,
  kstText,
  toneBadgeClass,
  type ConclusionTone,
} from "./MLCardParts";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; message: string; summary: string; rawVisible: boolean }
  | { phase: "ready"; data: MlFeatureSanityResponse };

const DASH = "-";
const LIST_CAP = 50;

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

// 불러오기 실패의 쉬운 말 요약 = 결론 문장(원문 = describeError → 개발 정보).
// 시간 초과 · 연결 실패는 lib/api/core.ts 가 같은 HTTP 0 으로 던지므로 원문 앞머리로 나눈다.
// 모르는 실패(rawVisible) = '원인 확인 필요' + 원문을 결론에도 보인다.
function plainError(e: unknown): { summary: string; rawVisible: boolean } {
  if (e instanceof ApiConfigError) {
    return { summary: "화면 설정 오류로 점검 결과를 불러오지 못했습니다.", rawVisible: false };
  }
  if (e instanceof ApiRequestError) {
    if (e.httpStatus > 0) {
      return {
        summary: `서버가 오류로 답해 점검 결과를 불러오지 못했습니다(HTTP ${e.httpStatus}).`,
        rawVisible: false,
      };
    }
    if (e.message.startsWith("요청 시간 초과")) {
      return { summary: "서버 응답 시간이 지나 점검 결과를 불러오지 못했습니다.", rawVisible: false };
    }
    if (e.message.startsWith("네트워크 호출 실패")) {
      return { summary: "서버에 연결하지 못해 점검 결과를 불러오지 못했습니다.", rawVisible: false };
    }
    return { summary: "요청이 실패해 점검 결과를 불러오지 못했습니다 · 원인 확인 필요.", rawVisible: true };
  }
  return { summary: "알 수 없는 오류로 점검 결과를 불러오지 못했습니다 · 원인 확인 필요.", rawVisible: true };
}

// 점검 상태 → 배지. 모르는 값은 원문 그대로(회색).
function statusView(status: unknown): { tone: ConclusionTone; label: string } {
  if (status === "ok") return { tone: "ok", label: "정상" };
  if (status === "warn") return { tone: "warn", label: "주의" };
  if (status === "error") return { tone: "bad", label: "오류" };
  return { tone: "muted", label: String(status ?? DASH) };
}

function StatusBadge({ status }: { status: unknown }) {
  const v = statusView(status);
  return <span className={toneBadgeClass(v.tone)}>{v.label}</span>;
}

function fmtPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

function fmtNum(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  return value.toFixed(4);
}

// 건수 칸 — 숫자면 쉼표만, 아니면 원래 값.
function countText(v: unknown): string {
  return typeof v === "number" ? fmtCount(v) : String(v ?? DASH);
}

// 비율(0~1) 원문 → '%' — 소수점 자리를 문자로 옮겨 자릿수를 잃지 않는다(0.958675 → 95.8675%).
// 지수 표기 등 틀에 안 맞는 값은 원래 값 그대로.
function ratioPct(raw: string): string {
  const m = /^(-?)(\d+)(?:\.(\d+))?$/.exec(raw);
  if (!m) return raw;
  const frac = (m[3] ?? "").padEnd(2, "0");
  const head = `${m[2]}${frac.slice(0, 2)}`.replace(/^0+(?=\d)/, "");
  const tail = frac.slice(2);
  return `${m[1]}${head}${tail ? `.${tail}` : ""}%`;
}

function ratioText(v: unknown): string {
  if (typeof v === "number" && Number.isFinite(v)) return ratioPct(String(v));
  return String(v ?? DASH);
}

const FIELD_KO: Record<string, string> = {
  return_5d: "5일 수익률",
  return_10d: "10일 수익률",
  return_20d: "20일 수익률",
  excess_return_5d_vs_kodex200: "KODEX 200 대비 5일",
  excess_return_10d_vs_kodex200: "KODEX 200 대비 10일",
  excess_return_20d_vs_kodex200: "KODEX 200 대비 20일",
  volatility_20d: "20일 변동성",
  drawdown_20d: "20일 고점 대비",
  volume_ratio_20d: "20일 평균 대비 거래량",
  distance_from_20d_high: "20일 고점과의 거리",
  drawdown_20d_market_proxy: "KODEX 200 20일 고점 대비",
  volatility_expansion_20d: "변동성 확대",
  down_day_volume_ratio: "하락일 거래량 비율",
  large_negative_day_proxy: "큰 하락일 신호",
  short_term_weakness_proxy: "단기 약세 신호",
  breadth_deterioration_proxy: "시장 폭 악화 신호",
};

const fieldKo = (f: string) => FIELD_KO[f] ?? f;
const pyVal = (v: string) => (v === "None" ? "없음" : v);

// 백엔드(app/ml_feature_sanity.py)가 같은 틀로 만드는 경고 · 오류 문장 → 쉬운 말.
// 틀에 안 맞으면 null(호출하는 쪽이 원문을 그대로 보인다).
const LINE_RULES: [RegExp, (m: RegExpExecArray) => string][] = [
  [
    /^ticker별 row 누락: (\d+)개 ticker 의 row 수가 trading_days×([\d.]+) 미만$/,
    (m) => `줄 수가 모자란 종목 ${fmtCount(Number(m[1]))}개(거래일 수의 ${ratioPct(m[2])} 미만)`,
  ],
  [
    /^asof별 ticker count 급감: (\d+)건 \(median=(\d+) 의 ([\d.]+) 미만\)$/,
    (m) =>
      `그날 종목 수가 크게 줄어든 날 ${fmtCount(Number(m[1]))}일(가운데 값 ${fmtCount(Number(m[2]))}종목의 ${ratioPct(m[3])} 미만)`,
  ],
  [
    /^latest asof 불일치: etf=(.*) \/ market_risk=(.*)$/,
    (m) => `ETF 값과 시장 값의 마지막 날짜가 다름: ETF ${pyVal(m[1])} · 시장 ${pyVal(m[2])}`,
  ],
  [/^etf_ml_feature_daily row 0건$/, () => "ETF 학습용 값이 0줄"],
  [/^market_risk_feature_daily row 0건$/, () => "시장 위험 신호 값이 0줄"],
  [
    /^KODEX200 시계열을 읽을 수 없음 — calculation check 불가$/,
    () => "KODEX 200 가격 자료를 읽을 수 없어 계산 검산을 못 함",
  ],
  [/^ticker=(\S+) asof=(\S+) ML row 부재$/, (m) => `견본 ${m[1]}: ${m[2]} 학습용 값 줄이 없음`],
  [
    /^ticker=(\S+) 원천 가격 없음 — 검산 skip$/,
    (m) => `견본 ${m[1]}: 원래 가격 자료가 없어 검산을 건너뜀`,
  ],
  [/^ticker=(\S+) asof=(\S+) 거래일 없음$/, (m) => `견본 ${m[1]}: ${m[2]} 거래일 자료가 없음`],
  [
    /^calc mismatch ticker=(\S+) field=(\S+) ml=(\S+) recomputed=(\S+)$/,
    (m) =>
      `계산이 다름: ${m[1]} ${fieldKo(m[2])} — 저장값 ${pyVal(m[3])} · 다시 계산 ${pyVal(m[4])}`,
  ],
  [
    /^ticker=(\S+) asof=(\S+) nav_status=(\S+) 인데 재검색 시 lookup 결과 None$/,
    (m) => `${m[1]} ${m[2]}: NAV가 연결됐다고 기록됐지만 다시 찾으면 NAV가 없음`,
  ],
  [
    /^FUTURE NAV ticker=(\S+) feature_asof=(\S+) nav_asof=(\S+)$/,
    (m) => `미래 날짜 NAV를 씀: ${m[1]} ${m[2]} 줄에 ${m[3]} NAV 연결`,
  ],
  [
    /^source_flags 누락 ticker=(\S+) feature_asof=(\S+) nav_asof=(\S+)$/,
    (m) => `${m[1]} ${m[2]}: 그 전 NAV(${m[3]})를 썼다는 표시가 빠짐`,
  ],
  [
    /^market_risk_feature_daily row 0건 — risk proxy 검산 불가$/,
    () => "시장 위험 신호 값이 0줄이라 위험 신호 값 점검을 못 함",
  ],
  [/^all-null risk proxy asof=(\S+)$/, (m) => `위험 신호 값이 모두 빈 날: ${m[1]}`],
  [
    /^null ratio > ([\d.]+): (\S+) = (\S+)$/,
    (m) => `빈 값 비율이 ${m[1]}를 넘음: ${fieldKo(m[2])} = ${m[3]}`,
  ],
];

function plainLine(s: string): string | null {
  for (const [re, fmt] of LINE_RULES) {
    const m = re.exec(s);
    if (m) return fmt(m);
  }
  return null;
}

const RISK_NULL_RATIO = /^null ratio > /;

function subList(sub: MlSanitySubChecks | undefined, key: "warnings" | "errors"): string[] {
  const v = sub?.[key];
  return Array.isArray(v) ? v : [];
}

// '경고 n건(아래) · 오류 n건(아래)' — 0건이면 생략.
function belowTail(sub: MlSanitySubChecks | undefined): string {
  const parts: string[] = [];
  const w = subList(sub, "warnings").length;
  const e = subList(sub, "errors").length;
  if (w > 0) parts.push(`경고 ${fmtCount(w)}건(아래)`);
  if (e > 0) parts.push(`오류 ${fmtCount(e)}건(아래)`);
  return parts.length ? ` · ${parts.join(" · ")}` : "";
}

const SNAPSHOT_MISSING_PREFIX = "sanity snapshot 미생성";
const SNAPSHOT_BROKEN_PREFIX = "snapshot 파일이 손상되어 읽을 수 없습니다";

function Conclusion({ state }: { state: LoadState }) {
  if (state.phase === "loading") {
    return (
      <CardConclusion tone="muted" label="불러오는 중">
        점검 결과를 불러오는 중입니다.
      </CardConclusion>
    );
  }
  if (state.phase === "error") {
    return (
      <CardConclusion tone="bad" label="불러오지 못함">
        {state.summary}
        {state.rawVisible ? ` 원문: ${state.message}` : null}
      </CardConclusion>
    );
  }
  const data = state.data;
  if (data.status === "error") {
    return (
      <CardConclusion tone="bad" label="파일 손상">
        점검 결과 파일이 손상되어 읽을 수 없습니다.
      </CardConclusion>
    );
  }
  if (data.status === "empty") {
    return (
      <CardConclusion tone="muted" label="점검 결과 없음">
        아직 점검 결과가 없습니다.
      </CardConclusion>
    );
  }
  if (!data.snapshot) {
    return (
      <CardConclusion tone="muted" label="확인 필요">
        응답에 점검 결과가 없습니다(응답 상태 {String(data.status ?? DASH)}).
      </CardConclusion>
    );
  }
  const snap = data.snapshot;
  const range = snap.feature_asof_range;
  const v = statusView(snap.sanity_status);
  const known = v.tone !== "muted";
  return (
    <CardConclusion tone={v.tone} label={v.label}>
      {known ? null : "알 수 없는 점검 상태 · "}경고 <b>{fmtCount(snap.warnings.length)}</b>건 ·
      오류 <b>{fmtCount(snap.errors.length)}</b>건 · 마지막 자료일 <b>{range.end ?? DASH}</b> ·{" "}
      <b>{fmtCount(range.trading_days)}</b>거래일 · ETF <b>{fmtCount(snap.etf_feature_row_count)}</b>
      줄 · 시장 <b>{fmtCount(snap.market_risk_row_count)}</b>줄 · 견본{" "}
      <b>{fmtCount(snap.checked_ticker_count)}</b>종목 검산
    </CardConclusion>
  );
}

function DevLines({ lines }: { lines: ReactNode[] }) {
  return (
    <DevDetails>
      {lines.map((l, i) => (
        <div key={i}>{l}</div>
      ))}
    </DevDetails>
  );
}

const DEV_COMMAND =
  "만드는 명령: scripts/check_ml_feature_sanity.py (화면의 「이전 자료와 실험 다시 만들기」도 같은 핵심 함수 build_sanity_report 를 부름)";

export default function MLFeatureSanityCard() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    fetchMlFeatureSanityLatest()
      .then((data) => {
        if (!cancelled) setState({ phase: "ready", data });
      })
      .catch((e) => {
        if (!cancelled) {
          setState({ phase: "error", message: describeError(e), ...plainError(e) });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="card">
      <h2>이전 자료 점검</h2>
      <Conclusion state={state} />
      <p className="helper" data-role="description" style={{ marginBottom: 8 }}>
        이전 Baseline 실험에 넣기 전에 자료를 점검한 결과입니다(자료 기간 · 계산 검산 · NAV 연결 ·
        위험 신호 값의 빈 비율). 모델 · 위험 기준 · 매수 · 매도 판단은 없습니다. 다시 점검은 아래
        「이전 자료와 실험 다시 만들기」에서 합니다.
      </p>
      {state.phase === "error" && (
        <DevLines lines={["조회: GET /ml/feature-sanity/latest", `오류 원문: ${state.message}`]} />
      )}
      {state.phase === "ready" && <SanityBody data={state.data} />}
    </div>
  );
}

function NoSnapshotBody({ data }: { data: MlFeatureSanityResponse }) {
  const msg = data.message ?? "";
  const dev = [
    `응답 상태: ${String(data.status)} · 파일: ${data.snapshot_path}`,
    msg ? `메시지 원문: ${msg}` : "메시지 원문: 없음",
    DEV_COMMAND,
  ];
  if (data.status === "error") {
    const known = msg.startsWith(SNAPSHOT_BROKEN_PREFIX);
    return (
      <>
        <div className="message error">
          점검 결과 파일은 있지만 내용을 읽을 수 없습니다.
          {msg && !known ? (
            <div style={{ marginTop: 4 }}>
              {msg} · 원인 확인 필요
            </div>
          ) : null}
        </div>
        <DevLines lines={dev} />
      </>
    );
  }
  const known = msg === "" || msg.startsWith(SNAPSHOT_MISSING_PREFIX);
  return (
    <>
      <div className="message info">
        {data.status === "empty"
          ? "점검 결과 파일이 아직 만들어지지 않았습니다. "
          : null}
        「이전 자료와 실험 다시 만들기」를 실행하면 점검 결과가 생깁니다.
        {!known ? (
          <div style={{ marginTop: 4, color: "var(--muted)" }}>{msg}</div>
        ) : null}
      </div>
      <DevLines lines={dev} />
    </>
  );
}

function SanityBody({ data }: { data: MlFeatureSanityResponse }) {
  if (data.status === "error" || data.status === "empty" || !data.snapshot) {
    return <NoSnapshotBody data={data} />;
  }
  const snap = data.snapshot;
  const range = snap.feature_asof_range;
  const cov = snap.coverage_checks;
  const calc = snap.calculation_checks;
  const nav = snap.nav_join_checks;
  const risk = snap.risk_proxy_checks;
  const checkedFields = Array.isArray(calc?.["checked_fields"])
    ? (calc?.["checked_fields"] as unknown[])
    : null;
  const match = cov?.["latest_asof_matches_readiness"];
  const matchText =
    match === true
      ? "ETF 값과 시장 값의 마지막 날짜가 같음"
      : match === false
        ? "ETF 값과 시장 값의 마지막 날짜가 다름"
        : `마지막 날짜 비교 ${String(match ?? DASH)}`;
  const riskOver = subList(risk, "warnings").filter((w) => RISK_NULL_RATIO.test(w)).length;
  const checkedAt = kstText(snap.generated_at);
  const navRaw = snap.sample_rows
    .filter((r) => r.nav_status && r.nav_status !== "ok")
    .map((r) => `${r.ticker}=${r.nav_status}`);

  return (
    <>
      {data.status !== "ok" ? (
        <div className="message info" style={{ marginBottom: 8 }}>
          응답 상태 원문 {String(data.status)} — 예상과 다름 · 확인 필요
        </div>
      ) : null}
      <table className="market-topn-table" style={{ marginBottom: 12 }}>
        <thead>
          <tr>
            <th>점검</th>
            <th style={{ width: 100 }}>결과</th>
            <th>내용</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>자료 기간 · 빠진 줄</td>
            <td>
              <StatusBadge status={cov?.status} />
            </td>
            <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              {range.start ?? DASH} → {range.end ?? DASH} · {matchText}
              {belowTail(cov)}
            </td>
          </tr>
          <tr>
            <td>계산 검산</td>
            <td>
              <StatusBadge status={calc?.status} />
            </td>
            <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              {/* checked_fields = 비교 대상 고정 목록(실제 검산 여부 아님 · KODEX 200 자료가 없으면 검산 0) */}
              {checkedFields
                ? `다시 계산해 비교하는 값 ${fmtCount(checkedFields.length)}개`
                : `다시 계산해 비교하는 값 ${DASH}`}{" "}
              · 경고 {fmtCount(subList(calc, "warnings").length)} · 오류{" "}
              {fmtCount(subList(calc, "errors").length)}
            </td>
          </tr>
          <tr>
            <td>NAV 연결</td>
            <td>
              <StatusBadge status={nav?.status} />
            </td>
            <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              미래 날짜 NAV를 쓴 줄 <strong>{countText(nav?.["future_nav_join_count"])}</strong> ·
              NAV가 없는 줄의 비율 {ratioText(nav?.["unavailable_ratio"])} · 같은 날 NAV로 연결{" "}
              {countText(nav?.["same_asof_count"])}줄 · 그 전 최신 NAV로 연결{" "}
              {countText(nav?.["past_latest_count"])}줄
            </td>
          </tr>
          <tr>
            <td>위험 신호 값</td>
            <td>
              <StatusBadge status={risk?.status} />
            </td>
            <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
              모든 값이 빈 날 <strong>{countText(risk?.["all_null_asof_count"])}</strong>일 · 빈
              비율이 기준을 넘은 값 {fmtCount(riskOver)}개{belowTail(risk)}
            </td>
          </tr>
        </tbody>
      </table>
      <IssueList title="오류" lines={snap.errors} failure color="var(--danger)" />
      <IssueList title="경고" lines={snap.warnings} color="var(--warn)" />
      <SampleTable rows={snap.sample_rows} />
      <p className="helper" style={{ marginTop: 8, fontSize: "0.78rem" }}>
        점검한 시각 {checkedAt ?? snap.generated_at}
      </p>
      <DevLines
        lines={[
          `점검 이름: coverage · calculation · nav join · risk proxy (sanity_status=${String(snap.sanity_status)})`,
          `응답 상태: ${String(data.status)} · 파일: ${data.snapshot_path}`,
          `만든 시각 원문: ${snap.generated_at}`,
          DEV_COMMAND,
          `값 원문: latest_asof_matches_readiness=${String(match)} · future_nav_join_count=${String(nav?.["future_nav_join_count"])} · unavailable_ratio=${String(nav?.["unavailable_ratio"])} · same_asof_count=${String(nav?.["same_asof_count"])} · past_latest_count=${String(nav?.["past_latest_count"])} · all_null_asof_count=${String(risk?.["all_null_asof_count"])}`,
          `다시 계산한 값: ${checkedFields ? checkedFields.map(String).join(" · ") : DASH}`,
          ...(navRaw.length ? [`견본 NAV 상태 원문: ${navRaw.join(" · ")}`] : []),
          ...rawLines("오류 원문", snap.errors),
          ...rawLines("경고 원문", snap.warnings),
        ]}
      />
    </>
  );
}

function rawLines(title: string, lines: string[]): string[] {
  if (lines.length === 0) return [];
  const out = [`${title} ${fmtCount(lines.length)}건:`];
  for (const s of lines.slice(0, LIST_CAP)) out.push(`· ${s}`);
  if (lines.length > LIST_CAP) out.push(`... (${fmtCount(lines.length - LIST_CAP)}건 추가)`);
  return out;
}

function IssueList({
  title,
  lines,
  failure = false,
  color,
}: {
  title: string;
  lines: string[];
  failure?: boolean;
  color: string;
}) {
  if (lines.length === 0) return null;
  return (
    <div style={{ marginBottom: 12 }}>
      <h3 style={{ fontSize: "0.9rem", margin: "8px 0 4px 0", color }}>
        {title} {fmtCount(lines.length)}건
      </h3>
      <ul style={{ margin: "4px 0 0", paddingLeft: 20, fontSize: "0.85rem" }}>
        {lines.slice(0, LIST_CAP).map((s, i) => {
          const plain = plainLine(s);
          return (
            <li key={`${title}-${i}`}>
              {plain ?? (failure ? `${s} · 원인 확인 필요` : s)}
            </li>
          );
        })}
        {lines.length > LIST_CAP && <li>... ({fmtCount(lines.length - LIST_CAP)}건 추가)</li>}
      </ul>
    </div>
  );
}

// 견본 행의 NAV 상태(ok 외) — 아는 값만 쉬운 말, 모르는 값은 원문.
function navStatusText(s: string): string {
  if (s === "unavailable") return "NAV 없음";
  if (s === "partial") return "예전에 받은 NAV 다시 씀";
  return s;
}

function SampleTable({ rows }: { rows: MlSanitySampleRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="helper" style={{ fontSize: "0.85rem" }}>
        견본 ETF 0개 — 위 「자료 기간 · 빠진 줄」 점검 결과를 확인하세요.
      </div>
    );
  }
  return (
    <>
      <h3
        style={{
          fontSize: "0.9rem",
          margin: "8px 0 4px 0",
          color: "var(--muted)",
        }}
      >
        견본 ETF(마지막 자료일)
      </h3>
      <table className="market-topn-table">
        <thead>
          <tr>
            <th style={{ width: 80 }}>코드</th>
            <th>이름</th>
            <th style={{ textAlign: "right" }}>5일 수익률</th>
            <th style={{ textAlign: "right" }}>20일 수익률</th>
            <th style={{ textAlign: "right" }}>KODEX 200 대비 20일</th>
            <th style={{ textAlign: "right" }}>20일 변동성</th>
            <th style={{ textAlign: "right" }}>20일 고점 대비</th>
            <th style={{ textAlign: "right" }}>NAV 괴리율</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ticker}>
              <td>
                <code>{r.ticker}</code>
              </td>
              <td>{r.name ?? DASH}</td>
              <td style={{ textAlign: "right" }}>{fmtPct(r.return_5d)}</td>
              <td style={{ textAlign: "right" }}>{fmtPct(r.return_20d)}</td>
              <td style={{ textAlign: "right" }}>
                {fmtPct(r.excess_return_20d_vs_kodex200)}
              </td>
              <td style={{ textAlign: "right" }}>{fmtNum(r.volatility_20d)}</td>
              <td style={{ textAlign: "right" }}>{fmtPct(r.drawdown_20d)}</td>
              <td style={{ textAlign: "right" }}>
                {fmtPct(r.nav_discount_rate_pct)}
                {r.nav_status && r.nav_status !== "ok" ? (
                  <span style={{ fontSize: "0.75rem", color: "var(--muted)" }}>
                    {" "}
                    ({navStatusText(r.nav_status)})
                  </span>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
