"""向量存储服务 — Milvus Lite 本地嵌入（零外部依赖）

架构：
  ┌─────────────────────────────────────┐
  │  VectorStore                         │
  │  ┌─────────────────────────────────┐ │
  │  │  Milvus Lite (primary)          │ │
  │  │  pymilvus.connections.connect() │ │
  │  └──────────────┬──────────────────┘ │
  │                 │ 失败时降级          │
  │  ┌──────────────▼──────────────────┐ │
  │  │  LocalNumpyStore (fallback)     │ │
  │  │  纯 numpy + pickle, 持久化到文件 │ │
  │  └─────────────────────────────────┘ │
  └─────────────────────────────────────┘
"""
import json
import logging
import os
import pickle
import time
from pathlib import Path
from typing import List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# 数据目录
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
os.makedirs(DATA_DIR, exist_ok=True)

MILVUS_DB_DIR = os.path.join(DATA_DIR, "milvus_db")
FALLBACK_PATH = os.path.join(DATA_DIR, "vector_store.pkl")

EMBEDDING_DIM = 768


# ══════════════════════════════════════════════
# 简易哈希嵌入（不依赖任何 ML 库）
# ══════════════════════════════════════════════

def _simple_embed(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """基于哈希的确定性嵌入，零外部依赖"""
    import hashlib
    import struct

    vec = [0.0] * dim
    words = text.lower().split()[:128]
    for i, word in enumerate(words):
        h = hashlib.md5(word.encode()).digest()
        # 每个词影响多个维度
        for j in range(8):
            idx = (i * 8 + j) % dim
            val = struct.unpack_from("!f", h, (j * 4) % 16)[0]
            vec[idx] += val / 100.0

    # L2 归一化
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


# ══════════════════════════════════════════════
# 降级方案：本地 Numpy 向量存储
# ══════════════════════════════════════════════

class LocalNumpyStore:
    """纯 Python 本地向量存储（无外部依赖）"""

    def __init__(self):
        self.documents: list[dict] = []  # [{id, title, content, skills, source, embedding}]
        self._next_id = 1
        self._load()

    def _load(self):
        if os.path.exists(FALLBACK_PATH):
            try:
                with open(FALLBACK_PATH, "rb") as f:
                    data = pickle.load(f)
                    self.documents = data.get("docs", [])
                    self._next_id = data.get("next_id", 1)
                logger.info(f"Loaded {len(self.documents)} docs from local store")
            except Exception as e:
                logger.warning(f"Failed to load local store: {e}")

    def _save(self):
        try:
            with open(FALLBACK_PATH, "wb") as f:
                pickle.dump({"docs": self.documents, "next_id": self._next_id}, f)
        except Exception as e:
            logger.warning(f"Failed to save local store: {e}")

    def add(self, title: str, content: str, skills: str = "",
            industry: str = "", source: str = "manual") -> int:
        doc_id = self._next_id
        self._next_id += 1
        embedding = _simple_embed(title + " " + content[:2048])
        self.documents.append({
            "id": doc_id,
            "title": title,
            "content": content,
            "skills": skills,
            "industry": industry,
            "source": source,
            "embedding": embedding,
            "created_at": time.time(),
        })
        self._save()
        return doc_id

    def search(self, query: str, top_k: int = 5) -> List[dict]:
        if not self.documents:
            return []
        q_emb = _simple_embed(query)
        scored = []
        for doc in self.documents:
            emb = doc.get("embedding", [])
            if not emb:
                continue
            # 余弦相似度
            dot = sum(a * b for a, b in zip(q_emb, emb))
            n1 = sum(v * v for v in q_emb) ** 0.5
            n2 = sum(v * v for v in emb) ** 0.5
            sim = dot / (n1 * n2 + 1e-10) if n1 > 0 and n2 > 0 else 0
            scored.append((sim, doc))

        scored.sort(key=lambda x: -x[0])
        results = []
        for sim, doc in scored[:top_k]:
            results.append({
                "id": doc["id"],
                "score": float(sim),
                "job_title": doc.get("title", ""),
                "industry": doc.get("industry", ""),
                "content": doc.get("content", "")[:500],
                "skills": doc.get("skills", ""),
                "source": doc.get("source", ""),
            })
        return results

    def delete(self, doc_id: int) -> bool:
        before = len(self.documents)
        self.documents = [d for d in self.documents if d.get("id") != doc_id]
        if len(self.documents) < before:
            self._save()
            return True
        return False

    def list_all(self) -> List[dict]:
        return [
            {"id": d["id"], "title": d.get("title", ""),
             "industry": d.get("industry", ""), "source": d.get("source", ""),
             "skills": d.get("skills", ""), "created_at": d.get("created_at")}
            for d in self.documents
        ]

    def count(self) -> int:
        return len(self.documents)


# ══════════════════════════════════════════════
# 统一向量存储接口
# ══════════════════════════════════════════════

class VectorStore:
    """向量存储（优先 Milvus Lite，降级本地存储）"""

    def __init__(self):
        self._milvus_available = False
        self._local = LocalNumpyStore()
        self._connected = False

    def connect(self):
        """初始化存储后端（纯本地模式，零外部依赖）"""
        if self._connected:
            return

        # 直接使用本地存储
        self._connected = True
        self._milvus_available = False
        logger.info("✅ Vector store: local (numpy-based, zero dependencies)")

    @property
    def _collection(self):
        if not hasattr(self, '_collection_ref'):
            return None
        return self._collection_ref

    def add_jd(self, jd_id: int, jd_title: str, content: str,
               skills: str = "", industry: str = "", source: str = "manual") -> Optional[int]:
        """添加 JD 到向量库"""
        if not self._connected:
            self.connect()

        if self._milvus_available:
            try:
                embedding = _simple_embed(jd_title + " " + content[:2048])
                self._collection.insert([
                    [embedding], [jd_title], [industry],
                    [content[:60000]], [skills], [source],
                ])
                self._collection.flush()
                return True
            except Exception as e:
                logger.warning(f"Milvus insert failed, fallback to local: {e}")

        # 降级到本地存储
        return self._local.add(jd_title, content, skills, industry, source)

    def search_similar_jd(self, query: str, top_k: int = 5) -> List[dict]:
        """搜索相似 JD"""
        if not self._connected:
            self.connect()

        if self._milvus_available:
            try:
                from pymilvus import Collection
                col = self._collection
                col.load()
                embedding = _simple_embed(query)
                results = col.search(
                    data=[embedding],
                    anns_field="embedding",
                    param={"metric_type": "IP", "params": {"nprobe": 16}},
                    limit=top_k,
                    output_fields=["title", "industry", "content", "skills"],
                )
                hits = []
                for hits_batch in results:
                    for hit in hits_batch:
                        hits.append({
                            "id": hit.id,
                            "score": hit.score,
                            "job_title": hit.entity.get("title", ""),
                            "industry": hit.entity.get("industry", ""),
                            "content": hit.entity.get("content", "")[:500],
                            "skills": hit.entity.get("skills", ""),
                        })
                return hits
            except Exception as e:
                logger.warning(f"Milvus search failed, fallback to local: {e}")

        return self._local.search(query, top_k)

    def batch_delete_docs(self, doc_ids: List[int]) -> int:
        """批量删除文档，返回成功删除数量"""
        count = 0
        for doc_id in doc_ids:
            try:
                if self.delete_doc(doc_id):
                    count += 1
            except Exception:
                pass
        return count

    def delete_doc(self, doc_id: int) -> bool:
        """删除文档"""
        if self._milvus_available:
            try:
                from pymilvus import Collection
                expr = f"id == {doc_id}"
                self._collection.delete(expr)
                return True
            except Exception:
                pass
        return self._local.delete(doc_id)

    def list_docs(self) -> List[dict]:
        """列出所有文档"""
        if self._milvus_available:
            try:
                self._collection.load()
                results = self._collection.query(expr="", output_fields=["id", "title", "industry", "source", "skills"])
                return [
                    {"id": r["id"], "title": r.get("title", ""),
                     "industry": r.get("industry", ""), "source": r.get("source", ""),
                     "skills": r.get("skills", "")}
                    for r in results
                ]
            except Exception:
                pass
        return self._local.list_all()

    def count(self) -> int:
        """文档总数"""
        if self._milvus_available:
            try:
                self._collection.load()
                return self._collection.num_entities
            except Exception:
                pass
        return self._local.count()

    def add_document(self, title: str, content: str, skills: str = "",
                     industry: str = "", source: str = "manual") -> int:
        """添加文档（公开接口）"""
        return self.add_jd(0, title, content, skills, industry, source)


# 全局单例
vector_store = VectorStore()
