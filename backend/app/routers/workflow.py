"""API 路由 — 双工作流控制（LangGraph interrupt/resume 模式）"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import RecruitmentRequest, JobDescription, WorkflowLog, WorkflowStateDB, RequestStatus, JDStatus, Offer, OfferStatus, Resume
from app.schemas import (
    RecruitmentRequestCreate,
    WorkflowActionRequest,
)
from app.workflows.state_v2 import (
    JDWorkflowState,
    get_initial_jd_state,
)
from app.workflows.graph_jd import (
    get_jd_graph, get_jd_graph_definition,
)
from app.workflows.graph_screening import (
    node_resume_collect, node_resume_auto_screen, node_candidate_pool,
    node_interview_schedule, node_interview_questions,
    node_interview_execute, node_interview_evaluate,
    node_offer_manage, node_onboarding,
    get_screening_graph_definition, auto_score_resumes,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workflow", tags=["工作流"])


# ══════════════════════════════════════════════
# 岗位审查 & 岗位管理（非工作流操作）
# ══════════════════════════════════════════════

@router.get("/pending-jds")
def list_pending_jds(db: Session = Depends(get_db)):
    """获取所有待审查的 JD（PENDING_REVIEW），按部门分组"""
    jds = db.query(JobDescription).filter(
        JobDescription.status.in_([JDStatus.PENDING_REVIEW, JDStatus.REGENERATING])
    ).order_by(JobDescription.created_at.desc()).all()

    groups = {}
    for jd in jds:
        dept = jd.department or "未分类"
        if dept not in groups:
            groups[dept] = []
        req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == jd.request_id).first()
        groups[dept].append({
            "id": jd.id,
            "request_id": jd.request_id,
            "title": jd.title,
            "department": jd.department,
            "content": jd.content,
            "original_content": jd.original_content,
            "status": jd.status.value if hasattr(jd.status, 'value') else str(jd.status),
            "created_at": jd.created_at.isoformat() if jd.created_at else None,
            "position_name": req.position_name if req else jd.title,
            "headcount": req.headcount if req else 1,
            "urgency": req.urgency if req else "normal",
            "budget_range": req.budget_range if req else None,
            "raw_requirements": req.raw_requirements if req else None,
        })

    return {"groups": groups, "total": len(jds), "departments": list(groups.keys())}


@router.post("/approve-jd/{jd_id}")
def approve_pending_jd(jd_id: int, db: Session = Depends(get_db)):
    """人工审查通过：PENDING_REVIEW → APPROVED"""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD 不存在")
    if jd.status != JDStatus.PENDING_REVIEW:
        raise HTTPException(status_code=400, detail=f"JD 状态不是待审查: {jd.status}")

    jd.status = JDStatus.APPROVED
    request = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == jd.request_id).first()
    if request:
        request.status = RequestStatus.COMPLETED

    try:
        from app.services.vector_store import vector_store
        skills_str = (jd.required_skills or "") + "," + (jd.nice_to_have or "")
        vector_store.add_jd(jd_id=jd.id, jd_title=jd.title, content=jd.content,
                            skills=skills_str, industry=jd.department or "", source="generated")
        jd.vector_synced = True
    except Exception as e:
        logger.warning(f"向量同步失败: {e}")
        jd.vector_synced = False

    db.commit()

    # 启动筛选工作流
    try:
        from app.database import SessionLocal as NewSession
        s_db = NewSession()
        try:
            from app.workflows.state_v2 import get_initial_screening_state
            s_state = get_initial_screening_state(jd.request_id, jd_id, jd.title[:100], jd.department or "")
            ws = WorkflowStateDB(
                request_id=jd.request_id, workflow_type="resume_screening",
                state_json=s_state, current_node="resume_collect", status="running",
            )
            s_db.add(ws)
            s_db.commit()
            logger.info(f"✅ 筛选工作流已自动启动 for request {jd.request_id}")
        except Exception as se:
            logger.warning(f"启动筛选工作流失败: {se}")
        finally:
            s_db.close()
    except Exception as e:
        logger.warning(f"启动筛选工作流异常: {e}")

    return {"jd_id": jd.id, "status": "approved", "message": "✅ 岗位已审核通过，筛选工作流已启动"}


@router.post("/reject-jd/{jd_id}")
def reject_pending_jd(jd_id: int, reason: str = "", db: Session = Depends(get_db)):
    """驳回待审查的 JD"""
    jd = db.query(JobDescription).filter(JobDescription.id == jd_id).first()
    if not jd:
        raise HTTPException(status_code=404, detail="JD 不存在")
    if jd.status != JDStatus.PENDING_REVIEW:
        raise HTTPException(status_code=400, detail=f"JD 状态不是待审查: {jd.status}")
    jd.status = JDStatus.REJECTED
    jd.review_comment = reason
    db.commit()
    return {"jd_id": jd.id, "status": "rejected", "message": "❌ 岗位已驳回"}


@router.get("/approved-jds")
def list_approved_jds(db: Session = Depends(get_db)):
    """获取所有已通过的 JD（APPROVED），按部门分组"""
    jds = db.query(JobDescription).filter(
        JobDescription.status == JDStatus.APPROVED
    ).order_by(JobDescription.created_at.desc()).all()

    groups = {}
    # 批量查询各岗位的 Offer 已填数量（含 Offer.jd_id 直接匹配 + 简历间接关联）
    filled_counts: dict[int, int] = {}
    offer_rows = db.query(Offer.jd_id, Offer.resume_id, Offer.status).filter(
        Offer.status.in_([OfferStatus.SENT, OfferStatus.ACCEPTED, OfferStatus.ONBOARDED]),
    ).all()
    # 先统计 jd_id 直接匹配的
    jd_ids_with_offer: set[int] = set()
    for row in offer_rows:
        if row.jd_id:
            filled_counts[row.jd_id] = filled_counts.get(row.jd_id, 0) + 1
            jd_ids_with_offer.add(row.jd_id)
    # 再统计 jd_id=None 但简历关联了岗位的
    for row in offer_rows:
        if not row.jd_id and row.resume_id:
            r = db.query(Resume.jd_id).filter(Resume.id == row.resume_id, Resume.jd_id.isnot(None)).first()
            if r and r.jd_id:
                filled_counts[r.jd_id] = filled_counts.get(r.jd_id, 0) + 1

    for jd in jds:
        dept = jd.department or "未分类"
        if dept not in groups:
            groups[dept] = []
        req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == jd.request_id).first()
        filled = filled_counts.get(jd.id, 0)
        groups[dept].append({
            "id": jd.id,
            "request_id": jd.request_id,
            "title": jd.title,
            "department": jd.department,
            "content": jd.content,
            "status": jd.status.value if hasattr(jd.status, 'value') else str(jd.status),
            "created_at": jd.created_at.isoformat() if jd.created_at else None,
            "position_name": req.position_name if req else jd.title,
            "headcount": req.headcount if req else 1,
            "filled_count": filled,
            "is_filled": req.headcount == 1 and filled >= 1 if req else False,
            "urgency": req.urgency if req else "normal",
            "vector_synced": jd.vector_synced,
        })

    return {"groups": groups, "total": len(jds), "departments": list(groups.keys())}


# ══════════════════════════════════════════════
# JD 工作流 — LangGraph invoke（简化版：无多轮澄清）
# ══════════════════════════════════════════════

def _get_graph():
    g = get_jd_graph()
    if not g:
        raise HTTPException(status_code=500, detail="LangGraph 不可用")
    return g


@router.post("/start", response_model=dict)
def start_workflow(request_data: RecruitmentRequestCreate, db: Session = Depends(get_db)):
    """创建需求并启动 JD 工作流（直接 AI 增强 → 生成 JD → PENDING_REVIEW）"""
    req = RecruitmentRequest(
        department=request_data.department,
        position_name=request_data.position_name,
        headcount=request_data.headcount,
        urgency=request_data.urgency,
        raw_requirements=request_data.raw_requirements,
        budget_range=request_data.budget_range,
        created_by=request_data.created_by,
        status=RequestStatus.DRAFT,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    # 初始化状态
    state = get_initial_jd_state(req.id)
    state["raw_requirements"] = req.raw_requirements

    _save_jd_db_state(db, req.id, state, "running")

    # 调用 LangGraph（简化版没有 interrupt）
    graph = _get_graph()
    config = {"configurable": {"thread_id": str(req.id)}}
    final_state = None

    try:
        for event in graph.stream(state, config, subgraphs=False):
            logger.info(f"Graph event for request {req.id}: {list(event.keys())}")
            for node_name, node_output in event.items():
                if isinstance(node_output, dict):
                    state.update(node_output)

        final_state = state
    except Exception as e:
        err_str = str(e)
        logger.error(f"Graph invoke 失败: {err_str}")
        state["status"] = "terminated"
        state["error"] = err_str
        _save_jd_db_state(db, req.id, state, "terminated")
        raise HTTPException(status_code=500, detail=f"工作流执行失败: {err_str}")

    if final_state:
        _save_jd_db_state(db, req.id, final_state, final_state.get("status", "running"))

    return {
        "request_id": req.id,
        "workflow_type": "jd_generation",
        "status": final_state.get("status", "running") if final_state else "completed",
        "jd_id": final_state.get("jd_id") if final_state else None,
        "jd_status": final_state.get("jd_status") if final_state else None,
        "enhanced_jd_text": final_state.get("enhanced_jd_text") if final_state else None,
        "message": "✅ JD 已生成，等待人工审查" if (final_state and final_state.get("status") == "completed") else "工作流执行中",
    }


# ══════════════════════════════════════════════
# 查询工作流状态
# ══════════════════════════════════════════════

@router.get("/active")
def list_active_workflows(db: Session = Depends(get_db)):
    """查看所有活跃工作流"""
    requests = db.query(RecruitmentRequest).order_by(
        RecruitmentRequest.created_at.desc()
    ).limit(20).all()

    result = []
    for req in requests:
        jd_ws = db.query(WorkflowStateDB).filter(
            WorkflowStateDB.request_id == req.id,
            WorkflowStateDB.workflow_type == "jd_generation",
        ).first()
        pending_jd = db.query(JobDescription).filter(
            JobDescription.request_id == req.id,
            JobDescription.status == JDStatus.PENDING_REVIEW,
        ).first()
        screen_ws = db.query(WorkflowStateDB).filter(
            WorkflowStateDB.request_id == req.id,
            WorkflowStateDB.workflow_type == "resume_screening",
        ).first()

        item = {
            "request_id": req.id,
            "position": req.position_name,
            "department": req.department,
            "status": req.status.value if hasattr(req.status, 'value') else str(req.status),
            "jd_workflow": {
                "current_node": jd_ws.current_node if jd_ws else None,
                "status": jd_ws.status if jd_ws else None,
                "jd_status": pending_jd.status.value if pending_jd else None,
            } if jd_ws else None,
            "has_pending_review": pending_jd is not None,
            "pending_jd_id": pending_jd.id if pending_jd else None,
            "screening_workflow": {
                "current_node": screen_ws.current_node if screen_ws else None,
                "status": screen_ws.status if screen_ws else None,
            } if screen_ws else None,
        }
        result.append(item)
    return result


@router.get("/{request_id}/state")
def get_workflow_state(request_id: int, db: Session = Depends(get_db)):
    """获取工作流状态"""
    response = {"request_id": request_id}

    # JD 工作流
    jd_state = _load_jd_db_state(db, request_id)
    if jd_state:
        response["jd_workflow"] = {
            "current_node": jd_state.get("current_node"),
            "status": jd_state.get("status"),
            "finalized_requirements": jd_state.get("finalized_requirements"),
            "jd_id": jd_state.get("jd_id"),
            "jd_status": jd_state.get("jd_status"),
            "enhanced_jd_text": jd_state.get("enhanced_jd_text"),
            "error": jd_state.get("error"),
        }
    else:
        response["jd_workflow"] = None

    # 筛选工作流
    screen_ws = db.query(WorkflowStateDB).filter(
        WorkflowStateDB.request_id == request_id,
        WorkflowStateDB.workflow_type == "resume_screening",
    ).first()
    if screen_ws:
        sc_state = screen_ws.state_json
        pool = sc_state.get("candidate_pool", [])
        response["screening_workflow"] = {
            "current_node": sc_state.get("current_node"),
            "status": sc_state.get("status"),
            "stats": {
                "resumes_total": len(sc_state.get("resume_ids", [])),
                "ai_screened": len(sc_state.get("ai_screened_ids", [])),
                "ai_rejected": len(sc_state.get("ai_rejected_ids", [])),
                "ai_recommended": len(sc_state.get("ai_recommended_ids", [])),
                "candidate_pool": len(pool),
                "interviews": len(sc_state.get("interview_ids", [])),
            },
            "candidate_pool": pool,
            "requires_human_intervention": sc_state.get("requires_human_intervention", False),
            "human_action": sc_state.get("human_action"),
            "human_action_data": sc_state.get("human_action_data"),
            "error": sc_state.get("error"),
        }
    else:
        response["screening_workflow"] = None

    req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()
    if req:
        response["raw_requirements"] = req.raw_requirements
        response["position"] = req.position_name
        response["department"] = req.department

    return response


@router.get("/graph-definition")
def get_graph():
    """返回两个工作流的图定义"""
    from app.workflows.graph_screening import get_screening_graph_definition
    return {
        "jd_generation": get_jd_graph_definition(),
        "resume_screening": get_screening_graph_definition(),
    }


# ══════════════════════════════════════════════
# 筛选工作流（保留原有实现）
# ══════════════════════════════════════════════

@router.post("/start-screening")
def start_screening_workflow(request_id: int, db: Session = Depends(get_db)):
    """启动简历筛选工作流"""
    req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="需求不存在")

    existing = db.query(WorkflowStateDB).filter(
        WorkflowStateDB.request_id == request_id,
        WorkflowStateDB.workflow_type == "resume_screening",
    ).first()
    if existing:
        return {"message": "筛选工作流已存在", "request_id": request_id}

    from app.workflows.state_v2 import get_initial_screening_state
    jd = db.query(JobDescription).filter(
        JobDescription.request_id == request_id,
        JobDescription.status == JDStatus.APPROVED,
    ).first()
    state = get_initial_screening_state(
        request_id, jd.id if jd else None,
        jd.title[:100] if jd else "", req.department or "",
    )
    ws = WorkflowStateDB(
        request_id=request_id, workflow_type="resume_screening",
        state_json=state, current_node="resume_collect", status="running",
    )
    db.add(ws)
    db.commit()
    return {"request_id": request_id, "workflow_type": "resume_screening",
            "current_node": "resume_collect", "message": "简历筛选工作流已启动"}


@router.post("/action")
def handle_action(action: WorkflowActionRequest, db: Session = Depends(get_db)):
    """处理筛选工作流的人工操作"""
    request_id = action.request_id
    action_type = action.action
    data = action.data or {}

    ws = db.query(WorkflowStateDB).filter(
        WorkflowStateDB.request_id == request_id,
        WorkflowStateDB.workflow_type == "resume_screening",
    ).first()
    if not ws:
        raise HTTPException(status_code=404, detail="筛选工作流未启动")

    state = ws.state_json
    try:
        state["human_action"] = action_type
        state["human_action_data"] = data
        state["requires_human_intervention"] = False

        node_map = {
            "review_candidates": node_candidate_pool,
            "select_candidates": node_candidate_pool,
            "arrange_interviews": node_interview_schedule,
            "complete_interview": node_interview_execute,
            "submit_evaluation": node_interview_evaluate,
            "send_offer": node_offer_manage,
            "offer_accepted": node_offer_manage,
            "complete_onboarding": node_onboarding,
        }
        fn = node_map.get(action_type)
        if fn:
            updates = fn(state)
            state.update(updates)

        ws.state_json = state
        ws.current_node = state.get("current_node", ws.current_node)
        db.commit()

    except Exception as e:
        logger.error(f"操作 {action_type} 失败: {e}")
        state["error"] = str(e)
        state["requires_human_intervention"] = True
        ws.state_json = state
        db.commit()

    return {
        "request_id": request_id,
        "workflow_type": "resume_screening",
        "current_node": state.get("current_node"),
        "status": state.get("status"),
        "requires_human_intervention": state.get("requires_human_intervention", False),
    }


@router.post("/{request_id}/trigger-screening")
def trigger_screening(request_id: int, db: Session = Depends(get_db)):
    """触发筛选工作流重新评估所有待评简历"""
    ws = db.query(WorkflowStateDB).filter(
        WorkflowStateDB.request_id == request_id,
        WorkflowStateDB.workflow_type == "resume_screening",
    ).first()
    if not ws:
        return {"error": "筛选工作流未启动"}

    state = ws.state_json
    jd_id = state.get("jd_id")
    result = auto_score_resumes(request_id, jd_id)

    pool = result.get("candidate_pool", [])
    state["candidate_pool"] = pool
    state["ai_screened_ids"] = result.get("screened_ids", state.get("ai_screened_ids", []))
    state["ai_rejected_ids"] = result.get("rejected_ids", state.get("ai_rejected_ids", []))
    state["screened_count"] = state.get("screened_count", 0) + result.get("screened_count", 0)
    state["current_node"] = "candidate_pool"
    state["requires_human_intervention"] = True
    state["human_action"] = "review_candidates"
    state["human_action_data"] = {"candidates": pool, "total": len(pool), "rejected": result.get("rejected_count", 0)}
    ws.state_json = state
    ws.current_node = "candidate_pool"
    db.commit()

    return {"screened_count": result.get("screened_count", 0),
            "rejected_count": result.get("rejected_count", 0), "candidate_pool": pool}


@router.get("/{request_id}/candidates")
def get_candidate_pool(request_id: int, db: Session = Depends(get_db)):
    """获取候选池"""
    ws = db.query(WorkflowStateDB).filter(
        WorkflowStateDB.request_id == request_id,
        WorkflowStateDB.workflow_type == "resume_screening",
    ).first()
    if not ws:
        return {"candidates": [], "count": 0}
    pool = ws.state_json.get("candidate_pool", [])
    pool.sort(key=lambda x: -x["score"])
    return {"candidates": pool, "count": len(pool)}


@router.get("/{request_id}/history")
def get_workflow_history(request_id: int, db: Session = Depends(get_db)):
    """获取工作流历史日志"""
    logs = db.query(WorkflowLog).filter(
        WorkflowLog.request_id == request_id
    ).order_by(WorkflowLog.started_at.desc()).limit(50).all()
    return [{"id": log.id, "node": log.node, "status": log.status,
             "output": log.output_data, "error": log.error,
             "started_at": log.started_at} for log in logs]


@router.delete("/{request_id}")
def delete_workflow(request_id: int, db: Session = Depends(get_db)):
    """删除整个工作流"""
    req = db.query(RecruitmentRequest).filter(RecruitmentRequest.id == request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"需求 {request_id} 不存在")
    db.query(WorkflowLog).filter(WorkflowLog.request_id == request_id).delete()
    db.query(WorkflowStateDB).filter(WorkflowStateDB.request_id == request_id).delete()
    db.query(JobDescription).filter(JobDescription.request_id == request_id).delete()
    db.delete(req)
    db.commit()
    logger.info(f"🗑️ 已删除工作流 request_id={request_id}")
    return {"message": f"工作流 {request_id} 已删除", "request_id": request_id}


# ══════════════════════════════════════════════
# 数据库持久化辅助
# ══════════════════════════════════════════════

def _load_jd_db_state(db: Session, request_id: int) -> dict | None:
    ws = db.query(WorkflowStateDB).filter(
        WorkflowStateDB.request_id == request_id,
        WorkflowStateDB.workflow_type == "jd_generation",
    ).first()
    return ws.state_json if ws else None


def _save_jd_db_state(db: Session, request_id: int, state: dict, status_str: str = "running"):
    ws = db.query(WorkflowStateDB).filter(
        WorkflowStateDB.request_id == request_id,
        WorkflowStateDB.workflow_type == "jd_generation",
    ).first()
    if not ws:
        ws = WorkflowStateDB(
            request_id=request_id, workflow_type="jd_generation",
            state_json=state, current_node="requirement_collect", status=status_str,
        )
        db.add(ws)
    else:
        ws.state_json = state
        ws.current_node = "requirement_collect"
        ws.status = status_str
    db.commit()
