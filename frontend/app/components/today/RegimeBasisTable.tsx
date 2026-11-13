"use client";

// POC6-29 보완 2차 — 시장 판정 근거 · KODEX 200(아침(기준일 마감) · 당일 두 판정의 수치 · 기준일 · 상태 [?]).
// 형수님 결정(2026-11-13): 근거 접기 ① 이 아니라 「오늘 시장 변화」의 당일 판정 바로 아래에 둔다. 표 아래 '당일 판정 근거(N건) ·
//   … · 점수' 줄은 바로 위 당일 판정 상자와 같은 근거라 뺐다(같은 날 결정 · 점수 표시 · 기준은 설계자 판정 요청).
// 숫자는 응답 칸 그대로(새 계산 없음) · 출처 · 저장 시각은 상태 옆 [?] 안에만(형수님 결정 2026-11-12).
// 당일 줄(형수님 결정 2026-11-13 · 검증자 F8) = 아침 기준 응답의 today_regime — 판정 값과 저장 시점이 서버의 같은 한 번 읽기.
//   그 칸이 없으면 시장 판정 응답의 판정 · 날짜만(저장 시점 확인 필요 · 따로 받은 가격 상세로 채우지 않음).
// 설계자 RESULT 재판정 V3(2026-11-13): D1 점수 열(그 행 판정과 같은 응답의 regime_score) · 제목 옆 [?] 산식 ·
//   D2 아침 · 당일이 같은 유효 응답의 같은 마감 뒤 저장 행이면 '아침·당일 공통' 한 행 · D3 이동평균 = 가격 + 현재가와의 거리.
import type { MarketTopNResponse } from "@/lib/api";
import type { MarketContext } from "@/lib/api/marketEvidence";
import type { MorningBasisResponse } from "@/lib/api/morningBasis";
import type { QueryState } from "@/lib/api/queryCache";
import { kstMdHm, regimeBasisClose, sameStoredPrice } from "@/lib/marketNowText";
import { commonClosedRow, itemOf, scoreRuleText, scoreText, todayBasis } from "@/lib/morningText";
import { md, signedPct } from "@/lib/todayMarketLines";
import SourceHint from "./SourceHint";
import { regimeLabelKo } from "./todayHelpers";

function won(v: number | null | undefined): string {
  return v == null || !Number.isFinite(v) ? "—" : `${Math.round(v).toLocaleString("ko-KR")}원`;
}

function tone(p: number | null | undefined): string {
  if (p == null) return "";
  return p > 0 ? "tc-up" : p < 0 ? "tc-down" : "";
}

const STATE_WORD: Record<string, string> = { intraday: "장중 저장", after_close: "마감 뒤 저장", unknown: "저장 시점 확인 필요" };

interface RegimeRow {
  key: string;
  name: string;
  ctx: MarketContext | null;
  missing: string | null;
  date: string;
  state: string;
  src: string | null;
}

function RegimeCells({ ctx }: { ctx: MarketContext }) {
  const k = ctx.kodex200;
  const ok = k && k.status === "ok";
  const end = k?.return_end_date ?? ctx.asof ?? null;
  // 20 · 60거래일 시작일 — 1 · 3개월 칸이 같은 값일 때만(같은 창) 그 시작일을 적는다(추측 없음).
  const s20 = k && k.return_1m_pct === k.return_20d_pct ? k.return_1m_start_date : null;
  const s60 = k && k.return_3m_pct === k.return_60d_pct ? k.return_3m_start_date : null;
  const pos = (p: "above" | "below" | null | undefined) => (p === "above" ? "위" : p === "below" ? "아래" : "위치 확인 불가");
  // D3 — '20일선 87,415원 · 3.63% 아래'(같은 행 판정에 쓴 이동평균 · 현재가와의 거리 · 둘 다 응답 칸 그대로)
  const ma = (name: string, v: number | null | undefined, d: number | null | undefined, p: "above" | "below" | null | undefined) =>
    v == null ? `${name} 자료 없음` : `${name} ${won(v)} · ${d == null ? "거리 자료 없음" : `${Math.abs(d).toFixed(2)}% ${pos(p)}`}`;
  const streak = ctx.regime_streak;
  return (
    <>
      <td>
        {regimeLabelKo(ctx.regime_code, ctx.regime_label)}
        {streak?.streak_days != null ? ` · ${streak.streak_days}거래일째${streak.at_least ? " 이상" : ""}` : ""}
      </td>
      <td data-testid="tc-regime-score">{scoreText(ctx)}</td>
      <td className={ok ? tone(k.return_20d_pct) : ""}>
        {ok ? `${signedPct(k.return_20d_pct ?? null)}${s20 ? ` (${md(s20)} → ${md(end)})` : ""}` : "—"}
      </td>
      <td className={ok ? tone(k.return_60d_pct) : ""}>
        {ok ? `${signedPct(k.return_60d_pct ?? null)}${s60 ? ` (${md(s60)} → ${md(end)})` : ""}` : "—"}
      </td>
      <td>
        {ok
          ? `${won(k.close)} · ${ma("20일선", k.ma20, k.ma20_distance_pct, k.ma20_position)} · ${ma("60일선", k.ma60, k.ma60_distance_pct, k.ma60_position)}`
          : "KODEX 200 시계열 부족"}
      </td>
    </>
  );
}

