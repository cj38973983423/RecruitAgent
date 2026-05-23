"""工作流图 — 简历筛选工作流 (Resume Screening)

流程: resume_collect → resume_auto_screen → candidate_pool
       → interview_schedule → interview_questions → interview_execute
       → interview_evaluate → offer_manage → onboarding
"""
import json
import logging
from typing import Optional

from app.workflows.state_v2 import ScreeningWorkflowState
from app.database import SessionLocal
from app.models import Resume, ResumeStatus, JobDescription, WorkflowLog
from app.services.resume_analyzer import analyze_resume_deep, ai_initial_screening
from app.services.resume_analyzer import ai_initial_screening
from app.services.llm_service import call_llm_json
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import StateGraph, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


# ══════════════════════════════════════════════
# 核心：自动评分 + 候选池
# ══════════════════════════════════════════════

def auto_score_resumes(request_id: int, jd_id: Optional[int] = None) -> dict:
    """⭐ 自动评分所有待评简历，更新候选池"""
    db = SessionLocal()
    try:
        # 获取所有未评分的简历
        pending = db.query(Resume).filter(
            Resume.ai_score.is_(None),
            Resume.raw_text.isnot(None),
        ).all()

        # 也获取已评分但不在候选池的简历（允许重新评分）
        existing = db.query(Resume).filter(
            Resume.ai_score.isnot(None),
            Resume.status.in_([ResumeStatus.PENDING, ResumeStatus.AI_PASS, ResumeStatus.AI_REJECT]),
        ).all()

        all_resumes = pending + existing

        if not all_resumes:
            return {"screened_count": 0, "candidate_pool": [], "screened_ids": [], "rejected_ids": []}

        # 获取 JD 内容做对比
        jd_content = ""
        jd_skills = []
        if jd_id:
            jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
            if jd:
                jd_content = jd.content or ""
                jd_skills = json.loads(jd.required_skills or "[]") if jd.required_skills else []

        screened_ids = []
        rejected_ids = []
        candidate_pool = []

        for resume in all_resumes:
            try:
                # 已有评分的直接用，不必再调 LLM
                if resume.ai_score is not None and resume.status in (ResumeStatus.AI_PASS, ResumeStatus.AI_REJECT):
                    score = resume.ai_score
                    if score >= 60:
                        candidate_pool.append({
                            "id": resume.id,
                            "name": resume.name or "未知",
                            "score": score,
                            "skills": json.loads(resume.skills) if resume.skills else [],
                            "education": resume.education or "",
                            "experience_years": resume.experience_years or 0,
                            "ai_reason": resume.ai_reason or "",
                            "file_name": resume.file_name or "",
                        })
                    continue

                # 未评分的：AI 评分
                screening = ai_initial_screening(resume.raw_text, jd_content, jd_skills)
                score = screening.get("score", 0)

                # 深度分析
                deep = analyze_resume_deep(resume.raw_text, jd_content)

                # 更新记录
                resume.ai_score = score
                resume.ai_score_detail = json.dumps(screening.get("score_detail", {}), ensure_ascii=False)
                resume.ai_reason = screening.get("recommendation", "") or screening.get("summary", "")
                resume.deep_analysis = deep

                # 风险过滤
                risk_warnings = deep.get("risk_warnings", [])
                frequent_change = deep.get("frequent_job_change", False)
                has_high_risk = any(w.get("severity") == "high" for w in risk_warnings if isinstance(w, dict))

                if has_high_risk or frequent_change:
                    resume.status = ResumeStatus.AI_REJECT
                    rejected_ids.append(resume.id)
                elif score >= 60:
                    resume.status = ResumeStatus.AI_PASS
                    resume.ai_recommended = (score >= 80)
                    screened_ids.append(resume.id)
                    candidate_pool.append({
                        "id": resume.id,
                        "name": resume.name or "未知",
                        "score": score,
                        "skills": json.loads(resume.skills) if resume.skills else [],
                        "education": resume.education or "",
                        "experience_years": resume.experience_years or 0,
                        "ai_reason": resume.ai_reason or "",
                        "file_name": resume.file_name or "",
                    })
                else:
                    resume.status = ResumeStatus.AI_REJECT
                    rejected_ids.append(resume.id)

            except Exception as e:
                logger.warning(f"简历 {resume.id} 评分失败: {e}")
                if resume.ai_score is None:
                    resume.ai_score = 0
                    resume.status = ResumeStatus.AI_REJECT
                    rejected_ids.append(resume.id)

        db.commit()
        db.close()

        # 候选池按分数降序
        candidate_pool.sort(key=lambda x: -x["score"])

        return {
            "screened_count": len(screened_ids),
            "rejected_count": len(rejected_ids),
            "candidate_pool": candidate_pool,
            "screened_ids": screened_ids,
            "rejected_ids": rejected_ids,
        }
    except Exception as e:
        db.close()
        logger.error(f"自动评分失败: {e}")
        return {"screened_count": 0, "candidate_pool": [], "screened_ids": [], "rejected_ids": [], "error": str(e)}


