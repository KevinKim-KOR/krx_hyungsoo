"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useTransition } from "react";

import {
  readRememberedMomentumEtfAccountId,
  writeRememberedMomentumEtfAccountId,
} from "../components/account-selection";
import { AppLoadingState } from "../components/AppLoadingState";
import { useToast } from "../components/ToastProvider";

type AccountOption = {
  account_id: string;
  order: number;
  name: string;
  icon: string;
};

type NoteResponse = {
  accounts?: AccountOption[];
  account_id?: string;
  content?: string;
  updated_at?: string | null;
  error?: string;
};

function formatUpdatedAt(value: string | null): string {
  if (!value) {
    return "아직 저장된 메모가 없습니다.";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("ko-KR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function NoteManager({
  onHeaderSummaryChange,
}: {
  onHeaderSummaryChange?: (summary: { accountLabel: string; saveLabel: string }) => void;
}) {
  const [accounts, setAccounts] = useState<AccountOption[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState("");
  const [content, setContent] = useState("");
  const [savedContent, setSavedContent] = useState("");
  const [updatedAt, setUpdatedAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const toast = useToast();

  const isDirty = content !== savedContent;
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const contentRef = useRef(content);
  const selectedAccountIdRef = useRef(selectedAccountId);
  contentRef.current = content;
  selectedAccountIdRef.current = selectedAccountId;

  const saveNote = useCallback(
    async (silent = false) => {
      const currentContent = contentRef.current;
      const accountId = selectedAccountIdRef.current;
      if (!accountId) return;
      try {
        setError(null);
        const response = await fetch("/api/note", {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ account_id: accountId, content: currentContent }),
        });
        const payload = (await response.json()) as { updated_at?: string; error?: string };
        if (!response.ok) {
          throw new Error(payload.error ?? "메모 저장에 실패했습니다.");
        }
        setSavedContent(currentContent);
        setUpdatedAt(payload.updated_at ?? null);
        if (!silent) {
          toast.success("[계좌 메모] 저장 완료");
        }
      } catch (saveError) {
        if (!silent) {
          setError(saveError instanceof Error ? saveError.message : "메모 저장에 실패했습니다.");
        }
      }
    },
    [toast],
  );

  // 타이핑 멈춘 후 3초 뒤 자동 저장
  useEffect(() => {
    if (!isDirty) return;
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(() => {
      void saveNote(true);
    }, 3000);
    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    };
  }, [content, isDirty, saveNote]);

  useEffect(() => {
    function handleBeforeUnload(event: BeforeUnloadEvent) {
      if (!isDirty) {
        return;
      }
      event.preventDefault();
      event.returnValue = "";
    }

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [isDirty]);

  async function load(accountId?: string) {
    try {
      setLoading(true);
      setError(null);
      const search = accountId ? `?account=${encodeURIComponent(accountId)}` : "";
      const response = await fetch(`/api/note${search}`, { cache: "no-store" });
      const payload = (await response.json()) as NoteResponse;
      if (!response.ok) {
        throw new Error(payload.error ?? "메모 데이터를 불러오지 못했습니다.");
      }

      setAccounts(payload.accounts ?? []);
      const nextAccountId = payload.account_id ?? "";
      setSelectedAccountId(nextAccountId);
      writeRememberedMomentumEtfAccountId(nextAccountId);
      const nextContent = String(payload.content ?? "");
      setContent(nextContent);
      setSavedContent(nextContent);
      setUpdatedAt(payload.updated_at ?? null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "메모 데이터를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load(readRememberedMomentumEtfAccountId() ?? undefined);
  }, []);

  const selectedAccount = useMemo(
    () => accounts.find((account) => account.account_id === selectedAccountId) ?? null,
    [accounts, selectedAccountId],
  );

  useEffect(() => {
    const accountLabel = selectedAccount ? `${selectedAccount.icon} ${selectedAccount.name}` : "-";
    const saveLabel = isDirty ? "저장되지 않은 변경이 있습니다." : `마지막 저장: ${formatUpdatedAt(updatedAt)}`;
    onHeaderSummaryChange?.({ accountLabel, saveLabel });
  }, [isDirty, onHeaderSummaryChange, selectedAccount, updatedAt]);

  function handleAccountChange(nextAccountId: string) {
    if (isDirty) {
      const confirmed = window.confirm("저장되지 않은 변경이 있습니다. 이동하면 변경 내용이 사라집니다.");
      if (!confirmed) {
        return;
      }
    }
    setSelectedAccountId(nextAccountId);
    writeRememberedMomentumEtfAccountId(nextAccountId);
    void load(nextAccountId);
  }

  function handleSave() {
    startTransition(async () => {
      await saveNote(false);
    });
  }

  if (loading) {
    return (
      <div className="appPageStack">
        <div className="appPageLoading">
          <AppLoadingState label="계좌 메모를 불러오는 중..." />
        </div>
      </div>
    );
  }

  return (
    <div className="appPageStack">
      {error ? (
        <div className="appBannerStack">
          {error ? <div className="bannerError">{error}</div> : null}
        </div>
      ) : null}

      <section className="appSection">
        <div className="card appCard">
          <div className="card-header">
            <div className="appMainHeader">
              <div className="appMainHeaderLeft noteMainHeaderLeft">
                <label className="appLabeledField accountSelect">
                  <span className="appLabeledFieldLabel">계좌</span>
                  <select
                    className="field compactField"
                    value={selectedAccountId}
                    onChange={(event) => handleAccountChange(event.target.value)}
                  >
                    {accounts.map((account) => (
                      <option key={account.account_id} value={account.account_id}>
                        {account.name}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          </div>
          <div className="card-header appActionHeader bg-light-subtle border-top">
            <div className="appActionHeaderInner">
              <button className="btn btn-primary btn-sm px-3 fw-bold" type="button" onClick={handleSave} disabled={isPending}>
                {isPending ? "저장 중..." : "메모 저장"}
              </button>
            </div>
          </div>
          <div className="card-body appCardBody">
            <div className="noteMetaRow">
              {isDirty ? <span>저장되지 않은 변경이 있습니다.</span> : <span>마지막 저장: {formatUpdatedAt(updatedAt)}</span>}
            </div>

            <textarea
              className="bulkTextarea"
              value={content}
              onChange={(event) => setContent(event.target.value)}
              placeholder="이 계좌에 대한 투자 전략이나 주의사항을 메모하세요. AI가 요약할 때 함께 참고합니다."
            />
          </div>
        </div>
      </section>
    </div>
  );
}
