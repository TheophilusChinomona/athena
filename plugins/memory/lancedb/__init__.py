"""LanceDB memory plugin — MemoryProvider for vector + BM25 hybrid recall.

Wraps the external hermes-memory-lancedb package as a proper MemoryProvider
plugin. Follows the same pattern as holographic and honcho providers.

Config in $HERMES_HOME/config.yaml (profile-scoped):
  memory:
    provider: lancedb

Requires:
  - hermes-memory-lancedb>=1.1.0 (pip install hermes-agent[theo])
  - OPENAI_API_KEY (for embeddings)

The heavy LanceDB logic lives in the hermes-memory-lancedb package.
This plugin is the thin adapter that fits it into the MemoryProvider ABC.
"""

from __future__ import annotations

import importlib
import json
import logging
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)


def _import_lancedb_provider():
    """Lazy import of the external LanceDB provider class.

    Returns the class or None if the package isn't installed.
    Never raises — callers should check for None.
    """
    try:
        from hermes_memory_lancedb import LanceDBMemoryProvider
        return LanceDBMemoryProvider
    except ImportError:
        return None


class LanceDBMemoryPlugin(MemoryProvider):
    """LanceDB vector memory with hybrid BM25+vector recall.

    Delegates all heavy lifting to hermes-memory-lancedb.
    This wrapper handles lifecycle integration with the Hermes plugin system.
    """

    def __init__(self):
        self._inner = None          # hermes_memory_lancedb.LanceDBMemoryProvider instance
        self._inner_class = None    # resolved lazily
        self._init_kwargs = {}      # stored for lazy init

    @property
    def name(self) -> str:
        return "lancedb"

    def is_available(self) -> bool:
        """Check if LanceDB provider can be loaded. No network calls."""
        cls = _import_lancedb_provider()
        if cls is None:
            return False
        # Delegate to the inner provider's own availability check if it has one
        try:
            instance = cls()
            if hasattr(instance, "is_available"):
                return instance.is_available()
            return True
        except Exception:
            return True  # class exists, init may fail later with real config

    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize the inner LanceDB provider."""
        cls = _import_lancedb_provider()
        if cls is None:
            logger.warning(
                "hermes-memory-lancedb is not installed. "
                "Run: pip install hermes-memory-lancedb"
            )
            return

        try:
            self._inner = cls()
            self._init_kwargs = kwargs
            if hasattr(self._inner, "initialize"):
                self._inner.initialize(session_id, **kwargs)
            logger.info("LanceDB memory provider initialized for session %s", session_id)
        except Exception as e:
            logger.warning("LanceDB memory provider init failed: %s", e)
            self._inner = None

    def system_prompt_block(self) -> str:
        if not self._inner:
            return ""
        try:
            if hasattr(self._inner, "system_prompt_block"):
                return self._inner.system_prompt_block()
        except Exception as e:
            logger.debug("LanceDB system_prompt_block failed: %s", e)
        return ""

    def prefetch(self, query: str, *, session_id: str = "") -> str:
        if not self._inner:
            return ""
        try:
            if hasattr(self._inner, "prefetch"):
                return self._inner.prefetch(query, session_id=session_id) or ""
        except Exception as e:
            logger.debug("LanceDB prefetch failed: %s", e)
        return ""

    def queue_prefetch(self, query: str, *, session_id: str = "") -> None:
        if not self._inner:
            return
        try:
            if hasattr(self._inner, "queue_prefetch"):
                self._inner.queue_prefetch(query, session_id=session_id)
        except Exception as e:
            logger.debug("LanceDB queue_prefetch failed: %s", e)

    def sync_turn(self, user_content: str, assistant_content: str, *, session_id: str = "") -> None:
        if not self._inner:
            return
        try:
            if hasattr(self._inner, "sync_turn"):
                self._inner.sync_turn(user_content, assistant_content, session_id=session_id)
        except Exception as e:
            logger.debug("LanceDB sync_turn failed: %s", e)

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        if not self._inner:
            return []
        try:
            if hasattr(self._inner, "get_tool_schemas"):
                return self._inner.get_tool_schemas()
        except Exception as e:
            logger.debug("LanceDB get_tool_schemas failed: %s", e)
        return []

    def handle_tool_call(self, tool_name: str, args: Dict[str, Any], **kwargs) -> str:
        if not self._inner:
            return json.dumps({"error": "LanceDB provider not initialized"})
        try:
            if hasattr(self._inner, "handle_tool_call"):
                return self._inner.handle_tool_call(tool_name, args, **kwargs)
        except Exception as e:
            logger.debug("LanceDB handle_tool_call failed: %s", e)
        return json.dumps({"error": f"LanceDB cannot handle tool {tool_name}"})

    def on_session_end(self, messages: List[Dict[str, Any]]) -> None:
        if not self._inner:
            return
        try:
            if hasattr(self._inner, "on_session_end"):
                self._inner.on_session_end(messages)
        except Exception as e:
            logger.debug("LanceDB on_session_end failed: %s", e)

    def on_pre_compress(self, messages: List[Dict[str, Any]]) -> str:
        if not self._inner:
            return ""
        try:
            if hasattr(self._inner, "on_pre_compress"):
                return self._inner.on_pre_compress(messages) or ""
        except Exception as e:
            logger.debug("LanceDB on_pre_compress failed: %s", e)
        return ""

    def on_memory_write(self, action: str, target: str, content: str) -> None:
        if not self._inner:
            return
        try:
            if hasattr(self._inner, "on_memory_write"):
                self._inner.on_memory_write(action, target, content)
        except Exception as e:
            logger.debug("LanceDB on_memory_write failed: %s", e)

    def shutdown(self) -> None:
        if not self._inner:
            return
        try:
            if hasattr(self._inner, "shutdown"):
                self._inner.shutdown()
        except Exception as e:
            logger.debug("LanceDB shutdown failed: %s", e)
        self._inner = None


# ---------------------------------------------------------------------------
# Plugin entry point
# ---------------------------------------------------------------------------

def register(ctx) -> None:
    """Register the LanceDB memory provider with the plugin system."""
    provider = LanceDBMemoryPlugin()
    ctx.register_memory_provider(provider)
