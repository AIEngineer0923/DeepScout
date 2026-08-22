import { workspaceFixture, FIXTURE_RUN_ID } from "../fixtures";

export const XSS_PAYLOADS = [
  "<script>alert(1)</script>",
  '<img src=x onerror=alert(1)>',
  "javascript:alert(1)",
  "[click](javascript:alert(1))",
  "<svg onload=alert(1)>",
] as const;

const SNAPSHOT_ID = "99999999-9999-4999-8999-999999999999";
const KNOWLEDGE_PAGE_ID = "abababab-abab-4aba-8aba-abababababab";

export const xssWorkspaceFixture = {
  ...workspaceFixture,
  status: "completed",
  report: {
    id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    title: XSS_PAYLOADS[0],
    body_markdown: XSS_PAYLOADS.join("\n\n"),
    created_at: "2026-08-21T10:03:00.000Z",
  },
  sources: [
    {
      ...workspaceFixture.sources[0],
      title: XSS_PAYLOADS[1],
      url: XSS_PAYLOADS[2],
    },
  ],
  claims: [
    {
      ...workspaceFixture.claims[0],
      statement: XSS_PAYLOADS[0],
    },
  ],
  evidence: [
    {
      ...workspaceFixture.evidence[0],
      quote: XSS_PAYLOADS[3],
    },
  ],
};

export const xssSnapshotFixture = {
  snapshot: {
    id: SNAPSHOT_ID,
    source_id: workspaceFixture.sources[0].id,
    source_title: XSS_PAYLOADS[1],
    url: "https://example.com/safe",
    content_text: XSS_PAYLOADS.join("\n"),
    mime_type: "text/html",
    byte_size: 1200,
    content_hash: "abc123",
    retrieved_at: "2026-08-21T10:01:05.000Z",
  },
  evidence: [
    {
      id: workspaceFixture.evidence[0].id,
      quote: XSS_PAYLOADS[4],
      claim_id: workspaceFixture.claims[0].id,
    },
  ],
};

export const xssKnowledgePageFixture = {
  id: KNOWLEDGE_PAGE_ID,
  title: XSS_PAYLOADS[0],
  body_markdown: XSS_PAYLOADS.join("\n"),
  version: 1,
  status: "published",
  statements: [
    {
      id: "bcbcbcbc-bcbc-4cbc-8cbc-bcbcbcbcbcbc",
      text: XSS_PAYLOADS[4],
      status: "supported",
    },
  ],
};

export const XSS_FIXTURE_RUN_ID = FIXTURE_RUN_ID;
export const XSS_SNAPSHOT_ID = SNAPSHOT_ID;
export const XSS_KNOWLEDGE_PAGE_ID = KNOWLEDGE_PAGE_ID;
