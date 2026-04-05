"""
prompt_manager.py
Prompt 模板管理与版本控制 —— 将硬编码在 llm_engine.py 的 prompt 统一管理。
支持：多语言、多任务模式、版本回滚、运行时热更新。
"""
import logging
from typing import Dict, Optional
from services.ai_gateway.schema_validator import AILanguage, TaskMode, DataType

logger = logging.getLogger("ai_gateway.prompt_manager")


# ------------------------------------------------------------------
# Prompt 模板定义（结构：mode → language → template）
# ------------------------------------------------------------------

_LANGUAGE_INSTRUCTION: Dict[AILanguage, str] = {
    AILanguage.ZH: "使用简体中文回答，不受用户输入语言影响。",
    AILanguage.EN: "Respond in English, regardless of the user's input language.",
    AILanguage.JA: "ユーザーの入力言語に関係なく、日本語で回答。",
}

_BASE_ROLE = "你是GIS空间数据分析助手。"

# 版本化模板库：key = (mode, data_type, version)
_PROMPT_TEMPLATES: Dict[tuple, str] = {

    # ── ANALYZE ──────────────────────────────────────────────────────
    (TaskMode.ANALYZE, DataType.RASTER, "v1"): (
        "{lang_instruction} {base_role}\n"
        "任务：根据用户问题分析栅格数据，输出文本报告。\n"
        "要求：\n"
        "- 专业、客观、结构清晰\n"
        "- 不编造数据\n"
        "- 不输出JSON"
    ),
    (TaskMode.ANALYZE, DataType.VECTOR, "v1"): (
        "{lang_instruction} {base_role}\n"
        "任务：根据用户问题分析矢量图层，输出文本报告。\n"
        "要求：\n"
        "- 专业、客观、结构清晰\n"
        "- 可使用工具查询具体要素\n"
        "- 不编造数据\n"
        "- 不输出JSON"
    ),

    # ── MODIFY ───────────────────────────────────────────────────────
    (TaskMode.MODIFY, DataType.RASTER, "v1"): (
        "{lang_instruction} {base_role}\n"
        "任务：根据用户指令修改栅格GIS数据并返回JSON。\n"
        "规则：\n"
        "1. 不修改只读字段\n"
        "2. 仅输出合法JSON（无Markdown、无解释）\n"
        "3. 仅包含允许修改字段（见Schema）\n"
        "4. 顶层必须包含 \"modified_data\"\n"
        "Schema:\n{modifiable_schema}"
    ),
    (TaskMode.MODIFY, DataType.VECTOR, "v1"): (
        "{lang_instruction} {base_role}\n"
        "任务：根据用户指令修改矢量GIS数据并返回JSON。\n"
        "规则：\n"
        "1. 不修改只读字段\n"
        "2. 仅输出合法JSON（无Markdown、无解释）\n"
        "3. 仅包含允许修改字段（见Schema）\n"
        "4. 顶层必须包含 \"modified_data\"\n"
        "Schema:\n{modifiable_schema}"
    ),
}

# 当前各 (mode, data_type) 使用的版本（支持运行时切换）
_ACTIVE_VERSIONS: Dict[tuple, str] = {
    (TaskMode.ANALYZE, DataType.RASTER): "v1",
    (TaskMode.ANALYZE, DataType.VECTOR): "v1",
    (TaskMode.MODIFY,  DataType.RASTER): "v1",
    (TaskMode.MODIFY,  DataType.VECTOR): "v1",
}


# ------------------------------------------------------------------
# 公开 API
# ------------------------------------------------------------------

def build_system_prompt(
    mode: TaskMode,
    data_type: DataType,
    language: AILanguage,
    modifiable_schema: str = "",
    version: Optional[str] = None,
) -> str:
    """
    构建 system prompt（替代 llm_engine._build_system_prompt）。
    version=None 时使用当前激活版本。
    """
    ver = version or _ACTIVE_VERSIONS.get((mode, data_type), "v1")
    template = _PROMPT_TEMPLATES.get((mode, data_type, ver))

    if template is None:
        logger.warning(f"[PromptManager] 未找到模板 ({mode},{data_type},{ver})，使用通用模板")
        template = (
            "{lang_instruction} {base_role}\n"
            "请根据用户指令处理GIS数据。"
        )

    return template.format(
        lang_instruction=_LANGUAGE_INSTRUCTION.get(language, ""),
        base_role=_BASE_ROLE,
        modifiable_schema=modifiable_schema,
    )


def set_active_version(mode: TaskMode, data_type: DataType, version: str) -> bool:
    """运行时切换指定 (mode, data_type) 的 prompt 版本（热更新，无需重启）"""
    key = (mode, data_type)
    if (mode, data_type, version) not in _PROMPT_TEMPLATES:
        logger.error(f"[PromptManager] 版本 {version} 不存在，切换失败")
        return False
    _ACTIVE_VERSIONS[key] = version
    logger.info(f"[PromptManager] 已切换 {mode}/{data_type} → {version}")
    return True


def register_template(
    mode: TaskMode,
    data_type: DataType,
    version: str,
    template: str,
) -> None:
    """动态注册新模板（用于 A/B 测试或外部配置加载）"""
    _PROMPT_TEMPLATES[(mode, data_type, version)] = template
    logger.info(f"[PromptManager] 已注册模板: ({mode},{data_type},{version})")


def list_versions(mode: TaskMode, data_type: DataType) -> list:
    """列出某 (mode, data_type) 下所有可用版本"""
    return [k[2] for k in _PROMPT_TEMPLATES if k[0] == mode and k[1] == data_type]
