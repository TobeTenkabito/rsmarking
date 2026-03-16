import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


from services.data_service.database import get_db

# 导入契约层与引擎层
from .schema_validator import AIRequestPayload
from .translator import process_ai_task

logger = logging.getLogger("ai_gateway.main")

# 创建路由器
router = APIRouter(
    prefix="/ai",
    tags=["AI Gateway - 智能空间数据网关"]
)


@router.post(
    "/process",
    summary="处理 AI 空间数据任务 (分析/修改)",
    description="""
    接收自然语言指令，对指定的栅格或矢量数据进行处理。
    - **analyze 模式**: 返回纯文本的专业空间数据分析报告。
    - **modify 模式**: 返回严格符合 Schema 的 JSON 数据，供前端确认后调用更新接口落库。
    """
)
async def handle_ai_task(
        payload: AIRequestPayload,
        db: AsyncSession = Depends(get_db)
):
    """
    统一的 AI 任务处理入口
    """
    logger.info(f"收到 AI 任务请求: 目标={payload.target_id}, "
                f"类型={payload.data_type}, 模式={payload.mode},语言={payload.language}")

    try:
        # 调用核心翻译与调度引擎
        result = await process_ai_task(payload=payload, db=db)
        return result

    except ValueError as e:
        # 捕获数据校验错误、找不到数据、AI 输出格式严重错误等业务异常 (400 Bad Request)
        logger.warning(f"AI 任务业务异常 (400): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except RuntimeError as e:
        # 捕获大模型调用失败、重试超限等网关/第三方依赖异常 (502 Bad Gateway)
        logger.error(f"AI 网关处理失败 (502): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 服务暂时不可用或解析失败: {str(e)}"
        )

    except Exception as e:
        # 捕获未知的系统级异常 (500 Internal Server Error)
        logger.exception(f"AI 任务发生未知系统错误 (500): {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请查看系统日志。"
        )

