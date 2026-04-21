import { fetchFastApiJson } from "./internal-api";

type AccountOption = {
  account_id: string;
  order: number;
  name: string;
  icon: string;
};

type AccountNoteData = {
  accounts: AccountOption[];
  account_id: string;
  content: string;
  updated_at: string | null;
};

export async function loadAccountNoteData(requestedAccountId?: string): Promise<AccountNoteData> {
  return fetchFastApiJson<AccountNoteData>(
    `/internal/note${requestedAccountId ? `?account_id=${encodeURIComponent(requestedAccountId)}` : ""}`,
  );
}

export async function saveAccountNoteData(accountIdRaw: string, contentRaw: string) {
  return fetchFastApiJson<{ updated_at: string }>("/internal/note", {
    method: "PATCH",
    body: JSON.stringify({ account_id: accountIdRaw, content: contentRaw }),
  });
}

export type { AccountNoteData };
