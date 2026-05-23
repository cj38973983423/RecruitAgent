"""工作流图 — 岗位生成工作流 (JD Generation)

简化版：去掉多轮澄清，模糊需求直接用 AI 技能增强 → 生成 JD → PENDING_REVIEW
"""

import json
import logging
import sqlite3

from app.workflows.state_v2 import JDWorkflowState
from app.services.llm_service import call_llm_json, call_llm
from app.services.jd_service import enhance_jd_with_rag, seed_standard_jds
from app.services.vector_store import vector_store
from app.database import SessionLocal
from app.models import (
    RecruitmentRequest, JobDescription, JDStatus, RequestStatus,
    WorkflowLog,
)

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import StateGraph, END
    from langgraph.checkpoint.sqlite import SqliteSaver
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    SqliteSaver = None


# ══════════════════════════════════════════════
# 节点函数
# ══════════════════════════════════════════════

def node_check_and_generate(state: JDWorkflowState) -> dict:
    """节点：AI 增强原始需求 → 直接生成 JD（跳过多轮澄清）

    无论需求多模糊，都用 AI 技能直接增强后生成 JD。
    """
    request_id = state["request_id"]
    db = SessionLocal()
    try:
        req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()
        if not req:
            return {"error": f"需求 {request_id} 不存在", "status": "terminated"}

        raw_text = state.get("raw_requirements") or req.raw_requirements or ""

        # ── 已有 finalized_requirements（resume 场景） ──
        if state.get("finalized_requirements"):
            _log(db, request_id, "requirement_collect", "completed",
                 {"finalized": state["finalized_requirements"][:200]})
            return state  # 直接透传

        # ── AI 增强：用技能把模糊需求变成完整需求描述 ──
        logger.info(f"🧠 AI 正在增强需求 {request_id}: {raw_text[:50]}...")

        enhance_prompt = f"""你是一个资深的招聘专家和 JD 写作专家。

直接输出补充完善后的招聘需求，不要任何开场白或解释。

原始需求：{raw_text}

请基于这个模糊需求，发挥你的行业知识，生成一份完整的、专业的招聘需求描述。
注意不要问用户问题，直接补充缺失信息。""".strip()

        try:
            finalized_text = call_llm(enhance_prompt, timeout=120)
            if not finalized_text or len(finalized_text.strip()) < 20:
                logger.warning(f"AI 增强输出过短，使用原始需求")
                finalized_text = raw_text
        except Exception as e:
            logger.warning(f"AI 增强需求失败: {e}")
            finalized_text = raw_text

        req.finalized_requirements = finalized_text
        req.is_clarified = True
        req.status = RequestStatus.READY
        db.commit()
        _log(db, request_id, "requirement_collect", "ai_enhanced",
             {"finalized": finalized_text[:200], "original_length": len(raw_text)})

        return {
            "finalized_requirements": finalized_text,
            "status": "running",
        }

    finally:
        db.close()


def node_jd_generation(state: JDWorkflowState) -> dict:
    """节点：JD 生成 — AI 增强 + RAG → PENDING_REVIEW"""
    request_id = state["request_id"]
    db = SessionLocal()
    try:
        req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()
        if not req:
            return {"error": f"需求 {request_id} 不存在", "status": "terminated"}

        try:
            vector_store.connect()
            seed_standard_jds()
        except Exception as e:
            logger.warning(f"向量库不可用: {e}")

        raw_jd = req.finalized_requirements or req.raw_requirements or ""
        try:
            enhancement = enhance_jd_with_rag(raw_jd)
        except Exception as e:
            logger.warning(f"AI 增强失败: {e}")
            enhancement = {"enhanced_jd": raw_jd, "responsibilities": [], "requirements": []}

        enhanced_text = enhancement.get("enhanced_jd", raw_jd)

        jd = JobDescription(
            request_id=request_id, version=1,
            title=req.position_name, department=req.department,
            content=enhanced_text, original_content=raw_jd,
            enhancement_log=enhancement,
            responsibilities=json.dumps(enhancement.get("responsibilities", []), ensure_ascii=False) if enhancement.get("responsibilities") else None,
            requirements_list=json.dumps(enhancement.get("requirements", []), ensure_ascii=False) if enhancement.get("requirements") else None,
            status=JDStatus.PENDING_REVIEW,
        )
        db.add(jd)
        db.commit()
        db.refresh(jd)

        req.enhanced_jd = enhanced_text
        req.status = RequestStatus.IN_PROGRESS
        db.commit()

        _log(db, request_id, "jd_generation", "completed", {"jd_id": jd.id, "enhanced": True})

        return {
            "jd_id": jd.id,
            "jd_status": "pending_review",
            "enhanced_jd_text": enhanced_text,
            "status": "completed",
        }
    finally:
        db.close()


# ══════════════════════════════════════════════
# 构建图
# ══════════════════════════════════════════════

_jd_graph = None
CHECKPOINTS_DB = "checkpoints.db"


def get_jd_graph():
    """获取编译后的岗位生成工作流图（简化版：AI增强 → 生成JD）"""
    global _jd_graph
    if _jd_graph is not None:
        return _jd_graph
    if not LANGGRAPH_AVAILABLE:
        return None

    conn = sqlite3.connect(CHECKPOINTS_DB, check_same_thread=False)
    workflow = StateGraph(JDWorkflowState)

    workflow.add_node("requirement_collect", node_check_and_generate)
    workflow.add_node("jd_generation", node_jd_generation)

    workflow.set_entry_point("requirement_collect")
    workflow.add_edge("requirement_collect", "jd_generation")
    workflow.add_edge("jd_generation", END)

    checkpointer = SqliteSaver(conn)
    _jd_graph = workflow.compile(checkpointer=checkpointer)
    return _jd_graph


def get_jd_graph_definition() -> dict:
    return {
        "nodes": [
            {"id": "requirement_collect", "label": "AI 需求增强", "type": "ai"},
            {"id": "jd_generation", "label": "AI 生成 JD（RAG增强）", "type": "ai"},
            {"id": "__end__", "label": "完成", "type": "end"},
        ],
        "edges": [
            {"from": "requirement_collect", "to": "jd_generation", "label": "增强完成"},
            {"from": "jd_generation", "to": "__end__", "label": "AI已生成"},
        ],
    }


# ══════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════

def _log(db, request_id, node, status, data=None):
    log = WorkflowLog(request_id=request_id, node=node, status=status, output_data=data)
    db.add(log)
    db.commit()
