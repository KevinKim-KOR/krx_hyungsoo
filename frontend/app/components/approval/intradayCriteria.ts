// POC6-34 L3 — 「OCI 운영·적용」 ② 「장중 급등락 설정」 카드의 판정 기준 표 문장(순수 함수).
//
// PLAN V1 §2-3 · O10 · O11 · I-16 ~ I-23 (설계자 PLAN 판정 Q6 · 2026-11-19 형수님 결정 '늘 펼침').
//   - 세 묶음 · 순서는 판정서 §2 표 순서다(I-18). 항목 이름은 기존 `POLICY_LABEL` 그대로다.
//   - 설정값 칸은 기존 표기 그대로(`5%` · `-5%` · `120분` · `4건`)이고, 값이 없거나 유한한 숫자가
//     아니면 '확인 불가'다(I-19). 0 이나 기본값으로 메우지 않는다.
//   - 문장은 고정 글이 아니다. 같은 응답의 값(자기 값 · 함께 쓰는 값 · 그 버전의 사업군 수)으로
//     만든다(I-20). 문장에 필요한 값이 하나라도 없으면 그 칸은 '확인 불가'다.
//   - 순위 개수 · 최소 성공 수는 백엔드 식을 옮긴 것이다(I-21 · `sector_signal._top_cut` ·
//     `coverage_pct = round(성공 / 사업군 × 100, 1)`). 정확히 반에 걸리는 값에서는 Python 반올림과
//     다를 수 있다(PLAN §7-8 · 지금 값 27개 · 80% 에는 해당 없음).
//
// 판정 기준 값은 설계 고정값(`app/intraday_config/generator.py` `CONFIRMED_POLICY`)이고, 화면에서
// 하나씩 고치는 기능은 없다. 이 파일은 **읽기 전용 설명**만 만든다.
//
// 단 보유 급등 · 급락 두 행은 예외다(검증자 r1 R1-F1 · K1). 실행 코드가 저장된 설정값을 읽지 않고
// 프로그램에 고정된 구간으로 판정하므로, '이 값의 뜻'은 설정값이 아니라 아래 고정 경계로 만든다.

export const UNKNOWN = "확인 불가";

export type PolicyValue = { key: string; value: unknown };

export type CriteriaRow = {
  key: string;
  label: string;
  value: string;
  what: string;
  meaning: string;
};

export type CriteriaGroup = { title: string; rows: CriteriaRow[] };

// OPS-03 §2 — 정책 키를 사용자 말로 옮긴다. 내부 키 이름을 그대로 보이지 않는다.
export const POLICY_LABEL: Record<string, string> = {
  drop_threshold_pct: "보유 급락 기준",
  surge_threshold_pct: "보유 급등 기준",
  sector_entry_min_pct: "진입 검토 하한",
  sector_chase_pct: "추격 주의 기준",
  sector_avoid_drop_pct: "진입 회피 기준",
  sector_rank_top_pct: "순위 조건",
  sector_min_coverage_pct: "최소 조회 성공률",
  cooldown_minutes: "재발송 대기",
  dedup_window_minutes: "중복 억제 창",
  max_sends_per_run: "회차당 최대",
  max_sends_per_day: "하루 최대",
  max_items_per_section: "구역별 최대",
};

const PCT_KEYS = new Set([
  "drop_threshold_pct",
  "surge_threshold_pct",
  "sector_entry_min_pct",
  "sector_chase_pct",
  "sector_avoid_drop_pct",
  "sector_rank_top_pct",
  "sector_min_coverage_pct",
]);

const MIN_KEYS = new Set(["cooldown_minutes", "dedup_window_minutes"]);

