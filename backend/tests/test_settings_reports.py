import json
import uuid

from fastapi.testclient import TestClient

from app.main import LOCAL_WORKSPACE_ID, UPLOAD_DIR, app, db


client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50001))


def test_workspace_settings_are_saved_and_loaded():
    original_response = client.get(f"/api/v1/workspaces/{LOCAL_WORKSPACE_ID}/settings")
    assert original_response.status_code == 200
    original = original_response.json()
    changed = {
        "name": "Settings regression workspace",
        "jurisdiction": "West Bengal, India",
        "assessment_notifications": not original["assessment_notifications"],
    }

    try:
        saved = client.patch(
            f"/api/v1/workspaces/{LOCAL_WORKSPACE_ID}/settings",
            json=changed,
        )
        assert saved.status_code == 200
        assert saved.json()["name"] == changed["name"]
        loaded = client.get(f"/api/v1/workspaces/{LOCAL_WORKSPACE_ID}/settings")
        assert loaded.status_code == 200
        assert loaded.json() == saved.json()

        export = client.get(f"/api/v1/workspaces/{LOCAL_WORKSPACE_ID}/export")
        assert export.status_code == 200
        assert export.headers["content-disposition"].endswith('filename="permitpilot-workspace-export.json"')
        assert export.json()["workspace"]["id"] == LOCAL_WORKSPACE_ID
    finally:
        client.patch(
            f"/api/v1/workspaces/{LOCAL_WORKSPACE_ID}/settings",
            json=original,
        )


def test_report_uses_business_assessment_and_downloads_pdf():
    business_id = str(uuid.uuid4())
    profile_version_id = str(uuid.uuid4())
    assessment_id = str(uuid.uuid4())
    report_id = None
    result = [{
        "rule_id": "TEST-001",
        "title": "Test establishment requirement",
        "status": "UNRESOLVED",
        "authority": "Test authority",
        "disclaimer": "Verify this candidate with the authority.",
    }]
    with db() as connection:
        connection.execute(
            "INSERT INTO businesses "
            "(id,workspace_id,business_name,business_type,country,state,city) "
            "VALUES (?,?,?,?,?,?,?)",
            (business_id, LOCAL_WORKSPACE_ID, "Report Test Shop", "retail", "India", "West Bengal", "Kolkata"),
        )
        connection.execute(
            "INSERT INTO business_profile_versions "
            "(id,business_id,version_number,structured_facts,confirmed_by) VALUES (?,?,?,?,?)",
            (profile_version_id, business_id, 1, json.dumps({
                "business_name": "Report Test Shop",
                "state": "West Bengal",
                "city": "Kolkata",
                "activities": ["retail"],
            }), "test"),
        )
        connection.execute(
            "INSERT INTO assessments "
            "(id,workspace_id,business_id,profile_revision,status,results_json) VALUES (?,?,?,?,?,?)",
            (assessment_id, LOCAL_WORKSPACE_ID, business_id, 1, "completed", json.dumps(result)),
        )

    try:
        current_assessment = client.get(f"/api/v1/businesses/{business_id}/requirements")
        assert current_assessment.status_code == 200
        assert current_assessment.json()["assessment_id"] == assessment_id

        created = client.post(
            "/api/v1/reports",
            params={"workspace_id": LOCAL_WORKSPACE_ID, "business_id": business_id},
        )
        assert created.status_code == 200
        report = created.json()
        report_id = report["report_id"]
        assert report["assessment_id"] == assessment_id
        assert report["profile"]["business_name"] == "Report Test Shop"
        assert report["results"] == result

        listing = client.get("/api/v1/reports", params={"workspace_id": LOCAL_WORKSPACE_ID})
        assert any(item["id"] == report_id for item in listing.json()["items"])

        download = client.get(f"/api/v1/reports/{report_id}/download")
        assert download.status_code == 200
        assert download.content.startswith(b"%PDF")
    finally:
        with db() as connection:
            if report_id:
                connection.execute("DELETE FROM reports WHERE id=?", (report_id,))
            connection.execute("DELETE FROM assessments WHERE id=?", (assessment_id,))
            connection.execute("DELETE FROM business_profile_versions WHERE id=?", (profile_version_id,))
            connection.execute("DELETE FROM businesses WHERE id=?", (business_id,))
        if report_id:
            pdf_path = UPLOAD_DIR / f"{report_id}-assessment.pdf"
            if pdf_path.exists():
                pdf_path.unlink()


def test_report_requires_an_assessment_for_the_selected_business():
    business_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute(
            "INSERT INTO businesses "
            "(id,workspace_id,business_name,business_type,country,state,city) "
            "VALUES (?,?,?,?,?,?,?)",
            (business_id, LOCAL_WORKSPACE_ID, "No Assessment Shop", "retail", "India", "West Bengal", "Kolkata"),
        )
    try:
        response = client.post(
            "/api/v1/reports",
            params={"workspace_id": LOCAL_WORKSPACE_ID, "business_id": business_id},
        )
        assert response.status_code == 409
        assert "run an assessment" in response.json()["detail"].lower()
    finally:
        with db() as connection:
            connection.execute("DELETE FROM businesses WHERE id=?", (business_id,))
