// POC6-14 — 「전향 ML 비교 · 연구」 카드의 문구 · 표시 함수(화면과 복사가 같은 함수를 쓴다 · PLAN 판정 Q2).
//
// - D20(늘 0 이하): 소수 둘째 자리로 만든 값이 0.00 이면 부호 없이 "0.00%"(+0.00% · -0.00% 섞지 않음).
// - MAE · 작게 추정한 정도(늘 0 이상 크기): 부호 없는 %p. 음수 · 비유한 값은 abs 로 살리지 않고 '확인 필요'.
// - 기존 fmtPct · fmtPctp 의 전역 동작은 바꾸지 않는다(이 카드 전용).
// - 시각은 Asia/Seoul 기준 'YYYY-MM-DD HH:MM:SS'(해석 못 하면 '미확인').

import type {
  ForwardActual,
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

export const NOT_EVAL_LONG = "이 기준일의 성숙 평가 상태 기록이 아직 없습니다";
export const D20_MEANING =
  "D20 = 기준일 종가 대비 다음 20거래일 종가 중 가장 깊은 하락(0 이하) · 연구 추정이며 매매 수익률이 아님";
const CHECK = "확인 필요";

export const ACTUAL_TEXT: Record<string, string> = {
  PENDING_NOT_DUE: "결과 대기",
  PENDING_CALENDAR: "결과 일정 확인 불가",
  DUE_DATA_MISSING: "결과 자료 미확보",
  DATA_CHECK_REQUIRED: "결과 자료 확인 필요",
  NOT_EVALUATED: "성숙 확인 전",
  CHECK_REQUIRED: "값 확인 필요",
};

export const METHOD_STATUS_TEXT: Record<string, string> = {
  FAILED: "실패",
  ENV_MISMATCH: "환경 불일치",
  NOT_RUN_ENV: "미실행(환경)",
  DATA_SHORT: "자료 부족",
  CHECK_REQUIRED: "값 확인 필요",
  MISSING: "기록 없음",
};

export const HELP_PARAGRAPHS = [
  "연구용 표시입니다. 운영 ML 로 채택되지 않았고 매수 · 매도 권고가 아닙니다.",
  "고정 연구 표본 — 06 연구에서 정해 둔 목록이며 보유 · 관심 · 추천 목록과 무관합니다(이름 = 선정 당시).",
  "D20 = 기준일 종가 대비 다음 20거래일 종가 중 가장 깊은 하락(0 이하로 제한). 20일째 수익률 · MDD · 장중 저점 · 손실 확률 · 보유 기간이 아닙니다.",
  "표의 예측은 범위 제한(−100% ~ 0%) 뒤 값입니다. 공개 확인 = 예측 파일이 이미 놓여 있음을 확인한 시각이며, 다음 거래일 15:30 전에 확인된 기록만 주 기록입니다.",
  `'성숙 확인 전' = ${NOT_EVAL_LONG}. 20거래일이 안 지났다는 뜻도, 앞으로 평가된다는 보장도 아닙니다.`,
  "누적 비교는 저장된 보고를 그대로 보여 줍니다. 비교마다 분모(공통 행)가 다르고, 오차가 작다는 것이 추천에 쓸 수 있다는 뜻은 아닙니다. D20 ≤ −8% 는 기존 연구의 보조 구분이며 경보 기준이 아닙니다.",
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

// 회차 id 의 UTC 접두(YYYYMMDDTHHMMSSZ) → KST 'YYYY-MM-DD HH:MM'(머리말 표시용 · 전체 id 는 행 상세).
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
    const retry = m.retried_at ? ` · 재시도 공개 확인 ${kstTime(m.retried_at)}` : "";
    return `OK · 범위 제한 뒤 ${fmtD20(m.pred_pct)}${retry}`;
  }
  return `${METHOD_STATUS_TEXT[m.status] ?? m.status} — ${m.reason || "사유 미기록"}`;
}

export function actualShort(a: ForwardActual | undefined): string {
  if (!a) return "-";
  if (a.state === "MATURED") return fmtD20(a.actual_pct);
  return ACTUAL_TEXT[a.state] ?? a.state;
}

export function actualLong(a: ForwardActual | undefined): string {
  if (!a) return "-";
  if (a.state === "MATURED") return `${fmtD20(a.actual_pct)} · 목표 끝 ${a.target_end ?? "미확인"}`;
  if (a.state === "NOT_EVALUATED") return NOT_EVAL_LONG;
  if (a.state === "CHECK_REQUIRED") return `${ACTUAL_TEXT.CHECK_REQUIRED} — ${a.reason ?? "사유 미기록"}`;
  return `${ACTUAL_TEXT[a.state] ?? a.state} — 상태 출처 ${a.basis_run ?? "미확인"} 회차(${kstTime(a.basis_at)})`;
}

// 화면 경고 · 복사문이 같은 문구를 쓰도록 여기 한 곳에서 만든다(검증자 r1 F2 · 화면에 보인 경고는 복사에도 남는다).
export type Notice = { level: "ok" | "info" | "error"; text: string };

