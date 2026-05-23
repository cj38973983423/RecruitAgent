"""API 路由 — 简历管理 + AI 分析"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import Resume, ResumeStatus, JobDescription
from app.schemas import ResumeResponse, ResumeBatchAction
from app.services.storage import save_upload_file, extract_text
from app.services.resume_analyzer import analyze_resume_deep, ai_initial_screening
from app.services.llm_service import call_llm_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/resumes", tags=["简历管理"])


class UpdateResumeJDInput(BaseModel):
    jd_id: Optional[int] = None


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...), jd_id: Optional[int] = Form(None),
                        db: Session = Depends(get_db)):
    """上传简历"""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""
    if ext not in ("pdf", "docx", "doc"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 和 DOCX 格式")

    path = await save_upload_file(file)

    resume = Resume(
        file_path=path, file_name=file.filename, file_type=ext,
        status=ResumeStatus.PENDING, jd_id=jd_id,
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)

    # 解析文档 → AI 结构化提取
    try:
        raw_text = extract_text(path, ext)
        if not raw_text:
            logger.warning(f"文件解析返回空: {file.filename}")
            db.commit()
            return {"id": resume.id, "file_name": resume.file_name, "raw_text": ""}

        resume.raw_text = raw_text
        parsed = call_llm_json(
            f"解析简历，返回 JSON: name, skills[], experience_years, education, work_experience, summary\n\n简历：{raw_text[:3000]}"
        )
        if parsed:
            resume.name = parsed.get("name")
            skills = parsed.get("skills", [])
            resume.skills = json.dumps(skills, ensure_ascii=False) if skills else None
            resume.experience_years = parsed.get("experience_years")
            # 序列化 JSON 字段（LLM 返回 dict/list，SQLite 需要字符串）
            edu = parsed.get("education")
            if edu and isinstance(edu, (dict, list)):
                resume.education = json.dumps(edu, ensure_ascii=False)
            elif isinstance(edu, str):
                resume.education = edu
            work = parsed.get("work_experience")
            if work and isinstance(work, (dict, list)):
                resume.work_experience = json.dumps(work, ensure_ascii=False)
            elif isinstance(work, str):
                resume.work_experience = work
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"简历解析失败: {e}", exc_info=True)

    db.commit()
    resume_id = resume.id
    file_name = resume.file_name

    # ⭐ 后台异步跑 AI 评分 + 深度分析（避免上传卡死）
    import threading
    def _process_resume_async(rid: int, jid: Optional[int]):
        from app.database import SessionLocal
        session = SessionLocal()
        try:
            r = session.query(Resume).filter(Resume.id == rid).first()
            if not r or not r.raw_text:
                return

            jd_content = ""
            jd_skills = []
            if jid:
                from app.models import JobDescription
                jd = session.query(JobDescription).filter(JobDescription.id == jid).first()
                if jd:
                    jd_content = jd.content or ""
                    jd_skills = json.loads(jd.required_skills or "[]") if jd.required_skills else []

            # 深度分析
            try:
                deep = analyze_resume_deep(r.raw_text, jd_content)
                r.deep_analysis = deep
            except Exception as e:
                logger.warning(f"深度分析失败 (rid={rid}): {e}")

            # AI 初筛评分
            try:
                screening = ai_initial_screening(r.raw_text, jd_content, jd_skills)
                r.ai_score = screening.get("score", 0)
                r.ai_score_detail = json.dumps(screening.get("score_detail", {}), ensure_ascii=False)
                r.ai_reason = screening.get("recommendation", "")
                r.ai_recommended = (screening.get("score", 0) >= 60)
                r.status = ResumeStatus.AI_PASS if r.ai_recommended else ResumeStatus.AI_REJECT
            except Exception as e:
                logger.warning(f"AI 评分失败 (rid={rid}): {e}")

            session.commit()
            logger.info(f"✅ 后台处理完成 rid={rid} status={r.status}")

            # ⭐ 推进筛选工作流
            try:
                from app.models import JobDescription, WorkflowStateDB

                # 通过 JD 找到 request_id
                if jid:
                    jd = session.query(JobDescription).filter(JobDescription.id == jid).first()
                    if jd:
                        req_id = jd.request_id
                        ws = session.query(WorkflowStateDB).filter(
                            WorkflowStateDB.request_id == req_id,
                            WorkflowStateDB.workflow_type == "resume_screening",
                        ).first()
                        if ws and ws.current_node == "resume_collect":
                            # 推进到 AI 自动评分节点
                            ws.current_node = "resume_auto_screen"
                            ws.status = "running"
                            session.commit()
                            logger.info(f"✅ 筛选工作流已推进: resume_collect → resume_auto_screen (request={req_id})")

                            # 检查是否所有简历都已评分 → 推进到候选池
                            total_resumes = session.query(Resume).filter(
                                Resume.jd_id == jid,
                                Resume.ai_score.isnot(None),
                            ).count()
                            if total_resumes > 0:
                                ws.current_node = "candidate_pool"
                                session.commit()
                                logger.info(f"✅ 筛选工作流已推进: resume_auto_screen → candidate_pool (request={req_id})")
            except Exception as e:
                logger.warning(f"推进筛选工作流失败: {e}")
        except Exception as e:
            logger.warning(f"后台处理简历失败 (rid={rid}): {e}")
        finally:
            session.close()

    threading.Thread(
        target=_process_resume_async,
        args=(resume_id, jd_id),
        daemon=True,
    ).start()

    return {"id": resume_id, "file_name": file_name, "status": "pending", "processing": True}


@router.get("", response_model=dict)
def list_resumes(
    jd_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None),
    sort_by: str = Query("created_at"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """简历列表（搜索/筛选/分页）"""
    query = db.query(Resume)

    if jd_id:
        query = query.filter(Resume.jd_id == jd_id)
    if status:
        query = query.filter(Resume.status == ResumeStatus(status))
    if keyword:
        kw = f"%{keyword}%"
        query = query.filter(Resume.name.ilike(kw) | Resume.skills.ilike(kw))
    if min_score is not None:
        query = query.filter(Resume.ai_score >= min_score)

    total = query.count()
    # ⭐ 候选池默认按分数降序
    if sort_by == "score":
        items = query.order_by(Resume.ai_score.desc().nullslast()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()
    else:
        items = query.order_by(Resume.created_at.desc()).offset(
            (page - 1) * page_size
        ).limit(page_size).all()

    # 填充岗位标题
    jd_cache: dict[int, str] = {}
    jd_ids = set(r.jd_id for r in items if r.jd_id)
    if jd_ids:
        jds = db.query(JobDescription.id, JobDescription.title, JobDescription.department).filter(
            JobDescription.id.in_(jd_ids)
        ).all()
        for jd in jds:
            dept = f"（{jd.department}）" if jd.department else ""
            jd_cache[jd.id] = f"{jd.title}{dept}"

    result_items = []
    for r in items:
        rd = ResumeResponse.model_validate(r)
        if r.jd_id and r.jd_id in jd_cache:
            rd.jd_title = jd_cache[r.jd_id]
        result_items.append(rd)

    return {
        "items": result_items,
        "total": total, "page": page, "page_size": page_size,
    }


@router.get("/candidate-pool")
def get_candidate_pool(jd_id: Optional[int] = Query(None), db: Session = Depends(get_db)):
    """候选池：AI评分≥60分的简历，按分数降序"""
    query = db.query(Resume).filter(
        Resume.ai_score >= 60,
        Resume.status.in_([ResumeStatus.AI_PASS, ResumeStatus.MANUAL_PASS]),
    )
    if jd_id:
        query = query.filter(Resume.jd_id == jd_id)
    items = query.order_by(Resume.ai_score.desc()).all()

    # 填充岗位标题
    jd_cache: dict[int, str] = {}
    jd_ids = set(r.jd_id for r in items if r.jd_id)
    if jd_ids:
        jds = db.query(JobDescription.id, JobDescription.title, JobDescription.department).filter(
            JobDescription.id.in_(jd_ids)
        ).all()
        for jd in jds:
            dept = f"（{jd.department}）" if jd.department else ""
            jd_cache[jd.id] = f"{jd.title}{dept}"

    result = []
    for r in items:
        rd = ResumeResponse.model_validate(r)
        if r.jd_id and r.jd_id in jd_cache:
            rd.jd_title = jd_cache[r.jd_id]
        result.append(rd)

    return {
        "candidates": result,
        "count": len(items),
    }


@router.get("/{resume_id}", response_model=ResumeResponse)
def get_resume(resume_id: int, db: Session = Depends(get_db)):
    """简历详情"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "简历不存在")
    rd = ResumeResponse.model_validate(resume)
    if resume.jd_id:
        jd = db.query(JobDescription.title, JobDescription.department).filter(
            JobDescription.id == resume.jd_id
        ).first()
        if jd:
            dept = f"（{jd.department}）" if jd.department else ""
            rd.jd_title = f"{jd.title}{dept}"
    return rd


