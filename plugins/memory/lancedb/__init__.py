"""LanceDB memory plugin — thin shim.

Implementation lives in the standalone hermes-memory-lancedb package.
Install: pip install hermes-memory-lancedb
Repo: https://github.com/andrew-maseko/hermes-memory-lancedb
"""

try:
    from hermes_memory_lancedb import LanceDBMemoryProvider
except ImportError as e:
    raise ImportError(
        "hermes-memory-lancedb is not installed. "
        "Run: pip install hermes-memory-lancedb\n"
        f"Original error: {e}"
    ) from e

__all__ = ["LanceDBMemoryProvider"]
