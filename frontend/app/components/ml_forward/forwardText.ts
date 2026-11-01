// POC6-14 — 「전향 ML 비교 · 연구」 카드의 문구 · 표시 함수(화면과 복사가 같은 함수를 쓴다 · PLAN 판정 Q2).
// 2026-11-01 POC6-15 — 화면 이름 「예측과 결과 비교」 · 문구를 쉬운 한국어로(D20 → 20거래일 내 종가 하락폭 ·
//   날짜 균형 MAE → 평균 오차 · 회차 → 실행 · 모델 판 → 모델 버전). 맨 위 '현재 결론 한 줄'(forwardConclusion)도
//   화면과 복사가 같이 쓴다. 상태 구분(보고 없음 · 비교 0 · 손상)과 숫자 · 단위 · 반올림은 그대로.
//
// - D20(늘 0 이하): 소수 둘째 자리로 만든 값이 0.00 이면 부호 없이 "0.00%"(+0.00% · -0.00% 섞지 않음).
// - MAE · 작게 추정한 정도(늘 0 이상 크기): 부호 없는 %p. 음수 · 비유한 값은 abs 로 살리지 않고 '확인 필요'.
// - 기존 fmtPct · fmtPctp 의 전역 동작은 바꾸지 않는다(이 카드 전용).
// - 시각은 Asia/Seoul 기준 'YYYY-MM-DD HH:MM:SS'(해석 못 하면 '미확인').

import type {
  ForwardActual,
  ForwardComparisonEntry,
  ForwardComparisonResponse,
  ForwardMethodCell,
  ForwardMethodKey,
  ForwardRow,
  TimeSpan,
} from "@/lib/api";

export const METHODS: [ForwardMethodKey, string][] = [
  ["MEDIAN", "중앙값 기준선"],
  ["RIDGE", "Ridge"],
  ["HGB", "HGB"],
  ["MLP_CPU", "MLP(CPU)"],
];

// 06 보고의 비교 세 가지(`app/forward_compare/report.py :: COMPARISONS`) — 비교마다 같은 종목 · 같은 날 공통 줄이
//   따로라 줄 수가 다르다(HGB 가 실패해도 MLP 비교는 있을 수 있음). 표 · 맨 위 결론 · 복사문이 이 목록 하나를 쓴다.
export const COMPARISONS: [string, string, ForwardMethodKey[]][] = [
  ["HGB_vs_MEDIAN_RIDGE", "HGB · 중앙값 기준선 · Ridge 함께", ["MEDIAN", "RIDGE", "HGB"]],
  ["MLP_CPU_vs_MEDIAN_RIDGE", "MLP(CPU) · 중앙값 기준선 · Ridge 함께", ["MEDIAN", "RIDGE", "MLP_CPU"]],
  ["ALL_FOUR", "네 방법 함께", ["MEDIAN", "RIDGE", "HGB", "MLP_CPU"]],
];

// 비교 하나의 상태 — 줄 수 > 0 = 결과 있음 · 0 = 아직 없음(정상) · 그 밖(항목 없음 · 숫자 아님 · 음수) = 구조 확인 필요.
export type ComparisonState = "has" | "empty" | "problem";

export function comparisonState(x: ForwardComparisonEntry | undefined): ComparisonState {
  const n = x?.rows;
  if (typeof n !== "number" || !Number.isFinite(n) || n < 0) return "problem";
  return n === 0 ? "empty" : "has";
}

// 세 비교의 줄 수 한 줄(맨 위 결론 · 복사문 공용 · 구조 확인 필요는 '미확인').
function comparisonList(rep: NonNullable<ForwardComparisonResponse["report"]>): string {
  return COMPARISONS.map(([key, label]) => {
    const n = rep.comparisons?.[key]?.rows;
    return `${label} ${typeof n === "number" && comparisonState(rep.comparisons?.[key]) !== "problem" ? `${n.toLocaleString("en-US")}건` : "미확인"}`;
  }).join(" · ");
}