// 이 둘은 **독립 조절 대상이 아니다**(설계자 OPS-03 필수 보완). 행으로 두지 않고 각주로
// 설명한다(PLAN §2-3 대조 범위). `dedup_window_minutes` 는 `cooldown_minutes` 의 호환
// 별칭이고, `max_sends_per_run` 은 회차당 본문 1개라는 구조에서 나온 고정값이다.
export const DERIVED_KEYS = new Set(["dedup_window_minutes", "max_sends_per_run"]);

export const CRITERIA_GROUPS: readonly { title: string; keys: readonly string[] }[] = [
  {
    title: "보유 종목 급등락",
    keys: ["surge_threshold_pct", "drop_threshold_pct"],
  },
  {
    title: "사업군 대표 ETF 검토",
    keys: [
      "sector_entry_min_pct",
      "sector_chase_pct",
      "sector_avoid_drop_pct",
      "sector_rank_top_pct",
    ],
  },
  {
    title: "발송 한도와 자료 조건",
    keys: [
      "cooldown_minutes",
      "max_sends_per_day",
      "max_items_per_section",
      "sector_min_coverage_pct",
    ],
  },
];

// 응답 키는 schema 12개로 고정이라 생기지 않는다. 생기면 세 묶음 뒤에 둔다(I-18).
export const OTHER_GROUP_TITLE = "그 밖의 기준";

// 제목은 판정서 글자 그대로(띄어쓰기 포함 · I-16).
export const CRITERIA_TITLE_RECORDED = "PC에 기록된 적용 기준";
export const CRITERIA_TITLE_CANDIDATE = "승인 시 적용될 기준";

// 표 위 한 줄(설계자 RESULT 판정 C5 · 2026-11-19) — 앞 두 문장은 판정 글자 그대로, 뒤 두 문장(PC 의 대표 ETF
// 선정 · 버전 단위 승인)은 같은 자리에 그대로 둔다. 보유 급등 · 급락은 설정 버전 값이 아니라 고정 경계다(K1).
export const CRITERIA_INTRO =
  "사업군 판정과 발송 조건은 설정 버전에서 확인합니다. 보유 급등·급락 판정에는 프로그램의 고정 경계를 적용합니다. PC 가 계산하는 것은 사업군 · 대표 ETF 목록(시가총액 순)입니다. 여기서 하나씩 고치지 않고 버전 전체를 승인합니다.";

export function criteriaTitle(hasCandidate: boolean): string {
  return hasCandidate ? CRITERIA_TITLE_CANDIDATE : CRITERIA_TITLE_RECORDED;
}

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function policyValueText(key: string, value: unknown): string {
  // 값이 없으면 **빠졌다는 사실을 보인다.** 0 으로 위장하지 않는다.
  const v = finite(value);
  if (v === null) return UNKNOWN;
  if (PCT_KEYS.has(key)) return `${v}%`;
  if (MIN_KEYS.has(key)) return `${v}분`;
  return `${v}건`;
}

// Python `round(x, 1)` 과 같은 자리 반올림(정확히 반에 걸리는 값만 다를 수 있음 · PLAN §7-8).
export function roundPct1(x: number): number {
  return Number(x.toFixed(1));
}

// `sector_signal._top_cut` 과 같다 — n 이 0 이면 0, 아니면 `max(1, 버림(n × 순위값 / 100))`.
export function rankCut(n: number, pct: number): number {
  if (n <= 0) return 0;
  return Math.max(1, Math.floor((n * pct) / 100));
}

// 판정에 필요한 최소 성공 수 k — '반올림 1자리(k / n × 100) ≥ 기준값' 을 만족하는 가장 작은 k(1 이상).
// 백엔드는 성공 0개를 늘 미달로 본다(`if not usable`). 만족하는 k 가 없으면 null.
export function minCoverageCount(n: number, pct: number): number | null {
  if (!Number.isInteger(n) || n <= 0) return null;
  for (let k = 1; k <= n; k += 1) {
    if (roundPct1((k / n) * 100) >= pct) return k;
  }
  return null;
}

