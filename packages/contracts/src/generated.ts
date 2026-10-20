/**
 * Domain contracts and API types for Dev Pre-Review.
 */

export type JobState =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelling"
  | "cancelled";

export type RuleState = "draft" | "approved" | "deprecated";

export type Severity = "critical" | "major" | "minor" | "info";

export type FindingStatus =
  | "violation"
  | "compliant"
  | "insufficient_information";

export type DrawingType = "pdf" | "dxf";

export type EvidenceKind = "rule" | "case" | "source_text" | "drawing_region";

export interface BoundingBox {
  page_or_layout: number | string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
}

export interface Evidence {
  kind: EvidenceKind;
  ref_id: string;
}

export interface Finding {
  id: string;
  job_id: string;
  rule_id?: string | null;
  rule_code: string;
  status: FindingStatus;
  severity: Severity;
  message: string;
  bbox?: BoundingBox | null;
  evidences: Evidence[];
}

export interface ImprovementSuggestion {
  finding_id: string;
  suggested_action: string;
  rationale: string;
  new_rule_candidate?: Record<string, unknown> | null;
}

export interface RuleDefinition {
  id: string;
  code: string;
  title: string;
  description: string;
  discipline: string;
  state: RuleState;
  severity: Severity;
  operator: string;
  field_name: string;
  parameters: Record<string, unknown>;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface AnalysisJobResponse {
  id: string;
  project_id: string;
  drawing_id: string;
  state: JobState;
  completed_steps: string[];
  failed_step?: string | null;
  error_code?: string | null;
  config_versions: Record<string, string>;
}

export interface CreateAnalysisRequest {
  project_id: string;
  drawing_id: string;
  config_versions?: Record<string, string>;
}

export interface FindingsResponse {
  job_id: string;
  findings: Finding[];
  suggestions: ImprovementSuggestion[];
}

export interface HardwareProfile {
  cpu_logical_cores: number;
  system_ram_gb: number;
  has_cuda: boolean;
  cuda_device_name?: string | null;
  cuda_vram_gb: number;
  execution_provider: "cpu" | "cuda";
}

export interface ModelRecommendation {
  profile_name: string;
  ocr_model: string;
  embedding_model: string;
  visual_model?: string | null;
  suggestion_mode: "local" | "cloud" | "rule_only";
  reason: string;
}

export interface ProfileResponse {
  hardware_profile: HardwareProfile;
  recommendation: ModelRecommendation;
}

export interface ConsentRequest {
  job_id: string;
  token: string;
  action: "grant" | "revoke";
}

export interface ProblemDetails {
  type: string;
  title: string;
  status: number;
  detail: string;
  instance?: string;
}

export interface ImportPreviewRow {
  row_number: number;
  category: string;
  raw_content: string;
  extracted_rule_code?: string | null;
  validation_status: "valid" | "warning" | "invalid";
  message?: string | null;
}

export interface ImportPreviewResponse {
  preview_id: string;
  filename: string;
  total_rows: number;
  valid_count: number;
  warning_count: number;
  invalid_count: number;
  rows: ImportPreviewRow[];
}
