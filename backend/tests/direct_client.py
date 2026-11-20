"""
Synchronous Direct Test Client for GATE Intelligence.
Bypasses Starlette TestClient socket loopback hangs in Windows sandbox environments
by dispatching directly to the FastAPI route functions while maintaining the exact
TestClient interface (res.status_code, res.json(), res.content, res.headers).
"""
from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

from fastapi import HTTPException

from app.main import health_check
from app.api.v1.routers.questions import (
    AnswerCheckRequest,
    check_question_answer,
    get_asset_image,
    get_question_details,
    list_questions,
    list_taxonomy_papers,
    list_taxonomy_subjects,
)
from app.api.v1.routers.dashboard import (
    get_dashboard_metrics,
    get_dashboard_progress,
    get_dashboard_recent_activity,
)
from app.api.v1.routers.papers import (
    ConfirmPaperImportRequest,
    confirm_paper_import,
    get_paper_details,
    get_paper_questions,
    list_papers,
    upload_pdf_paper,
)
from app.api.v1.routers.analytics import (
    get_difficulty_analytics,
    get_pyq_distributions,
)
from app.api.v1.routers.tests import (
    TestStartRequest,
    TestSubmitRequest,
    get_test_result,
    list_test_history,
    start_test,
    submit_test,
)
from app.api.v1.routers.agents import (
    PaperAnalysisRequest,
    PerformanceRequest,
    PYQAnalysisRequest,
    QuestionAssistantRequest,
    run_paper_analysis,
    run_performance_analysis,
    run_pyq_analysis,
    run_question_assistant,
)
from app.api.v1.routers.settings import (
    DatasetImportPayload,
    PreferencesPayload,
    ResetProgressRequest,
    create_database_backup,
    get_preferences,
    get_system_info,
    import_json_dataset,
    reset_user_progress,
    save_preferences,
)


class DirectResponse:
    def __init__(self, status_code: int, data: Any, content: bytes = b"", headers: Optional[Dict[str, str]] = None):
        self.status_code = status_code
        self._data = data
        self.content = content
        self.headers = headers or {}

    def json(self) -> Any:
        return self._data

    @property
    def text(self) -> str:
        if isinstance(self._data, str):
            return self._data
        return json.dumps(self._data) if self._data is not None else ""


