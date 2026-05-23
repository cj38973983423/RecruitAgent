"""LangGraph 工作流图 — 全流程状态机构建"""
import logging
from typing import Literal

from app.workflows.state import RecruitmentState, get_initial_state
from app.workflows.nodes.requirements import (
    node_requirement_collect,
    node_jd_generation,
    node_jd_review,
)
from app.workflows.nodes.resume_screening import (
    node_resume_collect,
    node_resume_ai_screen,
    node_resume_manual_screen,
)
from app.workflows.nodes.interview import (
    node_interview_schedule,
    node_interview_questions,
    node_interview_execute,
    node_interview_evaluate,
    node_offer_manage,
    node_onboarding,
)

logger = logging.getLogger(__name__)

# 尝试导入 LangGraph
try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    logger.warning("LangGraph not installed, using fallback state machine")


# ─── 条件跳转函数 ───

def route_after_clarification(state: RecruitmentState) -> Literal["jd_generation", "requirement_collect", "__end__"]:
    """需求澄清后的路由"""
    if state.get("status") == "terminated":
        return "__end__"
    if state.get("is_clarified") or state.get("current_node") == "jd_generation":
        return "jd_generation"
    return "requirement_collect"


def route_after_jd_review(state: RecruitmentState) -> Literal["jd_generation", "resume_collect", "__end__"]:
    """JD 审核后的路由"""
    if state.get("status") == "terminated":
        return "__end__"
    if state.get("jd_status") == "approved":
        return "resume_collect"
    return "jd_generation"  # 驳回，重新生成


def route_after_resume_collect(state: RecruitmentState) -> Literal["resume_ai_screen", "resume_collect", "__end__"]:
    """简历收集后的路由"""
    if state.get("status") == "terminated":
        return "__end__"
    if state.get("current_node") == "resume_ai_screen":
        return "resume_ai_screen"
    return "resume_collect"


def route_after_ai_screen(state: RecruitmentState) -> Literal["resume_manual_screen", "__end__"]:
    """AI 初筛后的路由"""
    if state.get("status") == "terminated":
        return "__end__"
    return "resume_manual_screen"


def route_after_manual_screen(state: RecruitmentState) -> Literal["interview_schedule", "__end__"]:
    """人工筛选后的路由"""
    if state.get("status") == "terminated":
        return "__end__"
    if state.get("current_node") == "interview_schedule":
        return "interview_schedule"
    # 没有合适候选人
    if not state.get("manual_passed_ids") and not state.get("ai_screened_ids"):
        return "__end__"
    return "interview_schedule"


def route_after_interview_schedule(state: RecruitmentState) -> Literal["interview_questions", "interview_schedule", "__end__"]:
    """面试安排后的路由"""
    if state.get("status") == "terminated":
        return "__end__"
    if state.get("current_node") == "interview_questions":
        return "interview_questions"
    return "interview_schedule"


def route_after_questions(state: RecruitmentState) -> Literal["interview_execute", "__end__"]:
    if state.get("status") == "terminated":
        return "__end__"
    return "interview_execute"


def route_after_interview(state: RecruitmentState) -> Literal["interview_evaluate", "__end__"]:
    if state.get("status") == "terminated":
        return "__end__"
    return "interview_evaluate"


def route_after_evaluation(state: RecruitmentState) -> Literal["offer_manage", "interview_schedule", "__end__"]:
    """面试评估后的路由：通过→Offer 或 下一轮面试"""
    if state.get("status") == "terminated":
        return "__end__"
    if state.get("current_node") == "offer_manage":
        return "offer_manage"
    if state.get("current_node") == "interview_schedule":
        return "interview_schedule"
    return "offer_manage"


def route_after_offer(state: RecruitmentState) -> Literal["onboarding", "offer_manage", "__end__"]:
    if state.get("status") == "terminated":
        return "__end__"
    if state.get("offer_status") == "accepted":
        return "onboarding"
    if state.get("current_node") == "onboarding":
        return "onboarding"
    if state.get("offer_status") in ("rejected", "withdrawn"):
        return "__end__"
    return "offer_manage"


def route_from_onboarding(state: RecruitmentState) -> Literal["__end__", "onboarding"]:
    if state.get("onboarding_status") == "completed":
        return "__end__"
    return "onboarding"


# ─── 构建图 ───

