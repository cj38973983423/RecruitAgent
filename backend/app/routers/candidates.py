"""候选人管理 API 路由 — 聚合简历 + 面试评价 + Offer 状态"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.models import (
    Resume, ResumeStatus, Interview, InterviewEvaluation,
    Offer, OfferStatus, InterviewRound, JobDescription,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/candidates", tags=["candidates"])

# ══════════════════════════════════════════════
# Schema
# ══════════════════════════════════════════════

from pydantic import BaseModel


class EvalSummary(BaseModel):
    round: str
    round_label: str
    evaluator: Optional[str] = None
    tech_score: Optional[float] = None
    communication_score: Optional[float] = None
    overall_score: Optional[float] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    conclusion: Optional[str] = None
    recommendation: Optional[str] = None
    created_at: Optional[str] = None


class InterviewSummary(BaseModel):
    id: int
    round: str
    round_label: str
    interviewer_name: Optional[str] = None
    status: str
    scheduled_at: Optional[str] = None
    meeting_link: Optional[str] = None
    evaluations: List[EvalSummary] = []


class OfferSummary(BaseModel):
    id: int
    salary: Optional[str] = None
    equity: Optional[str] = None
    status: str
    start_date: Optional[str] = None
    sent_at: Optional[str] = None
    accepted_at: Optional[str] = None


class CandidateDetail(BaseModel):
    """候选人完整信息"""
    id: int
    name: Optional[str] = None
    skills: Optional[str] = None
    experience_years: Optional[float] = None
    education: Optional[str] = None
    work_experience: Optional[str] = None
    ai_score: Optional[float] = None
    ai_recommended: bool = False
    ai_reason: Optional[str] = None
    deep_analysis: Optional[dict] = None
    status: str
    notes: Optional[str] = None
    jd_title: Optional[str] = None
    department: Optional[str] = None
    interviews: List[InterviewSummary] = []
    interviews_total: int = 0
    best_round: Optional[str] = None
    avg_score: Optional[float] = None
    offer: Optional[OfferSummary] = None
    offer_status: Optional[str] = None
    created_at: Optional[str] = None


class CandidateListResponse(BaseModel):
    total: int
    items: List[CandidateDetail]


# ══════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════

ROUND_LABELS = {
    "first": "一面", "second": "二面", "third": "三面", "hr": "HR面",
}
ROUND_ORDER = ["first", "second", "third", "hr"]


def _build_candidate(resume: Resume, db: Session) -> CandidateDetail:
    """聚合单个候选人的完整信息"""
    # JD 信息
    jd_title = None
    department = None
    if resume.jd_id:
        jd = db.query(JobDescription).filter(JobDescription.id == resume.jd_id).first()
        jd_title = jd.title if jd else None
        department = jd.department if jd else None

    # 面试 & 评价
    interviews = (
        db.query(Interview)
        .filter(Interview.resume_id == resume.id)
        .order_by(desc(Interview.created_at))
        .all()
    )

    interview_summaries = []
    total_scores = []
    best_round = None
    best_score = 0

    for iv in interviews:
        evals = (
            db.query(InterviewEvaluation)
            .filter(InterviewEvaluation.interview_id == iv.id)
            .order_by(InterviewEvaluation.created_at.desc())
            .all()
        )

        eval_list = []
        for e in evals:
            eval_list.append(EvalSummary(
                round=iv.round.value if hasattr(iv.round, 'value') else str(iv.round),
                round_label=ROUND_LABELS.get(
                    iv.round.value if hasattr(iv.round, 'value') else str(iv.round), ""
                ),
                evaluator=e.evaluator,
                tech_score=e.tech_score,
                communication_score=e.communication_score,
                overall_score=e.overall_score,
                strengths=e.strengths,
                weaknesses=e.weaknesses,
                conclusion=e.conclusion,
                recommendation=e.recommendation,
                created_at=e.created_at.isoformat() if e.created_at else None,
            ))
            if e.overall_score is not None:
                total_scores.append(e.overall_score)
                if e.overall_score > best_score:
                    best_score = e.overall_score
                    best_round = ROUND_LABELS.get(
                        iv.round.value if hasattr(iv.round, 'value') else str(iv.round), ""
                    )

        round_val = iv.round.value if hasattr(iv.round, 'value') else str(iv.round)
        interview_summaries.append(InterviewSummary(
            id=iv.id,
            round=round_val,
            round_label=ROUND_LABELS.get(round_val, ""),
            interviewer_name=iv.interviewer_name,
            status=iv.status.value if hasattr(iv.status, 'value') else str(iv.status),
            scheduled_at=iv.scheduled_at.isoformat() if iv.scheduled_at else None,
            meeting_link=iv.meeting_link,
            evaluations=eval_list,
        ))

    avg_score = round(sum(total_scores) / len(total_scores), 1) if total_scores else None

    # Offer
    offer = (
        db.query(Offer)
        .filter(Offer.resume_id == resume.id)
        .order_by(desc(Offer.created_at))
        .first()
    )
    offer_summary = None
    offer_status = None
    if offer:
        offer_summary = OfferSummary(
            id=offer.id,
            salary=offer.salary,
            equity=offer.equity,
            status=offer.status.value if hasattr(offer.status, 'value') else str(offer.status),
            start_date=offer.start_date.isoformat() if offer.start_date else None,
            sent_at=offer.sent_at.isoformat() if offer.sent_at else None,
            accepted_at=offer.accepted_at.isoformat() if offer.accepted_at else None,
        )
        offer_status = offer_summary.status

    return CandidateDetail(
        id=resume.id,
        name=resume.name,
        skills=resume.skills,
        experience_years=resume.experience_years,
        education=resume.education,
        work_experience=resume.work_experience,
        ai_score=resume.ai_score,
        ai_recommended=resume.ai_recommended or False,
        ai_reason=resume.ai_reason,
        deep_analysis=resume.deep_analysis,
        status=resume.status.value if hasattr(resume.status, 'value') else str(resume.status),
        notes=resume.notes,
        jd_title=jd_title,
        department=department,
        interviews=interview_summaries,
        interviews_total=len(interviews),
        best_round=best_round,
        avg_score=avg_score,
        offer=offer_summary,
        offer_status=offer_status,
        created_at=resume.created_at.isoformat() if resume.created_at else None,
    )


# ══════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════


@router.get("", response_model=CandidateListResponse)
def list_candidates(
    status: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    """查询候选人列表（已通过筛选，有面试记录的简历）"""
    # 默认只展示已通过筛选的候选人
    pool_statuses = [
        ResumeStatus.AI_PASS,
        ResumeStatus.MANUAL_PASS,
    ]

    q = db.query(Resume).filter(Resume.status.in_(pool_statuses))

    # 可选筛选
    if status:
        # 支持按简历状态筛选（如 manual_pass / ai_pass）
        resume_status_map = {
            "manual_pass": ResumeStatus.MANUAL_PASS,
            "ai_pass": ResumeStatus.AI_PASS,
            "ai_reject": ResumeStatus.AI_REJECT,
            "pending": ResumeStatus.PENDING,
        }
        if status in resume_status_map:
            q = q.filter(Resume.status == resume_status_map[status])
        elif status == "no_offer":
            # 无 Offer 的候选人（仅 manual_pass 可发 Offer）
            offered_ids = {o.resume_id for o in db.query(Offer.resume_id).all() if o.resume_id}
            q = q.filter(Resume.status == ResumeStatus.MANUAL_PASS)
            all_resumes = q.all()
            filtered = [r for r in all_resumes if r.id not in offered_ids]
            total = len(filtered)
            page_items = filtered[(page - 1) * page_size: page * page_size]
            items = [_build_candidate(r, db) for r in page_items]
            return CandidateListResponse(total=total, items=items)
        elif status == "has_offer":
            offered_ids = {o.resume_id for o in db.query(Offer.resume_id).all() if o.resume_id}
            all_resumes = q.all()
            filtered = [r for r in all_resumes if r.id in offered_ids]
            total = len(filtered)
            page_items = filtered[(page - 1) * page_size: page * page_size]
            items = [_build_candidate(r, db) for r in page_items]
            return CandidateListResponse(total=total, items=items)

    if search:
        q = q.filter(
            db.bindparam or Resume.name.ilike(f"%{search}%")
        )

    total = q.count()
    items = q.order_by(desc(Resume.updated_at)).offset((page - 1) * page_size).limit(page_size).all()

    return CandidateListResponse(
        total=total,
        items=[_build_candidate(r, db) for r in items],
    )


@router.get("/{candidate_id}", response_model=CandidateDetail)
def get_candidate_detail(candidate_id: int, db: Session = Depends(get_db)):
    """获取单个候选人完整信息"""
    resume = db.query(Resume).filter(Resume.id == candidate_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="候选人不存在")
    return _build_candidate(resume, db)


@router.get("/stats/summary")
def candidate_stats(db: Session = Depends(get_db)):
    """候选人统计"""
    from sqlalchemy import func

    pool_statuses = [ResumeStatus.AI_PASS, ResumeStatus.MANUAL_PASS]
    total_in_pool = db.query(func.count(Resume.id)).filter(
        Resume.status.in_(pool_statuses)
    ).scalar() or 0

    total_interviewed = db.query(func.count(
        db.query(Interview.resume_id)
        .distinct().subquery().c.resume_id
    )).scalar() if False else 0

    # 面试过的候选人（有面试记录的）
    interviewed_ids = {r[0] for r in db.query(Interview.resume_id).distinct().all() if r[0]}
    total_interviewed = len([r for r in db.query(Resume).filter(
        Resume.id.in_(interviewed_ids), Resume.status.in_(pool_statuses)
    ).all()])

    offered_count = db.query(func.count(Offer.id)).filter(
        Offer.status.in_([OfferStatus.SENT, OfferStatus.ACCEPTED, OfferStatus.ONBOARDED])
    ).scalar() or 0

    onboarded_count = db.query(func.count(Offer.id)).filter(
        Offer.status == OfferStatus.ONBOARDED
    ).scalar() or 0

    return {
        "total_in_pool": total_in_pool,
        "total_interviewed": total_interviewed,
        "offered_count": offered_count,
        "onboarded_count": onboarded_count,
    }


@router.delete("/{candidate_id}")
def remove_candidate_from_pool(candidate_id: int, db: Session = Depends(get_db)):
    """从候选人库移除（重置简历状态为 PENDING，保留数据）"""
    resume = db.query(Resume).filter(Resume.id == candidate_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="候选人不存在")
    if resume.status not in (ResumeStatus.AI_PASS, ResumeStatus.MANUAL_PASS):
        raise HTTPException(status_code=400, detail=f"该候选人不在候选人库中，当前状态: {resume.status}")

    resume.status = ResumeStatus.PENDING
    db.commit()
    logger.info(f"🗑️ 候选人 #{candidate_id} ({resume.name}) 已从候选人库移除")
    return {"ok": True, "id": candidate_id}
