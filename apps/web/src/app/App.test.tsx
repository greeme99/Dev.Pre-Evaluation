import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App shell", () => {
  it("renders the product heading", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "개발 도면 사전 검토" })).toBeVisible();
  });
});
