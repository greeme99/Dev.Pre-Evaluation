import type {
  AnalysisJobResponse,
  ConsentRequest,
  CreateAnalysisRequest,
  FindingsResponse,
  ProfileResponse,
  RuleDefinition,
} from "@dev-pre-review/contracts";

const API_BASE = "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public title: string,
    public detail: string,
  ) {
    super(`[${status}] ${title}: ${detail}`);
    this.name = "ApiError";
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!res.ok) {
    let title = "요청 처리 실패";
    let detail = "알 수 없는 오류가 발생했습니다.";
    try {
      const errData = await res.json();
      if (errData.title) title = errData.title;
      if (errData.detail) detail = errData.detail;
    } catch {
      detail = await res.text();
    }
    throw new ApiError(res.status, title, detail);
  }

  return res.json() as Promise<T>;
}

export const api = {
  // Analyses
  createAnalysis: (body: CreateAnalysisRequest) =>
    request<AnalysisJobResponse>("/analyses", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  getAnalysis: (jobId: string) =>
    request<AnalysisJobResponse>(`/analyses/${jobId}`),
  cancelAnalysis: (jobId: string) =>
    request<AnalysisJobResponse>(`/analyses/${jobId}/cancel`, { method: "POST" }),
  retryAnalysis: (jobId: string) =>
    request<AnalysisJobResponse>(`/analyses/${jobId}/retry`, { method: "POST" }),
  getFindings: (jobId: string) =>
    request<FindingsResponse>(`/analyses/${jobId}/findings`),

  // Rules
  getRules: (projectId?: string) => {
    const query = projectId ? `?project_id=${projectId}` : "";
    return request<RuleDefinition[]>(`/rules${query}`);
  },
  transitionRule: (ruleId: string, action: string, version: number) =>
    request<RuleDefinition>(`/rules/${ruleId}/transitions`, {
      method: "POST",
      body: JSON.stringify({ action, expected_version: version }),
    }),

  // Knowledge
  importKnowledgeCommit: (projectId: string, previewId: string) =>
    request<{ committed_count: number }>("/knowledge/import-commit", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, preview_id: previewId }),
    }),

  // Settings
  getProfile: () => request<ProfileResponse>("/settings/profile"),
  updateConsent: (req: ConsentRequest) =>
    request<{ status: string }>("/settings/consent", {
      method: "POST",
      body: JSON.stringify(req),
    }),
};
