"""工作流节点 — 面试安排 + 面试题生成 + 面试执行 + Offer + 入职"""
import json
import logging
from datetime import datetime
from app.workflows.state import RecruitmentState
from app.services.resume_analyzer import generate_interview_questions
from app.database import SessionLocal
from app.models import (
    Resume, JobDescription, Interview, InterviewQuestion,
    InterviewEvaluation, Offer, WorkflowLog,
    InterviewRound, InterviewStatus, OfferStatus,
)

logger = logging.getLogger(__name__)


def node_interview_schedule(state: RecruitmentState) -> dict:
    """节点：面试安排 — 协调面试官和候选人时间"""
    request_id = state["request_id"]

    db = SessionLocal()
    try:
        passed_ids = state.get("manual_passed_ids", []) or state.get("ai_screened_ids", [])

        if not passed_ids:
            _log_workflow(db, request_id, "interview_schedule", "no_candidates", {})
            return {"current_node": "completed"}

        _log_workflow(db, request_id, "interview_schedule", "awaiting_schedule", {
            "candidates_count": len(passed_ids),
        })

        return {
            "current_node": "interview_schedule",
            "requires_human_intervention": True,
            "human_action": "arrange_interviews",
            "human_action_data": {
                "candidate_ids": passed_ids,
                "message": "请为以下候选人安排面试时间",
            },
        }
    finally:
        db.close()


def create_interview(request_id: int, resume_id: int,
                     interviewer_name: str, scheduled_at: datetime,
                     jd_id: int | None = None) -> dict:
    """创建并保存面试记录"""
    db = SessionLocal()
    try:
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if not resume:
            return {"error": "简历不存在"}

        interview = Interview(
            resume_id=resume_id,
            jd_id=jd_id or resume.jd_id,
            round=InterviewRound.FIRST,
            interviewer_name=interviewer_name,
            candidate_name=resume.name or "未知",
            scheduled_at=scheduled_at,
            status=InterviewStatus.CONFIRMED,
        )
        db.add(interview)
        db.commit()
        db.refresh(interview)

        _log_workflow(db, request_id, "interview_schedule", "scheduled", {
            "interview_id": interview.id, "resume_id": resume_id,
        })

        return {"interview_id": interview.id}
    finally:
        db.close()


def node_interview_questions(state: RecruitmentState) -> dict:
    """节点：面试题生成 — AI 生成"""
    request_id = state["request_id"]
    interview_id = state.get("current_interview_id")

    if not interview_id:
        # 没有指定面试，为所有已安排的面试生成
        interview_ids = state.get("interview_ids", [])
        if not interview_ids:
            return {"current_node": "interview_execute"}
        interview_id = interview_ids[0]

    db = SessionLocal()
    try:
        interview = db.query(Interview).filter(Interview.id == interview_id).first()
        if not interview:
            return {"error": f"面试 {interview_id} 不存在"}

        # 获取简历和 JD
        resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()
        jd = None
        if interview.jd_id:
            jd = db.query(JobDescription).filter(JobDescription.id == interview.jd_id).first()

        resume_text = resume.raw_text if resume else ""
        jd_content = jd.content if jd else ""

        # AI 生成面试题
        questions = generate_interview_questions(jd_content, resume_text)

        # 保存到数据库
        for q in questions:
            question = InterviewQuestion(
                interview_id=interview_id,
                category=q.get("category", "tech"),
                difficulty=q.get("difficulty", "intermediate"),
                question_text=q.get("question", ""),
                expected_answer=q.get("expected_answer", ""),
                created_by="ai",
            )
            db.add(question)

        db.commit()

        # 更新面试状态
        interview.status = InterviewStatus.CONFIRMED
        db.commit()

        _log_workflow(db, request_id, "interview_questions", "completed", {
            "interview_id": interview_id,
            "questions_count": len(questions),
        })

        return {
            "current_node": "interview_execute",
            "requires_human_intervention": True,
            "human_action": "conduct_interview",
            "human_action_data": {
                "interview_id": interview_id,
                "questions_count": len(questions),
            },
        }
    finally:
        db.close()


def node_interview_execute(state: RecruitmentState) -> dict:
    """节点：面试执行 — 记录面试过程"""
    action = state.get("human_action")
    data = state.get("human_action_data") or {}

    interview_id = data.get("interview_id") or state.get("current_interview_id")

    db = SessionLocal()
    try:
        if action == "complete_interview":
            # 面试完成，记录
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            if interview:
                interview.status = InterviewStatus.COMPLETED
                interview.notes = data.get("notes", interview.notes or "")
                db.commit()

            _log_workflow(db, state["request_id"], "interview_execute", "completed", {
                "interview_id": interview_id,
            })

            return {
                "current_node": "interview_evaluate",
                "requires_human_intervention": True,
                "human_action": "evaluate_interview",
                "human_action_data": {"interview_id": interview_id},
            }

        # 等待面试执行
        return {
            "current_node": "interview_execute",
            "requires_human_intervention": True,
            "human_action": "conduct_interview",
            "human_action_data": {"interview_id": interview_id},
        }
    finally:
        db.close()


