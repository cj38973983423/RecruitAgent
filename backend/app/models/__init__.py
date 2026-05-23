"""数据模型 — 招聘全链路"""
import datetime
import enum
from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, ForeignKey,
    Enum as SAEnum, JSON, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


def _enum_values(enum_cls):
    """让 SAEnum 存储枚举的 value 而非 name"""
    return [e.value for e in enum_cls]


# ══════════════════════════════════════════════
# 枚举
# ══════════════════════════════════════════════

class WorkflowNode(str, enum.Enum):
    """LangGraph 工作流节点"""
    REQUIREMENT_COLLECT = "requirement_collect"
    JD_GENERATION = "jd_generation"
    JD_REVIEW = "jd_review"
    CHANNEL_PUBLISH = "channel_publish"
    RESUME_COLLECT = "resume_collect"
    RESUME_AI_SCREEN = "resume_ai_screen"
    RESUME_MANUAL_SCREEN = "resume_manual_screen"
    INTERVIEW_SCHEDULE = "interview_schedule"
    INTERVIEW_QUESTIONS = "interview_questions"
    INTERVIEW_EXECUTE = "interview_execute"
    INTERVIEW_EVALUATE = "interview_evaluate"
    OFFER_MANAGE = "offer_manage"
    ONBOARDING = "onboarding"
    COMPLETED = "completed"
    TERMINATED = "terminated"


class RequestStatus(str, enum.Enum):
    DRAFT = "draft"
    CLARIFYING = "clarifying"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class JDStatus(str, enum.Enum):
    DRAFT = "draft"
    REGENERATING = "regenerating"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ResumeStatus(str, enum.Enum):
    PENDING = "pending"
    AI_PASS = "ai_pass"
    AI_REJECT = "ai_reject"
    AI_RECOMMENDED = "ai_recommended"
    MANUAL_PASS = "manual_pass"
    MANUAL_REJECT = "manual_reject"
    INTERVIEWING = "interviewing"
    OFFERED = "offered"
    HIRED = "hired"


class InterviewRound(str, enum.Enum):
    FIRST = "first"
    SECOND = "second"
    THIRD = "third"
    HR = "hr"


class InterviewStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class OfferStatus(str, enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    ONBOARDED = "onboarded"


class InterviewerStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


# ══════════════════════════════════════════════
# 招聘需求
# ══════════════════════════════════════════════

class RecruitmentRequest(Base):
    """招聘需求"""
    __tablename__ = "recruitment_requests"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    department = Column(String(128), nullable=False, comment="需求部门")
    position_name = Column(String(256), nullable=False, comment="职位名称")
    headcount = Column(Integer, default=1, comment="招聘人数")
    urgency = Column(String(32), default="normal", comment="紧急程度: urgent/high/normal/low")

    # 原始需求（业务部门填写）
    raw_requirements = Column(Text, nullable=True, comment="原始需求描述")
    budget_range = Column(String(128), nullable=True, comment="薪资预算范围")

    # 多轮澄清记录
    clarification_history = Column(JSON, default=list, comment="澄清问答记录 [{q, a, round}]")
    clarification_round = Column(Integer, default=0, comment="当前澄清轮次")
    is_clarified = Column(Boolean, default=False, comment="是否已完成澄清")

    # 最终确认需求
    finalized_requirements = Column(Text, nullable=True, comment="最终确认的需求")
    enhanced_jd = Column(Text, nullable=True, comment="AI 增强后的 JD 描述")

    status = Column(SAEnum(RequestStatus, values_callable=_enum_values), default=RequestStatus.DRAFT)
    created_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 关联
    jds = relationship("JobDescription", back_populates="request", cascade="all, delete-orphan")


# ══════════════════════════════════════════════
# JD 描述
# ══════════════════════════════════════════════

class JobDescription(Base):
    """JD 描述 （含版本管理）"""
    __tablename__ = "job_descriptions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("recruitment_requests.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, default=1, comment="JD 版本号")

    # JD 内容
    title = Column(String(256), nullable=False)
    department = Column(String(128))
    location = Column(String(128))
    content = Column(Text, nullable=False, comment="JD 全文")
    required_skills = Column(Text, nullable=True, comment="必备技能 JSON")
    nice_to_have = Column(Text, nullable=True, comment="加分技能 JSON")
    experience_required = Column(String(64))
    education_required = Column(String(64))
    responsibilities = Column(Text, nullable=True, comment="岗位职责（结构化 JSON）")
    requirements_list = Column(Text, nullable=True, comment="任职要求（结构化 JSON）")

    # AI 增强相关
    original_content = Column(Text, nullable=True, comment="AI 增强前的原始 JD")
    enhancement_log = Column(JSON, nullable=True, comment="增强记录")

    # 向量库同步
    vector_id = Column(String(128), nullable=True, comment="Milvus 向量 ID")
    vector_synced = Column(Boolean, default=False)

    # 状态
    status = Column(SAEnum(JDStatus, values_callable=_enum_values), default=JDStatus.DRAFT)
    review_comment = Column(Text, nullable=True, comment="审核意见")
    reviewed_by = Column(String(128), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    request = relationship("RecruitmentRequest", back_populates="jds")


# ══════════════════════════════════════════════
# 简历
# ══════════════════════════════════════════════

class Resume(Base):
    """候选人简历"""
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    jd_id = Column(Integer, ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True)

    # 基本信息
    name = Column(String(128), index=True)
    phone = Column(String(32))
    email = Column(String(128))
    skills = Column(Text, comment="技能列表 JSON")
    experience_years = Column(Float)
    education = Column(Text, comment="教育经历 JSON")
    work_experience = Column(Text, comment="工作经历 JSON")

    # 文件
    file_path = Column(String(512))
    file_name = Column(String(256))
    file_type = Column(String(16))
    raw_text = Column(Text)

    # 深度分析结果
    deep_analysis = Column(JSON, nullable=True, comment=(
        "深度分析结果 JSON: {\n"
        "  project_authenticity: {score, flags, details},  # 项目真实性\n"
        "  job_fit: {score, reason},                        # 职责匹配度\n"
        "  career_trajectory: {score, trend, analysis},     # 晋升轨迹\n"
        "  risk_warnings: [                                 # 风险预警\n"
        "    {type, severity, detail}\n"
        "  ],\n"
        "  frequent_job_change: bool,                       # 频繁跳槽\n"
        "  resume_consistency: {score, issues}              # 简历一致性\n"
        "}"
    ))

    # AI 评分
    ai_score = Column(Float, comment="AI 综合评分 0-100")
    ai_score_detail = Column(Text, comment="四维度评分详情 JSON")
    ai_reason = Column(Text, comment="AI 推荐理由")
    ai_recommended = Column(Boolean, default=False)

    # 人工筛选
    status = Column(SAEnum(ResumeStatus, values_callable=_enum_values), default=ResumeStatus.PENDING)
    notes = Column(Text, nullable=True, comment="HR 内部备注")
    review_note = Column(Text)
    reviewed_by = Column(String(128))
    reviewed_at = Column(DateTime, nullable=True)

    # 查重
    duplicate_group = Column(String(64), nullable=True, comment="查重组标识")
    is_duplicate = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# ══════════════════════════════════════════════
# 面试
# ══════════════════════════════════════════════

class Interview(Base):
    """面试安排"""
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    jd_id = Column(Integer, ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True)

    round = Column(SAEnum(InterviewRound, values_callable=_enum_values), default=InterviewRound.FIRST)
    interviewer_name = Column(String(128), comment="面试官姓名")
    interviewer_email = Column(String(128))
    candidate_name = Column(String(128))
    candidate_email = Column(String(128))
    candidate_phone = Column(String(32))

    scheduled_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, default=60)
    location = Column(String(256), comment="面试地点 / 线上链接")
    meeting_link = Column(String(512))

    status = Column(SAEnum(InterviewStatus, values_callable=_enum_values), default=InterviewStatus.PENDING)
    notes = Column(Text)

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 关联
    questions = relationship("InterviewQuestion", back_populates="interview", cascade="all, delete-orphan")
    evaluations = relationship("InterviewEvaluation", back_populates="interview", cascade="all, delete-orphan")


