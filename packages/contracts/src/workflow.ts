/**
 * Generated from FastAPI OpenAPI by scripts/generate_workflow_contracts.py.
 * Do not edit by hand; run the generator or its --check mode.
 */

export interface CreateProjectRequest {
  name: string;
}

export interface ProjectResponse {
  id: string;
  name: string;
  created_at: string;
}

export interface DrawingUploadResponse {
  id: string;
  project_id: string;
  sha256: string;
  drawing_type: DrawingType;
  source_name: string;
}

export interface CreateAnalysisRequest {
  project_id: string;
  drawing_id: string;
  config_versions?: Record<string, string>;
}

export interface AnalysisJobResponse {
  id: string;
  project_id: string;
  drawing_id: string;
  state: JobState;
  completed_steps: Array<AnalysisStep>;
  failed_step?: AnalysisStep | null;
  error_code?: string | null;
  config_versions: Record<string, string>;
}

export interface FindingsResponse {
  job_id: string;
  findings: Array<Finding>;
  suggestions: Array<ImprovementSuggestion>;
}

export interface Finding {
  id?: string;
  job_id: string;
  status: FindingStatus;
  severity: Severity;
  confidence: number;
  finding_type: string;
  location: string;
  message: string;
  pixel_bbox?: [number, number, number, number] | null;
  cad_bbox?: [number, number, number, number] | null;
  evidence?: Array<Evidence>;
  created_at?: string;
}

export interface Evidence {
  kind: EvidenceKind;
  ref_id: string;
  score?: number | null;
  location?: string | null;
}

export interface ImprovementSuggestion {
  finding_id: string;
  issue: string;
  location: string;
  recommendation: string;
  evidence_refs?: Array<string>;
  verification_condition: string;
}

export type DrawingType = "pdf" | "dxf";

export type JobState = "queued" | "running" | "cancelling" | "cancelled" | "failed" | "completed";

export type AnalysisStep = "validate" | "extract" | "rules" | "retrieve" | "suggest" | "export_ready";

export type FindingStatus = "violation" | "suspected" | "insufficient_information";

export type Severity = "high" | "medium" | "low";

export type EvidenceKind = "rule" | "case" | "source";
