import logging
import json
from typing import Union
from sqlalchemy.ext.asyncio import AsyncSession
from services.ai_gateway.config import get_ai_model
from services.ai_gateway.llm_client import call_chat_completion
from services.ai_gateway.tool_executor import execute_vector_query
from services.ai_gateway.schema_validator import (
    AILanguage, TaskMode, DataType,
    RasterModifiable, VectorModifiable,
    validate_ai_json_output
)

logger = logging.getLogger("ai_gateway.llm_engine")


def _build_system_prompt(mode: TaskMode, data_type: DataType, language: AILanguage, modifiable_schema_json: str) -> str:
    LANGUAGE_MAP = {
        AILanguage.ZH: "Respond in Simplified Chinese regardless of the user's input language.",
        AILanguage.EN: "Respond in English regardless of the user's input language.",
        AILanguage.JA: "Respond in Japanese regardless of the user's input language.",
        AILanguage.ES: "Respond in Spanish regardless of the user's input language.",
    }
    base_prompt = f"{LANGUAGE_MAP[language]} You are a GIS spatial data analysis assistant.\n"
    if mode == TaskMode.ANALYZE:
        return base_prompt + (
            "Task: analyze the data based on the user's question and output a text report.\n"
            "Requirements:\n"
            "- Be professional, objective, and clearly structured.\n"
            "- Do not invent data.\n"
            "- Do not output JSON."
        )
    elif mode == TaskMode.MODIFY:
        return base_prompt + (
            "Task: modify GIS data according to the user's instruction and return JSON.\n"
            "Rules:\n"
            "1. Do not modify read-only fields.\n"
            "2. Output valid JSON only, with no Markdown or explanations.\n"
            "3. Include only fields allowed by the schema.\n"
            "4. The top level must contain \"modified_data\"\n"
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
    current_model = get_ai_model(model_name)

    # Load tools
    tools = None
    if mode == TaskMode.ANALYZE and expected_type == DataType.VECTOR and context_schema:
        tools = _get_vector_tools(list(context_schema.keys()))

    for attempt in range(max_retries + 1):
        ai_content = None
        try:
            # Upgrade a normal completion into a tool-capable loop with at most 3 consecutive calls to avoid infinite loops.
            for step in range(3):
                response = await call_chat_completion(
                    model_name=current_model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto" if tools else None,
                    temperature=0.1 if mode == TaskMode.MODIFY else 0.7,
                )

                response_message = response.choices[0].message
                messages.append(response_message)  # Append the AI response or tool request to history.

                # If there are no tool calls, the AI has produced the final text/JSON result
                if not response_message.tool_calls:
                    ai_content = response_message.content
                    if mode == TaskMode.ANALYZE:
                        return ai_content

                    if mode == TaskMode.MODIFY:
                        return validate_ai_json_output(ai_content, expected_type)

                # Handle tool calls
                for tool_call in response_message.tool_calls:
                    if tool_call.function.name == "query_vector_features":
                        args = json.loads(tool_call.function.arguments)
                        logger.info(f"AI called the query tool: {args}")

                        tool_result = await execute_vector_query(db, target_id, args, context_schema)

                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": tool_call.function.name,
                            "content": json.dumps(tool_result, ensure_ascii=False)
                        })

        except Exception as e:
            logger.warning(f"Model call or parsing failed (attempt {attempt + 1}): {str(e)}")
            if attempt == max_retries:
                raise RuntimeError(f"AI processing failed after the maximum retry count. Last error: {str(e)}")

            if mode == TaskMode.MODIFY and ai_content is not None:
                error_feedback = f"The JSON you just output is malformed and could not be parsed. Error details:\n{str(e)}\nRe-output valid JSON strictly following the schema, including only fields allowed for modification."
                messages.append({"role": "assistant", "content": ai_content})
                messages.append({"role": "user", "content": error_feedback})


def _get_vector_tools(valid_schema_keys: list) -> list:
    """Define the tool structure following the generic query protocol"""
    return [{
        "type": "function",
        "function": {
            "name": "query_vector_features",
            "description": f"Use this tool to query vector attributes when the context is insufficient to answer questions about specific features. Valid query fields: {valid_schema_keys}",
            "parameters": {
                "type": "object",
                "properties": {
                    "selected_columns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of field names to return"
                    },
                    "filter_conditions": {
                        "type": "array",
                        "description": "Structured filter conditions",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {"type": "string"},
                                "operator": {"type": "string", "enum": ["eq", "gt", "lt", "like"]},
                                "value": {"type": "string", "description": "Value to compare. Numeric values are also passed as strings."}
                            },
                            "required": ["column", "operator", "value"]
                        }
                    },
                    "limit": {"type": "integer", "description": "Return limit, maximum 50", "default": 5}
                },
                "required": ["selected_columns"]
            }
        }
    }]
