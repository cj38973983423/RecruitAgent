"""Offer 管理 API 路由"""
import json
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Offer, OfferStatus, Resume, JobDescription, ResumeStatus, RecruitmentRequest
from app.schemas import OfferCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/offers", tags=["offers"])


# ══════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class OfferResponse(BaseModel):
    id: int
    resume_id: Optional[int] = None
    jd_id: Optional[int] = None
    candidate_name: str
    position_name: str
    department: str
    salary: str
    equity: Optional[str] = None
    start_date: Optional[datetime] = None
    status: str
    sent_at: Optional[datetime] = None
    accepted_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OfferSendRequest(BaseModel):
    """发送 Offer 请求"""
    start_date: Optional[str] = None  # ISO date string


class OfferAcceptRequest(BaseModel):
    """接受 Offer 请求"""
    accepted_start_date: Optional[str] = None


class OfferRejectRequest(BaseModel):
    """拒绝 Offer 请求"""
    reject_reason: Optional[str] = None


# ══════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════


def _check_jd_headcount_filled(jd_id: Optional[int], db: Session, resume_id: Optional[int] = None) -> None:
    """检查岗位的招聘名额是否已满（headcount=1 且已有有效Offer）"""
    # 如果 jd_id 没传，尝试从简历里捞
    if not jd_id and resume_id:
        resume = db.query(Resume).filter(Resume.id == resume_id).first()
        if resume and resume.jd_id:
            jd_id = resume.jd_id
    if not jd_id:
        return
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        return
    req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == jd.request_id).first()
    if not req or req.headcount != 1:
        return  # 只对招1人的岗位做限制
    # 统计该岗位下已有 已发送/已接受/已入职 的 Offer 数量
    # 包括 Offer.jd_id 直接匹配 + Offer.jd_id 为空但简历关联了该岗位的
    filled = db.query(Offer).filter(
        Offer.status.in_([OfferStatus.SENT, OfferStatus.ACCEPTED, OfferStatus.ONBOARDED]),
        (
            (Offer.jd_id == jd_id) |
            ((Offer.jd_id.is_(None)) & (Offer.resume_id.isnot(None)) & (
                db.query(Resume.jd_id).filter(
                    Resume.id == Offer.resume_id,
                    Resume.jd_id == jd_id,
                ).exists()
            ))
        ),
    ).count()
    if filled >= 1:
        raise HTTPException(
            status_code=400,
            detail=f"该岗位「{jd.title}」只招 {req.headcount} 人，已有 Offer 发出/接受/入职，不可再发 Offer",
        )


