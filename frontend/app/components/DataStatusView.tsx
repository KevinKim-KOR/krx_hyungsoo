"use client";

// 「ETF NAV·괴리율 조회」 화면(data_status · POC6-34 전 이름 「데이터 상태」) — 2026-06-08 NAV / Discount Display FIX.
//
// 책임:
// - 저장된 etf_nav_daily (네이버 ETF 목록 1회 조회 결과) 의 전체 ETF NAV /
//   시장가 / 괴리율 / 기준일(asof) / 출처(source) / 수집 상태(status) 를 한 곳에서 조회.
// - 검색 (코드 / 이름) + 수집 상태 고르기 + 괴리율 기준 정렬.
// - 화면 진입 시 1회 GET /market/nav-discount/latest 호출 (외부 source 호출 X).
// - 매수/매도 판단 X — 조회 영역.
//
// 이전 정책 (2026-06-06 placeholder): "시장 데이터 / refresh 상태 들어갈 자리".
// 변경 사유: NAV / Discount Display FIX 의 전체 ETF 조회 위치를 이 화면으로 채택.
//
// POC6-33(PLAN §4 D1 ~ D6 · 판정 Q38 ~ Q45 · Q53) — 화면 글자 한국어:
// - 원값(status · source · flag)과 API 계약은 그대로 · 화면 글자는 공용 사전(lib/navLabels).
// - 사전 밖 원문은 표 아래 [자세히] 한 곳에서만(사전 밖 값이 있을 때만 · 원문 · 건수 · I-11).
// - 요약 줄의 수집됨 · 확인 불가 · 기타 건수 = 응답 items 전체를 고르기와 같은 판정 함수(statusGroup)로 센 값(I-6).
//   백엔드 summary.failed_count 는 partial 을 빼고 세므로 '기타'에 쓰지 않는다(다른 화면이 쓰는 summary 는 그대로).
// - 요약 날짜 값 = 응답 asof(행 날짜 최댓값) 그대로 · 각 행은 그 행 날짜 · 이전 목록 재사용 행은 '재저장일'(I-9).
//   그 최댓값 날짜에 이전 목록 재사용 행이 하나라도 있으면 라벨 '가장 최근 목록 날짜(재저장일 포함)',
//   아니면 '가장 최근 기준일'(RESULT 판정 §3 I-9 · 응답 items 전체로 판정 · 고르기 · 검색 · 200건 표시와 무관).
//
// POC6-34(PLAN §2-2 N1 ~ N8 · 판정 Q7 ~ Q9 · I-27 ~ I-35) — 화면 이름 · 문구만(메뉴 key `data_status` · 조회 동작 그대로):
// - h1 'ETF 순자산가치(NAV)·괴리율 조회'(첫 NAV 표기 = h1 · I-28) · 부제는 조회 범위 · 저장 자료 기준.
// - 버튼 [저장 자료 다시 읽기] = 같은 GET 다시 읽기(새로 받지 않음) · 오류 문구도 같은 이름(RELOAD_LABEL 하나 · I-29).
// - 안내 띠 = 새 자료 경로(「오늘의 투자 점검」 [최신 자료 갱신]) + 시장 갱신 성공 뒤 6시간 안에는 NAV 를 다시 받지 않음(I-30).
// - 표 위 범위 줄 '전체 A건 · 필터 결과 B건 · 표에 표시 C건'(A = 응답 items · B = 검색 + 고르기 결과 · C = 실제 그린 행 ·
//   B > 200 이면 ' (지금 정렬의 앞 200건)') · 표 아래는 B > 200 일 때 검색 · 필터 안내만(I-32 · I-33).
// - 뜻 줄 셋째 = 기준일 = PC 가 목록 갱신을 시작한 날짜 · 이전 목록 재사용 행은 '재저장일'(I-31).

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ApiConfigError,
  ApiRequestError,
  fetchNavDiscountLatest,
  type NavDiscountItem,
  type NavDiscountLatestResponse,
} from "@/lib/api";
import {
  NAV_TERM,
  discountFlagClass,
  discountFlagLabel,
  discountPctText,
  discountRateColor,
  isKnownDiscountFlag,
  isKnownNavSource,
  isKnownNavStatus,
  navDateCell,
  navDateLabel,
  navSourceLabel,
  navStatusLabel,
} from "@/lib/navLabels";

