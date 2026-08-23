import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";
import { LayoutSelector } from "@/components/LayoutSelector";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const dynamic = "force-dynamic";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "Deep Scout",
  description: "Evidence-backed autonomous research with provenance you can inspect.",
};

// viewportFit: "cover" is what makes env(safe-area-inset-*) resolve to non-zero on iOS.
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={inter.className}>
      <body className="page-overflow-guard">
        <Providers>
          <LayoutSelector>{children}</LayoutSelector>
        </Providers>
      </body>
    </html>
  );
}