# ══════════════════════════════════════════════
# 节点函数
# ══════════════════════════════════════════════

def node_resume_collect(state: ScreeningWorkflowState) -> dict:
    """节点：简历收集 — 检测新简历并自动评分"""
    request_id = state["request_id"]
    jd_id = state.get("jd_id")

    db = SessionLocal()
    try:
        # 统计所有简历
        query = db.query(Resume)
        if jd_id:
            query = query.filter(Resume.jd_id == jd_id)
        total = query.count()
        pending_count = query.filter(Resume.ai_score.is_(None), Resume.raw_text.isnot(None)).count()

        if total == 0:
            return {
                "current_node": "resume_collect",
                "requires_human_intervention": True,
                "human_action": "upload_resumes",
                "human_action_data": {"jd_id": jd_id, "message": "请上传简历"},
                "pending_count": 0,
                "resume_ids": [],
            }

        # 有新简历 → 自动进入评分
        if pending_count > 0:
            _log(db, request_id, "resume_collect", "has_new_resumes", {"total": total, "pending": pending_count})
            return {
                "current_node": "resume_auto_screen",
                "requires_human_intervention": False,
                "pending_count": pending_count,
                "resume_ids": [r.id for r in query.all()],
            }

        # 所有简历已评分 → 进入候选池
        return {
            "current_node": "candidate_pool",
            "requires_human_intervention": False,
            "pending_count": 0,
        }
    finally:
        db.close()


def node_resume_auto_screen(state: ScreeningWorkflowState) -> dict:
    """节点：自动评分 — AI 评估所有待评简历"""
    request_id = state["request_id"]
    jd_id = state.get("jd_id")

    result = auto_score_resumes(request_id, jd_id)
    screened_ids = result.get("screened_ids", [])
    rejected_ids = result.get("rejected_ids", [])
    candidate_pool = result.get("candidate_pool", [])

    db = SessionLocal()
    try:
        _log(db, request_id, "resume_auto_screen", "completed", {
            "screened": len(screened_ids),
            "rejected": len(rejected_ids),
            "candidates": len(candidate_pool),
        })

        updates = {
            "ai_screened_ids": state.get("ai_screened_ids", []) + screened_ids,
            "ai_rejected_ids": state.get("ai_rejected_ids", []) + rejected_ids,
            "screened_count": state.get("screened_count", 0) + len(screened_ids),
            "candidate_pool": candidate_pool,
            "current_node": "candidate_pool",
            "requires_human_intervention": True,
            "human_action": "review_candidates",
            "human_action_data": {
                "candidates": candidate_pool,
                "total": len(candidate_pool),
                "rejected": len(rejected_ids),
            },
        }
        return updates
    finally:
        db.close()


