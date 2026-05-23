"""
全链路测试数据生成
"""
import datetime
import sqlite3

DB = "/home/cj/recruitment-agent/backend/recruit_agent.db"
now = datetime.datetime.utcnow()

def run():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    for t in ['offers','interviews','interview_questions','interview_evaluations',
              'resumes','workflow_states','workflow_logs','job_descriptions','recruitment_requests']:
        c.execute(f"DELETE FROM {t}")

    # ── 1. 招聘需求 ──
    reqs = [
        ("技术部", "前端工程师", 2, "high"),
        ("产品部", "高级产品经理", 1, "urgent"),
        ("基础架构部", "SRE运维工程师", 3, "normal"),
        ("测试部", "测试开发工程师", 2, "normal"),
    ]
    req_ids = []
    for dept, pos, hc, urg in reqs:
        c.execute("INSERT INTO recruitment_requests (department,position_name,headcount,urgency,is_clarified,status,created_at) VALUES (?,?,?,?,1,'ready',?)",
                  (dept, pos, hc, urg, now.isoformat()))
        req_ids.append(c.lastrowid)

    # ── 2. JD ──
    jds = [
        ("前端工程师", "技术部", "精通React/Vue，3年以上经验，有大型项目架构经验",
         '["React","TypeScript","Vue","Webpack"]', '["Three.js","微前端"]', "3-5年", "本科"),
        ("高级产品经理", "产品部", "B端SaaS产品经验，3年以上，有0-1经验",
         '["产品规划","数据分析","用户研究","Axure"]', '["PMP","AI产品"]', "3-5年", "本科"),
        ("SRE运维工程师", "基础架构部", "精通K8s，熟悉云原生，2年以上SRE经验",
         '["Kubernetes","Docker","Linux","Prometheus","Python"]', '["Istio","Terraform"]', "2-5年", "本科"),
        ("测试开发工程师", "测试部", "自动化测试框架开发，Python/Java",
         '["Python","Selenium","Playwright","Pytest"]', '["Jenkins","Docker"]', "2-4年", "本科"),
    ]
    jd_ids = []
    for i,(title,dept,content,skills,nice,exp,edu) in enumerate(jds):
        c.execute("""INSERT INTO job_descriptions
            (request_id,version,title,department,location,content,required_skills,nice_to_have,
             experience_required,education_required,status,created_at)
            VALUES (?,1,?,?,?,?,?,?,?,?,'approved',?)""",
                  (req_ids[i], title, dept, "北京", content, skills, nice, exp, edu, now.isoformat()))
        jd_ids.append(c.lastrowid)

    # ── 3. 简历 ──
    resumes = [
        ("王小明", '["React","TypeScript","Vue","Node.js"]', 4, 88, 1, "manual_pass", jd_ids[0]),
        ("李小红", '["React","Vue","JavaScript"]',            2, 65, 0, "ai_pass",      jd_ids[0]),
        ("张经理", '["产品规划","数据分析","Axure","SQL"]',      5, 92, 1, "manual_pass", jd_ids[1]),
        ("赵运维", '["Kubernetes","Docker","Linux","Prometheus","Python"]', 4, 85, 1, "manual_pass", jd_ids[2]),
        ("钱运维", '["Kubernetes","Docker","Linux","Shell"]',  2, 58, 0, "ai_pass",      jd_ids[2]),
        ("孙测试", '["Python","Selenium","Pytest","Jenkins"]', 3, 78, 1, "manual_pass", jd_ids[3]),
        ("周测试", '["Python","Selenium","Postman"]',         1, 55, 0, "ai_pass",      jd_ids[3]),
    ]
    resume_ids = []
    for name,skills,exp,score,rec,status,jid in resumes:
        c.execute("INSERT INTO resumes (name,skills,experience_years,ai_score,ai_recommended,ai_reason,status,jd_id,file_name,is_duplicate,created_at) VALUES (?,?,?,?,?,?,?,?,?,0,?)",
                  (name, skills, exp, score, bool(rec),
                   f"AI评分{score}分，{'推荐' if rec else '不推荐'}",
                   status, jid, f"{name}_简历.pdf", now.isoformat()))
        resume_ids.append(c.lastrowid)

    # ── 4. 面试 ──
    interviews = [
        (resume_ids[0], jd_ids[0], "first",  "张面试官", "passed",  now+datetime.timedelta(hours=2)),
        (resume_ids[0], jd_ids[0], "second", "李面试官", "passed",  now+datetime.timedelta(days=1)),
        (resume_ids[2], jd_ids[1], "first",  "产品总监", "passed",  now+datetime.timedelta(hours=3)),
        (resume_ids[3], jd_ids[2], "first",  "架构师",   "pending", now+datetime.timedelta(days=2)),
        (resume_ids[5], jd_ids[3], "first",  "测试主管", "passed",  now+datetime.timedelta(hours=1)),
        (resume_ids[0], jd_ids[0], "hr",     "HR张",     "pending", now+datetime.timedelta(days=2,hours=3)),
    ]
    name_map = {resume_ids[i]: resumes[i][0] for i in range(len(resumes))}
    for rid, jid, rnd, iv, st, sched in interviews:
        c.execute("INSERT INTO interviews (resume_id,jd_id,round,interviewer_name,status,candidate_name,scheduled_at,duration_minutes,created_at) VALUES (?,?,?,?,?,?,?,60,?)",
                  (rid, jid, rnd, iv, st, name_map[rid], sched.isoformat(), now.isoformat()))

    # ── 5. Offer ──
    offers = [
        (resume_ids[0], jd_ids[0], "王小明", "前端工程师",     "技术部", "28K·15薪", "onboarded", now+datetime.timedelta(days=3)),
        (resume_ids[2], jd_ids[1], "张经理",  "高级产品经理",   "产品部", "35K·14薪", "onboarded", now+datetime.timedelta(days=2)),
        (resume_ids[5], jd_ids[3], "孙测试",  "测试开发工程师", "测试部", "20K·14薪", "sent",      now+datetime.timedelta(days=1)),
    ]
    for rid, jid, name, pos, dept, sal, st, sent in offers:
        c.execute("INSERT INTO offers (resume_id,jd_id,candidate_name,position_name,department,salary,status,sent_at,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                  (rid, jid, name, pos, dept, sal, st, sent.isoformat(), now.isoformat()))

    conn.commit()
    conn.close()

    # ── 报表 ──
    print("=" * 55)
    print("  📊 全链路测试数据")
    print("=" * 55)
    for r in reqs:
        print(f"  📋 {r[1]:10} 招{r[2]}人 [{r[3]}]")
    for j in jds:
        print(f"  📄 {j[0]:12} ✅ 已审批")
    for r in resumes:
        print(f"  👤 {r[0]:6} [{r[5]:12}] 评分={r[3]} → jd_id={r[6]}")
    for i in interviews:
        print(f"  🎙️ {name_map[i[0]]:6} {i[3]:6} [{i[4]:8}]")
    for o in offers:
        print(f"  💰 {o[2]:6} {o[3]} [{o[6]:10}]")
    print("=" * 55)

if __name__ == "__main__":
    run()
