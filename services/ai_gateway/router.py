import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


from services.data_service.database import get_db
from services.annotation_service.database import get_db as get_vector_db

# 导入契约层与引擎层
from .schema_validator import AIRequestPayload
from .translator import process_ai_task

logger = logging.getLogger("ai_gateway.main")

# 创建路由器
router = APIRouter(
    prefix="/ai",
    tags=["AI Gateway - 智能空间数据网关"]
)


@router.post("/process", summary="处理 AI 空间数据任务 (分析/修改)")
async def handle_ai_task(
        payload: AIRequestPayload,
        db: AsyncSession = Depends(get_db),
        vector_db: AsyncSession = Depends(get_vector_db)  # ← 新增
):
    logger.info(f"收到 AI 任务请求: 目标={payload.target_id}, "
                f"类型={payload.data_type}, 模式={payload.mode}, 语言={payload.language}")
    try:
        result = await process_ai_task(payload=payload, db=db, vector_db=vector_db)  # ← 透传
        return result
    except ValueError as e:
        logger.warning(f"AI 任务业务异常 (400): {str(e)}")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except RuntimeError as e:
        logger.error(f"AI 网关处理失败 (502): {str(e)}")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AI 服务暂时不可用或解析失败: {str(e)}")
    except Exception as e:
        logger.exception(f"AI 任务发生未知系统错误 (500): {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="服务器内部错误，请查看系统日志。")

