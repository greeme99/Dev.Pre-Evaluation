"""Encrypted backup and restore service with Argon2id and AES-256-GCM (FN-009, FR-014)."""

import hashlib
import json
import os
from datetime import datetime
from typing import Any
from uuid import UUID

import argon2.low_level as argon2_ll
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session, sessionmaker

from dev_pre_review import __version__
from dev_pre_review.domain.models import utc_now
from dev_pre_review.storage.schema import (
    analysis_jobs,
    drawing_artifacts,
    evidence,
    findings,
    knowledge_cases,
    projects,
    rules,
)

MAGIC = b"DPRB"  # Dev Pre-Review Backup
CURRENT_PACKAGE_VERSION = 1
SUPPORTED_VERSIONS = {1}
SALT_LEN = 16
NONCE_LEN = 12


class BackupError(Exception):
    """Base exception for backup and restore failures."""


class BackupAuthenticationError(BackupError):
    """Raised when passphrase is wrong or authentication tag verification fails."""


class BackupTamperedError(BackupError):
    """Raised when backup package structure or data is modified/corrupted."""


class IncompatibleVersionError(BackupError):
    """Raised when backup manifest version is newer or incompatible."""


def _parse_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    return datetime.fromisoformat(val)


def _parse_uuid(val: Any) -> UUID | None:
    if val is None:
        return None
    if isinstance(val, UUID):
        return val
    return UUID(str(val))


