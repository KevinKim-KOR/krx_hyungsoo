"use client";

// POC6-32 V2(PLAN §3-2 D2 · D3 · D4 · §9 I-6 · I-19 · I-21 · 목업 ③ [비교 상세]) — 「보유와 후보 비교」 '상품 확인' 표와
// 지수 상태 한 줄. 화면은 서로 다른 두 종목을 모두 골랐을 때만 이 칸을 고르기 칸 아래 · 기본 비교 위에 둔다.
// - 칸마다 공식 기초지수 · 지수산출기관 · 투자 대상(기초시장분류 · 기초자산분류) · 상품 구조(추적배수 · 복제방법 · 총보수) ·
//   과세유형 · 공식 기준정보 파일(KRX ETF 기본정보 CSV 파일 날짜). 값은 서버가 준 CSV 글자 그대로다(총보수만 소수 끝의 0 을
//   지우고 % 를 붙임 — '0.450000' → '0.45%').
// - 개별 주식 = '개별 주식 · 기초지수 해당 없음' · 공식 기준정보에 없거나 파일을 못 읽음 = 서버 사유 + ' — 확인 불가'(I-21).
// - 지수 상태 = 서버 판정(같은 공식 기초지수 · 다른 지수 · 같은 계열 · 기준 미확인)과 서버 사유. 화면은 다시 판정하지 않는다.
//   같은 공식 기초지수에서 구조가 다르면 '구조 다름: …'(확인된 값 · 보유 ↔ 후보) 글을 만들어 기본 비교 차이 줄 위에 둔다.
//   한쪽이라도 값이 빈 구조 칸은 '구조 다름'에 넣지 않고 '확인 안 된 구조 항목: 총보수(보유 쪽)'로 따로 적는다(r1 F2 ·
//   서버 `structure_unconfirmed` · 차이 줄은 그대로 씀).
// 읽기 전용 · 새 점수 · 등급 없음.

import { useSharedQuery, type QueryState } from "@/lib/api/queryCache";
import {
  etfOfficialKey,
  fetchEtfOfficial,
  type EtfOfficialResponse,
  type OfficialCsv,
  type OfficialItem,
  type OfficialPairState,
  type OfficialStructureDiff,
  type OfficialStructureUnconfirmed,
} from "@/lib/api/etfOfficial";

// 고른 두 종목이 없으면(한쪽만 · 같은 종목) 조회하지 않는다(phase = idle).
export function useEtfOfficial(tickers: readonly string[]): QueryState<EtfOfficialResponse> & { reload: () => void } {
  return useSharedQuery<EtfOfficialResponse>(etfOfficialKey(tickers), () => fetchEtfOfficial(tickers), {
    lazy: tickers.length === 0,
  });
}

const STATE_LABEL: Record<OfficialPairState, string> = {
  same: "같은 공식 기초지수",
  same_family: "다른 지수 · 같은 계열",
  different: "다른 지수",
  unconfirmed: "기준 미확인",
};

const CHIP: Record<OfficialPairState, string> = {
  same: "tc-sum-ok",
  same_family: "tc-sum-bad",
  different: "tc-sum-bad",
  unconfirmed: "tc-sum-muted",
};

function isPairState(v: unknown): v is OfficialPairState {
  return typeof v === "string" && Object.prototype.hasOwnProperty.call(STATE_LABEL, v);
}

// 지수 상태(차이 줄 조건) — 읽는 중이면 pending(차이를 아직 적지 않음) · 못 읽음 · 응답에 상태 없음 = 기준 미확인.
export type IndexGate =
  | { phase: "pending"; text: string }
  | { phase: "ready"; state: OfficialPairState; label: string; reason: string; structure: string | null };

