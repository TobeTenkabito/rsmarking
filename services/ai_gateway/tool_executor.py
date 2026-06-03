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
    Generic attribute-query executor. Guards against SQL injection by validating fields against properties_schema and converting types automatically.
    """
    columns = args.get("selected_columns", [])
    conditions = args.get("filter_conditions", [])
    limit = min(args.get("limit", 10), 50)  # Enforce a maximum return count of 50

    # 1. Field allowlist filtering
    safe_columns = [col for col in columns if col in valid_schema]
    if not safe_columns:
        safe_columns = list(valid_schema.keys())[:5]  # Fallback: return the first 5 fields

    select_parts = [f"properties->>'{col}' as {col}" for col in safe_columns]
    select_clause = ", ".join(select_parts) if select_parts else "properties"

    # 2. Build a safe parameterized WHERE clause
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

            # Cast PostgreSQL JSONB values so comparisons are correct (for example, 2 > 10 does not become a text comparison).
            if col_type in ['int', 'float']:
                db_col = f"(properties->>'{col}')::numeric"
                params[param_name] = float(val) if val else 0.0
            else:
                db_col = f"properties->>'{col}'"
                params[param_name] = f"%{val}%" if op == "like" else str(val)

            where_clauses.append(f"{db_col} {op_map[op]} :{param_name}")

    where_clause = " AND ".join(where_clauses)

    # 3. Execute query
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
        logger.error(f"Dynamic tool query failed: {e}")
        return [{"error": "Database query execution failed. Check whether filter condition types match."}]