def node_candidate_pool(state: ScreeningWorkflowState) -> dict:
    """节点：候选池 — 展示候选池，等待人工选择"""
    pool = state.get("candidate_pool", [])
    return {
        "current_node": "candidate_pool",
        "requires_human_intervention": True,
        "human_action": "select_candidates",
        "human_action_data": {
            "candidates": pool,
            "message": f"候选池有 {len(pool)} 人，选择进入面试的候选人",
        },
    }


def node_interview_schedule(state: ScreeningWorkflowState) -> dict:
    """节点：面试安排"""
    data = state.get("human_action_data") or {}
    return {
        "current_node": "interview_schedule",
        "requires_human_intervention": True,
        "human_action": "arrange_interviews",
        "human_action_data": data,
    }


def node_interview_questions(state: ScreeningWorkflowState) -> dict:
    """节点：面试题生成"""
    request_id = state["request_id"]
    data = state.get("human_action_data") or {}
    resume_ids = data.get("resume_ids", [])
    jd_title = state.get("jd_title", "")

    try:
        prompt = f"为岗位「{jd_title}」生成面试题（技术面），简历 ID: {resume_ids}"
        questions = call_llm_json(prompt, timeout=60)
    except Exception as e:
        questions = {"questions": [], "error": str(e)}

    db = SessionLocal()
    try:
        _log(db, request_id, "interview_questions", "completed", {"questions_count": len(questions.get("questions", []))})
    finally:
        db.close()

    next_node = "interview_execute" if questions.get("questions") else "interview_schedule"
    return {
        "current_node": next_node,
        "requires_human_intervention": False if questions.get("questions") else True,
        "human_action_data": {"questions": questions, "resume_ids": resume_ids},
    }


def node_interview_execute(state: ScreeningWorkflowState) -> dict:
    """节点：面试执行"""
    return {
        "current_node": "interview_execute",
        "requires_human_intervention": True,
        "human_action": "complete_interview",
    }


def node_interview_evaluate(state: ScreeningWorkflowState) -> dict:
    """节点：面试评估"""
    return {
        "current_node": "interview_evaluate",
        "requires_human_intervention": True,
        "human_action": "submit_evaluation",
    }


def node_offer_manage(state: ScreeningWorkflowState) -> dict:
    """节点：Offer 管理 — 等待 HR 发送 Offer 或候选人反馈"""
    data = state.get("human_action_data") or {}
    action = data.get("action", "")

    if action == "offer_sent":
        return {
            "current_node": "offer_manage",
            "requires_human_intervention": True,
            "human_action": "waiting_acceptance",
            "human_action_data": data,
            "offer_status": "sent",
        }
    elif action == "offer_accepted":
        return {
            "current_node": "onboarding",
            "requires_human_intervention": True,
            "human_action": "start_onboarding",
            "human_action_data": data,
            "offer_status": "accepted",
        }
    elif action == "offer_rejected":
        return {
            "current_node": "__end__",
            "requires_human_intervention": False,
            "human_action": "offer_rejected",
            "human_action_data": data,
            "offer_status": "rejected",
        }
    # 默认：等待 HR 操作（创建/发送 Offer）
    return {
        "current_node": "offer_manage",
        "requires_human_intervention": True,
        "human_action": "create_offer",
        "human_action_data": data,
        "offer_status": "draft",
    }


def node_onboarding(state: ScreeningWorkflowState) -> dict:
    """节点：入职跟进"""
    data = state.get("human_action_data") or {}
    action = data.get("action", "")

    if action == "onboarding_completed":
        return {
            "current_node": "__end__",
            "requires_human_intervention": False,
            "human_action": "completed",
            "onboarding_status": "completed",
        }

    return {
        "current_node": "onboarding",
        "requires_human_intervention": True,
        "human_action": "complete_onboarding",
        "onboarding_status": "pending",
    }


# ══════════════════════════════════════════════
# 公开 API
# ══════════════════════════════════════════════

def trigger_auto_score(request_id: int, jd_id: Optional[int] = None) -> dict:
    """⭐ 外部调用：触发简历自动评分（上传简历时调用）"""
    return auto_score_resumes(request_id, jd_id)


