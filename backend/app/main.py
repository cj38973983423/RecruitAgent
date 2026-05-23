"""FastAPI 主入口"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.routers import workflow, jd, resumes, interviews, kb, interviewers, offers, onboarding, candidates

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """生命周期：启动时建表"""
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    init_db()
    logger.info("Database tables initialized")
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="全流程招聘智能体 — LangGraph 状态机驱动",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(workflow.router)
app.include_router(jd.router)
app.include_router(resumes.router)
app.include_router(interviews.router)
app.include_router(kb.router)
app.include_router(interviewers.router)
app.include_router(offers.router)
app.include_router(onboarding.router)
app.include_router(candidates.router)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "version": settings.app_version, "app": settings.app_name}


@app.get("/api/stats")
async def get_stats():
    """获取招聘数据总览"""
    from app.database import SessionLocal
    from app.models import (
        RecruitmentRequest, Resume, Interview, Interviewer,
        RequestStatus, ResumeStatus, InterviewStatus,
        Offer, OfferStatus, JobDescription,
    )

    db = SessionLocal()
    try:
        from sqlalchemy import func

        # 招聘需求
        total_requests = db.query(func.count(RecruitmentRequest.id)).scalar() or 0
        requests_active = db.query(func.count(RecruitmentRequest.id)).filter(
            RecruitmentRequest.status.in_([RequestStatus.IN_PROGRESS, RequestStatus.CLARIFYING])
        ).scalar() or 0
        requests_completed = db.query(func.count(RecruitmentRequest.id)).filter(
            RecruitmentRequest.status == RequestStatus.COMPLETED
        ).scalar() or 0
        # 总计划招聘人数（所有需求的 headcount 之和）
        headcount_total = db.query(func.coalesce(func.sum(RecruitmentRequest.headcount), 0)).filter(
            RecruitmentRequest.status != RequestStatus.CANCELLED
        ).scalar() or 0
        # 已入职人数（所有状态为 ONBOARDED 的 Offer）
        hired_count = db.query(func.count(Offer.id)).filter(
            Offer.status == OfferStatus.ONBOARDED,
        ).scalar() or 0
        # 剩余待招
        remaining_headcount = max(0, headcount_total - hired_count)

        # 简历
        total_resumes = db.query(func.count(Resume.id)).scalar() or 0
        resumes_pending = db.query(func.count(Resume.id)).filter(
            Resume.status == ResumeStatus.PENDING
        ).scalar() or 0
        resumes_ai_pass = db.query(func.count(Resume.id)).filter(
            Resume.status == ResumeStatus.AI_PASS
        ).scalar() or 0
        resumes_ai_reject = db.query(func.count(Resume.id)).filter(
            Resume.status == ResumeStatus.AI_REJECT
        ).scalar() or 0
        resumes_manual_pass = db.query(func.count(Resume.id)).filter(
            Resume.status == ResumeStatus.MANUAL_PASS
        ).scalar() or 0
        resumes_in_pool = db.query(func.count(Resume.id)).filter(
            Resume.status.in_([ResumeStatus.AI_PASS, ResumeStatus.MANUAL_PASS])
        ).scalar() or 0

        # 面试
        total_interviews = db.query(func.count(Interview.id)).scalar() or 0
        interviews_pending = db.query(func.count(Interview.id)).filter(
            Interview.status == InterviewStatus.PENDING
        ).scalar() or 0
        interviews_confirmed = db.query(func.count(Interview.id)).filter(
            Interview.status == InterviewStatus.CONFIRMED
        ).scalar() or 0
        interviews_completed = db.query(func.count(Interview.id)).filter(
            Interview.status == InterviewStatus.COMPLETED
        ).scalar() or 0

        # 各轮次面试数
        interviews_by_round = {}
        for r in ["first", "second", "third", "hr"]:
            interviews_by_round[r] = db.query(func.count(Interview.id)).filter(
                Interview.round == r
            ).scalar() or 0

        # 面试官
        total_interviewers = db.query(func.count(Interviewer.id)).scalar() or 0
        active_interviewers = db.query(func.count(Interviewer.id)).filter(
            Interviewer.status == "active"
        ).scalar() or 0

        # Offer
        offers_sent = db.query(func.count(Offer.id)).filter(
            Offer.status.in_([OfferStatus.SENT, OfferStatus.ACCEPTED, OfferStatus.ONBOARDED, OfferStatus.WITHDRAWN])
        ).scalar() or 0
        # 已接受 = 已接受 + 已入职（入职的人当然接受了 Offer）
        offers_accepted = db.query(func.count(Offer.id)).filter(
            Offer.status.in_([OfferStatus.ACCEPTED, OfferStatus.ONBOARDED])
        ).scalar() or 0

        # 入职
        onboarded = db.query(func.count(Offer.id)).filter(
            Offer.status == OfferStatus.ONBOARDED
        ).scalar() or 0

        return {
            "requests": {
                "total": total_requests,
                "active": requests_active,
                "completed": requests_completed,
                "headcount_total": headcount_total,
                "hired_count": hired_count,
                "remaining_headcount": remaining_headcount,
            },
            "resumes": {
                "total": total_resumes,
                "pending": resumes_pending,
                "ai_pass": resumes_ai_pass,
                "ai_reject": resumes_ai_reject,
                "manual_pass": resumes_manual_pass,
                "in_pool": resumes_in_pool,
            },
            "interviews": {
                "total": total_interviews,
                "pending": interviews_pending,
                "confirmed": interviews_confirmed,
                "completed": interviews_completed,
                "by_round": interviews_by_round,
            },
            "interviewers": {
                "total": total_interviewers,
                "active": active_interviewers,
            },
            "pipeline": {
                "resumes_in_pool": resumes_in_pool,
                "interviews_total": total_interviews,
                "interviews_completed": interviews_completed,
                "offers_sent": offers_sent,
                "offers_accepted": offers_accepted,
                "onboarded": onboarded,
            },
        }
    finally:
        db.close()
