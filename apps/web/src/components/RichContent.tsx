"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeSanitize, { defaultSchema } from "rehype-sanitize";
import type { Components } from "react-markdown";
import { ExternalLink } from "@/components/ExternalLink";
import { safeHttpUrl } from "@/lib/safe-url";
import { buildCitationMap, linkifyNumericCitations } from "@/lib/citations";
import type { Workspace } from "@/lib/types";

const sanitizeSchema = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    th: [...(defaultSchema.attributes?.th ?? []), "align"],
    td: [...(defaultSchema.attributes?.td ?? []), "align"],
    a: [...(defaultSchema.attributes?.a ?? []), ["target", "rel"]],
  },
};

function markdownComponents(): Components {
  return {
    a: ({ href, children }) => {
      if (!href) return <span>{children}</span>;
      if (href.startsWith("/")) {
        return (
          <a href={href} className="rich-link">
            {children}
          </a>
        );
      }
      const safe = safeHttpUrl(href);
      if (!safe) return <span>{children}</span>;
      return <ExternalLink href={safe}>{children}</ExternalLink>;
    },
    table: ({ children }) => (
      <div className="rich-table-wrap">
        <table className="rich-table">{children}</table>
      </div>
    ),
    code: ({ className, children, ...props }) => {
      const inline = !className;
      if (inline) {
        return (
          <code className="rich-inline-code" {...props}>
            {children}
          </code>
        );
      }
      return (
        <pre className="rich-code-block">
          <code className={className} {...props}>
            {children}
          </code>
        </pre>
      );
    },
  };
}

export function RichContent({
  markdown,
  className = "rich-content",
  runId,
  sources,
}: {
  markdown: string;
  className?: string;
  runId?: string;
  sources?: Workspace["sources"];
}) {
  const prepared =
    runId && sources?.length
      ? linkifyNumericCitations(markdown, runId, buildCitationMap(markdown, sources))
      : markdown;

  return (
    <div className={className}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeSanitize, sanitizeSchema]]}
        components={markdownComponents()}
      >
        {prepared}
      </ReactMarkdown>
    </div>
  );
}