@router.post("", response_model=OfferResponse)
def create_offer(data: OfferCreate, db: Session = Depends(get_db)):
    """创建 Offer"""
    # ⭐ 校验岗位名额
    _check_jd_headcount_filled(data.jd_id, db, resume_id=data.resume_id)

    offer = Offer(
        resume_id=data.resume_id,
        jd_id=data.jd_id,
        candidate_name=data.candidate_name,
        position_name=data.position_name,
        department=data.department,
        salary=data.salary,
        equity=data.equity,
        start_date=data.start_date,
        notes=data.notes,
        status=OfferStatus.DRAFT,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    logger.info(f"✅ Offer 创建成功: ID={offer.id} for {data.candidate_name}")
    return offer


@router.get("", response_model=List[OfferResponse])
def list_offers(
    status: Optional[str] = None,
    resume_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """查询 Offer 列表"""
    q = db.query(Offer)
    if status:
        q = q.filter(Offer.status == status)
    if resume_id:
        q = q.filter(Offer.resume_id == resume_id)
    q = q.order_by(Offer.created_at.desc())
    return q.all()


@router.get("/{offer_id}", response_model=OfferResponse)
def get_offer(offer_id: int, db: Session = Depends(get_db)):
    """获取单个 Offer 详情"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer 不存在")
    return offer


@router.post("/{offer_id}/send", response_model=OfferResponse)
def send_offer(offer_id: int, body: OfferSendRequest = None, db: Session = Depends(get_db)):
    """发送 Offer → 状态变为 SENT"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer 不存在")
    if offer.status != OfferStatus.DRAFT:
        raise HTTPException(status_code=400, detail=f"Offer 状态不是 DRAFT，当前: {offer.status}")

    # ⭐ 校验岗位名额
    _check_jd_headcount_filled(offer.jd_id, db, resume_id=offer.resume_id)

    if body and body.start_date:
        try:
            offer.start_date = datetime.fromisoformat(body.start_date)
        except ValueError:
            pass

    offer.status = OfferStatus.SENT
    offer.sent_at = datetime.utcnow()
    db.commit()
    db.refresh(offer)

    # 同步更新简历状态
    if offer.resume_id:
        db.query(Resume).filter(Resume.id == offer.resume_id).update({"status": ResumeStatus.MANUAL_PASS})

    logger.info(f"📧 Offer #{offer_id} 已发送给 {offer.candidate_name}")

    # ⭐ 推进筛选工作流 → offer_manage
    try:
        from app.models import WorkflowStateDB, JobDescription
        if offer.jd_id:
            jd_obj = db.query(JobDescription).filter(JobDescription.id == offer.jd_id).first()
            if jd_obj:
                ws = db.query(WorkflowStateDB).filter(
                    WorkflowStateDB.request_id == jd_obj.request_id,
                    WorkflowStateDB.workflow_type == "resume_screening",
                ).first()
                if ws and ws.current_node in ("interview_execute", "interview_schedule", "candidate_pool"):
                    ws.current_node = "offer_manage"
                    db.commit()
                    logger.info(f"✅ 筛选工作流推进: → offer_manage (request={jd_obj.request_id})")
    except Exception as e:
        logger.warning(f"推进工作流失败: {e}")

    return offer


@router.post("/{offer_id}/accept", response_model=OfferResponse)
def accept_offer(offer_id: int, body: OfferAcceptRequest = None, db: Session = Depends(get_db)):
    """候选人接受 Offer"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer 不存在")
    if offer.status not in (OfferStatus.SENT, OfferStatus.DRAFT):
        raise HTTPException(status_code=400, detail=f"Offer 无法被接受，当前状态: {offer.status}")

    if body and body.accepted_start_date:
        try:
            offer.start_date = datetime.fromisoformat(body.accepted_start_date)
        except ValueError:
            pass

    offer.status = OfferStatus.ACCEPTED
    offer.accepted_at = datetime.utcnow()
    db.commit()
    db.refresh(offer)

    logger.info(f"🎉 Offer #{offer_id} 已被 {offer.candidate_name} 接受")
    return offer


@router.post("/{offer_id}/reject", response_model=OfferResponse)
def reject_offer(offer_id: int, body: OfferRejectRequest = None, db: Session = Depends(get_db)):
    """候选人拒绝 Offer"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer 不存在")
    if offer.status not in (OfferStatus.SENT, OfferStatus.DRAFT):
        raise HTTPException(status_code=400, detail=f"Offer 无法被拒绝，当前状态: {offer.status}")

    reason = body.reject_reason if body else None
    if reason:
        old_notes = offer.notes or ""
        offer.notes = f"[拒绝原因] {reason}\n{old_notes}" if old_notes else f"[拒绝原因] {reason}"

    offer.status = OfferStatus.REJECTED
    offer.rejected_at = datetime.utcnow()
    db.commit()
    db.refresh(offer)

    logger.info(f"😢 Offer #{offer_id} 被 {offer.candidate_name} 拒绝{'：' + reason if reason else ''}")
    return offer


@router.post("/{offer_id}/withdraw", response_model=OfferResponse)
def withdraw_offer(offer_id: int, db: Session = Depends(get_db)):
    """撤回 Offer"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer 不存在")
    if offer.status not in (OfferStatus.DRAFT, OfferStatus.SENT):
        raise HTTPException(status_code=400, detail=f"Offer 无法被撤回，当前状态: {offer.status}")

    offer.status = OfferStatus.WITHDRAWN
    db.commit()
    db.refresh(offer)

    logger.info(f"↩️ Offer #{offer_id} 已撤回")
    return offer


@router.delete("/{offer_id}")
def delete_offer(offer_id: int, db: Session = Depends(get_db)):
    """删除 Offer（可删除任意状态的 Offer）"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer 不存在")

    candidate_name = offer.candidate_name
    db.delete(offer)
    db.commit()
    logger.info(f"🗑️ Offer #{offer_id} ({candidate_name}) 已删除")
    return {"ok": True, "id": offer_id}
