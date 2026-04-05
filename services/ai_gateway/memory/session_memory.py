"""
session_memory.py
多轮对话记忆管理 —— 基于内存的 LRU 缓存，可替换为 Redis 后端
"""
import time
import logging
from collections import OrderedDict
from typing import List, Dict, Any, Optional

logger = logging.getLogger("ai_gateway.memory.session_memory")

# 单条消息结构
# {"role": "user"/"assistant"/"tool", "content": "...", "ts": 1234567890}

_MAX_SESSIONS   = 500    # 最多同时保存的会话数
_MAX_TURNS      = 20     # 每个会话最多保留的消息轮数（user+assistant 各算1条）
_TTL_SECONDS    = 3600   # 会话过期时间（1小时无活动自动清除）


class SessionMemoryStore:
    """
    线程安全的内存会话存储（单进程适用）。
    生产环境建议替换为 RedisSessionMemoryStore（接口相同）。
    """

    def __init__(
        self,
        max_sessions: int = _MAX_SESSIONS,
        max_turns: int = _MAX_TURNS,
        ttl: int = _TTL_SECONDS,
    ):
        self._store: OrderedDict[str, Dict] = OrderedDict()
        self.max_sessions = max_sessions
        self.max_turns = max_turns
        self.ttl = ttl

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        获取会话历史消息列表（已过滤过期会话）。
        返回格式与 litellm / openai messages 兼容：
        [{"role": "user", "content": "..."}, ...]
        """
        session = self._get_session(session_id)
        if session is None:
            return []
        # 只返回 role/content，去掉内部 ts 字段
        return [{"role": m["role"], "content": m["content"]} for m in session["messages"]]

    def append(self, session_id: str, role: str, content: str) -> None:
        """追加一条消息到会话历史"""
        session = self._get_or_create_session(session_id)
        session["messages"].append({
            "role": role,
            "content": content,
            "ts": time.time(),
        })
        session["last_active"] = time.time()
        # 超出最大轮数时，保留 system 消息 + 最新 (max_turns-1) 条
        non_system = [m for m in session["messages"] if m["role"] != "system"]
        system_msgs = [m for m in session["messages"] if m["role"] == "system"]
        if len(non_system) > self.max_turns:
            non_system = non_system[-self.max_turns:]
        session["messages"] = system_msgs + non_system
        self._store.move_to_end(session_id)

    def set_system(self, session_id: str, system_content: str) -> None:
        """设置/更新会话的 system prompt（始终保持在首位）"""
        session = self._get_or_create_session(session_id)
        session["messages"] = [m for m in session["messages"] if m["role"] != "system"]
        session["messages"].insert(0, {
            "role": "system",
            "content": system_content,
            "ts": time.time(),
        })

    def clear(self, session_id: str) -> None:
        """清除指定会话"""
        self._store.pop(session_id, None)
        logger.info(f"[SessionMemory] 会话已清除: {session_id}")

    def stats(self) -> Dict[str, Any]:
        """返回当前存储状态（用于监控）"""
        return {
            "active_sessions": len(self._store),
            "max_sessions": self.max_sessions,
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _get_session(self, session_id: str) -> Optional[Dict]:
        session = self._store.get(session_id)
        if session is None:
            return None
        # TTL 检查
        if time.time() - session["last_active"] > self.ttl:
            self._store.pop(session_id, None)
            logger.debug(f"[SessionMemory] 会话过期已清除: {session_id}")
            return None
        return session

    def _get_or_create_session(self, session_id: str) -> Dict:
        session = self._get_session(session_id)
        if session is not None:
            return session
        # LRU 淘汰
        if len(self._store) >= self.max_sessions:
            evicted_id, _ = self._store.popitem(last=False)
            logger.debug(f"[SessionMemory] LRU 淘汰会话: {evicted_id}")
        new_session = {"messages": [], "last_active": time.time()}
        self._store[session_id] = new_session
        return new_session


# 全局单例（在 main.py lifespan 中初始化后注入 app.state）
_default_store = SessionMemoryStore()


def get_session_store() -> SessionMemoryStore:
    return _default_store