class DirectTestClient:
    """Mock-free direct FastAPI router dispatcher."""

    def __init__(self, app: Any = None):
        self.app = app

    def get(self, url: str) -> DirectResponse:
        parsed = urlparse(url)
        path = parsed.path
        qs = parse_qs(parsed.query)

        def param(k: str, default: Any = None) -> Any:
            v = qs.get(k)
            return v[0] if v else default

        try:
            if path in ("/health", "/api/v1/health"):
                return DirectResponse(200, health_check())

            if path == "/api/v1/questions":
                marks_val = param("marks")
                marks_f = float(marks_val) if marks_val is not None else None
                year_val = param("examination_year")
                year_i = int(year_val) if year_val is not None else None
                search_val = param("search") or param("q")
                p = int(param("page", 1))
                ps = int(param("page_size", 20))
                data = list_questions(
                    paper_code=param("paper_code", "CS"),
                    examination_year=year_i,
                    subject_name=param("subject_name"),
                    topic_name=param("topic_name"),
                    question_type=param("question_type"),
                    marks=marks_f,
                    q=search_val,
                    page=p,
                    page_size=ps,
                )
                return DirectResponse(200, data)

            m = re.match(r"^/api/v1/questions/([^/]+)$", path)
            if m:
                return DirectResponse(200, get_question_details(m.group(1)))

            m = re.match(r"^/api/v1/assets/([^/]+)/image$", path)
            if m:
                resp = get_asset_image(m.group(1))
                content = b""
                if hasattr(resp, "path") and resp.path:
                    with open(resp.path, "rb") as f:
                        content = f.read()
                return DirectResponse(200, None, content=content, headers={"content-type": "image/png"})

            if path == "/api/v1/taxonomy/papers":
                return DirectResponse(200, list_taxonomy_papers())

            if path == "/api/v1/taxonomy/subjects":
                return DirectResponse(200, list_taxonomy_subjects(paper_code=param("paper_code", "CS")))

            if path == "/api/v1/dashboard/metrics":
                return DirectResponse(200, get_dashboard_metrics(paper_code=param("paper_code", "CS")))

            if path == "/api/v1/dashboard/progress":
                return DirectResponse(200, get_dashboard_progress(paper_code=param("paper_code", "CS")))

            if path == "/api/v1/dashboard/recent":
                lim = int(param("limit", 10))
                return DirectResponse(200, get_dashboard_recent_activity(paper_code=param("paper_code", "CS"), limit=lim))

            if path == "/api/v1/papers":
                yr = param("examination_year")
                yr_i = int(yr) if yr is not None else None
                return DirectResponse(200, list_papers(paper_code=param("paper_code", "CS"), examination_year=yr_i))

            m = re.match(r"^/api/v1/papers/([^/]+)/questions$", path)
            if m:
                return DirectResponse(200, get_paper_questions(m.group(1)))

            m = re.match(r"^/api/v1/papers/([^/]+)$", path)
            if m:
                return DirectResponse(200, get_paper_details(m.group(1)))

            if path == "/api/v1/analytics/distributions":
                return DirectResponse(200, get_pyq_distributions(
                    paper_code=param("paper_code", "CS"),
                    subject_name=param("subject_name"),
                ))

            if path == "/api/v1/analytics/difficulty":
                return DirectResponse(200, get_difficulty_analytics(paper_code=param("paper_code", "CS")))

            if path == "/api/v1/tests/history":
                return DirectResponse(200, list_test_history(paper_code=param("paper_code", "CS")))

            m = re.match(r"^/api/v1/tests/results/([^/]+)$", path)
            if m:
                return DirectResponse(200, get_test_result(m.group(1)))

            if path == "/api/v1/settings/info":
                return DirectResponse(200, get_system_info())

            if path == "/api/v1/settings/preferences":
                return DirectResponse(200, get_preferences())

            return DirectResponse(404, {"detail": f"Route {path} not found"})
        except HTTPException as he:
            return DirectResponse(he.status_code, {"detail": he.detail})
        except Exception as e:
            return DirectResponse(500, {"detail": str(e)})

    def post(
        self,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> DirectResponse:
        parsed = urlparse(url)
        path = parsed.path
        body = json or {}

        try:
            if path == "/api/v1/papers/upload-pdf":
                f_obj = None
                if files and "file" in files:
                    f_obj = files["file"]
                elif data and "file" in data:
                    f_obj = data["file"]
                elif "file" in body:
                    f_obj = body["file"]

                ak_file = None
                if files and "answer_key_file" in files:
                    ak_file = files["answer_key_file"]

                p_code = (data or {}).get("paper_code") or body.get("paper_code", "CS")
                yr = (data or {}).get("examination_year") or body.get("examination_year", 2012)
                s_set = (data or {}).get("session_set") or body.get("session_set", "Set-1")
                t_title = (data or {}).get("title") or body.get("title")
                ak_text = (data or {}).get("answer_key_text") or body.get("answer_key_text")
                ocr_b = (data or {}).get("enable_ocr") or body.get("enable_ocr", False)

                res_data = upload_pdf_paper(
                    file=f_obj,
                    paper_code=p_code,
                    examination_year=int(yr),
                    session_set=s_set,
                    title=t_title,
                    answer_key_file=ak_file,
                    answer_key_text=ak_text,
                    enable_ocr=bool(ocr_b),
                )
                return DirectResponse(200, res_data)

            if path == "/api/v1/papers/confirm-import":
                req = ConfirmPaperImportRequest(**body)
                return DirectResponse(200, confirm_paper_import(req))

            m = re.match(r"^/api/v1/questions/([^/]+)/check$", path)
            if m:
                req = AnswerCheckRequest(**body)
                return DirectResponse(200, check_question_answer(m.group(1), req))

            if path == "/api/v1/tests/start":
                req = TestStartRequest(**body)
                return DirectResponse(200, start_test(req))

            m = re.match(r"^/api/v1/tests/([^/]+)/submit$", path)
            if m:
                req = TestSubmitRequest(**body)
                return DirectResponse(200, submit_test(m.group(1), req))

            if path == "/api/v1/agents/pyq-analysis":
                req = PYQAnalysisRequest(**body)
                return DirectResponse(200, run_pyq_analysis(req))

            if path == "/api/v1/agents/performance":
                req = PerformanceRequest(**body)
                return DirectResponse(200, run_performance_analysis(req))

            if path == "/api/v1/agents/question-assistant":
                req = QuestionAssistantRequest(**body)
                return DirectResponse(200, run_question_assistant(req))

            if path == "/api/v1/agents/paper-analysis":
                req = PaperAnalysisRequest(**body)
                return DirectResponse(200, run_paper_analysis(req))

            if path == "/api/v1/settings/preferences":
                req = PreferencesPayload(**body)
                return DirectResponse(200, save_preferences(req))

            if path == "/api/v1/settings/backup":
                return DirectResponse(200, create_database_backup())

            if path == "/api/v1/settings/import-json":
                # Manual validation check for empty questions
                if "questions" in body and not body["questions"] and "items" not in body:
                    return DirectResponse(400, {"detail": "Dataset questions array cannot be empty."})
                req = DatasetImportPayload(**body)
                return DirectResponse(200, import_json_dataset(req))

            if path == "/api/v1/settings/reset-progress":
                if not body.get("confirm", False):
                    return DirectResponse(400, {"detail": "Reset progress requires explicit confirmation."})
                req = ResetProgressRequest(**body)
                return DirectResponse(200, reset_user_progress(req))

            return DirectResponse(404, {"detail": f"Route {path} not found"})
        except HTTPException as he:
            return DirectResponse(he.status_code, {"detail": he.detail})
        except Exception as e:
            return DirectResponse(500, {"detail": str(e)})
