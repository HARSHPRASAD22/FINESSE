import json
import pytest
import uuid
from fastapi.testclient import TestClient

import app.main as main
from app.demo_access import SESSION_TTL_SECONDS, create_session_token, verify_session_token
from app.main import LOCAL_WORKSPACE_ID, db


@pytest.mark.parametrize("token", ["", "not-a-token", "abc.bad", "é.signature", "a" * 129])
def test_invalid_demo_session_tokens_are_rejected(token):
    assert verify_session_token(token, "test-secret", now=1000) is False


def test_demo_session_token_is_signed_and_expires():
    token = create_session_token("test-secret", now=1000)

    assert verify_session_token(token, "test-secret", now=1000) is True
    assert verify_session_token(token, "different-secret", now=1000) is False
    assert verify_session_token(token, "test-secret", now=1000 + SESSION_TTL_SECONDS) is False


@pytest.fixture
def private_demo_client(monkeypatch):
    monkeypatch.setattr(main, "PRIVATE_DEMO_MODE", True)
    monkeypatch.setattr(main, "DEMO_ACCESS_CODE", "a-generated-demo-code-long-enough")
    monkeypatch.setattr(main, "DEMO_SESSION_SECRET", "s" * 48)
    return TestClient(main.app, base_url="https://permitpilot.test", client=("203.0.113.1", 50000))


def test_private_demo_requires_access_code_for_application_api(private_demo_client):
    response = private_demo_client.get("/api/v1/workspaces")

    assert response.status_code == 401
    assert response.json() == {"detail": "Demo access required"}


def test_private_demo_login_sets_secure_session_and_unlocks_api(private_demo_client):
    response = private_demo_client.post(
        "/api/v1/demo/login",
        json={"code": "a-generated-demo-code-long-enough"},
    )

    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert "secure" in response.headers["set-cookie"].lower()
    assert private_demo_client.get("/api/v1/workspaces").status_code == 200


def test_private_demo_rejects_wrong_code(private_demo_client):
    response = private_demo_client.post("/api/v1/demo/login", json={"code": "wrong"})

    assert response.status_code == 401
    assert private_demo_client.get("/api/v1/workspaces").status_code == 401


def test_health_check_is_public_and_contains_no_workspace_data(private_demo_client):
    response = private_demo_client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_static_frontend_serves_assets_and_spa_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "PRIVATE_DEMO_MODE", False)
    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", tmp_path)
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<main>PermitPilot</main>", encoding="utf-8")
    (tmp_path / "assets" / "app.css").write_text("body{color:black}", encoding="utf-8")
    client = TestClient(main.app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))

    assert client.get("/").text == "<main>PermitPilot</main>"
    assert client.get("/assets/app.css").text == "body{color:black}"
    assert client.get("/workspace-route").text == "<main>PermitPilot</main>"
    assert client.get("/api/v1/not-found").status_code == 404


@pytest.fixture
def saved_assessment():
    business_id = str(uuid.uuid4())
    assessment_id = str(uuid.uuid4())
    result = {
        "rule_id": "TEST-RULE-001",
        "rule_version": 1,
        "title": "Candidate registration check",
        "status": "APPLICABLE",
        "authority": "Test Authority",
        "jurisdiction": "IN-WB",
        "source_type": "CANDIDATE",
        "source": "Official source verification pending",
        "matched_conditions": ["business_activity"],
        "missing_facts": [],
    }
    with db() as connection:
        connection.execute(
            "INSERT INTO businesses (id,workspace_id,business_name,business_type,country,state,city) "
            "VALUES (?,?,?,?,?,?,?)",
            (business_id, LOCAL_WORKSPACE_ID, "Test business", "small_business", "India", "West Bengal", "Kolkata"),
        )
        connection.execute(
            "INSERT INTO business_profile_versions (id,business_id,version_number,structured_facts) "
            "VALUES (?,?,?,?)",
            (str(uuid.uuid4()), business_id, 1, json.dumps({"activities": ["retail"]})),
        )
        connection.execute(
            "INSERT INTO assessments (id,workspace_id,profile_revision,status,results_json,business_id) "
            "VALUES (?,?,?,?,?,?)",
            (assessment_id, LOCAL_WORKSPACE_ID, 1, "completed", json.dumps([result]), business_id),
        )
    try:
        yield assessment_id
    finally:
        with db() as connection:
            connection.execute("DELETE FROM assessments WHERE id=?", (assessment_id,))
            connection.execute("DELETE FROM business_profile_versions WHERE business_id=?", (business_id,))
            connection.execute("DELETE FROM businesses WHERE id=?", (business_id,))


def test_missing_gemini_key_returns_a_readable_saved_evidence_summary(saved_assessment, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    client = TestClient(main.app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))

    response = client.post(
        "/api/v1/requirements/question",
        json={"assessment_id": saved_assessment, "rule_id": "TEST-RULE-001", "question": "Why is this listed?"},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["provider"] == "evidence_fallback"
    assert "not a legal conclusion" in payload["answer"]
    assert "CANDIDATE" in " ".join(payload["evidence_used"])
    assert "context" not in payload


def test_gemini_error_details_are_not_returned_to_the_browser(saved_assessment, monkeypatch, caplog):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    def fail_with_sensitive_detail(*args, **kwargs):
        raise ValueError("private-test-key-in-request-url")

    monkeypatch.setattr(main.GeminiProvider, "generate_structured", fail_with_sensitive_detail)
    client = TestClient(main.app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))
    response = client.post(
        "/api/v1/requirements/question",
        json={"assessment_id": saved_assessment, "rule_id": "TEST-RULE-001", "question": "Why is this listed?"},
    )

    assert response.status_code == 200
    assert response.json()["provider"] == "evidence_fallback"
    assert response.json()["provider_error"] == "gemini_request_failed"
    assert "private-test-key-in-request-url" not in response.text
    assert "private-test-key-in-request-url" not in caplog.text