# ══════════════════════════════════════════════
# 构建图
# ══════════════════════════════════════════════

def build_screening_graph():
    if not LANGGRAPH_AVAILABLE:
        return None

    workflow = StateGraph(ScreeningWorkflowState)

    workflow.add_node("resume_collect", node_resume_collect)
    workflow.add_node("resume_auto_screen", node_resume_auto_screen)
    workflow.add_node("candidate_pool", node_candidate_pool)
    workflow.add_node("interview_schedule", node_interview_schedule)
    workflow.add_node("interview_questions", node_interview_questions)
    workflow.add_node("interview_execute", node_interview_execute)
    workflow.add_node("interview_evaluate", node_interview_evaluate)
    workflow.add_node("offer_manage", node_offer_manage)
    workflow.add_node("onboarding", node_onboarding)

    workflow.set_entry_point("resume_collect")

    # 路由
    workflow.add_conditional_edges("resume_collect",
        lambda s: "resume_auto_screen" if s.get("pending_count", 0) > 0
                  else "candidate_pool" if s.get("screened_count", 0) > 0
                  else "resume_collect")
    workflow.add_conditional_edges("resume_auto_screen", lambda s: "candidate_pool")
    workflow.add_conditional_edges("candidate_pool",
        lambda s: "interview_schedule" if s.get("human_action") == "select_candidates"
                  else "candidate_pool")
    workflow.add_conditional_edges("interview_schedule",
        lambda s: "interview_questions" if s.get("requires_human_intervention") == False
                  else "interview_schedule")
    workflow.add_conditional_edges("interview_questions",
        lambda s: "interview_execute")
    workflow.add_conditional_edges("interview_execute",
        lambda s: "interview_evaluate")
    workflow.add_conditional_edges("interview_evaluate",
        lambda s: "offer_manage")
    workflow.add_conditional_edges("offer_manage",
        lambda s: "onboarding" if s.get("human_action") == "offer_accepted" else "__end__"
        if s.get("human_action") == "offer_rejected" or s.get("offer_status") == "rejected"
        else "offer_manage")
    workflow.add_conditional_edges("onboarding",
        lambda s: "__end__")

    return workflow.compile()


def get_screening_graph_definition() -> dict:
    return {
        "nodes": [
            {"id": "resume_collect", "label": "简历收集", "type": "event"},
            {"id": "resume_auto_screen", "label": "AI自动评分", "type": "ai"},
            {"id": "candidate_pool", "label": "候选池(≥60分)", "type": "human"},
            {"id": "interview_schedule", "label": "面试安排", "type": "human"},
            {"id": "interview_questions", "label": "面试题生成", "type": "ai"},
            {"id": "interview_execute", "label": "面试执行", "type": "human"},
            {"id": "interview_evaluate", "label": "面试评估", "type": "human"},
            {"id": "offer_manage", "label": "Offer管理", "type": "human"},
            {"id": "onboarding", "label": "入职跟进", "type": "human"},
        ],
        "edges": [
            {"from": "resume_collect", "to": "resume_auto_screen", "label": "有新简历"},
            {"from": "resume_auto_screen", "to": "candidate_pool", "label": "评分完成"},
            {"from": "candidate_pool", "to": "interview_schedule", "label": "选择面试"},
            {"from": "interview_schedule", "to": "interview_questions", "label": "已排期"},
            {"from": "interview_questions", "to": "interview_execute", "label": "已出题"},
            {"from": "interview_execute", "to": "interview_evaluate", "label": "面试完成"},
            {"from": "interview_evaluate", "to": "offer_manage", "label": "推荐录用"},
            {"from": "offer_manage", "to": "onboarding", "label": "接受Offer"},
        ],
    }


def _log(db, request_id, node, status, data=None):
    log = WorkflowLog(request_id=request_id, node=node, status=status, output_data=data)
    db.add(log)
    db.commit()
