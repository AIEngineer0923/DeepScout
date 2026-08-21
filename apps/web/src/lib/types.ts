export type RunListItem = {
  id: string;
  goal: string;
  status: string;
  llm_provider: string;
  llm_model: string;
  research_mode?: string | null;
  output_language?: string;
  termination_reason: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  total_tokens: number | null;
  cost_usd: number | null;
  cost_status: string;
  parent_run_id?: string | null;
  lineage_kind?: string;
  source_count: number;
  evidence_count: number;
  claim_count: number;
  task_count: number;
  completed_task_count: number;
};

export type DemoCatalogItem = RunListItem & {
  public_slug: string | null;
  is_public_demo: boolean;
  demo_category?: string | null;
  demo_title?: string | null;
  demo_summary?: string | null;
  demo_why?: string | null;
};

export type Workspace = {
  run_id: string;
  event_head?: number;
  status: string;
  goal: string;
  termination_reason: string | null;
  llm_provider: string;
  llm_model: string;
  research_mode?: string | null;
  output_language?: string;
  is_public_demo?: boolean;
  public_slug?: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  completed_at: string | null;
  budget: {
    max_iterations: number;
    max_sources: number;
    max_tool_calls: number;
    max_total_tokens: number;
    max_cost_usd: number;
    concurrency_limit: number;
  };
  usage: {
    input_tokens: number | null;
    output_tokens: number | null;
    cached_input_tokens: number | null;
    reasoning_tokens: number | null;
    total_tokens: number | null;
    cost_usd: number | null;
    usage_status: string;
    cost_status: string;
    pricing_version: string | null;
    evaluation_total_tokens: number | null;
    evaluation_cost_usd: number | null;
    cost_unknown_reason: string | null;
    by_role?: Record<string, {
      input_tokens: number | null;
      output_tokens: number | null;
      cached_input_tokens: number | null;
      reasoning_tokens: number | null;
      total_tokens: number | null;
    }>;
  };
  counts: {
    tasks: number;
    sources: number;
    claims: number;
    evidence: number;
    contradictions: number;
    snapshots: number;
    consumed_sources: number;
    consumed_tool_calls: number;
  };
  completed_phases: string[];
  phase_timings: Record<string, string>;
  report: { id: string; title: string; body_markdown: string; created_at: string } | null;
  tasks: Array<{
    id: string;
    task_key: string;
    objective: string;
    status: string;
    depends_on: string[];
    allowed_tools: string[];
    worker_id: string | null;
    index: number;
    display_name: string;
    started_at: string | null;
    completed_at: string | null;
    retries: number;
  }>;
  workers: Array<{
    index: number;
    display_name: string;
    worker_id: string;
    task_id: string;
    task_key: string;
    role: string;
    agent_backed: boolean;
    parent: string;
    assigned_task: string;
    state: string;
    started_at: string | null;
    completed_at: string | null;
    allowed_tools: string[];
    retries: number;
    skills?: string[];
  }>;
  sources: Array<{
    id: string;
    title: string;
    url: string;
    domain: string;
    source_type: string;
    created_at: string | null;
    fetch_state: string;
    snapshot_available: boolean;
    snapshot_id: string | null;
    claim_count: number;
    evidence_count: number;
    task_id: string | null;
    task_key: string | null;
    worker_index: number | null;
    preference?: string;
  }>;
  source_preferences?: Array<{ id: string; action: string; identity_kind: string; identity_value: string; reason: string }>;
  snapshots: Array<{
    id: string;
    source_id: string;
    source_title: string;
    url: string;
    retrieved_at: string | null;
    mime_type: string;
    byte_size: number;
    content_hash: string;
    word_count: number;
    evidence_count: number;
  }>;
  claims: Array<{
    id: string;
    statement: string;
    verification_status: string;
    source_id: string | null;
    task_id: string | null;
    task_key: string | null;
    worker_index: number | null;
    evidence_count: number;
    independent_source_count: number;
    created_at: string | null;
  }>;
  evidence: Array<{
    id: string;
    claim_id: string;
    quote: string;
    locator: string;
    snapshot_id: string;
    source_id: string | null;
    created_at: string | null;
  }>;
  contradictions: Array<{
    id: string;
    description: string;
    evidence_status: string;
    claim_a_id: string;
    claim_b_id: string;
    created_at: string | null;
  }>;
  activity: Array<{
    sequence: number;
    type: string;
    payload: Record<string, unknown>;
    created_at: string | null;
  }>;
  evaluations: Array<{
    evaluator_id: string;
    version: string;
    category: string;
    method: string;
    applicability: string;
    description: string;
    value: unknown;
  }>;
  runtime?: {
    parent_run_id: string | null;
    root_run_id?: string | null;
    lineage_kind?: string;
    fork_reason: string | null;
    monitor_id?: string | null;
    replans_used: number;
    config_schema_version?: string | number | null;
    max_delegation_depth?: number;
  };
  resume: {
    domain_authority: string;
    checkpoint_role: string;
    completed_task_count: number;
    remaining_task_count: number;
    preserved_sources: number;
    preserved_evidence: number;
    current_phase: string;
    latest_job_type: string | null;
    latest_job_status: string | null;
    resumable: boolean;
  };
  architecture: Record<string, { label: string; kind: string }>;
};

export type Overview = {
  active: RunListItem | null;
  recent: RunListItem[];
  totals: {
    runs: number;
    sources: number;
    evidence: number;
    claims: number;
    known_cost_usd: number | null;
    cost_status: string;
    avg_completion_seconds: number | null;
  };
  identity: { label: string; role: string; mode?: string };
  langsmith: { connected: boolean; project: string; region: string; tracing: boolean };
  providers: Record<string, { configured: boolean; model?: string }>;
};
