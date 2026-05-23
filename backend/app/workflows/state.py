"""LangGraph 工作流状态定义"""
from typing import TypedDict, List, Optional, Any, Annotated
import operator


class RecruitmentState(TypedDict):
    """招聘全流程状态"""
    # 工作流控制
    request_id: int
    current_node: str                    # 当前节点名称
    status: str                          # running / paused / completed / terminated
    error: Optional[str]                 # 错误信息
    messages: Annotated[List[dict], operator.add]  # 对话历史

    # 需求阶段
    raw_requirements: Optional[str]      # 原始需求
    clarification_round: int             # 当前澄清轮次
    clarification_history: List[dict]    # 澄清问答记录
    is_clarified: bool                   # 是否已完成澄清
    finalized_requirements: Optional[str]  # 确认后的需求
    enhanced_jd_text: Optional[str]      # AI 增强后的 JD

    # JD 阶段
    jd_id: Optional[int]
    jd_status: str                       # draft / pending_review / approved / rejected
    jd_review_comment: Optional[str]
    jd_vector_synced: bool               # 是否同步到向量库

    # 渠道发布 (预留)
    channel_publish_status: str

    # 简历阶段
    resume_ids: List[int]                # 收集到的简历 ID
    ai_screened_ids: List[int]           # AI 初筛通过的 ID
    ai_rejected_ids: List[int]           # AI 初筛淘汰的 ID
    ai_recommended_ids: List[int]        # AI 推荐的 ID
    manual_passed_ids: List[int]         # 人工复筛通过 ID
    manual_rejected_ids: List[int]       # 人工复筛淘汰 ID
    duplicate_resume_ids: List[int]      # 重复简历 ID

    screening_threshold: float           # 筛选阈值

    # 面试阶段
    interview_ids: List[int]             # 面试 ID 列表
    current_interview_id: Optional[int]
    interview_round_count: int           # 当前面试轮次计数

    # Offer 阶段
    offer_id: Optional[int]
    offer_status: str

    # 入职阶段
    onboarding_status: str
    onboarding_tasks: List[str]

    # 人工干预标记
    requires_human_intervention: bool    # 是否等待人工操作
    human_action: Optional[str]          # 人工操作类型
    human_action_data: Optional[dict]    # 人工操作数据


def get_initial_state(request_id: int) -> RecruitmentState:
    """创建初始状态"""
    return {
        "request_id": request_id,
        "current_node": "requirement_collect",
        "status": "running",
        "error": None,
        "messages": [],

        "raw_requirements": None,
        "clarification_round": 0,
        "clarification_history": [],
        "is_clarified": False,
        "finalized_requirements": None,
        "enhanced_jd_text": None,

        "jd_id": None,
        "jd_status": "draft",
        "jd_review_comment": None,
        "jd_vector_synced": False,

        "channel_publish_status": "pending",

        "resume_ids": [],
        "ai_screened_ids": [],
        "ai_rejected_ids": [],
        "ai_recommended_ids": [],
        "manual_passed_ids": [],
        "manual_rejected_ids": [],
        "duplicate_resume_ids": [],
        "screening_threshold": 60.0,

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
    }