export const NOT_EVAL_LONG = "이 기준일의 결과 확인 기록이 아직 없습니다";
export const D20_MEANING =
  "20거래일 내 종가 하락폭(연구 문서 이름 D20) = 기준일 종가 대비 이후 20거래일 종가 중 가장 낮은 변화(0 이하) · 연구 추정이며 매매 수익률이 아님";
// 백엔드 고정 표시(RESEARCH_LABEL) → 쉬운 말. 다른 값이 오면 원문 그대로.
const LABEL_TEXT: Record<string, string> = { "연구용 · 운영 미채택": "연구용 · 운영에 쓰지 않음" };

export function labelText(label: string | null | undefined): string {
  if (!label) return "연구용";
  return LABEL_TEXT[label] ?? label;
}
const CHECK = "확인 필요";

export const ACTUAL_TEXT: Record<string, string> = {
  PENDING_NOT_DUE: "결과 대기",
  PENDING_CALENDAR: "결과 일정 확인 불가",
  DUE_DATA_MISSING: "결과 자료 미확보",
  DATA_CHECK_REQUIRED: "결과 자료 확인 필요",
  NOT_EVALUATED: "결과 확인 전",
  CHECK_REQUIRED: "값 확인 필요",
};

export const METHOD_STATUS_TEXT: Record<string, string> = {
  FAILED: "실패",
  ENV_MISMATCH: "환경 불일치",
  NOT_RUN_ENV: "실행 안 함(환경)",
  DATA_SHORT: "자료 부족",
  CHECK_REQUIRED: "값 확인 필요",
  MISSING: "기록 없음",
};

export const HELP_PARAGRAPHS = [
  "연구용입니다. 운영에 쓰도록 채택되지 않았고 매수 · 매도 권고가 아닙니다.",
  "흐름(구조 설명): 시장 자료를 가져와 → 필요할 때 모델을 학습하고 → 기준일마다 예측을 미리 기록한 뒤 → 20거래일 자료가 모이면 실제 결과와 비교합니다. 오늘 각 단계가 끝났다는 표시가 아닙니다.",
  "고정 연구 대상: 이 연구에서 미리 정해 둔 ETF 목록입니다. 보유 · 관심 · 추천 목록과 관계없습니다(이름 = 정할 당시 이름).",
  "20거래일 내 종가 하락폭(연구 문서 이름 D20): 기준일 종가 대비 이후 20거래일 종가 중 가장 낮은 변화입니다. 모두 기준일보다 높으면 0입니다. 20일째 수익률 · 고점 대비 최대 낙폭 · 장중 저점 · 손실 확률 · 보유 기간이 아닙니다. 표의 예측은 −100% ~ 0% 범위로 맞춘 값입니다.",
  "네 가지 방법: 중앙값 기준선(과거 값의 가운데) · Ridge(선형 모델) · HGB(나무 모델) · MLP(신경망 · CPU로 계산).",
  "예측 공개 확인: 예측 파일이 이미 놓여 있음을 확인한 시각입니다. 다음 거래일 15:30 전에 확인된 기록만 비교에 넣습니다.",
  `결과 상태: '결과 대기' = 20거래일이 아직 지나지 않음 · '결과 확인 전' = ${NOT_EVAL_LONG}(20거래일이 안 지났다는 뜻도, 앞으로 확인된다는 보장도 아님).`,
  "평균 오차(%p): 기준일마다 종목별 |예측 − 실제|를 평균하고, 그 값을 날짜마다 같은 비중으로 다시 평균합니다. 같은 종목 · 같은 날에 비교할 방법이 모두 있는 경우만 셉니다. 비교마다 건수가 달라 한 줄 순위로 합치지 않으며, 오차가 작다고 추천에 쓸 수 있다는 뜻은 아닙니다. 하락폭 −8% 이하 구분은 기존 연구의 보조 구분이며 경보 기준이 아닙니다.",
];

export function fmtD20(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  if (!Number.isFinite(v)) return CHECK;
  const r = Number(v.toFixed(2));
  if (r === 0) return "0.00%";
  return `${r > 0 ? "+" : ""}${v.toFixed(2)}%`;
}