class InterviewQuestion(Base):
    """面试题"""
    __tablename__ = "interview_questions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(32), comment="tech / behavioral / scene / soft_skill")
    difficulty = Column(String(16), comment="basic / intermediate / advanced")
    question_text = Column(Text, nullable=False)
    expected_answer = Column(Text, nullable=True, comment="参考答案 / 评分标准")
    created_by = Column(String(16), default="ai", comment="ai / manual")
    is_used = Column(Boolean, default=False)

    interview = relationship("Interview", back_populates="questions")


class InterviewEvaluation(Base):
    """面试评价"""
    __tablename__ = "interview_evaluations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    interview_id = Column(Integer, ForeignKey("interviews.id", ondelete="CASCADE"), nullable=False)
    evaluator = Column(String(128), comment="评价人（面试官）")
    tech_score = Column(Float, comment="技术能力评分")
    communication_score = Column(Float, comment="沟通能力评分")
    overall_score = Column(Float, comment="综合评分")
    strengths = Column(Text, comment="优势")
    weaknesses = Column(Text, comment="不足")
    conclusion = Column(Text, comment="面试结论")
    recommendation = Column(String(32), comment="推荐结果: pass / hold / reject")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    interview = relationship("Interview", back_populates="evaluations")


# ══════════════════════════════════════════════
# Offer
# ══════════════════════════════════════════════

class Offer(Base):
    """Offer 管理"""
    __tablename__ = "offers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    resume_id = Column(Integer, ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True)
    jd_id = Column(Integer, ForeignKey("job_descriptions.id", ondelete="SET NULL"), nullable=True)
    candidate_name = Column(String(128))
    position_name = Column(String(256))
    department = Column(String(128))
    salary = Column(String(128), comment="薪资方案")
    equity = Column(String(128), nullable=True, comment="股权/期权")
    start_date = Column(DateTime, nullable=True)
    status = Column(SAEnum(OfferStatus, values_callable=_enum_values), default=OfferStatus.DRAFT)
    sent_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    rejected_at = Column(DateTime, nullable=True)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# ══════════════════════════════════════════════
# 面试官库
# ══════════════════════════════════════════════

class Interviewer(Base):
    """面试官"""
    __tablename__ = "interviewers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(128), nullable=False, index=True, comment="面试官姓名")
    email = Column(String(256), nullable=True, comment="邮箱")
    phone = Column(String(32), nullable=True, comment="手机号")
    position = Column(String(128), nullable=True, comment="职位/职称")
    department = Column(String(128), nullable=True, comment="所属部门")
    skills = Column(Text, nullable=True, comment="擅长领域/技术栈 JSON")
    interview_count = Column(Integer, default=0, comment="累计面试次数")
    rating = Column(Float, nullable=True, comment="综合评分")
    notes = Column(Text, nullable=True, comment="备注")
    status = Column(SAEnum(InterviewerStatus, values_callable=_enum_values), default=InterviewerStatus.ACTIVE)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


# ══════════════════════════════════════════════
# 工作流日志
# ══════════════════════════════════════════════

class WorkflowLog(Base):
    """工作流运行日志"""
    __tablename__ = "workflow_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("recruitment_requests.id", ondelete="CASCADE"), nullable=False)
    node = Column(String(64), nullable=False, comment="当前节点")
    status = Column(String(32), default="running", comment="running / completed / failed / skipped")
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)


class WorkflowStateDB(Base):
    """工作流状态持久化（替代内存存储）"""
    __tablename__ = "workflow_states"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    request_id = Column(Integer, ForeignKey("recruitment_requests.id", ondelete="CASCADE"), nullable=False)
    workflow_type = Column(String(32), default="jd_generation", comment="jd_generation / resume_screening")
    state_json = Column(JSON, nullable=False, comment="完整工作流状态 JSON")
    current_node = Column(String(64))
    status = Column(String(32), default="running")
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    __table_args__ = (
        # 同一个 request 可以有 JD 工作流和筛选工作流
        UniqueConstraint("request_id", "workflow_type", name="uq_request_workflow"),
    )
