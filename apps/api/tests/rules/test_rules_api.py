"""Tests for Rules REST API endpoints."""

from uuid import uuid4

import pytest
from conftest import Seed
from fastapi import status
from fastapi.testclient import TestClient

from dev_pre_review.main import create_app, get_database
from dev_pre_review.storage.database import Database


@pytest.fixture
def api_client(database: Database) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_database] = lambda: database
    return TestClient(app)


def test_create_rule_and_list_rules(api_client: TestClient, seed: Seed) -> None:
    case_id = str(uuid4())
    create_body = {
        "project_id": str(seed.project.id),
        "drawing_types": ["pdf", "dxf"],
        "field": "tolerance",
        "operator": "max",
        "value": "0.05",
        "unit": "mm",
        "severity": "high",
        "source_case_ids": [case_id],
    }

    resp = api_client.post("/api/rules", json=create_body)
    assert resp.status_code == status.HTTP_201_CREATED
    rule_data = resp.json()
    assert rule_data["field"] == "tolerance"
    assert rule_data["state"] == "draft"
    assert rule_data["version"] == 1
    rule_id = rule_data["id"]

    # List rules with project filter
    list_resp = api_client.get(f"/api/rules?project_id={seed.project.id}")
    assert list_resp.status_code == status.HTTP_200_OK
    rules = list_resp.json()
    assert len(rules) == 1
    assert rules[0]["id"] == rule_id

    # List rules with state filter
    draft_resp = api_client.get(f"/api/rules?project_id={seed.project.id}&state=draft")
    assert draft_resp.status_code == status.HTTP_200_OK
    assert len(draft_resp.json()) == 1

    approved_resp = api_client.get(f"/api/rules?project_id={seed.project.id}&state=approved")
    assert approved_resp.status_code == status.HTTP_200_OK
    assert len(approved_resp.json()) == 0


def test_rule_transitions_via_api(api_client: TestClient, seed: Seed) -> None:
    # 1. Create draft rule
    create_body = {
        "project_id": str(seed.project.id),
        "drawing_types": ["pdf"],
        "field": "material",
        "operator": "equals",
        "value": "SUS304",
        "unit": None,
        "severity": "medium",
        "source_case_ids": [str(uuid4())],
    }
    create_resp = api_client.post("/api/rules", json=create_body)
    rule_id = create_resp.json()["id"]

    # 2. Transition draft -> approved
    trans_body = {"target_state": "approved", "expected_version": 1}
    appr_resp = api_client.post(f"/api/rules/{rule_id}/transitions", json=trans_body)
    assert appr_resp.status_code == status.HTTP_200_OK
    assert appr_resp.json()["state"] == "approved"
    assert appr_resp.json()["version"] == 2

    # 3. Version conflict on stale version
    conflict_body = {"target_state": "inactive", "expected_version": 1}
    conflict_resp = api_client.post(f"/api/rules/{rule_id}/transitions", json=conflict_body)
    assert conflict_resp.status_code == status.HTTP_409_CONFLICT

    # 4. Transition approved -> inactive
    inact_body = {"target_state": "inactive", "expected_version": 2}
    inact_resp = api_client.post(f"/api/rules/{rule_id}/transitions", json=inact_body)
    assert inact_resp.status_code == status.HTTP_200_OK
    assert inact_resp.json()["state"] == "inactive"
    assert inact_resp.json()["version"] == 3

    # 5. Invalid transition inactive -> draft
    invalid_body = {"target_state": "draft", "expected_version": 3}
    invalid_resp = api_client.post(f"/api/rules/{rule_id}/transitions", json=invalid_body)
    assert invalid_resp.status_code == status.HTTP_400_BAD_REQUEST

    # 6. Not found transition
    not_found_resp = api_client.post(f"/api/rules/{uuid4()}/transitions", json=trans_body)
    assert not_found_resp.status_code == status.HTTP_404_NOT_FOUND
