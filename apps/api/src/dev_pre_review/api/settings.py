"""System settings, hardware profile and consent endpoints (FN-008, MOD-001~MOD-005)."""

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from dev_pre_review.models.consent import ConsentManager
from dev_pre_review.models.hardware import HardwareDetector, HardwareProfile
from dev_pre_review.models.manifests import ModelRecommendation, ModelRegistry

router = APIRouter(prefix="/api/settings", tags=["settings"])

_GLOBAL_CONSENT_MANAGER = ConsentManager()


def get_consent_manager() -> ConsentManager:
    return _GLOBAL_CONSENT_MANAGER


class ProfileResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    hardware_profile: HardwareProfile
    recommendation: ModelRecommendation


class ConsentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    token: str
    action: str  # "grant" or "revoke"


@router.get("/profile", response_model=ProfileResponse)
def get_system_profile() -> ProfileResponse:
    detector = HardwareDetector()
    profile = detector.detect()

    manifest_path = Path("packaging/windows/models.json")
    if manifest_path.exists():
        registry = ModelRegistry.load_from_path(manifest_path)
    else:
        registry = ModelRegistry(models={})

    recommendation = registry.recommend(profile)
    return ProfileResponse(
        hardware_profile=profile,
        recommendation=recommendation,
    )


@router.post("/consent")
def update_consent(req: ConsentRequest) -> dict[str, str]:
    cm = get_consent_manager()
    if req.action == "grant":
        cm.grant_consent(req.job_id, req.token)
        return {"status": "granted", "job_id": str(req.job_id)}
    if req.action == "revoke":
        cm.revoke_consent(req.job_id)
        return {"status": "revoked", "job_id": str(req.job_id)}
    return {"status": "ignored", "action": req.action}
