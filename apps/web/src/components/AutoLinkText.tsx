import { ExternalLink } from "@/components/ExternalLink";
import { safeHttpUrl } from "@/lib/safe-url";

const URL_PATTERN = /(https?:\/\/[^\s<]+[^\s<.,;:!?'")\]}>])/gi;

export function AutoLinkText({
  text,
  className = "wrap-text",
}: {
  text: string;
  className?: string;
}) {
  const parts = text.split(URL_PATTERN);
  return (
    <span className={className}>
      {parts.map((part, index) => {
        if (!part) return null;
        const safe = safeHttpUrl(part);
        if (safe) {
          return (
            <ExternalLink key={`${safe}-${index}`} href={safe}>
              {part}
            </ExternalLink>
          );
        }
        return <span key={`text-${index}`}>{part}</span>;
      })}
    </span>
  );
}
