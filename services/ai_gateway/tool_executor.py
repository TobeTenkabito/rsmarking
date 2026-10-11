import logging
from typing import List, Dict, Any
from sqlalchemy import Numeric, bindparam, cast, column, select, table
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_gateway.tool_executor")


async def execute_vector_query(
        db: AsyncSession,
        layer_id: str,
        args: dict,
        valid_schema: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Query allowed properties using bound JSON keys and generated SQL aliases.
    """
    columns = args.get("selected_columns", [])
    conditions = args.get("filter_conditions", [])
    try:
        limit = max(1, min(int(args.get("limit", 10)), 50))
    except (TypeError, ValueError, OverflowError):
        limit = 10

    # 1. Field allowlist filtering
    safe_columns = list(dict.fromkeys(col for col in columns if col in valid_schema))
    if not safe_columns:
        safe_columns = list(valid_schema.keys())[:5]  # Fallback: return the first 5 fields

    features = table("features", column("properties", JSONB), column("layer_id", UUID(as_uuid=False)))
    select_parts = [
        features.c.properties[bindparam(f"column_{i}", col)].astext.label(f"field_{i}")
        for i, col in enumerate(safe_columns)
    ]
    query = select(*(select_parts or [features.c.properties])).where(
        features.c.layer_id == bindparam("layer_id")
    ).limit(bindparam("limit"))

    # 2. Build a safe parameterized WHERE clause
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
                db_col = cast(features.c.properties[bindparam(f"filter_column_{i}", col)].astext, Numeric)
                try:
                    params[param_name] = float(val) if val else 0.0
                except (TypeError, ValueError, OverflowError):
                    return [{"error": "Numeric filter values must be valid numbers."}]
            else:
                db_col = features.c.properties[bindparam(f"filter_column_{i}", col)].astext
                params[param_name] = f"%{val}%" if op == "like" else str(val)

            value = bindparam(param_name)
            comparisons = {"eq": db_col.__eq__, "gt": db_col.__gt__, "lt": db_col.__lt__, "like": db_col.ilike}
            query = query.where(comparisons[op](value))

    try:
        res = await db.execute(query, params)
        if not safe_columns:
            return [dict(row._mapping) for row in res.all()]
        return [
            {col: row._mapping[f"field_{i}"] for i, col in enumerate(safe_columns)}
            for row in res.all()
        ]
    except Exception as e:
        logger.error(f"Dynamic tool query failed: {e}")
        return [{"error": "Database query execution failed. Check whether filter condition types match."}]