function regimeRows(morning: QueryState<MorningBasisResponse>, market: QueryState<MarketTopNResponse>): RegimeRow[] {
  // 아침 줄은 이전 응답이어도 그대로(카드 아래 줄이 다시 읽기 실패를 알림) · 당일 줄은 todayBasis 가 이전 응답을 쓰지 않음(F10)
  const mb = morning.phase === "success" ? morning.data : null;
  const mr = mb?.morning_regime ?? null;
  const kItem = itemOf(mb, "kodex200");
  const ctx = market.phase === "success" ? (market.data.market_context ?? null) : null;
  // 아침 줄 — 저장 상태 · 출처는 아침 판정이 쓴 기준일 행(날짜 · 종가)일 때만(서버가 같은 한 번 읽기로 만든 값 · 방어).
  const mOk = mr?.status === "ok" ? mr.context : null;
  const mRow =
    kItem?.basis_row &&
    mr?.basis_date &&
    kItem.basis_row.date === mr.basis_date &&
    (!mOk || sameStoredPrice({ date: mr.basis_date, close: regimeBasisClose(mOk) }, kItem.basis_row))
      ? kItem.basis_row
      : null;
  const tb = todayBasis(morning, ctx, market.phase);
  const tRow = tb.row;
  // D2 — 같은 유효 응답의 같은 마감 뒤 저장 행이면 한 행(값 = 아침 판정 · 둘이 같은 행으로 계산됨)
  const common = commonClosedRow(morning);
  if (common && mr?.status === "ok" && mr.context) {
    return [
      {
        key: "common",
        name: `아침·당일 공통(${md(common.date)} 마감)`,
        ctx: mr.context,
        missing: null,
        date: md(common.date),
        state: STATE_WORD[common.state] ?? "",
        src: common.fetched_at_kst ? `FDR 일별 가격 · ${kstMdHm(common.fetched_at_kst)} 저장` : null,
      },
    ];
  }
  return [
    {
      key: "morning",
      name: `아침(${mr?.basis_date ? `${md(mr.basis_date)} 마감` : "기준일 확인 중"})`,
      ctx: mr?.status === "ok" ? mr.context : null,
      // 아침 기준을 못 읽으면 '불러오는 중'으로 남기지 않는다(첫 조회 실패 · 읽기 실패 응답 · 판정 칸 없음)
      missing: mr
        ? mr.status === "ok"
          ? null
          : `아침 판정 미확인 — ${mr.reason ?? "기준일 근거 확인 불가"}`
        : morning.phase === "error"
          ? "아침 요약 기준을 불러오지 못했습니다"
          : morning.phase === "success"
            ? morning.data.status !== "ok"
              ? (morning.data.message ?? "아침 요약 기준을 읽지 못했습니다")
              : "아침 판정 확인 불가"
            : "불러오는 중",
      date: mr?.basis_date ? md(mr.basis_date) : "",
      state: mRow ? (STATE_WORD[mRow.state] ?? "") : "",
      src: mRow && kItem?.received_at ? `FDR 일별 가격 · ${kstMdHm(kItem.received_at)} 저장` : null,
    },
    {
      key: "today",
      name: "당일",
      ctx: tb.ctx,
      missing: tb.ctx
        ? null
        : (tb.missing ?? "불러오는 중"), // 실패 · 판정 없음 사유는 todayBasis 한 곳(상자 · 복사와 같은 문장)
      date: tb.date ? md(tb.date) : "",
      state: tRow ? (STATE_WORD[tRow.state] ?? "") : tb.date ? STATE_WORD.unknown : "",
      src: tRow?.fetched_at_kst ? `FDR 일별 가격 · ${kstMdHm(tRow.fetched_at_kst)} 저장` : null,
    },
  ];
}

export default function RegimeBasisTable({
  market,
  morning,
}: {
  market: QueryState<MarketTopNResponse>;
  morning: QueryState<MorningBasisResponse>;
}) {
  return (
    <section className="tc-regime-basis" aria-label="시장 판정 근거" data-testid="tc-kodex-basis">
      <div className="tc-label">
        시장 판정 근거 · KODEX 200
        <SourceHint
          text={scoreRuleText(
            morning.phase === "success" ? (morning.data.score_rule ?? null) : null,
            morning.phase === "loading" || morning.phase === "idle",
          )}
          testId="tc-score-rule"
          label="점수 산식 보기"
          align="left"
        />
      </div>
      <div className="ec-table-wrap">
        <table className="ec-table tc-ev-table">
          <thead>
            <tr>
              <th scope="col">판정</th>
              <th scope="col">국면</th>
              <th scope="col">점수</th>
              <th scope="col">20거래일</th>
              <th scope="col">60거래일</th>
              <th scope="col">가격 · 이동평균</th>
              <th scope="col">기준일 · 상태</th>
            </tr>
          </thead>
          <tbody>
            {regimeRows(morning, market).map((r) => (
              <tr key={r.key} data-testid={`tc-regime-${r.key}`}>
                <th scope="row">{r.name}</th>
                {r.ctx ? (
                  <RegimeCells ctx={r.ctx} />
                ) : (
                  <>
                    <td>{r.missing}</td>
                    {/* D1 — 점수를 확인하지 못한 행은 '확인 불가' */}
                    <td data-testid="tc-regime-score">확인 불가</td>
                    <td colSpan={3}>—</td>
                  </>
                )}
                <td>
                  {r.date} <span className="tc-muted tc-small">{r.state}</span>
                  <SourceHint text={r.src} testId={`tc-src-regime-${r.key}`} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
