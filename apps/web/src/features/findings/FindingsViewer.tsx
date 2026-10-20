import { useState } from "react";
import type { Finding, FindingStatus, ImprovementSuggestion } from "@dev-pre-review/contracts";

interface Props {
  findings: Finding[];
  suggestions: ImprovementSuggestion[];
  drawingImageUrl?: string;
}

export function FindingsViewer({
  findings,
  suggestions,
  drawingImageUrl = "/mock-drawing.png",
}: Props) {
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(
    findings[0]?.id ?? null
  );
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const selectedFinding = findings.find((f) => f.id === selectedFindingId) ?? findings[0];
  const selectedSuggestion = suggestions.find((s) => s.finding_id === selectedFinding?.id);

  const filteredFindings = findings.filter((f) => {
    if (statusFilter === "ALL") return true;
    return f.status.toUpperCase() === statusFilter;
  });

  const getStatusBadge = (status: FindingStatus) => {
    switch (status) {
      case "violation":
        return <span className="badge badge-danger">❌ 위반 (Violation)</span>;
      case "compliant":
        return <span className="badge badge-success">✅ 준수 (Compliant)</span>;
      case "insufficient_information":
        return <span className="badge badge-warning">⚠️ 정보 부족 (Insufficient)</span>;
    }
  };

  return (
    <section className="findings-viewer-panel" aria-labelledby="findings-viewer-title">
      <div className="viewer-header">
        <h2 id="findings-viewer-title">도면 검토 결과 및 근거 분석</h2>
        <div className="filter-group">
          <label htmlFor="findings-filter">판정 필터:</label>
          <select
            id="findings-filter"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">전체 결과</option>
            <option value="VIOLATION">위반 사항만</option>
            <option value="COMPLIANT">준수 항목만</option>
            <option value="INSUFFICIENT_INFORMATION">정보 부족만</option>
          </select>
        </div>
      </div>

      <div className="findings-layout">
        {/* Left: Findings List */}
        <div className="findings-sidebar" aria-label="검토 결과 목록">
          <h3>검토 항목 ({filteredFindings.length}건)</h3>
          <ul className="findings-list">
            {filteredFindings.map((finding) => {
              const isSelected = finding.id === selectedFinding?.id;
              return (
                <li key={finding.id}>
                  <button
                    type="button"
                    className={`finding-card-btn ${isSelected ? "selected" : ""}`}
                    onClick={() => setSelectedFindingId(finding.id)}
                    aria-pressed={isSelected}
                  >
                    <div className="card-top">
                      <span className="rule-code">{finding.rule_code}</span>
                      {getStatusBadge(finding.status)}
                    </div>
                    <p className="finding-msg">{finding.message}</p>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Center: Drawing Canvas with BoundingBox overlay */}
        <div className="drawing-canvas-area" aria-label="도면 시각화 영역">
          <h3>도면 하이라이트</h3>
          <div className="canvas-wrapper">
            <div className="drawing-viewport">
              <div
                className="mock-canvas"
                role="img"
                aria-label="도면 렌더링 화면"
                data-drawing-src={drawingImageUrl}
              >
                <span className="drawing-placeholder-text">도면 뷰어 (PDF/DXF)</span>
                {selectedFinding?.bbox && (
                  <div
                    className="highlight-box"
                    aria-label={`좌표 하이라이트 영역 x0:${selectedFinding.bbox.x0}, y0:${selectedFinding.bbox.y0}`}
                    style={{
                      left: `${selectedFinding.bbox.x0}%`,
                      top: `${selectedFinding.bbox.y0}%`,
                      width: `${selectedFinding.bbox.x1 - selectedFinding.bbox.x0}%`,
                      height: `${selectedFinding.bbox.y1 - selectedFinding.bbox.y0}%`,
                    }}
                  >
                    <span className="box-tag">{selectedFinding.rule_code}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Right: Evidence & Suggestion Detail Panel */}
        <div className="evidence-panel" aria-label="근거 및 개선 제안 패널">
          {selectedFinding ? (
            <div className="detail-content">
              <h3>판정 상세 정보</h3>
              <div className="info-row">
                <span className="label">규칙 코드:</span>
                <span>{selectedFinding.rule_code}</span>
              </div>
              <div className="info-row">
                <span className="label">상태:</span>
                <span>{getStatusBadge(selectedFinding.status)}</span>
              </div>
              <div className="info-row">
                <span className="label">심각도:</span>
                <span className={`badge severity-${selectedFinding.severity}`}>
                  {selectedFinding.severity.toUpperCase()}
                </span>
              </div>
              <p className="detail-message">{selectedFinding.message}</p>

              <hr />

              <h4>근거 항목 (Evidences):</h4>
              <ul className="evidence-list">
                {selectedFinding.evidences.map((ev, idx) => (
                  <li key={idx} className="evidence-item">
                    <span className="badge badge-secondary">{ev.kind.toUpperCase()}</span>
                    <span className="evidence-ref">{ev.ref_id}</span>
                  </li>
                ))}
              </ul>

              {selectedSuggestion && (
                <div className="suggestion-box">
                  <h4>개선 제안 (AI / Local Rule):</h4>
                  <p className="suggested-action">
                    <strong>조치 제안:</strong> {selectedSuggestion.suggested_action}
                  </p>
                  <p className="rationale">
                    <strong>근거 이유:</strong> {selectedSuggestion.rationale}
                  </p>
                  {selectedSuggestion.new_rule_candidate && (
                    <div className="candidate-rule-box">
                      <span className="badge badge-info">DRAFT 새 규칙 후보</span>
                      <pre>
                        {JSON.stringify(selectedSuggestion.new_rule_candidate, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <p className="text-muted">선택된 검토 결과가 없습니다.</p>
          )}
        </div>
      </div>
    </section>
  );
}