export function fmtSizePp(v: number | null | undefined): string {
  if (v === null || v === undefined) return "-";
  if (!Number.isFinite(v) || v < 0) return CHECK;
  return `${v.toFixed(2)}%p`;
}

export function kstTime(iso: string | null | undefined): string {
  if (!iso) return "미확인";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "미확인";
  const p = Object.fromEntries(
    new Intl.DateTimeFormat("en-CA", {
      timeZone: "Asia/Seoul",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hourCycle: "h23",
    })
      .formatToParts(d)
      .map((x) => [x.type, x.value]),
  );
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}:${p.second}`;
}

// 실행(회차) id 의 UTC 접두(YYYYMMDDTHHMMSSZ) → KST 'YYYY-MM-DD HH:MM'(화면 표시용 · 전체 id 는 개발 정보 · 복사문).
export function runTime(runId: string): string {
  const m = /^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z/.exec(runId);
  if (!m) return runId;
  return kstTime(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:${m[6]}Z`).slice(0, 16);
}

export function spanText(s: TimeSpan | null | undefined): string {
  if (!s) return "미확인";
  return s.min === s.max ? kstTime(s.min) : `${kstTime(s.min)} ~ ${kstTime(s.max)}`;
}

export function methodShort(m: ForwardMethodCell | undefined): string {
  if (!m) return "-";
  if (m.status === "OK") return fmtD20(m.pred_pct);
  return METHOD_STATUS_TEXT[m.status] ?? m.status;
}

export function methodLong(m: ForwardMethodCell | undefined): string {
  if (!m) return "-";
  if (m.status === "OK") {
    const retry = m.retried_at ? ` · 다시 시도해 채움(공개 확인 ${kstTime(m.retried_at)})` : "";
    return `정상 · ${fmtD20(m.pred_pct)}(−100 ~ 0% 범위로 맞춘 값)${retry}`;
  }
  // 실패 · 미실행 사유는 06 이 남긴 원문 — 해석하지 않고 '원인 확인 필요'와 함께 그대로(판정 §4)
  return `${METHOD_STATUS_TEXT[m.status] ?? m.status} — ${m.reason ? `원인 확인 필요 · 원문: ${m.reason}` : "사유 미기록"}`;
}

export function actualShort(a: ForwardActual | undefined): string {
  if (!a) return "-";
  if (a.state === "MATURED") return fmtD20(a.actual_pct);
  return ACTUAL_TEXT[a.state] ?? a.state;
}

export function actualLong(a: ForwardActual | undefined): string {
  if (!a) return "-";
  if (a.state === "MATURED") return `${fmtD20(a.actual_pct)} · 20거래일 끝 날짜 ${a.target_end ?? "미확인"}`;
  if (a.state === "NOT_EVALUATED") return NOT_EVAL_LONG;
  if (a.state === "CHECK_REQUIRED") return `${ACTUAL_TEXT.CHECK_REQUIRED} — ${a.reason ?? "사유 미기록"}`;
  const at = a.basis_run ? `${runTime(a.basis_run)} 실행` : "실행 미확인";
  return `${ACTUAL_TEXT[a.state] ?? a.state} — 결과 상태 확인 ${at}(${kstTime(a.basis_at)})`;
}

// 화면 경고 · 복사문이 같은 문구를 쓰도록 여기 한 곳에서 만든다(검증자 r1 F2 · 화면에 보인 경고는 복사에도 남는다).
export type Notice = { level: "ok" | "info" | "error"; text: string };