def build_recruitment_graph() -> StateGraph:
    """构建招聘全流程 LangGraph"""
    if not LANGGRAPH_AVAILABLE:
        logger.warning("LangGraph 不可用，返回空图")
        return None

    workflow = StateGraph(RecruitmentState)

    # 添加节点
    workflow.add_node("requirement_collect", node_requirement_collect)
    workflow.add_node("jd_generation", node_jd_generation)
    workflow.add_node("jd_review", node_jd_review)
    workflow.add_node("resume_collect", node_resume_collect)
    workflow.add_node("resume_ai_screen", node_resume_ai_screen)
    workflow.add_node("resume_manual_screen", node_resume_manual_screen)
    workflow.add_node("interview_schedule", node_interview_schedule)
    workflow.add_node("interview_questions", node_interview_questions)
    workflow.add_node("interview_execute", node_interview_execute)
    workflow.add_node("interview_evaluate", node_interview_evaluate)
    workflow.add_node("offer_manage", node_offer_manage)
    workflow.add_node("onboarding", node_onboarding)

    # 设置入口
    workflow.set_entry_point("requirement_collect")

    # 条件边
    workflow.add_conditional_edges(
        "requirement_collect",
        route_after_clarification,
    )
    workflow.add_conditional_edges(
        "jd_generation",
        lambda s: "jd_review",
    )
    workflow.add_conditional_edges(
        "jd_review",
        route_after_jd_review,
    )
    workflow.add_conditional_edges(
        "resume_collect",
        route_after_resume_collect,
    )
    workflow.add_conditional_edges(
        "resume_ai_screen",
        route_after_ai_screen,
    )
    workflow.add_conditional_edges(
        "resume_manual_screen",
        route_after_manual_screen,
    )
    workflow.add_conditional_edges(
        "interview_schedule",
        route_after_interview_schedule,
    )
    workflow.add_conditional_edges(
        "interview_questions",
        route_after_questions,
    )
    workflow.add_conditional_edges(
        "interview_execute",
        route_after_interview,
    )
    workflow.add_conditional_edges(
        "interview_evaluate",
        route_after_evaluation,
    )
    workflow.add_conditional_edges(
        "offer_manage",
        route_after_offer,
    )
    workflow.add_conditional_edges(
        "onboarding",
        route_from_onboarding,
    )

    return workflow.compile()


def get_graph_definition() -> dict:
    """返回图定义（用于前端展示）"""
    return {
        "nodes": [
            {"id": "requirement_collect", "label": "需求收集", "type": "ai_human"},
            {"id": "jd_generation", "label": "JD生成(AI增强)", "type": "ai"},
            {"id": "jd_review", "label": "JD审核", "type": "human"},
            {"id": "resume_collect", "label": "简历收集", "type": "event"},
            {"id": "resume_ai_screen", "label": "AI初筛", "type": "ai"},
            {"id": "resume_manual_screen", "label": "人工复筛", "type": "human"},
            {"id": "interview_schedule", "label": "面试安排", "type": "human"},
            {"id": "interview_questions", "label": "面试题生成(AI)", "type": "ai"},
            {"id": "interview_execute", "label": "面试执行", "type": "human"},
            {"id": "interview_evaluate", "label": "面试评估", "type": "human"},
            {"id": "offer_manage", "label": "Offer管理", "type": "human"},
            {"id": "onboarding", "label": "入职跟进", "type": "human"},
        ],
        "edges": [
            {"from": "requirement_collect", "to": "jd_generation", "label": "需求已澄清"},
            {"from": "requirement_collect", "to": "requirement_collect", "label": "继续澄清"},
            {"from": "jd_generation", "to": "jd_review", "label": "AI已增强"},
            {"from": "jd_review", "to": "resume_collect", "label": "审核通过"},
            {"from": "jd_review", "to": "jd_generation", "label": "驳回修改"},
            {"from": "resume_collect", "to": "resume_ai_screen", "label": "有简历待筛"},
            {"from": "resume_ai_screen", "to": "resume_manual_screen", "label": "AI已完成"},
            {"from": "resume_manual_screen", "to": "interview_schedule", "label": "人工确认"},
            {"from": "interview_schedule", "to": "interview_questions", "label": "已排期"},
            {"from": "interview_questions", "to": "interview_execute", "label": "已出题"},
            {"from": "interview_execute", "to": "interview_evaluate", "label": "面试完成"},
            {"from": "interview_evaluate", "to": "offer_manage", "label": "推荐录用"},
            {"from": "interview_evaluate", "to": "interview_schedule", "label": "下一轮面试"},
            {"from": "offer_manage", "to": "onboarding", "label": "接受Offer"},
            {"from": "onboarding", "to": "__end__", "label": "入职完成"},
        ],
    }
