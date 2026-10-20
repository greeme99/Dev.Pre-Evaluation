import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";
import { AppRouter } from "./router";

vi.mock("./api", () => ({
  api: {
    createProject: vi.fn(),
    uploadDrawing: vi.fn(),
    createAnalysis: vi.fn(),
    getAnalysis: vi.fn(),
    getFindings: vi.fn(),
    cancelAnalysis: vi.fn(),
    retryAnalysis: vi.fn(),
  },
}));

describe("production workflow router", () => {
  beforeEach(() => vi.clearAllMocks());

  it("shows only real workflow tabs and opens persisted results with the returned job ID", async () => {
    vi.mocked(api.createProject).mockResolvedValue({ id: "project-live", name: "Motor", created_at: "now" });
    vi.mocked(api.uploadDrawing).mockResolvedValue({ id: "drawing-live", project_id: "project-live", sha256: "hash", drawing_type: "pdf", source_name: "motor.pdf" });
    vi.mocked(api.createAnalysis).mockResolvedValue({ id: "job-live", project_id: "project-live", drawing_id: "drawing-live", state: "completed", completed_steps: ["validate", "extract", "rules", "export_ready"], config_versions: {} });
    vi.mocked(api.getFindings).mockResolvedValue({
      job_id: "job-live",
      findings: [{
        id: "finding-live", job_id: "job-live", finding_type: "dimension", status: "violation", severity: "high", confidence: 0.9,
        location: "페이지 1", message: "실제 API finding입니다.", pixel_bbox: [1, 2, 3, 4], evidence: [],
      }],
      suggestions: [],
    });

    render(<AppRouter />);
    expect(screen.getAllByRole("tab")).toHaveLength(1);
    expect(screen.queryByRole("tab", { name: "지식 가져오기" })).not.toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "규칙 카탈로그" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("프로젝트 이름:"), { target: { value: "Motor" } });
    fireEvent.change(screen.getByLabelText("PDF 또는 DXF 도면:"), {
      target: { files: [new File(["pdf"], "motor.pdf", { type: "application/pdf" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "검사 시작" }));

    await waitFor(() => expect(screen.getAllByText("실제 API finding입니다.")).toHaveLength(2));
    expect(screen.getByRole("tab", { name: "검토 결과" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("link", { name: "📥 CSV (.csv)" })).toHaveAttribute("href", "/api/analyses/job-live/export.csv");
    expect(api.getFindings).toHaveBeenCalledWith("job-live");
  });
});
