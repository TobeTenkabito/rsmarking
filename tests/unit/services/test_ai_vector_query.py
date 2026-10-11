import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.dialects import postgresql

from services.ai_gateway.tool_executor import execute_vector_query

LAYER_ID = "76467ec3-bcef-43d5-9428-f66883b6b151"


def run_query(args, schema, rows=()):
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: rows)))
    result = asyncio.run(execute_vector_query(db, LAYER_ID, args, schema))
    statement, params = db.execute.call_args.args
    compiled = statement.compile(dialect=postgresql.dialect())
    return result, str(compiled), {**compiled.params, **params}


@pytest.mark.parametrize("key", ["owner's name", 'a"; DROP TABLE features; --', "中文 字段", "select", "", "x" * 100])
def test_arbitrary_schema_keys_are_bound_with_generated_aliases(key):
    result, sql, params = run_query(
        {"selected_columns": [key], "filter_conditions": [{"column": key, "operator": "eq", "value": "O'Reilly"}]},
        {key: "str"},
        [SimpleNamespace(_mapping={"field_0": "O'Reilly"})],
    )
    assert "AS field_0" in sql
    if key and key != "select":
        assert key not in sql
    assert "->> %(column_0)s" in sql and "->> %(filter_column_0)s" in sql
    assert params["column_0"] == params["filter_column_0"] == key
    assert params["val_0"] == "O'Reilly"
    assert "O'Reilly" not in sql
    assert result == [{key: "O'Reilly"}]


def test_numeric_like_and_layer_filters_are_parameterized():
    _, sql, params = run_query({
        "selected_columns": ["count", "name", "name", "unknown"],
        "filter_conditions": [
            {"column": "count", "operator": "gt", "value": 10},
            {"column": "name", "operator": "like", "value": "forest' OR 1=1 --"},
            {"column": "unknown", "operator": "eq", "value": 1},
            {"column": "name", "operator": "OR 1=1", "value": "x"},
        ],
        "limit": 500,
    }, {"count": "int", "name": "str"})
    assert " AS NUMERIC) > %(val_0)s" in sql
    assert "ILIKE %(val_1)s" in sql
    assert params["val_0"] == 10.0 and params["val_1"] == "%forest' OR 1=1 --%"
    assert params["layer_id"] == LAYER_ID and params["limit"] == 50
    assert "unknown" not in sql and "OR 1=1" not in sql


@pytest.mark.parametrize("limit, expected", [(-1, 1), ("invalid", 10), (None, 10)])
def test_empty_schema_returns_properties_and_bounds_limit(limit, expected):
    result, sql, params = run_query({"limit": limit}, {}, [SimpleNamespace(_mapping={"properties": {"x": 1}})])
    assert "SELECT features.properties" in sql
    assert params["limit"] == expected
    assert result == [{"properties": {"x": 1}}]


def test_database_failure_returns_controlled_tool_error():
    db = SimpleNamespace(execute=AsyncMock(side_effect=RuntimeError("database unavailable")))
    result = asyncio.run(execute_vector_query(db, LAYER_ID, {}, {"name": "str"}))
    assert "error" in result[0] and "database unavailable" not in result[0]["error"]


def test_invalid_numeric_filter_never_reaches_database():
    db = SimpleNamespace(execute=AsyncMock())
    result = asyncio.run(execute_vector_query(db, LAYER_ID, {
        "filter_conditions": [{"column": "count", "operator": "gt", "value": "invalid"}],
    }, {"count": "int"}))
    assert "error" in result[0]
    db.execute.assert_not_awaited()