// 등락률은 소수 첫째 자리로 반올림한 값으로 판정한다. 그래서 경계 · 예시는 0.1 단위(정수 t = 값 × 10)로 쓴다.
// 백엔드는 반올림한 등락률(t / 10 에 가장 가까운 수)과 기준값을 그대로 비교한다(`ret >= 기준` · `ret <= 기준`).
// 곱셈 오차로 한 칸 어긋나지 않게 같은 비교로 한 번 더 맞춘다.
// '≥ 기준' 을 만족하는 가장 작은 0.1 단위 값.
function tenthsAtLeast(v: number): number {
  let t = Math.ceil(v * 10);
  while ((t - 1) / 10 >= v) t -= 1;
  while (t / 10 < v) t += 1;
  return t;
}
// '≤ 기준' 을 만족하는 가장 큰 0.1 단위 값.
function tenthsAtMost(v: number): number {
  let t = Math.floor(v * 10);
  while ((t + 1) / 10 <= v) t += 1;
  while (t / 10 > v) t -= 1;
  return t;
}
function tenthText(t: number): string {
  const s = (t / 10).toFixed(1);
  return t > 0 ? `+${s}%` : `${s}%`;
}
// 설정값 표기에 오른 쪽 '+' 만 붙인다(I-19).
function signedText(v: number): string {
  return v > 0 ? `+${v}%` : `${v}%`;
}
function pctText(v: number): string {
  return `${v}%`;
}
function pctOf(k: number, n: number): string {
  return roundPct1((k / n) * 100).toFixed(1);
}
function numText(x: number): string {
  return String(Number(x.toPrecision(12)));
}
function hoursText(minutes: number): string {
  if (minutes < 60) return "";
  if (minutes % 60 === 0) return `(${minutes / 60}시간)`;
  return `(${Math.floor(minutes / 60)}시간 ${minutes % 60}분)`;
}

type Ctx = { v: (key: string) => number | null; n: number };
type Texts = { what: string; meaning: string };

const HOLDING_WHAT =
  "보유 종목의 오늘 등락률을 봅니다. 직전 거래일 종가 대비 값을 소수 첫째 자리로 반올림해서 씁니다.";
const HELD_EXCLUDED = "보유 중인 종목은 빠집니다.";
const SECTOR_SECTIONS = "그 회차의 「신규 진입 검토」와 「진입 회피」 구역을 모두 뺍니다.";

// 보유 급등 · 급락 — 프로그램에 고정된 구간 경계(검증자 r1 R1-F1 · K1).
// 실행 코드(`app/runtime_evidence/holdings_risk.py`)는 저장된 설정값(`surge_threshold_pct` ·
// `drop_threshold_pct`)을 읽지 않고 `_SURGE_BANDS`(하한 포함 · 상한 제외) · `_RISK_BANDS`(상한 포함 ·
// 하한 제외)로 판정한다. 첫 값이 후보가 되는 경계다. 공용 고정 자료
// `tests/fixtures/poc6_34_holdings_bands.json` 과 같아야 한다 — 서버 상수 ↔ 고정 자료는
// `tests/test_holdings_risk_alert.py`, 이 상수 ↔ 고정 자료는 `intradayCriteria.test.ts` 가 대조한다.
export const HOLDING_SURGE_LOWER_BOUNDS: readonly number[] = [5, 7, 10];
export const HOLDING_DROP_UPPER_BOUNDS: readonly number[] = [-5, -7, -10];

function signedNum(v: number): string {
  return v > 0 ? `+${v}` : `${v}`;
}

// '+5 ~ +7% · +7 ~ +10% · +10% 이상' — 이웃 경계끼리 잇고 마지막은 열린 구간이다.
function bandsText(bounds: readonly number[], openWord: string): string {
  const parts = bounds
    .slice(0, -1)
    .map((b, i) => `${signedNum(b)} ~ ${signedText(bounds[i + 1])}`);
  parts.push(`${signedText(bounds[bounds.length - 1])} ${openWord}`);
  return parts.join(" · ");
}

