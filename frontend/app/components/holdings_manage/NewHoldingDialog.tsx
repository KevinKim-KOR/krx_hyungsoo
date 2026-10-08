"use client";

// POC5-05 개정 2 — 새 보유 추가(최초 매수 · 잔고 등록) · 과거 보유의 재매수 창.
// 설계 §2 · §4 · §11-3 · PLAN §2-8 · 사용자 확인 목업:
//   - 최초 매수 = 실제 거래일 · 체결단가로 BUY(action new_position).
//   - 잔고 등록 = 거래를 모르는 기존 잔고(매수일 미상 · 입력 평단 기준 · action register).
//   - 재매수 = 선택한 과거 보유 줄(position_id)의 새 보유 기간 · 종목 · 계좌 고정 · 최초 매수만.
//   - 같은 (종목코드, 계좌)의 과거 보유가 있으면 안내 + History 연결. 여러 줄이면 임의로
//     잇지 않고 과거 보유에서 고르게 한다(서버도 409).
//   record_id 규칙 · 409 문구는 매매 입력 창과 같다(useTradeSave).
//   계좌는 목록에서만 고른다(POC3-08 (D) 자유입력 차단 유지 · 목록 = 추천값 + 현재 · 과거 보유의 계좌).

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import {
  fetchEtfName,
  type HoldingCycleView,
  type PositionHistory,
  type TradeCommandResult,
} from "@/lib/api";
import { DEFAULT_GROUP } from "@/lib/holdings_view";
import Dialog from "./Dialog";
import { fmtNum, fmtSignedMoney, parseInput, toDecimalText, todayKst } from "./format";
import { useTradeSave, type SaveCommand } from "./TradeDialog";

const TICKER_RE = /^[0-9A-Z]{6}$/;
const ACCOUNT_MAX = 30;

export interface RebuyTarget {
  position_id: string;
  ticker: string;
  name: string | null;
  account_group: string;
}

interface Props {
  revision: number;
  rebuy?: RebuyTarget | null;
  pastPositions: PositionHistory[];
  accountOptions: string[];
  onClose: () => void;
  onSaved: (result: TradeCommandResult) => void;
  onOpenHistory: (positionId: string) => void;
}

type Lookup = {
  ticker: string;
  status: "loading" | "found" | "missing" | "error";
  name: string | null;
};

function nameText(rebuy: RebuyTarget | null, lookup: Lookup | null, ticker: string): string {
  if (rebuy?.name) return rebuy.name;
  if (!lookup || lookup.ticker !== ticker) return "—";
  if (lookup.status === "loading") return "조회 중…";
  if (lookup.status === "found" && lookup.name) return lookup.name;
  if (lookup.status === "error") return "(종목명 조회 실패)";
  return "(ETF 목록에 없음 — 개별주일 수 있음)";
}

// 맞는 과거 보유의 종료 기간 수 · 가장 최근 종료 기간(안내 문구용).
function pastSummary(matched: PositionHistory[]): {
  closedCount: number;
  latest: { positionId: string; cycle: HoldingCycleView } | null;
} {
  let closedCount = 0;
  let latest: { positionId: string; cycle: HoldingCycleView } | null = null;
  for (const p of matched) {
    for (const c of p.cycles) {
      if (c.status !== "CLOSED") continue;
      closedCount += 1;
      if (latest === null || (c.end_date ?? "") > (latest.cycle.end_date ?? "")) {
        latest = { positionId: p.position_id, cycle: c };
      }
    }
  }
  return { closedCount, latest };
}

