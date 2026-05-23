"""API 路由 — 面试管理"""
import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Interview, InterviewQuestion, InterviewEvaluation, Resume, ResumeStatus, JobDescription
from app.schemas import (
    InterviewCreate, InterviewResponse, InterviewQuestionResponse,
    InterviewEvaluationCreate, QuickPassRequest,
)
from app.services.resume_analyzer import generate_interview_questions

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interviews", tags=["面试管理"])


_ROUND_ORDER = ["first", "second", "third", "hr"]
_ROUND_LABELS = {"first": "一面", "second": "二面", "third": "三面", "hr": "HR面"}


@router.get("/pipeline")
def get_interview_pipeline(db: Session = Depends(get_db)):
    """面试流水线：按轮次分组返回各轮候选人，附带所有前序轮次评价"""
    from sqlalchemy import func
    rounds = _ROUND_ORDER
    labels = _ROUND_LABELS
    pipeline = []
    for r in rounds:
        items = db.query(Interview).filter(
            Interview.round == r
        ).order_by(Interview.created_at.desc()).all()

        interviews = []
        for item in items:
            iv = InterviewResponse.model_validate(item)
            iv_dict = iv.model_dump()

            # 获取候选人部门（通过简历 → JD）
            resume = db.query(Resume).filter(Resume.id == item.resume_id).first()
            department = None
            if resume and resume.jd_id:
                jd = db.query(JobDescription).filter(JobDescription.id == resume.jd_id).first()
                if jd:
                    department = jd.department
            iv_dict["department"] = department

            # 收集所有前序轮次的评价
            prev_evals = []
            curr_idx = _ROUND_ORDER.index(r)
            for pi in range(curr_idx):
                prev_round = _ROUND_ORDER[pi]
                prev = db.query(Interview).filter(
                    Interview.resume_id == item.resume_id,
                    Interview.round == prev_round,
                    Interview.status == "completed",
                ).order_by(Interview.created_at.desc()).first()
                if prev:
                    prev_eval = db.query(InterviewEvaluation).filter(
                        InterviewEvaluation.interview_id == prev.id
                    ).order_by(InterviewEvaluation.created_at.desc()).first()
                    if prev_eval:
                        prev_evals.append({
                            "round": prev_round,
                            "round_label": labels.get(prev_round, prev_round),
                            "evaluator": prev_eval.evaluator,
                            "tech_score": prev_eval.tech_score,
                            "communication_score": prev_eval.communication_score,
                            "overall_score": prev_eval.overall_score,
                            "strengths": prev_eval.strengths,
                            "weaknesses": prev_eval.weaknesses,
                            "conclusion": prev_eval.conclusion,
                            "recommendation": prev_eval.recommendation,
                        })
            if prev_evals:
                iv_dict["prev_evaluations"] = prev_evals
            interviews.append(iv_dict)

        pipeline.append({
            "round": r,
            "label": labels.get(r, r),
            "count": len(items),
            "interviews": interviews,
        })
    return {"pipeline": pipeline, "total": sum(p["count"] for p in pipeline)}


@router.get("")
def list_interviews(
    status: str | None = Query(None, description="筛选状态"),
    resume_id: int | None = Query(None),
    db: Session = Depends(get_db),
):
    """获取面试列表"""
    query = db.query(Interview)
    if status:
        query = query.filter(Interview.status == status)
    if resume_id:
        query = query.filter(Interview.resume_id == resume_id)
    items = query.order_by(Interview.created_at.desc()).all()
    return [InterviewResponse.model_validate(i) for i in items]


