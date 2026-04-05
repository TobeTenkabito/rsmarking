"""
streaming_handler.py
SSE 流式输出 —— 包装 llm_engine 的流式调用，通过 FastAPI StreamingResponse 推送。
"""
import json
import logging
from typing import AsyncGenerator

from fastapi.responses import StreamingResponse
from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession

from services.ai_gateway.schema_validator import AIRequestPayload, TaskMode, DataType
from services.ai_gateway.data_extractor import _extract_raster_data, _extract_vector_data
from services.ai_gateway.llm_engine import _build_system_prompt
from services.ai_gateway.memory.session_memory import SessionMemoryStore
from services.ai_gateway.context_builder import build_map_context

logger = logging.getLogger("ai_gateway.streaming_handler")

# SSE 数据帧格式
def _sse(data: str) -> str:
    return f"data: {data}\n\n"

def _sse_json(obj: dict) -> str:
    return _sse(json.dumps(obj, ensure_ascii=False))


async def _token_stream(messages: list, model_name: str) -> AsyncGenerator[str, None]:
    """核心流式生成器：逐 token 推送 SSE 帧"""
    try:
        response = await acompletion(
            model=model_name,
            messages=messages,
            stream=True,
            temperature=0.7,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield _sse_json({"type": "token", "content": delta.content})

        # 流结束标记
        yield _sse_json({"type": "done"})

    except Exception as e:
        logger.error(f"[StreamingHandler] 流式调用失败: {e}")
        yield _sse_json({"type": "error", "message": str(e)})


async def handle_stream(
    payload: AIRequestPayload,
    db: AsyncSession,
    vector_db: AsyncSession,
    model_name: str,
    session_store: SessionMemoryStore,
) -> StreamingResponse:
    """
    流式分析入口（仅支持 ANALYZE 模式）。
    MODIFY 模式需要完整 JSON 输出，不适合流式。
    """
    if payload.mode != TaskMode.ANALYZE:
        async def _err():
            yield _sse_json({"type": "error", "message": "流式输出仅支持 ANALYZE 模式"})
        return StreamingResponse(_err(), media_type="text/event-stream")

    # 1. 提取数据上下文
    if payload.data_type == DataType.RASTER:
        context_data = await _extract_raster_data(db, int(payload.target_id))
    else:
        context_data = await _extract_vector_data(vector_db, str(payload.target_id))

    # 2. 构建地图视野上下文（前端注入）
    map_ctx = build_map_context(payload)

    # 3. 构建 system prompt（ANALYZE 模式无需 modifiable_schema）
    system_prompt = _build_system_prompt(
        TaskMode.ANALYZE, payload.data_type, payload.language, ""
    )

    # 4. 拼接消息：历史记忆 + 本次输入
    history = session_store.get_history(payload.session_id) if payload.session_id else []
    context_json = context_data.model_dump_json(indent=2)
    user_content = (
        f"{map_ctx}\n\n"
        f"【数据上下文】\n{context_json}\n\n"
        f"【用户问题】\n{payload.user_prompt}"
    )
    messages = [{"role": "system", "content": system_prompt}] + history + [
        {"role": "user", "content": user_content}
    ]

    # 5. 保存本次用户消息到记忆
    if payload.session_id:
        session_store.append(payload.session_id, "user", payload.user_prompt)

    # 6. 返回 StreamingResponse（在流结束后异步保存 AI 回复）
    full_response_parts = []

    async def _stream_and_save():
        async for chunk in _token_stream(messages, model_name):
            # 解析 token 内容用于保存记忆
            try:
                data = json.loads(chunk.removeprefix("data: ").strip())
                if data.get("type") == "token":
                    full_response_parts.append(data["content"])
            except Exception:
                pass
            yield chunk
        # 流结束后保存完整 AI 回复
        if payload.session_id and full_response_parts:
            session_store.append(
                payload.session_id, "assistant", "".join(full_response_parts)
            )

    return StreamingResponse(
        _stream_and_save(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 关闭 Nginx 缓冲，确保实时推送
        },
    )