export function indexGateOf(q: QueryState<EtfOfficialResponse>): IndexGate {
  if (q.phase === "idle" || q.phase === "loading") {
    return { phase: "pending", text: "공식 기준정보를 읽는 중이라 차이는 아직 적지 않습니다" };
  }
  const unconfirmed = (reason: string): IndexGate => ({
    phase: "ready",
    state: "unconfirmed",
    label: STATE_LABEL.unconfirmed,
    reason,
    structure: null,
  });
  if (q.phase === "error") return unconfirmed("공식 기준정보를 읽지 못함");
  const p = q.data.pair;
  if (!p || !isPairState(p.state)) return unconfirmed("공식 기준정보 응답에 두 상품의 지수 상태가 없음");
  return {
    phase: "ready",
    state: p.state,
    label: STATE_LABEL[p.state],
    reason: p.reason ?? "",
    structure: p.state === "same" ? structureText(p.structure_diffs ?? [], p.structure_unconfirmed ?? []) : null,
  };
}

// 총보수(CSV 글자) → 화면 표기. 숫자 글자면 소수 끝의 0 만 지워 % 를 붙인다(값은 바꾸지 않음) · 그 밖은 글자 그대로.
export function feeText(v: string | null | undefined): string | null {
  const s = (v ?? "").trim();
  if (!s) return null;
  if (!/^\d+(\.\d+)?$/.test(s)) return s;
  return `${s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s}%`;
}

function structureValue(d: OfficialStructureDiff, v: string | null): string {
  return (d.field === "총보수" ? feeText(v) : v?.trim() || null) ?? "—";
}

const SIDE_TEXT: Record<OfficialStructureUnconfirmed["side"], string> = {
  a: "보유 쪽",
  b: "후보 쪽",
  both: "두 쪽 모두",
};

// '구조 다름: 추적배수 일반 ↔ 2X 레버리지 · 총보수 0.15% ↔ 0.45%(보유 ↔ 후보)' + 빈 칸이 있으면
// ' / 확인 안 된 구조 항목: 총보수(보유 쪽)'(차이 문장과 따로) · 둘 다 없으면 null.
export function structureText(
  diffs: readonly OfficialStructureDiff[],
  unconfirmed: readonly OfficialStructureUnconfirmed[] = [],
): string | null {
  const out: string[] = [];
  if (diffs.length > 0) {
    const parts = diffs.map((d) => `${d.field} ${structureValue(d, d.a)} ↔ ${structureValue(d, d.b)}`);
    out.push(`구조 다름: ${parts.join(" · ")}(보유 ↔ 후보)`);
  }
  if (unconfirmed.length > 0) {
    const parts = unconfirmed.map((u) => `${u.field}(${SIDE_TEXT[u.side] ?? "어느 쪽인지 모름"})`);
    out.push(`확인 안 된 구조 항목: ${parts.join(" · ")}`);
  }
  return out.length > 0 ? out.join(" / ") : null;
}

type RowKey = "index" | "provider" | "target" | "structure" | "tax" | "file";

const ROWS: [RowKey, string][] = [
  ["index", "공식 기초지수"],
  ["provider", "지수산출기관"],
  ["target", "투자 대상"],
  ["structure", "상품 구조"],
  ["tax", "과세유형"],
  ["file", "공식 기준정보 파일"],
];

const DASH = "—";

function joined(parts: (string | null | undefined)[]): string {
  const xs = parts.map((p) => (p ?? "").trim()).filter((p) => !!p);
  return xs.length > 0 ? xs.join(" · ") : DASH;
}

// 한 종목의 표 칸 글(공식 기준정보가 없으면 첫 칸에 사유 · 나머지는 —).
export function productCells(it: OfficialItem | undefined, csv: OfficialCsv): Record<RowKey, string> {
  const fileOk = csv.ok ? (csv.asof ? `KRX ${csv.asof} 파일` : "KRX 파일(날짜 확인 불가)") : "파일을 읽지 못함";
  const empty = { provider: DASH, target: DASH, structure: DASH, tax: DASH };
  if (!it) return { index: "공식 기준정보 응답에 없음 — 확인 불가", ...empty, file: fileOk };
  if (!it.found) {
    if (it.kind === "stock") return { index: it.missing_reason ?? "개별 주식 · 기초지수 해당 없음", ...empty, file: "해당 없음" };
    return {
      index: `${it.missing_reason ?? "공식 기준정보에 없음"} — 확인 불가`,
      ...empty,
      file: csv.ok ? `${fileOk}에 없음` : fileOk,
    };
  }
  const fee = feeText(it.fee_pct);
  return {
    index: it.index_name?.trim() || DASH,
    provider: it.index_provider?.trim() || DASH,
    target: joined([it.market, it.asset]),
    structure: joined([it.multiple, it.replication, fee ? `총보수 ${fee}` : null]),
    tax: it.tax?.trim() || DASH,
    file: fileOk,
  };
}

