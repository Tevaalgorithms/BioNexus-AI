export interface RunSummary {
  run_id: string; project_id: string; status: string; stop_reason: string | null; release_id: string;
  disease: string; targets: string[]; created_at: string; cost_usd: number; budget_warning: boolean;
}
export interface Evidence {
  evidence_id: string; source: string; source_id: string; study_family: string; target: string;
  finding: string; stance: string; species: string; context: string; passage: string;
  available_on: string; license_ok: boolean; review_state: string; accepted: boolean;
}
export interface MatrixRow {
  target: string; supporting_families: number; opposing_families: number; unknown_families: number;
  net_stance: string; evidence_ids: string[];
}
export interface Claim { claim_id: string; text: string; stance: string; evidence_ids: string[] }
export interface Issue { issue_id: string; kind: string; subject: string; description: string }
export interface RunDetail extends RunSummary {
  question: string; evidence_cutoff: string; matrix: MatrixRow[]; evidence: Evidence[]; claims: Claim[];
  issues: Issue[]; excluded: { evidence_id: string; reason: string }[]; next_steps: string[];
  completeness: { source: string; retained: number; excluded: number; status: string }[];
  graph_context: string[]; timeline: { message_id: string; from: string; to: string; type: string; depth: number; evidence_ids: string[] }[];
}
export interface Report {
  report_id: string; run_id: string; version: number; status: "draft" | "approved"; parent_version: number | null;
  markdown: string; manifest: Record<string, any>; content_hash: string; approved_by: string | null;
}
export interface RunEvent { seq: number; kind: string; data: Record<string, any> }
export interface Release {
  release_id: string; revision: number; reason: string; created_by: string; created_at: string; parent_id: string | null;
  bindings: Record<string, { model_id: string; fallback_model_id: string | null; max_output_tokens: number; temperature: number | null }>;
  skill_versions: Record<string, string>;
}
export interface ModelRow {
  model_id: string; provider: string; supports_structured_output: boolean; input_usd_per_million: number;
  output_usd_per_million: number; price_verified_on: string | null; credential_status: string; status: string;
}