// 설정값이 고정 경계와 다르면 그 사실을 덧붙인다. 값이 없으면('확인 불가') 비교하지 않는다.
function storedDiffText(stored: number | null, edge: number): string {
  if (stored === null || stored === edge) return "";
  return (
    ` 이 설정값(${signedText(stored)})은 실제 판정 경계(${signedText(edge)})와 다릅니다` +
    ` — 판정에는 ${signedText(edge)}가 쓰입니다.`
  );
}

function surgeTexts(c: Ctx): Texts {
  const edge = HOLDING_SURGE_LOWER_BOUNDS[0];
  const b = tenthsAtLeast(edge);
  return {
    what: HOLDING_WHAT,
    meaning:
      `실행 코드는 이 설정값을 읽지 않고, 프로그램에 고정된 ${signedText(edge)} 이상` +
      `(${bandsText(HOLDING_SURGE_LOWER_BOUNDS, "이상")})으로 판정합니다. ` +
      `오늘 ${tenthText(b + 2)}인 보유 종목은 급등 후보가 됩니다` +
      `(정확히 ${tenthText(b)} 포함 · ${tenthText(b - 1)} 해당 없음).` +
      storedDiffText(c.v("surge_threshold_pct"), edge),
  };
}

function dropTexts(c: Ctx): Texts {
  const edge = HOLDING_DROP_UPPER_BOUNDS[0];
  const b = tenthsAtMost(edge);
  return {
    what: HOLDING_WHAT,
    meaning:
      `실행 코드는 이 설정값을 읽지 않고, 프로그램에 고정된 ${signedText(edge)} 이하` +
      `(${bandsText(HOLDING_DROP_UPPER_BOUNDS, "이하")})로 판정합니다. ` +
      `오늘 ${tenthText(b - 2)}인 보유 종목은 급락 후보가 됩니다` +
      `(정확히 ${tenthText(b)} 포함 · ${tenthText(b + 1)} 해당 없음).` +
      storedDiffText(c.v("drop_threshold_pct"), edge),
  };
}

function entryTexts(c: Ctx): Texts {
  const what =
    "사업군 대표 ETF의 오늘 등락률을 소수 첫째 자리로 반올림해서 봅니다. 대표를 못 읽은 사업군은 대체 ETF가 있으면 그 값을 씁니다.";
  const e = c.v("sector_entry_min_pct");
  const chase = c.v("sector_chase_pct");
  const rank = c.v("sector_rank_top_pct");
  if (e === null || chase === null || rank === null) return { what, meaning: UNKNOWN };
  const lo = tenthsAtLeast(e);
  const ex = lo + 1;
  const range = `정확히 ${tenthText(lo)}부터 ${signedText(chase)} 미만까지`;
  // 진입 검토 예시가 추격 주의 이상이면 예시 절을 빼고 범위 문장만 둔다(I-20).
  const first =
    ex >= tenthsAtLeast(chase)
      ? `오늘 등락률이 ${range}인 대표 ETF는 하한을 충족합니다.`
      : `오늘 ${tenthText(ex)}인 대표 ETF는 하한을 충족합니다(${range}).`;
  return {
    what,
    meaning:
      `${first} 「신규 진입 검토」로 알리려면 상승 순위 상위 ${pctText(rank)} 안에 들고, ` +
      `직전 거래일 종가 기준 5일 · 20일 수익률이 모두 0보다 커야 합니다. ${HELD_EXCLUDED}`,
  };
}

