"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { detectLocaleFromNavigator } from "./locale";
import { UI_LOCALE_KEY, isLocale, translate, type Locale } from "./messages";

type I18nContextValue = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nContextValue>({
  locale: "en",
  setLocale: () => undefined,
  t: (key) => key,
});

function readStoredLocale(): Locale | null {
  if (typeof window === "undefined") return null;
  const stored = window.localStorage.getItem(UI_LOCALE_KEY);
  if (isLocale(stored)) return stored;
  const cookie = document.cookie
    .split(";")
    .map((part) => part.trim())
    .find((part) => part.startsWith(`${UI_LOCALE_KEY}=`));
  const value = cookie?.split("=")[1];
  return isLocale(value) ? value : null;
}

function persistLocale(locale: Locale) {
  window.localStorage.setItem(UI_LOCALE_KEY, locale);
  document.cookie = `${UI_LOCALE_KEY}=${locale}; path=/; max-age=31536000; SameSite=Lax`;
  document.documentElement.lang = locale;
}

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("en");

  useEffect(() => {
    const stored = readStoredLocale();
    const next = stored ?? detectLocaleFromNavigator();
    setLocaleState(next);
    persistLocale(next);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    persistLocale(next);
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => translate(locale, key, vars),
    [locale],
  );

  const value = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}

export function useT() {
  return useI18n().t;
}
