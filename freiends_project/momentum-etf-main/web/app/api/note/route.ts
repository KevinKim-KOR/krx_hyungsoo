import { NextRequest, NextResponse } from "next/server";

import { loadAccountNoteData, saveAccountNoteData } from "../../../lib/note-store";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  try {
    const accountId = request.nextUrl.searchParams.get("account") ?? undefined;
    const data = await loadAccountNoteData(accountId);
    return NextResponse.json(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "메모 데이터를 불러오지 못했습니다.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function PATCH(request: NextRequest) {
  try {
    const payload = (await request.json()) as { account_id?: string; content?: string };
    const result = await saveAccountNoteData(payload.account_id ?? "", payload.content ?? "");
    return NextResponse.json(result);
  } catch (error) {
    const message = error instanceof Error ? error.message : "메모 저장에 실패했습니다.";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