type LoadState =
  | { phase: "loading" }
  | { phase: "error"; summary: string; raw: string }
  | { phase: "ready"; data: NavDiscountLatestResponse };

type StatusGroup = "ok" | "unavailable" | "other";
type StatusFilter = "all" | StatusGroup;
type SortKey = "ticker" | "discount" | "absdiscount";
type SortOrder = "asc" | "desc";

const DASH = "-";
// 버튼 이름 — 버튼과 오류 문구가 같은 글자를 쓴다(POC6-34 N3).
const RELOAD_LABEL = "저장 자료 다시 읽기";
// 표에 그리는 행 수 상한(지금 정렬의 앞 N건).
const MAX_ROWS = 200;

// 수집 상태 고르기 · 요약 건수가 함께 쓰는 판정 하나(I-6).
// 기타 = ok · unavailable 이 아닌 값(이전 목록 재사용 partial · 사전 밖 값 포함).
function statusGroup(status: string): StatusGroup {
  if (status === "ok") return "ok";
  if (status === "unavailable") return "unavailable";
  return "other";
}

function countGroups(items: readonly NavDiscountItem[]): Record<StatusGroup, number> {
  const c: Record<StatusGroup, number> = { ok: 0, unavailable: 0, other: 0 };
  for (const it of items) c[statusGroup(it.status)] += 1;
  return c;
}

// 요약 날짜 라벨(I-9) — 값(응답 asof)은 바꾸지 않고 라벨만 고른다. 행 날짜 칸이 '재저장일'로 보이는 행
// (navDateLabel · 같은 판정)이 그 날짜에 하나라도 있으면 재저장일이 섞인 목록 날짜다. items = 응답 전체.
function summaryDateLabel(items: readonly NavDiscountItem[], asof: string | null): string {
  const reusedAtMax = !!asof && items.some((it) => it.asof === asof && navDateLabel(it.status) === "재저장일");
  return reusedAtMax ? "가장 최근 목록 날짜(재저장일 포함)" : "가장 최근 기준일";
}

type RawCount = { value: string; count: number };
type UnknownRaw = { sources: RawCount[]; statuses: RawCount[]; flags: RawCount[] };

function tally(values: string[]): RawCount[] {
  const m = new Map<string, number>();
  for (const v of values) m.set(v, (m.get(v) ?? 0) + 1);
  return [...m.entries()].map(([value, count]) => ({ value, count }));
}

// 사전 밖 원문(응답 items 전체 기준) — 표 칸은 '기타 출처' · '상태 확인 필요'로 보이고 원문은 [자세히]에만.
function unknownRawOf(items: readonly NavDiscountItem[]): UnknownRaw {
  return {
    sources: tally(items.filter((it) => it.source && !isKnownNavSource(it.source)).map((it) => it.source)),
    statuses: tally(items.filter((it) => !isKnownNavStatus(it.status)).map((it) => it.status)),
    flags: tally(
      items.filter((it) => it.flag != null && !isKnownDiscountFlag(it.flag)).map((it) => it.flag as string),
    ),
  };
}

function describeError(e: unknown): string {
  if (e instanceof ApiConfigError) return `구성 오류: ${e.message}`;
  if (e instanceof ApiRequestError) {
    return `요청 실패(HTTP ${e.httpStatus}): ${e.message}`;
  }
  return `알 수 없는 오류: ${(e as Error).message}`;
}

