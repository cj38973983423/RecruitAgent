"""简历深度分析服务 — 项目真实性、风险预警、晋升轨迹"""
import json
import logging
from typing import Optional

from app.services.llm_service import call_llm_json

logger = logging.getLogger(__name__)

SCREENING_SYSTEM_PROMPT = """你是一位资深的招聘专家和简历分析师。
请对简历进行深度分析，识别风险点，评估候选人质量。
分析必须客观、准确、有依据。"""


def analyze_resume_deep(raw_text: str, jd_content: Optional[str] = None) -> dict:
    """简历深度分析：项目真实性 + 职责匹配 + 晋升轨迹 + 风险预警"""
    jd_section = f"\n目标职位描述：\n{jd_content[:2000]}" if jd_content else ""

    prompt = f"""请对以下简历进行深度分析，返回 JSON 格式。

{jd_section}

简历内容：
{raw_text[:4000]}

请分析以下维度：

1. **project_authenticity** (项目真实性):
   - score: 0-100, 项目描述是否具体、可验证
   - flags: 可疑信号列表（如"参与"而非"负责"、缺少量化数据、公司名称模糊）
   - details: 详细分析

2. **job_fit** (职责匹配度):
   - score: 0-100
   - matching_points: 与 JD 匹配的点
   - gap_points: 差距点

3. **career_trajectory** (职业晋升轨迹):
   - score: 0-100 (0=原地踏步, 100=快速成长)
   - trend: "上升" / "平稳" / "下降" / "不明"
   - analysis: 晋升路径分析

4. **risk_warnings** (风险预警):
   - 数组，每项包含 {{type, severity("high"/"medium"/"low"), detail}}
   - 自动识别：频繁跳槽、简历造假嫌疑、空档期、跨行业跨度过大等

5. **frequent_job_change**: true/false (是否频繁跳槽，定义：近5年换工作超过3次)

6. **resume_consistency**: {{score, issues[]}} (简历内部一致性)

请只返回 JSON。"""

    result = call_llm_json(prompt, system_prompt=SCREENING_SYSTEM_PROMPT, timeout=180)
    return result


def ai_initial_screening(raw_text: str, jd_content: str,
                         required_skills: list[str]) -> dict:
    """AI 初筛：判断是否通过硬性条件"""
    skills_str = "、".join(required_skills) if required_skills else "无明确要求"

    prompt = f"""请对以下简历进行初步筛选，判断是否符合以下硬性要求：

【必备技能】：{skills_str}

【JD 摘要】：
{jd_content[:1500]}

【简历】：
{raw_text[:3000]}

请返回 JSON：
{{
    "passed": true/false,
    "reject_reason": "如果不通过，写明原因；如果通过则留空",
    "score": 0-100,
    "score_detail": {{
        "skill_match": 0-100,
        "experience_match": 0-100,
        "education_match": 0-100,
        "overall_fit": 0-100
    }},
    "summary": "30字以内的候选人亮点",
    "recommendation": "推荐理由（50字以内）"
}}"""

    result = call_llm_json(prompt, timeout=120)
    return result


def generate_interview_questions(jd_content: str, resume_text: str,
                                 question_count: int = 5) -> list[dict]:
    """基于 JD + 简历生成面试题"""
    prompt = f"""请基于以下【职位描述】和【候选人简历】，生成 {question_count} 道高质量的面试题。

涵盖不同类型：
- 技术题（考察硬技能）
- 项目题（考察实战经验）
- 场景题（考察问题解决能力）
- 软技能题（考察沟通/协作/抗压）

【职位描述】：
{jd_content[:2000]}

【候选人简历】：
{resume_text[:2000]}

请返回 JSON 数组：
[
    {{
        "category": "tech / project / scene / soft_skill",
        "difficulty": "basic / intermediate / advanced",
        "question": "问题内容",
        "expected_answer": "参考答案 / 考察要点",
        "reason": "为什么问这个问题（基于简历哪段经历）"
    }}
]"""

    result = call_llm_json(prompt, timeout=180)
    if isinstance(result, list):
        return result
    # 可能包在某个 key 下
    for key in ["questions", "items", "data"]:
        if isinstance(result.get(key), list):
            return result[key]
    return []
