import os
import json
import logging
import numpy as np
import rasterio
from uuid import UUID
from typing import Union, Dict, Any, Optional
from litellm import acompletion
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from dotenv import load_dotenv

# 导入跨服务依赖
from functions.common.snowflake_utils import get_next_index_id
from services.data_service.crud import RasterCRUD
from services.annotation_service.crud.feature import LayerCRUD
from services.annotation_service.models.feature import Feature, Layer

# 导入最新的契约层
from services.ai_gateway.schema_validator import (
    AIRequestPayload,
    AILanguage,
    TaskMode,
    DataType,
    RasterContextData,
    VectorContextData,
    RasterModifiable,
    VectorModifiable,
    SpatialBounds,
    NumericStats,
    validate_ai_json_output
)


load_dotenv()

MODEL = os.getenv("AI_MODEL", "deepseek/deepseek-chat")  # 这里输入你的对话模型
logger = logging.getLogger("ai_gateway.translator")

# 加这行，重启后终端会打印出来
logger.info(f"[AI] 当前使用模型: {MODEL}, Key前缀: {os.getenv('DEEPSEEK_API_KEY', 'NOT FOUND')[:8]}")

# ==========================================
# 1. Level 2 深度统计特征提取 (工业级优化)
# ==========================================

def _compute_raster_stats(file_path: str) -> Optional[NumericStats]:
    """使用 rasterio 进行轻量级降采样统计，防止大文件 OOM"""
    if not file_path or not os.path.exists(file_path):
        return None

    try:
        with rasterio.open(file_path) as src:
            # 工业级优化：降采样到最大 512x512 进行统计，极大地节省内存和时间
            factor = max(1, src.width // 512, src.height // 512)
            out_shape = (1, int(src.height / factor), int(src.width / factor))

            data = src.read(1, out_shape=out_shape)
            # 排除无效值 (NoData)
            valid_data = data[data != src.nodata] if src.nodata is not None else data

            if valid_data.size == 0:
                return None

            min_val = float(np.min(valid_data))
            max_val = float(np.max(valid_data))
            mean_val = float(np.mean(valid_data))
            std_val = float(np.std(valid_data))

            # 计算 5 等分直方图 (20%, 40%, 60%, 80%, 100%)
            hist, bin_edges = np.histogram(valid_data, bins=5)
            hist_dict = {
                f"{bin_edges[i]:.2f}-{bin_edges[i + 1]:.2f}": int(hist[i])
                for i in range(5)
            }

            return NumericStats(
                min=min_val, max=max_val, mean=mean_val,
                std_dev=std_val, histogram=hist_dict
            )
    except Exception as e:
        logger.warning(f"提取栅格统计特征失败 ({file_path}): {e}")
        return None


# ==========================================
# 2. 强类型数据提取与降维 (Database -> Pydantic ContextData)
# ==========================================

async def _extract_raster_data(db: AsyncSession, raster_id: int) -> RasterContextData:
    """从数据库提取栅格完整上下文 (包含物理元数据与深度统计)"""
    raster = await RasterCRUD.get_raster_by_index_id(db, raster_id)
    if not raster:
        raise ValueError(f"未找到 index_id 为 {raster_id} 的栅格数据")

    # 1. 安全解析 bounds (兼容 dict 和 list)
    b_data = raster.bounds or [0.0, 0.0, 0.0, 0.0]
    if isinstance(b_data, dict):
        xmin, ymin = b_data.get("xmin", 0.0), b_data.get("ymin", 0.0)
        xmax, ymax = b_data.get("xmax", 0.0), b_data.get("ymax", 0.0)
    else:
        xmin, ymin = b_data[0], b_data[1]
        xmax, ymax = b_data[2] if len(b_data) > 2 else b_data[0], b_data[3] if len(b_data) > 3 else b_data[1]

    # 2. 安全解析 center
    c_data = raster.center or [0.0, 0.0]
    if isinstance(c_data, dict):
        cx, cy = c_data.get("x", 0.0), c_data.get("y", 0.0)
    else:
        cx, cy = c_data[0], c_data[1]

    # 3. 提取 Level 2 深度统计特征
    stats = _compute_raster_stats(raster.file_path)

    return RasterContextData(
        name=raster.file_name or "unknown_raster",
        crs=raster.crs or "EPSG:4326",
        bounds=SpatialBounds(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax),
        center={"x": cx, "y": cy},
        width=raster.width,
        height=raster.height,
        bands_count=raster.bands or 1,
        data_type=raster.data_type or "unknown",
        resolution={"x": raster.resolution_x or 0.0, "y": raster.resolution_y or 0.0},
        stats=stats
    )


async def _extract_vector_data(db: AsyncSession, layer_id: str) -> VectorContextData:
    """使用 PostGIS 原生函数提取矢量完整上下文 (包含分布与属性聚合)"""
    layer_crud = LayerCRUD(db)
    layer = await layer_crud.get_layer(layer_id)
    if not layer:
        raise ValueError(f"未找到 id 为 {layer_id} 的矢量图层")

    # 1. 查询类别分布和要素总数
    stmt_stats = select(Feature.category, func.count(Feature.id)).where(Feature.layer_id == layer_id).group_by(
        Feature.category)
    result_stats = await db.execute(stmt_stats)
    distribution = {row[0] or "uncategorized": row[1] for row in result_stats.all()}
    total_features = sum(distribution.values())

    # 2. 使用 PostGIS ST_Extent 计算真实 Bounding Box
    stmt_bounds = text("""
        SELECT 
            ST_XMin(ST_Extent(geom)) as xmin,
            ST_YMin(ST_Extent(geom)) as ymin,
            ST_XMax(ST_Extent(geom)) as xmax,
            ST_YMax(ST_Extent(geom)) as ymax
        FROM features 
        WHERE layer_id = :layer_id
    """)
    result_bounds = await db.execute(stmt_bounds, {"layer_id": layer_id})
    bounds_row = result_bounds.fetchone()

    if bounds_row and bounds_row.xmin is not None:
        bounds = SpatialBounds(
            xmin=bounds_row.xmin, ymin=bounds_row.ymin,
            xmax=bounds_row.xmax, ymax=bounds_row.ymax
        )
    else:
        bounds = SpatialBounds(xmin=-180.0, ymin=-90.0, xmax=180.0, ymax=90.0)

    # 3. 动态探查 Schema 并计算数值型字段的 Level 2 深度统计
    stmt_schema = select(Feature.properties).where(Feature.layer_id == layer_id).limit(1)
    result_schema = await db.execute(stmt_schema)
    schema_row = result_schema.scalar_one_or_none()

    properties_schema = {}
    numeric_stats = {}

    if schema_row:
        for k, v in schema_row.items():
            prop_type = type(v).__name__
            properties_schema[k] = prop_type

            # 利用 PostgreSQL JSONB 极速聚合计算
            if prop_type in ['int', 'float']:
                agg_stmt = text(f"""
                    SELECT 
                        MIN((properties->>'{k}')::numeric),
                        MAX((properties->>'{k}')::numeric),
                        AVG((properties->>'{k}')::numeric)
                    FROM features 
                    WHERE layer_id = :layer_id AND properties ? '{k}'
                """)
                agg_res = await db.execute(agg_stmt, {"layer_id": layer_id})
                agg_row = agg_res.fetchone()
                if agg_row and agg_row[0] is not None:
                    numeric_stats[k] = NumericStats(
                        min=float(agg_row[0]),
                        max=float(agg_row[1]),
                        mean=float(agg_row[2])
                    )

    return VectorContextData(
        name=layer.name,
        crs="EPSG:4326",
        bounds=bounds,
        feature_count=total_features,
        category_distribution=distribution,
        properties_schema=properties_schema,
        numeric_stats=numeric_stats
    )


# ==========================================
# 3. Prompt 引擎 (强制读写分离)
# ==========================================

def _build_system_prompt(mode: TaskMode, data_type: DataType, language: AILanguage, modifiable_schema_json: str) -> str:
    """构建强约束的 System Prompt"""
    LANGUAGE_MAP = {
        AILanguage.ZH: "你必须使用【简体中文】回答，所有输出内容包括分析报告、字段说明、错误信息均使用中文。",
        AILanguage.EN: "You MUST respond in【English】. All output including analysis, "
                       "field descriptions, and error messages must be in English.",
        AILanguage.JA: "必ず【日本語】で回答してください。分析レポート、フィールドの説明、エラーメッセージを含むすべての出力は日本語で記述してください。",
    }
    language_instruction = LANGUAGE_MAP[language]

    base_prompt = f"{language_instruction},你是一个专业的 GIS 空间数据分析与处理 AI 助手。\n"

    if mode == TaskMode.ANALYZE:
        return base_prompt + (
            "请根据用户的自然语言提问，对这些数据进行专业的分析，并输出纯文本的分析报告。\n"
            "要求：专业、客观、条理清晰。不得编造数据中不存在的信息。不要输出任何 JSON 代码。"
        )

    elif mode == TaskMode.MODIFY:
        return base_prompt + f"""
你现在的任务是：根据用户的指令，修改提供的 GIS 数据，并返回修改后的完整 JSON。

【极其重要的规则】
1. 提供的原始数据中包含了大量只读的统计特征（如极值、均值、边界等），这些是客观物理数据，**绝对不可修改**。
2. 你必须且只能输出合法的 JSON 字符串，不要包含任何 Markdown 标记（如 ```json），不要包含任何解释性文本！
3. 你的输出必须严格符合以下 JSON Schema，**只能包含允许修改的字段**：
{modifiable_schema_json}
4. 你的输出必须包含一个顶层键 "modified_data"，里面存放你修改后的数据。
5. 你可以增加一个顶层键 "explanation"，简短说明你修改了什么。

示例输出格式：
{{
  "modified_data": {{ ...仅包含允许修改的字段... }},
  "explanation": "我将图层名称修改为了..."
}}
"""


# ==========================================
# 4. 核心 LLM 调用与重试逻辑
# ==========================================

async def call_llm_with_retry(
        messages: list,
        model_name: str,
        mode: TaskMode,
        expected_type: DataType,
        max_retries: int = 2
) -> Union[str, Union[RasterModifiable, VectorModifiable]]:
    """调用大模型，并在 Modify 模式下处理格式校验与自动重试"""

    current_model = os.getenv("AI_NAME", model_name)

    for attempt in range(max_retries + 1):
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
                # 使用核心解译器进行物理防篡改校验
                validated_data = validate_ai_json_output(ai_content, expected_type)
                return validated_data

        except Exception as e:
            logger.warning(f"大模型调用或解析失败 (尝试 {attempt + 1}): {str(e)}")
            if attempt == max_retries:
                raise RuntimeError(f"AI 处理失败，已达到最大重试次数。最后一次错误: {str(e)}")

            if mode == TaskMode.MODIFY:
                error_feedback = f"你刚才输出的 JSON 格式有误，导致了解析失败。错误信息如下：\n{str(e)}\n请严格按照 Schema 重新输出合法的 JSON，并且只能包含允许修改的字段。"
                messages.append({"role": "assistant", "content": ai_content})
                messages.append({"role": "user", "content": error_feedback})

            ai_content = locals().get('ai_content', '<未获取到响应>')  # 防止 NameError
            logger.error(f"第 {attempt + 1} 次调用失败，ai_content={ai_content}, 错误: {e}")
            if attempt == max_retries:
                raise


# ==========================================
# 5. 暴露给外部的统一入口
# ==========================================

async def process_ai_task(
        payload: AIRequestPayload,
        db: AsyncSession,
        model_name: str = MODEL
) -> Dict[str, Any]:
    """AI 网关的主处理流程"""
    logger.info(f"开始处理 AI 任务: Target={payload.target_id}, Mode={payload.mode}, Type={payload.data_type}")

    # 1. 提取原始上下文数据
    if payload.data_type == DataType.RASTER:
        context_data = await _extract_raster_data(db, int(payload.target_id))
        modifiable_schema = RasterModifiable.model_json_schema()
    else:
        context_data = await _extract_vector_data(db, str(payload.target_id))
        modifiable_schema = VectorModifiable.model_json_schema()

    original_json_str = context_data.model_dump_json(indent=2)

    # 2. 构建 Prompt
    system_prompt = _build_system_prompt(
        payload.mode,
        payload.data_type,
        payload.language,
        json.dumps(modifiable_schema, ensure_ascii=False)
    )
    user_prompt = (
        f"【原始数据上下文】\n{original_json_str}\n\n"
        f"【用户指令】\n{payload.user_prompt}\n\n"
        f"请使用 {payload.language.value} 语言进行回复。"
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # 3. 调用 AI
    result = await call_llm_with_retry(messages, model_name, payload.mode, payload.data_type)

    # 4. 分析模式直接返回
    if payload.mode == TaskMode.ANALYZE:
        return {
            "status": "success",
            "mode": "analyze",
            "report": result
        }

    # 5. 修改模式
    if payload.mode == TaskMode.MODIFY:
        validated_data = result  # 已经是 RasterModifiable / VectorModifiable

        # ✅ 修复1：只保留 AI 明确返回的非 None 字段，避免覆盖有效数据
        modified_dict = validated_data.model_dump(exclude_none=True)

        if not modified_dict:
            logger.warning("[process_ai_task] AI 返回的可修改字段全为空，放弃写入")
            return {
                "status": "no_change",
                "mode": "modify",
                "message": "AI 未返回任何可修改字段"
            }

        logger.info(f"[process_ai_task] AI 修改内容: {modified_dict}")

        # ── 覆盖模式 ──
        if payload.overwrite:
            if payload.data_type == DataType.RASTER:
                updated = await RasterCRUD.update_raster(
                    db, int(payload.target_id), modified_dict
                )
                if not updated:
                    raise ValueError(f"覆盖失败：找不到 index_id={payload.target_id} 的栅格记录")

            else:  # VECTOR
                layer_crud = LayerCRUD(db)
                updated = await layer_crud.update_layer(
                    UUID(str(payload.target_id)),
                    {"name": modified_dict.get("name")}
                )
                if not updated:
                    raise ValueError(f"覆盖失败：找不到 id={payload.target_id} 的矢量图层")

            # ✅ 修复2：覆盖模式提交事务
            await db.commit()
            logger.info(f"[process_ai_task] 覆盖写入成功: target_id={payload.target_id}")

            return {
                "status": "success",
                "mode": "modify",
                "action": "overwrite",
                "target_id": str(payload.target_id),
                "modified_data": modified_dict
            }

        # ── 新建模式（默认）──
        else:
            if payload.data_type == DataType.RASTER:
                original = await RasterCRUD.get_raster_by_index_id(db, int(payload.target_id))
                if not original:
                    raise ValueError(f"新建失败：找不到 index_id={payload.target_id} 的栅格记录")

                new_name = modified_dict.get("name", original.file_name)
                # 自动补 .tif 后缀
                if not new_name.endswith(".tif"):
                    new_name = f"{new_name}.tif"

                new_meta = {
                    # ✅ 修复3：用处理后的 new_name，其余字段从原始记录复制
                    "file_name": new_name,
                    "index_id": get_next_index_id(),
                    "bundle_id": original.bundle_id,
                    "file_path": original.file_path,   # 共享物理文件，不复制
                    "cog_path": original.cog_path,
                    "crs": original.crs,
                    "bounds": original.bounds,
                    "center": original.center,
                    "width": original.width,
                    "height": original.height,
                    "bands": original.bands,
                    "data_type": original.data_type,
                    "resolution_x": original.resolution_x,
                    "resolution_y": original.resolution_y,
                }
                new_raster = await RasterCRUD.create_raster(db, new_meta)

                # ✅ 修复2：新建模式也要提交事务
                await db.commit()
                logger.info(f"[process_ai_task] 新建 Raster 成功: new_index_id={new_raster.index_id}")

                return {
                    "status": "success",
                    "mode": "modify",
                    "action": "create_new",
                    "new_index_id": new_raster.index_id,
                    "modified_data": modified_dict
                }

            else:  # VECTOR
                layer_crud = LayerCRUD(db)
                original = await layer_crud.get_layer(UUID(str(payload.target_id)))
                if not original:
                    raise ValueError(f"新建失败：找不到 id={payload.target_id} 的矢量图层")

                new_layer = await layer_crud.create_layer(
                    project_id=original.project_id,
                    name=modified_dict.get("name", f"{original.name}_AI修正版"),
                    source_index_id=original.source_raster_index_id
                )

                # ✅ 修复2：新建模式也要提交事务
                await db.commit()
                logger.info(f"[process_ai_task] 新建 Vector Layer 成功: new_layer_id={new_layer.id}")

                return {
                    "status": "success",
                    "mode": "modify",
                    "action": "create_new",
                    "new_layer_id": str(new_layer.id),
                    "modified_data": modified_dict
                }

    # 兜底（理论上不会走到这里）
    logger.error(f"[process_ai_task] 未知的 mode: {payload.mode}")
    raise ValueError(f"未知的任务模式: {payload.mode}")