class BackupService:
    """Argon2id key-derived AES-256-GCM encrypted backup/restore manager."""

    @staticmethod
    def _derive_key(passphrase: str, salt: bytes) -> bytes:
        return argon2_ll.hash_secret_raw(
            secret=passphrase.encode("utf-8"),
            salt=salt,
            time_cost=2,
            memory_cost=65536,
            parallelism=1,
            hash_len=32,
            type=argon2_ll.Type.ID,
        )

    def create(
        self,
        session_factory: sessionmaker[Session],
        passphrase: str,
        include_sources: bool = False,
    ) -> bytes:
        with session_factory() as session:
            all_projects = [dict(r) for r in session.execute(select(projects)).mappings().all()]
            all_drawings = [
                dict(r) for r in session.execute(select(drawing_artifacts)).mappings().all()
            ]
            all_jobs = [dict(r) for r in session.execute(select(analysis_jobs)).mappings().all()]
            all_findings = [dict(r) for r in session.execute(select(findings)).mappings().all()]
            all_evidence = [dict(r) for r in session.execute(select(evidence)).mappings().all()]
            all_cases = [dict(r) for r in session.execute(select(knowledge_cases)).mappings().all()]
            all_rules = [dict(r) for r in session.execute(select(rules)).mappings().all()]

        version_manifest: dict[str, Any] = {
            "package_version": CURRENT_PACKAGE_VERSION,
            "app_version": __version__,
            "created_at": utc_now().isoformat(),
            "include_sources": include_sources,
        }
        payload_obj: dict[str, Any] = {
            "version_manifest": version_manifest,
            "data": {
                "projects": all_projects,
                "drawings": all_drawings,
                "jobs": all_jobs,
                "findings": all_findings,
                "evidence": all_evidence,
                "knowledge_cases": all_cases,
                "rules": all_rules,
            },
        }

        # JSON serialize with UUID and datetime converted to string
        def _json_serial(obj: Any) -> Any:
            if isinstance(obj, UUID):
                return str(obj)
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return str(obj)

        raw_json = json.dumps(payload_obj, default=_json_serial, ensure_ascii=False).encode("utf-8")
        content_hash = hashlib.sha256(raw_json).hexdigest()
        version_manifest["content_sha256"] = content_hash

        plaintext = json.dumps(payload_obj, default=_json_serial, ensure_ascii=False).encode(
            "utf-8"
        )

        salt = os.urandom(SALT_LEN)
        nonce = os.urandom(NONCE_LEN)
        key = self._derive_key(passphrase, salt)

        header = MAGIC + CURRENT_PACKAGE_VERSION.to_bytes(2, byteorder="big")
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=header)

        return header + salt + nonce + ciphertext

    def _decrypt_payload(self, package_bytes: bytes, passphrase: str) -> dict[str, Any]:
        min_len = 4 + 2 + SALT_LEN + NONCE_LEN + 16  # Magic + Ver + Salt + Nonce + GCM Tag
        if len(package_bytes) < min_len:
            raise BackupTamperedError("Package size is smaller than minimum required header length")

        magic = package_bytes[:4]
        if magic != MAGIC:
            raise BackupTamperedError("Invalid package magic signature")

        pkg_version = int.from_bytes(package_bytes[4:6], byteorder="big")
        if pkg_version not in SUPPORTED_VERSIONS:
            raise IncompatibleVersionError(f"Unsupported package version: {pkg_version}")

        salt = package_bytes[6 : 6 + SALT_LEN]
        nonce = package_bytes[6 + SALT_LEN : 6 + SALT_LEN + NONCE_LEN]
        ciphertext = package_bytes[6 + SALT_LEN + NONCE_LEN :]
        header = magic + package_bytes[4:6]

        try:
            key = self._derive_key(passphrase, salt)
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data=header)
        except InvalidTag as err:
            raise BackupAuthenticationError(
                "Passphrase authentication failed or package data is corrupted"
            ) from err
        except Exception as err:
            raise BackupAuthenticationError("Failed to decrypt backup package") from err

        try:
            parsed = json.loads(plaintext.decode("utf-8"))
            if not isinstance(parsed, dict) or "data" not in parsed:
                raise BackupTamperedError("Invalid backup package contents structure")
            return parsed
        except Exception as err:
            raise BackupTamperedError("Corrupted JSON payload in backup package") from err

    def preview(self, package_bytes: bytes, passphrase: str) -> dict[str, Any]:
        payload = self._decrypt_payload(package_bytes, passphrase)
        manifest = payload.get("version_manifest", {})
        data = payload.get("data", {})

        return {
            "version_manifest": manifest,
            "project_count": len(data.get("projects", [])),
            "drawing_count": len(data.get("drawings", [])),
            "job_count": len(data.get("jobs", [])),
            "finding_count": len(data.get("findings", [])),
            "rule_count": len(data.get("rules", [])),
            "case_count": len(data.get("knowledge_cases", [])),
        }

    def restore(
        self,
        package_bytes: bytes,
        passphrase: str,
        target_session_factory: sessionmaker[Session],
    ) -> None:
        payload = self._decrypt_payload(package_bytes, passphrase)
        data = payload.get("data", {})

        with target_session_factory() as session, session.begin():
            # Clear existing data in foreign-key dependent reverse order
            session.execute(delete(evidence))
            session.execute(delete(findings))
            session.execute(delete(analysis_jobs))
            session.execute(delete(drawing_artifacts))
            session.execute(delete(rules))
            session.execute(delete(knowledge_cases))
            session.execute(delete(projects))

            # Re-populate in dependency order
            for p in data.get("projects", []):
                session.execute(
                    insert(projects).values(
                        id=_parse_uuid(p["id"]),
                        name=p["name"],
                        status=p["status"],
                        created_at=_parse_dt(p["created_at"]),
                        data_version=p["data_version"],
                    )
                )

            for d in data.get("drawings", []):
                session.execute(
                    insert(drawing_artifacts).values(
                        id=_parse_uuid(d["id"]),
                        project_id=_parse_uuid(d["project_id"]),
                        sha256=d["sha256"],
                        drawing_type=d["drawing_type"],
                        source_name=d["source_name"],
                        parser_version=d["parser_version"],
                        created_at=_parse_dt(d["created_at"]),
                    )
                )

            for j in data.get("jobs", []):
                session.execute(
                    insert(analysis_jobs).values(
                        id=_parse_uuid(j["id"]),
                        seq=j["seq"],
                        project_id=_parse_uuid(j["project_id"]),
                        drawing_id=_parse_uuid(j["drawing_id"]),
                        state=j["state"],
                        completed_steps=j["completed_steps"],
                        failed_step=j.get("failed_step"),
                        error_code=j.get("error_code"),
                        config_versions=j.get("config_versions", {}),
                        created_at=_parse_dt(j["created_at"]),
                        started_at=_parse_dt(j.get("started_at")),
                        finished_at=_parse_dt(j.get("finished_at")),
                        updated_at=_parse_dt(j["updated_at"]),
                        version=j["version"],
                    )
                )

            for f in data.get("findings", []):
                session.execute(
                    insert(findings).values(
                        id=_parse_uuid(f["id"]),
                        job_id=_parse_uuid(f["job_id"]),
                        status=f["status"],
                        severity=f["severity"],
                        confidence=f["confidence"],
                        finding_type=f["finding_type"],
                        location=f["location"],
                        message=f["message"],
                        pixel_bbox=f.get("pixel_bbox"),
                        cad_bbox=f.get("cad_bbox"),
                        created_at=_parse_dt(f["created_at"]),
                    )
                )

            for ev in data.get("evidence", []):
                session.execute(
                    insert(evidence).values(
                        finding_id=_parse_uuid(ev["finding_id"]),
                        position=ev["position"],
                        kind=ev["kind"],
                        ref_id=ev["ref_id"],
                        score=ev.get("score"),
                        location=ev.get("location"),
                    )
                )

            for r in data.get("rules", []):
                session.execute(
                    insert(rules).values(
                        id=_parse_uuid(r["id"]),
                        project_id=_parse_uuid(r["project_id"]),
                        state=r["state"],
                        drawing_types=r["drawing_types"],
                        field=r["field"],
                        operator=r["operator"],
                        parameters=r["parameters"],
                        severity=r["severity"],
                        confidence=r["confidence"],
                        code=r["code"],
                        title=r["title"],
                        description=r["description"],
                        discipline=r["discipline"],
                        unit=r.get("unit"),
                        created_at=_parse_dt(r["created_at"]),
                        updated_at=_parse_dt(r["updated_at"]),
                        version=r["version"],
                    )
                )

            for c in data.get("knowledge_cases", []):
                session.execute(
                    insert(knowledge_cases).values(
                        id=_parse_uuid(c["id"]),
                        project_id=_parse_uuid(c["project_id"]),
                        text=c["text"],
                        table_data=c["table_data"],
                        image_refs=c["image_refs"],
                        source_file_sha256=c["source_file_sha256"],
                        source_sheet=c["source_sheet"],
                        source_cell=c["source_cell"],
                        created_at=_parse_dt(c["created_at"]),
                    )
                )
