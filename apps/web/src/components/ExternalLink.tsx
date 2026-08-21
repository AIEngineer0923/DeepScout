import { safeHttpUrl } from "@/lib/safe-url";

export function ExternalLink({ href, children }: { href: string; children: React.ReactNode }) {
  const safe = safeHttpUrl(href);
  if (!safe) return <span className="muted">{children}</span>;
  return (
    <a href={safe} target="_blank" rel="noopener noreferrer">
      {children}
    </a>
  );
}
