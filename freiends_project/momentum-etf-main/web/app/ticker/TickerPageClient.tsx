"use client";

import { PageFrame } from "../components/PageFrame";
import { TickerDetailManager } from "./TickerDetailManager";

export function TickerPageClient() {
  return (
    <PageFrame title="개별종목" fullHeight fullWidth>
      <TickerDetailManager />
    </PageFrame>
  );
}
