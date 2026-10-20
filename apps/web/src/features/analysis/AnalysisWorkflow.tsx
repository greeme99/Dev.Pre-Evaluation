import { useEffect, useRef, useState } from "react";
import type { AnalysisJobResponse, AnalysisStep, FindingsResponse, JobState } from "@dev-pre-review/contracts";
import { api } from "../../app/api";

interface Props {
  onComplete: (result: FindingsResponse) => void;
  pollIntervalMs?: number;
}

const MAX_POLL_ATTEMPTS = 120;
const POLL_INTERVAL_MS = 1000;
const TOTAL_STEPS: AnalysisStep[] = ["validate", "extract", "rules", "retrieve", "suggest", "export_ready"];
const TERMINAL_STATES: JobState[] = ["completed", "failed", "cancelled"];

const wait = (milliseconds: number) => new Promise<void>((resolve) => window.setTimeout(resolve, milliseconds));

export function AnalysisWorkflow({ onComplete, pollIntervalMs = POLL_INTERVAL_MS }: Props) {
  const [projectName, setProjectName] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [currentJob, setCurrentJob] = useState<AnalysisJobResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const pollRunRef = useRef(0);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const setJobIfMounted = (job: AnalysisJobResponse) => {
    if (mountedRef.current) setCurrentJob(job);
  };

  const pollUntilTerminal = async (initialJob: AnalysisJobResponse) => {
    const pollRun = ++pollRunRef.current;
    let job = initialJob;
    setIsPolling(true);
    setJobIfMounted(job);
    try {
      for (let attempt = 0; !TERMINAL_STATES.includes(job.state) && attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
        if (!mountedRef.current || pollRun !== pollRunRef.current) return;
        if (pollIntervalMs > 0) await wait(pollIntervalMs);
        if (!mountedRef.current || pollRun !== pollRunRef.current) return;
        job = await api.getAnalysis(job.id);
        if (pollRun !== pollRunRef.current) return;
        setJobIfMounted(job);
      }
      if (!mountedRef.current || pollRun !== pollRunRef.current) return;
      if (!TERMINAL_STATES.includes(job.state)) {
        throw new Error("검사 상태 확인 시간이 초과되었습니다. 작업 ID로 다시 확인해 주세요.");
      }
      if (job.state === "completed") {
        const result = await api.getFindings(job.id);
        if (mountedRef.current && pollRun === pollRunRef.current) onComplete(result);
      }
    } finally {
      if (mountedRef.current && pollRun === pollRunRef.current) setIsPolling(false);
    }
  };

  const handleStart = async () => {
    if (!selectedFile || !projectName.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const project = await api.createProject({ name: projectName.trim() });
      if (!mountedRef.current) return;
      const drawing = await api.uploadDrawing(project.id, selectedFile);
      if (!mountedRef.current) return;
      const job = await api.createAnalysis({ project_id: project.id, drawing_id: drawing.id });
      if (mountedRef.current) setLoading(false);
      await pollUntilTerminal(job);
    } catch (cause) {
      if (mountedRef.current) setError(cause instanceof Error ? cause.message : "검사를 시작하지 못했습니다.");
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  const handleCancel = async () => {
    if (!currentJob) return;
    pollRunRef.current += 1;
    setIsPolling(false);
    setLoading(true);
    setError(null);
    try {
      const updated = await api.cancelAnalysis(currentJob.id);
      setJobIfMounted(updated);
      if (!TERMINAL_STATES.includes(updated.state)) {
        if (mountedRef.current) setLoading(false);
        await pollUntilTerminal(updated);
      }
    } catch (cause) {
      if (mountedRef.current) {
        setError(cause instanceof Error ? cause.message : "검사를 중단하지 못했습니다.");
        try {
          const latest = await api.getAnalysis(currentJob.id);
          if (mountedRef.current) setLoading(false);
          await pollUntilTerminal(latest);
        } catch {
          // Keep the cancellation failure visible if resuming status polling also fails.
        }
      }
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  const handleRetry = async () => {
    if (!currentJob) return;
    setLoading(true);
    setError(null);
    try {
      const updated = await api.retryAnalysis(currentJob.id);
      if (mountedRef.current) setLoading(false);
      await pollUntilTerminal(updated);
    } catch (cause) {
      if (mountedRef.current) setError(cause instanceof Error ? cause.message : "검사를 다시 시작하지 못했습니다.");
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  };

  const getProgressPercentage = (job: AnalysisJobResponse) => {
    if (job.state === "completed") return 100;
    return Math.round((job.completed_steps.length / TOTAL_STEPS.length) * 100);
  };

  const getStateBadgeClass = (state: JobState) => {
    switch (state) {
      case "completed": return "badge-success";
      case "running": return "badge-primary";
      case "queued": return "badge-info";
      case "failed": return "badge-danger";
      case "cancelling":
      case "cancelled": return "badge-warning";
    }
  };

  const getStateLabel = (state: JobState) => {
    switch (state) {
      case "queued": return "대기 중 (Queued)";
      case "running": return "검사 실행 중 (Running)";
      case "completed": return "검사 완료 (Completed)";
      case "failed": return "검사 실패 (Failed)";
      case "cancelling": return "취소 처리 중 (Cancelling)";
      case "cancelled": return "취소됨 (Cancelled)";
    }
  };

  return (
    <section className="analysis-workflow-panel" aria-labelledby="analysis-workflow-title">
      <h2 id="analysis-workflow-title">도면 검사 실행 및 진행 상태</h2>

      <div className="drawing-selector-group">
        <label htmlFor="project-name">프로젝트 이름:</label>
        <input
          id="project-name"
          type="text"
          value={projectName}
          onChange={(event) => setProjectName(event.target.value)}
          disabled={loading || isPolling}
          required
        />
        <label htmlFor="drawing-file">PDF 또는 DXF 도면:</label>
        <input
          id="drawing-file"
          type="file"
          accept=".pdf,.dxf,application/pdf,application/dxf"
          onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
          disabled={loading || isPolling}
          required
        />
        <button
          type="button"
          onClick={handleStart}
          disabled={loading || isPolling || currentJob?.state === "queued" || currentJob?.state === "running" || currentJob?.state === "cancelling" || !projectName.trim() || !selectedFile}
          className="btn btn-primary"
        >
          검사 시작
        </button>
      </div>

      {error && <div className="error-banner" role="alert">{error}</div>}

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
            <div className="progress-bar" role="progressbar" aria-valuenow={getProgressPercentage(currentJob)} aria-valuemin={0} aria-valuemax={100}>
              <div className="progress-bar-fill" style={{ width: `${getProgressPercentage(currentJob)}%` }} />
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
                    <span className="step-name">{step.toUpperCase()}</span>: {isCompleted ? "완료" : isFailed ? "실패" : "대기"}
                  </li>
                );
              })}
            </ul>
          </div>

          {currentJob.error_code && <div className="error-banner" role="alert">오류 발생: <strong>{currentJob.error_code}</strong></div>}

          <div className="job-actions">
            {(currentJob.state === "running" || currentJob.state === "queued") && (
              <button type="button" onClick={handleCancel} disabled={loading} className="btn btn-warning">검사 중단</button>
            )}
            {(currentJob.state === "failed" || currentJob.state === "cancelled") && (
              <button type="button" onClick={handleRetry} disabled={loading} className="btn btn-secondary">다시 시도</button>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
