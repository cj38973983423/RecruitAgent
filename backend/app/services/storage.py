"""文件存储和文本提取 — 集成 MinerU 文档解析"""

import os
import aiofiles
import logging
from fastapi import UploadFile
from app.config import settings

logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def save_upload_file(file: UploadFile) -> str:
    """保存上传文件，返回相对路径"""
    safe_name = f"{os.urandom(8).hex()}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)
    async with aiofiles.open(file_path, "wb") as f:
        content = await file.read()
        await f.write(content)
    return safe_name


def get_full_path(file_path: str) -> str:
    """将相对路径转为绝对路径"""
    if file_path.startswith("/"):
        return file_path
    return os.path.join(UPLOAD_DIR, file_path)


def extract_text(file_path: str, file_type: str) -> str:
    """提取文本内容 — 委托给 MinerU document_parser"""
    from app.services.document_parser import extract_text as parser_extract
    return parser_extract(file_path, file_type)
