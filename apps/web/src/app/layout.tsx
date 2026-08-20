import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DeepScout",
  description: "Autonomous Research & Decision Intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