# ── 时间冲突检测 ──
def _check_time_conflict(data: InterviewCreate, db: Session, exclude_id: int | None = None) -> list[dict]:
    """检测候选人/面试官的时间冲突，返回冲突列表"""
    if not data.scheduled_at:
        return []
    conflicts = []
    start = data.scheduled_at
    end = data.scheduled_at + timedelta(minutes=data.duration_minutes or 60)
    # 统一为 offset-naive（数据库存的是 naive，前端可能带时区）
    if start.tzinfo is not None:
        start = start.replace(tzinfo=None)
        end = end.replace(tzinfo=None)

    # 冲突查询：已确认/进行中的面试，时间段重叠
    base_q = db.query(Interview).filter(
        Interview.status.in_(["confirmed", "completed"]),
    )
    if exclude_id:
        base_q = base_q.filter(Interview.id != exclude_id)

    active = base_q.all()
    for iv in active:
        if not iv.scheduled_at:
            continue
        iv_start = iv.scheduled_at
        iv_end = iv.scheduled_at + timedelta(minutes=iv.duration_minutes or 60)
        # 重叠判断：[start, end) vs [iv_start, iv_end)
        if start < iv_end and iv_start < end:
            # 候选人冲突
            if iv.resume_id == data.resume_id:
                conflicts.append({
                    "type": "candidate",
                    "message": f"该候选人在 {iv_start.strftime('%m/%d %H:%M')}~{iv_end.strftime('%H:%M')} 已有「{_ROUND_LABELS.get(iv.round.value, iv.round.value)}」面试",
                    "interview_id": iv.id,
                    "conflict_time": iv_start.isoformat(),
                })
            # 面试官冲突
            if iv.interviewer_name and iv.interviewer_name == data.interviewer_name:
                conflicts.append({
                    "type": "interviewer",
                    "message": f"面试官「{iv.interviewer_name}」在 {iv_start.strftime('%m/%d %H:%M')}~{iv_end.strftime('%H:%M')} 已有面试",
                    "interview_id": iv.id,
                    "conflict_time": iv_start.isoformat(),
                })
    return conflicts


