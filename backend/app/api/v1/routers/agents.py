"""
Lightweight Agents Router (/api/v1/agents).
Provides fast, local, deterministic execution for the 4 practical agents:
1. PYQ Analysis Agent
2. Performance Agent
3. Question Assistant
4. Paper Analysis Agent
Zero external LLM API calls, zero Redis/Celery, operates 100% offline.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.agents.lightweight_agents import (
    PaperAnalysisAgent,
    PerformanceAgent,
    PYQAnalysisAgent,
    QuestionAssistant,
)

router = APIRouter(tags=["agents"])


class PYQAnalysisRequest(BaseModel):
    paper_code: str = "CS"
    subject_name: Optional[str] = None


class PerformanceRequest(BaseModel):
    paper_code: str = "CS"


class QuestionAssistantRequest(BaseModel):
    question_id: str


class PaperAnalysisRequest(BaseModel):
    paper_id: Optional[str] = None
    year: Optional[int] = None
    paper_code: str = "CS"


@router.post("/agents/pyq-analysis")
def run_pyq_analysis(payload: PYQAnalysisRequest) -> Dict[str, Any]:
    return PYQAnalysisAgent.analyze(
        paper_code=payload.paper_code,
        subject_name=payload.subject_name,
    )


@router.post("/agents/performance")
def run_performance_analysis(payload: PerformanceRequest) -> Dict[str, Any]:
    return PerformanceAgent.evaluate(paper_code=payload.paper_code)


@router.post("/agents/question-assistant")
def run_question_assistant(payload: QuestionAssistantRequest) -> Dict[str, Any]:
    return QuestionAssistant.assist(question_id=payload.question_id)


@router.post("/agents/paper-analysis")
def run_paper_analysis(payload: PaperAnalysisRequest) -> Dict[str, Any]:
    return PaperAnalysisAgent.analyze(
        paper_id=payload.paper_id,
        year=payload.year,
        paper_code=payload.paper_code,
    )
