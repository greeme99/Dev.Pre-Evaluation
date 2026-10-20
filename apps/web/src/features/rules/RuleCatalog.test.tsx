import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { RuleDefinition } from "@dev-pre-review/contracts";
import { RuleCatalog } from "./RuleCatalog";

const sampleRules: RuleDefinition[] = [
  {
    id: "rule-1",
    code: "RULE-001",
    title: "최소 외경 규격",
    description: "외경 10mm 이상",
    discipline: "MACHINING",
    state: "draft",
    severity: "critical",
    operator: "min",
    field_name: "outer_diameter",
    parameters: { value: 10 },
    version: 1,
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-20T00:00:00Z",
  },
  {
    id: "rule-2",
    code: "RULE-002",
    title: "표면 거칠기",
    description: "Ra 1.6 이하",
    discipline: "SURFACE",
    state: "approved",
    severity: "major",
    operator: "max",
    field_name: "roughness_ra",
    parameters: { value: 1.6 },
    version: 2,
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-20T00:00:00Z",
  },
];

describe("RuleCatalog", () => {
  it("renders rules and filters by state", () => {
    render(<RuleCatalog initialRules={sampleRules} />);

    expect(screen.getByRole("heading", { name: "규칙 카탈로그" })).toBeVisible();
    expect(screen.getByText("RULE-001")).toBeVisible();
    expect(screen.getByText("RULE-002")).toBeVisible();

    // Filter to APPROVED
    const filterSelect = screen.getByLabelText("상태 필터:");
    fireEvent.change(filterSelect, { target: { value: "APPROVED" } });

    expect(screen.queryByText("RULE-001")).not.toBeInTheDocument();
    expect(screen.getByText("RULE-002")).toBeVisible();
  });

  it("triggers approve transition", async () => {
    const handleTransition = vi.fn().mockResolvedValue(undefined);
    render(<RuleCatalog initialRules={sampleRules} onTransition={handleTransition} />);

    const approveBtn = screen.getByRole("button", { name: "승인" });
    fireEvent.click(approveBtn);

    expect(handleTransition).toHaveBeenCalledWith("rule-1", "approve", 1);
  });
});
