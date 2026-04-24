import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "POC 1단계 승인 루프",
  description: "AI 초안 생성 → 사람의 승인/거절 → 외부 전달",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
