import type { Metadata } from "next";
import type { ReactNode } from "react";

import "@tabler/core/dist/css/tabler.min.css";
import { AppShell } from "./AppShell";
import { buildBucketCssVariables } from "../lib/bucket-theme";
import { ToastProvider } from "./components/ToastProvider";
import "./globals.css";

export const metadata: Metadata = {
  title: "Jason 투자",
  description: "Jason 투자 운영 UI",
};

type RootLayoutProps = {
  children: ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="ko" data-scroll-behavior="smooth">
      <body>
        <style>{buildBucketCssVariables()}</style>
        <ToastProvider>
          <AppShell>{children}</AppShell>
        </ToastProvider>
      </body>
    </html>
  );
}