def node_interview_evaluate(state: RecruitmentState) -> dict:
    """节点：面试评估 — 汇总评价"""
    action = state.get("human_action")
    data = state.get("human_action_data") or {}

    db = SessionLocal()
    try:
        if action == "submit_evaluation":
            interview_id = data.get("interview_id")
            evaluation = InterviewEvaluation(
                interview_id=interview_id,
                evaluator=data.get("evaluator", ""),
                tech_score=data.get("tech_score", 0),
                communication_score=data.get("communication_score", 0),
                overall_score=data.get("overall_score", 0),
                strengths=data.get("strengths", ""),
                weaknesses=data.get("weaknesses", ""),
                conclusion=data.get("conclusion", ""),
                recommendation=data.get("recommendation", "hold"),
            )
            db.add(evaluation)
            db.commit()

            # 更新简历状态
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            if interview and data.get("recommendation") == "pass":
                resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()
                if resume:
                    resume.status = "interviewing"
                db.commit()

            _log_workflow(db, state["request_id"], "interview_evaluate", "completed", {
                "interview_id": interview_id,
                "recommendation": data.get("recommendation"),
            })

            # 检查是否还有下一轮面试
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            if interview:
                round_num = interview.round
                # 假设最多 3 轮
                if round_num.value in ("first", "second") and data.get("recommendation") == "pass":
                    # 安排下一轮
                    return {
                        "interview_round_count": state.get("interview_round_count", 0) + 1,
                        "current_node": "interview_schedule",
                        "requires_human_intervention": True,
                        "human_action": "arrange_next_round",
                        "human_action_data": {
                            "resume_id": interview.resume_id,
                            "next_round": round_num,
                            "message": "候选人通过当前轮次，请安排下一轮面试",
                        },
                    }

            # 面试通过，进入 Offer
            return {
                "current_node": "offer_manage",
                "requires_human_intervention": True,
                "human_action": "prepare_offer",
                "human_action_data": {
                    "interview_id": interview_id,
                },
            }

        # 等待评估提交
        return {
            "current_node": "interview_evaluate",
            "requires_human_intervention": True,
            "human_action": "evaluate_interview",
            "human_action_data": {"interview_id": state.get("current_interview_id")},
        }
    finally:
        db.close()


def node_offer_manage(state: RecruitmentState) -> dict:
    """节点：Offer 管理"""
    action = state.get("human_action")
    data = state.get("human_action_data") or {}

    db = SessionLocal()
    try:
        if action == "send_offer":
            candidate_id = data.get("resume_id")
            resume = db.query(Resume).filter(Resume.id == candidate_id).first()

            offer = Offer(
                resume_id=candidate_id,
                jd_id=state.get("jd_id"),
                candidate_name=data.get("candidate_name", resume.name if resume else ""),
                position_name=data.get("position_name", ""),
                department=data.get("department", ""),
                salary=data.get("salary", ""),
                equity=data.get("equity"),
                start_date=data.get("start_date"),
                status=OfferStatus.SENT,
                notes=data.get("notes", ""),
            )
            db.add(offer)
            db.commit()
            db.refresh(offer)

            # 更新简历状态
            if resume:
                resume.status = "offered"
                db.commit()

            _log_workflow(db, state["request_id"], "offer_manage", "sent", {
                "offer_id": offer.id,
            })

            return {
                "offer_id": offer.id,
                "offer_status": "sent",
                "current_node": "offer_manage",
                "requires_human_intervention": True,
                "human_action": "track_offer_response",
                "human_action_data": {"offer_id": offer.id},
            }

        elif action == "offer_accepted":
            offer_id = data.get("offer_id")
            offer = db.query(Offer).filter(Offer.id == offer_id).first()
            if offer:
                offer.status = OfferStatus.ACCEPTED
                offer.accepted_at = datetime.utcnow()
                # 更新简历
                resume = db.query(Resume).filter(Resume.id == offer.resume_id).first()
                if resume:
                    resume.status = "hired"
                db.commit()

            return {
                "offer_status": "accepted",
                "current_node": "onboarding",
                "requires_human_intervention": True,
                "human_action": "start_onboarding",
                "human_action_data": {"offer_id": offer_id},
            }

        return {
            "current_node": "offer_manage",
            "requires_human_intervention": True,
            "human_action": "prepare_offer",
        }
    finally:
        db.close()


def node_onboarding(state: RecruitmentState) -> dict:
    """节点：入职跟进"""
    action = state.get("human_action")
    data = state.get("human_action_data") or {}

    tasks = list(state.get("onboarding_tasks", []))
    if action == "complete_onboarding":
        tasks.append("onboarding_completed")
        return {
            "onboarding_status": "completed",
            "onboarding_tasks": tasks,
            "current_node": "completed",
            "status": "completed",
        }

    # 入职任务清单
    default_tasks = [
        "背调检查",
        "体检提醒",
        "入职材料收集（身份证、学历证明等）",
        "IT 账号开通",
        "工位安排",
        "入职培训安排",
    ]

    _log_workflow(db, state["request_id"], "onboarding", "in_progress", {
        "tasks": default_tasks,
    })

    return {
        "onboarding_status": "in_progress",
        "onboarding_tasks": default_tasks,
        "current_node": "onboarding",
        "requires_human_intervention": True,
        "human_action": "complete_onboarding",
        "human_action_data": {"tasks": default_tasks},
    }