@router.post("/{resume_id}/deep-analyze")
def deep_analyze_resume(resume_id: int, jd_id: Optional[int] = Query(None),
                        db: Session = Depends(get_db)):
    """深度分析简历"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume or not resume.raw_text:
        raise HTTPException(400, "简历无效或无文本内容")

    jd_content = ""
    if jd_id:
        from app.models import JobDescription
        jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        if jd:
            jd_content = jd.content or ""

    deep = analyze_resume_deep(resume.raw_text, jd_content)
    resume.deep_analysis = deep
    db.commit()

    return deep


@router.post("/{resume_id}/screen")
def screen_resume(resume_id: int, jd_id: Optional[int] = Query(None),
                  db: Session = Depends(get_db)):
    """AI 初筛单份简历"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume or not resume.raw_text:
        raise HTTPException(400, "简历无效")

    jd_content = ""
    jd_skills = []
    if jd_id:
        from app.models import JobDescription
        jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
        if jd:
            jd_content = jd.content or ""
            jd_skills = json.loads(jd.required_skills or "[]") if jd.required_skills else []

    screening = ai_initial_screening(resume.raw_text, jd_content, jd_skills)
    resume.ai_score = screening.get("score", 0)
    resume.ai_score_detail = json.dumps(screening.get("score_detail", {}), ensure_ascii=False)
    resume.ai_reason = screening.get("recommendation", "")
    resume.ai_recommended = (screening.get("score", 0) >= 60)

    if resume.ai_recommended:
        resume.status = ResumeStatus.AI_PASS
    else:
        resume.status = ResumeStatus.AI_REJECT

    db.commit()
    return screening


