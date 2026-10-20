import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
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
  afterEach(() => vi.useRealTimers());

  it("runs project → upload → analysis polling → persisted findings → CSV in the production router", async () => {
    vi.useFakeTimers();
    vi.mocked(api.createProject).mockResolvedValue({ id: "project-live", name: "Motor", created_at: "now" });
    vi.mocked(api.uploadDrawing).mockResolvedValue({ id: "drawing-live", project_id: "project-live", sha256: "hash", drawing_type: "pdf", source_name: "motor.pdf" });
    vi.mocked(api.createAnalysis).mockResolvedValue({ id: "job-live", project_id: "project-live", drawing_id: "drawing-live", state: "queued", completed_steps: [], config_versions: {} });
    vi.mocked(api.getAnalysis)
      .mockResolvedValueOnce({ id: "job-live", project_id: "project-live", drawing_id: "drawing-live", state: "queued", completed_steps: [], config_versions: {} })
      .mockResolvedValueOnce({ id: "job-live", project_id: "project-live", drawing_id: "drawing-live", state: "running", completed_steps: ["validate"], config_versions: {} })
      .mockResolvedValueOnce({ id: "job-live", project_id: "project-live", drawing_id: "drawing-live", state: "completed", completed_steps: ["validate", "extract", "rules", "export_ready"], config_versions: {} });
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
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "검사 시작" }));
      for (let index = 0; index < 8; index += 1) await Promise.resolve();
    });
    expect(screen.getByText("대기 중 (Queued)")).toBeVisible();

    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    expect(screen.getByText("대기 중 (Queued)")).toBeVisible();
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    expect(screen.getByText("검사 실행 중 (Running)")).toBeVisible();
    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });

    expect(screen.getAllByText("실제 API finding입니다.")).toHaveLength(2);
    expect(screen.getByRole("tab", { name: "검토 결과" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("link", { name: "📥 CSV (.csv)" })).toHaveAttribute("href", "/api/analyses/job-live/export.csv");
    expect(api.createProject).toHaveBeenCalledWith({ name: "Motor" });
    expect(api.uploadDrawing).toHaveBeenCalledWith("project-live", expect.any(File));
    expect(api.createAnalysis).toHaveBeenCalledWith({ project_id: "project-live", drawing_id: "drawing-live" });
    expect(api.getAnalysis).toHaveBeenCalledTimes(3);
    expect(api.getFindings).toHaveBeenCalledWith("job-live");
    const invocation = (mock: unknown) => (mock as { mock: { invocationCallOrder: number[] } }).mock.invocationCallOrder;
    expect(invocation(api.createProject)[0]).toBeLessThan(invocation(api.uploadDrawing)[0]!);
    expect(invocation(api.uploadDrawing)[0]).toBeLessThan(invocation(api.createAnalysis)[0]!);
    expect(invocation(api.createAnalysis)[0]).toBeLessThan(invocation(api.getAnalysis)[0]!);
    expect(invocation(api.getAnalysis)[2]).toBeLessThan(invocation(api.getFindings)[0]!);
  });
});
