"""Pydantic 请求/响应模型"""
import json
from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field

from app.models import (
    WorkflowNode, RequestStatus, JDStatus, ResumeStatus,
    InterviewRound, InterviewStatus, OfferStatus, InterviewerStatus,
)


# ══════════════════════════════════════════════
# 工作流
# ══════════════════════════════════════════════

class WorkflowStateResponse(BaseModel):
    request_id: int
    current_node: str
    status: str
    available_actions: List[str] = []


class WorkflowActionRequest(BaseModel):
    request_id: int
    action: str
    data: Optional[dict] = None


# ══════════════════════════════════════════════
# 招聘需求
# ══════════════════════════════════════════════

class RecruitmentRequestCreate(BaseModel):
    department: str
    position_name: str
    headcount: int = 1
    urgency: str = "normal"
    raw_requirements: Optional[str] = None
    budget_range: Optional[str] = None
    created_by: Optional[str] = None


class ClarifyAnswer(BaseModel):
    request_id: int
    question_id: str
    answer: str


class RecruitmentRequestResponse(BaseModel):
    id: int
    department: str
    position_name: str
    headcount: int
    urgency: str
    status: RequestStatus
    clarification_round: int
    is_clarified: bool
    clarification_history: Optional[list] = None
    finalized_requirements: Optional[str] = None
    enhanced_jd: Optional[str] = None
    created_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# JD
# ══════════════════════════════════════════════

class JDCreate(BaseModel):
    request_id: int
    title: str
    department: Optional[str] = None
    location: Optional[str] = None
    content: str
    required_skills: Optional[str] = None
    nice_to_have: Optional[str] = None
    experience_required: Optional[str] = None
    education_required: Optional[str] = None


class JDEnhanceRequest(BaseModel):
    jd_id: int
    additional_context: Optional[str] = None


class JDReviewRequest(BaseModel):
    jd_id: int
    approved: bool
    review_comment: Optional[str] = None
    reviewed_by: Optional[str] = None


class JDResponse(BaseModel):
    id: int
    request_id: int
    version: int
    title: str
    department: Optional[str] = None
    status: JDStatus
    content: Optional[str] = None
    required_skills: Optional[str] = None
    enhanced_content: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════
# 简历
# ══════════════════════════════════════════════

class ResumeDeepAnalysis(BaseModel):
    """简历深度分析结果"""
    project_authenticity: Optional[dict] = None
    job_fit: Optional[dict] = None
    career_trajectory: Optional[dict] = None
    risk_warnings: Optional[list] = None
    frequent_job_change: Optional[bool] = None
    resume_consistency: Optional[dict] = None


class ResumeResponse(BaseModel):
    id: int
    name: Optional[str] = None
    skills: Optional[str] = None
    experience_years: Optional[float] = None
    ai_score: Optional[float] = None
    ai_recommended: bool = False
    ai_reason: Optional[str] = None
    status: ResumeStatus
    deep_analysis: Optional[Any] = None
    is_duplicate: bool = False
    file_name: Optional[str] = None
    jd_id: Optional[int] = None
    jd_title: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ResumeBatchAction(BaseModel):
    resume_ids: List[int]
    action: str  # pass / reject / note
    note: Optional[str] = None
    reviewer: Optional[str] = None


# ══════════════════════════════════════════════
# 面试
# ══════════════════════════════════════════════

class InterviewCreate(BaseModel):
    resume_id: int
    jd_id: Optional[int] = None
    round: InterviewRound = InterviewRound.FIRST
    interviewer_name: str
    interviewer_email: Optional[str] = None
    candidate_email: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    duration_minutes: int = 60
    location: Optional[str] = None
    meeting_link: Optional[str] = None


class InterviewResponse(BaseModel):
    id: int
    resume_id: int
    round: InterviewRound
    interviewer_name: Optional[str] = None
    candidate_name: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    status: InterviewStatus
    meeting_link: Optional[str] = None

    model_config = {"from_attributes": True}


class InterviewQuestionResponse(BaseModel):
    id: int
    category: str
    difficulty: str
    question_text: str
    expected_answer: Optional[str] = None
    created_by: str = "ai"

    model_config = {"from_attributes": True}


class InterviewEvaluationCreate(BaseModel):
    evaluator: str
    tech_score: float = Field(ge=0, le=100)
    communication_score: float = Field(ge=0, le=100)
    overall_score: float = Field(ge=0, le=100)
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    conclusion: Optional[str] = None
    recommendation: str  # pass / hold / reject


class QuickPassRequest(BaseModel):
    """快速通过请求"""
    rating_level: str = "good"  # excellent / good / average
    notes: Optional[str] = None
    evaluator: Optional[str] = None


# ══════════════════════════════════════════════
# Offer
# ══════════════════════════════════════════════

class OfferCreate(BaseModel):
    resume_id: int
    jd_id: Optional[int] = None
    candidate_name: str
    position_name: str
    department: str
    salary: str
    equity: Optional[str] = None
    start_date: Optional[datetime] = None
    notes: Optional[str] = None


# ══════════════════════════════════════════════
# 面试官库
# ══════════════════════════════════════════════

class InterviewerCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    skills: Optional[list[str]] = None
    notes: Optional[str] = None
    max_interviews_per_day: int = 5


class InterviewerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    skills: Optional[list[str]] = None
    interview_count: Optional[int] = None
    rating: Optional[float] = None
    notes: Optional[str] = None
    status: Optional[InterviewerStatus] = None


class InterviewerResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    position: Optional[str] = None
    department: Optional[str] = None
    skills: Optional[list[str]] = None
    interview_count: int = 0
    rating: Optional[float] = None
    notes: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm(cls, obj):
        """手动从ORM对象构造，处理skills JSON字符串转换"""
        data = {}
        for field in cls.model_fields:
            data[field] = getattr(obj, field, None)
        # 特殊处理skills：JSON字符串→列表
        skills_raw = data.get("skills")
        if isinstance(skills_raw, str):
            try:
                parsed = json.loads(skills_raw)
                if isinstance(parsed, list):
                    data["skills"] = parsed
                else:
                    data["skills"] = [s.strip() for s in skills_raw.split(",") if s.strip()]
            except (json.JSONDecodeError, TypeError):
                data["skills"] = [s.strip() for s in skills_raw.split(",") if s.strip()]
        # status枚举→字符串
        status_val = data.get("status")
        if hasattr(status_val, "value"):
            data["status"] = status_val.value
        # created_at→字符串
        ca = data.get("created_at")
        if hasattr(ca, "isoformat"):
            data["created_at"] = ca.isoformat()
        return cls(**data)
