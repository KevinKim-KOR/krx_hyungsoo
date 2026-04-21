import { NextResponse } from "next/server";

import { loadSnapshotList } from "@/lib/snapshot-store";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const snapshots = await loadSnapshotList();
    return NextResponse.json({ snapshots });
  } catch (error) {
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "스냅샷 목록을 불러오지 못했습니다.",
      },
      { status: 500 },
    );
  }
}
