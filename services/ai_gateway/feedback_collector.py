"""
feedback_collector.py
收集 AI 结果反馈 —— 记录用户对 AI 输出的评价，用于后续微调与质量监控。
"""
import time
import logging
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_gateway.feedback_collector")


# ------------------------------------------------------------------
# Schema
# ------------------------------------------------------------------

class FeedbackRating(str, Enum):
    GOOD    = "good"     # 👍 结果准确有用
    BAD     = "bad"      # 👎 结果错误或无用
    PARTIAL = "partial"  # 🤔 部分正确


class FeedbackPayload(BaseModel):
    """前端提交的反馈请求体"""
    session_id:  str            = Field(..., description="关联的会话ID")
    request_id:  Optional[str]  = Field(None, description="关联的请求ID（用于精确溯源）")
    rating:      FeedbackRating = Field(..., description="评分")
    comment:     Optional[str]  = Field(None, max_length=500, description="用户文字说明")
    ai_output:   Optional[str]  = Field(None, description="被评价的 AI 输出内容（前端回传）")
    user_prompt: Optional[str]  = Field(None, description="对应的用户输入")
    data_type:   Optional[str]  = Field(None, description="raster / vector")
    task_mode:   Optional[str]  = Field(None, description="analyze / modify")


class FeedbackRecord(BaseModel):
    """存储的反馈记录（含服务端附加字段）"""
    feedback_id: str
    session_id:  str
    request_id:  Optional[str]
    rating:      FeedbackRating
    comment:     Optional[str]
    ai_output:   Optional[str]
    user_prompt: Optional[str]
    data_type:   Optional[str]
    task_mode:   Optional[str]
    created_at:  float = Field(default_factory=time.time)


# ------------------------------------------------------------------
# 存储后端（内存版，可替换为数据库写入）
# ------------------------------------------------------------------

class FeedbackStore:
    """
    内存反馈存储（开发/测试用）。
    生产环境：替换 save() 方法为异步数据库写入。
    """

    def __init__(self, max_records: int = 10000):
        self._records: List[FeedbackRecord] = []
        self.max_records = max_records

    async def save(self, record: FeedbackRecord) -> None:
        """保存一条反馈记录"""
        if len(self._records) >= self.max_records:
            self._records.pop(0)   # 简单 FIFO 淘汰
        self._records.append(record)
        logger.info(
            f"[Feedback] session={record.session_id} "
            f"rating={record.rating.value} "
            f"comment={record.comment or '(无)'}"
        )

    def get_stats(self) -> Dict[str, Any]:
        """统计各评分比例（用于监控面板）"""
        total = len(self._records)
        if total == 0:
            return {"total": 0}
        counts = {r.value: 0 for r in FeedbackRating}
        for rec in self._records:
            counts[rec.rating.value] += 1
        return {
            "total": total,
            "good_rate":    round(counts["good"]    / total, 3),
            "bad_rate":     round(counts["bad"]     / total, 3),
            "partial_rate": round(counts["partial"] / total, 3),
            "counts": counts,
        }

    def get_bad_cases(self, limit: int = 20) -> List[Dict]:
        """获取最近的差评案例（用于人工复核/微调数据集构建）"""
        bad = [r for r in self._records if r.rating == FeedbackRating.BAD]
        return [r.model_dump() for r in bad[-limit:]]


# ------------------------------------------------------------------
# 核心入口函数
# ------------------------------------------------------------------

async def collect_feedback(
    payload: FeedbackPayload,
    store: FeedbackStore,
    request_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    处理一条反馈提交。
    在 router.py 的 /feedback 端点中调用。
    """
    import uuid
    record = FeedbackRecord(
        feedback_id=str(uuid.uuid4()),
        session_id=payload.session_id,
        request_id=request_id or payload.request_id,
        rating=payload.rating,
        comment=payload.comment,
        ai_output=payload.ai_output,
        user_prompt=payload.user_prompt,
        data_type=payload.data_type,
        task_mode=payload.task_mode,
    )
    await store.save(record)
    return {
        "status": "ok",
        "feedback_id": record.feedback_id,
        "message": "反馈已记录，感谢您的评价"
    }


# 全局单例
_default_store = FeedbackStore()

def get_feedback_store() -> FeedbackStore:
    return _default_store