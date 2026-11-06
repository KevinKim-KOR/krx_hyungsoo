"use client";

// POC6-24 — 「보유 현황」 자금 기준 카드(보유 배너 바로 아래 · 목업 A · B · C 배치).
//
// - 보기: 검토에 포함할 현금 · 이번 검토의 추가 투입 한도 · 확인일 · 보유 + 입력 현금 합계 · 보유 / 현금 구성.
//   숫자는 모두 서버 `/holdings/enriched` 의 capital 칸(서버 저장값으로 계산)을 그대로 쓴다.
// - 편집: 세 칸 · [저장] [취소] [비우기]. 편집 중 값은 저장에 성공하기 전까지 합계 · 비중 · AI 근거에 쓰지 않는다.
//   저장 실패 = 입력값 유지 + 사유 · 저장된 값은 그대로.
// - 미입력 · 0원 · 미정 · 계산 안 함 · 확인 불가는 서로 다른 글로 보인다(0원으로 바꾸지 않음).

import { useState } from "react";
import {
  ApiRequestError,
  saveCapitalContext,
  type CapitalPayload,
  type CapitalView,
} from "@/lib/api";
import { fmtMoney, fmtPct } from "@/lib/holdings_view";

const DASH = "—";

export function kstToday(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

// fmtMoney(null) 은 '0원'(toFiniteNumber(null) = 0) — 값 없음은 먼저 거른다.
function won(v: number | null): string {
  return v === null ? DASH : (fmtMoney(v) ?? DASH);
}

function priceDateText(cv: CapitalView): string {
  const pd = cv.price_date;
  if (pd.state === "NO_HOLDINGS") return "가격 기준일 대상 없음";
  if (pd.state === "NONE_PRICED") return "시세 확인된 보유 없음";
  if (pd.state === "UNKNOWN") return "가격 기준일 확인 불가";
  return pd.min === pd.max ? `${pd.min}` : `${pd.min} ~ ${pd.max}`;
}

// 입력 칸 글 → 원 단위 정수(빈칸 = null). 쉼표 · 공백만 허용.
export function parseWon(text: string): { ok: true; value: number | null } | { ok: false; reason: string } {
  const t = text.replace(/[,\s]/g, "");
  if (t === "") return { ok: true, value: null };
  if (!/^\d+$/.test(t)) return { ok: false, reason: "원 단위 숫자(정수)만 입력하세요." };
  const n = Number(t);
  if (!Number.isSafeInteger(n)) return { ok: false, reason: "금액이 너무 큽니다." };
  return { ok: true, value: n };
}

function errorDetail(e: unknown): string {
  if (e instanceof ApiRequestError) {
    const b = e.body as unknown;
    if (b && typeof b === "object" && "detail" in b) {
      const d = (b as { detail: unknown }).detail;
      if (typeof d === "string") return d;
      return "입력 형식이 올바르지 않습니다.";
    }
    return `요청 실패(HTTP ${e.httpStatus})`;
  }
  return "서버에 연결하지 못했습니다.";
}

// 서버 손상 거절 문구 머리(app/api_holdings.py :: put_capital_context 의 500 detail 과 같은 글).
const CORRUPT_DETAIL_HEAD = "자금 기준 파일 손상";

// 검증자 r1 F1 — 서버가 '쓰기 전에 거절'했다고 확정되는 실패만 '저장된 값은 바뀌지 않았습니다'로 안내한다.
//   422 = 입력 오류(검증 뒤 쓰기 전 거절) · 500 + 손상 문구 = 손상 파일을 덮어쓰지 않고 거절.
//   그 밖(연결 끊김 · 시간 초과 · 예상 밖 서버 오류)은 요청을 보낸 뒤 결과를 모르는 것 — 이미 저장됐을 수 있다.
export function refusedBeforeWrite(e: unknown): boolean {
  if (!(e instanceof ApiRequestError)) return false;
  if (e.httpStatus === 422) return true;
  const b = e.body as unknown;
  const d = b && typeof b === "object" && "detail" in b ? (b as { detail: unknown }).detail : null;
  return e.httpStatus === 500 && typeof d === "string" && d.startsWith(CORRUPT_DETAIL_HEAD);
}

function unknownReason(e: unknown): string {
  if (e instanceof ApiRequestError && e.httpStatus > 0) return `서버 오류 HTTP ${e.httpStatus}`;
  return "서버 응답을 받지 못함";
}

interface Props {
  // null = 보유 응답(/holdings/enriched) 자체를 불러오지 못함 · READ_FAILED = 자금 기준 파일만 읽지 못함
  capital: CapitalView | null;
  onSaved: () => void | Promise<void>;
}

export default function CapitalContextPanel({ capital, onSaved }: Props) {
  const [editing, setEditing] = useState(false);
  const [cashText, setCashText] = useState("");
  const [limitText, setLimitText] = useState("");
  const [dayText, setDayText] = useState("");
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (capital === null || capital.status === "READ_FAILED") {
    return (
      <div className="cap-card" data-testid="capital-panel">
        <div className="cap-head">
          <div className="cap-title">
            자금 기준<span className="cap-tag">확인 불가</span>
          </div>
          <button type="button" className="btn-md" disabled>
            입력·수정
          </button>
        </div>
        {capital === null ? (
          <div className="cap-err">
            보유 현황을 불러오지 못해 자금 기준도 확인할 수 없습니다 — 0원으로 보지 않습니다(위 오류 문구 참고 ·
            새로 고침하면 다시 읽음).
          </div>
        ) : (
          <div className="cap-err">
            자금 기준을 불러오지 못했습니다 — 0원으로 보지 않습니다. 보유 조회 · 판단 근거 미리보기는 그대로 쓸 수
            있습니다(새로 고침하면 다시 읽음).
          </div>
        )}
      </div>
    );
  }

  const cv = capital;
  const entered = cv.status === "ENTERED";

  const startEdit = () => {
    setCashText(cv.cash_krw === null ? "" : cv.cash_krw.toLocaleString("ko-KR"));
    setLimitText(cv.limit_krw === null ? "" : cv.limit_krw.toLocaleString("ko-KR"));
    setDayText(cv.confirmed_on ?? kstToday()); // 첫 입력의 기본값 = 오늘(KST)
    setErr(null);
    setEditing(true);
  };

  // 서버 저장값 다시 읽기(부모 = /holdings/enriched 재조회 · 그 실패는 부모가 화면에 적는다).
  const reload = async () => {
    try {
      await onSaved();
    } catch {
      // 부모(HoldingsView.loadEnriched)가 오류를 표시한다 — 여기서 저장 실패로 바꾸지 않음
    }
  };

  const submit = async (payload: CapitalPayload) => {
    setSaving(true);
    setErr(null);
    let outcome: "saved" | "refused" | "unknown" = "unknown";
    try {
      await saveCapitalContext(payload);
      outcome = "saved";
    } catch (e) {
      if (refusedBeforeWrite(e)) {
        outcome = "refused";
        setErr(
          `저장하지 못했습니다 — ${errorDetail(e)} 입력한 값은 그대로 두었고, 저장된 값은 바뀌지 않았습니다.`,
        );
      } else {
        setErr(
          `저장 결과를 확인하지 못했습니다(${unknownReason(e)}) — 서버에 이미 저장됐을 수도 있어 저장된 값을 다시 ` +
            "읽습니다(아래 '지금 저장된 값'). 입력한 값은 그대로 두었습니다. 같은 값으로 다시 [저장]해도 됩니다" +
            "(세 칸을 한 묶음으로 바꿈).",
        );
      }
    }
    if (outcome === "saved") setEditing(false);
    // 저장 성공 · 결과 모름 = 서버 값을 다시 읽어 화면을 맞춘다(결과 모름을 '바뀌지 않음'으로 단정하지 않음).
    if (outcome !== "refused") await reload();
    setSaving(false);
  };

  const onSave = () => {
    const c = parseWon(cashText);
    if (!c.ok) {
      setErr(`저장하지 못했습니다 — 검토에 포함할 현금: ${c.reason} 입력한 값은 그대로 두었습니다.`);
      return;
    }
    const a = parseWon(limitText);
    if (!a.ok) {
      setErr(`저장하지 못했습니다 — 추가 투입 한도: ${a.reason} 입력한 값은 그대로 두었습니다.`);
      return;
    }
    if (c.value === null && a.value === null) {
      setErr("현금과 한도가 모두 비어 있습니다 — 모두 지우려면 [비우기]를 누르세요.");
      return;
    }
    void submit({ cash_krw: c.value, limit_krw: a.value, confirmed_on: dayText || null });
  };

  if (editing) {
    return (
      <div className="cap-card" data-testid="capital-panel">
        <div className="cap-head">
          <div className="cap-title">
            자금 기준 입력 · 수정
            <span className="cap-tag edit">편집 중 — 저장 전 값은 합계 · 비중 · AI 근거에 쓰지 않음</span>
          </div>
        </div>
        <div className="btn-row cap-actions">
          <button type="button" onClick={onSave} disabled={saving}>
            {saving ? "저장 중..." : "저장"}
          </button>
          <button
            type="button"
            className="reject"
            onClick={() => {
              setEditing(false);
              setErr(null);
            }}
            disabled={saving}
          >
            취소
          </button>
          <button
            type="button"
            className="reject"
            onClick={() => void submit({ cash_krw: null, limit_krw: null, confirmed_on: null })}
            disabled={saving}
          >
            비우기
          </button>
        </div>
        <div className="cap-form">
          <label className="lbl" htmlFor="cap-cash">
            검토에 포함할 현금(원)
          </label>
          <label className="lbl" htmlFor="cap-limit">
            이번 검토의 추가 투입 한도(원)
          </label>
          <label className="lbl" htmlFor="cap-day">
            현금 · 한도 확인일
          </label>
          <input
            id="cap-cash"
            inputMode="numeric"
            value={cashText}
            onChange={(e) => setCashText(e.target.value)}
          />
          <input
            id="cap-limit"
            inputMode="numeric"
            value={limitText}
            onChange={(e) => setLimitText(e.target.value)}
          />
          <input
            id="cap-day"
            type="date"
            max={kstToday()}
            value={dayText}
            onChange={(e) => setDayText(e.target.value)}
          />
          <div className="hint">예수금과 따로 둔 현금 중 이 보유와 함께 볼 금액 · 비우면 미입력 · 0원은 0원</div>
          <div className="hint">현금 중 이번에 더 살 수 있는 최대 금액 · 비우면 미정 · 현금보다 클 수 없음</div>
          <div className="hint">기본 오늘 · 지난 날짜 가능 · 미래 날짜 불가</div>
        </div>
        {err ? (
          <div className="cap-err" role="alert">
            {err}
          </div>
        ) : null}
        <div className="cap-note">
          지금 저장된 값:{" "}
          {entered
            ? `현금 ${won(cv.cash_krw)} · 한도 ${cv.limit_krw === null ? "미정" : won(cv.limit_krw)} · 확인일 ${cv.confirmed_on}`
            : "미입력"}{" "}
          · [비우기] = 세 칸 모두 미입력으로 저장(0원 아님)
        </div>
      </div>
    );
  }

  const shares = cv.holdings_share_pct !== null && cv.cash_share_pct !== null;
  const dateText = priceDateText(cv);
  const valueSub =
    cv.holdings_rows === 0
      ? "보유 없음 · 가격 기준일 대상 없음"
      : cv.complete
        ? `${dateText} · ${cv.priced_rows}/${cv.holdings_rows}종목`
        : `부분 합계 · ${cv.priced_rows}/${cv.holdings_rows}종목 · ${dateText}`;

  return (
    <div className="cap-card" data-testid="capital-panel">
      <div className="cap-head">
        <div className="cap-title">
          자금 기준
          <span className="cap-tag">{entered ? `직접 입력 · 확인일 ${cv.confirmed_on}` : "아직 입력하지 않음"}</span>
        </div>
        <button type="button" className="btn-md" onClick={startEdit}>
          {entered ? "입력·수정" : "입력"}
        </button>
      </div>

      {cv.total_krw !== null ? (
        <>
          <div className="cap-conc">
            보유 + 입력 현금 합계 <b>{won(cv.total_krw)}</b>
            <span className="split">
              {shares
                ? `보유 ${fmtPct(cv.holdings_share_pct)} · 현금 ${fmtPct(cv.cash_share_pct)}`
                : "보유 · 현금 구성 계산 불가(합계 0원)"}
            </span>
          </div>
          {shares ? (
            <>
              <div className="cap-bar" aria-hidden="true">
                <div className="h" style={{ width: `${cv.holdings_share_pct}%` }} />
                <div className="c" style={{ width: `${cv.cash_share_pct}%` }} />
              </div>
              <div className="cap-legend">
                <span>
                  <span className="sw h" />
                  보유 평가액 {fmtPct(cv.holdings_share_pct)}
                </span>
                <span>
                  <span className="sw c" />
                  입력 현금 {fmtPct(cv.cash_share_pct)}
                </span>
              </div>
            </>
          ) : null}
        </>
      ) : cv.total_reason === "PARTIAL" ? (
        <div className="cap-conc none">
          보유 {cv.priced_rows}/{cv.holdings_rows}종목만 시세 확인 — 합계 · 보유/현금 구성 · &lsquo;입력 현금 포함&rsquo;
          비중은 계산하지 않습니다(부분 합계를 전체처럼 보이지 않게). 종목 행의 &lsquo;보유 내 비중&rsquo;은 시세
          확인된 종목 평가액 기준입니다.
        </div>
      ) : (
        <div className="cap-conc none">
          현금 미입력 — 보유 + 입력 현금 합계와 &lsquo;입력 현금 포함&rsquo; 비중은 현금을 입력하면 계산합니다.
        </div>
      )}

      <div className="cap-grid">
        <div>
          <div className="k">검토에 포함할 현금</div>
          {cv.cash_krw === null ? (
            <div className="v na">미입력</div>
          ) : (
            <>
              <div className="v">{won(cv.cash_krw)}</div>
              {cv.cash_krw === 0 ? <div className="s">직접 입력한 0원</div> : null}
            </>
          )}
        </div>
        <div>
          <div className="k">이번 검토의 추가 투입 한도</div>
          {!entered ? (
            <div className="v na">미입력</div>
          ) : cv.limit_krw === null ? (
            <>
              <div className="v na">미정</div>
              <div className="s">현금 전액을 한도로 보지 않음</div>
            </>
          ) : (
            <>
              <div className="v">{won(cv.limit_krw)}</div>
              <div className="s">합계에 더하지 않음</div>
            </>
          )}
        </div>
        <div>
          <div className="k">현금 · 한도 확인일</div>
          <div className={cv.confirmed_on ? "v" : "v na"}>{cv.confirmed_on ?? DASH}</div>
        </div>
        <div>
          <div className="k">보유 평가액 · 가격 기준일</div>
          <div className={cv.price_date.state === "NONE_PRICED" ? "v na" : "v"}>
            {cv.price_date.state === "NONE_PRICED" ? "계산 불가" : won(cv.holdings_value)}
          </div>
          <div className="s">{valueSub}</div>
        </div>
      </div>

      {cv.total_krw !== null && cv.same_day === false ? (
        <div className="cap-warn">
          가격 기준일({dateText})과 현금 확인일({cv.confirmed_on})이 달라 <b>기준일이 다른 참고 합계 · 비중</b>입니다(종목
          행의 &lsquo;입력 현금 포함&rsquo; 비중 포함).
        </div>
      ) : cv.total_krw !== null && cv.price_date.state === "UNKNOWN" ? (
        <div className="cap-warn">
          가격 기준일을 확인하지 못해 같은 기준일의 합계 · 비중으로 보지 않습니다(종목 행의 &lsquo;입력 현금 포함&rsquo;
          비중 포함).
        </div>
      ) : null}
      {entered ? (
        <div className="cap-note">
          직접 입력한 확인일 기준 값 · 거래 · 입출금 뒤 자동으로 바뀌지 않습니다 · 합계는 이 보유 목록과 입력 현금의
          평가 합계이며 투자 총예산 · 전체 재산이 아닙니다.
        </div>
      ) : null}
      {cv.holdings_rows > 0 ? (
        <div className="cap-note">
          종목 행의 비중은 계좌 행마다 따로 계산합니다(같은 종목이 여러 계좌에 있으면 행마다 나옴) · 판단 근거
          미리보기의 종목 비중은 같은 종목의 모든 계좌 합산입니다.
        </div>
      ) : null}
      <details className="cap-help">
        <summary>자세히</summary>
        생활비 · 비상금은 넣지 않아도 됩니다. &lsquo;총 매입금액&rsquo;은 지금 보유분의 취득금액이며 넣은 원금이
        아닙니다. 매매 · 입출금 뒤에는 다음 검토 때 직접 고쳐 주세요(날짜도 자동으로 바뀌지 않음). 저장한 값은 이
        PC 에만 두며 「보유 OCI 반영」으로 보내지 않습니다. 판단 근거 미리보기에는 생성할 때의 저장값이 들어가고,
        값을 고친 뒤에는 [다시 생성]해야 바뀝니다.
      </details>
    </div>
  );
}