// 불러오기 실패의 쉬운 말(원문 = describeError → [자세히]). 시간 초과 · 연결 실패는 lib/api/core.ts 가
// 같은 HTTP 0 으로 던지므로 원문 앞머리로 나눈다(MLFeatureSanityCard 와 같은 나눔).
function plainError(e: unknown): string {
  if (e instanceof ApiConfigError) return "화면 설정 오류로 자료를 불러오지 못했습니다.";
  if (e instanceof ApiRequestError) {
    if (e.httpStatus > 0) return "서버가 오류로 답해 자료를 불러오지 못했습니다.";
    if (e.message.startsWith("요청 시간 초과")) return "서버 응답 시간이 지나 자료를 불러오지 못했습니다.";
    if (e.message.startsWith("네트워크 호출 실패")) return "서버에 연결하지 못해 자료를 불러오지 못했습니다.";
  }
  return "자료를 불러오지 못했습니다 · 원인 확인 필요.";
}

function fmtCount(n: number): string {
  return n.toLocaleString("ko-KR");
}

function fmtNumber(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return DASH;
  return Math.round(value).toLocaleString();
}

// 배지 색은 원값 기준 그대로(수집됨 · 확인 불가 · 이전 목록 재사용 · 그 밖 회색 테두리).
function statusBadgeClass(status: string): string {
  if (status === "ok") return "constituent-status-badge constituent-status-ok";
  if (status === "unavailable") {
    return "constituent-status-badge constituent-status-unavailable";
  }
  if (status === "partial") {
    return "constituent-status-badge constituent-status-timeout";
  }
  return "constituent-status-badge";
}

