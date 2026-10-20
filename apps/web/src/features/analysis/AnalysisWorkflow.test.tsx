import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { FindingsResponse } from "@dev-pre-review/contracts";
import { api } from "../../app/api";
import { AnalysisWorkflow } from "./AnalysisWorkflow";

vi.mock("../../app/api", () => ({
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

const findingResult: FindingsResponse = {
  job_id: "job-real-42",
  findings: [
    {
      id: "finding-real-1",
      job_id: "job-real-42",
      finding_type: "dimension",
      status: "violation",
      severity: "high",
      confidence: 0.97,
      location: "페이지 1 / 축 외경",
      message: "축 외경이 최소 기준보다 작습니다.",
      pixel_bbox: [12, 20, 42, 48],
      evidence: [{ kind: "rule", ref_id: "RULE-001" }],
    },
  ],
  suggestions: [],
};

const callOrder = (mock: unknown) =>
  (mock as { mock: { invocationCallOrder: number[] } }).mock.invocationCallOrder[0]!;

describe("AnalysisWorkflow", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.useRealTimers());

  it("creates, uploads, analyzes, polls, and returns persisted findings in order", async () => {
    vi.mocked(api.createProject).mockResolvedValue({ id: "project-real-7", name: "Axle" , created_at: "now" });
    vi.mocked(api.uploadDrawing).mockResolvedValue({
      id: "drawing-real-8", project_id: "project-real-7", sha256: "hash", drawing_type: "pdf", source_name: "shaft.pdf",
    });
    vi.mocked(api.createAnalysis).mockResolvedValue({
      id: "job-real-42", project_id: "project-real-7", drawing_id: "drawing-real-8", state: "queued", completed_steps: [], config_versions: {},
    });
    vi.mocked(api.getAnalysis)
      .mockResolvedValueOnce({ id: "job-real-42", project_id: "project-real-7", drawing_id: "drawing-real-8", state: "queued", completed_steps: [], config_versions: {} })
      .mockResolvedValueOnce({ id: "job-real-42", project_id: "project-real-7", drawing_id: "drawing-real-8", state: "running", completed_steps: ["validate"], config_versions: {} })
      .mockResolvedValueOnce({ id: "job-real-42", project_id: "project-real-7", drawing_id: "drawing-real-8", state: "completed", completed_steps: ["validate", "extract", "rules", "export_ready"], config_versions: {} });
    vi.mocked(api.getFindings).mockResolvedValue(findingResult);
    const onComplete = vi.fn();

    render(<AnalysisWorkflow onComplete={onComplete} pollIntervalMs={0} />);
    fireEvent.change(screen.getByLabelText("프로젝트 이름:"), { target: { value: "Axle" } });
    const file = new File(["%PDF-1.4"], "shaft.pdf", { type: "application/pdf" });
    fireEvent.change(screen.getByLabelText("PDF 또는 DXF 도면:"), { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: "검사 시작" }));

    await waitFor(() => expect(onComplete).toHaveBeenCalledWith(findingResult));
    expect(api.createProject).toHaveBeenCalledWith({ name: "Axle" });
    expect(api.uploadDrawing).toHaveBeenCalledWith("project-real-7", file);
    expect(api.createAnalysis).toHaveBeenCalledWith({ project_id: "project-real-7", drawing_id: "drawing-real-8" });
    expect(api.getAnalysis).toHaveBeenCalledTimes(3);
    expect(api.getFindings).toHaveBeenCalledWith("job-real-42");
    expect(callOrder(api.createProject)).toBeLessThan(callOrder(api.uploadDrawing));
    expect(callOrder(api.uploadDrawing)).toBeLessThan(callOrder(api.createAnalysis));
    expect(callOrder(api.createAnalysis)).toBeLessThan(callOrder(api.getAnalysis));
    expect((api.getAnalysis as unknown as { mock: { invocationCallOrder: number[] } }).mock.invocationCallOrder[2])
      .toBeLessThan(callOrder(api.getFindings));
  });

  it("surfaces API errors without reporting successful completion", async () => {
    vi.mocked(api.createProject).mockRejectedValue(new Error("프로젝트 생성 실패"));
    const onComplete = vi.fn();
    render(<AnalysisWorkflow onComplete={onComplete} pollIntervalMs={0} />);
    fireEvent.change(screen.getByLabelText("프로젝트 이름:"), { target: { value: "Axle" } });
    fireEvent.change(screen.getByLabelText("PDF 또는 DXF 도면:"), {
      target: { files: [new File(["x"], "shaft.pdf", { type: "application/pdf" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "검사 시작" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("프로젝트 생성 실패");
    expect(onComplete).not.toHaveBeenCalled();
  });

  it("keeps cancellation available during polling and ignores stale poll results", async () => {
    vi.useFakeTimers();
    vi.mocked(api.createProject).mockResolvedValue({ id: "project-cancel", name: "Axle", created_at: "now" });
    vi.mocked(api.uploadDrawing).mockResolvedValue({ id: "drawing-cancel", project_id: "project-cancel", sha256: "hash", drawing_type: "pdf", source_name: "shaft.pdf" });
    vi.mocked(api.createAnalysis).mockResolvedValue({ id: "job-cancel", project_id: "project-cancel", drawing_id: "drawing-cancel", state: "queued", completed_steps: [], config_versions: {} });
    vi.mocked(api.cancelAnalysis).mockResolvedValue({ id: "job-cancel", project_id: "project-cancel", drawing_id: "drawing-cancel", state: "cancelling", completed_steps: [], config_versions: {} });
    vi.mocked(api.getAnalysis).mockResolvedValue({ id: "job-cancel", project_id: "project-cancel", drawing_id: "drawing-cancel", state: "cancelled", completed_steps: [], config_versions: {} });
    const file = new File(["x"], "shaft.pdf", { type: "application/pdf" });

    render(<AnalysisWorkflow onComplete={vi.fn()} />);
    fireEvent.change(screen.getByLabelText("프로젝트 이름:"), { target: { value: "Axle" } });
    fireEvent.change(screen.getByLabelText("PDF 또는 DXF 도면:"), { target: { files: [file] } });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "검사 시작" }));
      for (let index = 0; index < 8; index += 1) await Promise.resolve();
    });

    const cancel = screen.getByRole("button", { name: "검사 중단" });
    expect(cancel).toBeEnabled();
    await act(async () => {
      fireEvent.click(cancel);
      for (let index = 0; index < 5; index += 1) await Promise.resolve();
    });
    expect(api.cancelAnalysis).toHaveBeenCalledWith("job-cancel");
    expect(screen.getByText("취소 처리 중 (Cancelling)")).toBeVisible();
    expect(api.getAnalysis).not.toHaveBeenCalled();

    await act(async () => { await vi.advanceTimersByTimeAsync(1_000); });
    expect(screen.getByText("취소됨 (Cancelled)")).toBeVisible();

    await act(async () => { await vi.advanceTimersByTimeAsync(2_000); });
    expect(api.getAnalysis).toHaveBeenCalledTimes(1);
  });

  it("uses the real retry API and polls that retry without duplicate analysis requests", async () => {
    vi.mocked(api.createProject).mockResolvedValue({ id: "project-retry", name: "Axle", created_at: "now" });
    vi.mocked(api.uploadDrawing).mockResolvedValue({ id: "drawing-retry", project_id: "project-retry", sha256: "hash", drawing_type: "pdf", source_name: "shaft.pdf" });
    vi.mocked(api.createAnalysis).mockResolvedValue({ id: "job-retry", project_id: "project-retry", drawing_id: "drawing-retry", state: "failed", completed_steps: ["validate"], failed_step: "extract", config_versions: {} });
    vi.mocked(api.retryAnalysis).mockResolvedValue({ id: "job-retry", project_id: "project-retry", drawing_id: "drawing-retry", state: "queued", completed_steps: [], config_versions: {} });
    vi.mocked(api.getAnalysis).mockResolvedValue({ id: "job-retry", project_id: "project-retry", drawing_id: "drawing-retry", state: "completed", completed_steps: ["validate", "extract", "rules", "export_ready"], config_versions: {} });
    vi.mocked(api.getFindings).mockResolvedValue(findingResult);
    const onComplete = vi.fn();

    render(<AnalysisWorkflow onComplete={onComplete} pollIntervalMs={0} />);
    fireEvent.change(screen.getByLabelText("프로젝트 이름:"), { target: { value: "Axle" } });
    fireEvent.change(screen.getByLabelText("PDF 또는 DXF 도면:"), {
      target: { files: [new File(["x"], "shaft.pdf", { type: "application/pdf" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "검사 시작" }));
    const retry = await screen.findByRole("button", { name: "다시 시도" });
    fireEvent.click(retry);

    await waitFor(() => expect(onComplete).toHaveBeenCalledWith(findingResult));
    expect(api.retryAnalysis).toHaveBeenCalledTimes(1);
    expect(api.getAnalysis).toHaveBeenCalledTimes(1);
    expect(api.createAnalysis).toHaveBeenCalledTimes(1);
  });

  it("passes an empty real findings response through unchanged", async () => {
    const emptyResult: FindingsResponse = { job_id: "job-empty", findings: [], suggestions: [] };
    vi.mocked(api.createProject).mockResolvedValue({ id: "project-1", name: "Empty", created_at: "now" });
    vi.mocked(api.uploadDrawing).mockResolvedValue({ id: "drawing-1", project_id: "project-1", sha256: "hash", drawing_type: "dxf", source_name: "empty.dxf" });
    vi.mocked(api.createAnalysis).mockResolvedValue({ id: "job-empty", project_id: "project-1", drawing_id: "drawing-1", state: "completed", completed_steps: ["validate", "extract", "rules", "export_ready"], config_versions: {} });
    vi.mocked(api.getFindings).mockResolvedValue(emptyResult);
    const onComplete = vi.fn();

    render(<AnalysisWorkflow onComplete={onComplete} pollIntervalMs={0} />);
    fireEvent.change(screen.getByLabelText("프로젝트 이름:"), { target: { value: "Empty" } });
    fireEvent.change(screen.getByLabelText("PDF 또는 DXF 도면:"), {
      target: { files: [new File(["x"], "empty.dxf", { type: "application/dxf" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "검사 시작" }));

    await waitFor(() => expect(onComplete).toHaveBeenCalledWith(emptyResult));
  });
});
