"""JD 增强服务 — RAG + 联网搜索 + 多轮澄清 + AI 润色 + 严格修改"""

import json
import logging
import re
from typing import Optional

from app.services.llm_service import call_llm, call_llm_json, call_llm_plain
from app.services.vector_store import vector_store

logger = logging.getLogger(__name__)

JD_SYSTEM_PROMPT = """你是一位资深的招聘专家和 JD 写作专家。
你擅长从模糊的需求中提炼出清晰、结构化的职位描述。
你的输出必须专业、准确、有吸引力。"""

REGENERATE_SYSTEM_PROMPT = None


# ══════════════════════════════════════════════
# 联网搜索（DuckDuckGo，零 API Key）
# ══════════════════════════════════════════════

def web_search_jd(query: str, num_results: int = 5) -> list[dict]:
    """联网搜索岗位相关信息，返回 [{title, snippet, url}]（搜狗搜索，国内可用）"""
    try:
        from app.services.web_search import sogou_search
        return sogou_search(query, num_results)
    except Exception as e:
        logger.warning(f"[WebSearch] 联网搜索失败: {e}")
        return []


def save_web_results_to_kb(query: str, results: list[dict], industry: str = ""):
    """将联网搜索结果存入向量知识库，供后续 RAG 使用"""
    if not results:
        return 0
    saved = 0
    for r in results:
        title = r.get("title", "")
        snippet = r.get("snippet", "")
        content = f"{title}\n{snippet}"
        if len(content.strip()) < 30:
            continue
        try:
            vector_store.add_document(
                title=f"[联网] {title[:60]}",
                content=content,
                skills="",
                industry=industry or "互联网/科技",
                source="web_search",
            )
            saved += 1
        except Exception as e:
            logger.warning(f"[WebSearch] 保存搜索文档失败: {e}")
    logger.info(f"[WebSearch] 已存入知识库: {saved}/{len(results)} 条")
    return saved


# ══════════════════════════════════════════════
# 增强结果质检（防止 AI 偷懒直接复读）
# ══════════════════════════════════════════════

def _is_identical_output(output: str, original: str, threshold: float = 0.80) -> bool:
    """判断增强输出是否和原始输入过于相似（文本重合度检测）"""
    if not output or not original:
        return False
    clean = lambda s: re.sub(r'[\s，。！？、；：""''（）【】《》,.!?;:()\[\]{}]', '', s).strip()
    o = clean(output)
    r = clean(original)
    if not o or not r:
        return False
    shorter = min(len(o), len(r))
    if shorter < 10:
        return o == r
    common = sum(1 for a, b in zip(o, r) if a == b)
    ratio = common / shorter
    return ratio >= threshold


# ══════════════════════════════════════════════
# 生成澄清问题
# ══════════════════════════════════════════════

def generate_clarification_questions(raw_requirements: str,
                                     history: list[dict] | None = None,
                                     round_num: int = 1) -> list[dict]:
    """基于当前需求生成澄清问题"""
    history_text = ""
    if history:
        history_text = "\n历史对话：\n"
        for h in history:
            history_text += f"Q: {h.get('q')}\nA: {h.get('a')}\n"

    prompt = f"""你正在与业务部门沟通招聘需求，当前信息如下：

【原始需求】：
{raw_requirements or "（暂无详细需求）"}
{history_text}

【当前轮次】：第 {round_num} 轮

请分析当前信息中不明确、有歧义、缺失的关键信息，生成 2-4 个澄清问题。
问题应该帮助补齐以下关键信息：
- 岗位的核心职责和日常产出
- 技术栈和工具要求
- 团队规模和管理职责
- 项目类型和业务场景
- 软性素质要求
- 吸引候选人的亮点

请返回 JSON 数组：
[
    {{"question_id": "q1", "question": "问题内容", "reason": "为什么要问这个"}},
    ...
]"""

    result = call_llm_json(prompt, system_prompt=JD_SYSTEM_PROMPT, timeout=120)
    if isinstance(result, list):
        return result
    for key in ["questions", "items"]:
        if isinstance(result.get(key), list):
            return result[key]
    return []


# ══════════════════════════════════════════════
# JD 增强（RAG → 联网兜底 → AI 润色）
# ══════════════════════════════════════════════