class UpdateNotesInput(BaseModel):
    notes: str


@router.patch("/{resume_id}/notes")
def update_resume_notes(resume_id: int, data: UpdateNotesInput, db: Session = Depends(get_db)):
    """更新简历内部备注"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "简历不存在")
    resume.notes = data.notes
    db.commit()
    logger.info(f"📝 更新备注 resume_id={resume_id}")
    return {"id": resume.id, "notes": resume.notes}


@router.patch("/{resume_id}/jd")
def update_resume_jd(resume_id: int, data: UpdateResumeJDInput, db: Session = Depends(get_db)):
    """手动关联 / 切换岗位"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(404, "简历不存在")
    resume.jd_id = data.jd_id
    db.commit()
    # 返回完整简历信息（含 jd_title）
    rd = ResumeResponse.model_validate(resume)
    if data.jd_id:
        jd = db.query(JobDescription.title, JobDescription.department).filter(
            JobDescription.id == data.jd_id
        ).first()
        if jd:
            dept = f"（{jd.department}）" if jd.department else ""
            rd.jd_title = f"{jd.title}{dept}"
    logger.info(f"🔗 关联岗位 resume_id={resume_id} → jd_id={data.jd_id}")
    return rd


@router.post("/batch-action")
def batch_action(action: ResumeBatchAction, db: Session = Depends(get_db)):
    """批量操作简历"""
    updated = 0
    for rid in action.resume_ids:
        resume = db.query(Resume).filter(Resume.id == rid).first()
        if not resume:
            continue
        if action.action == "pass":
            resume.status = ResumeStatus.MANUAL_PASS
        elif action.action == "reject":
            resume.status = ResumeStatus.MANUAL_REJECT
        if action.note:
            resume.review_note = action.note
        if action.reviewer:
            resume.reviewed_by = action.reviewer
        updated += 1

    db.commit()
    return {"updated": updated}


@router.delete("/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    """删除指定简历"""
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    if not resume:
        raise HTTPException(status_code=404, detail=f"简历 {resume_id} 不存在")

    # 删除文件
    if resume.file_path:
        import os
        try:
            os.remove(resume.file_path)
        except Exception:
            pass

    db.delete(resume)
    db.commit()
    logger.info(f"🗑️ 已删除简历 id={resume_id}")
    return {"message": f"简历 {resume_id} 已删除", "resume_id": resume_id}
