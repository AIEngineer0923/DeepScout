import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { UI_LOCALE_KEY } from "@/i18n/messages";
import { detectLocaleFromAcceptLanguage } from "@/i18n/locale";

export function middleware(request: NextRequest) {
  const response = NextResponse.next();
  const existing = request.cookies.get(UI_LOCALE_KEY)?.value;
  if (existing === "en" || existing === "it") {
    return response;
  }
  const detected = detectLocaleFromAcceptLanguage(request.headers.get("accept-language"));
  response.cookies.set(UI_LOCALE_KEY, detected, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
  });
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
