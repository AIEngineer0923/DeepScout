import type { NextConfig } from "next";
import fs from "node:fs";
import path from "node:path";

const isDev = process.env.NODE_ENV !== "production";
const scriptSrc = isDev
  ? "script-src 'self' 'unsafe-inline' 'unsafe-eval'"
  : "script-src 'self' 'unsafe-inline'";
const apiOrigin = process.env.NEXT_PUBLIC_API_URL
  ? new URL(process.env.NEXT_PUBLIC_API_URL).origin
  : "";
const connectSrc = [
  "connect-src 'self'",
  "http://127.0.0.1:8000",
  "http://localhost:8000",
  ...(apiOrigin && apiOrigin !== "http://localhost:8000" && apiOrigin !== "http://127.0.0.1:8000"
    ? [apiOrigin]
    : []),
  ...(isDev ? ["ws:", "wss:"] : []),
].join(" ");

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=()",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      scriptSrc,
      "style-src 'self' 'unsafe-inline'",
      "img-src 'self' data: blob:",
      "font-src 'self' data:",
      connectSrc,
      "frame-ancestors 'none'",
      "base-uri 'self'",
      "form-action 'self'",
    ].join("; "),
  },
];

const repoRoot = path.join(__dirname, "../..");
const inMonorepo = fs.existsSync(path.join(repoRoot, "pyproject.toml"));

const nextConfig: NextConfig = {
  output: "standalone",
  ...(inMonorepo ? { outputFileTracingRoot: repoRoot } : {}),
  poweredByHeader: false,
  productionBrowserSourceMaps: false,
  compress: true,
  async headers() {
    return [
      {
        source: "/_next/static/:path*",
        headers: [
          { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
        ],
      },
      { source: "/:path*", headers: securityHeaders },
    ];
  },
};

export default nextConfig;