def enhance_jd_with_rag(raw_jd: str, industry: str = "",
                        additional_context: str = "",
                        max_retries: int = 2) -> dict:
    """AI 增强 JD：RAG 检索 → 不足时联网搜索 → AI 润色

    流程：
      1. 从向量库检索相似 JD
      2. 如果结果为空或相似度过低 → 联网搜索并存入知识库
      3. AI 基于所有上下文增强 JD
      4. 校验输出是否与输入雷同 → 重试
    """
    similar_jds = vector_store.search_similar_jd(raw_jd, top_k=3)

    rag_context = ""
    need_web_search = False

    # ── 判断 RAG 结果质量 ──
    if not similar_jds:
        logger.info("[JD增强] 向量库无匹配结果，需要联网搜索")
        need_web_search = True
    else:
        # 检查最高分是否过低（哈希嵌入的分数普遍偏低，用 0.15 作为阈值）
        top_score = similar_jds[0].get("score", 0)
        if top_score < 0.15:
            logger.info(f"[JD增强] 向量库匹配分偏低 ({top_score:.3f})，触发联网搜索")
            need_web_search = True
        else:
            rag_context = "\n\n【行业参考 JD（基于向量检索）】：\n"
            for i, ref in enumerate(similar_jds, 1):
                rag_context += f"\n--- 参考 {i}: {ref.get('job_title', '')} (相似度: {ref.get('score', 0):.3f}) ---\n"
                rag_context += ref.get('content', '')[:800] + "\n"

    # ── 联网搜索兜底 ──
    web_context = ""
    if need_web_search:
        # 从 raw_jd 提取关键词作为搜索查询（取前 80 字）
        query = raw_jd.strip()[:80]
        search_results = web_search_jd(query)
        if search_results:
            # 存入知识库
            save_web_results_to_kb(query, search_results, industry)
            # 组装为上下文
            web_context = "\n\n【联网搜索参考信息】：\n"
            for i, r in enumerate(search_results, 1):
                title = r.get("title", "")
                snippet = r.get("snippet", "")
                if snippet:
                    web_context += f"\n--- 网络来源 {i}: {title} ---\n{snippet[:600]}\n"

    extra = f"\n【额外补充信息】：{additional_context}" if additional_context else ""

    # ── 组装完整上下文 ──
    context = rag_context + web_context

    prompt = f"""请对以下职位描述进行专业增强。

【原始 JD】：
{raw_jd}
{extra}
{context}

【要求】
1. **必须增强**输出的内容，不能和原始 JD 雷同
2. **结构化** — 拆分为"岗位职责"和"任职要求"两个列表
3. **润色** — 让语言更专业、吸引人，但不要夸大或虚假
4. **补充** — 基于行业参考或联网信息，补充该岗位常见的职责和要求
5. **市场对标** — 标注每条要求是"必备"还是"加分"
6. **技能分级** — 将技能按重要性分为 P0(必备)、P1(重要)、P2(加分)
7. **行业洞察** — 如果提供了联网搜索信息，请基于它们补充行业趋势和市场数据

请只返回一个有效的 JSON 对象，不要任何开场白、解释、Markdown 格式或其它文字：

{{
    "enhanced_jd": "完整的增强后 JD 文本（包含岗位职责和任职要求的完整描述，必须和原始 JD 显著不同）",
    "responsibilities": ["职责1", "职责2", ...],
    "requirements": ["要求1", "要求2", ...],
    "skills_matrix": {{
        "p0_required": ["技能1", ...],
        "p1_important": ["技能2", ...],
        "p2_plus": ["技能3", ...]
    }},
    "market_insights": "基于参考和联网信息的市场洞察（薪资、趋势等）",
    "suggested_title": "建议的职位名称"
}}"""

    # ── 尝试生成，最多重试 max_retries 次 ──
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            text = call_llm_plain(prompt, timeout=180)
            result = json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group())
                except json.JSONDecodeError:
                    result = None
            else:
                result = None

        if not result:
            last_error = "AI 返回非 JSON 格式"
            logger.warning(f"[JD增强] 第 {attempt+1} 次尝试解析失败")
            continue

        enhanced_text = result.get("enhanced_jd", "")

        # ── 质检：不能和原始输入雷同 ──
        if _is_identical_output(enhanced_text, raw_jd):
            last_error = f"输出与原始内容过于相似 (attempt {attempt+1})"
            logger.warning(f"[JD增强] {last_error}，重试中...")
            # 更强硬的提示
            prompt += f"\n\n⚠️ 警告：上轮输出与原始 JD 太相似了（{attempt+1}次）。必须大幅改写！请补充岗位细节、市场数据，至少 500 字。"
            continue

        # 成功！
        if attempt > 0:
            logger.info(f"[JD增强] 第 {attempt+1} 次尝试成功")
        return result

    # 所有重试都失败，兜底
    logger.warning(f"[JD增强] 所有重试均失败 ({last_error})，使用结构兜底")
    return {
        "enhanced_jd": f"# 职位描述\n\n## 岗位职责\n- 负责相关业务模块的设计、开发和维护\n\n## 任职要求\n- 相关领域经验\n\n*（基于以下原始需求自动生成）*\n\n{raw_jd}",
        "responsibilities": ["负责相关业务模块的设计、开发和维护"],
        "requirements": ["相关领域经验"],
    }


