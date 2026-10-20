import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Finding, ImprovementSuggestion } from "@dev-pre-review/contracts";
import { FindingsViewer } from "./FindingsViewer";

const mockFindings: Finding[] = [
  {
    id: "finding-1",
    job_id: "job-1",
    rule_code: "DIM-001",
    status: "violation",
    severity: "critical",
    message: "외경 9.5mm는 규격 10.0mm 이상을 위반합니다.",
    bbox: {
      page_or_layout: 1,
      x0: 20,
      y0: 30,
      x1: 40,
      y1: 50,
    },
    evidences: [
      { kind: "rule", ref_id: "RULE-DIM-001" },
      { kind: "case", ref_id: "CASE-2025-08" },
    ],
  },
  {
    id: "finding-2",
    job_id: "job-1",
    rule_code: "SURF-002",
    status: "compliant",
    severity: "minor",
    message: "표면 조도 Ra 0.4um로 허용 기준 Ra 0.8um 이하를 충족합니다.",
    bbox: null,
    evidences: [{ kind: "rule", ref_id: "RULE-SURF-002" }],
  },
];

const mockSuggestions: ImprovementSuggestion[] = [
  {
    finding_id: "finding-1",
    suggested_action: "선삭 가공 마진을 0.5mm 증대할 것을 권장합니다.",
    rationale: "유사 불량 사례 CASE-2025-08에서 마진 부족으로 인한 치수 미달 확인됨.",
    new_rule_candidate: {
      code: "RULE-AUTO-DIM",
      title: "선삭 안전 마진 규정",
      state: "DRAFT",
    },
  },
];

describe("FindingsViewer", () => {
  it("renders findings list, coordinates highlight, and evidence details", () => {
    render(<FindingsViewer findings={mockFindings} suggestions={mockSuggestions} />);

    expect(screen.getByRole("heading", { name: "도면 검토 결과 및 근거 분석" })).toBeVisible();

    // Left sidebar and details items
    expect(screen.getAllByText("DIM-001")[0]).toBeVisible();
    expect(screen.getAllByText("SURF-002")[0]).toBeVisible();

    // Highlight box for selected finding (finding-1)
    expect(
      screen.getByLabelText("좌표 하이라이트 영역 x0:20, y0:30")
    ).toBeVisible();

    // Evidence panel
    expect(screen.getByText("RULE-DIM-001")).toBeVisible();
    expect(screen.getByText("CASE-2025-08")).toBeVisible();

    // Suggestion box
    expect(screen.getByText("선삭 가공 마진을 0.5mm 증대할 것을 권장합니다.")).toBeVisible();
    expect(screen.getByText(/선삭 안전 마진 규정/)).toBeVisible();
  });

  it("filters findings by status", () => {
    render(<FindingsViewer findings={mockFindings} suggestions={mockSuggestions} />);

    const filterSelect = screen.getByLabelText("판정 필터:");
    fireEvent.change(filterSelect, { target: { value: "COMPLIANT" } });

    const sidebar = screen.getByLabelText("검토 결과 목록");
    expect(sidebar).not.toHaveTextContent("DIM-001");
    expect(sidebar).toHaveTextContent("SURF-002");
  });
});