export default function NewHoldingDialog({
  revision,
  rebuy = null,
  pastPositions,
  accountOptions,
  onClose,
  onSaved,
  onOpenHistory,
}: Props) {
  const uid = useId();
  const [today] = useState(todayKst);
  const options = useMemo(
    () => Array.from(new Set(accountOptions.length ? accountOptions : [DEFAULT_GROUP])),
    [accountOptions],
  );
  const [mode, setMode] = useState<"buy" | "register">("buy");
  const [tickerInput, setTickerInput] = useState("");
  const [acctSel, setAcctSel] = useState(() =>
    options.includes(DEFAULT_GROUP) ? DEFAULT_GROUP : options[0],
  );
  const [date, setDate] = useState(today);
  const [time, setTime] = useState("");
  const [price, setPrice] = useState("");
  const [qty, setQty] = useState("");
  const [lookup, setLookup] = useState<Lookup | null>(null);
  // ETF 목록에 없거나 조회가 실패한 종목(개별주 등)은 종목명을 직접 적는다(선택 · 표시용).
  const [typedName, setTypedName] = useState("");
  const wanted = useRef("");
  const { saving, error, save } = useTradeSave(onSaved);

  // 종목명 자동 조회 — 응답 적용 직전 '지금 칸의 종목코드'와 다시 대조한다(늦게 온 이전 응답 무시).
  const runLookup = useCallback((t: string) => {
    wanted.current = t;
    if (!TICKER_RE.test(t)) {
      setLookup(null);
      return;
    }
    setLookup({ ticker: t, status: "loading", name: null });
    fetchEtfName(t).then(
      (res) => {
        if (wanted.current !== t) return;
        const found = Boolean(res.found && res.name);
        setLookup({ ticker: t, status: found ? "found" : "missing", name: found ? res.name : null });
      },
      () => {
        if (wanted.current !== t) return;
        setLookup({ ticker: t, status: "error", name: null });
      },
    );
  }, []);

  const rebuyTicker = rebuy?.ticker ?? null;
  const rebuyNeedsName = Boolean(rebuy && !rebuy.name);
  useEffect(() => {
    if (rebuyTicker && rebuyNeedsName) runLookup(rebuyTicker);
  }, [rebuyTicker, rebuyNeedsName, runLookup]);

  const isBuy = Boolean(rebuy) || mode === "buy";
  const ticker = rebuy ? rebuy.ticker : tickerInput;
  const account = rebuy ? rebuy.account_group : acctSel;

  const matched = rebuy
    ? pastPositions.filter((p) => p.position_id === rebuy.position_id)
    : TICKER_RE.test(ticker)
      ? pastPositions.filter(
          (p) => !p.is_open && p.ticker === ticker && p.account_group === account,
        )
      : [];
  const ambiguous = !rebuy && matched.length > 1;
  const { closedCount, latest } = pastSummary(matched);

  const lookedUp = lookup && lookup.ticker === ticker && lookup.status === "found" ? lookup.name : null;
  const needsName =
    !rebuy &&
    lookup !== null &&
    lookup.ticker === ticker &&
    (lookup.status === "missing" || lookup.status === "error");
  const sendName =
    rebuy?.name ??
    lookedUp ??
    (needsName && typedName.trim() ? typedName.trim() : null) ??
    matched[0]?.name ??
    null;
  const priceNum = parseInput(price);
  const qtyNum = parseInput(qty);
  const amount =
    priceNum !== null && qtyNum !== null && priceNum > 0 && qtyNum > 0 ? priceNum * qtyNum : null;
  // 계좌 글자 수는 서버(파이썬 len)와 같이 코드 포인트로 센다 — UTF-16 길이로 세면 이모지가 든
  // 기존 30자 계좌(재매수 줄 · 목록의 기존 계좌)가 막힌다.
  const accountOk = account !== "" && Array.from(account).length <= ACCOUNT_MAX;
  const canSave =
    !saving &&
    // 재매수는 그 줄의 종목 · 계좌(기존 비정형 코드 포함)를 쓴다 — 새 입력 형식 검사 대상 아님.
    (Boolean(rebuy) || TICKER_RE.test(ticker)) &&
    accountOk &&
    amount !== null &&
    (!isBuy || date !== "") &&
    !ambiguous;

  const submit = () => {
    if (!canSave) return;
    const identity = { ticker, account_group: account, name: sendName };
    const cmd: SaveCommand = isBuy
      ? {
          base_revision: revision,
          action: "new_position",
          position_id: rebuy?.position_id ?? null,
          ...identity,
          trade: {
            trade_date: date,
            trade_time: time || null,
            price: toDecimalText(price),
            quantity: toDecimalText(qty),
            memo: null,
          },
        }
      : {
          base_revision: revision,
          action: "register",
          ...identity,
          holding: { quantity: toDecimalText(qty), avg_buy_price: toDecimalText(price) },
        };
    void save(cmd);
  };

  const title = rebuy
    ? `재매수 — ${rebuy.name?.trim() || rebuy.ticker} · ${rebuy.account_group}`
    : "새 보유 추가";
  const note = rebuy
    ? "재매수는 실제 매수 거래로 기록합니다. 종목 · 계좌는 과거 보유와 같고, 거래일 · 체결단가 · 수량만 입력합니다."
    : isBuy
      ? "최초 매수는 실제 거래일 · 체결단가로 기록합니다. 거래를 모르는 기존 잔고는 '잔고 등록'을 고르세요(매수일 미상)."
      : "잔고 등록은 거래를 모르는 기존 잔고입니다. 매수일은 미상으로 남고, 손익은 입력 평단 기준으로 계산합니다.";
  const shownName = nameText(rebuy, lookup, ticker);

  return (
    <Dialog
      title={title}
      onClose={onClose}
      footer={
        <>
          <button type="button" className="hmx-ghost" onClick={onClose} disabled={saving}>
            취소
          </button>
          <button type="button" onClick={submit} disabled={!canSave}>
            {saving ? "저장 중…" : "저장"}
          </button>
        </>
      }
    >
      {rebuy ? null : (
        <div
          className="hmx-seg"
          role="group"
          aria-label="추가 방식"
          style={{ maxWidth: 360, marginBottom: 14 }}
        >
          <button type="button" aria-pressed={mode === "buy"} onClick={() => setMode("buy")}>
            최초 매수
          </button>
          <button
            type="button"
            aria-pressed={mode === "register"}
            onClick={() => setMode("register")}
          >
            잔고 등록
          </button>
        </div>
      )}
      <form className="hmx-form" onSubmit={(e) => e.preventDefault()}>
        <div className="hmx-field">
          <label htmlFor={`${uid}-ticker`}>종목코드</label>
          <input
            id={`${uid}-ticker`}
            autoComplete="off"
            placeholder="예: 069500"
            value={ticker}
            readOnly={Boolean(rebuy)}
            onChange={(e) => {
              const t = e.target.value.trim().toUpperCase();
              setTickerInput(t);
              runLookup(t);
            }}
          />
        </div>
        {needsName ? (
          <div className="hmx-field">
            <label htmlFor={`${uid}-name-input`}>종목명 (선택 · ETF 목록에 없음)</label>
            <input
              id={`${uid}-name-input`}
              maxLength={60}
              placeholder={matched[0]?.name ?? "예: 삼성전자"}
              value={typedName}
              onChange={(e) => setTypedName(e.target.value)}
            />
          </div>
        ) : (
          <div className="hmx-field">
            <span className="hmx-lbl" id={`${uid}-name`}>
              종목명
            </span>
            <output className="hmx-out" aria-labelledby={`${uid}-name`} title={shownName}>
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {shownName}
              </span>
            </output>
          </div>
        )}
        <div className="hmx-field">
          <label htmlFor={`${uid}-acct`}>계좌</label>
          {rebuy ? (
            <input id={`${uid}-acct`} value={rebuy.account_group} readOnly />
          ) : (
            <select
              id={`${uid}-acct`}
              value={acctSel}
              onChange={(e) => setAcctSel(e.target.value)}
            >
              {options.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </select>
          )}
        </div>
        {isBuy ? (
          <>
            <div className="hmx-field">
              <label htmlFor={`${uid}-date`}>거래일</label>
              <input
                id={`${uid}-date`}
                type="date"
                value={date}
                max={today}
                onChange={(e) => setDate(e.target.value)}
              />
            </div>
            <div className="hmx-field">
              <label htmlFor={`${uid}-time`}>거래 시각 (선택)</label>
              <input
                id={`${uid}-time`}
                type="time"
                value={time}
                onChange={(e) => setTime(e.target.value)}
              />
            </div>
            <div className="hmx-field">
              <span className="hmx-lbl" id={`${uid}-kind`}>
                종류
              </span>
              <output className="hmx-out" aria-labelledby={`${uid}-kind`}>
                최초 매수
              </output>
            </div>
          </>
        ) : null}
        <div className="hmx-field">
          <label htmlFor={`${uid}-price`}>{isBuy ? "체결단가 (원)" : "평단 (원)"}</label>
          <input
            id={`${uid}-price`}
            className="hmx-num"
            inputMode="decimal"
            autoComplete="off"
            value={price}
            onChange={(e) => setPrice(e.target.value)}
          />
        </div>
        <div className="hmx-field">
          <label htmlFor={`${uid}-qty`}>수량</label>
          <input
            id={`${uid}-qty`}
            className="hmx-num"
            inputMode="decimal"
            autoComplete="off"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
          />
        </div>
        <div className="hmx-field">
          <span className="hmx-lbl" id={`${uid}-amt`}>
            {isBuy ? "계산 금액 (원)" : "매입금액 (원)"}
          </span>
          <output className="hmx-out hmx-right" aria-labelledby={`${uid}-amt`}>
            {amount === null ? "—" : fmtNum(amount)}
          </output>
        </div>
      </form>
      {latest || ambiguous ? (
        <div className="hmx-info">
          {latest ? (
            <>
              같은 종목 · 계좌의 과거 보유 기간 {closedCount}건이 있습니다(
              {latest.cycle.start_date ?? "매수일 미상"} ~ {latest.cycle.end_date ?? "—"} · 실현{" "}
              {fmtSignedMoney(latest.cycle.realized_pnl) ?? "—"}). 저장하면 그 종목의 새 보유
              기간으로 시작하고, 이전 기간의 원가 · 손익은 넘어오지 않습니다.{" "}
              <button
                type="button"
                className="hmx-ghost hmx-btn-sm"
                onClick={() => onOpenHistory(latest.positionId)}
              >
                History 보기
              </button>
            </>
          ) : null}
          {ambiguous ? (
            <div style={{ marginTop: latest ? 6 : 0, fontWeight: 600 }}>
              같은 종목 · 계좌의 과거 보유가 {matched.length}줄입니다 — 과거 보유에서 재매수할 줄을
              고르세요.
            </div>
          ) : null}
        </div>
      ) : null}
      <p className="hmx-note">{note}</p>
      {error ? (
        <div className="hmx-error" role="alert">
          {error}
        </div>
      ) : null}
    </Dialog>
  );
}
