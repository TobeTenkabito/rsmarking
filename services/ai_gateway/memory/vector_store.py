"""
vector_store.py
RAG 向量检索 —— 将历史标注/分析结论向量化存储，供后续查询召回。
依赖：sentence-transformers（本地）或 litellm embedding API（远程）
"""
import logging
import time
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("ai_gateway.memory.vector_store")


@dataclass
class VectorDocument:
    """向量库中的一条文档记录"""
    doc_id: str
    text: str                          # 原始文本（用于返回给 LLM）
    embedding: List[float]             # 向量
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class InMemoryVectorStore:
    """
    基于 numpy 余弦相似度的轻量向量库。
    生产环境建议替换为 pgvector / Qdrant / Chroma（接口相同）。
    """

    def __init__(self):
        self._docs: List[VectorDocument] = []

    # ------------------------------------------------------------------
    # 写入
    # ------------------------------------------------------------------

    def add(self, doc_id: str, text: str, embedding: List[float], metadata: Dict = None) -> None:
        """添加一条文档（若 doc_id 已存在则更新）"""
        self._docs = [d for d in self._docs if d.doc_id != doc_id]
        self._docs.append(VectorDocument(
            doc_id=doc_id,
            text=text,
            embedding=embedding,
            metadata=metadata or {},
        ))
        logger.debug(f"[VectorStore] 已写入文档: {doc_id}，当前总量: {len(self._docs)}")

    # ------------------------------------------------------------------
    # 检索
    # ------------------------------------------------------------------

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 3,
        filter_meta: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        余弦相似度检索，返回 top_k 条最相关文档。
        filter_meta: 元数据过滤，例如 {"data_type": "raster"}
        """
        if not self._docs:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        results = []
        for doc in self._docs:
            # 元数据过滤
            if filter_meta:
                if not all(doc.metadata.get(k) == v for k, v in filter_meta.items()):
                    continue
            d_vec = np.array(doc.embedding, dtype=np.float32)
            d_norm = np.linalg.norm(d_vec)
            if d_norm == 0:
                continue
            score = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))
            results.append({"doc": doc, "score": score})

        results.sort(key=lambda x: x["score"], reverse=True)
        return [
            {
                "doc_id": r["doc"].doc_id,
                "text": r["doc"].text,
                "score": round(r["score"], 4),
                "metadata": r["doc"].metadata,
            }
            for r in results[:top_k]
        ]

    def count(self) -> int:
        return len(self._docs)


# ------------------------------------------------------------------
# Embedding 工具函数（可替换为任意 embedding 模型）
# ------------------------------------------------------------------

async def get_embedding(text: str, model: str = "text-embedding-3-small") -> List[float]:
    """
    调用 litellm embedding API 获取向量。
    若无网络，可替换为 sentence-transformers 本地模型。
    """
    try:
        from litellm import aembedding
        response = await aembedding(model=model, input=[text])
        return response.data[0]["embedding"]
    except Exception as e:
        logger.error(f"[VectorStore] Embedding 获取失败: {e}")
        # 降级：返回零向量（不影响主流程，只是检索无结果）
        return [0.0] * 1536


# ------------------------------------------------------------------
# RAG 注入辅助：将检索结果格式化为 Prompt 片段
# ------------------------------------------------------------------

def format_rag_context(docs: List[Dict[str, Any]]) -> str:
    """将检索到的文档列表格式化为注入 LLM 的上下文字符串"""
    if not docs:
        return ""
    lines = ["【相关历史知识库参考】"]
    for i, d in enumerate(docs, 1):
        lines.append(f"{i}. [相似度:{d['score']}] {d['text']}")
    return "\n".join(lines)


# 全局单例
_default_store = InMemoryVectorStore()


def get_vector_store() -> InMemoryVectorStore:
    return _default_store