# ══════════════════════════════════════════════
# 严格修改 JD
# ══════════════════════════════════════════════

def regenerate_jd_with_hints(original_jd: str, modification_hints: str) -> dict:
    """严格按修改建议重新生成 JD，带逐条校验"""

    system_prompt = """你是 JD 修改执行器，不是聊天助手。

【核心规则】
1. 用户给出的修改要求是**硬性指令**，每条都必须执行
2. 输出**只包含修改后的 JD 文本**，不要任何开场白、解释、备注
3. 原 JD 中与修改要求冲突的内容必须修改
4. 原 JD 中未被修改要求涉及的内容尽量保留
5. 如果你无法执行某条指令，在原位置添加注释说明"""

    prompt = f"""修改以下职位描述，严格遵循所有修改要求。

【原 JD】：
{original_jd}

【修改要求（必须全部执行）】：
{modification_hints}

直接输出修改后的完整 JD，不要任何多余文字。"""

    text = call_llm_plain(prompt, system_prompt=system_prompt, timeout=180)

    # 清理 AI 可能的多余开场白
    lines = text.strip().split("\n")
    cleaned_lines = []
    started = False
    for line in lines:
        if not started:
            stripped = line.strip()
            if stripped and not stripped.startswith(("没问题", "好的", "收到", "明白", "指令", "保证", "直接", "---", "```")):
                if stripped.startswith(("#", "【", "岗位", "职责", "任职", "要求")):
                    started = True
                    cleaned_lines.append(line)
                elif not stripped:
                    continue
                else:
                    started = True
                    cleaned_lines.append(line)
            continue
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines).strip()

    if text and len(text) > 20:
        logger.info(f"[JD修改] AI 严格修改完成，输出长度: {len(text)}字")

        # 校验每条修改要求是否落实
        hints_lines = [h.strip() for h in modification_hints.strip().split("\n") if h.strip()]
        missing_hints = []
        for hint in hints_lines:
            hint_clean = hint.lstrip("0123456789.、- )）")
            if not hint_clean:
                continue
            text_no_space = re.sub(r'\s+', '', text)

            if "去掉" in hint_clean or "删除" in hint_clean or "移除" in hint_clean:
                target = hint_clean.replace("去掉", "").replace("删除", "").replace("移除", "").strip()
                target_ns = re.sub(r'\s+', '', target)
                if target_ns and target_ns in text_no_space:
                    missing_hints.append(f"✗ 要求删除「{target}」，但输出中仍存在")
            elif "改为" in hint_clean or "改成" in hint_clean or "调整" in hint_clean:
                parts = re.split(r'改为|改成|调整为?', hint_clean)
                if len(parts) >= 2:
                    target_val = parts[-1].strip().rstrip("。，,.")
                    target_ns = re.sub(r'\s+', '', target_val)
                    if target_val and len(target_val) > 1 and target_ns not in text_no_space:
                        missing_hints.append(f"✗ 要求改为「{target_val}」，但输出中未找到")
            elif "新增" in hint_clean or "增加" in hint_clean or "添加" in hint_clean or "加" in hint_clean:
                target = re.split(r'新增|增加|添加|加', hint_clean)[-1].strip().lstrip("。，, ").rstrip("。，, ")
                target_ns = re.sub(r'\s+', '', target)
                for kw in target.split():
                    kw = kw.strip().rstrip("，。,.")
                    kw_ns = re.sub(r'\s+', '', kw)
                    if len(kw_ns) >= 2 and kw_ns not in text_no_space:
                        missing_hints.append(f"✗ 要求新增「{kw}」，但输出中未找到")
                        break

        if missing_hints:
            correction = "\n".join(missing_hints)
            logger.warning(f"[JD修改] 未完全执行，发送修正指令:\n{correction}")
            fix_prompt = f"""你之前修改的 JD 有以下问题：

{correction}

原 JD 内容：
{original_jd}

请修正上述问题，输出完整的修正后 JD（不要省略任何部分，直接输出完整文本）。"""
            text2 = call_llm_plain(fix_prompt, system_prompt=system_prompt, timeout=180)
            if text2 and len(text2) > 20:
                text = text2
                logger.info(f"[JD修改] AI 修正完成，长度: {len(text2)}字")

        return {"enhanced_jd": text, "responsibilities": [], "requirements": []}

    logger.warning(f"[JD修改] AI 输出过短或为空，使用原内容兜底")
    return {"enhanced_jd": original_jd, "responsibilities": [], "requirements": []}