export interface ProductSide {
  ticker: string;
  name: string;
}

export default function ProductCheckTable({
  q,
  gate,
  hold,
  cand,
}: {
  q: QueryState<EtfOfficialResponse>;
  gate: IndexGate;
  hold: ProductSide;
  cand: ProductSide;
}) {
  return (
    <section className="tc-card hcc-product" aria-labelledby="hcc-product-h" data-testid="hcc-product">
      <h2 id="hcc-product-h" className="hcc-h2">
        상품 확인 — 공식 기초지수 · 투자 대상 · 상품 구조
      </h2>
      {q.phase === "success" ? (
        <ProductRows data={q.data} hold={hold} cand={cand} />
      ) : q.phase === "error" ? (
        <p className="wb-warn" data-testid="hcc-product-error">
          공식 기준정보를 읽지 못했습니다 — [다시 불러오기]로 다시 시도하세요.
        </p>
      ) : (
        <div className="ec-small">공식 기준정보 확인 중...</div>
      )}
      {q.phase === "success" && q.stale ? (
        <p className="wb-warn" data-testid="hcc-product-stale">
          공식 기준정보를 다시 읽지 못해 이전에 읽은 값을 보입니다.
        </p>
      ) : null}
      {gate.phase === "ready" ? (
        <div className="hcc-state-line" data-testid="hcc-index-state">
          <span className={`tc-sum-badge ${CHIP[gate.state]}`} data-testid="hcc-index-chip">
            {gate.label}
          </span>
          <span data-testid="hcc-index-reason">
            {gate.reason ? `${gate.reason} — ` : ""}
            {gate.state === "same"
              ? "기간 · 가격 상태가 맞는 줄만 아래 기본 비교에 차이(해당 기간 가격 성과)를 적습니다"
              : "수익률 차이 요약을 쓰지 않고 각 ETF 값만 보입니다"}
          </span>
        </div>
      ) : null}
    </section>
  );
}

function ProductRows({ data, hold, cand }: { data: EtfOfficialResponse; hold: ProductSide; cand: ProductSide }) {
  const csv: OfficialCsv = data.csv ?? { name: null, asof: null, ok: false, error: null };
  const items = data.items ?? {};
  const hc = productCells(items[hold.ticker], csv);
  const cc = productCells(items[cand.ticker], csv);
  return (
    <>
      <div className="ec-table-wrap">
        <table className="ec-table hcc-table" data-testid="hcc-product-table">
          <colgroup>
            <col className="hcc-col-k" />
            <col />
            <col />
          </colgroup>
          <thead>
            <tr>
              <th scope="col">항목</th>
              <th scope="col" data-testid="hcc-p-head-holding">
                보유 · {hold.name}
              </th>
              <th scope="col" data-testid="hcc-p-head-candidate">
                후보 · {cand.name}
              </th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map(([k, label]) => (
              <tr key={k}>
                <th scope="row">{label}</th>
                <td data-testid={`hcc-p-${k}-holding`}>{hc[k]}</td>
                <td data-testid={`hcc-p-${k}-candidate`}>{cc[k]}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="ec-small">
        공식 기준정보 = KRX ETF 기본정보 파일(파일 날짜 기준 · 그 뒤 바뀐 상품 정보는 확인 불가) · 공식 기준정보에 없거나
        개별 주식이면 지수 상태는 &apos;기준 미확인&apos;입니다.
      </div>
    </>
  );
}
