"""Tests for drawing upload and validation API endpoint (API-005, SCR-003)."""

from pathlib import Path

import pymupdf
import pytest
from fastapi import status
from fastapi.testclient import TestClient

from dev_pre_review.main import create_app


@pytest.fixture
def api_client() -> TestClient:
    return TestClient(create_app())


def create_sample_pdf(path: Path, encrypt: bool = False) -> None:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "Sample Engineering Drawing")
    if encrypt:
        doc.save(
            path,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            user_pw="secret",
            owner_pw="secret_owner",
        )
    else:
        doc.save(path)
    doc.close()


def test_api_validates_valid_pdf(api_client: TestClient, tmp_path: Path) -> None:
    pdf_path = tmp_path / "sample.pdf"
    create_sample_pdf(pdf_path)

    with open(pdf_path, "rb") as f:
        resp = api_client.post(
            "/api/drawings/validate",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["is_valid"] is True
    assert data["drawing_type"] == "pdf"
    assert data["page_count"] == 1
    assert data["stored_file_sha256"] is not None
    assert len(data["errors"]) == 0


def test_api_rejects_dwg_file(api_client: TestClient, tmp_path: Path) -> None:
    dwg_path = tmp_path / "sample.dwg"
    dwg_path.write_bytes(b"AC1032DWGBYTES")

    with open(dwg_path, "rb") as f:
        resp = api_client.post(
            "/api/drawings/validate",
            files={"file": ("sample.dwg", f, "application/acad")},
        )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["is_valid"] is False
    assert any(err["code"] == "unsupported_extension" for err in data["errors"])


def test_api_rejects_encrypted_pdf(api_client: TestClient, tmp_path: Path) -> None:
    locked_pdf = tmp_path / "locked.pdf"
    create_sample_pdf(locked_pdf, encrypt=True)

    with open(locked_pdf, "rb") as f:
        resp = api_client.post(
            "/api/drawings/validate",
            files={"file": ("locked.pdf", f, "application/pdf")},
        )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["is_valid"] is False
    assert any(err["code"] == "encrypted_file" for err in data["errors"])


def test_api_rejects_extension_spoofing(api_client: TestClient, tmp_path: Path) -> None:
    spoofed_path = tmp_path / "spoofed.pdf"
    spoofed_path.write_bytes(b"NOT_A_PDF_CONTENT")

    with open(spoofed_path, "rb") as f:
        resp = api_client.post(
            "/api/drawings/validate",
            files={"file": ("spoofed.pdf", f, "application/pdf")},
        )

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["is_valid"] is False
    assert any(err["code"] == "signature_mismatch" for err in data["errors"])
