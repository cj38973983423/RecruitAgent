"""API 路由 — JD 管理 + AI 增强 + 重新生成"""

import json
import logging
import threading
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models import JobDescription, JDStatus
from app.schemas import JDCreate, JDEnhanceRequest, JDReviewRequest, JDResponse
from app.services.jd_service import enhance_jd_with_rag, regenerate_jd_with_hints, get_standard_jd_by_title

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/jds", tags=["JD管理"])


class JDRegenerateRequest(BaseModel):
    modification_hints: str = ""


class JDSaveContentRequest(BaseModel):
    content: str


def _background_regenerate(jd_id: int, hints: str):
    """后台线程：严格按修改建议重新生成 JD"""
    db = SessionLocal()
    try:
        logger.info(f"🔄 后台开始重新生成 JD {jd_id}...")
        jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        if not jd:
            logger.error(f"JD {jd_id} 不存在，放弃重新生成")
            return

        # 使用严格修改模式
        enhancement = regenerate_jd_with_hints(jd.content, hints)
        enhanced_text = enhancement.get("enhanced_jd", jd.content)

        jd.content = enhanced_text
        jd.enhancement_log = enhancement
        jd.status = JDStatus.PENDING_REVIEW
        jd.review_comment = hints

        if enhancement.get("responsibilities"):
            jd.responsibilities = json.dumps(enhancement["responsibilities"], ensure_ascii=False)
        if enhancement.get("requirements"):
            jd.requirements_list = json.dumps(enhancement["requirements"], ensure_ascii=False)

        db.commit()
        logger.info(f"✅ 后台重新生成 JD {jd_id} 完成")
    except Exception as e:
        logger.error(f"❌ 后台重新生成 JD {jd_id} 失败: {e}")
        try:
            jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
            if jd and jd.status == JDStatus.REGENERATING:
                jd.status = JDStatus.PENDING_REVIEW
                jd.review_comment = f"重新生成失败: {str(e)[:200]}"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post("", response_model=JDResponse)
def create_jd(jd: JDCreate, db: Session = Depends(get_db)):
    """创建 JD"""
    db_jd = JobDescription(
        request_id=jd.request_id,
        title=jd.title,
        department=jd.department,
        location=jd.location,
        content=jd.content,
        required_skills=jd.required_skills,
        nice_to_have=jd.nice_to_have,
        experience_required=jd.experience_required,
        education_required=jd.education_required,
        status=JDStatus.DRAFT,
    )
    db.add(db_jd)
    db.commit()
    db.refresh(db_jd)
    return JDResponse.model_validate(db_jd)


@router.post("/enhance")
def enhance_jd(request: JDEnhanceRequest, db: Session = Depends(get_db)):
    """AI 增强 JD"""
    jd = db.query(JobDescription).filter(JobDescription.id == request.jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD 不存在")

    enhancement = enhance_jd_with_rag(jd.content, additional_context=request.additional_context or "")
    jd.content = enhancement.get("enhanced_jd", jd.content)
    jd.enhancement_log = enhancement

    if enhancement.get("responsibilities"):
        jd.responsibilities = json.dumps(enhancement["responsibilities"], ensure_ascii=False)
    if enhancement.get("requirements"):
        jd.requirements_list = json.dumps(enhancement["requirements"], ensure_ascii=False)

    db.commit()
    return enhancement


@router.post("/{jd_id}/review")
def review_jd(jd_id: int, review: JDReviewRequest, db: Session = Depends(get_db)):
    """审核 JD"""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD 不存在")

    jd.status = JDStatus.APPROVED if review.approved else JDStatus.REJECTED
    jd.review_comment = review.review_comment
    jd.reviewed_by = review.reviewed_by
    db.commit()

    return {"jd_id": jd.id, "status": jd.status.value, "approved": review.approved}


@router.post("/{jd_id}/regenerate")
def regenerate_jd(jd_id: int, req_data: JDRegenerateRequest, db: Session = Depends(get_db)):
    """重新生成 JD（后台执行，立即返回），状态设为 REGENERATING"""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD 不存在")
    if jd.status == JDStatus.REGENERATING:
        raise HTTPException(status_code=400, detail="该 JD 正在重新生成中，请稍候")

    hints = req_data.modification_hints or ""

    # 立即标记为 REGENERATING，前端能立刻看到状态变化
    jd.status = JDStatus.REGENERATING
    jd.review_comment = hints
    db.commit()

    # 后台线程执行 AI 生成
    thread = threading.Thread(target=_background_regenerate, args=(jd_id, hints), daemon=True)
    thread.start()

    logger.info(f"🔄 已启动后台重新生成 JD {jd_id}")

    return {
        "jd_id": jd.id,
        "status": "regenerating",
        "message": "🔄 AI 正在重新生成中，请稍候...",
    }


@router.put("/{jd_id}/content")
def save_jd_content(jd_id: int, req_data: JDSaveContentRequest, db: Session = Depends(get_db)):
    """保存手动编辑的 JD 内容"""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD 不存在")
    if jd.status == JDStatus.REGENERATING:
        raise HTTPException(status_code=400, detail="JD 正在重新生成中，请稍候")

    jd.content = req_data.content
    if jd.status not in (JDStatus.PENDING_REVIEW, JDStatus.REJECTED):
        jd.status = JDStatus.PENDING_REVIEW
    db.commit()

    logger.info(f"💾 已保存 JD {jd_id} 的手动编辑")
    return {
        "jd_id": jd.id,
        "status": jd.status.value,
        "message": "✅ JD 内容已保存",
    }


@router.get("/standard/{job_title}")
def search_standard_jds(job_title: str):
    """搜索标准 JD（从 Milvus 向量库）"""
    results = get_standard_jd_by_title(job_title)
    return {"results": results}


@router.get("")
def list_jds(request_id: int = None, status: str = None, db: Session = Depends(get_db)):
    """JD 列表，支持按 request_id 和 status 筛选"""
    query = db.query(JobDescription)
    if request_id:
        query = query.filter(JobDescription.request_id == request_id)
    if status:
        query = query.filter(JobDescription.status == status)
    jds = query.order_by(JobDescription.created_at.desc()).all()
    return [JDResponse.model_validate(j) for j in jds]


@router.delete("/{jd_id}")
def delete_jd(jd_id: int, db: Session = Depends(get_db)):
    """删除指定 JD"""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail=f"JD {jd_id} 不存在")
    db.delete(jd)
    db.commit()
    logger.info(f"🗑️ 已删除 JD id={jd_id}")
    return {"message": f"JD {jd_id} 已删除", "jd_id": jd_id}
