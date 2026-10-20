"""Repository for saving and retrieving import profiles."""

from uuid import UUID

from dev_pre_review.domain.errors import NotFound
from dev_pre_review.knowledge.contracts import ImportProfile


class ImportProfileRepository:
    def __init__(self) -> None:
        self._profiles: dict[UUID, ImportProfile] = {}

    def save(self, profile: ImportProfile) -> ImportProfile:
        self._profiles[profile.id] = profile
        return profile

    def get(self, profile_id: UUID) -> ImportProfile:
        profile = self._profiles.get(profile_id)
        if profile is None:
            raise NotFound("ImportProfile", profile_id)
        return profile

    def list_all(self) -> list[ImportProfile]:
        return list(self._profiles.values())
