"""Small polling projection, scoped to one request and safe to display while running."""

from . import agent_state_store as store


def get_agent_progress(session_id: str, request_id: str) -> dict:
    state = store.load_state(session_id)
    pending = state.get("pending") if state else None
    if pending and pending.get("request_id") == request_id:
        workflow = pending.get("workflow") or {}
        events = workflow.get("events") or []
        event = events[-1] if events else {}
        activity = pending.get("activity") or {}
        if event.get("agent") and event["agent"] != activity.get("role"):
            activity = {}
        task_id = activity.get("task_id") or event.get("task_id", "")
        tasks = (workflow.get("plan") or {}).get("tasks", [])
        task = next((task for task in tasks if task["id"] == task_id), {})
        return {
            "request_id": request_id,
            "status": "interrupted" if pending.get("failure") else "running",
            "stage": workflow.get("stage", "executing"),
            "role": activity.get("role") or event.get("agent", "single"),
            "phase": activity.get("phase", "preparing"),
            "tool": activity.get("tool", ""),
            "task_title": task.get("title", ""),
            "model_calls": workflow.get("model_calls", 0),
            "tool_calls": workflow.get("tool_calls", len(pending.get("steps", []))),
            "completed_tasks": len(workflow.get("completed_tasks", {})),
            "total_tasks": len(tasks),
            "round": workflow.get("round", 0),
            "updated_at": state.get("updated_at"),
        }
    response = store.load_request_response(session_id, request_id)
    if response:
        workflow = response.get("workflow") or {}
        return {
            "request_id": request_id,
            "status": response["status"],
            "stage": workflow.get("stage", "complete"),
            "phase": "complete",
            "model_calls": workflow.get("model_calls", 0),
            "tool_calls": workflow.get("tool_calls", len(response.get("steps", []))),
        }
    return {"request_id": request_id, "status": "waiting", "phase": "preparing"}
