import json
import io
import hmac
import ipaddress
import logging
import os
import re
import sqlite3
import textwrap
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
import httpx
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from bs4 import BeautifulSoup
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from app.integrations.source_research import (
    capture_official_document,
    capture_site_pages,
    capture_source,
    capture_failure_details,
    describe_capture_error,
    is_official_document_link,
)
from dotenv import load_dotenv
from app.integrations.gemini import GeminiProvider
from app.rules import evaluate_profile
from datetime import date
from app.demo_access import create_session_token, verify_session_token

load_dotenv()
logger = logging.getLogger(__name__)

LOCAL_USER_ID = "local-single-user"
LOCAL_WORKSPACE_ID = "local-workspace"
PRIVATE_DEMO_MODE = os.getenv("APP_ENV", "development").lower() == "private_demo"
DEMO_ACCESS_CODE = os.getenv("DEMO_ACCESS_CODE", "")
DEMO_SESSION_SECRET = os.getenv("DEMO_SESSION_SECRET", "")
DEMO_SESSION_COOKIE = "permitpilot-demo-session"
if PRIVATE_DEMO_MODE:
    if not 20 <= len(DEMO_ACCESS_CODE) <= 256:
        raise RuntimeError("DEMO_ACCESS_CODE must be 20 to 256 characters in private demo mode")
    if len(DEMO_SESSION_SECRET) < 32:
        raise RuntimeError("DEMO_SESSION_SECRET must be at least 32 characters in private demo mode")


def get_local_user() -> dict:
    return {"id": LOCAL_USER_ID, "email": "local@permitpilot"}


def authorize_workspace(workspace_id: str, user: dict | None) -> None:
    if user is None or user.get("id") != LOCAL_USER_ID:
        raise HTTPException(status_code=403, detail="Workspace access denied")
    with db() as connection:
        membership = connection.execute(
            "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
            (workspace_id, user["id"]),
        ).fetchone()
    if membership is None:
        raise HTTPException(status_code=403, detail="Workspace access denied")


def require_reviewer(user: dict | None) -> None:
    if user is None or user.get("id") != LOCAL_USER_ID:
        raise HTTPException(status_code=403, detail="Local workspace access required")
    with db() as connection:
        membership = connection.execute(
            "SELECT role FROM workspace_members WHERE workspace_id=? AND user_id=?",
            (LOCAL_WORKSPACE_ID, LOCAL_USER_ID),
        ).fetchone()
    if membership is None or membership["role"] != "owner":
        raise HTTPException(status_code=403, detail="Reviewer authorization required")

DB_PATH = Path(os.getenv("DATABASE_PATH") or Path(__file__).resolve().parent.parent / "permitpilot.db")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR") or Path(__file__).resolve().parent.parent / "uploads")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
FORM_CACHE_DIR = UPLOAD_DIR / "generated" / "official-forms"


