import logging
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_gateway.tool_executor")


async def execute_vector_query(
        db: AsyncSession,
        layer_id: str,
        args: dict,
        valid_schema: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    通用属性查询执行器。防范 SQL 注入，通过 properties_schema 验证字段并自动转换类型。
    """
    columns = args.get("selected_columns", [])
    conditions = args.get("filter_conditions", [])
    limit = min(args.get("limit", 10), 50)  # 强制限制最大返回 50 条

    # 1. 字段白名单过滤
    safe_columns = [col for col in columns if col in valid_schema]
    if not safe_columns:
        safe_columns = list(valid_schema.keys())[:5]  # 兜底：返回前5个字段

    select_parts = [f"properties->>'{col}' as {col}" for col in safe_columns]
    select_clause = ", ".join(select_parts) if select_parts else "properties"

    # 2. 构建安全的参数化 WHERE 子句
    where_clauses = ["layer_id = :layer_id"]
    params: Dict[str, Any] = {"layer_id": str(layer_id), "limit": limit}

    op_map = {"eq": "=", "gt": ">", "lt": "<", "like": "ILIKE"}

    for i, cond in enumerate(conditions):
        col = cond.get("column")
        op = cond.get("operator")
        val = cond.get("value")

        if col in valid_schema and op in op_map:
            param_name = f"val_{i}"
            col_type = valid_schema[col]

            # 针对 PostgreSQL JSONB 的类型强转，确保比较逻辑正确 (例如 2 > 10 不会变成文本比较)
            if col_type in ['int', 'float']:
                db_col = f"(properties->>'{col}')::numeric"
                params[param_name] = float(val) if val else 0.0
            else:
                db_col = f"properties->>'{col}'"
                params[param_name] = f"%{val}%" if op == "like" else str(val)

            where_clauses.append(f"{db_col} {op_map[op]} :{param_name}")

    where_clause = " AND ".join(where_clauses)

    # 3. 执行查询
    query_sql = text(f"""
        SELECT {select_clause} 
        FROM features 
        WHERE {where_clause} 
        LIMIT :limit
    """)

    try:
        res = await db.execute(query_sql, params)
        return [dict(row._mapping) for row in res.all()]
    except Exception as e:
        logger.error(f"动态工具查询失败: {e}")
        return [{"error": "数据库查询执行异常，请检查过滤条件类型是否匹配"}]