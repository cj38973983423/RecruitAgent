"""API 路由 — 面试官库管理"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Interviewer, InterviewerStatus
from app.schemas import InterviewerCreate, InterviewerUpdate, InterviewerResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/interviewers", tags=["面试官库"])


@router.get("", response_model=list[InterviewerResponse])
def list_interviewers(
    status: str | None = Query(None, description="筛选：active / inactive"),
    keyword: str | None = Query(None, description="搜索关键字（姓名/部门/职位）"),
    db: Session = Depends(get_db),
):
    """获取面试官列表，支持按状态和关键字筛选"""
    query = db.query(Interviewer)
    if status:
        query = query.filter(Interviewer.status == status)
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(
            Interviewer.name.ilike(kw)
            | Interviewer.department.ilike(kw)
            | Interviewer.position.ilike(kw)
        )
    interviewers = query.order_by(Interviewer.created_at.desc()).all()
    return [InterviewerResponse.from_orm(i) for i in interviewers]


@router.get("/{interviewer_id}", response_model=InterviewerResponse)
def get_interviewer(interviewer_id: int, db: Session = Depends(get_db)):
    """获取单个面试官详情"""
    interviewer = db.query(Interviewer).filter(Interviewer.id == interviewer_id).first()
    if not interviewer:
        raise HTTPException(404, "面试官不存在")
    return InterviewerResponse.from_orm(interviewer)


@router.post("", response_model=InterviewerResponse)
def create_interviewer(data: InterviewerCreate, db: Session = Depends(get_db)):
    """新增面试官"""
    interviewer = Interviewer(
        name=data.name,
        email=data.email,
        phone=data.phone,
        position=data.position,
        department=data.department,
        skills=json.dumps(data.skills, ensure_ascii=False) if data.skills else None,
        notes=data.notes,
        status=InterviewerStatus.ACTIVE,
    )
    db.add(interviewer)
    db.commit()
    db.refresh(interviewer)
    logger.info(f"✅ 新增面试官: {interviewer.name} (id={interviewer.id})")
    return InterviewerResponse.from_orm(interviewer)


@router.put("/{interviewer_id}", response_model=InterviewerResponse)
def update_interviewer(interviewer_id: int, data: InterviewerUpdate, db: Session = Depends(get_db)):
    """更新面试官信息"""
    interviewer = db.query(Interviewer).filter(Interviewer.id == interviewer_id).first()
    if not interviewer:
        raise HTTPException(404, "面试官不存在")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "skills" and isinstance(value, list):
            setattr(interviewer, field, json.dumps(value, ensure_ascii=False))
        else:
            setattr(interviewer, field, value)

    db.commit()
    db.refresh(interviewer)
    logger.info(f"✅ 更新面试官: {interviewer.name} (id={interviewer.id})")
    return InterviewerResponse.from_orm(interviewer)


@router.delete("/{interviewer_id}")
def delete_interviewer(interviewer_id: int, db: Session = Depends(get_db)):
    """删除面试官"""
    interviewer = db.query(Interviewer).filter(Interviewer.id == interviewer_id).first()
    if not interviewer:
        raise HTTPException(404, "面试官不存在")
    db.delete(interviewer)
    db.commit()
    logger.info(f"🗑️ 删除面试官: {interviewer.name} (id={interviewer_id})")
    return {"message": f"面试官「{interviewer.name}」已删除"}


@router.post("/{interviewer_id}/toggle-status")
def toggle_interviewer_status(interviewer_id: int, db: Session = Depends(get_db)):
    """切换面试官状态（启用/停用）"""
    interviewer = db.query(Interviewer).filter(Interviewer.id == interviewer_id).first()
    if not interviewer:
        raise HTTPException(404, "面试官不存在")
    interviewer.status = (
        InterviewerStatus.INACTIVE
        if interviewer.status == InterviewerStatus.ACTIVE
        else InterviewerStatus.ACTIVE
    )
    db.commit()
    logger.info(f"🔄 切换面试官 {interviewer.name} 状态: {interviewer.status.value}")
    return {
        "id": interviewer.id,
        "status": interviewer.status.value,
    }