export default function DataStatusView() {
  const [state, setState] = useState<LoadState>({ phase: "loading" });
  const [query, setQuery] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [sortKey, setSortKey] = useState<SortKey>("absdiscount");
  const [sortOrder, setSortOrder] = useState<SortOrder>("desc");

  const load = useCallback(() => {
    setState({ phase: "loading" });
    fetchNavDiscountLatest()
      .then((data) => setState({ phase: "ready", data }))
      .catch((e) => setState({ phase: "error", summary: plainError(e), raw: describeError(e) }));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const allItems = useMemo<NavDiscountItem[]>(
    () => (state.phase === "ready" ? state.data.items : []),
    [state],
  );
  const counts = useMemo(() => countGroups(allItems), [allItems]);
  const unknownRaw = useMemo(() => unknownRawOf(allItems), [allItems]);
  const dateLabel = useMemo(
    () => summaryDateLabel(allItems, state.phase === "ready" ? state.data.asof : null),
    [allItems, state],
  );

  const filteredSorted = useMemo<NavDiscountItem[]>(() => {
    const q = query.trim().toLowerCase();
    let items = allItems;
    if (q) {
      items = items.filter(
        (it) =>
          it.ticker.toLowerCase().includes(q) ||
          (it.name ?? "").toLowerCase().includes(q),
      );
    }
    if (statusFilter !== "all") {
      items = items.filter((it) => statusGroup(it.status) === statusFilter);
    }
    const compareNumber = (a: number | null, b: number | null) => {
      const av = a ?? -Infinity;
      const bv = b ?? -Infinity;
      return av === bv ? 0 : av < bv ? -1 : 1;
    };
    const sorted = [...items].sort((a, b) => {
      let cmp = 0;
      if (sortKey === "ticker") cmp = a.ticker.localeCompare(b.ticker);
      else if (sortKey === "discount") {
        cmp = compareNumber(a.discount_rate_pct, b.discount_rate_pct);
      } else {
        const aa = a.discount_rate_pct == null ? null : Math.abs(a.discount_rate_pct);
        const bb = b.discount_rate_pct == null ? null : Math.abs(b.discount_rate_pct);
        cmp = compareNumber(aa, bb);
      }
      return sortOrder === "desc" ? -cmp : cmp;
    });
    return sorted;
  }, [allItems, query, statusFilter, sortKey, sortOrder]);

  return (
    <section aria-labelledby="data-status-h">
      <h1 id="data-status-h">ETF {NAV_TERM}·괴리율 조회</h1>
      <p className="subtitle">
        전체 ETF 의 저장 자료에서 수집 상태 · 큰 괴리를 찾아보는 조회용 표 — 저장된 자료 기준(이 화면은 새로 받지 않음).
      </p>
      <div className="role-banner" data-testid="ds-banner">
        <strong>[보조 화면 — 자료 조회]</strong> 네이버 ETF 목록을 받아 PC 에 저장한 전체 ETF 의 NAV · 시장가 ·
        괴리율을 한곳에서 검색 · 정렬합니다. 매수 · 매도 · 교체 판단 화면이 아닙니다. [{RELOAD_LABEL}]는 PC 에
        저장된 값만 다시 읽습니다(새로 받지 않음). 새 자료는 「오늘의 투자 점검」의 [최신 자료 갱신]으로 받습니다.
        마지막 시장 갱신이 성공한 뒤 6시간 안에는 [최신 자료 갱신]을 눌러도 NAV 를 다시 받지 않습니다.
      </div>

      <NavDiscountControls
        state={state}
        counts={counts}
        dateLabel={dateLabel}
        totalCount={allItems.length}
        query={query}
        statusFilter={statusFilter}
        sortKey={sortKey}
        sortOrder={sortOrder}
        onQueryChange={setQuery}
        onStatusFilterChange={setStatusFilter}
        onSortKeyChange={setSortKey}
        onSortOrderToggle={() =>
          setSortOrder((p) => (p === "desc" ? "asc" : "desc"))
        }
        onReload={load}
        filteredCount={filteredSorted.length}
      />

      {state.phase === "loading" && (
        <div className="card">
          <div className="message info">불러오는 중...</div>
        </div>
      )}

      {state.phase === "error" && (
        <div className="card">
          <div className="message error">
            {state.summary} [{RELOAD_LABEL}]로 다시 시도하세요.
          </div>
          <details className="ds-raw">
            <summary>자세히</summary>
            <div className="ds-raw-body">{state.raw}</div>
          </details>
        </div>
      )}

      {state.phase === "ready" && state.data.status === "empty" && (
        <div className="card placeholder-card">
          <h2>저장된 NAV 자료가 없습니다</h2>
          <p>
            「오늘의 투자 점검」에서 [최신 자료 갱신] 버튼을 한 번 실행하면 네이버 ETF 목록의 NAV 가
            저장됩니다.
          </p>
        </div>
      )}

      {state.phase === "ready" && state.data.status === "ok" && (
        <NavDiscountTable items={filteredSorted} totalCount={allItems.length} unknownRaw={unknownRaw} />
      )}

      {/* 2026-06-11 UI 안전실행 (지시문 §5.1) — 화면 상단에서 ML evidence
          갱신을 background 로 시작 + 단계별 상태 확인. 본 카드는 baseline 산식 /
          매수·매도 판단 0건 (§8 금지사항 준수). */}

      {/* 2026-06-08 ML Feature Sanity Check (지시문 §4.7) — ML 최소 데이터 레인
          상태 아래에 sanity 요약 표시. read-only API 호출만 (재계산 X). */}

      {/* 2026-06-11 ML Baseline v0 룩백 검증 (지시문 §12) — sanity 카드 아래에
          후보 발굴 / 위험 패턴 baseline 의 룩백 검증 결과 요약 표시. read-only. */}
    </section>
  );
}

function NavDiscountControls({
  state,
  counts,
  dateLabel,
  totalCount,
  query,
  statusFilter,
  sortKey,
  sortOrder,
  onQueryChange,
  onStatusFilterChange,
  onSortKeyChange,
  onSortOrderToggle,
  onReload,
  filteredCount,
}: {
  state: LoadState;
  counts: Record<StatusGroup, number>;
  dateLabel: string;
  totalCount: number;
  query: string;
  statusFilter: StatusFilter;
  sortKey: SortKey;
  sortOrder: SortOrder;
  onQueryChange: (v: string) => void;
  onStatusFilterChange: (v: StatusFilter) => void;
  onSortKeyChange: (v: SortKey) => void;
  onSortOrderToggle: () => void;
  onReload: () => void;
  filteredCount: number;
}) {
  const ready = state.phase === "ready";
  const asof = ready ? state.data.asof : null;
  const source = ready ? state.data.source : null;
  return (
    <div className="card">
      <h2>조회 옵션</h2>
      {ready && (
        <p className="helper" style={{ marginBottom: 8 }} data-testid="ds-summary">
          전체 {fmtCount(totalCount)}건 · {navStatusLabel("ok")} {fmtCount(counts.ok)} ·{" "}
          {navStatusLabel("unavailable")} {fmtCount(counts.unavailable)} · 기타{" "}
          <span data-testid="ds-count-other">{fmtCount(counts.other)}</span> · {dateLabel}{" "}
          {asof || DASH} · 출처 {navSourceLabel(source)} · 필터 결과{" "}
          <span data-testid="ds-count-filtered">{fmtCount(filteredCount)}</span>건
        </p>
      )}
      {/* 라벨 글자(검색 · 수집 상태 · 정렬)는 한 줄(좁아지면 '검 / 색'으로 세로 꺾이던 것 · 입력 칸은 줄바꿈으로 다음 줄) */}
      <div
        className="ds-controls"
        style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <label style={{ display: "flex", gap: 6, alignItems: "center", whiteSpace: "nowrap" }}>
          검색
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="코드 / ETF명"
            style={{ minWidth: 160 }}
          />
        </label>
        <label style={{ display: "flex", gap: 6, alignItems: "center", whiteSpace: "nowrap" }}>
          수집 상태
          <select
            value={statusFilter}
            onChange={(e) => onStatusFilterChange(e.target.value as StatusFilter)}
          >
            <option value="all">전체</option>
            <option value="ok">{navStatusLabel("ok")}</option>
            <option value="unavailable">{navStatusLabel("unavailable")}</option>
            <option value="other">기타</option>
          </select>
        </label>
        <label style={{ display: "flex", gap: 6, alignItems: "center", whiteSpace: "nowrap" }}>
          정렬
          <select
            value={sortKey}
            onChange={(e) => onSortKeyChange(e.target.value as SortKey)}
          >
            <option value="absdiscount">괴리율 절대값</option>
            <option value="discount">괴리율(부호 포함)</option>
            <option value="ticker">코드</option>
          </select>
        </label>
        <button type="button" onClick={onSortOrderToggle}>
          {sortOrder === "desc" ? "↓ 내림차순" : "↑ 오름차순"}
        </button>
        <button type="button" onClick={onReload}>
          {RELOAD_LABEL}
        </button>
      </div>
    </div>
  );
}

function rawLine(label: string, list: RawCount[]): string | null {
  if (list.length === 0) return null;
  return `${label} ${list.map((r) => `${r.value === "" ? "(빈 값)" : r.value} · ${fmtCount(r.count)}건`).join(" / ")}`;
}

// 사전 밖 원문 — 사전 밖 값이 하나라도 있을 때만 접힌 [자세히] 한 곳(I-11 ②).
function UnknownRawDetails({ raw }: { raw: UnknownRaw }) {
  const lines = [
    rawLine("출처 원문", raw.sources),
    rawLine("수집 상태 원문", raw.statuses),
    rawLine("괴리율 표시 원문", raw.flags),
  ].filter((l): l is string => l != null);
  if (lines.length === 0) return null;
  return (
    <details className="ds-raw" data-testid="ds-raw">
      <summary>자세히 — 사전에 없는 원문</summary>
      <div className="ds-raw-body">
        {lines.map((l) => (
          <div key={l}>{l}</div>
        ))}
      </div>
    </details>
  );
}

function NavDiscountTable({
  items,
  totalCount,
  unknownRaw,
}: {
  items: NavDiscountItem[];
  totalCount: number;
  unknownRaw: UnknownRaw;
}) {
  if (items.length === 0) {
    return (
      <div className="card">
        <div className="message info">필터 조건에 맞는 항목이 없습니다.</div>
        <UnknownRawDetails raw={unknownRaw} />
      </div>
    );
  }
  // 너무 많으면 지금 정렬의 앞 200건만 그린다(검색/필터 후에도 1000+ 인 경우 대비).
  const visible = items.slice(0, MAX_ROWS);
  const overLimit = items.length > MAX_ROWS;
  return (
    <div className="card market-topn-card ds-card">
      <h2>전체 ETF NAV / 괴리율</h2>
      {/* 표시 범위(POC6-34 N5 · I-32) — A = 응답 전체 · B = 검색 + 고르기 결과 · C = 실제 그린 행 */}
      <p className="helper" style={{ marginBottom: 8 }} data-testid="ds-range">
        전체 {fmtCount(totalCount)}건 · 필터 결과 {fmtCount(items.length)}건 · 표에 표시 {fmtCount(visible.length)}건
        {overLimit && ` (지금 정렬의 앞 ${fmtCount(MAX_ROWS)}건)`}
      </p>
      <div className="ds-meaning">
        <div>
          <strong>수집 상태</strong> = 그 기준일에 NAV · 시장가 · 괴리율을 받았는지
        </div>
        <div>
          <strong>괴리율 표시</strong> = 받은 값의 괴리율 절대값이 3% · 5% 이상인지(자료 확인용 · 매수 · 매도
          판단 아님) · 괴리율 양수 = 시장가가 NAV 보다 높음
        </div>
        <div>
          <strong>기준일</strong> = PC 가 목록 갱신을 시작한 날짜(원자료의 산정일은 이 화면에서 확인할 수 없음) · 이전
          목록 재사용 행은 ‘재저장일’로 표시
        </div>
      </div>
      <table className="market-topn-table">
        <thead>
          <tr>
            <th style={{ width: 90 }}>코드</th>
            <th>ETF명</th>
            <th style={{ textAlign: "right", width: 110 }}>NAV</th>
            <th style={{ textAlign: "right", width: 110 }}>시장가</th>
            <th style={{ textAlign: "right", width: 100 }}>괴리율</th>
            <th style={{ width: 140 }}>기준일</th>
            <th style={{ width: 100 }}>출처</th>
            <th style={{ width: 130 }}>수집 상태</th>
          </tr>
        </thead>
        <tbody>
          {visible.map((it) => {
            const flagLabel = discountFlagLabel(it.flag);
            return (
              <tr key={`${it.ticker}-${it.asof}-${it.source}`}>
                <td>
                  <code>{it.ticker}</code>
                </td>
                <td>{it.name ?? DASH}</td>
                <td style={{ textAlign: "right" }}>{fmtNumber(it.nav)}</td>
                <td style={{ textAlign: "right" }}>{fmtNumber(it.market_price)}</td>
                <td
                  style={{
                    textAlign: "right",
                    color: discountRateColor(it.discount_rate_pct),
                  }}
                >
                  {discountPctText(it.discount_rate_pct)}
                  {flagLabel && (
                    <>
                      {" "}
                      <span className={discountFlagClass(it.flag)}>{flagLabel}</span>
                    </>
                  )}
                </td>
                {/* '재저장일 YYYY-MM-DD' 가 날짜 중간에서 꺾이지 않게 한 줄(I-9 · 표는 자동 폭이라 열이 늘어남) */}
                <td style={{ whiteSpace: "nowrap" }}>{navDateCell(it.status, it.asof)}</td>
                <td style={{ fontSize: "0.78rem", color: "var(--muted)" }}>
                  {navSourceLabel(it.source)}
                </td>
                <td>
                  <span className={statusBadgeClass(it.status)}>{navStatusLabel(it.status)}</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <UnknownRawDetails raw={unknownRaw} />
      {overLimit && (
        <p className="helper" style={{ marginTop: 8 }} data-testid="ds-narrow-hint">
          필터 · 검색을 좁히면 앞 {fmtCount(MAX_ROWS)}건 밖의 ETF 도 표에서 볼 수 있습니다.
        </p>
      )}
    </div>
  );
}