def db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_db():
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, jurisdiction TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS workspace_settings (
                workspace_id TEXT PRIMARY KEY,
                assessment_notifications INTEGER NOT NULL DEFAULT 1,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );
            CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'owner',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (workspace_id, user_id),
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );
            CREATE TABLE IF NOT EXISTS businesses (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                business_name TEXT NOT NULL,
                business_type TEXT,
                country TEXT NOT NULL DEFAULT 'India',
                state TEXT NOT NULL DEFAULT 'West Bengal',
                city TEXT,
                current_profile_version TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );
            CREATE TABLE IF NOT EXISTS business_profile_versions (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                structured_facts TEXT NOT NULL,
                original_description TEXT,
                confirmed_by TEXT,
                confirmed_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES businesses(id),
                UNIQUE (business_id, version_number)
            );
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, revision INTEGER NOT NULL,
                facts_json TEXT NOT NULL, confirmed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS assessments (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, profile_revision INTEGER NOT NULL,
                status TEXT NOT NULL, results_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS assessment_results (
                id TEXT PRIMARY KEY,
                assessment_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                rule_version INTEGER NOT NULL,
                status TEXT NOT NULL,
                matched_conditions TEXT NOT NULL DEFAULT '[]',
                unmet_conditions TEXT NOT NULL DEFAULT '[]',
                missing_facts TEXT NOT NULL DEFAULT '[]',
                exceptions_triggered TEXT NOT NULL DEFAULT '[]',
                explanation_codes TEXT NOT NULL DEFAULT '[]',
                verification_state TEXT NOT NULL DEFAULT 'CANDIDATE',
                FOREIGN KEY (assessment_id) REFERENCES assessments(id)
            );
            CREATE TABLE IF NOT EXISTS assessment_evidence (
                id TEXT PRIMARY KEY,
                assessment_result_id TEXT NOT NULL,
                source_reference TEXT,
                provision_reference TEXT,
                excerpt TEXT,
                source_snapshot_id TEXT,
                FOREIGN KEY (assessment_result_id) REFERENCES assessment_results(id)
            );
            CREATE TABLE IF NOT EXISTS simulations (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, changes_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, filename TEXT NOT NULL,
                mime_type TEXT NOT NULL, size_bytes INTEGER NOT NULL, storage_path TEXT NOT NULL,
                state TEXT NOT NULL, extracted_json TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
                detail TEXT NOT NULL, read INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS regulatory_updates (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, authority TEXT NOT NULL,
                jurisdiction TEXT NOT NULL, review_state TEXT NOT NULL, url TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
                status TEXT NOT NULL, priority TEXT NOT NULL, due_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS agent_sessions (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, goal TEXT NOT NULL,
                stage TEXT NOT NULL, memory_json TEXT NOT NULL, messages_json TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, assessment_id TEXT,
                report_type TEXT NOT NULL, status TEXT NOT NULL,
                storage_path TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_workspace_members_user ON workspace_members(user_id);
            CREATE INDEX IF NOT EXISTS idx_businesses_workspace ON businesses(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_profile_versions_business ON business_profile_versions(business_id);
            CREATE INDEX IF NOT EXISTS idx_assessments_workspace ON assessments(workspace_id);
            CREATE INDEX IF NOT EXISTS idx_assessment_results_assessment ON assessment_results(assessment_id);
            """
        )
        assessment_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(assessments)").fetchall()
        }
        if "business_id" not in assessment_columns:
            connection.execute("ALTER TABLE assessments ADD COLUMN business_id TEXT")
        regulatory_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(regulatory_updates)").fetchall()
        }
        if "url" not in regulatory_columns:
            connection.execute("ALTER TABLE regulatory_updates ADD COLUMN url TEXT")
        existing = connection.execute("SELECT id FROM workspaces WHERE id = ?", (LOCAL_WORKSPACE_ID,)).fetchone()
        if not existing:
            connection.execute(
                "INSERT INTO workspaces (id,name,jurisdiction) VALUES (?,?,?)",
                (LOCAL_WORKSPACE_ID, "My Workspace", "West Bengal, India"),
            )
        connection.execute(
            "INSERT OR IGNORE INTO workspace_members (workspace_id,user_id,role) VALUES (?,?,?)",
            (LOCAL_WORKSPACE_ID, LOCAL_USER_ID, "owner"),
        )


initialize_db()

app = FastAPI(
    title="PermitPilot API",
    version="1.0.0",
    docs_url=None if PRIVATE_DEMO_MODE else "/docs",
    redoc_url=None if PRIVATE_DEMO_MODE else "/redoc",
    openapi_url=None if PRIVATE_DEMO_MODE else "/openapi.json",
)
configured_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in configured_origins.split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def local_only_requests(request: Request, call_next):
    if request.url.path == "/healthz":
        return await call_next(request)

    if PRIVATE_DEMO_MODE:
        public_demo_paths = {
            "/api/v1/demo/session",
            "/api/v1/demo/login",
        }
        if request.url.path.startswith("/api/") and request.url.path not in public_demo_paths:
            token = request.cookies.get(DEMO_SESSION_COOKIE)
            if not verify_session_token(token, DEMO_SESSION_SECRET):
                return JSONResponse(status_code=401, content={"detail": "Demo access required"})
        return await call_next(request)

    client_host = request.client.host if request.client else ""
    try:
        is_loopback = ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        is_loopback = False
    host_header = (request.url.hostname or "").lower()
    origin = request.headers.get("origin")
    if not is_loopback or host_header not in {"localhost", "127.0.0.1", "::1"} or any(
        header in request.headers for header in ("forwarded", "x-forwarded-for", "x-real-ip")
    ) or (origin and origin not in [value.strip() for value in configured_origins.split(",")]):
        return JSONResponse(status_code=403, content={"detail": "PermitPilot is available only on this device"})
    return await call_next(request)


class DemoAccessRequest(BaseModel):
    code: str = Field(min_length=1, max_length=256)


@app.get("/healthz")
def deployment_health():
    return {"status": "ok"}


@app.get("/api/v1/demo/session")
def demo_session(request: Request):
    authenticated = not PRIVATE_DEMO_MODE or verify_session_token(
        request.cookies.get(DEMO_SESSION_COOKIE),
        DEMO_SESSION_SECRET,
    )
    return JSONResponse(
        {"authenticated": authenticated, "private_demo": PRIVATE_DEMO_MODE},
        headers={"Cache-Control": "no-store"},
    )


@app.post("/api/v1/demo/login")
def demo_login(payload: DemoAccessRequest):
    if not PRIVATE_DEMO_MODE:
        return {"authenticated": True, "private_demo": False}
    if not hmac.compare_digest(payload.code.encode("utf-8"), DEMO_ACCESS_CODE.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid demo access code")

    response = JSONResponse({"authenticated": True, "private_demo": True})
    response.set_cookie(
        key=DEMO_SESSION_COOKIE,
        value=create_session_token(DEMO_SESSION_SECRET),
        max_age=12 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/api/v1/demo/logout")
def demo_logout():
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(
        key=DEMO_SESSION_COOKIE,
        httponly=True,
        secure=PRIVATE_DEMO_MODE,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


class ProfileFacts(BaseModel):
    business_name: str
    business_type: str = "home_bakery"
    state: str = "West Bengal"
    city: str = "Kolkata"
    activities: list[str] = ["baking", "online_sales"]
    premises: str = "residential_kitchen"
    employee_count: int | None = None
    annual_turnover: int | None = None


class CandidateProfileFacts(BaseModel):
    business_name: str | None = None
    business_category: str | None = None
    business_type: str | None = None
    activities: list[str] = []
    products_services: list[str] = []
    country: str = "India"
    state: str = "West Bengal"
    city: str | None = None
    premises: str | None = None
    operating_model: str | None = None
    employee_count: int | None = None
    annual_turnover: int | None = None
    sales_channels: list[str] = []
    existing_registrations: list[str] = []
    missing_information: list[str] = []


class CreateBusinessRequest(BaseModel):
    workspace_id: str
    business_name: str
    business_type: str | None = None
    country: str = "India"
    state: str = "West Bengal"
    city: str | None = None
    original_description: str | None = None


class WorkspaceSettingsUpdate(BaseModel):
    name: str
    jurisdiction: str
    assessment_notifications: bool


class ConfirmProfileRequest(BaseModel):
    facts: dict
    original_description: str | None = None


class RequirementQuestionRequest(BaseModel):
    assessment_id: str
    rule_id: str
    question: str = Field(min_length=1, max_length=800)


class RequirementQuestionAnswer(BaseModel):
    answer: str = Field(min_length=1, max_length=2000)
    evidence_used: list[str] = Field(default_factory=list, max_length=8)
    missing_information: list[str] = Field(default_factory=list, max_length=12)
    confidence: Literal["high", "medium", "low"] | None = None


@app.get("/api/v1/health")
def health():
    return {
        "status": "ok",
        "mode": "private-demo" if PRIVATE_DEMO_MODE else "local",
        "database": "sqlite",
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY")),
        "submission_enabled": False,
        "source_scope": ["West Bengal", "Kolkata"],
    }


@app.get("/api/v1/workspaces")
def list_workspaces(user: dict | None = Depends(get_local_user)):
    with db() as connection:
        rows = connection.execute(
            """
            SELECT w.* 
            FROM workspaces w
            JOIN workspace_members wm ON wm.workspace_id = w.id
            WHERE wm.user_id = ?
            """,
            (user["id"],),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/v1/workspaces")
def create_workspace(name: str = "My Workspace", jurisdiction: str = "West Bengal, India", user: dict | None = Depends(get_local_user)):
    with db() as connection:
        existing = connection.execute(
            """
            SELECT w.* FROM workspaces w
            JOIN workspace_members wm ON wm.workspace_id = w.id
            WHERE wm.user_id = ? LIMIT 1
            """,
            (user["id"],),
        ).fetchone()
    if existing:
        return {"workspace_id": existing["id"], "name": existing["name"], "jurisdiction": existing["jurisdiction"], "role": "owner", "created": False}
    workspace_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute(
            "INSERT INTO workspaces (id,name,jurisdiction) VALUES (?,?,?)",
            (workspace_id, name, jurisdiction),
        )
        connection.execute(
            "INSERT INTO workspace_members (workspace_id,user_id,role) VALUES (?,?,?)",
            (workspace_id, user["id"], "owner"),
        )
    return {"workspace_id": workspace_id, "name": name, "jurisdiction": jurisdiction, "role": "owner"}


@app.post("/api/v1/businesses")
def create_business(payload: CreateBusinessRequest, user: dict | None = Depends(get_local_user)):
    authorize_workspace(payload.workspace_id, user)
    business_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute(
            "INSERT INTO businesses "
            "(id,workspace_id,business_name,business_type,country,state,city,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
            (
                business_id,
                payload.workspace_id,
                payload.business_name,
                payload.business_type,
                payload.country,
                payload.state,
                payload.city,
            ),
        )
    return {
        "business_id": business_id,
        "workspace_id": payload.workspace_id,
        "business_name": payload.business_name,
        "business_type": payload.business_type,
        "country": payload.country,
        "state": payload.state,
        "city": payload.city,
    }


@app.get("/api/v1/workspaces/{workspace_id}/businesses")
def list_businesses(workspace_id: str, user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    with db() as connection:
        rows = connection.execute(
            "SELECT * FROM businesses WHERE workspace_id=? ORDER BY created_at DESC",
            (workspace_id,),
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/api/v1/businesses/{business_id}")
def get_business(business_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        row = connection.execute(
            "SELECT * FROM businesses WHERE id=?",
            (business_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Business not found")
    authorize_workspace(row["workspace_id"], user)
    profile = None
    with db() as connection:
        profile_row = connection.execute(
            "SELECT * FROM business_profile_versions WHERE business_id=? ORDER BY version_number DESC LIMIT 1",
            (business_id,),
        ).fetchone()
    if profile_row:
        profile = {
            "id": profile_row["id"],
            "version_number": profile_row["version_number"],
            "structured_facts": json.loads(profile_row["structured_facts"]),
            "original_description": profile_row["original_description"],
            "confirmed_at": profile_row["confirmed_at"],
        }
    return {"business": dict(row), "profile": profile}


@app.get("/api/v1/businesses/{business_id}/profile-history")
def business_profile_history(business_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        business = connection.execute("SELECT workspace_id FROM businesses WHERE id=?", (business_id,)).fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    authorize_workspace(business["workspace_id"], user)
    with db() as connection:
        rows = connection.execute(
            "SELECT * FROM business_profile_versions WHERE business_id=? ORDER BY version_number DESC",
            (business_id,),
        ).fetchall()
    return {
        "items": [
            {
                "id": row["id"],
                "revision": row["version_number"],
                "facts": json.loads(row["structured_facts"]),
                "original_description": row["original_description"],
                "confirmed_by": row["confirmed_by"],
                "confirmed_at": row["confirmed_at"],
            }
            for row in rows
        ]
    }


@app.post("/api/v1/businesses/{business_id}/confirm-profile")
def confirm_profile(
    business_id: str,
    payload: ConfirmProfileRequest,
    user: dict | None = Depends(get_local_user),
):
    with db() as connection:
        business = connection.execute(
            "SELECT * FROM businesses WHERE id=?",
            (business_id,),
        ).fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    authorize_workspace(business["workspace_id"], user)

    facts = payload.facts
    facts["confirmed_by"] = user["id"]
    facts["confirmation_timestamp"] = date.today().isoformat()

    with db() as connection:
        connection.execute("BEGIN")
        try:
            previous = connection.execute(
                "SELECT MAX(version_number) FROM business_profile_versions WHERE business_id=?",
                (business_id,),
            ).fetchone()[0]
            version = (previous or 0) + 1
            profile_id = str(uuid.uuid4())
            confirmed_at = date.today().isoformat()
            connection.execute(
                "INSERT INTO business_profile_versions "
                "(id,business_id,version_number,structured_facts,original_description,confirmed_by,confirmed_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    profile_id,
                    business_id,
                    version,
                    json.dumps(facts),
                    payload.original_description,
                    user["id"],
                    confirmed_at,
                ),
            )
            connection.execute(
                "UPDATE businesses SET current_profile_version=?,business_name=?,business_type=?,country=?,state=?,city=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (
                    str(profile_id),
                    facts.get("business_name") or business["business_name"],
                    facts.get("business_type") or business["business_type"],
                    facts.get("country") or business["country"],
                    facts.get("state") or business["state"],
                    facts.get("city") or business["city"],
                    business_id,
                ),
            )
            evaluation = evaluate_profile(facts, date.today().isoformat())
            assessment_id = str(uuid.uuid4())
            connection.execute(
                "INSERT INTO assessments "
                "(id,workspace_id,business_id,profile_revision,status,results_json,created_at) "
                "VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                (
                    assessment_id,
                    business["workspace_id"],
                    business_id,
                    version,
                    "completed",
                    json.dumps(evaluation["results"]),
                ),
            )
            for result in evaluation["results"]:
                result_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO assessment_results "
                    "(id,assessment_id,rule_id,rule_version,status,matched_conditions,unmet_conditions,"
                    "missing_facts,exceptions_triggered,explanation_codes,verification_state) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        result_id,
                        assessment_id,
                        result["rule_id"],
                        result["rule_version"],
                        result["status"],
                        json.dumps(result.get("matched_conditions", [])),
                        json.dumps([]),
                        json.dumps(result.get("missing_facts", [])),
                        json.dumps([]),
                        json.dumps([result["rule_id"]]),
                        result["source_type"],
                    ),
                )
                connection.execute(
                    "INSERT INTO assessment_evidence "
                    "(id,assessment_result_id,source_reference,provision_reference,excerpt,source_snapshot_id) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        str(uuid.uuid4()),
                        result_id,
                        result.get("source"),
                        None,
                        None,
                        None,
                    ),
                )
                connection.execute(
                    "INSERT INTO assessment_evidence "
                    "(id,assessment_result_id,source_reference,provision_reference,excerpt,source_snapshot_id) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        str(uuid.uuid4()),
                        result_id,
                        result.get("source"),
                        None,
                        None,
                        None,
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    return {
        "business_id": business_id,
        "profile": {
            "id": profile_id,
            "version_number": version,
            "structured_facts": facts,
            "confirmed_at": confirmed_at,
        },
        "assessment": {
            "id": assessment_id,
            "status": "completed",
            "profile_revision": version,
            "engine_version": evaluation["engine_version"],
            "evaluation_date": evaluation["evaluation_date"],
            "results": evaluation["results"],
        },
    }


@app.post("/api/v1/businesses/{business_id}/extract-facts")
def extract_facts(business_id: str, description: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        business = connection.execute("SELECT workspace_id FROM businesses WHERE id=?", (business_id,)).fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    authorize_workspace(business["workspace_id"], user)
    text = description.lower()
    business_name = "My Business"
    name_match = None
    quoted = None
    import re
    quoted_match = re.search(r"(?:called|named)\s+[\"']([^\"']+)[\"']", text)
    if quoted_match:
        quoted = quoted_match.group(1).strip()
    elif "bakery" in text:
        quoted = "Bakery"
    elif "restaurant" in text or "cafe" in text:
        quoted = "Café"
    elif "shop" in text:
        quoted = "Retail Shop"
    if quoted:
        business_name = quoted.title()
    is_food = any(word in text for word in ("bakery", "food", "restaurant", "cafe", "café", "snack", "cake", "bread"))
    activities = []
    if "bread" in text or "cake" in text or "bakery" in text:
        activities.append("baking")
    if "online" in text or "delivery" in text:
        activities.append("online_sales")
    if not activities:
        activities = ["retail_or_service"]
    premises = "residential_kitchen" if any(word in text for word in ("home", "residential", "house")) else "commercial_premises"
    city = "Kolkata" if "kolkata" in text else "West Bengal"
    candidate = CandidateProfileFacts(
        business_name=business_name,
        business_type="home_bakery" if is_food and premises == "residential_kitchen" else ("food_business" if is_food else "small_business"),
        business_category="food" if is_food else "small_business",
        activities=activities,
        products_services=["baked goods"] if "bakery" in text or "baking" in text else [],
        country="India",
        state="West Bengal",
        city=city,
        premises=premises,
        operating_model="online_sales" if "online_sales" in activities else "local",
        employee_count=None,
        annual_turnover=None,
        sales_channels=["online"] if "online_sales" in activities else [],
        missing_information=["annual_turnover", "employee_count"],
    )
    provider = "deterministic-fallback"
    provider_error = None
    if os.getenv("GEMINI_API_KEY"):
        try:
            generated = GeminiProvider().generate_structured(
                prompt=f"Extract candidate business facts from this description. Return JSON only: {description}",
                system_prompt="Return a valid JSON object with keys business_name,business_category,business_type,activities,products_services,country,state,city,premises,operating_model,employee_count,annual_turnover,sales_channels,existing_registrations,missing_information. Do not infer missing facts.",
            )
            candidate = CandidateProfileFacts.model_validate(generated)
            provider = "gemini"
        except Exception as exc:
            provider_error = str(exc)
    facts = ProfileFacts(
        business_name=candidate.business_name or business_name,
        business_type=candidate.business_type or ("home_bakery" if is_food and premises == "residential_kitchen" else ("food_business" if is_food else "small_business")),
        city=candidate.city or city,
        activities=candidate.activities or activities,
        premises=candidate.premises or premises,
        employee_count=candidate.employee_count,
        annual_turnover=candidate.annual_turnover,
    )
    missing = []
    for field_name in ("annual_turnover", "employee_count", "business_name", "city", "premises"):
        if getattr(facts, field_name) is None:
            missing.append(field_name)
    return {
        "business_id": business_id,
        "facts": facts.model_dump(),
        "needs_confirmation": candidate.missing_information or missing,
        "provider": provider,
        "fallback_used": provider == "deterministic-fallback",
        "provider_error": provider_error,
        "disclaimer": "Extracted candidate facts require user review.",
    }


@app.post("/api/v1/assessments")
def create_assessment(
    business_id: str,
    profile_revision: int | None = None,
    user: dict | None = Depends(get_local_user),
):
    with db() as connection:
        business = connection.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    authorize_workspace(business["workspace_id"], user)
    with db() as connection:
        if profile_revision is None:
            profile_row = connection.execute(
                "SELECT * FROM business_profile_versions WHERE business_id=? ORDER BY version_number DESC LIMIT 1",
                (business_id,),
            ).fetchone()
        else:
            profile_row = connection.execute(
                "SELECT * FROM business_profile_versions WHERE business_id=? AND version_number=?",
                (business_id, profile_revision),
            ).fetchone()
    if not profile_row:
        raise HTTPException(status_code=409, detail="Business profile has not been confirmed")
    facts = json.loads(profile_row["structured_facts"])
    evaluation = evaluate_profile(facts, date.today().isoformat())
    results = evaluation["results"]
    actual_profile_version = profile_row["version_number"]
    assessment_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute("BEGIN")
        try:
            connection.execute(
                "INSERT INTO assessments (id,workspace_id,business_id,profile_revision,status,results_json) VALUES (?,?,?,?,?,?)",
                (
                    assessment_id,
                    business["workspace_id"],
                    business_id,
                    actual_profile_version,
                    "completed",
                    json.dumps(results),
                ),
            )
            for result in results:
                result_id = str(uuid.uuid4())
                connection.execute(
                    "INSERT INTO assessment_results "
                    "(id,assessment_id,rule_id,rule_version,status,matched_conditions,unmet_conditions,"
                    "missing_facts,exceptions_triggered,explanation_codes,verification_state) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        result_id,
                        assessment_id,
                        result["rule_id"],
                        result["rule_version"],
                        result["status"],
                        json.dumps(result.get("matched_conditions", [])),
                        json.dumps([]),
                        json.dumps(result.get("missing_facts", [])),
                        json.dumps([]),
                        json.dumps([result["rule_id"]]),
                        result["source_type"],
                    ),
                )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return {
        "assessment_id": assessment_id,
        "business_id": business_id,
        "profile_revision": actual_profile_version,
        "engine_version": evaluation["engine_version"],
        "evaluation_date": evaluation["evaluation_date"],
        "status": "completed",
        "results": results,
    }


@app.get("/api/v1/assessments/{assessment_id}")
def get_assessment(assessment_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        row = connection.execute("SELECT * FROM assessments WHERE id=?", (assessment_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Assessment not found")
    authorize_workspace(row["workspace_id"], user)
    return {
        "assessment_id": row["id"],
        "business_id": row["business_id"] if "business_id" in row.keys() else None,
        "workspace_id": row["workspace_id"],
        "profile_revision": row["profile_revision"],
        "engine_version": "rules-engine-local-1.0",
        "status": row["status"],
        "results": json.loads(row["results_json"]),
    }


@app.get("/api/v1/businesses/{business_id}/assessments")
def business_assessment_history(business_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        business = connection.execute("SELECT workspace_id FROM businesses WHERE id=?", (business_id,)).fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    authorize_workspace(business["workspace_id"], user)
    with db() as connection:
        rows = connection.execute(
            "SELECT * FROM assessments WHERE business_id=? ORDER BY created_at DESC",
            (business_id,),
        ).fetchall()
    return {
        "items": [
            {
                "id": row["id"],
                "profile_revision": row["profile_revision"],
                "status": row["status"],
                "engine_version": "rules-engine-local-1.0",
                "created_at": row["created_at"],
                "results": json.loads(row["results_json"]),
            }
            for row in rows
        ]
    }


@app.get("/api/v1/businesses/{business_id}/requirements")
def requirements(business_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        business = connection.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    authorize_workspace(business["workspace_id"], user)
    with db() as connection:
        row = connection.execute(
            "SELECT * FROM assessments WHERE business_id=? ORDER BY created_at DESC LIMIT 1",
            (business_id,),
        ).fetchone()
        profile = connection.execute(
            "SELECT version_number,structured_facts FROM business_profile_versions "
            "WHERE business_id=? ORDER BY version_number DESC LIMIT 1",
            (business_id,),
        ).fetchone()
    if row:
        return {
            "assessment_id": row["id"],
            "business_id": row["business_id"],
            "workspace_id": row["workspace_id"],
            "profile_revision": row["profile_revision"],
            "engine_version": "rules-engine-local-1.0",
            "status": row["status"],
            "results": json.loads(row["results_json"]),
        }
    if not profile:
        return {
            "business_id": business_id,
            "profile_confirmed": False,
            "results": [],
            "engine_version": "rules-engine-local-1.0",
        }
    evaluation = evaluate_profile(json.loads(profile["structured_facts"]), date.today().isoformat())
    return {
        "business_id": business_id,
        "profile_revision": profile["version_number"],
        "profile_confirmed": True,
        **evaluation,
    }


@app.get("/api/v1/businesses/{business_id}/dashboard")
def business_dashboard(business_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        business = connection.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    authorize_workspace(business["workspace_id"], user)
    with db() as connection:
        profile = connection.execute(
            "SELECT * FROM business_profile_versions WHERE business_id=? ORDER BY version_number DESC LIMIT 1",
            (business_id,),
        ).fetchone()
        assessment = connection.execute(
            "SELECT * FROM assessments WHERE business_id=? ORDER BY created_at DESC LIMIT 1",
            (business_id,),
        ).fetchone()
        tasks = connection.execute(
            "SELECT * FROM compliance_tasks WHERE workspace_id=?",
            (business["workspace_id"],),
        ).fetchall() if False else []
    if not assessment:
        return {
            "business": dict(business),
            "profile": {
                "id": profile["id"] if profile else None,
                "version_number": profile["version_number"] if profile else None,
                "structured_facts": json.loads(profile["structured_facts"]) if profile else None,
            } if profile else None,
            "assessment": None,
            "counts": {
                "applicable": 0,
                "not_applicable": 0,
                "conditional": 0,
                "unresolved": 0,
                "not_evaluated": 0,
            },
            "missing_facts": [],
            "outstanding_tasks": [],
        }
    results = json.loads(assessment["results_json"])
    counts = {status.lower(): sum(1 for item in results if item["status"] == status) for status in ("APPLICABLE","NOT_APPLICABLE","CONDITIONAL","UNRESOLVED","NOT_EVALUATED")}
    missing_facts = sorted({
        fact
        for item in results
        for fact in item.get("missing_facts", [])
    })
    return {
        "business": dict(business),
        "profile": {
            "id": profile["id"] if profile else None,
            "version_number": profile["version_number"] if profile else None,
            "structured_facts": json.loads(profile["structured_facts"]) if profile else None,
        } if profile else None,
        "assessment": {
            "id": assessment["id"],
            "profile_revision": assessment["profile_revision"],
            "status": assessment["status"],
            "created_at": assessment["created_at"],
            "engine_version": "rules-engine-local-1.0",
        },
        "counts": counts,
        "missing_facts": missing_facts,
        "outstanding_tasks": [],
    }


@app.get("/api/v1/assessments/{assessment_id}/requirements/{rule_id}")
def requirement_detail(
    assessment_id: str,
    rule_id: str,
    user: dict | None = Depends(get_local_user),
):
    with db() as connection:
        assessment = connection.execute("SELECT * FROM assessments WHERE id=?", (assessment_id,)).fetchone()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    authorize_workspace(assessment["workspace_id"], user)
    results = json.loads(assessment["results_json"])
    selected = next((item for item in results if item["rule_id"] == rule_id), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Requirement not found in assessment")
    with db() as connection:
        profile_row = connection.execute(
            "SELECT structured_facts FROM business_profile_versions WHERE business_id=? AND version_number=?",
            (assessment["business_id"], assessment["profile_revision"]),
        ).fetchone() if "business_id" in assessment.keys() and assessment["business_id"] else None
    facts = json.loads(profile_row["structured_facts"]) if profile_row else {}
    return {
        "assessment_id": assessment_id,
        "profile_revision": assessment["profile_revision"],
        "rule": selected,
        "confirmed_business_facts": facts,
        "evidence": [
            {
                "source_reference": selected.get("source"),
                "authority": selected.get("authority"),
                "verification_state": selected.get("source_type"),
                "provision_reference": None,
            }
        ],
    }


@app.post("/api/v1/requirements/question")
def requirement_question(
    payload: RequirementQuestionRequest,
    user: dict | None = Depends(get_local_user),
):
    with db() as connection:
        assessment = connection.execute("SELECT * FROM assessments WHERE id=?", (payload.assessment_id,)).fetchone()
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    authorize_workspace(assessment["workspace_id"], user)
    results = json.loads(assessment["results_json"])
    selected = next((item for item in results if item["rule_id"] == payload.rule_id), None)
    if not selected:
        raise HTTPException(status_code=404, detail="Requirement not found")
    profile_facts = {}
    if "business_id" in assessment.keys() and assessment["business_id"]:
        with db() as connection:
            profile_row = connection.execute(
                "SELECT structured_facts FROM business_profile_versions "
                "WHERE business_id=? AND version_number=?",
                (assessment["business_id"], assessment["profile_revision"]),
            ).fetchone()
        if profile_row:
            profile_facts = json.loads(profile_row["structured_facts"])
    evidence_context = {
        "status": selected["status"],
        "rule": selected,
        "confirmed_facts": profile_facts,
        "missing_facts": selected.get("missing_facts", []),
        "source": selected.get("source"),
    }

    def evidence_only_response(provider_error: Literal["gemini_not_configured", "gemini_request_failed"]) -> dict:
        title = str(selected.get("title") or selected.get("rule_id") or "This requirement")
        status = str(selected.get("status") or "UNRESOLVED")
        authority = str(selected.get("authority") or "the relevant authority")
        source_type = str(selected.get("source_type") or "unverified")
        source = str(selected.get("source") or "No source excerpt is stored.")
        matched_conditions = selected.get("matched_conditions") or []
        missing_facts = selected.get("missing_facts") or []
        evidence_used = [f"Saved candidate result: {title} — {status}."]
        if matched_conditions:
            evidence_used.append(f"Matched conditions: {', '.join(map(str, matched_conditions))}.")
        evidence_used.append(f"Source status: {source_type}; {source}")
        if missing_facts:
            evidence_used.append(f"Missing facts: {', '.join(map(str, missing_facts))}.")
        answer = (
            "Gemini is unavailable, so this is a summary of the saved assessment—not a legal conclusion. "
            f"The saved candidate assessment records “{title}” as {status}. "
            + (
                f"It lists these matched conditions: {', '.join(map(str, matched_conditions))}. "
                if matched_conditions
                else ""
            )
            + (
                f"It lists these missing facts: {', '.join(map(str, missing_facts))}. "
                if missing_facts
                else "It lists no missing facts. "
            )
            + f"The source is marked {source_type} and names {authority}. "
            + "Verify the current requirement with the authority before acting."
        )
        return {
            "answer": answer,
            "provider": "evidence_fallback",
            "provider_error": provider_error,
            "evidence_used": evidence_used,
            "missing_information": list(map(str, missing_facts)),
            "confidence": "low",
        }

    if not os.getenv("GEMINI_API_KEY"):
        return evidence_only_response("gemini_not_configured")

    try:
        response = GeminiProvider().generate_structured(
            prompt=(
                "Answer the user's question using only this evidence context. "
                "Do not determine legal applicability or invent sources. "
                "Return evidence_used and missing_information as short lists of strings, "
                "and confidence as high, medium, or low.\n"
                f"Question: {payload.question}\n"
                f"Context: {json.dumps(evidence_context)}"
            ),
            system_prompt=(
                "You explain an already-computed compliance result. "
                "Return JSON only with keys answer, evidence_used, missing_information, confidence. "
                "Use only the supplied confirmed facts and source context. Treat candidate rules and "
                "unverified sources as unconfirmed; never state that a legal requirement is verified."
            ),
        )
        validated = RequirementQuestionAnswer.model_validate(response)
        return {"provider": "gemini", **validated.model_dump()}
    except (httpx.HTTPError, RuntimeError, KeyError, IndexError, TypeError, ValueError) as exc:
        logger.warning("Assessment question used evidence fallback after Gemini failure (%s)", type(exc).__name__)
        return evidence_only_response("gemini_request_failed")
@app.post("/api/v1/simulations")
def simulation(
    business_id: str | None = None,
    workspace_id: str | None = None,
    employee_count: int | None = None,
    sell_online: bool = True,
    user: dict | None = Depends(get_local_user),
):
    if business_id:
        with db() as connection:
            business = connection.execute("SELECT * FROM businesses WHERE id=?", (business_id,)).fetchone()
        if not business:
            raise HTTPException(status_code=404, detail="Business not found")
        workspace_id = business["workspace_id"]
    if not workspace_id:
        raise HTTPException(status_code=400, detail="business_id or workspace_id is required")
    authorize_workspace(workspace_id, user)
    with db() as connection:
        if business_id:
            row = connection.execute(
                "SELECT structured_facts FROM business_profile_versions WHERE business_id=? ORDER BY version_number DESC LIMIT 1",
                (business_id,),
            ).fetchone()
        else:
            row = None
    baseline = json.loads(row["structured_facts"]) if row else {
        "business_name": "Unconfirmed business",
        "business_type": None,
        "activities": [],
        "premises": None,
        "annual_turnover": None,
        "employee_count": None,
    }
    scenario = dict(baseline)
    scenario["employee_count"] = employee_count
    activities = list(scenario.get("activities") or [])
    if sell_online and "online_sales" not in activities:
        activities.append("online_sales")
    elif not sell_online:
        activities = [activity for activity in activities if activity != "online_sales"]
    scenario["activities"] = activities
    baseline_evaluation = evaluate_profile(baseline, date.today().isoformat())
    scenario_evaluation = evaluate_profile(scenario, date.today().isoformat())
    baseline_ids = {item["rule_id"]: item["status"] for item in baseline_evaluation["results"]}
    scenario_ids = {item["rule_id"]: item["status"] for item in scenario_evaluation["results"]}
    changes = []
    for rule_id in sorted(set(baseline_ids) | set(scenario_ids)):
        before = baseline_ids.get(rule_id)
        after = scenario_ids.get(rule_id)
        if before is None:
            changes.append({"type": "ADDED", "rule_id": rule_id, "after": after})
        elif after is None:
            changes.append({"type": "REMOVED", "rule_id": rule_id, "before": before})
        elif before != after:
            changes.append({"type": "CHANGED", "rule_id": rule_id, "before": before, "after": after})
    baseline_count = len(baseline_evaluation["results"])
    count = len(scenario_evaluation["results"])
    simulation_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute("INSERT INTO simulations (id,workspace_id,changes_json) VALUES (?,?,?)", (simulation_id, workspace_id, json.dumps({"employee_count": employee_count, "sell_online": sell_online, "changes": changes, "count": count})))
    return {
        "simulation_id": simulation_id,
        "baseline_requirements": baseline_count,
        "scenario_requirements": count,
        "changes": changes,
        "verification_state": "CANDIDATE",
        "disclaimer": "Scenario results are candidate checks, not verified legal requirements.",
    }


@app.post("/api/v1/documents/upload")
async def upload_document(workspace_id: str = LOCAL_WORKSPACE_ID, file: UploadFile = File(...), user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    if file.size is not None and file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")
    allowed = {"application/pdf", "image/png", "image/jpeg"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=415, detail="Only PDF, PNG and JPG files are supported")
    document_id = str(uuid.uuid4())
    storage_path = UPLOAD_DIR / f"{document_id}-{file.filename}"
    content = await file.read()
    storage_path.write_bytes(content)
    extracted = {
        "needs_user_review": True,
        "document_type": "address_or_identity_evidence" if any(word in file.filename.lower() for word in ("address", "aadhaar", "proof", "id")) else "application_support",
        "fields": [
            {"name": "document_name", "value": file.filename, "confidence": 1.0},
            {"name": "file_type", "value": file.content_type, "confidence": 1.0},
        ],
    }
    with db() as connection:
        connection.execute(
            "INSERT INTO documents (id,workspace_id,filename,mime_type,size_bytes,storage_path,state,extracted_json) VALUES (?,?,?,?,?,?,?,?)",
            (document_id, workspace_id, file.filename, file.content_type, len(content), str(storage_path), "review_ready", json.dumps(extracted)),
        )
    return {"document_id": document_id, "filename": file.filename, "size_bytes": len(content), "processing_state": "review_ready", "review_state": "needs_review"}


@app.get("/api/v1/documents")
def list_documents(workspace_id: str = LOCAL_WORKSPACE_ID, user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    with db() as connection:
        rows = connection.execute("SELECT * FROM documents WHERE workspace_id=? ORDER BY created_at DESC", (workspace_id,)).fetchall()
    return {"items": [{"id": r["id"], "filename": r["filename"], "mime_type": r["mime_type"], "size_bytes": r["size_bytes"], "processing_state": r["state"], "review_state": "needs_review", "created_at": r["created_at"]} for r in rows]}


@app.post("/api/v1/documents/{document_id}/review")
def review_document(document_id: str, extracted_fields: dict, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        row = connection.execute("SELECT id,workspace_id FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        authorize_workspace(row["workspace_id"], user)
        connection.execute("UPDATE documents SET state='completed',extracted_json=? WHERE id=?", (json.dumps(extracted_fields), document_id))
    return {"document_id": document_id, "processing_state": "completed", "review_state": "reviewed"}


@app.post("/api/v1/documents/{document_id}/process")
def process_document(document_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        row = connection.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        authorize_workspace(row["workspace_id"], user)
        connection.execute("UPDATE documents SET state='review_ready' WHERE id=?", (document_id,))
    return {"document_id": document_id, "processing_state": "review_ready", "review_state": "needs_review", "extracted": json.loads(row["extracted_json"])}


@app.post("/api/v1/reports")
def create_report(
    workspace_id: str = LOCAL_WORKSPACE_ID,
    business_id: str | None = None,
    user: dict | None = Depends(get_local_user),
):
    authorize_workspace(workspace_id, user)
    if not business_id:
        with db() as connection:
            latest_business = connection.execute(
                "SELECT id FROM businesses WHERE workspace_id=? ORDER BY updated_at DESC,created_at DESC LIMIT 1",
                (workspace_id,),
            ).fetchone()
        business_id = latest_business["id"] if latest_business else None
    report_id = str(uuid.uuid4())
    with db() as connection:
        if business_id:
            business = connection.execute(
                "SELECT id FROM businesses WHERE id=? AND workspace_id=?",
                (business_id, workspace_id),
            ).fetchone()
            if not business:
                raise HTTPException(status_code=404, detail="Business not found in this workspace")
            assessment = connection.execute(
                "SELECT id,business_id,profile_revision,results_json FROM assessments "
                "WHERE workspace_id=? AND business_id=? ORDER BY created_at DESC LIMIT 1",
                (workspace_id, business_id),
            ).fetchone()
            if not assessment:
                raise HTTPException(status_code=409, detail="Confirm the business profile and run an assessment before creating a report")
            profile = connection.execute(
                "SELECT structured_facts FROM business_profile_versions "
                "WHERE business_id=? AND version_number=?",
                (business_id, assessment["profile_revision"]),
            ).fetchone()
            if not profile:
                raise HTTPException(status_code=409, detail="The assessment's confirmed profile revision is unavailable")
            profile_facts = json.loads(profile["structured_facts"])
        else:
            profile = connection.execute(
                "SELECT facts_json FROM profiles WHERE workspace_id=? ORDER BY revision DESC LIMIT 1",
                (workspace_id,),
            ).fetchone()
            assessment = connection.execute(
                "SELECT id,business_id,results_json FROM assessments WHERE workspace_id=? ORDER BY created_at DESC LIMIT 1",
                (workspace_id,),
            ).fetchone()
            if not assessment:
                raise HTTPException(status_code=409, detail="Run an assessment before creating a report")
            profile_facts = json.loads(profile["facts_json"]) if profile else {"business_name": "My Business"}
        assessment_id = assessment["id"]
        connection.execute(
            "INSERT INTO reports (id,workspace_id,assessment_id,report_type,status) VALUES (?,?,?,?,?)",
            (report_id, workspace_id, assessment_id, "assessment_summary", "ready"),
        )
    results = json.loads(assessment["results_json"])
    return {
        "report_id": report_id,
        "assessment_id": assessment_id,
        "business_id": business_id or assessment["business_id"],
        "workspace_id": workspace_id,
        "status": "ready",
        "profile": profile_facts,
        "results": results,
        "disclaimer": "Candidate data — verify against current official sources.",
    }


@app.get("/api/v1/reports/{report_id}/print", response_class=HTMLResponse)
def print_report(report_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        report = connection.execute("SELECT workspace_id,assessment_id FROM reports WHERE id=?", (report_id,)).fetchone()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    authorize_workspace(report["workspace_id"], user)
    with db() as connection:
        assessment = connection.execute("SELECT results_json FROM assessments WHERE id=?", (report["assessment_id"],)).fetchone() if report["assessment_id"] else None
    results = json.loads(assessment["results_json"]) if assessment else []
    result_rows = "".join(f"<tr><td>{r['title']}</td><td>{r['status']}</td><td>{r['authority']}</td></tr>" for r in results)
    return f"""<!doctype html><html><head><title>PermitPilot report</title><style>body{{font-family:Arial;max-width:800px;margin:40px auto}}table{{width:100%;border-collapse:collapse}}td,th{{border:1px solid #222;padding:10px}}.notice{{margin-top:30px;border:2px solid #222;padding:12px}}</style></head><body><h1>PermitPilot Assessment Report</h1><p>Report {report_id} · Candidate source data</p><table><thead><tr><th>Requirement</th><th>Status</th><th>Authority</th></tr></thead><tbody>{result_rows}</tbody></table><div class="notice">CANDIDATE DATA — Verify all requirements against current official sources before action. This document is not legal advice.</div></body></html>"""


@app.get("/api/v1/reports")
def list_reports(workspace_id: str = LOCAL_WORKSPACE_ID, user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    with db() as connection:
        rows = connection.execute("SELECT * FROM reports WHERE workspace_id=? ORDER BY created_at DESC", (workspace_id,)).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.get("/api/v1/reports/{report_id}")
def get_report(report_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        row = connection.execute("SELECT * FROM reports WHERE id=?", (report_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    authorize_workspace(row["workspace_id"], user)
    return dict(row)


@app.get("/api/v1/reports/{report_id}/download")
def download_report(report_id: str, user: dict | None = Depends(get_local_user)):
    pdf_path = UPLOAD_DIR / f"{report_id}-assessment.pdf"
    with db() as connection:
        report = connection.execute("SELECT workspace_id,assessment_id FROM reports WHERE id=?", (report_id,)).fetchone()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    authorize_workspace(report["workspace_id"], user)
    with db() as connection:
        assessment = None
        if report and report["assessment_id"]:
            assessment = connection.execute(
                "SELECT results_json,business_id,profile_revision FROM assessments WHERE id=?",
                (report["assessment_id"],),
            ).fetchone()
        profile = None
        if assessment and assessment["business_id"]:
            profile = connection.execute(
                "SELECT structured_facts FROM business_profile_versions WHERE business_id=? AND version_number=?",
                (assessment["business_id"], assessment["profile_revision"]),
            ).fetchone()
    if not assessment:
        raise HTTPException(status_code=409, detail="The report's assessment is no longer available")
    results = json.loads(assessment["results_json"])
    profile_facts = json.loads(profile["structured_facts"]) if profile else {}
    pdf = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    pdf.setTitle("PermitPilot Assessment Report")

    y = height - 55

    def write_report_line(value: str, bold: bool = False, size: int = 9):
        nonlocal y
        text = str(value)
        if any(ord(character) > 126 for character in text):
            text = json.dumps(text, ensure_ascii=True)
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        for line in textwrap.wrap(text, width=92) or [""]:
            if y < 85:
                pdf.showPage()
                y = height - 55
                pdf.setFont("Helvetica", 9)
            pdf.drawString(50, y, line)
            y -= size + 5

    write_report_line("PermitPilot Assessment Report", bold=True, size=17)
    write_report_line(f"Report ID: {report_id}")
    write_report_line(f"Business: {profile_facts.get('business_name') or 'Business profile'}")
    write_report_line(f"Jurisdiction: {profile_facts.get('city') or ''}, {profile_facts.get('state') or 'West Bengal'}")
    write_report_line(f"Generated: {date.today().isoformat()}")
    y -= 10
    for rule in results:
        write_report_line(rule.get("title") or rule.get("rule_id") or "Requirement", bold=True, size=11)
        write_report_line(f"Status: {rule.get('status', 'UNRESOLVED')} | Authority: {rule.get('authority', 'Not confirmed')}")
        if rule.get("disclaimer"):
            write_report_line(rule["disclaimer"])
        y -= 8
    y -= 5
    write_report_line("Candidate data - verify against current official sources before action.", bold=True)
    write_report_line("This document is not legal advice.")
    pdf.save()
    return FileResponse(pdf_path, media_type="application/pdf", filename="permitpilot-assessment.pdf")


@app.get("/api/v1/businesses/{business_id}/dependency-graph")
def dependency_graph(business_id: str, user: dict | None = Depends(get_local_user)):
    authorize_workspace(business_id, user)
    with db() as connection:
        row = connection.execute("SELECT facts_json FROM profiles WHERE workspace_id=? ORDER BY revision DESC LIMIT 1", (business_id,)).fetchone()
    facts = json.loads(row["facts_json"]) if row else None
    nodes = [{"id": "profile", "type": "business_fact", "label": facts["business_name"] if facts else "Business profile"}]
    edges = []
    if facts:
        activities = facts.get("activities") or []
        is_food = "baking" in activities or facts.get("business_type") in ("home_bakery", "food_business")
        if is_food:
            nodes.append({"id": "fssai", "type": "requirement", "label": "FSSAI registration"})
            edges.append({"from": "profile", "to": "fssai", "type": "triggered_by"})
        nodes.append({"id": "shop", "type": "requirement", "label": "Establishment registration"})
        edges.append({"from": "profile", "to": "shop", "type": "triggered_by"})
        nodes.append({"id": "address", "type": "evidence", "label": "Premises evidence"})
        edges.append({"from": "address", "to": "shop", "type": "evidence_for"})
    return {"business_id": business_id, "nodes": nodes, "edges": edges}


@app.get("/api/v1/notifications")
def notifications(workspace_id: str = LOCAL_WORKSPACE_ID, user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    with db() as connection:
        rows = connection.execute("SELECT * FROM notifications WHERE workspace_id=? ORDER BY created_at DESC", (workspace_id,)).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.post("/api/v1/notifications/{notification_id}/read")
def read_notification(notification_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        row = connection.execute("SELECT workspace_id FROM notifications WHERE id=?", (notification_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found")
        authorize_workspace(row["workspace_id"], user)
        connection.execute("UPDATE notifications SET read=1 WHERE id=?", (notification_id,))
    return {"id": notification_id, "read": True}


@app.get("/api/v1/tasks")
def list_tasks(workspace_id: str = LOCAL_WORKSPACE_ID, user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    with db() as connection:
        rows = connection.execute("SELECT * FROM tasks WHERE workspace_id=? ORDER BY created_at", (workspace_id,)).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.patch("/api/v1/tasks/{task_id}")
def update_task(task_id: str, status: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        row = connection.execute("SELECT workspace_id FROM tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Task not found")
        authorize_workspace(row["workspace_id"], user)
        connection.execute("UPDATE tasks SET status=? WHERE id=?", (status, task_id))
    return {"id": task_id, "status": status}


@app.post("/api/v1/tasks")
def create_task(workspace_id: str, title: str, priority: str = "medium", due_date: str | None = None, user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    task_id = str(uuid.uuid4())
    with db() as connection:
        connection.execute(
            "INSERT INTO tasks (id,workspace_id,title,status,priority,due_date) VALUES (?,?,?,?,?,?)",
            (task_id, workspace_id, title, "open", priority, due_date),
        )
    return {"id": task_id, "workspace_id": workspace_id, "title": title, "status": "open", "priority": priority, "due_date": due_date}


@app.patch("/api/v1/workspaces/{workspace_id}")
def update_workspace(workspace_id: str, name: str, jurisdiction: str = "West Bengal, India", user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    with db() as connection:
        row = connection.execute("SELECT id FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
        if row:
            connection.execute("UPDATE workspaces SET name=?,jurisdiction=? WHERE id=?", (name, jurisdiction, workspace_id))
        else:
            connection.execute("INSERT INTO workspaces (id,name,jurisdiction) VALUES (?,?,?)", (workspace_id, name, jurisdiction))
    return {"workspace_id": workspace_id, "name": name, "jurisdiction": jurisdiction}


@app.get("/api/v1/workspaces/{workspace_id}/settings")
def get_workspace_settings(workspace_id: str, user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    with db() as connection:
        workspace = connection.execute(
            "SELECT name,jurisdiction FROM workspaces WHERE id=?",
            (workspace_id,),
        ).fetchone()
        settings = connection.execute(
            "SELECT assessment_notifications FROM workspace_settings WHERE workspace_id=?",
            (workspace_id,),
        ).fetchone()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {
        "workspace_id": workspace_id,
        "name": workspace["name"],
        "jurisdiction": workspace["jurisdiction"],
        "assessment_notifications": bool(settings["assessment_notifications"]) if settings else True,
    }


@app.patch("/api/v1/workspaces/{workspace_id}/settings")
def update_workspace_settings(
    workspace_id: str,
    payload: WorkspaceSettingsUpdate,
    user: dict | None = Depends(get_local_user),
):
    authorize_workspace(workspace_id, user)
    name = payload.name.strip()
    jurisdiction = payload.jurisdiction.strip()
    if not name or not jurisdiction:
        raise HTTPException(status_code=400, detail="Workspace name and jurisdiction are required")
    with db() as connection:
        connection.execute(
            "UPDATE workspaces SET name=?,jurisdiction=? WHERE id=?",
            (name, jurisdiction, workspace_id),
        )
        connection.execute(
            "INSERT INTO workspace_settings (workspace_id,assessment_notifications,updated_at) "
            "VALUES (?,?,CURRENT_TIMESTAMP) "
            "ON CONFLICT(workspace_id) DO UPDATE SET "
            "assessment_notifications=excluded.assessment_notifications,updated_at=CURRENT_TIMESTAMP",
            (workspace_id, int(payload.assessment_notifications)),
        )
    return {
        "workspace_id": workspace_id,
        "name": name,
        "jurisdiction": jurisdiction,
        "assessment_notifications": payload.assessment_notifications,
    }


@app.get("/api/v1/workspaces/{workspace_id}/export")
def export_workspace_data(workspace_id: str, user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)

    def rows_as_dicts(query: str, parameters: tuple = ()) -> list[dict]:
        with db() as connection:
            return [dict(row) for row in connection.execute(query, parameters).fetchall()]

    workspace = rows_as_dicts("SELECT * FROM workspaces WHERE id=?", (workspace_id,))
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    data = {
        "format": "permitpilot-workspace-export-v1",
        "workspace": workspace[0],
        "businesses": rows_as_dicts("SELECT * FROM businesses WHERE workspace_id=?", (workspace_id,)),
        "business_profile_versions": rows_as_dicts(
            "SELECT bpv.* FROM business_profile_versions bpv "
            "JOIN businesses b ON b.id=bpv.business_id WHERE b.workspace_id=?",
            (workspace_id,),
        ),
        "profiles": rows_as_dicts("SELECT * FROM profiles WHERE workspace_id=?", (workspace_id,)),
        "assessments": rows_as_dicts("SELECT * FROM assessments WHERE workspace_id=?", (workspace_id,)),
        "assessment_results": rows_as_dicts(
            "SELECT ar.* FROM assessment_results ar JOIN assessments a ON a.id=ar.assessment_id "
            "WHERE a.workspace_id=?",
            (workspace_id,),
        ),
        "assessment_evidence": rows_as_dicts(
            "SELECT ae.* FROM assessment_evidence ae "
            "JOIN assessment_results ar ON ar.id=ae.assessment_result_id "
            "JOIN assessments a ON a.id=ar.assessment_id WHERE a.workspace_id=?",
            (workspace_id,),
        ),
        "tasks": rows_as_dicts("SELECT * FROM tasks WHERE workspace_id=?", (workspace_id,)),
        "documents": rows_as_dicts(
            "SELECT id,workspace_id,filename,mime_type,size_bytes,state,extracted_json,created_at "
            "FROM documents WHERE workspace_id=?",
            (workspace_id,),
        ),
        "notifications": rows_as_dicts("SELECT * FROM notifications WHERE workspace_id=?", (workspace_id,)),
        "simulations": rows_as_dicts("SELECT * FROM simulations WHERE workspace_id=?", (workspace_id,)),
        "reports": rows_as_dicts("SELECT * FROM reports WHERE workspace_id=?", (workspace_id,)),
        "agent_sessions": rows_as_dicts(
            "SELECT id,workspace_id,goal,stage,memory_json,messages_json,status,created_at,updated_at "
            "FROM agent_sessions WHERE workspace_id=?",
            (workspace_id,),
        ),
    }
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": 'attachment; filename="permitpilot-workspace-export.json"'},
    )


def get_local_business_facts() -> dict | None:
    with db() as connection:
        row = connection.execute(
            "SELECT bpv.structured_facts FROM businesses b "
            "JOIN business_profile_versions bpv ON bpv.business_id=b.id "
            "WHERE b.workspace_id=? ORDER BY bpv.version_number DESC LIMIT 1",
            (LOCAL_WORKSPACE_ID,),
        ).fetchone()
    return json.loads(row["structured_facts"]) if row else None


def is_food_profile(facts: dict | None) -> bool:
    if not facts:
        return False
    activities = [str(activity).lower() for activity in facts.get("activities") or []]
    return any(re.search(r"\b(food|baking|cooking|catering|restaurant|bakery)\b", activity) for activity in activities) or bool(
        re.search(r"\b(food|bakery)\b", str(facts.get("business_type") or ""), re.I)
    )


@app.get("/api/v1/regulatory/updates")
def regulatory_updates(user: dict | None = Depends(get_local_user)):
    with db() as connection:
        rows = connection.execute("SELECT * FROM regulatory_updates ORDER BY created_at DESC").fetchall()
    is_food = is_food_profile(get_local_business_facts())
    rows = [
        row for row in rows
        if row["id"] != "update-demo-001"
        and (is_food or row["authority"].lower() != "fssai")
    ]
    return {"updates": [dict(row) for row in rows]}


@app.post("/api/v1/regulatory/scans")
def scan_regulatory_sources(user: dict | None = Depends(get_local_user)):
    source_targets = list(AGENT_SOURCE_TARGETS["common"])
    if is_food_profile(get_local_business_facts()):
        source_targets = AGENT_SOURCE_TARGETS["food"] + source_targets
    scan_sources = [(authority, url, "IN-WB") for authority, url, _ in source_targets]
    captured = []
    for authority, url, jurisdiction in scan_sources:
        try:
            source = capture_source(url)
            captured.append({
                "authority": authority,
                "title": source["title"],
                "url": source["canonical_url"],
                "captured": True,
                "content_hash": source["content_hash"],
            })
            with db() as connection:
                connection.execute(
                    "INSERT OR IGNORE INTO regulatory_updates (id,title,authority,jurisdiction,review_state,url) VALUES (?,?,?,?,?,?)",
                    (f"scan-{source['content_hash'][:12]}", source["title"], authority, jurisdiction, "candidate", source["canonical_url"]),
                )
                connection.execute(
                    "UPDATE regulatory_updates SET url=? WHERE id=? AND (url IS NULL OR url='')",
                    (source["canonical_url"], f"scan-{source['content_hash'][:12]}"),
                )
        except Exception as exc:
            captured.append({
                "authority": authority,
                "title": url,
                "url": url,
                "captured": False,
                "capture_error": str(exc),
            })
    return {"captured": captured, "captured_count": sum(1 for item in captured if item["captured"]), "failed_count": sum(1 for item in captured if not item["captured"])}


@app.post("/api/v1/regulatory/updates/{update_id}/review")
def review_update(update_id: str, decision: str = "needs_revision", user: dict | None = Depends(get_local_user)):
    require_reviewer(user)
    if decision not in {"approved", "rejected", "needs_revision"}:
        raise HTTPException(status_code=400, detail="Invalid review decision")
    with db() as connection:
        row = connection.execute("SELECT id FROM regulatory_updates WHERE id=?", (update_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Update not found")
        connection.execute("UPDATE regulatory_updates SET review_state=? WHERE id=?", (decision, update_id))
    return {"update_id": update_id, "decision": decision, "state": "review_recorded"}


class AgentMessage(BaseModel):
    message: str


class OfficialFormFillRequest(BaseModel):
    fields: dict[str, str]


AGENT_SOURCE_TARGETS = {
    "common": [
        ("West Bengal Urban Development", "https://udma.wb.gov.in/", "State urban and municipal services"),
        ("West Bengal Shops & Establishments", "https://wbshopsonline.gov.in/", "Labour and establishment portal"),
        ("GST Department", "https://www.gst.gov.in/", "Goods and Services Tax portal"),
    ],
    "food": [
        ("FSSAI FoSCoS", "https://foscos.fssai.gov.in/", "Food business registration portal"),
        ("FSSAI", "https://www.fssai.gov.in/", "Food safety information"),
    ],
}


def infer_agent_facts(goal: str) -> dict:
    lowered = goal.lower()
    activity = None
    industry = "general"
    activity_patterns = [
        ("food", r"\b(bakery|baker|restaurant|cafe|café|food|catering|snack|grocery)\b", "Food preparation or sale"),
        ("retail", r"\b(shop|store|retail|hardware|clothing|boutique)\b", "Retail sale of goods"),
        ("personal_services", r"\b(salon|barber|beauty|spa)\b", "Personal care services"),
        ("health", r"\b(clinic|medical|healthcare|dentist|pharmacy)\b", "Health-related services"),
        ("professional_services", r"\b(consult|accounting|software|it services|agency)\b", "Professional services"),
        ("manufacturing", r"\b(manufactur|factory|production|workshop)\b", "Manufacturing or production"),
    ]
    for candidate_industry, pattern, label in activity_patterns:
        if re.search(pattern, lowered):
            industry = candidate_industry
            activity = label
            break

    named_match = re.search(
        r"\b(?:called|named)\s+[\"']([^\"']+)[\"']",
        goal,
        re.IGNORECASE,
    )
    location_match = re.search(r"\bin\s+([^,.!?]+)", goal, re.IGNORECASE)
    location = location_match.group(1).strip() if location_match else None
    if location and location.lower() in {"my town", "my city", "my area", "my village"}:
        location = None
    premises = None
    if re.search(r"\b(home|house|residential)\b", lowered):
        premises = "residential"
    elif re.search(r"\b(shared|co-working)\b", lowered):
        premises = "shared"
    elif re.search(r"\b(shopfront|commercial|office|storefront)\b", lowered):
        premises = "commercial"

    inferred_fields = []
    if named_match:
        inferred_fields.append("business_name")
    if activity:
        inferred_fields.append("activity")
    if location:
        inferred_fields.append("location")
    if premises:
        inferred_fields.append("premises")
    return {
        "goal": goal.strip(),
        "jurisdiction": "West Bengal, India",
        "industry": industry,
        "business_type": industry,
        "business_name": named_match.group(1).strip() if named_match else None,
        "activity": activity,
        "location": location,
        "premises": premises,
        "annual_turnover": None,
        "employee_count": None,
        "owner_name": None,
        "address": None,
        "_skipped": [],
        "_inferred_fields": inferred_fields,
    }


def source_highlights(text: str) -> list[str]:
    candidates = re.split(r"(?<=[.!?])\s+", text)
    relevant = re.compile(
        r"\b(registr|application|licen[cs]e|permit|form|certificate|fee|submit|document|renew|municipal)\w*\b",
        re.I,
    )
    highlights = []
    for candidate in candidates:
        snippet = candidate.strip()
        if snippet and relevant.search(snippet) and snippet not in highlights:
            highlights.append(snippet[:500])
        if len(highlights) == 5:
            break
    return highlights


def summarize_public_sources(sources: list[dict]) -> dict:
    captured_sources = [source for source in sources if source["captured"]][:4]
    if not captured_sources:
        return {"status": "no_sources", "summaries": []}
    if not os.getenv("GEMINI_API_KEY"):
        return {"status": "not_configured", "summaries": []}

    public_pages = [
        {"url": source["url"], "title": source["title"], "text": source["excerpt"][:800]}
        for source in captured_sources
    ]
    try:
        result = GeminiProvider().generate_structured(
            prompt=json.dumps({"public_pages": public_pages}, ensure_ascii=False),
            system_prompt=(
                "Summarize only explicit administrative procedures stated in the supplied public page text. "
                "Do not decide whether a requirement applies to a business, do not add legal advice, and do not infer missing rules. "
                "Return JSON: {\"summaries\":[{\"source_url\":\"exact supplied URL\","
                "\"findings\":[{\"statement\":\"concise restatement\","
                "\"evidence_quote\":\"exact verbatim substring from that page\"}]}]}. "
                "Use no user or business facts. Return an empty findings list when the page contains no supported procedure."
            ),
        )
    except (httpx.HTTPError, RuntimeError, ValueError, KeyError, IndexError, TypeError):
        return {"status": "unavailable", "summaries": []}

    if not isinstance(result, dict) or not isinstance(result.get("summaries"), list):
        return {"status": "no_supported_findings", "summaries": []}
    page_text = {
        source["url"]: " ".join(source["excerpt"].split()).casefold()
        for source in captured_sources
    }
    summaries = []
    for summary in result["summaries"]:
        if not isinstance(summary, dict) or not isinstance(summary.get("findings"), list):
            continue
        source_url = summary.get("source_url")
        if not isinstance(source_url, str) or source_url not in page_text:
            continue
        findings = []
        for finding in summary["findings"]:
            if not isinstance(finding, dict):
                continue
            statement = finding.get("statement")
            quote = " ".join(str(finding.get("evidence_quote") or "").split())
            if (
                isinstance(statement, str)
                and statement.strip()
                and quote
                and quote.casefold() in page_text[source_url]
            ):
                findings.append({"statement": statement.strip(), "evidence_quote": quote})
        if findings:
            summaries.append({"source_url": source_url, "findings": findings})
    return {"status": "available" if summaries else "no_supported_findings", "summaries": summaries}


def next_agent_question(memory: dict) -> tuple[str, str]:
    questions = [
        ("business_name", "What business name should appear on the application or preparation sheet?"),
        ("activity", "What will the business sell or do?"),
        ("location", "Which town/city and state is the business in? This prototype currently covers West Bengal, India."),
        ("premises", "Will it operate from a home, shared, or commercial premises?"),
        ("owner_name", "Who is the applicant or owner? You may skip personal details for now."),
        ("address", "What is the business address? You may skip this for now."),
    ]
    if memory.get("industry") == "food" or re.search(r"\b(gst|tax|turnover)\b", memory.get("goal", ""), re.I):
        questions.append(("annual_turnover", "What is the estimated annual turnover in INR? You may skip if unknown."))
    if re.search(r"\b(employee|staff|worker|team)\b", memory.get("goal", ""), re.I):
        questions.append(("employee_count", "How many employees or workers do you expect? You may skip if unknown."))
    skipped = set(memory.get("_skipped", []))
    for key, question in questions:
        if not memory.get(key) and key not in skipped:
            return key, question
    return "complete", "The interview is complete. I will show the collected facts, missing details, and captured sources for review."


def update_memory_from_message(memory: dict, message: str) -> bool:
    text = message.strip()
    missing_key, _ = next_agent_question(memory)
    if missing_key == "complete":
        return False
    if text.lower() in {"skip", "unknown", "not sure", "prefer not to say", "i don't know"}:
        if missing_key == "location":
            return False
        memory.setdefault("_skipped", []).append(missing_key)
        return True
    if missing_key in {"annual_turnover", "employee_count"}:
        amount = re.search(r"\d[\d,]*(?:\.\d+)?", text)
        if not amount:
            return False
        value = float(amount.group(0).replace(",", ""))
        if missing_key == "annual_turnover":
            lowered = text.lower()
            if "crore" in lowered:
                value *= 10_000_000
            elif "lakh" in lowered or "lac" in lowered:
                value *= 100_000
            elif re.search(r"\b(?:k|thousand)\b", lowered):
                value *= 1_000
        memory[missing_key] = int(value)
    elif missing_key == "premises":
        lowered = text.lower()
        if any(value in lowered for value in ("home", "residential", "house")):
            memory[missing_key] = "residential"
        elif "shared" in lowered or "co-working" in lowered:
            memory[missing_key] = "shared"
        elif any(value in lowered for value in ("commercial", "shop", "office", "storefront")):
            memory[missing_key] = "commercial"
        else:
            return False
    else:
        memory[missing_key] = text
    memory["_inferred_fields"] = [
        field for field in memory.get("_inferred_fields", []) if field != missing_key
    ]
    return True


@app.post("/api/v1/agent/sessions")
def create_agent_session(goal: str, workspace_id: str = LOCAL_WORKSPACE_ID, user: dict | None = Depends(get_local_user)):
    authorize_workspace(workspace_id, user)
    if not goal.strip():
        raise HTTPException(status_code=400, detail="A goal is required")
    session_id = str(uuid.uuid4())
    memory = infer_agent_facts(goal)
    missing_key, first_question = next_agent_question(memory)
    stage = "ready_to_research" if missing_key == "complete" else "interview"
    messages = [
        {"role": "agent", "content": "I’ll collect only the details used in this preparation sheet. Source findings are candidates for review, not legal advice, and I will not submit anything.", "type": "system"},
    ]
    inferred = [f"{key}: {memory[key]}" for key in memory["_inferred_fields"]]
    if inferred:
        messages.append({
            "role": "agent",
            "content": f"Candidate facts parsed from your goal (not confirmed): {', '.join(inferred)}.",
            "type": "candidate_facts",
        })
    if stage == "interview":
        messages.append({"role": "agent", "content": first_question, "type": "question"})
    with db() as connection:
        connection.execute(
            "INSERT INTO agent_sessions (id,workspace_id,goal,stage,memory_json,messages_json,status) VALUES (?,?,?,?,?,?,?)",
            (session_id, workspace_id, goal.strip(), stage, json.dumps(memory), json.dumps(messages), "active"),
        )
    return {"session_id": session_id, "goal": goal.strip(), "stage": stage, "memory": memory, "messages": messages}


@app.get("/api/v1/agent/sessions/{session_id}")
def get_agent_session(session_id: str, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        row = connection.execute("SELECT * FROM agent_sessions WHERE id=?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent session not found")
    authorize_workspace(row["workspace_id"], user)
    return {"session_id": row["id"], "goal": row["goal"], "stage": row["stage"], "memory": json.loads(row["memory_json"]), "messages": json.loads(row["messages_json"]), "status": row["status"]}


@app.post("/api/v1/agent/sessions/{session_id}/message")
def agent_message(session_id: str, payload: AgentMessage, user: dict | None = Depends(get_local_user)):
    with db() as connection:
        row = connection.execute("SELECT * FROM agent_sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent session not found")
        authorize_workspace(row["workspace_id"], user)
        memory = json.loads(row["memory_json"])
        messages = json.loads(row["messages_json"])
        messages.append({"role": "user", "content": payload.message, "type": "answer"})
        accepted = update_memory_from_message(memory, payload.message)
        next_key, question = next_agent_question(memory)
        stage = "ready_to_research" if next_key == "complete" else "interview"
        if not accepted:
            question = "I couldn't use that answer for this field. Please provide a valid value, or skip if the field is optional."
            if next_key != "complete":
                question = f"{question} {next_agent_question(memory)[1]}"
            stage = "interview"
        elif next_key == "complete":
            skipped = memory.get("_skipped", [])
            if skipped:
                question = f"Interview complete. Not provided: {', '.join(skipped)}. I can now collect public sources and prepare a review sheet."
        messages.append({"role": "agent", "content": question, "type": "question" if stage == "interview" else "ready"})
        connection.execute(
            "UPDATE agent_sessions SET stage=?,memory_json=?,messages_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (stage, json.dumps(memory), json.dumps(messages), session_id),
        )
    return {"session_id": session_id, "stage": stage, "memory": memory, "messages": messages}


@app.post("/api/v1/agent/sessions/{session_id}/research")
def research_agent_session(session_id: str, user: dict | None = Depends(get_local_user)):
    session = get_agent_session(session_id, user)
    memory = session["memory"]
    if session["stage"] not in {"ready_to_research", "research_complete"}:
        raise HTTPException(status_code=409, detail="Complete the interview before starting research")
    location = (memory.get("location") or "").lower()
    supported_locations = (
        "west bengal", "kolkata", "howrah", "asansol", "durgapur", "siliguri",
        "kharagpur", "bardhaman", "burdwan", "malda", "hooghly", "darjeeling",
    )
    if not any(place in location for place in supported_locations):
        result = {
            "session_id": session_id,
            "status": "unsupported_jurisdiction",
            "jurisdiction": memory.get("location"),
            "sources": [],
            "forms": [],
            "source_summaries": [],
            "live_search": {"status": "not_available", "answer": "", "sources": []},
            "summary_status": "no_sources",
            "missing": ["West Bengal jurisdiction confirmation"],
            "warnings": ["This prototype has source coverage only for West Bengal, India. No requirements or forms were inferred."],
        }
        memory["_research"] = result
        with db() as connection:
            connection.execute(
                "UPDATE agent_sessions SET stage='out_of_scope',memory_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (json.dumps(memory), session_id),
            )
        return result

    targets = list(AGENT_SOURCE_TARGETS["common"])
    if memory.get("industry") == "food":
        targets = AGENT_SOURCE_TARGETS["food"] + targets
    sources = []
    forms = []
    seen_forms = set()
    form_link_pattern = re.compile(r"\b(form|application|registr(?:ation|y)?|licen[cs]e|download|certificate)\b", re.I)
    document_fetch_count = 0

    def capture_target(target: tuple[str, str, str]) -> dict:
        authority, url, title = target
        try:
            return {
                "authority": authority,
                "title": title,
                "url": url,
                "pages": capture_site_pages(url, max_linked_pages=2, timeout=8),
            }
        except (httpx.HTTPError, ValueError, UnicodeError) as exc:
            failure = capture_failure_details(exc)
            return {
                "authority": authority,
                "title": title,
                "url": url,
                "error": describe_capture_error(exc),
                **failure,
            }

    with ThreadPoolExecutor(max_workers=min(5, len(targets))) as executor:
        captured_results = list(executor.map(capture_target, targets))
    for result in captured_results:
        if "error" in result:
            sources.append({
                "authority": result["authority"],
                "title": result["title"],
                "url": result["url"],
                "classification": "official_domain",
                "captured": False,
                "capture_error": result["error"],
                "validation_status": result["validation_status"],
                "http_status": result["http_status"],
                "checked_on": date.today().isoformat(),
            })
            continue
        for page in result["pages"]:
            source = page.get("source")
            if not page["captured"]:
                sources.append({
                    "authority": result["authority"],
                    "title": page["title"],
                    "url": page["url"],
                    "classification": "official_domain",
                    "captured": False,
                    "capture_error": page["capture_error"],
                    "page_depth": page["depth"],
                    "parent_url": page["parent_url"],
                    "validation_status": page["validation_status"],
                    "http_status": page["http_status"],
                    "checked_on": date.today().isoformat(),
                })
                continue
            captured_source = {
                "authority": result["authority"],
                "title": page["title"] or result["title"],
                "url": page["url"],
                "classification": "official_domain",
                "captured": True,
                "content_hash": source["content_hash"],
                "excerpt": source["text_excerpt"][:1200],
                "highlights": source_highlights(source["text_excerpt"]),
                "content_type": source["content_type"],
                "page_depth": page["depth"],
                "parent_url": page["parent_url"],
                "validation_status": "working",
                "http_status": source.get("status_code"),
                "checked_on": date.today().isoformat(),
            }
            sources.append(captured_source)
            for link in source.get("links", []):
                is_document = is_official_document_link(link)
                if (
                    link["url"] not in seen_forms
                    and (is_document or form_link_pattern.search(f"{link['title']} {link['url']}"))
                    and len(forms) < 8
                ):
                    seen_forms.add(link["url"])
                    if is_document and document_fetch_count >= 4:
                        form = {
                            "title": link["title"],
                            "official_url": link["url"],
                            "source_page": captured_source["url"],
                            "resource_type": "document",
                            "status": "fetch_limit_reached",
                            "validation_status": "unverified",
                            "checked_on": date.today().isoformat(),
                        }
                    else:
                        if is_document:
                            document_fetch_count += 1
                        form = verify_candidate_form_link(
                            link["title"],
                            link["url"],
                            captured_source["url"],
                            memory,
                            session_id,
                        )
                    forms.append(form)
    required_fields = ("business_name", "activity", "location", "premises")
    missing = [field for field in required_fields if not memory.get(field)]
    warnings = []
    live_search = {"status": "not_needed", "answer": "", "sources": [], "queries": []}
    shops_portal = next(
        (source for source in sources if source["authority"] == "West Bengal Shops & Establishments"),
        None,
    )
    live_search_attempted = False
    if shops_portal and not shops_portal["captured"]:
        if os.getenv("GEMINI_API_KEY"):
            live_search_attempted = True
            try:
                business_activity = str(
                    memory.get("activity") or memory.get("industry") or "new business"
                )[:200]
                live_search = GeminiProvider().search_grounded(
                    "Find current West Bengal government pages and application forms for this business activity: "
                    f"{business_activity}. Prefer a direct official PDF or the exact official online-application page. "
                    "Distinguish a blank form from an online portal, cite official government sources only, and do not "
                    "infer that a form applies or provide legal advice. If no exact form can be confirmed, say so."
                )
            except (httpx.HTTPError, RuntimeError, ValueError, KeyError, IndexError, TypeError) as exc:
                live_search = {"status": "unavailable", "answer": "", "sources": [], "queries": []}
                warnings.append(
                    f"Gemini live web search failed ({type(exc).__name__}); check the configured model, API access, and network."
                )
            if live_search["status"] != "available" and not any(
                "Gemini live web search failed" in warning for warning in warnings
            ):
                warnings.append(
                    "Gemini live web search returned no answer with official government citations."
                )
        else:
            live_search = {"status": "not_configured", "answer": "", "sources": [], "queries": []}
            warnings.append(
                "The Shops & Establishments portal was unreachable and Gemini live web search is not configured."
            )
    if live_search.get("status") == "available":
        validated_citations = []
        for citation in live_search.get("sources", [])[:8]:
            citation_url = citation["url"]
            is_document = is_official_document_link({"url": citation_url})
            existing_form = next(
                (form for form in forms if form["official_url"] == citation_url),
                None,
            )
            if existing_form:
                verified = existing_form
            elif is_document and document_fetch_count >= 4:
                verified = {
                    "title": citation["title"],
                    "official_url": citation_url,
                    "source_page": citation_url,
                    "resource_type": "document",
                    "status": "fetch_limit_reached",
                    "validation_status": "unverified",
                    "checked_on": date.today().isoformat(),
                }
            else:
                verified = verify_candidate_form_link(
                    citation["title"],
                    citation_url,
                    citation_url,
                    memory,
                    session_id,
                )
                if is_document:
                    document_fetch_count += 1
            citation.update({
                "validation_status": verified["validation_status"],
                "checked_on": verified["checked_on"],
                "http_status": verified.get("http_status"),
            })
            if verified.get("capture_error"):
                citation["capture_error"] = verified["capture_error"]
            validated_citations.append(citation)
            if (
                citation_url not in seen_forms
                and (is_document or form_link_pattern.search(f"{citation['title']} {citation_url}"))
                and len(forms) < 8
            ):
                seen_forms.add(citation_url)
                forms.append(verified)
        live_search["sources"] = validated_citations
    source_summary = (
        {"status": "skipped_for_live_search", "summaries": []}
        if live_search_attempted
        else summarize_public_sources(sources)
    )
    if not any(source["captured"] for source in sources):
        if live_search["status"] == "available":
            warnings.append(
                "No official pages could be fetched directly. Gemini search citations are research leads; verify them manually."
            )
        else:
            warnings.append("No official pages could be captured. Treat this as a fact sheet only.")
    if not forms:
        warnings.append(
            "No application form or document link was detected on the captured static pages. "
            "Some portals load forms with JavaScript or require an authenticated session."
        )
    elif not any(form["validation_status"] == "working" for form in forms):
        warnings.append(
            "Candidate links were detected, but none could be verified as working. "
            "Links marked Not found should not be used; unavailable links still need a manual check."
        )
    if source_summary["status"] in {"not_configured", "unavailable", "no_supported_findings"}:
        warnings.append("No source-grounded AI summary is available; captured excerpts remain for manual review.")
    result = {
        "session_id": session_id,
        "status": "research_complete",
        "jurisdiction": "West Bengal, India",
        "sources": sources,
        "forms": forms,
        "source_summaries": source_summary["summaries"],
        "live_search": live_search,
        "summary_status": source_summary["status"],
        "missing": missing,
        "unconfirmed": memory.get("_inferred_fields", []),
        "warnings": warnings,
        "disclaimer": "Captured page text and links are research leads, not verified legal requirements.",
    }
    memory["_research"] = result
    with db() as connection:
        connection.execute(
            "UPDATE agent_sessions SET stage='research_complete',memory_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (json.dumps(memory), session_id),
        )
    return result


def suggest_pdf_field_values(fields: list[dict], memory: dict) -> dict[str, str]:
    matches = [
        ("business_name", ("business name", "trade name", "establishment name", "firm name", "enterprise name")),
        ("owner_name", ("applicant name", "owner name", "proprietor name", "authorised signatory", "authorized signatory")),
        ("address", ("business address", "premises address", "establishment address", "address")),
        ("activity", ("nature of business", "business activity", "activity description", "activity")),
        ("location", ("district", "city", "town", "location")),
        ("employee_count", ("number of employees", "employee count", "number of workers", "staff count")),
        ("annual_turnover", ("annual turnover", "turnover", "annual sales")),
    ]
    unconfirmed = set(memory.get("_inferred_fields") or [])
    suggestions = {}
    for field in fields:
        normalized = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", f"{field['name']} {field['label']}")
        normalized = re.sub(r"[_\W]+", " ", normalized).casefold()
        for memory_key, labels in matches:
            value = memory.get(memory_key)
            if (
                memory_key not in unconfirmed
                and value is not None
                and any(label in normalized for label in labels)
            ):
                suggestions[field["name"]] = str(value)[:500]
                break
    return suggestions


def verify_candidate_form_link(
    title: str,
    url: str,
    source_page: str,
    memory: dict,
    session_id: str,
) -> dict:
    form = {
        "title": title,
        "official_url": url,
        "source_page": source_page,
        "resource_type": "document" if is_official_document_link({"url": url}) else "portal_page",
        "status": "unavailable",
        "validation_status": "unavailable",
        "checked_on": date.today().isoformat(),
    }
    try:
        if form["resource_type"] == "document":
            document = capture_official_document(url, timeout=8, cache_directory=FORM_CACHE_DIR)
            cached_pdf = document.pop("cached_pdf_name", None)
            form.update(document)
            form["status"] = "document_available"
            form["validation_status"] = "working"
            if cached_pdf:
                form["preview_url"] = f"/api/v1/agent/sessions/{session_id}/forms/{form['content_hash']}/preview"
                form["suggested_values"] = suggest_pdf_field_values(form["fillable_fields"], memory)
        else:
            page = capture_source(url, timeout=8)
            form.update({
                "status": "portal_available",
                "validation_status": "working",
                "page_title": page["title"],
                "page_excerpt": page["text_excerpt"][:1200],
                "resolved_url": page["canonical_url"],
            })
    except (httpx.HTTPError, ValueError, UnicodeError) as exc:
        failure = capture_failure_details(exc)
        form.update(failure)
        form["status"] = "not_found" if failure["validation_status"] == "not_found" else "unavailable"
        form["capture_error"] = describe_capture_error(exc)
    return form


@app.post("/api/v1/agent/sessions/{session_id}/generate")
def generate_agent_package(session_id: str, user: dict | None = Depends(get_local_user)):
    session = get_agent_session(session_id, user)
    memory = session["memory"]
    research = memory.get("_research")
    if session["stage"] != "research_complete" or not research:
        raise HTTPException(status_code=409, detail="Run source research before generating the review sheet")
    package_dir = UPLOAD_DIR / "generated"
    package_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = package_dir / f"{session_id}-preparation-sheet.pdf"
    pdf = canvas.Canvas(str(pdf_path), pagesize=A4)
    width, height = A4
    pdf.setTitle("PermitPilot Application Preparation Sheet")
    y = height - 55

    def write_lines(value: str, bold: bool = False, size: int = 9):
        nonlocal y
        text = str(value)
        if any(ord(character) > 126 for character in text):
            text = json.dumps(text, ensure_ascii=True)
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        for line in textwrap.wrap(text, width=92) or [""]:
            if y < 55:
                pdf.showPage()
                y = height - 55
                pdf.setFont("Helvetica", 9)
            pdf.drawString(50, y, line)
            y -= size + 5

    write_lines("PermitPilot — Application Preparation Sheet", bold=True, size=17)
    write_lines("DRAFT ONLY — NOT AN OFFICIAL FORM, LEGAL OPINION, SIGNATURE, OR SUBMISSION")
    y -= 10
    write_lines("Goal and location", bold=True, size=11)
    write_lines(f"Goal: {memory.get('goal') or 'Not provided'}")
    write_lines(f"Jurisdiction: {memory.get('location')}, West Bengal, India")
    y -= 8
    write_lines("Collected facts", bold=True, size=11)
    fields = [
        ("Business name", memory.get("business_name")),
        ("Applicant", memory.get("owner_name")),
        ("Address", memory.get("address")),
        ("Activity", memory.get("activity")),
        ("Premises", memory.get("premises")),
        ("Annual turnover (INR)", memory.get("annual_turnover")),
        ("Employees", memory.get("employee_count")),
    ]
    for label, value in fields:
        write_lines(f"{label}: {value if value is not None else 'NOT PROVIDED'}")
    if research["missing"]:
        write_lines(f"Facts not confirmed: {', '.join(research['missing'])}")
    if research["unconfirmed"]:
        write_lines(f"Goal-derived values to verify: {', '.join(research['unconfirmed'])}")
    y -= 8
    write_lines("Official-source pages", bold=True, size=11)
    captured_sources = [source for source in research["sources"] if source["captured"]]
    if not captured_sources:
        write_lines("No source page was successfully captured. Do not rely on this sheet for compliance decisions.")
    for source in research["sources"]:
        write_lines(f"{source['authority']}: {source['title']}", bold=True)
        write_lines(source["url"])
        if source["captured"]:
            write_lines(f"SHA-256: {source['content_hash']}")
            write_lines("Relevant text excerpts (not legal interpretations):")
            for highlight in source["highlights"]:
                write_lines(f"- {highlight}")
        else:
            write_lines(f"Page capture failed: {source.get('capture_error', 'No capture details available')}")
    live_search = research.get("live_search") or {}
    if live_search.get("status") == "available":
        y -= 8
        write_lines("Gemini real-time Google Search lead — verify at source", bold=True, size=11)
        write_lines(live_search["answer"])
        for source in live_search["sources"]:
            write_lines(f"{source['title']}: {source['url']}")
    if research["source_summaries"]:
        y -= 8
        write_lines("AI notes from public source text; verify each quote", bold=True, size=11)
        for summary in research["source_summaries"]:
            write_lines(f"Source: {summary['source_url']}")
            for finding in summary["findings"]:
                write_lines(f"- {finding['statement']}")
                write_lines(f"  Quote: {finding['evidence_quote']}")
    y -= 8
    write_lines("Official forms and application links — live status", bold=True, size=11)
    if research["forms"]:
        for form in research["forms"]:
            status = form.get("validation_status", "unverified").upper()
            write_lines(f"{form['title']} [{status}]: {form['official_url']}")
            if status == "NOT_FOUND":
                write_lines(
                    f"Do not use this link; the source returned HTTP {form.get('http_status') or '404/410'}."
                )
            if form.get("document_type"):
                page_count = form.get("page_count")
                write_lines(
                    f"Retrieved {form['document_type']} document"
                    + (f" · {page_count} pages" if page_count else "")
                    + f" · {form.get('byte_size', 0)} bytes"
                )
                if form.get("fillable_fields"):
                    write_lines(f"Detected {len(form['fillable_fields'])} fillable text fields; user review required.")
                if form.get("text_excerpt"):
                    write_lines(f"Extracted form text preview: {form['text_excerpt'][:500]}")
            elif form.get("capture_error"):
                write_lines(f"Document retrieval failed: {form['capture_error']}")
            else:
                write_lines("Candidate page only; not verified as the correct form for this business.")
    else:
        write_lines("No form link was detected on captured pages. No official form has been mapped or filled.")
    y -= 8
    write_lines("Next step: verify applicability and the correct form with the authority, then complete and submit it yourself.")
    pdf.save()
    review_state = {
        "form_title": "Application preparation sheet — not an official form",
        "mapped_fields": fields,
        "pdf_url": f"/api/v1/agent/sessions/{session_id}/document",
        "candidate_forms": research["forms"],
        "sources": research["sources"],
        "source_summaries": research["source_summaries"],
        "live_search": live_search,
        "missing": research["missing"],
        "unconfirmed": research["unconfirmed"],
        "signature_required": False,
        "submission_allowed": False,
        "disclaimer": "No official form has been mapped, signed, or submitted. Verify all facts and requirements with the relevant authority.",
    }
    with db() as connection:
        connection.execute(
            "UPDATE agent_sessions SET stage='review',status='awaiting_approval',memory_json=?,messages_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (json.dumps({**memory, "_review": review_state}), json.dumps(session["messages"]), session_id),
        )
    return {"session_id": session_id, "stage": "review", "review": review_state}


@app.get("/api/v1/agent/sessions/{session_id}/document")
def download_agent_document(session_id: str, user: dict | None = Depends(get_local_user)):
    session = get_agent_session(session_id, user)
    pdf_path = UPLOAD_DIR / "generated" / f"{session_id}-preparation-sheet.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Review package has not been generated")
    return FileResponse(pdf_path, media_type="application/pdf", filename="permitpilot-preparation-sheet.pdf")


def get_cached_official_pdf(session_id: str, content_hash: str, user: dict) -> tuple[dict, Path]:
    if not re.fullmatch(r"[a-f0-9]{64}", content_hash):
        raise HTTPException(status_code=404, detail="Official form document not found")
    session = get_agent_session(session_id, user)
    research = session["memory"].get("_research") or {}
    form = next(
        (
            candidate for candidate in research.get("forms", [])
            if candidate.get("content_hash") == content_hash
            and candidate.get("document_type") == "PDF"
            and candidate.get("status") == "document_available"
        ),
        None,
    )
    if not form:
        raise HTTPException(status_code=404, detail="Official form document not found")
    pdf_path = FORM_CACHE_DIR / f"{content_hash}.pdf"
    if not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="Cached official form is no longer available")
    return form, pdf_path


@app.get("/api/v1/agent/sessions/{session_id}/forms/{content_hash}/preview")
def preview_official_form(
    session_id: str,
    content_hash: str,
    user: dict | None = Depends(get_local_user),
):
    form, pdf_path = get_cached_official_pdf(session_id, content_hash, user)
    title = re.sub(r"[^A-Za-z0-9 _.-]", "", form.get("title", "official-form"))[:80].strip() or "official-form"
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{title}.pdf"'},
    )


@app.post("/api/v1/agent/sessions/{session_id}/forms/{content_hash}/fill")
def fill_official_form(
    session_id: str,
    content_hash: str,
    request: OfficialFormFillRequest,
    user: dict | None = Depends(get_local_user),
):
    form, pdf_path = get_cached_official_pdf(session_id, content_hash, user)
    if len(request.fields) > 100:
        raise HTTPException(status_code=422, detail="A maximum of 100 form fields can be filled")
    allowed_fields = {
        field["name"]
        for field in form.get("fillable_fields", [])
        if field.get("type") == "text"
    }
    if not request.fields or not set(request.fields).issubset(allowed_fields):
        raise HTTPException(status_code=422, detail="Only detected text fields from this form can be filled")
    if any(len(value) > 500 for value in request.fields.values()):
        raise HTTPException(status_code=422, detail="Form field values must be 500 characters or fewer")
    values = {name: value for name, value in request.fields.items() if value.strip()}
    if not values:
        raise HTTPException(status_code=422, detail="Enter at least one value before creating a filled draft")
    try:
        reader = PdfReader(str(pdf_path), strict=False)
        writer = PdfWriter(clone_from=reader)
        for page in writer.pages:
            writer.update_page_form_field_values(page, values, auto_regenerate=True)
        output = io.BytesIO()
        writer.write(output)
    except (PdfReadError, OSError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail="The official PDF could not be filled safely") from exc
    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="permitpilot-filled-draft.pdf"'},
    )


@app.post("/api/v1/agent/sessions/{session_id}/approve")
def approve_agent_package(session_id: str, reviewer_name: str, user: dict | None = Depends(get_local_user)):
    if not reviewer_name.strip():
        raise HTTPException(status_code=400, detail="Reviewer name is required")
    with db() as connection:
        row = connection.execute("SELECT * FROM agent_sessions WHERE id=?", (session_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent session not found")
        authorize_workspace(row["workspace_id"], user)
        if row["stage"] != "review":
            raise HTTPException(status_code=409, detail="Generate and review the preparation sheet first")
        memory = json.loads(row["memory_json"])
        memory["_approval"] = {
            "reviewer_name": reviewer_name.strip(),
            "acknowledged": True,
            "submission_status": "manual_submission_required",
        }
        connection.execute("UPDATE agent_sessions SET stage='approved',status='approved',memory_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (json.dumps(memory), session_id))
    return {
        "session_id": session_id,
        "review_acknowledged": True,
        "submission_status": "manual_submission_required",
        "government_submission": False,
    }


FRONTEND_DIST_DIR = Path(
    os.getenv("FRONTEND_DIST_DIR", Path(__file__).resolve().parent.parent / "static")
).resolve()


@app.get("/", include_in_schema=False)
def serve_frontend():
    index_path = FRONTEND_DIST_DIR / "index.html"
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail="Frontend build not found")
    return FileResponse(index_path)


@app.get("/{asset_path:path}", include_in_schema=False)
def serve_frontend_asset(asset_path: str):
    if asset_path == "healthz" or asset_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    requested_path = (FRONTEND_DIST_DIR / asset_path).resolve()
    if requested_path != FRONTEND_DIST_DIR and FRONTEND_DIST_DIR not in requested_path.parents:
        raise HTTPException(status_code=404, detail="Not found")
    if requested_path.is_file():
        return FileResponse(requested_path)
    index_path = FRONTEND_DIST_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)
    raise HTTPException(status_code=404, detail="Frontend build not found")
