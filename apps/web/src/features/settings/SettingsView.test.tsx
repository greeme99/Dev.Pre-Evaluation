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

  it("triggers backup creation and diagnostic bundle download", async () => {
    const handleCreateBackup = vi.fn().mockResolvedValue(undefined);
    const handleDownloadDiagnostics = vi.fn().mockResolvedValue(undefined);

    render(
      <SettingsView
        onCreateBackup={handleCreateBackup}
        onDownloadDiagnostics={handleDownloadDiagnostics}
      />
    );

    // Passphrase validation
    const backupBtn = screen.getByRole("button", { name: "🔒 백업 파일 다운로드" });
    expect(backupBtn).toBeDisabled();

    const passInput = screen.getByLabelText("백업 암호 (최소 8자):");
    fireEvent.change(passInput, { target: { value: "password123" } });
    expect(backupBtn).not.toBeDisabled();

    fireEvent.click(backupBtn);
    expect(handleCreateBackup).toHaveBeenCalledWith("password123");

    // Diagnostics button
    const diagBtn = screen.getByRole("button", { name: "📋 진단 번들 JSON 생성" });
    fireEvent.click(diagBtn);
    expect(handleDownloadDiagnostics).toHaveBeenCalled();
  });
});
