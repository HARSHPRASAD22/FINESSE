import json
from io import BytesIO
import uuid

from fastapi.testclient import TestClient
from pypdf import PdfReader
from reportlab.pdfgen import canvas

import app.main as agent_module
from app.integrations import gemini, source_research
from app.main import LOCAL_WORKSPACE_ID, UPLOAD_DIR, app, db, infer_agent_facts, next_agent_question


client = TestClient(app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000))


def test_gemini_grounded_search_returns_only_official_citations(monkeypatch):
    request_payload = {}
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "candidates": [{
                    "content": {"parts": [{"text": "Current registration information."}]},
                    "groundingMetadata": {
                        "groundingChunks": [
                            {"web": {"uri": "https://labour.wb.gov.in/shops", "title": "West Bengal Labour"}},
                            {"web": {"uri": "https://example.com/unofficial", "title": "Unofficial"}},
                            {"web": {"uri": "http://wb.gov.in/insecure", "title": "Insecure"}},
                        ],
                    },
                }],
            }

    def fake_post(url, **kwargs):
        request_payload.update(kwargs["json"])
        return FakeResponse()

    monkeypatch.setattr(gemini.httpx, "post", fake_post)
    result = gemini.GeminiProvider().search_grounded("Find registration information")

    assert request_payload["tools"] == [{"google_search": {}}]
    assert result["status"] == "available"
    assert result["answer"] == "Current registration information."
    assert result["sources"] == [{
        "url": "https://labour.wb.gov.in/shops",
        "title": "West Bengal Labour",
    }]


def test_goal_prefills_known_retail_activity_and_location():
    memory = infer_agent_facts("I want to open a retail shop in Kolkata")

    assert memory["industry"] == "retail"
    assert memory["activity"] == "Retail sale of goods"
    assert memory["location"] == "Kolkata"
    assert next_agent_question(memory)[0] == "business_name"