export function reportNotices(data: ForwardComparisonResponse): Notice[] {
  const rep = data.report;
  const runs = data.basis?.record_runs.join(", ") || "미확인";
  if (!rep || rep.state === "NONE") {
    return [{ level: "info", text: "보고 없음 — 06 실행이 아직 비교 보고를 남기지 않았습니다. 이 화면은 보고를 만들지 않습니다." }];
  }
  if (!rep.generated_at) {
    // 정상 보고가 하나도 없다(파일은 있으나 모두 읽지 못함) — '보고 없음'으로 바꾸지 않는다
    return [
      {
        level: "error",
        text: `최신 보고 확인 필요 — 보고 파일 ${rep.unreadable?.length ?? "미확인"}개를 모두 읽지 못했습니다. 숫자를 보여 주지 않습니다.`,
      },
    ];
  }
  const out: Notice[] = [];
  if (rep.selected_D === "INCLUDED") {
    out.push({ level: "ok", text: "이 기준일을 기록한 회차의 보고가 있습니다 — 아래 누적 보고 집계에 포함" });
  } else if (rep.selected_D === "RUN_REPORT_MISSING") {
    out.push({
      level: "info",
      text: `보고서 확인 대기 — 이 기준일을 기록한 회차(${runs})의 보고가 아직 없습니다(작성 중이거나 만들어지지 않음). 아래는 그 전 정상 보고입니다. 이 화면은 보고를 만들지 않습니다.`,
    });
  } else {
    out.push({
      level: "error",
      text: `최신 보고 확인 필요 — 이 기준일을 기록한 회차(${runs})의 보고 파일을 읽지 못했습니다. 아래는 읽을 수 있는 그 전 정상 보고입니다.`,
    });
  }
  const newer = rep.newer_unreadable?.length ?? 0;
  if (newer > 0 && rep.selected_D !== "RUN_REPORT_UNREADABLE") {
    out.push({ level: "error", text: `최신 보고 확인 필요 — 더 늦은 이름의 보고 파일 ${newer}개를 읽지 못했습니다.` });
  }
  if (rep.state === "CHECK_REQUIRED") {
    out.push({ level: "error", text: "보고 값 확인 필요 — 허용 범위를 벗어난 값은 숫자로 보이지 않습니다." });
  }
  return out;
}

export function cardNotices(data: ForwardComparisonResponse): Notice[] {
  const n = data.basis?.unreadable_runs.length ?? 0;
  return n > 0
    ? [{ level: "error", text: `회차 기록 ${n}개를 읽지 못했습니다 — 성숙 상태는 「값 확인 필요」로 둡니다.` }]
    : [];
}

export function reportLine(data: ForwardComparisonResponse): string {
  const rep = data.report;
  const notices = reportNotices(data).map((x) => `보고 상태: ${x.text}`);
  if (!rep || rep.state === "NONE" || !rep.generated_at) return ["누적 비교 보고: 정상 보고 없음", ...notices].join("\n");
  const p = rep.predicted_dates;
  const m = rep.matured_dates;
  const rows = rep.comparisons?.ALL_FOUR?.rows ?? null;
  const head =
    `누적 비교 보고 ${rep.id ?? "미확인"}: ${kstTime(rep.generated_at)} KST 생성` +
    ` · 예측 포함 기준일 ${p?.count ?? 0}개${p?.count ? `(${p.first} ~ ${p.last})` : ""}` +
    ` · 성숙 비교 기준일 ${m?.count ?? 0}개${m?.count ? `(${m.first} ~ ${m.last})` : ""}` +
    ` · 네 방법 공통 비교 행 ${rows ?? "미확인"}${rows === 0 ? " — 아직 비교할 결과 없음" : ""}`;
  return [head, ...notices].join("\n");
}

// [복사] 문장 — 지금 화면에 그린 응답(data)에서만 만든다(클릭 때 조회 · 실행 없음).
export function copyText(data: ForwardComparisonResponse, row: ForwardRow): string {
  const det = row.detail;
  const methods = METHODS.map(([k, label]) => {
    const m = row.methods?.[k];
    if (!m) return `${label} 미확인`;
    if (m.status === "OK") return `${label} ${fmtD20(m.pred_pct)}`;
    return `${label} ${METHOD_STATUS_TEXT[m.status] ?? m.status}${m.reason ? `(${m.reason})` : ""}`;
  });
  return [
    `[전향 ML 비교 · 연구 — ${data.label}]`,
    `고정 연구 표본(${data.cohort?.size ?? "미확인"}종 · 보유 · 추천 목록과 무관) 중 ${row.ticker} ${row.name ?? "이름 미확인"}`,
    `기준일 D ${data.selected_D ?? "미확인"} · 공개 확인 ${kstTime(det?.visible_by)} KST · 모델 판 ${det?.model_version ?? "미확인"} · 기록 회차 ${det?.run_id ?? "미확인"}`,
    `D20 예측(범위 제한 뒤): ${methods.join(" · ")}`,
    `실제 D20: ${actualLong(row.actual)}`,
    ...cardNotices(data).map((x) => `주의: ${x.text}`),
    reportLine(data),
    D20_MEANING,
  ].join("\n");
}
