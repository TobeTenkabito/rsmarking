import os
import logging
from typing import Union
from litellm import acompletion

from services.ai_gateway.schema_validator import (
    AILanguage, TaskMode, DataType,
    RasterModifiable, VectorModifiable,
    validate_ai_json_output
)

logger = logging.getLogger("ai_gateway.llm_engine")


def _build_system_prompt(mode: TaskMode, data_type: DataType, language: AILanguage, modifiable_schema_json: str) -> str:
    # 保持原有逻辑不变
    LANGUAGE_MAP = {
        AILanguage.ZH: "你必须使用【简体中文】回答，所有输出内容包括分析报告、字段说明、错误信息均使用中文。",
        AILanguage.EN: "You MUST respond in【English】. All output including analysis, field descriptions, and error messages must be in English.",
        AILanguage.JA: "必ず【日本語】で回答してください。分析レポート、フィールドの説明、エラーメッセージを含むすべての出力は日本語で記述してください。",
    }
    language_instruction = LANGUAGE_MAP[language]
    base_prompt = f"{language_instruction},你是一个专业的 GIS 空间数据分析与处理 AI 助手。\n"

    if mode == TaskMode.ANALYZE:
        return base_prompt + "请根据用户的自然语言提问，对这些数据进行专业的分析，并输出纯文本的分析报告。\n要求：专业、客观、条理清晰。不得编造数据中不存在的信息。不要输出任何 JSON 代码。"
    elif mode == TaskMode.MODIFY:
        return base_prompt + f"""你现在的任务是：根据用户的指令，修改提供的 GIS 数据，并返回修改后的完整 JSON。
【极其重要的规则】
1. 提供的原始数据中包含了大量只读的统计特征（如极值、均值、边界等），这些是客观物理数据，**绝对不可修改**。
2. 你必须且只能输出合法的 JSON 字符串，不要包含任何 Markdown 标记（如 ```json），不要包含任何解释性文本！
3. 你的输出必须严格符合以下 JSON Schema，**只能包含允许修改的字段**：
{modifiable_schema_json}
4. 你的输出必须包含一个顶层键 "modified_data"，里面存放你修改后的数据。
5. 你可以增加一个顶层键 "explanation"，简短说明你修改了什么。
"""


async def call_llm_with_retry(messages: list, model_name: str, mode: TaskMode, expected_type: DataType,
                              max_retries: int = 2) -> Union[str, RasterModifiable, VectorModifiable]:
    current_model = os.getenv("AI_NAME", model_name)

    for attempt in range(max_retries + 1):
        ai_content = None  # 修复：提前声明，防止未赋值引发异常
        try:
            logger.info(f"正在调用大模型 {current_model} (尝试 {attempt + 1}/{max_retries + 1})...")
            response = await acompletion(
                model=current_model,
                messages=messages,
                temperature=0.1 if mode == TaskMode.MODIFY else 0.7,
            )
            ai_content = response.choices[0].message.content

            if mode == TaskMode.ANALYZE:
                return ai_content

            if mode == TaskMode.MODIFY:
                validated_data = validate_ai_json_output(ai_content, expected_type)
                return validated_data

        except Exception as e:
            logger.warning(f"大模型调用或解析失败 (尝试 {attempt + 1}): {str(e)}")
            if attempt == max_retries:
                raise RuntimeError(f"AI 处理失败，已达到最大重试次数。最后一次错误: {str(e)}")

            if mode == TaskMode.MODIFY and ai_content is not None:
                # 修复：确保解析失败才拼接历史对话，若是网络异常(ai_content无值)则不破坏会话结构
                error_feedback = f"你刚才输出的 JSON 格式有误，导致了解析失败。错误信息如下：\n{str(e)}\n请严格按照 Schema 重新输出合法的 JSON，并且只能包含允许修改的字段。"
                messages.append({"role": "assistant", "content": ai_content})
                messages.append({"role": "user", "content": error_feedback})