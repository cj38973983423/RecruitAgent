"""API 路由 — 知识库管理 (JD RAG 知识库)"""
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from typing import List

from app.services.vector_store import vector_store
from app.services.storage import extract_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/knowledge-base", tags=["知识库"])


class KBQuery(BaseModel):
    query: str
    top_k: int = 5


class KBAddRequest(BaseModel):
    title: str
    content: str
    skills: str = ""
    industry: str = ""
    source: str = "manual"


@router.get("/status")
def get_status():
    """知识库状态"""
    try:
        vector_store.connect()
        count = vector_store.count()
        return {
            "status": "connected",
            "total_documents": count,
            "backend": "milvus_lite" if vector_store._milvus_available else "local_fallback",
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(""),
    skills: str = Form(""),
    industry: str = Form(""),
):
    """上传文档到知识库（支持 PDF/DOCX/TXT）"""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else ""

    if ext not in ("pdf", "docx", "doc", "txt"):
        raise HTTPException(status_code=400, detail="仅支持 PDF / DOCX / TXT 格式")

    # 提取文本
    from app.services.storage import save_upload_file
    path = await save_upload_file(file)
    content = extract_text(path, ext)

    if not content or len(content.strip()) < 20:
        raise HTTPException(status_code=400, detail="文件内容提取失败或内容过少")

    # 使用文件名作为标题
    doc_title = title or file.filename.replace(f".{ext}", "")

    # 添加到向量库
    vector_store.connect()
    doc_id = vector_store.add_document(
        title=doc_title,
        content=content,
        skills=skills,
        industry=industry,
        source="upload",
    )

    return {
        "id": doc_id,
        "title": doc_title,
        "content_length": len(content),
        "message": f"「{doc_title}」已加入知识库",
    }


@router.post("/add-text")
def add_text_document(data: KBAddRequest):
    """手动添加文本到知识库"""
    vector_store.connect()
    doc_id = vector_store.add_document(
        title=data.title,
        content=data.content,
        skills=data.skills,
        industry=data.industry,
        source=data.source,
    )
    return {"id": doc_id, "title": data.title, "message": "添加成功"}


@router.post("/search")
def search_knowledge_base(data: KBQuery):
    """搜索知识库"""
    vector_store.connect()
    results = vector_store.search_similar_jd(data.query, data.top_k)
    return {"results": results, "total": len(results)}


@router.get("/documents")
def list_documents():
    """列出知识库所有文档"""
    vector_store.connect()
    docs = vector_store.list_docs()
    return {"documents": docs, "total": len(docs)}


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int):
    """删除知识库文档"""
    vector_store.connect()
    ok = vector_store.delete_doc(doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"message": "删除成功", "id": doc_id}


class BatchDeleteRequest(BaseModel):
    doc_ids: List[int]


@router.post("/documents/batch-delete")
def batch_delete_documents(data: BatchDeleteRequest):
    """批量删除知识库文档"""
    if not data.doc_ids:
        raise HTTPException(status_code=400, detail="请选择要删除的文档")
    vector_store.connect()
    count = vector_store.batch_delete_docs(data.doc_ids)
    return {"message": f"成功删除 {count} 个文档", "deleted_count": count}


@router.post("/seed-standard")
def seed_standard_jds():
    """预置标准 JD 到知识库"""
    from app.services.jd_service import seed_standard_jds as _seed
    vector_store.connect()
    try:
        _seed()
        return {"message": "标准 JD 已预置", "count": vector_store.count()}
    except Exception as e:
        logger.warning(f"预置失败: {e}")
        return {"message": f"预置失败: {e}", "count": 0}
