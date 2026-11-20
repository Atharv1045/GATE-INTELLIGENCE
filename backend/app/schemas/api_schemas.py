"""
Pydantic Request and Response Schemas for GATE Intelligence REST API (/api/v1/).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UserRegisterRequest(BaseModel):
    email: str = Field(..., description="Student email address")
    full_name: str = Field(..., min_length=2, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)
    target_paper_code: str = Field(default="CS")
    target_year: int = Field(default=2026, ge=2024, le=2030)


class UserLoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    target_paper_code: str
    target_year: int
    role: str
    preferences: Dict[str, Any] = {}
    created_at: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class QuestionOptionSchema(BaseModel):
    option_label: str
    option_text: str
    is_correct: Optional[bool] = None


class AnswerKeySchema(BaseModel):
    answer_type: str
    correct_options: List[str] = []
    numerical_min: Optional[float] = None
    numerical_max: Optional[float] = None
    tolerance: float = 0.01
    provenance: str = "unverified"
    explanation: Optional[str] = None


class QuestionUpdateRequest(BaseModel):
    question_text: Optional[str] = None
    question_type: Optional[str] = None
    marks: Optional[float] = None
    negative_marks: Optional[float] = None
    subject_name: Optional[str] = None
    primary_topic_name: Optional[str] = None
    subtopic_name: Optional[str] = None
    difficulty_level: Optional[str] = None
    options: Optional[List[QuestionOptionSchema]] = None
    answer_key: Optional[AnswerKeySchema] = None


class QuestionVerifyRequest(BaseModel):
    provenance: str = Field(default="manually_verified")
    correct_options: Optional[List[str]] = None
    numerical_min: Optional[float] = None
    numerical_max: Optional[float] = None
    explanation: Optional[str] = None


class TutorAskRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=2000)
    paper_code: Optional[str] = "CS"
    subject_name: Optional[str] = None
    topic_name: Optional[str] = None
    examination_year: Optional[int] = None
    top_k: int = Field(default=5, ge=1, le=15)


class MockTestGenerateRequest(BaseModel):
    title: Optional[str] = None
    paper_code: str = Field(default="CS")
    test_mode: str = Field(
        default="topic_wise",
        description="full_length | subject_wise | topic_wise | mixed_topic | difficulty_based | pyq_only | ai_practice",
    )
    subject_filter: Optional[str] = None
    topic_filter: Optional[str] = None
    difficulty_filter: Optional[str] = None
    question_count: int = Field(default=10, ge=1, le=65)
    duration_minutes: int = Field(default=30, ge=5, le=180)
    include_ai_questions: bool = Field(default=False)


class StudentAnswerItem(BaseModel):
    question_id: str
    selected_options: List[str] = []
    numerical_answer: Optional[float] = None
    marked_for_review: bool = False
    time_spent_seconds: int = 0


class MockTestSubmitRequest(BaseModel):
    time_taken_seconds: int = Field(default=0, ge=0)
    responses: List[StudentAnswerItem]


class StudyPlanGenerateRequest(BaseModel):
    paper_code: str = Field(default="CS")
    target_year: int = Field(default=2026)
    available_days: int = Field(default=60, ge=7, le=365)
    daily_hours: float = Field(default=4.0, ge=1.0, le=14.0)


class StudyPlanUpdateRequest(BaseModel):
    progress_percent: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    completed_topics: Optional[List[str]] = None
    daily_hours: Optional[float] = None
