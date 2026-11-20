"""
GATE Intelligence Unified API Router (/api/v1).
Aggregates the 7 modular sub-routers:
1. questions.py   -> Question Bank browsing, filtering, search, interactive answer check
2. dashboard.py   -> Student metrics, subject progress bars, recent activity log
3. papers.py      -> Paper Library catalog, details, question preview
4. analytics.py   -> PYQ Analytics distributions (subject, topic, year, marks, types)
5. tests.py       -> CBT Mock Test creation, 180-min timer, authoritative GATE scoring
6. agents.py      -> 4 Lightweight deterministic local agents
7. settings.py    -> Preferences, backups, reset progress, validated JSON import
Includes clean backward-compatibility aliases for seamless frontend transitions.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.v1.routers.agents import router as agents_router
from app.api.v1.routers.analytics import (
    get_pyq_distributions,
    router as analytics_router,
)
from app.api.v1.routers.dashboard import router as dashboard_router
from app.api.v1.routers.papers import router as papers_router
from app.api.v1.routers.questions import router as questions_router
from app.api.v1.routers.settings import router as settings_router
from app.api.v1.routers.tests import (
    CandidateQuestionResponse,
    TestStartRequest,
    TestSubmitRequest,
    router as tests_router,
    start_test,
    submit_test,
)

router = APIRouter()

# Mount all 7 sub-routers
router.include_router(questions_router)
router.include_router(dashboard_router)
router.include_router(papers_router)
router.include_router(analytics_router)
router.include_router(tests_router)
router.include_router(agents_router)
router.include_router(settings_router)


# =========================================================================
# Backward-Compatibility & Helper Aliases
# =========================================================================

# Analytics backward-compatibility endpoints
@router.get("/analytics/overview")
def analytics_overview(paper_code: str = Query("CS")) -> Dict[str, Any]:
    return get_pyq_distributions(paper_code=paper_code)


@router.get("/analytics/subjects")
def analytics_subjects(paper_code: str = Query("CS")) -> Dict[str, Any]:
    data = get_pyq_distributions(paper_code=paper_code)
    return {"paper_code": paper_code, "subjects": data.get("subject_distribution", [])}


@router.get("/analytics/topics")
def analytics_topics(
    paper_code: str = Query("CS"),
    subject_name: Optional[str] = Query(None),
) -> Dict[str, Any]:
    data = get_pyq_distributions(paper_code=paper_code, subject_name=subject_name)
    return {"paper_code": paper_code, "topics": data.get("topic_distribution", [])}


@router.get("/analytics/trends")
def analytics_trends(paper_code: str = Query("CS")) -> Dict[str, Any]:
    data = get_pyq_distributions(paper_code=paper_code)
    return {"paper_code": paper_code, "trends": data.get("year_trends", [])}


# Mock Tests backward-compatibility endpoints
class LegacyTestGenerateRequest(BaseModel):
    paper_code: str = "CS"
    test_mode: str = "full"
    duration_minutes: int = 180
    subject_name: Optional[str] = None
    paper_id: Optional[str] = None
    year: Optional[int] = None


@router.post("/tests/generate")
def legacy_generate_test(payload: LegacyTestGenerateRequest) -> Dict[str, Any]:
    req = TestStartRequest(
        paper_code=payload.paper_code,
        test_mode=payload.test_mode,
        paper_id=payload.paper_id,
        year=payload.year,
        subject_name=payload.subject_name,
        duration_minutes=payload.duration_minutes,
    )
    return start_test(req)


# Single-user local profile endpoints (eliminates auth blockers & JWT failures)
@router.get("/auth/me")
def get_auth_me() -> Dict[str, Any]:
    return {
        "id": "local_gate_student",
        "email": "student@local.gate",
        "full_name": "GATE Aspirant",
        "role": "student",
        "target_paper_code": "CS",
        "target_year": 2026,
    }


@router.post("/auth/login")
def auth_login() -> Dict[str, Any]:
    return {
        "access_token": "local_dev_token",
        "token_type": "bearer",
        "user": {
            "id": "local_gate_student",
            "email": "student@local.gate",
            "full_name": "GATE Aspirant",
            "role": "student",
        },
    }


@router.post("/auth/register")
def auth_register() -> Dict[str, Any]:
    return auth_login()
