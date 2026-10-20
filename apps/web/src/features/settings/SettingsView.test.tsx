import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SettingsView } from "./SettingsView";

describe("SettingsView", () => {
  it("renders hardware profile and allows consent toggle with modal preview", async () => {
    const handleConsentChange = vi.fn().mockResolvedValue(undefined);
    render(<SettingsView onConsentChange={handleConsentChange} />);

    expect(screen.getByRole("heading", { name: "시스템 환경 설정 및 하드웨어 진단" })).toBeVisible();
    expect(screen.getByText("8 Cores")).toBeVisible();
    expect(screen.getByText("16 GB")).toBeVisible();
    expect(screen.getByText("차단됨 (Revoked)")).toBeVisible();

    // Click consent setup -> opens modal
    const consentBtn = screen.getByRole("button", { name: "전송 동의 설정" });
    fireEvent.click(consentBtn);

    expect(screen.getByRole("dialog")).toBeVisible();
    expect(screen.getByText("전송 데이터 사전 확인 (Transmission Preview)")).toBeVisible();

    // Confirm modal
    const confirmBtn = screen.getByRole("button", { name: "확인 및 전송 동의" });
    fireEvent.click(confirmBtn);

    expect(handleConsentChange).toHaveBeenCalledWith(true);
    expect(await screen.findByText("허용됨 (Granted)")).toBeVisible();
  });
});
