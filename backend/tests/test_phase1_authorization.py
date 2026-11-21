import uuid

from fastapi.testclient import TestClient

from app.main import LOCAL_WORKSPACE_ID, app, db


client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))


def test_local_dashboard_starts_without_login():
    response = client.get("/api/v1/workspaces")

    assert response.status_code == 200
    assert [workspace["id"] for workspace in response.json()["items"]] == [LOCAL_WORKSPACE_ID]


def test_forwarded_remote_request_is_rejected():
    response = client.get("/api/v1/workspaces", headers={"x-forwarded-for": "203.0.113.1"})

    assert response.status_code == 403


def test_other_workspace_business_is_not_visible_to_local_user():
    workspace_id = f"test-workspace-{uuid.uuid4()}"
    business_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute(
            "INSERT INTO workspaces (id,name,jurisdiction) VALUES (?,?,?)",
            (workspace_id, "Isolated Test Workspace", "West Bengal"),
        )
        connection.execute(
            "INSERT INTO businesses "
            "(id,workspace_id,business_name,business_type,country,state,city) "
            "VALUES (?,?,?,?,?,?,?)",
            (business_id, workspace_id, "Private Test Business", "small_business", "India", "West Bengal", "Kolkata"),
        )
    try:
        response = client.get(f"/api/v1/businesses/{business_id}/profile-history")
        assert response.status_code == 403
    finally:
        with db() as connection:
            connection.execute("DELETE FROM businesses WHERE id=?", (business_id,))
            connection.execute("DELETE FROM workspaces WHERE id=?", (workspace_id,))


def test_other_workspace_document_cannot_be_reviewed():
    workspace_id = f"test-workspace-{uuid.uuid4()}"
    document_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute(
            "INSERT INTO workspaces (id,name,jurisdiction) VALUES (?,?,?)",
            (workspace_id, "Isolated Test Workspace", "West Bengal"),
        )
        connection.execute(
            "INSERT INTO documents "
            "(id,workspace_id,filename,mime_type,size_bytes,storage_path,state,extracted_json) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (document_id, workspace_id, "private.pdf", "application/pdf", 1, "test/private.pdf", "needs_review", "{}"),
        )
    try:
        response = client.post(
            f"/api/v1/documents/{document_id}/review",
            json={"document_name": "confirmed"},
        )
        assert response.status_code == 403
    finally:
        with db() as connection:
            connection.execute("DELETE FROM documents WHERE id=?", (document_id,))
            connection.execute("DELETE FROM workspaces WHERE id=?", (workspace_id,))
