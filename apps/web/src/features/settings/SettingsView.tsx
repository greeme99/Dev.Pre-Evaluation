import { useState } from "react";
import type { ProfileResponse } from "@dev-pre-review/contracts";

interface Props {
  initialProfile?: ProfileResponse;
  onConsentChange?: (granted: boolean) => Promise<void>;
  onCreateBackup?: (passphrase: string) => Promise<void>;
  onDownloadDiagnostics?: () => Promise<void>;
}

const defaultProfile: ProfileResponse = {
  hardware_profile: {
    cpu_logical_cores: 8,
    system_ram_gb: 16,
    has_cuda: false,
    cuda_device_name: null,
    cuda_vram_gb: 0,
    execution_provider: "cpu",
  },
  recommendation: {
    profile_name: "cpu_standard",
    ocr_model: "paddleocr-cpu",
    embedding_model: "bge-m3-cpu",
    visual_model: null,
    suggestion_mode: "local",
    reason: "GPU 미감지 환경으로 CPU 로컬 경량 모델 및 규칙 전용 검토를 권장합니다.",
  },
};

export function SettingsView({
  initialProfile = defaultProfile,
  onConsentChange,
  onCreateBackup,
  onDownloadDiagnostics,
}: Props) {
  const [profile] = useState<ProfileResponse>(initialProfile);
  const [consentGranted, setConsentGranted] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [backupPassphrase, setBackupPassphrase] = useState("");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const handleToggleConsent = async () => {
    if (!consentGranted) {
      setShowPreviewModal(true);
      return;
    }
    setIsUpdating(true);
    try {
      if (onConsentChange) {
        await onConsentChange(false);
      }
      setConsentGranted(false);
      setStatusMessage("외부 AI 전송 동의가 철회되었습니다.");
    } finally {
      setIsUpdating(false);
    }
  };

  const handleConfirmGrant = async () => {
    setIsUpdating(true);
    setShowPreviewModal(false);
    try {
      if (onConsentChange) {
        await onConsentChange(true);
      }
      setConsentGranted(true);
      setStatusMessage("외부 AI 전송 동의가 설정되었습니다.");
    } finally {
      setIsUpdating(false);
    }
  };

  const handleCreateBackup = async () => {
    if (backupPassphrase.length < 8) return;
    setStatusMessage("암호화 백업 패키지를 생성 중입니다...");
    try {
      if (onCreateBackup) {
        await onCreateBackup(backupPassphrase);
      }
      setStatusMessage("암호화 백업 파일이 생성되었습니다.");
    } catch {
      setStatusMessage("백업 생성 중 오류가 발생했습니다.");
    }
  };

  const handleDownloadDiagnostics = async () => {
    setStatusMessage("진단 번들을 수집 중입니다...");
    try {
      if (onDownloadDiagnostics) {
        await onDownloadDiagnostics();
      }
      setStatusMessage("진단 번들이 다운로드되었습니다.");
    } catch {
      setStatusMessage("진단 번들 생성 중 오류가 발생했습니다.");
    }
  };

  return (
    <section className="settings-panel" aria-labelledby="settings-title">
      <h2 id="settings-title">시스템 환경 설정 및 하드웨어 진단</h2>

      {statusMessage && (
        <div className="status-banner" role="status" aria-live="polite">
          {statusMessage}
        </div>
      )}

      {/* Hardware & Recommendation */}
      <div className="card settings-card">
        <h3>하드웨어 감지 프로파일</h3>
        <div className="grid-2col">
          <div className="info-item">
            <span className="label">CPU 논리 코어:</span>
            <span>{profile.hardware_profile.cpu_logical_cores} Cores</span>
          </div>
          <div className="info-item">
            <span className="label">시스템 RAM:</span>
            <span>{profile.hardware_profile.system_ram_gb} GB</span>
          </div>
          <div className="info-item">
            <span className="label">GPU 가속:</span>
            <span>
              {profile.hardware_profile.has_cuda
                ? `CUDA (${profile.hardware_profile.cuda_device_name}, ${profile.hardware_profile.cuda_vram_gb}GB)`
                : "미지원 (CPU 모드)"}
            </span>
          </div>
          <div className="info-item">
            <span className="label">실행 프로바이더:</span>
            <span className="badge badge-primary">
              {profile.hardware_profile.execution_provider.toUpperCase()}
            </span>
          </div>
        </div>

        <div className="recommendation-box">
          <h4>추천 모델 모드: <strong>{profile.recommendation.suggestion_mode}</strong></h4>
          <p>{profile.recommendation.reason}</p>
        </div>
      </div>

      {/* Data Transmission Consent */}
      <div className="card settings-card">
        <h3>외부 원격 AI 제안 데이터 전송 동의 (Privacy & Consent)</h3>
        <p className="description">
          원격 LLM을 통한 정밀 개선 제안을 사용하려면 도면 텍스트의 외부 전송 사전 동의가 필요합니다.
          동의가 없으면 도면 원본이나 추출 텍스트가 외부로 절대 유출되지 않으며, 로컬 규칙 엔진만 동작합니다.
        </p>

        <div className="consent-toggle-row">
          <div className="switch-label">
            <span>외부 AI 전송 동의 상태: </span>
            <strong>{consentGranted ? "허용됨 (Granted)" : "차단됨 (Revoked)"}</strong>
          </div>
          <button
            id="consent-switch"
            type="button"
            className={`btn ${consentGranted ? "btn-danger" : "btn-primary"}`}
            disabled={isUpdating}
            onClick={handleToggleConsent}
          >
            {consentGranted ? "동의 철회하기" : "전송 동의 설정"}
          </button>
        </div>
      </div>

      {/* Encrypted Backup & Diagnostics */}
      <div className="card settings-card">
        <h3>데이터 백업 및 시스템 진단 번들 (Backup & Diagnostics)</h3>
        <p className="description">
          Argon2id 키 유도 및 AES-256-GCM 인증 암호화로 전체 프로젝트·도면·규칙 데이터를 안전하게 백업하거나,
          오류 문제 해결을 위한 개인정보 제거 진단 번들을 생성합니다.
        </p>

        <div className="grid-2col">
          <div className="action-subcard">
            <h4>암호화 백업 생성</h4>
            <div className="input-group">
              <label htmlFor="backup-passphrase">백업 암호 (최소 8자):</label>
              <input
                id="backup-passphrase"
                type="password"
                value={backupPassphrase}
                onChange={(e) => setBackupPassphrase(e.target.value)}
                placeholder="암호를 입력하세요"
              />
            </div>
            <button
              type="button"
              disabled={backupPassphrase.length < 8}
              onClick={handleCreateBackup}
              className="btn btn-primary"
            >
              🔒 백업 파일 다운로드
            </button>
          </div>

          <div className="action-subcard">
            <h4>시스템 진단 번들</h4>
            <p className="subtext">
              도면 원문, 파일 절대 경로, API 키는 완전히 마스킹되어 포함되지 않습니다.
            </p>
            <button
              type="button"
              onClick={handleDownloadDiagnostics}
              className="btn btn-secondary"
            >
              📋 진단 번들 JSON 생성
            </button>
          </div>
        </div>
      </div>

      {/* Transmission Preview Modal */}
      {showPreviewModal && (
        <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="modal-title">
          <div className="modal-content">
            <h3 id="modal-title">전송 데이터 사전 확인 (Transmission Preview)</h3>
            <p>외부 OpenAI API로 전송될 페이로드 항목을 사전에 확인하십시오:</p>
            <ul className="preview-list">
              <li>규칙 위반 소명 텍스트 요약</li>
              <li>도면 발췌 치수 텍스트 (개인정보 및 파일 경로는 제외됨)</li>
            </ul>
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => setShowPreviewModal(false)}
              >
                취소
              </button>
              <button
                type="button"
                className="btn btn-primary"
                onClick={handleConfirmGrant}
              >
                확인 및 전송 동의
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
