import { useState } from "react";
import type { ImportPreviewResponse } from "@dev-pre-review/contracts";

interface Props {
  projectId: string;
  onCommitSuccess?: (count: number) => void;
}

export function KnowledgeImport({ projectId, onCommitSuccess }: Props) {
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreviewResponse | null>(null);
  const [isCommitting, setIsCommitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const handleSimulatePreview = () => {
    if (!selectedFile) return;
    // Mock/Simulated preview data for UI workflow
    setPreview({
      preview_id: `prev-${projectId.slice(0, 4)}`,
      filename: selectedFile,
      total_rows: 3,
      valid_count: 2,
      warning_count: 1,
      invalid_count: 0,
      rows: [
        {
          row_number: 1,
          category: "치수",
          raw_content: "외경 허용 오차는 ±0.05 이내일 것",
          extracted_rule_code: "DIM-001",
          validation_status: "valid",
          message: "정상 파싱됨",
        },
        {
          row_number: 2,
          category: "표면조도",
          raw_content: "조도 Ra 0.8 이하",
          extracted_rule_code: "SURF-002",
          validation_status: "valid",
          message: "정상 파싱됨",
        },
        {
          row_number: 3,
          category: "재질",
          raw_content: "SUS304 또는 동등 이상",
          extracted_rule_code: null,
          validation_status: "warning",
          message: "단위 또는 연산자 미지정",
        },
      ],
    });
    setStatusMessage("미리보기를 불러왔습니다.");
  };

  const handleCommit = async () => {
    if (!preview) return;
    setIsCommitting(true);
    setStatusMessage("지식을 확정 등록 중입니다...");
    try {
      // Mock / Commit API logic
      const committedCount = preview.valid_count;
      setStatusMessage(`${committedCount}개 규칙이 성공적으로 등록되었습니다.`);
      onCommitSuccess?.(committedCount);
      setPreview(null);
      setSelectedFile(null);
    } finally {
      setIsCommitting(false);
    }
  };

  return (
    <section className="knowledge-import-panel" aria-labelledby="knowledge-import-title">
      <h2 id="knowledge-import-title">지식 및 규칙 가져오기</h2>
      <p className="description">
        검토 기준 Excel 문서를 업로드하여 규칙 후보를 미리보고 확정합니다.
      </p>

      <div className="file-input-group">
        <label htmlFor="file-upload">규칙 엑셀 파일 선택</label>
        <input
          id="file-upload"
          type="file"
          accept=".xlsx,.xls,.csv"
          onChange={(e) => {
            const file = e.target.files?.[0];
            setSelectedFile(file ? file.name : null);
          }}
        />
        <button
          type="button"
          disabled={!selectedFile}
          onClick={handleSimulatePreview}
          className="btn btn-secondary"
        >
          미리보기 불러오기
        </button>
      </div>

      {statusMessage && (
        <div className="status-banner" role="status" aria-live="polite">
          {statusMessage}
        </div>
      )}

      {preview && (
        <div className="preview-container">
          <div className="preview-summary">
            <span>총 {preview.total_rows}건</span>
            <span className="badge badge-success">유효 {preview.valid_count}건</span>
            <span className="badge badge-warning">경고 {preview.warning_count}건</span>
            <span className="badge badge-danger">오류 {preview.invalid_count}건</span>
          </div>

          <table className="preview-table" aria-label="가져오기 미리보기 목록">
            <thead>
              <tr>
                <th scope="col">행</th>
                <th scope="col">분류</th>
                <th scope="col">원문 내용</th>
                <th scope="col">규칙 코드</th>
                <th scope="col">상태</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((row) => (
                <tr key={row.row_number} className={`row-${row.validation_status}`}>
                  <td>{row.row_number}</td>
                  <td>{row.category}</td>
                  <td>{row.raw_content}</td>
                  <td>{row.extracted_rule_code ?? "-"}</td>
                  <td>
                    <span className={`badge badge-${row.validation_status}`}>
                      {row.validation_status === "valid"
                        ? "유효"
                        : row.validation_status === "warning"
                          ? "경고"
                          : "오류"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          <div className="actions-bar">
            <button
              type="button"
              disabled={isCommitting || preview.valid_count === 0}
              onClick={handleCommit}
              className="btn btn-primary"
            >
              {isCommitting ? "등록 중..." : "확정 가져오기"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
