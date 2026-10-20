import { useState } from "react";
import type { Finding, FindingStatus, ImprovementSuggestion } from "@dev-pre-review/contracts";

interface Props {
  jobId: string;
  findings: Finding[];
  suggestions: ImprovementSuggestion[];
}

export function FindingsViewer({ jobId, findings, suggestions }: Props) {
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(findings[0]?.id ?? null);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const selectedFinding = findings.find((finding) => finding.id === selectedFindingId) ?? findings[0];
  const selectedSuggestion = suggestions.find((suggestion) => suggestion.finding_id === selectedFinding?.id);
  const filteredFindings = findings.filter((finding) => statusFilter === "ALL" || finding.status.toUpperCase() === statusFilter);

  const getStatusBadge = (status: FindingStatus) => {
    switch (status) {
      case "violation":
        return <span className="badge badge-danger">❌ 위반 (Violation)</span>;
      case "suspected":
        return <span className="badge badge-warning">⚠️ 의심 (Suspected)</span>;
      case "insufficient_information":
        return <span className="badge badge-warning">⚠️ 정보 부족 (Insufficient)</span>;
    }
  };

  const bbox = selectedFinding?.pixel_bbox ?? selectedFinding?.cad_bbox;

  return (
    <section className="findings-viewer-panel" aria-labelledby="findings-viewer-title">
      <div className="viewer-header">
        <h2 id="findings-viewer-title">도면 검토 결과 및 근거 분석</h2>
        <div className="filter-group">
          <label htmlFor="findings-filter">판정 필터:</label>
          <select id="findings-filter" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
            <option value="ALL">전체 결과</option>
            <option value="VIOLATION">위반 사항만</option>
            <option value="SUSPECTED">의심 항목만</option>
            <option value="INSUFFICIENT_INFORMATION">정보 부족만</option>
          </select>
          <div className="export-actions">
            <a href={`/api/analyses/${jobId}/export.csv`} download className="btn btn-sm btn-secondary">
              📥 CSV (.csv)
            </a>
          </div>
        </div>
      </div>

      <div className="findings-layout">
        <div className="findings-sidebar" aria-label="검토 결과 목록">
          <h3>검토 항목 ({filteredFindings.length}건)</h3>
          {filteredFindings.length > 0 ? (
            <ul className="findings-list">
              {filteredFindings.map((finding) => {
                const isSelected = finding.id === selectedFinding?.id;
                return (
                  <li key={finding.id ?? `${finding.job_id}-${finding.finding_type}`}>
                    <button
                      type="button"
                      className={`finding-card-btn ${isSelected ? "selected" : ""}`}
                      onClick={() => setSelectedFindingId(finding.id ?? null)}
                      aria-pressed={isSelected}
                    >
                      <div className="card-top">
                        <span className="rule-code">{finding.finding_type}</span>
                        {getStatusBadge(finding.status)}
                      </div>
                      <p className="finding-msg">{finding.message}</p>
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : <p className="text-muted">저장된 검토 결과가 없습니다.</p>}
        </div>

        <div className="drawing-canvas-area" aria-label="도면 시각화 영역">
          <h3>도면 하이라이트</h3>
          <div className="canvas-wrapper">
            <div className="drawing-viewport">
              <div className="mock-canvas" role="img" aria-label="도면 렌더링 화면">
                <span className="drawing-placeholder-text">도면 뷰어 (PDF/DXF)</span>
                {bbox && (
                  <div
                    className="highlight-box"
                    aria-label={`좌표 하이라이트 영역 x0:${bbox[0]}, y0:${bbox[1]}`}
                    style={{ left: `${bbox[0]}%`, top: `${bbox[1]}%`, width: `${bbox[2] - bbox[0]}%`, height: `${bbox[3] - bbox[1]}%` }}
                  >
                    <span className="box-tag">{selectedFinding?.finding_type}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="evidence-panel" aria-label="근거 및 개선 제안 패널">
          {selectedFinding ? (
            <div className="detail-content">
              <h3>판정 상세 정보</h3>
              <div className="info-row"><span className="label">유형:</span><span>{selectedFinding.finding_type}</span></div>
              <div className="info-row"><span className="label">위치:</span><span>{selectedFinding.location}</span></div>
              <div className="info-row"><span className="label">상태:</span><span>{getStatusBadge(selectedFinding.status)}</span></div>
              <div className="info-row">
                <span className="label">심각도:</span>
                <span className={`badge severity-${selectedFinding.severity}`}>{selectedFinding.severity.toUpperCase()}</span>
              </div>
              <div className="info-row"><span className="label">신뢰도:</span><span>{Math.round(selectedFinding.confidence * 100)}%</span></div>
              <p className="detail-message">{selectedFinding.message}</p>

              <hr />

              <h4>근거 항목 (Evidence):</h4>
              {(selectedFinding.evidence?.length ?? 0) > 0 ? (
                <ul className="evidence-list">
                  {selectedFinding.evidence!.map((evidence, index) => (
                    <li key={`${evidence.ref_id}-${index}`} className="evidence-item">
                      <span className="badge badge-secondary">{evidence.kind.toUpperCase()}</span>
                      <span className="evidence-ref">{evidence.ref_id}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-muted">등록된 근거가 없습니다.</p>}

              {selectedSuggestion && (
                <div className="suggestion-box">
                  <h4>개선 제안:</h4>
                  <p className="suggested-action"><strong>조치 제안:</strong> {selectedSuggestion.recommendation}</p>
                  <p className="rationale"><strong>문제:</strong> {selectedSuggestion.issue}</p>
                  <p><strong>위치:</strong> {selectedSuggestion.location}</p>
                  <p><strong>검증 조건:</strong> {selectedSuggestion.verification_condition}</p>
                </div>
              )}
            </div>
          ) : <p className="text-muted">선택된 검토 결과가 없습니다.</p>}
        </div>
      </div>
    </section>
  );
}