function chaseTexts(c: Ctx): Texts {
  const what =
    "사업군 대표 ETF의 오늘 등락률(소수 첫째 자리 반올림)이 크게 오른 경우를 가립니다.";
  const chase = c.v("sector_chase_pct");
  if (chase === null) return { what, meaning: UNKNOWN };
  const b = tenthsAtLeast(chase);
  return {
    what,
    meaning:
      `오늘 ${tenthText(b + 2)}(정확히 ${tenthText(b)} 포함)인 대표 ETF는 순위와 상관없이 ` +
      `「진입 회피」 구역의 '단기 급등 · 추격 주의' 후보가 됩니다. ` +
      `이렇게 오른 종목은 신규 진입 검토로는 알리지 않습니다. ${HELD_EXCLUDED}`,
  };
}

function avoidTexts(c: Ctx): Texts {
  const what =
    "사업군 대표 ETF의 오늘 등락률(소수 첫째 자리 반올림)이 크게 내린 경우를 가립니다.";
  const a = c.v("sector_avoid_drop_pct");
  const rank = c.v("sector_rank_top_pct");
  if (a === null || rank === null) return { what, meaning: UNKNOWN };
  const b = tenthsAtMost(a);
  const ex = tenthText(b - 1);
  return {
    what,
    meaning:
      `오늘 ${ex}(정확히 ${tenthText(b)} 포함)인 대표 ETF가 하락 순위 하위 ${pctText(rank)} 안에 들면 ` +
      `「진입 회피」 구역의 '장중 급락' 후보가 됩니다. ` +
      `${ex}라도 하위 ${pctText(rank)} 밖이면 알리지 않습니다. ${HELD_EXCLUDED}`,
  };
}

function rankTexts(c: Ctx): Texts {
  const rank = c.v("sector_rank_top_pct");
  const cov = c.v("sector_min_coverage_pct");
  if (rank === null) return { what: UNKNOWN, meaning: UNKNOWN };
  const what =
    "오늘 등락률을 읽은 사업군 대표 ETF(대표를 못 읽으면 대체 ETF)를 등락률로 줄 세운 순위를 봅니다. " +
    `많이 오른 쪽 위 ${pctText(rank)}는 신규 진입 검토에, 많이 내린 쪽 아래 ${pctText(rank)}는 장중 급락 회피에 씁니다.`;
  const n = c.n;
  const k = cov === null ? null : minCoverageCount(n, cov);
  if (cov === null || k === null) return { what, meaning: UNKNOWN };
  const cn = rankCut(n, rank);
  const prod = (n * rank) / 100;
  // 버림이 0 이면 백엔드가 최소 1개를 남긴다(`max(1, …)`).
  const cutText = Math.floor(prod) >= 1 ? "소수점을 버려" : "소수점을 버리면 0개지만 최소 1개를 남겨";
  const head =
    k === n ? `${n}개 사업군이 모두 읽혀야 순위를 매기며, ` : `${n}개 사업군이 모두 읽히면 `;
  const parts = [
    `${head}${n}×${pctText(rank)}=${numText(prod)}에서 ${cutText} 오른 쪽 ${cn}개, 내린 쪽 ${cn}개가 순위 조건을 충족합니다.`,
  ];
  if (k < n) {
    const ck = rankCut(k, rank);
    parts.push(ck === cn ? `${k}개만 읽혀도 같은 수입니다.` : `${k}개만 읽히면 ${ck}개씩입니다.`);
  }
  parts.push(
    k >= 2
      ? `${k - 1}개 이하로 읽히면 조회 성공률 ${pctText(cov)}에 못 미쳐 순위를 매기지 않습니다.`
      : "하나도 읽히지 않으면 순위를 매기지 않습니다.",
  );
  return { what, meaning: parts.join(" ") };
}

