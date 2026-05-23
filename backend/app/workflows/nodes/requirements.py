"""工作流节点 — 需求收集 + JD 生成 + JD 审核"""
import logging
from app.workflows.state import RecruitmentState
from app.services.llm_service import call_llm_json
from app.services.jd_service import (
    generate_clarification_questions,
    enhance_jd_with_rag,
    seed_standard_jds,
)
from app.services.vector_store import vector_store
from app.database import SessionLocal
from app.models import (
    RecruitmentRequest, JobDescription, JDStatus, RequestStatus,
    WorkflowLog, WorkflowNode,
)

logger = logging.getLogger(__name__)


def node_requirement_collect(state: RecruitmentState) -> dict:
    """节点：需求收集 — 多轮澄清"""
    request_id = state["request_id"]

    db = SessionLocal()
    try:
        req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()
        if not req:
            return {"error": f"招聘需求 {request_id} 不存在", "status": "terminated"}

        current_round = state["clarification_round"]

        # 清除之前的干预标记
        updates = {
            "requires_human_intervention": False,
            "human_action": None,
            "human_action_data": None,
        }

        if not state.get("raw_requirements"):
            updates["raw_requirements"] = req.raw_requirements

        # 检查是否澄清完成或达到最大轮数
        max_rounds = 3
        if state.get("is_clarified") or current_round >= max_rounds:
            # 收集完成，生成最终需求
            history_lines = []
            for h in state.get("clarification_history", []):
                history_lines.append(f"Q: {h.get('q')}\nA: {h.get('a')}")
            history_text = "\n".join(history_lines)

            prompt = f"""基于以下需求信息和澄清对话，生成最终确认的招聘需求描述。

原始需求：{req.raw_requirements or '无'}

澄清历史：
{history_text}

请整合所有信息，输出一份完整的招聘需求描述。"""

            result = call_llm_json(prompt, timeout=120)
            finalized = result.get("finalized_requirements") or result.get("enhanced_jd") or req.raw_requirements

            req.status = RequestStatus.READY
            req.finalized_requirements = finalized
            req.is_clarified = True
            db.commit()

            _log_workflow(db, request_id, "requirement_collect", "completed", {
                "finalized_requirements": finalized[:200],
            })

            updates["finalized_requirements"] = finalized
            updates["is_clarified"] = True
            updates["current_node"] = "jd_generation"
            return updates

        # 生成澄清问题
        questions = generate_clarification_questions(
            req.raw_requirements,
            state.get("clarification_history"),
            current_round + 1,
        )

        if not questions:
            # 没有需要澄清的问题，直接进入下一步
            req.status = RequestStatus.READY
            req.is_clarified = True
            db.commit()

            updates["is_clarified"] = True
            updates["current_node"] = "jd_generation"
            updates["finalized_requirements"] = req.raw_requirements
            return updates

        # 等待用户回答
        req.status = RequestStatus.CLARIFYING
        req.clarification_round = current_round
        db.commit()

        _log_workflow(db, request_id, "requirement_collect", "awaiting_input", {
            "questions": questions,
            "round": current_round + 1,
        })

        # 设置人工干预标记
        updates["requires_human_intervention"] = True
        updates["human_action"] = "answer_clarification"
        updates["human_action_data"] = {"questions": questions, "round": current_round + 1}
        updates["current_node"] = "requirement_collect"
        return updates

    finally:
        db.close()


def submit_clarification(request_id: int, question_id: str, answer: str) -> dict:
    """提交澄清回答（人工操作触发）"""
    db = SessionLocal()
    try:
        req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()
        if not req:
            return {"error": "需求不存在"}

        if req.clarification_history is None:
            req.clarification_history = []

        history = list(req.clarification_history)
        history.append({"q": question_id, "a": answer, "round": req.clarification_round + 1})
        req.clarification_history = history
        req.clarification_round = req.clarification_round + 1
        db.commit()

        return {
            "clarification_round": req.clarification_round,
            "is_clarified": False,  # 继续下一轮
        }
    finally:
        db.close()


