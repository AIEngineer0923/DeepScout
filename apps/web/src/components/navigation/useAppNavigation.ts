"use client";

import { useMemo } from "react";
import { usePathname, useRouter } from "next/navigation";
import { RESEARCH_NAV, isResearchNavCurrent, researchHref } from "@/components/research/researchNav";
import {
  IconClaims,
  IconEvals,
  IconHistory,
  IconHome,
  IconLive,
  IconPlan,
  IconPlus,
  IconQuality,
  IconReport,
  IconResume,
  IconSettings,
  IconSnapshot,
  IconSources,
  IconWorkers,
} from "@/components/Icons";
import { useT } from "@/i18n/context";
import type { ComponentType } from "react";

const RESEARCH_ICONS = [
  IconLive,
  IconPlan,
  IconWorkers,
  IconSources,
  IconSnapshot,
  IconClaims,
  IconQuality,
  IconReport,
  IconEvals,
] as const;

export type AppNavItem = {
  id: string;
  label: string;
  href: string;
  icon?: ComponentType<{ className?: string }>;
  current: boolean;
  enabled: boolean;
  section?: string;
  onDisabledClick?: () => void;
};

export type AppNavContext = {
  demoReadOnly: boolean;
  runId: string | null;
  isAuthenticated: boolean;
  isHosted: boolean;
  overviewHref: string;
  newResearchHref: string;
};

export function useAppNavigation(ctx: AppNavContext) {
  const pathname = usePathname();
  const router = useRouter();
  const t = useT();
  const { demoReadOnly, runId, isAuthenticated, isHosted, overviewHref, newResearchHref } = ctx;

  return useMemo(() => {
    const items: AppNavItem[] = [
      {
        id: "overview",
        label: demoReadOnly ? t("demo.backToCatalog") : t("nav.overview"),
        href: overviewHref,
        icon: IconHome,
        current: pathname === overviewHref,
        enabled: true,
      },
      {
        id: "new-research",
        label: t("nav.newResearch"),
        href: newResearchHref,
        icon: IconPlus,
        current: pathname === "/research/new",
        enabled: true,
      },
    ];

    items.push({
      id: "section-research",
      label: t("nav.section.research"),
      href: "#",
      current: false,
      enabled: true,
      section: "label",
    });

    RESEARCH_NAV.forEach((navItem, index) => {
      const enabled = Boolean(runId);
      const href = runId ? researchHref(navItem.id, runId) : "/research/select";
      items.push({
        id: navItem.id,
        label: t(`nav.${navItem.id}`),
        href,
        icon: RESEARCH_ICONS[index],
        current: runId ? isResearchNavCurrent(navItem.id, pathname, runId) : false,
        enabled,
        onDisabledClick: () => router.push("/research/select"),
      });
    });

    if (!demoReadOnly) {
      const secondary: Omit<AppNavItem, "section">[] = [
        { id: "history", label: t("nav.history"), href: "/history", icon: IconHistory, current: pathname === "/history", enabled: true },
        {
          id: "knowledge",
          label: t("nav.knowledge"),
          href: "/knowledge",
          icon: IconClaims,
          current: pathname.startsWith("/knowledge"),
          enabled: true,
        },
        {
          id: "monitors",
          label: t("nav.monitors"),
          href: "/monitors",
          icon: IconLive,
          current: pathname.startsWith("/monitors"),
          enabled: true,
        },
        {
          id: "compare",
          label: t("nav.compare"),
          href: "/compare",
          icon: IconEvals,
          current: pathname.startsWith("/compare"),
          enabled: true,
        },
        {
          id: "resume",
          label: t("nav.resume"),
          href: runId ? `/resume/${runId}` : "/research/select",
          icon: IconResume,
          current: pathname.startsWith("/resume"),
          enabled: Boolean(runId),
          onDisabledClick: () => router.push("/research/select"),
        },
        { id: "reviews", label: t("nav.reviews"), href: "/reviews", icon: IconEvals, current: pathname === "/reviews", enabled: true },
        { id: "learning", label: t("nav.learning"), href: "/learning", icon: IconEvals, current: pathname === "/learning", enabled: true },
        { id: "demo", label: t("nav.demo"), href: "/demo", icon: IconEvals, current: pathname === "/demo", enabled: true },
      ];
      items.push(...secondary);
    }

    if (!isAuthenticated && isHosted && !demoReadOnly) {
      items.push({
        id: "sign-in",
        label: t("nav.signIn"),
        href: "/login",
        icon: IconSettings,
        current: pathname === "/login",
        enabled: true,
      });
    }

    if (!demoReadOnly && (isAuthenticated || !isHosted)) {
      items.push({
        id: "account",
        label: t("nav.account"),
        href: "/account",
        icon: IconSettings,
        current: pathname === "/account",
        enabled: true,
      });
    }

    if (!demoReadOnly) {
      items.push({
        id: "settings",
        label: t("nav.settings"),
        href: "/settings",
        icon: IconSettings,
        current: pathname === "/settings",
        enabled: true,
      });
    }

    return items;
  }, [
    demoReadOnly,
    isAuthenticated,
    isHosted,
    newResearchHref,
    overviewHref,
    pathname,
    router,
    runId,
    t,
  ]);
}
