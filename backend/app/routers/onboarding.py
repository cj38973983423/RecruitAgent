"""入职管理 API 路由"""
import logging
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List

from app.database import get_db
from app.models import Offer, OfferStatus, Resume, ResumeStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


# ══════════════════════════════════════════════
# Schemas
# ══════════════════════════════════════════════


class OnboardingItem(BaseModel):
    """待入职/已入职候选人"""
    id: int
    candidate_name: str
    position_name: str
    department: str
    salary: str
    start_date: Optional[str] = None
    accepted_at: Optional[str] = None
    onboarded_at: Optional[str] = None
    status: str  # pending / completed
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class OnboardingCompleteRequest(BaseModel):
    """确认入职"""
    actual_start_date: Optional[str] = None
    notes: Optional[str] = None


# ══════════════════════════════════════════════
# Routes
# ══════════════════════════════════════════════


@router.get("/pending", response_model=List[dict])
def list_pending_onboarding(db: Session = Depends(get_db)):
    """查询待入职列表（Offer 已接受但未入职）"""
    offers = (
        db.query(Offer)
        .filter(Offer.status == OfferStatus.ACCEPTED)
        .order_by(Offer.accepted_at.desc())
        .all()
    )
    result = []
    for o in offers:
        result.append({
            "id": o.id,
            "resume_id": o.resume_id,
            "candidate_name": o.candidate_name,
            "position_name": o.position_name,
            "department": o.department,
            "salary": o.salary,
            "equity": o.equity,
            "start_date": o.start_date.isoformat() if o.start_date else None,
            "accepted_at": o.accepted_at.isoformat() if o.accepted_at else None,
            "onboarded_at": None,
            "status": "pending",
            "notes": o.notes,
        })
    return result


@router.get("/completed", response_model=List[dict])
def list_completed_onboarding(db: Session = Depends(get_db)):
    """查询已入职列表"""
    offers = (
        db.query(Offer)
        .filter(Offer.status == "onboarded")
        .order_by(Offer.updated_at.desc())
        .all()
    )
    result = []
    for o in offers:
        result.append({
            "id": o.id,
            "resume_id": o.resume_id,
            "candidate_name": o.candidate_name,
            "position_name": o.position_name,
            "department": o.department,
            "salary": o.salary,
            "equity": o.equity,
            "start_date": o.start_date.isoformat() if o.start_date else None,
            "accepted_at": o.accepted_at.isoformat() if o.accepted_at else None,
            "onboarded_at": o.updated_at.isoformat() if o.updated_at else None,
            "status": "completed",
            "notes": o.notes,
        })
    return result


@router.post("/{offer_id}/complete", response_model=dict)
def complete_onboarding(
    offer_id: int,
    body: OnboardingCompleteRequest = None,
    db: Session = Depends(get_db),
):
    """确认入职完成"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer 不存在")
    if offer.status != OfferStatus.ACCEPTED:
        raise HTTPException(status_code=400, detail=f"Offer 状态不是 ACCEPTED，当前: {offer.status}")

    # 更新入职信息
    offer.status = OfferStatus.ONBOARDED
    if body and body.actual_start_date:
        try:
            offer.start_date = datetime.fromisoformat(body.actual_start_date)
        except ValueError:
            pass
    if body and body.notes:
        old_notes = offer.notes or ""
        offer.notes = f"[入职完成] {body.notes}\n{old_notes}" if old_notes else f"[入职完成] {body.notes}"

    db.commit()

    logger.info(f"🎊 {offer.candidate_name} 已确认入职！")

    # ⭐ 推进筛选工作流 → onboarding
    try:
        from app.models import WorkflowStateDB, JobDescription
        if offer.jd_id:
            jd_obj = db.query(JobDescription).filter(JobDescription.id == offer.jd_id).first()
            if jd_obj:
                ws = db.query(WorkflowStateDB).filter(
                    WorkflowStateDB.request_id == jd_obj.request_id,
                    WorkflowStateDB.workflow_type == "resume_screening",
                ).first()
                if ws and ws.current_node in ("offer_manage", "interview_execute"):
                    ws.current_node = "onboarding"
                    ws.status = "completed"
                    db.commit()
                    logger.info(f"✅ 筛选工作流推进: → onboarding (request={jd_obj.request_id}) 工作流完成!")
    except Exception as e:
        logger.warning(f"推进工作流失败: {e}")

    return {
        "ok": True,
        "id": offer_id,
        "candidate_name": offer.candidate_name,
        "status": "onboarded",
    }


@router.delete("/{offer_id}")
def delete_onboarding_record(offer_id: int, db: Session = Depends(get_db)):
    """删除/撤销入职记录（待入职→回退到 ACCEPTED，已入职→回退到 ACCEPTED）"""
    offer = db.query(Offer).filter(Offer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer 不存在")
    if offer.status not in (OfferStatus.ACCEPTED, OfferStatus.ONBOARDED):
        raise HTTPException(status_code=400, detail=f"当前状态不支持删除: {offer.status}")

    candidate_name = offer.candidate_name
    # 回退到 ACCEPTED，移除入职完成标记
    offer.status = OfferStatus.ACCEPTED
    offer.updated_at = datetime.utcnow()
    db.commit()
    logger.info(f"🗑️ 入职记录已撤销: #{offer_id} ({candidate_name})")
    return {"ok": True, "id": offer_id, "candidate_name": candidate_name}
