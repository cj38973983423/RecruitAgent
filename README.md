# RecruitAgent — 全流程招聘智能体

> 基于 LangGraph 状态机的 AI 招聘助手，覆盖招聘全链路

## 架构

```
需求收集 → JD生成 → JD审核 → 简历筛选 → 面试管理 → Offer → 入职
               ↑                        ↑                  ↑
           AI 增强 + RAG          AI 出题 + 评估    名额自动校验
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 工作流引擎 | LangGraph (SqliteSaver) |
| 后端 | FastAPI + SQLite |
| AI 引擎 | DeepSeek (v4 Flash) |
| 前端 | React + TypeScript + Ant Design |
| 构建工具 | Vite |

## 快速开始

### 1. 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 LLM_API_KEY

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://localhost:5173` 即可使用。

## 功能模块

### 📋 岗位管理
- AI 辅助 JD 生成与增强
- 多轮需求澄清
- 岗位名额自动管控

### 📄 简历管理
- 多格式简历上传 (PDF/DOCX)
- AI 自动评分 (技能40%/经验30%/教育15%/契合度15%)
- 按岗位匹配筛选

### 🎙️ 面试管理
- 流水线视图：一面→二面→三面→HR面
- AI 自动出题
- AI 辅助评价草稿
- 快速通过/评估

### 💰 Offer 管理
- 从草稿到入职全流程
- 岗位名额拦截（防止超额发 Offer）
- 候选人去重（有 Offer 的不可重复选择）

## 项目结构

```
recruit-agent/
├── backend/                   # FastAPI 后端
│   ├── app/
│   │   ├── main.py           # 入口 & 路由注册
│   │   ├── config.py         # 配置
│   │   ├── database.py       # 数据库
│   │   ├── models/           # SQLAlchemy 模型
│   │   ├── routers/          # API 路由
│   │   ├── schemas/          # Pydantic 模型
│   │   ├── services/         # 业务逻辑 & LLM 调用
│   │   └── workflows/        # LangGraph 工作流
│   └── requirements.txt
├── frontend/                  # React 前端
│   └── src/
│       ├── api/              # API 封装
│       ├── components/       # 通用组件
│       └── pages/            # 页面
├── docs/                     # 文档
└── scripts/                  # 工具脚本
```
