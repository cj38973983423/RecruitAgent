"""工作流节点 — 简历收集 + AI 初筛 + 人工复筛"""
import json
import logging
from app.workflows.state import RecruitmentState
from app.services.resume_analyzer import analyze_resume_deep, ai_initial_screening
from app.database import SessionLocal
from app.models import Resume, ResumeStatus, WorkflowLog
from app.services.storage import extract_text

logger = logging.getLogger(__name__)


def node_resume_collect(state: RecruitmentState) -> dict:
    """节点：简历收集 — 已上传则自动进入初筛"""
    # 这个节点主要等待事件触发
    # 简历通过 API 上传
    db = SessionLocal()
    try:
        jd_id = state.get("jd_id")
        query = db.query(Resume)
        if jd_id:
            query = query.filter(Resume.jd_id == jd_id)

        total = query.count()
        pending = query.filter(Resume.status == ResumeStatus.PENDING).count()

        if pending == 0:
            # 还没简历，等待上传
            _log_workflow(db, state["request_id"], "resume_collect", "awaiting_upload", {
                "total_resumes": total,
            })
            return {
                "requires_human_intervention": True,
                "human_action": "upload_resumes",
                "human_action_data": {"jd_id": jd_id},
                "current_node": "resume_collect",
            }

        # 有新简历，进入初筛
        return {
            "current_node": "resume_ai_screen",
            "requires_human_intervention": False,
        }
    finally:
        db.close()


def node_resume_ai_screen(state: RecruitmentState) -> dict:
    """节点：AI 初筛 — 深度分析 + 风险预警 + 自动推荐"""
    request_id = state["request_id"]
    jd_id = state.get("jd_id")

    db = SessionLocal()
    try:
        # 获取待评分简历
        resumes = db.query(Resume).filter(
            Resume.status == ResumeStatus.PENDING,
            Resume.raw_text.isnot(None),
        ).all()

        if not resumes:
            _log_workflow(db, request_id, "resume_ai_screen", "no_pending", {})
            return {
                "current_node": "resume_manual_screen",
            }

        # 获取 JD 内容
        jd_content = ""
        jd_skills = []
        from app.models import JobDescription
        if jd_id:
            jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
            if jd:
                jd_content = jd.content or ""
                jd_skills = json.loads(jd.required_skills or "[]") if jd.required_skills else []

        threshold = state.get("screening_threshold", 60)

        screened_ids = []
        rejected_ids = []
        recommended_ids = []

        for resume in resumes:
            try:
                # 1. AI 初筛
                screening = ai_initial_screening(
                    resume.raw_text, jd_content, jd_skills
                )
                passed = screening.get("passed", False)
                score = screening.get("score", 0)

                # 2. 深度分析
                deep = analyze_resume_deep(resume.raw_text, jd_content)

                # 3. 查重检查
                is_dup = _check_duplicate(db, resume)

                # 保存结果
                resume.ai_score = score
                resume.ai_score_detail = json.dumps(screening.get("score_detail", {}), ensure_ascii=False)
                resume.ai_reason = screening.get("recommendation", "") or screening.get("summary", "")
                resume.deep_analysis = deep
                resume.is_duplicate = is_dup

                risk_warnings = deep.get("risk_warnings", [])
                frequent_change = deep.get("frequent_job_change", False)

                # 风险过滤
                has_high_risk = any(
                    w.get("severity") == "high" for w in risk_warnings if isinstance(w, dict)
                )

                if is_dup:
                    resume.status = ResumeStatus.AI_REJECT
                    rejected_ids.append(resume.id)
                elif has_high_risk or frequent_change:
                    resume.status = ResumeStatus.AI_REJECT
                    rejected_ids.append(resume.id)
                    if not resume.ai_reason:
                        resume.ai_reason = f"风险过滤: {json.dumps(risk_warnings, ensure_ascii=False)[:200]}"
                elif passed and score >= threshold:
                    resume.status = ResumeStatus.AI_PASS
                    resume.ai_recommended = (score >= 80)
                    screened_ids.append(resume.id)
                    if score >= 80:
                        recommended_ids.append(resume.id)
                else:
                    resume.status = ResumeStatus.AI_REJECT
                    rejected_ids.append(resume.id)

            except Exception as e:
                logger.warning(f"简历 {resume.id} AI 评分失败: {e}")
                # 评分失败不阻止流程
                resume.ai_score = 0
                resume.status = ResumeStatus.AI_REJECT
                rejected_ids.append(resume.id)

        db.commit()

        _log_workflow(db, request_id, "resume_ai_screen", "completed", {
            "total": len(resumes),
            "screened": len(screened_ids),
            "rejected": len(rejected_ids),
            "recommended": len(recommended_ids),
        })

        return {
            "ai_screened_ids": screened_ids,
            "ai_rejected_ids": rejected_ids,
            "ai_recommended_ids": recommended_ids,
            "current_node": "resume_manual_screen",
            "requires_human_intervention": True,
            "human_action": "review_screening_results",
            "human_action_data": {
                "screened": len(screened_ids),
                "rejected": len(rejected_ids),
                "recommended": len(recommended_ids),
            },
        }
    finally:
        db.close()


def node_resume_manual_screen(state: RecruitmentState) -> dict:
    """节点：人工复筛 — HR 验证 AI 结果"""
    action = state.get("human_action")
    data = state.get("human_action_data") or {}

    db = SessionLocal()
    try:
        resume_ids = data.get("resume_ids", [])
        action_type = data.get("action")  # pass / reject
        note = data.get("note", "")
        reviewer = data.get("reviewer", "")

        passed_ids = list(state.get("manual_passed_ids", []))
        rejected_ids = list(state.get("manual_rejected_ids", []))

        if action_type == "pass":
            for rid in resume_ids:
                resume = db.query(Resume).filter(Resume.id == rid).first()
                if resume:
                    resume.status = ResumeStatus.MANUAL_PASS
                    resume.review_note = note
                    resume.reviewed_by = reviewer
                    passed_ids.append(rid)
            db.commit()

        elif action_type == "reject":
            for rid in resume_ids:
                resume = db.query(Resume).filter(Resume.id == rid).first()
                if resume:
                    resume.status = ResumeStatus.MANUAL_REJECT
                    resume.review_note = note
                    resume.reviewed_by = reviewer
                    rejected_ids.append(rid)
            db.commit()

        _log_workflow(db, state["request_id"], "resume_manual_screen", "completed", {
            "passed": len(passed_ids),
            "rejected": len(rejected_ids),
        })

        return {
            "manual_passed_ids": passed_ids,
            "manual_rejected_ids": rejected_ids,
            "current_node": "interview_schedule",
            "requires_human_intervention": False,
        }
    finally:
        db.close()


def _check_duplicate(db, resume) -> bool:
    """检查简历是否重复（同姓名 + 相似技能）"""
    if not resume.name:
        return False
    exists = db.query(Resume).filter(
        Resume.name == resume.name,
        Resume.id != resume.id,
        Resume.status != ResumeStatus.AI_REJECT,
    ).first()
    return exists is not None