export function reportNotices(data: ForwardComparisonResponse): Notice[] {
  const rep = data.report;
  const runs = data.basis?.record_runs.map(runTime).join(", ") || "미확인";
  if (!rep || rep.state === "NONE") {
    return [{ level: "info", text: "비교 보고가 아직 없습니다 — 정기 실행이 아직 비교 보고를 남기지 않았습니다. 이 화면은 보고를 만들지 않습니다." }];
  }
  if (!rep.generated_at) {
    // 정상 보고가 하나도 없다(파일은 있으나 모두 읽지 못함) — '보고 없음'으로 바꾸지 않는다
    return [
      {
        level: "error",
        text: `최신 보고를 확인해야 합니다 — 보고 파일 ${rep.unreadable?.length ?? "미확인"}개를 모두 읽지 못했습니다. 숫자를 보여 주지 않습니다.`,
      },
    ];
  }
  const out: Notice[] = [];
  if (rep.selected_D === "INCLUDED") {
    out.push({ level: "ok", text: "이 기준일을 기록한 실행의 비교 보고가 있습니다 — 아래 누적 비교에 포함" });
  } else if (rep.selected_D === "RUN_REPORT_MISSING") {
    out.push({
      level: "info",
      text: `이 기준일 보고 대기 — 이 기준일을 기록한 실행(${runs})의 보고가 아직 없습니다(작성 중이거나 만들어지지 않음). 아래는 그 전 정상 보고입니다. 이 화면은 보고를 만들지 않습니다.`,
    });
  } else {
    out.push({
      level: "error",
      text: `최신 보고를 확인해야 합니다 — 이 기준일을 기록한 실행(${runs})의 보고 파일을 읽지 못했습니다. 아래는 읽을 수 있는 그 전 정상 보고입니다.`,
    });
  }
  const newer = rep.newer_unreadable?.length ?? 0;
  if (newer > 0 && rep.selected_D !== "RUN_REPORT_UNREADABLE") {
    out.push({ level: "error", text: `최신 보고를 확인해야 합니다 — 이름 순서상 더 나중인 보고 파일 ${newer}개를 읽지 못했습니다.` });
  }
  if (rep.state === "CHECK_REQUIRED") {
    out.push({ level: "error", text: "보고 값 확인 필요 — 허용 범위를 벗어난 값은 숫자로 보이지 않습니다." });
  }
  return out;
}

export function cardNotices(data: ForwardComparisonResponse): Notice[] {
  const n = data.basis?.unreadable_runs.length ?? 0;
  return n > 0
    ? [{ level: "error", text: `실행 기록 ${n}개를 읽지 못했습니다 — 결과 상태는 「값 확인 필요」로 둡니다.` }]
    : [];
}

// 맨 위 '현재 결론 한 줄'(판정 §3) — 이미 받은 응답 값만 쓴다(새 판정 · 승자 · 효용 없음).
//   보고 없음 · 보고 손상 · 정상 보고에 비교 0 · 비교 있음을 합치지 않는다. 손상 · 읽기 실패 경고는
//   이 줄 바로 아래(카드)와 복사문에 같은 글로 남는다(reportNotices · cardNotices).
//   '비교 결과 있음' = 세 비교 중 하나라도 줄이 있음 · '아직 없음' = 세 비교 모두 0(검증자 r1 F1 — 네 방법 공통만 보면
//   HGB · MLP 비교가 있는데도 없음으로 요약됨).
export type Conclusion = { tone: "ok" | "warn" | "muted" | "bad"; label: string; text: string };

export function forwardConclusion(data: ForwardComparisonResponse): Conclusion {
  if (data.status === "NO_RECORDS") {
    return { tone: "muted", label: "예측 기록 없음", text: "공개 확인된 예측 기록이 아직 없습니다" };
  }
  if (data.status !== "OK") {
    return { tone: "bad", label: "확인 필요", text: "기록을 읽지 못해 숫자를 보여 주지 않습니다" };
  }
  const rep = data.report;
  if (!rep || rep.state === "NONE") {
    return { tone: "muted", label: "비교 보고가 아직 없습니다", text: "이 화면은 보고를 만들지 않습니다" };
  }
  if (!rep.generated_at || reportNotices(data).some((n) => n.level === "error")) {
    return { tone: "bad", label: "최신 보고를 확인해야 합니다", text: "아래 안내를 먼저 확인해 주세요" };
  }
  if (cardNotices(data).length > 0) {
    return { tone: "bad", label: "실행 기록을 확인해야 합니다", text: "아래 안내를 먼저 확인해 주세요" };
  }
  const c = rep.counts ?? {};
  const num = (v: unknown) => (typeof v === "number" ? v.toLocaleString("en-US") : "미확인");
  const base =
    `비교 보고 ${kstTime(rep.generated_at).slice(0, 16)} 만듦 · 지금까지 예측 ${num(c.primary_records)}건` +
    ` · 결과가 나온 예측 ${num(c.matured)}건`;
  const waiting = rep.selected_D === "RUN_REPORT_MISSING" ? " · 이 기준일 보고는 대기 중(그 전 보고 기준)" : "";
  const states = COMPARISONS.map(([key]) => comparisonState(rep.comparisons?.[key]));
  if (states.includes("problem")) {
    return { tone: "bad", label: "최신 보고를 확인해야 합니다", text: "비교 항목을 확인해야 합니다" };
  }
  if (states.every((x) => x === "empty")) {
    return { tone: "muted", label: "아직 비교할 결과가 없습니다", text: base + waiting };
  }
  const m = rep.matured_dates;
  return {
    tone: "ok",
    label: "비교 결과 있음",
    text: `${base} · 결과가 나온 기준일 ${m?.count ?? 0}개 · 같은 종목 · 같은 날 비교: ${comparisonList(rep)}${waiting}`,
  };
}