@router.post("", response_model=InterviewResponse)
def create_interview(data: InterviewCreate, db: Session = Depends(get_db)):
    """安排面试 — 自动检测时间冲突"""
    resume = db.query(Resume).filter(Resume.id == data.resume_id).first()
    if not resume:
        raise HTTPException(404, "简历不存在")
    if resume.status != ResumeStatus.MANUAL_PASS:
        raise HTTPException(400, f"候选人「{resume.name or '未知'}」尚未通过人工审核（当前状态: {resume.status.value if hasattr(resume.status, 'value') else resume.status}），请先在简历管理中标记为人工通过")

    # ── 时间冲突检测 ──
    conflicts = _check_time_conflict(data, db)
    if conflicts:
        msgs = [c["message"] for c in conflicts]
        logger.warning(f"⛔ 时间冲突: {'; '.join(msgs)}")
        raise HTTPException(409, f"时间冲突: {'; '.join(msgs)}")
    # ──────────────────

    # ── 删除同候选人同轮次的待安排记录（避免重复） ──
    existing_pending = db.query(Interview).filter(
        Interview.resume_id == data.resume_id,
        Interview.round == data.round,
        Interview.status == "pending",
    ).all()
    for ep in existing_pending:
        db.delete(ep)
        logger.info(f"🗑️ 删除原待安排记录 id={ep.id} ({resume.name} - {data.round})")
    # ────────────────────────────────────────────────

    interview = Interview(
        resume_id=data.resume_id,
        jd_id=data.jd_id or resume.jd_id,
        round=data.round,
        interviewer_name=data.interviewer_name,
        interviewer_email=data.interviewer_email,
        candidate_name=resume.name or "未知",
        candidate_email=data.candidate_email,
        scheduled_at=data.scheduled_at or datetime.utcnow(),
        duration_minutes=data.duration_minutes,
        location=data.location,
        meeting_link=data.meeting_link,
        status="confirmed",
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    # ⭐ 推进筛选工作流 → interview_schedule
    try:
        from app.models import WorkflowStateDB
        jid = data.jd_id or resume.jd_id
        if jid:
            jd_obj = db.query(JobDescription).filter(JobDescription.id == jid).first()
            if jd_obj:
                ws = db.query(WorkflowStateDB).filter(
                    WorkflowStateDB.request_id == jd_obj.request_id,
                    WorkflowStateDB.workflow_type == "resume_screening",
                ).first()
                if ws and ws.current_node in ("candidate_pool", "resume_auto_screen"):
                    ws.current_node = "interview_schedule"
                    db.commit()
                    logger.info(f"✅ 筛选工作流推进: → interview_schedule (request={jd_obj.request_id})")
    except Exception as e:
        logger.warning(f"推进工作流失败: {e}")

    return InterviewResponse.model_validate(interview)


@router.get("/{interview_id}/questions", response_model=list[InterviewQuestionResponse])
def list_questions(interview_id: int, db: Session = Depends(get_db)):
    """获取面试题"""
    questions = db.query(InterviewQuestion).filter(
        InterviewQuestion.interview_id == interview_id
    ).all()
    return [InterviewQuestionResponse.model_validate(q) for q in questions]


@router.post("/{interview_id}/generate-questions")
def generate_questions(interview_id: int, db: Session = Depends(get_db)):
    """AI 生成面试题"""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(404, "面试不存在")

    resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()
    jd = None
    if interview.jd_id:
        jd = db.query(JobDescription).filter(JobDescription.id == interview.jd_id).first()

    resume_text = resume.raw_text if resume else ""
    jd_content = jd.content if jd else ""

    questions = generate_interview_questions(jd_content, resume_text)

    saved = []
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
        db.flush()
        saved.append(InterviewQuestionResponse.model_validate(question))

    db.commit()
    return saved


@router.post("/{interview_id}/evaluate")
def evaluate_interview(interview_id: int, data: InterviewEvaluationCreate,
                       db: Session = Depends(get_db)):
    """提交面试评价 — pass 自动创建下一轮"""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(404, "面试不存在")

    evaluation = InterviewEvaluation(
        interview_id=interview_id,
        evaluator=data.evaluator,
        tech_score=data.tech_score,
        communication_score=data.communication_score,
        overall_score=data.overall_score,
        strengths=data.strengths,
        weaknesses=data.weaknesses,
        conclusion=data.conclusion,
        recommendation=data.recommendation,
    )
    db.add(evaluation)

    interview.status = "completed"

    # ── pass → 自动创建下一轮面试（pending 状态） ──
    if data.recommendation == "pass":
        _create_next_round(db, interview)

    db.commit()

    # ⭐ 推进筛选工作流 → interview_execute
    try:
        from app.models import WorkflowStateDB, JobDescription
        jid = interview.jd_id or (db.query(Resume).filter(Resume.id == interview.resume_id).first().jd_id if interview.resume_id else None)
        if jid:
            jd_obj = db.query(JobDescription).filter(JobDescription.id == jid).first()
            if jd_obj:
                ws = db.query(WorkflowStateDB).filter(
                    WorkflowStateDB.request_id == jd_obj.request_id,
                    WorkflowStateDB.workflow_type == "resume_screening",
                ).first()
                if ws and ws.current_node in ("interview_schedule", "candidate_pool"):
                    ws.current_node = "interview_execute"
                    db.commit()
                    logger.info(f"✅ 筛选工作流推进: → interview_execute (request={jd_obj.request_id})")
    except Exception as e:
        logger.warning(f"推进工作流失败: {e}")

    # 返回下一轮信息
    next_round = _get_next_round_value(interview.round)
    return {
        "id": evaluation.id,
        "recommendation": data.recommendation,
        "next_round_created": next_round is not None,
        "next_round": next_round,
    }


def _get_next_round_value(current_round: str) -> str | None:
    """返回下一轮的值，如果是 hr 则返回 None（已到最后一轮）"""
    try:
        idx = _ROUND_ORDER.index(current_round)
        if idx < len(_ROUND_ORDER) - 1:
            return _ROUND_ORDER[idx + 1]
    except ValueError:
        pass
    return None


def _create_next_round(db: Session, current: Interview):
    """创建下一轮面试记录（pending 状态）"""
    next_round = _get_next_round_value(current.round)
    if not next_round:
        logger.info(f"面试 {current.id} 已是最后一轮（HR面），不再创建下一轮")
        return

    # 检查是否已有同轮次 pending/confirmed 记录，避免重复创建
    existing = db.query(Interview).filter(
        Interview.resume_id == current.resume_id,
        Interview.round == next_round,
        Interview.status.in_(["pending", "confirmed"]),
    ).first()
    if existing:
        logger.info(f"面试 {current.id} 的下一轮({next_round})已存在，跳过创建")
        return

    new_interview = Interview(
        resume_id=current.resume_id,
        jd_id=current.jd_id,
        round=next_round,
        candidate_name=current.candidate_name,
        candidate_email=current.candidate_email,
        candidate_phone=current.candidate_phone,
        status="pending",
    )
    db.add(new_interview)
    db.flush()
    logger.info(f"✅ 自动创建下一轮面试: {current.candidate_name} → {next_round} (id={new_interview.id})")


_RATING_TEMPLATES = {
    "excellent": {"tech_score": 90, "comm_score": 90, "overall": 90, "strengths": "表现优秀，技能扎实，沟通流畅"},
    "good":      {"tech_score": 75, "comm_score": 75, "overall": 75, "strengths": "表现良好，基本符合要求"},
    "average":   {"tech_score": 60, "comm_score": 60, "overall": 60, "strengths": "基础能力尚可，有提升空间"},
}


@router.post("/{interview_id}/quick-pass")
def quick_pass_interview(interview_id: int, data: QuickPassRequest = None,
                         db: Session = Depends(get_db)):
    """快速通过：接收评分等级，自动创建下一轮"""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(404, "面试不存在")
    if interview.status != "confirmed":
        raise HTTPException(400, "仅已安排的面试可通过")

    rating = _RATING_TEMPLATES.get(data.rating_level if data else "good", _RATING_TEMPLATES["good"])
    strengths = data.notes if data and data.notes else rating["strengths"]
    evaluator = data.evaluator if data and data.evaluator else "系统自动"

    evaluation = InterviewEvaluation(
        interview_id=interview_id,
        evaluator=evaluator,
        tech_score=rating["tech_score"],
        communication_score=rating["comm_score"],
        overall_score=rating["overall"],
        strengths=strengths,
        conclusion=strengths,
        recommendation="pass",
    )
    db.add(evaluation)
    interview.status = "completed"
    _create_next_round(db, interview)
    db.commit()

    next_round = _get_next_round_value(interview.round)
    logger.info(f"⚡ 快速通过面试 {interview_id}: {interview.candidate_name} [{data.rating_level if data else 'good'}] → 下一轮: {next_round or '无'}")
    return {
        "id": evaluation.id,
        "recommendation": "pass",
        "next_round_created": next_round is not None,
        "next_round": next_round,
    }


@router.post("/{interview_id}/ai-evaluation-draft")
def ai_evaluation_draft(interview_id: int, db: Session = Depends(get_db)):
    """AI 辅助生成面试评价草稿"""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(404, "面试不存在")

    resume = db.query(Resume).filter(Resume.id == interview.resume_id).first()
    jd = None
    if interview.jd_id:
        jd = db.query(JobDescription).filter(JobDescription.id == interview.jd_id).first()

    resume_text = (resume.raw_text or "")[:2000] if resume else ""
    jd_content = (jd.content or "")[:1000] if jd else ""
    questions = db.query(InterviewQuestion).filter(
        InterviewQuestion.interview_id == interview_id
    ).all()
    questions_text = "\n".join(
        f"Q{i+1}: {q.question_text}" for i, q in enumerate(questions[:5])
    ) if questions else "（未生成面试题）"

    prompt = f"""请根据以下信息，为这场面试生成一份评价草稿。

【岗位要求】
{jd_content}

【候选人简历】
{resume_text}

【面试题】
{questions_text}

请返回 JSON：
{{
    "tech_score": 0-100,
    "project_score": 0-100,
    "communication_score": 0-100,
    "teamwork_score": 0-100,
    "overall_score": 0-100,
    "strengths": "优势描述（50字以内）",
    "weaknesses": "待提升项（50字以内）",
    "conclusion": "面试结论（50字以内）",
    "recommendation": "pass 或 hold 或 reject"
}}
注意：tech_score 是技术深度，project_score 是项目经验，
communication_score 是沟通表达，teamwork_score 是团队协作。
根据候选人简历和岗位匹配度合理打分，不确定的项目打 70 分。"""

    from app.services.llm_service import call_llm_json
    draft = call_llm_json(prompt, timeout=120)
    return draft or {
        "tech_score": 70, "project_score": 70, "communication_score": 70,
        "teamwork_score": 70, "overall_score": 70,
        "strengths": "候选人具备基础能力", "weaknesses": "需进一步考察",
        "conclusion": "建议进入下一轮", "recommendation": "pass",
    }


@router.delete("/{interview_id}")
def delete_interview(interview_id: int, db: Session = Depends(get_db)):
    """删除面试"""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(404, "面试不存在")
    db.delete(interview)
    db.commit()
    logger.info(f"🗑️ 删除面试 id={interview_id}")
    return {"message": f"面试 {interview_id} 已删除"}


@router.get("/{interview_id}")
def get_interview(interview_id: int, db: Session = Depends(get_db)):
    """面试详情"""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(404, "面试不存在")

    questions = db.query(InterviewQuestion).filter(
        InterviewQuestion.interview_id == interview_id
    ).all()
    evaluations = db.query(InterviewEvaluation).filter(
        InterviewEvaluation.interview_id == interview_id
    ).all()

    return {
        "interview": InterviewResponse.model_validate(interview),
        "questions": [InterviewQuestionResponse.model_validate(q) for q in questions],
        "evaluations": [
            {
                "id": e.id,
                "evaluator": e.evaluator,
                "overall_score": e.overall_score,
                "recommendation": e.recommendation,
                "conclusion": e.conclusion,
            }
            for e in evaluations
        ],
    }
