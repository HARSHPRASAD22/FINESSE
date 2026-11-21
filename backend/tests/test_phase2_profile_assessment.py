import uuid

from fastapi.testclient import TestClient

from app.main import LOCAL_USER_ID, app, db


client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))


def cleanup_test_business(workspace_id: str, business_id: str) -> None:
    with db() as connection:
        connection.execute(
            "DELETE FROM assessment_evidence WHERE assessment_result_id IN "
            "(SELECT id FROM assessment_results WHERE assessment_id IN "
            "(SELECT id FROM assessments WHERE business_id=?))",
            (business_id,),
        )
        connection.execute(
            "DELETE FROM assessment_results WHERE assessment_id IN "
            "(SELECT id FROM assessments WHERE business_id=?)",
            (business_id,),
        )
        connection.execute("DELETE FROM assessments WHERE business_id=?", (business_id,))
        connection.execute("DELETE FROM business_profile_versions WHERE business_id=?", (business_id,))
        connection.execute("DELETE FROM businesses WHERE id=?", (business_id,))
        connection.execute("DELETE FROM workspace_members WHERE workspace_id=?", (workspace_id,))
        connection.execute("DELETE FROM workspaces WHERE id=?", (workspace_id,))


def test_confirm_profile_creates_revision_and_assessment():
    workspace_id = f"user-{uuid.uuid4()}"
    business_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute(
            "INSERT INTO workspaces (id,name,jurisdiction) VALUES (?,?,?)",
            (workspace_id, "Test Workspace", "West Bengal"),
        )
        connection.execute(
            "INSERT INTO workspace_members (workspace_id,user_id,role) VALUES (?,?,?)",
            (workspace_id, LOCAL_USER_ID, "owner"),
        )
        connection.execute(
            "INSERT INTO businesses "
            "(id,workspace_id,business_name,business_type,country,state,city) "
            "VALUES (?,?,?,?,?,?,?)",
            (business_id, workspace_id, "Test Bakery", "home_bakery", "India", "West Bengal", "Kolkata"),
        )
    try:
        response = client.post(
            f"/api/v1/businesses/{business_id}/confirm-profile",
            json={
                "original_description": "A home bakery in Kolkata",
                "facts": {
                    "business_name": "Test Bakery",
                    "business_type": "home_bakery",
                    "country": "India",
                    "state": "West Bengal",
                    "city": "Kolkata",
                    "activities": ["baking", "online_sales"],
                    "premises": "residential_kitchen",
                    "employee_count": None,
                    "annual_turnover": None,
                },
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["profile"]["version_number"] == 1
        assert payload["assessment"]["profile_revision"] == 1
        assert payload["assessment"]["status"] == "completed"
        assert payload["assessment"]["results"]
    finally:
        cleanup_test_business(workspace_id, business_id)


def test_profile_revision_is_incremented_not_overwritten():
    workspace_id = f"user-{uuid.uuid4()}"
    business_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute(
            "INSERT INTO workspaces (id,name,jurisdiction) VALUES (?,?,?)",
            (workspace_id, "Test Workspace", "West Bengal"),
        )
        connection.execute(
            "INSERT INTO workspace_members (workspace_id,user_id,role) VALUES (?,?,?)",
            (workspace_id, LOCAL_USER_ID, "owner"),
        )
        connection.execute(
            "INSERT INTO businesses "
            "(id,workspace_id,business_name,business_type,country,state,city) "
            "VALUES (?,?,?,?,?,?,?)",
            (business_id, workspace_id, "Test Bakery", "home_bakery", "India", "West Bengal", "Kolkata"),
        )
    try:
        facts = {
            "original_description": "A home bakery in Kolkata",
            "facts": {
                "business_name": "Test Bakery",
                "business_type": "home_bakery",
                "country": "India",
                "state": "West Bengal",
                "city": "Kolkata",
                "activities": ["baking"],
                "premises": "residential_kitchen",
                "employee_count": None,
                "annual_turnover": None,
            },
        }
        first = client.post(f"/api/v1/businesses/{business_id}/confirm-profile", json=facts)
        second = client.post(f"/api/v1/businesses/{business_id}/confirm-profile", json=facts)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json()["profile"]["version_number"] == 2
    finally:
        cleanup_test_business(workspace_id, business_id)
