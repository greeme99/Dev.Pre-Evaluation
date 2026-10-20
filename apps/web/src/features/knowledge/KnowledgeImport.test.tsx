import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KnowledgeImport } from "./KnowledgeImport";

describe("KnowledgeImport", () => {
  it("renders upload form and handles preview simulation", async () => {
    render(<KnowledgeImport projectId="proj-123" />);

    expect(screen.getByRole("heading", { name: "지식 및 규칙 가져오기" })).toBeVisible();

    const fileInput = screen.getByLabelText("규칙 엑셀 파일 선택");
    const previewBtn = screen.getByRole("button", { name: "미리보기 불러오기" });

    expect(previewBtn).toBeDisabled();

    // Select file
    const file = new File(["dummy"], "rules.xlsx", {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    fireEvent.change(fileInput, { target: { files: [file] } });

    expect(previewBtn).not.toBeDisabled();
    fireEvent.click(previewBtn);

    // Preview table rendered
    expect(await screen.findByRole("table", { name: "가져오기 미리보기 목록" })).toBeVisible();
    expect(screen.getByText("DIM-001")).toBeVisible();
    expect(screen.getByRole("button", { name: "확정 가져오기" })).toBeVisible();
  });
});
