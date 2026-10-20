import { useState } from "react";
import type { AnalysisJobResponse, JobState } from "@dev-pre-review/contracts";

interface Props {
  projectId: string;
  onStartAnalysis?: (drawingId: string) => Promise<AnalysisJobResponse>;
  onCancelAnalysis?: (jobId: string) => Promise<AnalysisJobResponse>;
  onRetryAnalysis?: (jobId: string) => Promise<AnalysisJobResponse>;
  initialJob?: AnalysisJobResponse | null;
}

const TOTAL_STEPS = ["extract", "retrieve", "evaluate", "generate"];

export function AnalysisWorkflow({
  projectId,
  onStartAnalysis,
  onCancelAnalysis,
  onRetryAnalysis,
  initialJob = null,
}: Props) {
  const [currentJob, setCurrentJob] = useState<AnalysisJobResponse | null>(initialJob);
  const [selectedDrawing, setSelectedDrawing] = useState<string>("draw-001");
  const [loading, setLoading] = useState(false);

  const handleStart = async () => {
    setLoading(true);
    try {
      if (onStartAnalysis) {
        const job = await onStartAnalysis(selectedDrawing);
        setCurrentJob(job);
      } else {
        // Mock fallback for standalone testing
        setCurrentJob({
          id: "job-test-1",
          project_id: projectId,
          drawing_id: selectedDrawing,
          state: "running",
          completed_steps: ["extract"],
          failed_step: null,
          error_code: null,
          config_versions: {},
        });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!currentJob) return;
    setLoading(true);
    try {
      if (onCancelAnalysis) {
        const updated = await onCancelAnalysis(currentJob.id);
        setCurrentJob(updated);
      } else {
        setCurrentJob({ ...currentJob, state: "cancelled" });
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!currentJob) return;
    setLoading(true);
    try {
      if (onRetryAnalysis) {
        const updated = await onRetryAnalysis(currentJob.id);
        setCurrentJob(updated);
      } else {
        setCurrentJob({ ...currentJob, state: "queued", error_code: null, failed_step: null });
      }
    } finally {
      setLoading(false);
    }
  };

  const getProgressPercentage = (job: AnalysisJobResponse) => {
    if (job.state === "completed") return 100;
    const completedCount = job.completed_steps.length;
    return Math.round((completedCount / TOTAL_STEPS.length) * 100);
  };

  const getStateBadgeClass = (state: JobState) => {
    switch (state) {
      case "completed":
        return "badge-success";
      case "running":
        return "badge-primary";
      case "queued":
        return "badge-info";
      case "failed":
        return "badge-danger";
      case "cancelling":
      case "cancelled":
        return "badge-warning";
    }
  };

  const getStateLabel = (state: JobState) => {
    switch (state) {
      case "queued":
        return "대기 중 (Queued)";
      case "running":
        return "검사 실행 중 (Running)";
      case "completed":
        return "검사 완료 (Completed)";
      case "failed":
        return "검사 실패 (Failed)";
      case "cancelling":
        return "취소 처리 중 (Cancelling)";
      case "cancelled":
        return "취소됨 (Cancelled)";
    }
  };

  return (
    <section className="analysis-workflow-panel" aria-labelledby="analysis-workflow-title">
      <h2 id="analysis-workflow-title">도면 검사 실행 및 진행 상태</h2>

      <div className="drawing-selector-group">
        <label htmlFor="drawing-select">검토 대상 도면 선택:</label>
        <select
          id="drawing-select"
          value={selectedDrawing}
          onChange={(e) => setSelectedDrawing(e.target.value)}
          disabled={loading || currentJob?.state === "running"}
        >
          <option value="draw-001">sample_motor_shaft.pdf</option>
          <option value="draw-002">bracket_assembly.dxf</option>
        </select>
        <button
          type="button"
          onClick={handleStart}
          disabled={loading || currentJob?.state === "running"}
          className="btn btn-primary"
        >
          검사 시작
        </button>
      </div>

      {currentJob && (
        <div className="job-status-card" aria-label="검사 작업 상태">
          <div className="job-header">
            <div>
              <h3>작업 ID: {currentJob.id}</h3>
              <p>도면: {currentJob.drawing_id}</p>
            </div>
            <span className={`badge ${getStateBadgeClass(currentJob.state)}`}>
              {getStateLabel(currentJob.state)}
            </span>
          </div>

          <div className="progress-container">
            <div className="progress-bar-label">
              <span>진행률</span>
              <span>{getProgressPercentage(currentJob)}%</span>
            </div>
            <div
              className="progress-bar"
              role="progressbar"
              aria-valuenow={getProgressPercentage(currentJob)}
              aria-valuemin={0}
              aria-valuemax={100}
            >
              <div
                className="progress-bar-fill"
                style={{ width: `${getProgressPercentage(currentJob)}%` }}
              />
            </div>
          </div>

          <div className="steps-tracker">
            <h4>단계별 진행 상황:</h4>
            <ul>
              {TOTAL_STEPS.map((step) => {
                const isCompleted = currentJob.completed_steps.includes(step);
                const isFailed = currentJob.failed_step === step;
                return (
                  <li key={step} className={`step-item ${isCompleted ? "done" : isFailed ? "failed" : ""}`}>
                    <span className="step-name">{step.toUpperCase()}</span>:{" "}
                    {isCompleted ? "완료" : isFailed ? "실패" : "대기"}
                  </li>
                );
              })}
            </ul>
          </div>

          {currentJob.error_code && (
            <div className="error-banner" role="alert">
              오류 발생: <strong>{currentJob.error_code}</strong>
            </div>
          )}

          <div className="job-actions">
            {(currentJob.state === "running" || currentJob.state === "queued") && (
              <button
                type="button"
                onClick={handleCancel}
                disabled={loading}
                className="btn btn-warning"
              >
                검사 중단
              </button>
            )}
            {(currentJob.state === "failed" || currentJob.state === "cancelled") && (
              <button
                type="button"
                onClick={handleRetry}
                disabled={loading}
                className="btn btn-secondary"
              >
                다시 시도
              </button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