def node_jd_generation(state: RecruitmentState) -> dict:
    """节点：JD 生成 — AI 增强"""
    request_id = state["request_id"]

    db = SessionLocal()
    try:
        req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()
        if not req:
            return {"error": f"需求 {request_id} 不存在", "status": "terminated"}

        # 初始化向量库（可选：失败降级）
        try:
            vector_store.connect()
            seed_standard_jds()
        except Exception as e:
            logger.warning(f"向量库不可用，使用纯 AI 增强: {e}")

        # AI 增强 JD
        raw_jd = req.finalized_requirements or req.raw_requirements or ""
        try:
            enhancement = enhance_jd_with_rag(raw_jd)
        except Exception as e:
            logger.warning(f"AI 增强失败，使用原始需求: {e}")
            enhancement = {"enhanced_jd": raw_jd, "responsibilities": [], "requirements": []}

        enhanced_text = enhancement.get("enhanced_jd", raw_jd)

        # 创建 JD 版本
        import json
        jd = JobDescription(
            request_id=request_id,
            version=1,
            title=req.position_name,
            department=req.department,
            content=enhanced_text,
            original_content=raw_jd,
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

        _log_workflow(db, request_id, "jd_generation", "completed", {
            "jd_id": jd.id,
            "enhanced": True,
        })

        return {
            "jd_id": jd.id,
            "jd_status": "pending_review",
            "enhanced_jd_text": enhanced_text,
            "current_node": "jd_review",
            "requires_human_intervention": True,
            "human_action": "review_jd",
            "human_action_data": {
                "jd_id": jd.id,
                "enhanced_jd": enhanced_text,
            },
        }
    finally:
        db.close()


def node_jd_review(state: RecruitmentState) -> dict:
    """节点：JD 审核"""
    # 人工审核，更新状态
    action = state.get("human_action")
    data = state.get("human_action_data") or {}

    jd_id = state.get("jd_id")
    if not jd_id:
        return {"error": "JD ID 为空", "status": "terminated"}

    db = SessionLocal()
    try:
        jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        if not jd:
            return {"error": f"JD {jd_id} 不存在"}

        approved = data.get("approved", True)
        comment = data.get("review_comment", "")

        if approved:
            jd.status = JDStatus.APPROVED
            jd.review_comment = comment

            # 同步到向量库
            skills_str = (jd.required_skills or "") + "," + (jd.nice_to_have or "")
            try:
                vector_store.add_jd(
                    jd_id=jd.id,
                    jd_title=jd.title,
                    content=jd.content,
                    skills=skills_str,
                    industry=jd.department or "",
                    source="generated",
                )
                jd.vector_synced = True
            except Exception as e:
                logger.warning(f"JD {jd_id} 向量同步失败: {e}")
                jd.vector_synced = False

            db.commit()

            _log_workflow(db, state["request_id"], "jd_review", "completed", {
                "jd_id": jd_id, "approved": True,
            })

            return {
                "jd_status": "approved",
                "jd_vector_synced": jd.vector_synced,
                "current_node": "resume_collect",
                "requires_human_intervention": False,
            }
        else:
            jd.status = JDStatus.REJECTED
            jd.review_comment = comment
            db.commit()

            _log_workflow(db, state["request_id"], "jd_review", "completed", {
                "jd_id": jd_id, "approved": False,
            })

            # 退回 JD 生成阶段修改
            return {
                "jd_status": "rejected",
                "current_node": "jd_generation",
                "requires_human_intervention": False,
            }
    finally:
        db.close()


def _log_workflow(db, request_id, node, status, data=None):
    """记录工作流日志"""
    log = WorkflowLog(
        request_id=request_id,
        node=node,
        status=status,
        output_data=data,
    )
    db.add(log)
    db.commit()