function cooldownTexts(c: Ctx): Texts {
  const what =
    "알린 종목이 조건 밖으로 벗어났다가 같은 상태로 다시 잡혔을 때, 다시 알리려면 마지막 알림부터 지나야 하는 시간입니다. " +
    "사업군 대표 ETF 신호와 보유 급등에 종목별로 적용합니다.";
  const m = c.v("cooldown_minutes");
  if (m === null) return { what, meaning: UNKNOWN };
  const t = policyValueText("cooldown_minutes", m);
  return {
    what,
    meaning:
      `마지막으로 알린 회차 시작 시각부터 ${t}${hoursText(m)} 이상 지난 회차에서 같은 상태로 다시 잡혀야 다시 보냅니다. ` +
      `${t} 안에 다시 잡혀 그대로 이어지거나, 같은 상태가 끊기지 않고 이어지면 시간이 지나도 다시 보내지 않습니다. ` +
      "상태가 바뀌면 기다리지 않고 보냅니다. 보유 급락은 이 대기 대신 같은 날 더 나쁜 구간으로 내려갈 때만 다시 알립니다.",
  };
}

function dailyTexts(c: Ctx): Texts {
  const what =
    "같은 날(한국 시각) 장중 급등락 알림 메시지를 끝까지 보낸 횟수를 셉니다. " +
    "종목 수가 아니라 메시지 수이며, 정해진 시각에 나가는 정기 알림은 세지 않습니다.";
  const d = c.v("max_sends_per_day");
  const run = c.v("max_sends_per_run");
  if (d === null || run === null) return { what, meaning: UNKNOWN };
  return {
    what,
    meaning:
      `그날 장중 급등락 알림을 ${policyValueText("max_sends_per_day", d)} 보내면 남은 장중 점검 회차에는 ` +
      "보유 급락을 포함해 아무것도 보내지 않고, 다음 날 다시 0부터 셉니다. " +
      `점검 회차 하나에서는 최대 ${policyValueText("max_sends_per_run", run)}만 보냅니다.`,
  };
}

function sectionTexts(c: Ctx): Texts {
  const what =
    "알림 메시지 한 건의 구역(보유종목 · 신규 진입 검토 · 진입 회피)마다 싣는 종목 수의 상한입니다.";
  const s = c.v("max_items_per_section");
  if (s === null) return { what, meaning: UNKNOWN };
  return {
    what,
    meaning:
      `한 구역에 조건을 충족한 종목이 ${s + 2}개여도 이번 메시지에는 ${s}개만 실리고, ` +
      `한 메시지에는 최대 ${s * 3}종목이 실립니다. 실리지 못한 2개는 보낸 것으로 기록하지 않습니다. ` +
      // POC6-35 PLAN 판정 Q8(2026-11-19) — 구역 한도에 밀린 재진입 신호도 다음 회차에 다시 검토.
      "보유 급락, 아직 알린 적 없는 신호, 마지막 알림과 상태가 다른 신호, 구역 한도에 밀린 재진입 신호는 다음 회차의 조건과 발송 한도에 따라 다시 검토합니다.",
  };
}

function coverageTexts(c: Ctx): Texts {
  // '이 표에 표시한 설정' — 후보가 있으면 후보 버전, 없으면 활성 버전이다(설계자 RESULT 판정 · 조회 성공률 문구).
  const what =
    "이 표에 표시한 설정의 사업군 가운데 오늘 시세(등락률)를 읽은 사업군의 비율을 봅니다. " +
    "대표 ETF 대신 대체 ETF로 읽은 경우도 성공으로 셉니다.";
  const cov = c.v("sector_min_coverage_pct");
  const n = c.n;
  const k = cov === null ? null : minCoverageCount(n, cov);
  if (k === null) return { what, meaning: UNKNOWN };
  const head =
    k === n
      ? `${n}개 사업군이 모두 읽혀야 사업군 판정을 하고, `
      : `${n}개 사업군 중 ${k}개 이상(${pctOf(k, n)}%)을 읽으면 사업군 판정을 하고, `;
  const tail =
    k >= 2 ? `${k - 1}개(${pctOf(k - 1, n)}%) 이하이면 ${SECTOR_SECTIONS}` : `하나도 읽지 못하면 ${SECTOR_SECTIONS}`;
  return { what, meaning: `${head}${tail} 보유 종목 급등락 알림은 그대로 판정합니다.` };
}

