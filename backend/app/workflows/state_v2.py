"""工作流状态 — 岗位生成工作流

使用 LangGraph 原生 interrupt 机制处理人工干预，不再手动管理 requires_human_intervention
"""
from typing import TypedDict, List, Optional, Any


class JDWorkflowState(TypedDict):
    """岗位生成工作流状态 — 用于 LangGraph interrupt 模式"""
    # 基础信息
    request_id: int
    status: str                # running / completed / terminated
    error: Optional[str]

    # 需求阶段
    raw_requirements: Optional[str]
    is_specific: bool          # AI判断：需求是否具体
    clarification_round: int
    clarification_history: List[dict]   # [{"q", "a", "round"}]
    finalized_requirements: Optional[str]

    # JD 阶段
    jd_id: Optional[int]
    jd_status: str             # draft / pending_review / approved / rejected
    enhanced_jd_text: Optional[str]


def get_initial_jd_state(request_id: int) -> JDWorkflowState:
    return {
        "request_id": request_id,
        "status": "running",
        "error": None,

        "raw_requirements": None,
        "is_specific": False,
        "clarification_round": 0,
        "clarification_history": [],
        "finalized_requirements": None,

        "jd_id": None,
        "jd_status": "draft",
        "enhanced_jd_text": None,
    }


# ══════════════════════════════════════════════
# 工作流 2：简历筛选工作流（给 graph_screening.py 用）
# ══════════════════════════════════════════════

class ScreeningWorkflowState(TypedDict):
    """简历筛选工作流状态"""
    request_id: int
    current_node: str
    status: str
    error: Optional[str]
    workflow_type: str

    jd_id: Optional[int]
    jd_title: Optional[str]
    department: Optional[str]

    resume_ids: List[int]
    candidate_pool: List[dict]
    screened_count: int
    pending_count: int

    ai_screened_ids: List[int]
    ai_rejected_ids: List[int]
    ai_recommended_ids: List[int]

    manual_passed_ids: List[int]
    manual_rejected_ids: List[int]

    interview_ids: List[int]
    current_interview_id: Optional[int]
    interview_round_count: int

    offer_id: Optional[int]
    offer_status: str

    onboarding_status: str
    onboarding_tasks: List[str]

    requires_human_intervention: bool
    human_action: Optional[str]
    human_action_data: Optional[dict]

    screening_threshold: float


def get_initial_screening_state(request_id: int, jd_id: Optional[int] = None,
                                 jd_title: str = "", department: str = "") -> ScreeningWorkflowState:
    return {
        "request_id": request_id,
        "current_node": "resume_collect",
        "status": "running",
        "error": None,
        "workflow_type": "resume_screening",

        "jd_id": jd_id,
        "jd_title": jd_title,
        "department": department,

        "resume_ids": [],
        "candidate_pool": [],
        "screened_count": 0,
        "pending_count": 0,

        "ai_screened_ids": [],
        "ai_rejected_ids": [],
        "ai_recommended_ids": [],

        "manual_passed_ids": [],
        "manual_rejected_ids": [],

        "interview_ids": [],
        "current_interview_id": None,
        "interview_round_count": 0,

        "offer_id": None,
        "offer_status": "draft",

        "onboarding_status": "pending",
        "onboarding_tasks": [],

        "requires_human_intervention": False,
        "human_action": None,
        "human_action_data": None,

        "screening_threshold": 60.0,
    }
