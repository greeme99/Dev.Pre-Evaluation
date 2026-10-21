"""OpenAPI is the source contract for the project-to-findings workflow."""

from dev_pre_review.main import create_app


def test_workflow_paths_reference_response_schemas() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]

    expected = {
        ("/api/projects", "post"): "ProjectResponse",
        ("/api/projects/{project_id}/drawings", "post"): "DrawingUploadResponse",
        ("/api/analyses", "post"): "AnalysisJobResponse",
        ("/api/analyses/{job_id}", "get"): "AnalysisJobResponse",
        ("/api/analyses/{job_id}/findings", "get"): "FindingsResponse",
    }
    for (path, method), response_schema in expected.items():
        response = paths[path][method]["responses"][
            "201"
            if method == "post"
            and path
            in {
                "/api/projects",
                "/api/projects/{project_id}/drawings",
                "/api/analyses",
            }
            else "200"
        ]
        assert response["content"]["application/json"]["schema"]["$ref"].endswith(
            f"/{response_schema}"
        )


def test_workflow_response_schemas_keep_backend_fields_and_enums() -> None:
    schemas = create_app().openapi()["components"]["schemas"]

    expected_schemas = {
        "CreateProjectRequest",
        "ProjectResponse",
        "DrawingUploadResponse",
        "CreateAnalysisRequest",
        "AnalysisJobResponse",
        "FindingsResponse",
        "Finding",
        "Evidence",
        "ImprovementSuggestion",
        "DrawingType",
        "JobState",
        "AnalysisStep",
        "FindingStatus",
        "Severity",
        "EvidenceKind",
    }
    assert expected_schemas <= schemas.keys()

    job = schemas["AnalysisJobResponse"]["properties"]
    assert job["state"]["$ref"].endswith("/JobState")
    assert job["completed_steps"]["items"]["$ref"].endswith("/AnalysisStep")
    assert any(
        option.get("$ref", "").endswith("/AnalysisStep") for option in job["failed_step"]["anyOf"]
    )

    finding_fields = set(schemas["Finding"]["properties"])
    assert {
        "confidence",
        "finding_type",
        "location",
        "pixel_bbox",
        "cad_bbox",
        "evidence",
        "created_at",
    } <= finding_fields


def test_workflow_requests_document_json_and_multipart_bodies() -> None:
    paths = create_app().openapi()["paths"]

    project_request = paths["/api/projects"]["post"]["requestBody"]
    assert project_request["content"]["application/json"]["schema"]["$ref"].endswith(
        "/CreateProjectRequest"
    )

    upload_request = paths["/api/projects/{project_id}/drawings"]["post"]["requestBody"]
    assert "multipart/form-data" in upload_request["content"]

    analysis_request = paths["/api/analyses"]["post"]["requestBody"]
    assert analysis_request["content"]["application/json"]["schema"]["$ref"].endswith(
        "/CreateAnalysisRequest"
    )