def test_simulation_endpoint_returns_candidate_outcome():
    response = client.post(
        f"/api/v1/simulations?workspace_id={LOCAL_WORKSPACE_ID}&employee_count=4&sell_online=true"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["simulation_id"]
    assert isinstance(result["baseline_requirements"], int)
    assert isinstance(result["scenario_requirements"], int)
    assert result["verification_state"] == "CANDIDATE"
    with db() as connection:
        connection.execute("DELETE FROM simulations WHERE id=?", (result["simulation_id"],))


def test_unconfirmed_business_has_no_assumed_sector_requirements():
    business_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute(
            "INSERT INTO businesses "
            "(id,workspace_id,business_name,business_type,country,state,city) "
            "VALUES (?,?,?,?,?,?,?)",
            (business_id, LOCAL_WORKSPACE_ID, "Unconfirmed Shop", "small_business", "India", "West Bengal", "Kolkata"),
        )
    try:
        response = client.get(f"/api/v1/businesses/{business_id}/requirements")

        assert response.status_code == 200
        assert response.json()["profile_confirmed"] is False
        assert response.json()["results"] == []
    finally:
        with db() as connection:
            connection.execute("DELETE FROM businesses WHERE id=?", (business_id,))


def test_seeded_demo_update_is_hidden_without_deleting_its_record():
    demo_id = "update-demo-001"
    inserted_for_test = False
    with db() as connection:
        existing = connection.execute(
            "SELECT id FROM regulatory_updates WHERE id=?",
            (demo_id,),
        ).fetchone()
        if not existing:
            connection.execute(
                "INSERT INTO regulatory_updates (id,title,authority,jurisdiction,review_state) "
                "VALUES (?,?,?,?,?)",
                (demo_id, "Home-based food activity guidance", "West Bengal Labour Department", "IN-WB", "candidate"),
            )
            inserted_for_test = True
    try:
        response = client.get("/api/v1/regulatory/updates")

        assert response.status_code == 200
        assert all(update["id"] != demo_id for update in response.json()["updates"])
        with db() as connection:
            assert connection.execute(
                "SELECT id FROM regulatory_updates WHERE id=?",
                (demo_id,),
            ).fetchone()
    finally:
        if inserted_for_test:
            with db() as connection:
                connection.execute("DELETE FROM regulatory_updates WHERE id=?", (demo_id,))


def test_source_scan_persists_captured_source_url(monkeypatch):
    source_url = "https://example.gov.in/services"
    content_hash = uuid.uuid4().hex * 2
    update_id = f"scan-{content_hash[:12]}"

    def fake_capture_source(url, timeout=20):
        return {
            "canonical_url": url,
            "title": "Official services",
            "content_hash": content_hash,
        }

    monkeypatch.setitem(agent_module.AGENT_SOURCE_TARGETS, "common", [("Test Authority", source_url, "IN-WB")])
    monkeypatch.setitem(agent_module.AGENT_SOURCE_TARGETS, "food", [])
    monkeypatch.setattr(agent_module, "capture_source", fake_capture_source)

    try:
        scan = client.post("/api/v1/regulatory/scans")
        updates = client.get("/api/v1/regulatory/updates")

        assert scan.status_code == 200
        assert scan.json()["captured_count"] == 1
        source_record = next(item for item in updates.json()["updates"] if item["id"] == update_id)
        assert source_record["url"] == source_url
    finally:
        with db() as connection:
            connection.execute("DELETE FROM regulatory_updates WHERE id=?", (update_id,))


def test_site_extraction_follows_only_bounded_relevant_same_host_links(monkeypatch):
    root_url = "https://wbshopsonline.gov.in/"
    relevant_url = "https://wbshopsonline.gov.in/registration"
    requested_urls = []

    def fake_capture_source(url, timeout=20):
        requested_urls.append(url)
        if url == root_url:
            return {
                "canonical_url": root_url,
                "title": "Official home",
                "content_hash": "root",
                "text_excerpt": "Home page.",
                "links": [
                    {"title": "About", "url": "https://wbshopsonline.gov.in/about"},
                    {"title": "Registration", "url": "https://www.gst.gov.in/registration"},
                    {"title": "Registration", "url": relevant_url},
                    {"title": "Application form", "url": "https://wbshopsonline.gov.in/form.pdf"},
                    {"title": "License application", "url": "https://wbshopsonline.gov.in/license"},
                ],
            }
        return {
            "canonical_url": url,
            "title": "Registration",
            "content_hash": "page",
            "text_excerpt": "Registration instructions.",
            "links": [],
        }

    monkeypatch.setattr(source_research, "capture_source", fake_capture_source)

    pages = source_research.capture_site_pages(root_url, max_linked_pages=1, timeout=1)

    assert requested_urls == [root_url, relevant_url]
    assert [page["depth"] for page in pages] == [0, 1]
    assert all(page["captured"] for page in pages)


def test_site_extraction_marks_404_links_as_not_found(monkeypatch):
    root_url = "https://wbshopsonline.gov.in/"
    missing_url = "https://wbshopsonline.gov.in/application-form"

    def fake_capture_source(url, timeout=20):
        if url == root_url:
            return {
                "canonical_url": root_url,
                "title": "Official home",
                "content_hash": "root",
                "text_excerpt": "Home page.",
                "links": [{"title": "Application form", "url": missing_url}],
            }
        request = source_research.httpx.Request("GET", url)
        response = source_research.httpx.Response(404, request=request)
        raise source_research.httpx.HTTPStatusError(
            "Not found",
            request=request,
            response=response,
        )

    monkeypatch.setattr(source_research, "capture_source", fake_capture_source)

    pages = source_research.capture_site_pages(root_url, max_linked_pages=1)

    assert pages[1]["captured"] is False
    assert pages[1]["validation_status"] == "not_found"
    assert pages[1]["http_status"] == 404


def test_agent_marks_dead_form_links_as_not_found(monkeypatch):
    session_id = str(uuid.uuid4())
    root_url = "https://wbshopsonline.gov.in/"
    missing_url = "https://wbshopsonline.gov.in/forms/licence-application"
    memory = {
        "goal": "Open a retail shop in Kolkata",
        "industry": "retail",
        "location": "Kolkata",
        "_inferred_fields": [],
    }

    def fake_capture_source(url, timeout=20):
        if url == root_url:
            return {
                "canonical_url": root_url,
                "title": "Official services",
                "content_hash": "root",
                "text_excerpt": "Business services.",
                "content_type": "text/html",
                "status_code": 200,
                "links": [{"title": "Licence application form", "url": missing_url}],
            }
        request = source_research.httpx.Request("GET", url)
        response = source_research.httpx.Response(404, request=request)
        raise source_research.httpx.HTTPStatusError(
            "Not found",
            request=request,
            response=response,
        )

    monkeypatch.setitem(agent_module.AGENT_SOURCE_TARGETS, "common", [("Test Authority", root_url, "Test services")])
    monkeypatch.setitem(agent_module.AGENT_SOURCE_TARGETS, "food", [])
    monkeypatch.setattr(source_research, "capture_source", fake_capture_source)
    monkeypatch.setattr(agent_module, "capture_source", fake_capture_source)
    monkeypatch.setattr(
        agent_module,
        "summarize_public_sources",
        lambda sources: {"status": "not_configured", "summaries": []},
    )
    with db() as connection:
        connection.execute(
            "INSERT INTO agent_sessions "
            "(id,workspace_id,goal,stage,memory_json,messages_json,status) "
            "VALUES (?,?,?,?,?,?,?)",
            (session_id, LOCAL_WORKSPACE_ID, memory["goal"], "ready_to_research", json.dumps(memory), "[]", "active"),
        )
    try:
        response = client.post(f"/api/v1/agent/sessions/{session_id}/research")

        assert response.status_code == 200
        result = response.json()
        assert result["forms"][0]["validation_status"] == "not_found"
        assert result["forms"][0]["http_status"] == 404
        assert result["forms"][0]["status"] == "not_found"
        assert any(source.get("validation_status") == "not_found" for source in result["sources"])
    finally:
        with db() as connection:
            connection.execute("DELETE FROM agent_sessions WHERE id=?", (session_id,))


def test_retail_research_does_not_add_food_forms(monkeypatch):
    session_id = str(uuid.uuid4())
    memory = {
        "goal": "Open a retail shop in Kolkata",
        "jurisdiction": "West Bengal, India",
        "industry": "retail",
        "business_name": "Test Shop",
        "activity": "Retail sale of goods",
        "location": "Kolkata",
        "premises": "commercial",
        "owner_name": "Test Owner",
        "address": "Test Address",
        "_skipped": [],
    }
    visited_urls = []

    def fake_capture_source(url, timeout=20):
        visited_urls.append(url)
        return {
            "canonical_url": url,
            "title": "Official services",
            "content_hash": "abc123",
            "text_excerpt": "Public official information.",
            "content_type": "text/html",
            "links": [
                {
                    "title": "Business application form",
                    "url": "https://wbshopsonline.gov.in/application-form.pdf",
                }
            ],
        }

    def fake_capture_document(url, timeout=10, cache_directory=None):
        return {
            "official_url": url,
            "document_type": "PDF",
            "content_type": "application/pdf",
            "byte_size": 1024,
            "content_hash": "form-hash",
            "preview_status": "available",
            "page_count": 1,
            "text_excerpt": "Business application form",
            "fillable_fields": [],
        }

    class FakeGeminiProvider:
        def generate_structured(self, prompt, system_prompt):
            assert "Test Owner" not in prompt
            assert "Test Address" not in prompt
            first_url = json.loads(prompt)["public_pages"][0]["url"]
            return {
                "summaries": [{
                    "source_url": first_url,
                    "findings": [
                        {
                            "statement": "The page contains public official information.",
                            "evidence_quote": "Public official information.",
                        },
                        {
                            "statement": "Unsupported invented claim.",
                            "evidence_quote": "Invented requirement.",
                        },
                    ],
                }],
            }

    monkeypatch.setattr(source_research, "capture_source", fake_capture_source)
    monkeypatch.setattr(agent_module, "capture_official_document", fake_capture_document)
    monkeypatch.setattr(agent_module, "GeminiProvider", FakeGeminiProvider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with db() as connection:
        connection.execute(
            "INSERT INTO agent_sessions "
            "(id,workspace_id,goal,stage,memory_json,messages_json,status) "
            "VALUES (?,?,?,?,?,?,?)",
            (session_id, LOCAL_WORKSPACE_ID, memory["goal"], "ready_to_research", json.dumps(memory), "[]", "active"),
        )
    try:
        response = client.post(f"/api/v1/agent/sessions/{session_id}/research")

        assert response.status_code == 200
        result = response.json()
        assert not any("fssai" in url.lower() for url in visited_urls)
        assert result["forms"][0]["official_url"].endswith("application-form.pdf")
        assert result["forms"][0]["status"] == "document_available"
        assert result["forms"][0]["validation_status"] == "working"
        assert result["forms"][0]["text_excerpt"] == "Business application form"
        assert result["status"] == "research_complete"
        assert result["summary_status"] == "available"
        assert len(result["source_summaries"][0]["findings"]) == 1
        assert result["source_summaries"][0]["findings"][0]["evidence_quote"] == "Public official information."
        retry = client.post(f"/api/v1/agent/sessions/{session_id}/research")
        assert retry.status_code == 200
        assert retry.json()["status"] == "research_complete"
        review_response = client.post(f"/api/v1/agent/sessions/{session_id}/generate")
        assert review_response.status_code == 200
        review = review_response.json()["review"]
        assert "not an official form" in review["form_title"].lower()
        assert review["source_summaries"] == result["source_summaries"]
        assert review["submission_allowed"] is False
        approval = client.post(
            f"/api/v1/agent/sessions/{session_id}/approve",
            params={"reviewer_name": "Test Reviewer"},
        )
        assert approval.status_code == 200
        assert approval.json()["government_submission"] is False
    finally:
        with db() as connection:
            connection.execute("DELETE FROM agent_sessions WHERE id=?", (session_id,))
        pdf_path = UPLOAD_DIR / "generated" / f"{session_id}-preparation-sheet.pdf"
        if pdf_path.exists():
            pdf_path.unlink()


def test_failed_shops_portal_fetch_uses_gemini_live_search(monkeypatch):
    session_id = str(uuid.uuid4())
    memory = {
        "goal": "Open a retail shop in Kolkata",
        "jurisdiction": "West Bengal, India",
        "industry": "retail",
        "business_name": "Test Shop",
        "activity": "Retail sale of goods",
        "location": "Kolkata",
        "premises": "commercial",
        "owner_name": None,
        "address": None,
        "_skipped": [],
        "_inferred_fields": [],
    }

    def fail_capture(url, timeout=20):
        raise agent_module.httpx.ConnectError("DNS unavailable")

    class FakeGeminiProvider:
        def search_grounded(self, prompt):
            assert "West Bengal" in prompt
            return {
                "status": "available",
                "answer": "Use the official labour department service.",
                "sources": [{"url": "https://labour.wb.gov.in/shops", "title": "West Bengal Labour"}],
                "queries": ["West Bengal shops registration"],
            }

    monkeypatch.setitem(
        agent_module.AGENT_SOURCE_TARGETS,
        "common",
        [("West Bengal Shops & Establishments", "https://wbshopsonline.gov.in/", "Labour portal")],
    )
    monkeypatch.setitem(agent_module.AGENT_SOURCE_TARGETS, "food", [])
    monkeypatch.setattr(source_research, "capture_source", fail_capture)
    monkeypatch.setattr(agent_module, "GeminiProvider", FakeGeminiProvider)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    with db() as connection:
        connection.execute(
            "INSERT INTO agent_sessions "
            "(id,workspace_id,goal,stage,memory_json,messages_json,status) "
            "VALUES (?,?,?,?,?,?,?)",
            (session_id, LOCAL_WORKSPACE_ID, memory["goal"], "ready_to_research", json.dumps(memory), "[]", "active"),
        )
    try:
        response = client.post(f"/api/v1/agent/sessions/{session_id}/research")

        assert response.status_code == 200
        result = response.json()
        assert result["live_search"]["status"] == "available"
        assert result["live_search"]["sources"][0]["url"] == "https://labour.wb.gov.in/shops"
        review_response = client.post(f"/api/v1/agent/sessions/{session_id}/generate")
        assert review_response.status_code == 200
        assert review_response.json()["review"]["live_search"] == result["live_search"]
    finally:
        with db() as connection:
            connection.execute("DELETE FROM agent_sessions WHERE id=?", (session_id,))
        pdf_path = UPLOAD_DIR / "generated" / f"{session_id}-preparation-sheet.pdf"
        if pdf_path.exists():
            pdf_path.unlink()


def test_unsupported_jurisdiction_does_not_fetch_sources(monkeypatch):
    session_id = str(uuid.uuid4())
    memory = {
        "goal": "Open a retail shop in Boston",
        "industry": "retail",
        "location": "Boston",
        "_inferred_fields": [],
    }

    def fail_if_called(url, timeout=20):
        raise AssertionError(f"Unexpected source request: {url}")

    monkeypatch.setattr(source_research, "capture_source", fail_if_called)
    with db() as connection:
        connection.execute(
            "INSERT INTO agent_sessions "
            "(id,workspace_id,goal,stage,memory_json,messages_json,status) "
            "VALUES (?,?,?,?,?,?,?)",
            (session_id, LOCAL_WORKSPACE_ID, memory["goal"], "ready_to_research", json.dumps(memory), "[]", "active"),
        )
    try:
        response = client.post(f"/api/v1/agent/sessions/{session_id}/research")

        assert response.status_code == 200
        assert response.json()["status"] == "unsupported_jurisdiction"
        assert response.json()["sources"] == []
        assert response.json()["forms"] == []
    finally:
        with db() as connection:
            connection.execute("DELETE FROM agent_sessions WHERE id=?", (session_id,))


def test_source_capture_lists_only_allowlisted_official_form_links(monkeypatch):
    source_url = "https://wbshopsonline.gov.in/"
    html = (
        '<html><title>Services</title><body>Registration guidance.'
        '<a href="/forms/trade-license">Trade license application</a>'
        '<a href="https://example.com/download-form.pdf">External form</a>'
        "</body></html>"
    )

    def fake_get(url, **kwargs):
        return source_research.httpx.Response(
            200,
            text=html,
            request=source_research.httpx.Request("GET", url),
        )

    monkeypatch.setattr(source_research.httpx, "get", fake_get)

    captured = source_research.capture_source(source_url)

    assert captured["title"] == "Services"
    assert captured["links"] == [{
        "title": "Trade license application",
        "url": "https://wbshopsonline.gov.in/forms/trade-license",
    }]


def test_source_capture_retries_transient_timeout(monkeypatch):
    source_url = "https://wbshopsonline.gov.in/"
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise source_research.httpx.ConnectTimeout(
                "TLS handshake timed out",
                request=source_research.httpx.Request("GET", url),
            )
        return source_research.httpx.Response(
            200,
            text="<html><title>Official portal</title><body>Registration guidance.</body></html>",
            request=source_research.httpx.Request("GET", url),
        )

    monkeypatch.setattr(source_research.httpx, "get", fake_get)

    captured = source_research.capture_source(source_url, timeout=1)

    assert calls == [source_url, source_url]
    assert captured["title"] == "Official portal"


def test_official_pdf_form_is_fetched_and_text_previewed(monkeypatch):
    form_url = "https://wbshopsonline.gov.in/forms/application.pdf"
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    pdf.drawString(72, 740, "Official application form")
    pdf.drawString(72, 720, "Applicant name: __________________")
    pdf.save()
    pdf_bytes = pdf_buffer.getvalue()

    def fake_get(url, **kwargs):
        return source_research.httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=source_research.httpx.Request("GET", url),
        )

    monkeypatch.setattr(source_research.httpx, "get", fake_get)

    form = source_research.capture_official_document(form_url)

    assert form["document_type"] == "PDF"
    assert form["preview_status"] == "available"
    assert "Applicant name" in form["text_excerpt"]
    assert form["page_count"] == 1
    assert form["byte_size"] == len(pdf_bytes)


def test_official_fillable_pdf_can_be_previewed_and_filled(monkeypatch):
    form_url = "https://wbshopsonline.gov.in/forms/application.pdf"
    session_id = str(uuid.uuid4())
    pdf_buffer = BytesIO()
    pdf = canvas.Canvas(pdf_buffer)
    pdf.drawString(72, 740, "Official application form")
    pdf.acroForm.textfield(
        name="applicant_name",
        tooltip="Applicant name",
        x=72,
        y=700,
        width=250,
        height=20,
    )
    pdf.save()
    pdf_bytes = pdf_buffer.getvalue()

    def fake_get(url, **kwargs):
        return source_research.httpx.Response(
            200,
            content=pdf_bytes,
            headers={"content-type": "application/pdf"},
            request=source_research.httpx.Request("GET", url),
        )

    monkeypatch.setattr(source_research.httpx, "get", fake_get)
    form = source_research.capture_official_document(
        form_url,
        cache_directory=agent_module.FORM_CACHE_DIR,
    )
    memory = {
        "_research": {
            "forms": [{
                "official_url": form_url,
                "content_hash": form["content_hash"],
                "document_type": "PDF",
                "status": "document_available",
                "fillable_fields": form["fillable_fields"],
            }],
        },
    }
    with db() as connection:
        connection.execute(
            "INSERT INTO agent_sessions "
            "(id,workspace_id,goal,stage,memory_json,messages_json,status) "
            "VALUES (?,?,?,?,?,?,?)",
            (session_id, LOCAL_WORKSPACE_ID, "Test application", "research_complete", json.dumps(memory), "[]", "active"),
        )
    try:
        preview = client.get(
            f"/api/v1/agent/sessions/{session_id}/forms/{form['content_hash']}/preview"
        )
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "application/pdf"
        assert "inline" in preview.headers["content-disposition"]

        filled = client.post(
            f"/api/v1/agent/sessions/{session_id}/forms/{form['content_hash']}/fill",
            json={"fields": {"applicant_name": "Asha Sen"}},
        )
        assert filled.status_code == 200
        assert PdfReader(BytesIO(filled.content)).get_fields()["applicant_name"].get("/V") == "Asha Sen"

        rejected = client.post(
            f"/api/v1/agent/sessions/{session_id}/forms/{form['content_hash']}/fill",
            json={"fields": {"not_a_pdf_field": "ignored"}},
        )
        assert rejected.status_code == 422
    finally:
        with db() as connection:
            connection.execute("DELETE FROM agent_sessions WHERE id=?", (session_id,))
        (agent_module.FORM_CACHE_DIR / f"{form['content_hash']}.pdf").unlink(missing_ok=True)


def test_source_capture_rejects_redirect_outside_official_allowlist(monkeypatch):
    source_url = "https://wbshopsonline.gov.in/"
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return source_research.httpx.Response(
            302,
            headers={"location": "http://127.0.0.1/private"},
            request=source_research.httpx.Request("GET", url),
        )

    monkeypatch.setattr(source_research.httpx, "get", fake_get)

    try:
        source_research.capture_source(source_url)
    except ValueError as error:
        assert "allowlisted" in str(error)
    else:
        raise AssertionError("A redirect outside the allowlist should be rejected")
    assert calls == [source_url]
