import { NextResponse } from "next/server";

import { fetchFastApiJson } from "@/lib/internal-api";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const data = await fetchFastApiJson<{ status: string }>("/internal/health", { cache: "no-store" });
    return NextResponse.json(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Health check failed";
    // 에러 발생하더라도 503을 줘서 클라이언트가 catch하게
    return NextResponse.json({ error: message }, { status: 503 });
  }
}
