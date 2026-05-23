"""应用配置"""
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    app_name: str = "RecruitAgent"
    app_version: str = "0.1.0"

    # 数据库（默认 SQLite 本地开发）
    database_url: str = "sqlite:///./recruit_agent.db"

    # Milvus 向量库
    milvus_host: str = "localhost"
    milvus_port: str = "19530"
    milvus_collection: str = "jd_knowledge_base"

    # 嵌入模型
    embedding_model: str = "BAAI/bge-small-zh-v1.5"

    # LLM API（兼容 OpenAI 格式）
    llm_api_key: str = ""                             # API 密钥（通过 .env 或环境变量设置）
    llm_base_url: str = "https://api.deepseek.com"    # API 地址
    llm_model: str = "deepseek-v4-flash"              # 模型名
    llm_timeout: int = 180                            # 超时（秒）

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # CORS
    cors_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # 招聘流程配置
    screening_score_threshold: float = 60.0  # 初筛通过线
    max_jd_clarification_rounds: int = 3     # JD 澄清最大轮数

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