# ══════════════════════════════════════════════
# 向量库工具
# ══════════════════════════════════════════════

def get_standard_jd_by_title(job_title: str) -> list[dict]:
    """从向量库检索同岗位的标准 JD"""
    return vector_store.search_similar_jd(job_title, top_k=5)


def seed_standard_jds():
    """预置一批标准 JD 到向量库（首次初始化用）"""
    standard_jds = [
        {
            "title": "高级 Python 后端工程师",
            "industry": "互联网/科技",
            "content": """岗位职责：
1. 负责公司核心业务系统的后端架构设计与开发
2. 参与高并发、高可用分布式系统的设计与优化
3. 编写高质量的代码和单元测试，保证系统稳定性
4. 参与技术方案评审和代码审查
5. 指导初中级开发工程师

任职要求：
1. 本科及以上学历，计算机相关专业
2. 5 年以上 Python 开发经验，3 年以上后端架构经验
3. 精通 FastAPI / Django / Flask 等 Web 框架
4. 熟悉 PostgreSQL、Redis、消息队列等中间件
5. 有微服务架构和容器化部署经验（Docker / K8s）
6. 良好的系统设计能力和沟通协作能力""",
            "skills": "Python,FastAPI,Django,PostgreSQL,Redis,Docker,Kubernetes,微服务",
        },
        {
            "title": "前端开发工程师",
            "industry": "互联网/科技",
            "content": """岗位职责：
1. 负责 Web 前端架构设计和核心功能开发
2. 与产品、设计、后端协作，高质量交付产品
3. 参与前端基础设施建设，提升开发效率
4. 持续优化页面性能和用户体验

任职要求：
1. 3 年以上前端开发经验
2. 精通 React / Vue 等主流框架
3. 熟悉 TypeScript，有大型项目实践经验
4. 了解前端工程化（Webpack / Vite）
5. 有性能优化和组件库建设经验优先""",
            "skills": "React,Vue,TypeScript,Webpack,Vite,前端工程化",
        },
        {
            "title": "产品经理",
            "industry": "互联网/科技",
            "content": """岗位职责：
1. 负责产品的需求分析、产品规划和设计
2. 撰写 PRD，协调研发、设计、测试等团队推进产品上线
3. 分析产品数据，持续优化产品体验
4. 关注行业动态和竞品分析

任职要求：
1. 3-5 年产品经理经验
2. 具备优秀的需求分析和文档撰写能力
3. 熟悉产品设计工具（Figma / Axure）
4. 有数据驱动产品的思维方式
5. 有 B 端或 SaaS 产品经验优先""",
            "skills": "产品设计,PRD,数据分析,Figma,需求分析",
        },
        {
            "title": "数据分析师",
            "industry": "互联网/科技",
            "content": """岗位职责：
1. 负责业务数据的采集、清洗、分析和可视化
2. 搭建数据指标体系，输出数据报告
3. 通过数据分析发现业务增长点和优化方向
4. 与产品、运营团队协作，推动数据驱动的决策

任职要求：
1. 2 年以上数据分析经验
2. 精通 SQL，能独立完成复杂查询
3. 熟悉 Python 数据分析工具（Pandas / NumPy）
4. 熟悉数据可视化工具（Tableau / PowerBI / Superset）
5. 有 AB 测试和用户增长分析经验优先""",
            "skills": "SQL,Python,Pandas,Tableau,数据分析,AB测试",
        },
    ]

    vector_store.connect()
    for jd in standard_jds:
        try:
            vector_store.add_jd(
                jd_id=0,
                jd_title=jd["title"],
                content=jd["content"],
                skills=jd["skills"],
                industry=jd["industry"],
                source="standard",
            )
        except Exception as e:
            logger.warning(f"种子 JD 写入失败: {jd['title']} - {e}")

    logger.info(f"已预置 {len(standard_jds)} 个标准 JD 到向量库")
