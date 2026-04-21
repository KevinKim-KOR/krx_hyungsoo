import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET() {
  const internalToken = process.env.FASTAPI_INTERNAL_TOKEN || "";
  const baseUrl = process.env.FASTAPI_INTERNAL_URL || "http://127.0.0.1:8000";

  try {
    const response = await fetch(`${baseUrl}/internal/market/fx`, {
      cache: "no-store",
      headers: {
        "X-Internal-Token": internalToken,
      },
    });

    if (!response.ok) {
        return NextResponse.json({ error: "환율 데이터를 가져오지 못했습니다." }, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "환율 데이터 요청 중 오류 발생",
      },
      { status: 500 },
    );
  }
}
