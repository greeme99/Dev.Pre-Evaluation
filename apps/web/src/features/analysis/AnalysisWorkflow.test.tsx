import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AnalysisJobResponse } from "@dev-pre-review/contracts";
import { AnalysisWorkflow } from "./AnalysisWorkflow";

const runningJob: AnalysisJobResponse = {
  id: "job-run-123",
  project_id: "proj-1",
  drawing_id: "draw-001",
  state: "running",
  completed_steps: ["extract", "retrieve"],
  failed_step: null,
  error_code: null,
  config_versions: {},
};

const failedJob: AnalysisJobResponse = {
  id: "job-fail-123",
  project_id: "proj-1",
  drawing_id: "draw-001",
  state: "failed",
  completed_steps: ["extract"],
  failed_step: "retrieve",
  error_code: "ERR_RETRIEVAL_TIMEOUT",
  config_versions: {},
};

describe("AnalysisWorkflow", () => {
  it("renders running state and allows cancel", () => {
    const handleCancel = vi.fn().mockResolvedValue({ ...runningJob, state: "cancelled" });
    render(
      <AnalysisWorkflow
        projectId="proj-1"
        initialJob={runningJob}
        onCancelAnalysis={handleCancel}
      />
    );

    expect(screen.getByRole("heading", { name: "도면 검사 실행 및 진행 상태" })).toBeVisible();
    expect(screen.getByText("검사 실행 중 (Running)")).toBeVisible();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");

    const cancelBtn = screen.getByRole("button", { name: "검사 중단" });
    fireEvent.click(cancelBtn);
    expect(handleCancel).toHaveBeenCalledWith("job-run-123");
  });

  it("renders failed state and allows retry", () => {
    const handleRetry = vi.fn().mockResolvedValue({ ...failedJob, state: "queued" });
    render(
      <AnalysisWorkflow
        projectId="proj-1"
        initialJob={failedJob}
        onRetryAnalysis={handleRetry}
      />
    );

    expect(screen.getByText("검사 실패 (Failed)")).toBeVisible();
    expect(screen.getByText("ERR_RETRIEVAL_TIMEOUT")).toBeVisible();

    const retryBtn = screen.getByRole("button", { name: "다시 시도" });
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalledWith("job-fail-123");
  });
});
