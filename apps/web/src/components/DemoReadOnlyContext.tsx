"use client";

import { createContext, useContext, type ReactNode } from "react";

const DemoReadOnlyContext = createContext(false);

export function DemoReadOnlyProvider({ children, value }: { children: ReactNode; value: boolean }) {
  return <DemoReadOnlyContext.Provider value={value}>{children}</DemoReadOnlyContext.Provider>;
}

export function useDemoReadOnly() {
  return useContext(DemoReadOnlyContext);
}