export function reportLine(data: ForwardComparisonResponse): string {
  const rep = data.report;
  const notices = reportNotices(data).map((x) => `보고 상태: ${x.text}`);
  if (!rep || rep.state === "NONE" || !rep.generated_at) return ["누적 비교 보고: 정상 보고 없음", ...notices].join("\n");
  const p = rep.predicted_dates;
  const m = rep.matured_dates;
  const states = COMPARISONS.map(([key]) => comparisonState(rep.comparisons?.[key]));
  const tail = states.includes("problem")
    ? " — 비교 항목 확인 필요"
    : states.every((x) => x === "empty")
      ? " — 아직 비교할 결과가 없습니다"
      : "";
  const head =
    `누적 비교 보고 ${rep.id ?? "미확인"}: ${kstTime(rep.generated_at)} KST 만듦` +
    ` · 예측이 들어간 기준일 ${p?.count ?? 0}개${p?.count ? `(${p.first} ~ ${p.last})` : ""}` +
    ` · 결과가 나온 기준일 ${m?.count ?? 0}개${m?.count ? `(${m.first} ~ ${m.last})` : ""}` +
    ` · 같은 종목 · 같은 날 비교: ${comparisonList(rep)}${tail}`;
  return [head, ...notices].join("\n");
}

// [복사] 문장 — 지금 화면에 그린 응답(data)에서만 만든다(클릭 때 조회 · 실행 없음).
export function copyText(data: ForwardComparisonResponse, row: ForwardRow): string {
  const det = row.detail;
  const methods = METHODS.map(([k, label]) => {
    const m = row.methods?.[k];
    if (!m) return `${label} 미확인`;
    if (m.status === "OK") return `${label} ${fmtD20(m.pred_pct)}`;
    return `${label} ${METHOD_STATUS_TEXT[m.status] ?? m.status}${m.reason ? `(원인 확인 필요 · 원문: ${m.reason})` : ""}`;
  });
  const c = forwardConclusion(data);
  return [
    `[예측과 결과 비교(연구 이름: 전향 ML 비교) — ${labelText(data.label)}]`,
    `현재 결론: ${c.label} · ${c.text}`,
    `고정 연구 대상(${data.cohort?.size ?? "미확인"}종 · 보유 · 추천 목록과 무관) 중 ${row.ticker} ${row.name ?? "이름 미확인"}`,
    `기준일 ${data.selected_D ?? "미확인"} · 예측 공개 확인 ${kstTime(det?.visible_by)} KST · 모델 버전 ${det?.model_version ?? "미확인"} · 기록 실행 ${det?.run_id ?? "미확인"}`,
    `예측(20거래일 내 종가 하락폭 · −100 ~ 0% 범위로 맞춘 값): ${methods.join(" · ")}`,
    `실제: ${actualLong(row.actual)}`,
    ...cardNotices(data).map((x) => `주의: ${x.text}`),
    reportLine(data),
    D20_MEANING,
  ].join("\n");
}
