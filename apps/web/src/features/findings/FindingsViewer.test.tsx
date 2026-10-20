import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Finding, ImprovementSuggestion } from "@dev-pre-review/contracts";
import { FindingsViewer } from "./FindingsViewer";

const findings: Finding[] = [
  {
    id: "finding-1",
    job_id: "job-real-1",
    finding_type: "dimension",
    status: "violation",
    severity: "high",
    confidence: 0.95,
    location: "페이지 1 / 외경",
    message: "외경이 규격보다 작습니다.",
    pixel_bbox: [20, 30, 40, 50],
    evidence: [{ kind: "rule", ref_id: "RULE-DIM-001" }, { kind: "case", ref_id: "CASE-2025-08" }],
  },
  {
    id: "finding-2",
    job_id: "job-real-1",
    finding_type: "surface_finish",
    status: "suspected",
    severity: "low",
    confidence: 0.62,
    location: "레이아웃 A",
    message: "표면 조도를 확인해야 합니다.",
    cad_bbox: [1, 2, 5, 8],
    evidence: [],
  },
];

const suggestions: ImprovementSuggestion[] = [
  {
    finding_id: "finding-1",
    issue: "치수가 기준에 미달합니다.",
    location: "페이지 1 / 외경",
    recommendation: "가공 여유치수를 0.5mm 늘립니다.",
    evidence_refs: ["CASE-2025-08"],
    verification_condition: "수정 도면에서 최소 직경 10mm를 확인합니다.",
  },
];

describe("FindingsViewer", () => {
  it("renders backend finding fields, bbox tuple, evidence, suggestion, and real job CSV", () => {
    render(<FindingsViewer jobId="job-real-1" findings={findings} suggestions={suggestions} />);

    expect(screen.getByRole("heading", { name: "도면 검토 결과 및 근거 분석" })).toBeVisible();
    expect(screen.getAllByText("dimension")[0]).toBeVisible();
    expect(screen.getAllByText("페이지 1 / 외경")[0]).toBeVisible();
    expect(screen.getByText("95%")).toBeVisible();
    expect(screen.getByLabelText("좌표 하이라이트 영역 x0:20, y0:30")).toBeVisible();
    expect(screen.getByText("RULE-DIM-001")).toBeVisible();
    expect(screen.getByText("CASE-2025-08")).toBeVisible();
    expect(screen.getByText("가공 여유치수를 0.5mm 늘립니다.")).toBeVisible();
    expect(screen.getByText("수정 도면에서 최소 직경 10mm를 확인합니다.")).toBeVisible();
    expect(screen.getByRole("link", { name: "📥 CSV (.csv)" })).toHaveAttribute("href", "/api/analyses/job-real-1/export.csv");
  });

  it("filters findings by actual status and preserves CSV for an empty result", () => {
    const { rerender } = render(<FindingsViewer jobId="job-real-1" findings={findings} suggestions={suggestions} />);
    fireEvent.change(screen.getByLabelText("판정 필터:"), { target: { value: "SUSPECTED" } });
    const sidebar = screen.getByLabelText("검토 결과 목록");
    expect(sidebar).not.toHaveTextContent("dimension");
    expect(sidebar).toHaveTextContent("surface_finish");

    rerender(<FindingsViewer jobId="job-empty" findings={[]} suggestions={[]} />);
    expect(screen.getByText("저장된 검토 결과가 없습니다.")).toBeVisible();
    expect(screen.getByRole("link", { name: "📥 CSV (.csv)" })).toHaveAttribute("href", "/api/analyses/job-empty/export.csv");
  });
});
