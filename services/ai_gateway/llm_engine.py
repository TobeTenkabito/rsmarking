import os
import logging
import json
from typing import Union
from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession
from services.ai_gateway.tool_executor import execute_vector_query
from services.ai_gateway.schema_validator import (
    AILanguage, TaskMode, DataType,
    RasterModifiable, VectorModifiable,
    validate_ai_json_output
)

logger = logging.getLogger("ai_gateway.llm_engine")


def _build_system_prompt(mode: TaskMode, data_type: DataType, language: AILanguage, modifiable_schema_json: str) -> str:
    LANGUAGE_MAP = {
        AILanguage.ZH: "使用简体中文回答，不受用户输入语言影响。",
        AILanguage.EN: "Respond in English,regardless of the user's input language.",
        AILanguage.JA: "ユーザーの入力言語に関係なく、日本語で回答。",
    }
    base_prompt = f"{LANGUAGE_MAP[language]} 你是GIS空间数据分析助手。\n"
    if mode == TaskMode.ANALYZE:
        return base_prompt + (
            "任务：根据用户问题分析数据，输出文本报告。\n"
            "要求：\n"
            "- 专业、客观、结构清晰\n"
            "- 不编造数据\n"
            "- 不输出JSON"
        )
    elif mode == TaskMode.MODIFY:
        return base_prompt + (
            "任务：根据用户指令修改GIS数据并返回JSON。\n"
            "规则：\n"
            "1. 不修改只读字段\n"
            "2. 仅输出合法JSON（无Markdown、无解释）\n"
            "3. 仅包含允许修改字段（见Schema）\n"
            "4. 顶层必须包含 \"modified_data\"\n"
            f"Schema:\n{modifiable_schema_json}"
        )


async def call_llm_with_retry(
        messages: list,
        model_name: str,
        mode: TaskMode,
        expected_type: DataType,
        db: AsyncSession = None,
        target_id: str = None,
        context_schema: dict = None,
        max_retries: int = 2
) -> Union[str, RasterModifiable, VectorModifiable]:
    current_model = os.getenv("AI_NAME", model_name)

    # 装载工具
    tools = None
    if mode == TaskMode.ANALYZE and expected_type == DataType.VECTOR and context_schema:
        tools = _get_vector_tools(list(context_schema.keys()))

    for attempt in range(max_retries + 1):
        try:
            # 将普通的 completion 升级为支持 tools 的循环 (最大允许3次连续调用防止死循环)
            for step in range(3):
                response = await acompletion(
                    model=current_model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto" if tools else None,
                    temperature=0.1 if mode == TaskMode.MODIFY else 0.7,
                )

                response_message = response.choices[0].message
                messages.append(response_message)  # 将 AI 的回复（或调用请求）放入历史

                # 如果没有工具调用，说明 AI 给出了最终文本/JSON 结论
                if not response_message.tool_calls:
                    ai_content = response_message.content
                    if mode == TaskMode.ANALYZE:
                        return ai_content

                    if mode == TaskMode.MODIFY:
                        return validate_ai_json_output(ai_content, expected_type)

                # 处理工具调用
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "query_vector_features":
                        args = json.loads(tool_call.function.arguments)
                        logger.info(f"AI 调用了查询工具: {args}")

                        tool_result = await execute_vector_query(db, target_id, args, context_schema)

                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": json.dumps(tool_result, ensure_ascii=False)
                        })

        except Exception as e:
            logger.warning(f"大模型调用或解析失败 (尝试 {attempt + 1}): {str(e)}")
            if attempt == max_retries:
                raise RuntimeError(f"AI 处理失败，已达到最大重试次数。最后一次错误: {str(e)}")

            if mode == TaskMode.MODIFY and ai_content is not None:
                error_feedback = f"你刚才输出的 JSON 格式有误，导致了解析失败。错误信息如下：\n{str(e)}\n请严格按照 Schema 重新输出合法的 JSON，并且只能包含允许修改的字段。"
                messages.append({"role": "assistant", "content": ai_content})
                messages.append({"role": "user", "content": error_feedback})


def _get_vector_tools(valid_schema_keys: list) -> list:
    """定义遵循通用查询协议的工具结构"""
    return [{
        "type": "function",
        "function": {
            "name": "query_vector_features",
            "description": f"当上下文数据不足以回答用户关于具体要素的提问时，使用此工具查询矢量属性。可查询的合法字段：{valid_schema_keys}",
            "parameters": {
                "type": "object",
                "properties": {
                    "selected_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "需要返回的字段名列表"
                    },
                    "filter_conditions": {
                        "type": "array",
                        "description": "结构化过滤条件",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "operator": {"type": "string", "enum": ["eq", "gt", "lt", "like"]},
                                "value": {"type": "string", "description": "用于比较的值。若是数字也会解析为字符串传入"}
                            },
                            "required": ["column", "operator", "value"]
                        }
                    },
                    "limit": {"type": "integer", "description": "返回数量限制，最大50", "default": 5}
                },
                "required": ["selected_columns"]
            }
        }
    }]