const TEXTS: Record<string, (c: Ctx) => Texts> = {
  surge_threshold_pct: surgeTexts,
  drop_threshold_pct: dropTexts,
  sector_entry_min_pct: entryTexts,
  sector_chase_pct: chaseTexts,
  sector_avoid_drop_pct: avoidTexts,
  sector_rank_top_pct: rankTexts,
  cooldown_minutes: cooldownTexts,
  max_sends_per_day: dailyTexts,
  max_items_per_section: sectionTexts,
  sector_min_coverage_pct: coverageTexts,
};

function rawValue(values: readonly PolicyValue[], key: string): unknown {
  return values.find((p) => p.key === key)?.value;
}

// `sectorCount` = 그 버전의 사업군 수(후보가 있으면 후보 · 없으면 활성 · I-20).
// 응답에 키가 아예 없어도 행은 그린다(값 '확인 불가') — 표는 늘 펼친다(Q6).
export function buildCriteria(
  values: readonly PolicyValue[],
  sectorCount: number,
): CriteriaGroup[] {
  const ctx: Ctx = { v: (key) => finite(rawValue(values, key)), n: sectorCount };
  const groups: CriteriaGroup[] = CRITERIA_GROUPS.map((g) => ({
    title: g.title,
    rows: g.keys.map((key) => ({
      key,
      label: POLICY_LABEL[key],
      value: policyValueText(key, rawValue(values, key)),
      ...TEXTS[key](ctx),
    })),
  }));
  const known = new Set(CRITERIA_GROUPS.flatMap((g) => g.keys));
  const other = values.filter((p) => !known.has(p.key) && !DERIVED_KEYS.has(p.key));
  if (other.length > 0) {
    groups.push({
      title: OTHER_GROUP_TITLE,
      rows: other.map((p) => ({
        key: p.key,
        label: POLICY_LABEL[p.key] ?? p.key,
        value: policyValueText(p.key, p.value),
        what: UNKNOWN,
        meaning: UNKNOWN,
      })),
    });
  }
  return groups;
}

const FOOTNOTE_TAIL =
  "위 등락률 기준은 알림 후보를 고르는 조건이며, 실제 발송에는 보유 종목 제외 · 조회 성공률 · 재발송 대기 · " +
  "구역별 최대 · 하루 최대가 함께 적용됩니다(보유 급락은 같은 날 더 나쁜 구간으로 내려갈 때만 다시 알림).";

// 표 아래 각주(I-23 · 설계자 RESULT 판정 C9 · 2026-11-19). '회차당 최대' 값이 확인되면 기존 설명 그대로(숫자는
// 같은 응답의 값)다. 값이 없으면(활성 · 후보 모두) 중복 억제 창 설명을 한 문장으로 끊고 '회차당 최대 건수는 이
// 설정에서 확인할 수 없습니다.'를 따로 쓴다 — 값 자리에 '확인 불가'를 끼워 넣지 않는다.
export function criteriaFootnote(values: readonly PolicyValue[]): string {
  const run = policyValueText("max_sends_per_run", rawValue(values, "max_sends_per_run"));
  if (run === UNKNOWN) {
    return (
      "중복 억제 창은 재발송 대기와 같은 값만 저장되는 다른 이름이라 따로 동작하지 않습니다. " +
      "회차당 최대 건수는 이 설정에서 확인할 수 없습니다. " +
      FOOTNOTE_TAIL
    );
  }
  return (
    "중복 억제 창은 재발송 대기와 같은 값만 저장되는 다른 이름이라 따로 동작하지 않고, " +
    `회차당 최대 ${run}은 한 점검 회차가 알림 메시지를 하나만 만드는 구조에서 나온 고정값입니다. ` +
    FOOTNOTE_TAIL
  );
}
